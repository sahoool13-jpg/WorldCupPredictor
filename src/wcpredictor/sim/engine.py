"""Tournament Monte Carlo (plan.md §19).

Seeds every iteration from the **true current state** (real played results banked, fixed) and
simulates only the remaining fixtures, applying group tiebreakers (§3.2), the third-place
ranking (§3.3), the committed Annex C R32 assignment (§19.1) and the bracket (§19.4) to
produce advancement / title probabilities. Completed results are never re-simulated.
"""
from __future__ import annotations

import bisect
import json
import random
from collections import defaultdict
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..data.errors import DataError
from ..data.model import Match, Status, slugify
from ..model.dixon_coles import scoreline_matrix
from ..model.etp import knockout_home_advance_prob, penalty_home_prob
from ..model.lambdas import lambdas
from . import bracket as bracket_mod
from . import standings
from .annex_c import assign_thirds

_ROOT = Path(__file__).resolve().parents[3]
ROUNDS = ["R32", "R16", "QF", "SF", "F", "title"]


# ----------------------------------------------------------------------------- inputs
def _groups() -> Dict[str, List[str]]:
    return json.loads((_ROOT / "data" / "reference" / "groups.json").read_text())["groups"]


def partition(matches: List[Match], groups: Dict[str, List[str]]):
    """Split the resolved fixtures into real played group results (fixed) and remaining
    group fixtures, by group."""
    played: Dict[str, list] = {g: [] for g in groups}
    remaining: Dict[str, list] = {g: [] for g in groups}
    for m in matches:
        if m.group is None:
            continue  # knockout placeholder
        if m.status is Status.FINAL:
            played[m.group].append((m.home, m.away, m.home_goals, m.away_goals))
        else:
            remaining[m.group].append((m.home, m.away))
    return played, remaining


# ----------------------------------------------------------------------------- samplers
def _build_cdf(home: str, away: str, ratings, gparams, gconf, gh: float, ga: float
               ) -> List[Tuple[float, int, int]]:
    lh, la = lambdas(ratings[home], ratings[away], gparams, gh, ga)
    m = scoreline_matrix(lh, la, gparams["rho"], gconf["g_max"])
    cdf, cum = [], 0.0
    for i, row in enumerate(m):
        for j, p in enumerate(row):
            cum += p
            cdf.append((cum, i, j))
    return cdf


class Sim:
    def __init__(self, matches, ratings, gparams, gconf, hosts, ko_specs, groups=None,
                 ko_results=None, details=None):
        self.groups = groups or _groups()
        self.matches = list(matches)
        self.played, remaining = partition(matches, self.groups)
        self.ratings, self.gparams, self.gconf, self.hosts = ratings, gparams, gconf, hosts
        self.ko_specs = ko_specs
        # full per-team RatingDetail (prior/elo*/form/squad/…) for the "why this %?" explainer
        # (plan.md §22). Optional — descriptive only, never an odds input.
        self.details = details
        # completed knockout ties: real, fixed advancers bound to bracket slots by team-pair
        # (plan.md §21). Pinned, never re-simulated.
        self.ko_results = list(ko_results or [])
        self.pinned = {kr.pair: kr.winner for kr in self.ko_results}
        # host advantage: a tapered log-lambda boost for host nations only (plan.md host fix)
        self.host_boost = gconf.get("host_log_boost", 0.0)
        self.host_taper = gconf.get("host_taper", {})
        # precompute a scoreline CDF per remaining (group-round) fixture
        gt = self.host_taper.get("group", 1.0)
        self.remaining = {g: [(h, a, _build_cdf(h, a, ratings, gparams, gconf,
                                                self._gamma(h, gt), self._gamma(a, gt)))
                              for (h, a) in fixtures]
                          for g, fixtures in remaining.items()}
        self._validate_pins()

    def _gamma(self, team: str, taper: float) -> float:
        return self.host_boost * taper if team in self.hosts else 0.0

    @lru_cache(maxsize=None)
    def _p_adv(self, t1: str, t2: str, rnd: str) -> float:
        tp = self.host_taper.get(rnd, 0.0)
        lh, la = lambdas(self.ratings[t1], self.ratings[t2], self.gparams,
                         self._gamma(t1, tp), self._gamma(t2, tp))
        pen = penalty_home_prob(self.ratings[t1], self.ratings[t2], self.gparams,
                                self.gconf["pen_slope"])
        return knockout_home_advance_prob(lh, la, self.gparams["rho"], pen,
                                          self.gconf["et_frac"], self.gconf["g_max"])

    def _winner(self, rng, t1: str, t2: str, rnd: str) -> str:
        return t1 if rng.random() < self._p_adv(t1, t2, rnd) else t2

    def _group_results(self, rng):
        gr, thirds = {}, []
        for g, teams in self.groups.items():
            results = list(self.played[g])
            for h, a, cdf in self.remaining[g]:
                x = rng.random()
                _, i, j = cdf[bisect.bisect_left(cdf, (x, -1, -1))]
                results.append((h, a, i, j))
            order, s = standings.rank_group(teams, results, rng)
            gr[g] = {"1": order[0], "2": order[1], "3": order[2]}
            t3 = order[2]
            thirds.append({"group": g, "team": t3, "pts": s[t3]["pts"],
                           "gd": s[t3]["gd"], "gf": s[t3]["gf"]})
        return gr, thirds

    def _resolve_bracket(self, rng):
        """One full bracket resolution from the current real state: group sim + thirds + Annex C
        + the knockout tree, with completed KO ties pinned to their real advancers."""
        gr, thirds = self._group_results(rng)
        qualified = standings.rank_thirds(thirds, self.ratings, rng)[:8]
        assign = assign_thirds([d["group"] for d in qualified])
        return bracket_mod.simulate(gr, assign, self.ko_specs,
                                    lambda a, b, rnd: self._winner(rng, a, b, rnd),
                                    pinned=self.pinned)

    def once(self, rng):
        return self._resolve_bracket(rng)["reach"]

    def _groups_complete(self) -> bool:
        return all(not fixtures for fixtures in self.remaining.values())

    def _validate_pins(self):
        """Strict (D6b): a real knockout result must bind to an actual bracket slot. Pins are
        only meaningful once the group stage is decided (the bracket pairings are fixed); a
        pinned pair that never appears as a slot is drift/unreachable -> raise."""
        if not self.pinned:
            return
        if not self._groups_complete():
            raise DataError(
                "knockout results supplied before the group stage is complete: the bracket "
                "pairings are not yet fixed, so a real KO tie cannot be bound to a slot."
            )
        out = self._resolve_bracket(random.Random(0))
        missing = set(self.pinned) - out["pinned_used"]
        if missing:
            pairs = [tuple(sorted(p)) for p in missing]
            raise DataError(
                f"knockout result(s) {pairs} did not match any bracket slot for the current "
                f"qualified field — unreachable pairing or stale data."
            )

    def bracket_state(self):
        """The realized knockout tree from the current real state (deterministic once the group
        stage is complete): per-slot round, the two teams, the advancer, and whether that tie is
        a real completed result. Empty until the bracket is determined. For the dashboard."""
        if not self._groups_complete():
            return []
        return self._resolve_bracket(random.Random(0))["slots"]

    def run(self, n: int, seed: int):
        rng = random.Random(seed)
        counts = defaultdict(lambda: {r: 0 for r in ROUNDS})
        for _ in range(n):
            for team, rounds in self.once(rng).items():
                for r in rounds:
                    counts[team][r] += 1
        return {t: {r: c[r] / n for r in ROUNDS} for t, c in counts.items()}


# ----------------------------------------------------------------------------- driver
def build_sim(as_of: datetime, live: bool, espn_start=None, espn_end=None):
    import dataclasses

    from ..data import http, openfootball as of_mod, pipeline
    from ..data.sources import DEFAULT_ESPN
    from ..data.teams import TeamRegistry
    from ..ratings.engine import compute_ratings, load_config as load_rconf
    from ..ratings.prior import load_prior
    from ..model.calibrate import load_params

    from ..data.knockout import extract_knockouts

    reg = TeamRegistry.load()
    groups_obj, matches_obj = of_mod.fetch_raw(http.get_json)
    _, fixtures = of_mod.load_structure(groups_obj, matches_obj, reg)
    ko_results = []
    if live:
        espn_cfg = DEFAULT_ESPN
        if espn_start:
            espn_cfg = dataclasses.replace(espn_cfg, window_start=espn_start)
        if espn_end:
            espn_cfg = dataclasses.replace(espn_cfg, window_end=espn_end)
        overlay = pipeline.fetch_overlay(http.get_json, reg, espn_cfg)
        group_overlay, ko_overlay = pipeline.split_overlay(fixtures, overlay)
        matches = pipeline.reconcile(fixtures, group_overlay, as_of)
        group_pairs = {f.pair for f in fixtures if f.group is not None and not f.is_placeholder}
        ko_results = extract_knockouts(group_pairs, ko_overlay, as_of)
    else:
        matches = _matches_from_openfootball(fixtures, as_of)
    rconf = load_rconf()
    # ratings learn ONLY from played GROUP matches (D6a: frozen post-group; KO re-seeds the
    # bracket, not Elo). compute_ratings already keys on m.group, so KO matches don't feed it.
    details = compute_ratings(matches, as_of, load_prior(), rconf)
    ratings = {t: d.rating for t, d in details.items()}
    gparams = load_params()
    gconf = json.loads((_ROOT / "configs" / "goal_model.json").read_text())
    # bracket WIRING from the committed static reference, NOT the live feed — openfootball
    # mutates KO refs into concrete team names as groups clinch (e.g. 1E->Germany), which breaks
    # resolution. Group results stay live; only the tree is frozen (plan.md §19.4).
    specs = bracket_mod.load_bracket()
    return Sim(matches, ratings, gparams, gconf, set(rconf["hosts"]), specs,
               ko_results=ko_results, details=details)


def _matches_from_openfootball(fixtures, as_of):
    """Offline fallback (no ESPN): treat openfootball's own scored group games as FINAL."""
    out = []
    for f in fixtures:
        if f.group is None:
            continue
        if f.of_score is not None and f.kickoff_utc <= as_of:
            out.append(Match(f.match_id, f.round, f.group, f.home, f.away, f.home_id,
                             f.away_id, f.kickoff_utc, Status.FINAL,
                             f.of_score[0], f.of_score[1], "openfootball"))
        else:
            out.append(Match(f.match_id, f.round, f.group, f.home, f.away, f.home_id,
                             f.away_id, f.kickoff_utc, Status.SCHEDULED))
    return out


def main(argv=None) -> int:
    import argparse
    import dataclasses
    p = argparse.ArgumentParser(description="WC-2026 tournament Monte Carlo")
    p.add_argument("--as-of"); p.add_argument("--live", action="store_true")
    p.add_argument("--espn-start"); p.add_argument("--espn-end")
    p.add_argument("--n", type=int, default=50000); p.add_argument("--seed", type=int, default=2026)
    p.add_argument("--top", type=int, default=15)
    args = p.parse_args(argv)
    as_of = (datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
             if args.as_of else datetime.now(timezone.utc))
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)

    sim = build_sim(as_of, args.live, args.espn_start, args.espn_end)
    probs = sim.run(args.n, args.seed)
    ranked = sorted(probs.items(), key=lambda kv: -kv[1]["title"])
    print(f"title odds  as_of={as_of.isoformat()}  n={args.n}  seed={args.seed}")
    print(f"{'#':>2}  {'team':<22} {'title':>6} {'final':>6} {'SF':>6} {'QF':>6} {'R16':>6} {'adv':>6}")
    for i, (t, p) in enumerate(ranked[:args.top], 1):
        print(f"{i:2}. {t:<22} {p['title']*100:5.1f}% {p['F']*100:5.1f}% {p['SF']*100:5.1f}% "
              f"{p['QF']*100:5.1f}% {p['R16']*100:5.1f}% {p['R32']*100:5.1f}%")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
