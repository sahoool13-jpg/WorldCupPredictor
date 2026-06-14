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



def build_payload(sim, probs, *, n_sims: int, seed: int, as_of: datetime,
                  source: dict, prev: Optional[dict] = None) -> dict:
    group_of = {t: g for g, teams in sim.groups.items() for t in teams}
    prev_title = {r["team"]: r["title"] for r in (prev or {}).get("title_odds", [])}
    finals = [m for m in sim.matches if m.status is Status.FINAL and m.group is not None]
    zero = {"title": 0.0, **{k: 0.0 for k in REACH_KEYS}}

    title_odds = []
    for team in group_of:  # all 48 teams (a team absent from the sim never advanced -> 0%)
        p = probs.get(team, zero)
        title = round(p["title"], 5)
        title_odds.append({
            "team": team, "group": group_of.get(team),
            "title": title,
            "title_delta": round(title - prev_title.get(team, title), 5),
            "reach": {k: round(p[k], 5) for k in REACH_KEYS},
            "status": _status(p["R32"]),
        })
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
    # last 5 completed matches, most-recent first (point-in-time: finals are FINAL & kickoff<=as_of)
    recent_results = [{"date": m.kickoff_utc.date().isoformat(),
                       "home": m.home, "away": m.away,
                       "home_goals": m.home_goals, "away_goals": m.away_goals}
                      for m in reversed(by_kickoff[-5:])]

    return {
        "meta": {
            "as_of": as_of.isoformat(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "n_sims": n_sims, "seed": seed, "source": source,
            "n_played": len(finals), "matches_reflected": reflected,
        },
        "title_odds": title_odds,
        "movers": _movers(title_odds),
        "recent_results": recent_results,
        "groups": groups,
    }
