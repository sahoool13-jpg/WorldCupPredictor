"""Phase-2 ratings engine (plan.md §17): blend an Elo base (prior + in-tournament,
shrinkage-weighted) with recent form and a squad proxy into one transparent per-team rating.

Point-in-time (CRITICAL, §17.1): only played matches (FINAL, kickoff <= as_of) are folded
in; a FINAL dated after as_of RAISES. The engine never sees pending/simulated fixtures.
"""
from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from ..data.errors import FutureResultLeak
from ..data.model import Match, Status
from . import elo

_CONFIG = Path(__file__).resolve().parents[3] / "configs" / "ratings.json"


def load_config(path: Path = _CONFIG) -> dict:
    return json.loads(path.read_text())


@dataclass
class RatingDetail:
    team: str
    prior: float
    elo_live: float
    n: int                 # played matches at as_of
    w_live: float
    elo_star: float        # shrinkage blend of prior <-> live
    form: float            # mean (actual - expected) over the last form_window matches
    squad: float           # D2-squad: defaults to prior
    z_elo: float = 0.0
    z_form: float = 0.0
    z_squad: float = 0.0
    blend_z: float = 0.0   # the §17.4 weighted z-blend
    rating: float = 0.0    # blend_z re-expressed on the Elo scale (readable)

    def explain(self) -> dict:
        return {
            "team": self.team, "rating": round(self.rating, 1),
            "prior": round(self.prior, 1), "elo_live": round(self.elo_live, 1),
            "n_played": self.n, "w_live": round(self.w_live, 3),
            "elo_star": round(self.elo_star, 1), "form": round(self.form, 3),
            "squad": round(self.squad, 1),
            "contrib": {"elo": round(self.z_elo, 3), "form": round(self.z_form, 3),
                        "squad": round(self.z_squad, 3)},
        }


def _played(matches: List[Match], prior: Dict[str, float], as_of: datetime) -> List[Match]:
    out = []
    for m in matches:
        if m.status is not Status.FINAL:
            continue
        if m.home not in prior or m.away not in prior:
            continue  # placeholder / non-finalist
        if m.kickoff_utc > as_of:  # defense in depth (plan.md §4 / §17.1)
            raise FutureResultLeak(
                f"ratings got a FINAL after as_of: {m.home} v {m.away} "
                f"{m.kickoff_utc.isoformat()} > {as_of.isoformat()}")
        out.append(m)
    return sorted(out, key=lambda x: x.kickoff_utc)


def _zscores(values: Dict[str, float]) -> Dict[str, float]:
    xs = list(values.values())
    mu = statistics.fmean(xs)
    sd = statistics.pstdev(xs)
    if sd == 0:
        return {k: 0.0 for k in values}
    return {k: (v - mu) / sd for k, v in values.items()}


def compute_ratings(matches: List[Match], as_of: datetime, prior: Dict[str, float],
                    config: dict) -> Dict[str, RatingDetail]:
    hosts: Set[str] = set(config.get("hosts", []))
    k, home_adv = config["k"], config["home_adv"]
    k_shrink, window = config["k_shrink"], int(config["form_window"])
    w = config["weights"]

    elo_live = dict(prior)
    n_played: Dict[str, int] = {t: 0 for t in prior}
    form_log: Dict[str, list] = {t: [] for t in prior}

    for m in _played(matches, prior, as_of):
        h, a = m.home, m.away
        ha = home_adv if h in hosts else 0.0
        aa = home_adv if a in hosts else 0.0
        sa, gd = elo.score_of(m.home_goals, m.away_goals)
        ea = elo.expected_score(elo_live[h] + ha, elo_live[a] + aa)
        form_log[h].append(sa - ea)
        form_log[a].append((1.0 - sa) - (1.0 - ea))
        elo_live[h], elo_live[a] = elo.update_one(
            elo_live[h], elo_live[a], sa, gd, k, home_adv_a=ha, home_adv_b=aa)
        n_played[h] += 1
        n_played[a] += 1

    details: Dict[str, RatingDetail] = {}
    for t in prior:
        n = n_played[t]
        w_live = n / (n + k_shrink) if (n + k_shrink) > 0 else 0.0
        elo_star = w_live * elo_live[t] + (1.0 - w_live) * prior[t]
        recent = form_log[t][-window:]
        form = statistics.fmean(recent) if recent else 0.0
        details[t] = RatingDetail(team=t, prior=prior[t], elo_live=elo_live[t], n=n,
                                  w_live=w_live, elo_star=elo_star, form=form, squad=prior[t])

    z_elo = _zscores({t: d.elo_star for t, d in details.items()})
    z_form = _zscores({t: d.form for t, d in details.items()})
    z_squad = _zscores({t: d.squad for t, d in details.items()})
    elo_star_vals = [d.elo_star for d in details.values()]
    mu, sd = statistics.fmean(elo_star_vals), statistics.pstdev(elo_star_vals)
    for t, d in details.items():
        d.z_elo, d.z_form, d.z_squad = z_elo[t], z_form[t], z_squad[t]
        d.blend_z = w["elo"] * d.z_elo + w["form"] * d.z_form + w["squad"] * d.z_squad
        d.rating = mu + sd * d.blend_z  # readable Elo-scale rendering of the blend
    return details


def ranked(details: Dict[str, RatingDetail]) -> List[RatingDetail]:
    return sorted(details.values(), key=lambda d: -d.rating)


def main(argv=None) -> int:
    import argparse
    import dataclasses
    from datetime import timezone

    from ..data import pipeline
    from ..data.sources import DEFAULT_ESPN
    from .prior import load_prior

    p = argparse.ArgumentParser(description="Compute WC-2026 team strength ratings")
    p.add_argument("--as-of", help="ISO instant (default: now, UTC)")
    p.add_argument("--espn-start"); p.add_argument("--espn-end")
    p.add_argument("--top", type=int, default=15)
    p.add_argument("--prior-only", action="store_true",
                   help="skip live fetch; show the pre-tournament prior ranking")
    args = p.parse_args(argv)

    as_of = (datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
             if args.as_of else datetime.now(timezone.utc))
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)

    prior = load_prior()
    config = load_config()
    if args.prior_only:
        matches: List[Match] = []
    else:
        espn_cfg = DEFAULT_ESPN
        if args.espn_start:
            espn_cfg = dataclasses.replace(espn_cfg, window_start=args.espn_start)
        if args.espn_end:
            espn_cfg = dataclasses.replace(espn_cfg, window_end=args.espn_end)
        matches = pipeline.run(as_of=as_of, espn_cfg=espn_cfg)

    details = compute_ratings(matches, as_of, prior, config)
    n_final = sum(1 for m in matches if m.status is Status.FINAL)
    print(f"ratings as_of={as_of.isoformat()}  played={n_final}  (blend weights={config['weights']})")
    print(f"{'#':>2}  {'team':<22} {'rating':>7} {'elo*':>7} {'prior':>7} {'n':>2} {'form':>6}")
    for i, d in enumerate(ranked(details)[:args.top], 1):
        print(f"{i:2}. {d.team:<22} {d.rating:7.1f} {d.elo_star:7.1f} {d.prior:7.1f} "
              f"{d.n:2d} {d.form:+6.2f}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
