"""Build the dashboard data contract `latest.json` (plan.md §20.2).

Pure/deterministic given the sim result + ratings/state. `title_delta` is computed against the
previous committed payload (matched by team); with a **fixed RNG seed** and unchanged inputs the
odds are byte-identical, so an unchanged run yields `title_delta == 0` for every team — every
nonzero delta is a real move.
"""
from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Optional

from ..data.model import Status
from ..model.lambdas import lambdas
from ..sim import standings

REACH_KEYS = ["R32", "R16", "QF", "SF", "F"]


def _status(p_adv: float) -> str:
    if p_adv >= 0.99999:
        return "through"
    if p_adv <= 1e-9:
        return "eliminated"
    return "alive"


def _movers(title_odds: list, n: int = 3) -> dict:
    """Top-n risers/fallers by title_delta (reusing the already-computed deltas). Both lists
    are EMPTY when nothing moved (the fixed-seed between-matchday state)."""
    moved = [r for r in title_odds if abs(r["title_delta"]) >= 1e-9]
    pick = lambda rows: [{"team": r["team"], "group": r["group"], "title_delta": r["title_delta"]}
                         for r in rows[:n]]
    risers = sorted((r for r in moved if r["title_delta"] > 0), key=lambda r: -r["title_delta"])
    fallers = sorted((r for r in moved if r["title_delta"] < 0), key=lambda r: r["title_delta"])
    return {"risers": pick(risers), "fallers": pick(fallers)}



def _why_map(sim) -> dict:
    """The "why this %?" explainer per team (plan.md §22, D7: all 48, λ-only): the rating
    breakdown (already computed by the ratings engine) + this team's attack/defence goal
    expectation vs an *average* opponent at neutral + the host-edge flag. Read-only/descriptive
    — never an odds input, so it can't perturb the fixed-seed deltas. Empty (block omitted) when
    the sim wasn't given rating details (graceful degrade)."""
    details = getattr(sim, "details", None)
    if not details:
        return {}
    ratings = sim.ratings
    avg = sum(ratings.values()) / len(ratings)
    gp = sim.gparams
    out = {}
    for t, d in details.items():
        atk, dfn = lambdas(ratings[t], avg, gp, 0.0, 0.0)  # neutral vs an average side
        out[t] = {
            "rating": {"blended": round(d.rating, 1), "prior": round(d.prior, 1),
                       "elo_live": round(d.elo_live, 1), "form_delta": round(d.form, 3),
                       "squad_delta": round(d.squad, 1), "w_live": round(d.w_live, 3),
                       "n_played": d.n},
            "goals": {"attack_lambda": round(atk, 2), "defence_lambda": round(dfn, 2),
                      "host_edge": t in sim.hosts},
        }
    return out


def build_payload(sim, probs, *, n_sims: int, seed: int, as_of: datetime,
                  source: dict, prev: Optional[dict] = None) -> dict:
    group_of = {t: g for g, teams in sim.groups.items() for t in teams}
    prev_title = {r["team"]: r["title"] for r in (prev or {}).get("title_odds", [])}
    finals = [m for m in sim.matches if m.status is Status.FINAL and m.group is not None]
    zero = {"title": 0.0, **{k: 0.0 for k in REACH_KEYS}}
    why = _why_map(sim)

    title_odds = []
    for team in group_of:  # all 48 teams (a team absent from the sim never advanced -> 0%)
        p = probs.get(team, zero)
        title = round(p["title"], 5)
        row = {
            "team": team, "group": group_of.get(team),
            "title": title,
            "title_delta": round(title - prev_title.get(team, title), 5),
            "reach": {k: round(p[k], 5) for k in REACH_KEYS},
            "status": _status(p["R32"]),
        }
        if team in why:
            row["why"] = why[team]
        title_odds.append(row)
    title_odds.sort(key=lambda r: (-r["title"], r["team"]))

    groups = []
    for g, teams in sim.groups.items():
        played = [(m.home, m.away, m.home_goals, m.away_goals) for m in finals if m.group == g]
        tbl = standings.table(teams, played)
        order, _ = standings.rank_group(teams, played, random.Random(seed))
        groups.append({"group": g, "table": [
            {"team": t, "pld": tbl[t]["pld"], "pts": tbl[t]["pts"],
             "gd": tbl[t]["gd"], "gf": tbl[t]["gf"],
             "status": _status(probs.get(t, {}).get("R32", 0.0))}
            for t in order]})

    by_kickoff = sorted(finals, key=lambda x: x.kickoff_utc)
    reflected = [{"date": m.kickoff_utc.date().isoformat(), "group": m.group,
                  "home": m.home, "hg": m.home_goals, "away": m.away, "ag": m.away_goals}
                 for m in by_kickoff]

    # the live knockout tree + completed KO ties (plan.md §21). Empty until the bracket is
    # determined (group stage complete). Completed ties carry their real, fixed result.
    bracket = _bracket_block(sim)

    # recent results ticker: group + knockout finals, newest first, last 5 (point-in-time —
    # both streams are FINAL with kickoff <= as_of).
    played = [(m.kickoff_utc, m.home, m.away, m.home_goals, m.away_goals) for m in finals]
    played += [(k.kickoff_utc, k.home, k.away, k.home_goals, k.away_goals) for k in sim.ko_results]
    played.sort(key=lambda x: x[0])
    recent_results = [{"date": ko.date().isoformat(), "home": h, "away": a,
                       "home_goals": hg, "away_goals": ag}
                      for (ko, h, a, hg, ag) in reversed(played[-5:])]

    return {
        "meta": {
            "as_of": as_of.isoformat(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "n_sims": n_sims, "seed": seed, "source": source,
            "n_played": len(finals), "n_ko_played": len(sim.ko_results),
            "matches_reflected": reflected,
        },
        "title_odds": title_odds,
        "movers": _movers(title_odds),
        "recent_results": recent_results,
        "groups": groups,
        "bracket": bracket,
    }


def _bracket_block(sim) -> list:
    """Per-slot knockout tree from the sim's realized bracket (deterministic once groups are
    complete): round, the two teams, the advancer, and whether the tie is a real completed
    result. ``result`` carries the displayed scoreline for pinned (real) ties, else null."""
    slots = sim.bracket_state()
    if not slots:
        return []
    ko_by_pair = {k.pair: k for k in sim.ko_results}
    out = []
    for s in slots:
        kr = ko_by_pair.get(frozenset((s["t1"], s["t2"])))
        out.append({
            "round": s["round"], "num": s["num"],
            "t1": s["t1"], "t2": s["t2"],
            "winner": s["winner"], "played": bool(s["pinned"]),
            "result": (None if kr is None else
                       {"home": kr.home, "away": kr.away,
                        "home_goals": kr.home_goals, "away_goals": kr.away_goals}),
        })
    return out
