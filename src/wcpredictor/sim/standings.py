"""Group tables, group ranking (§3.2), and third-place ranking (§3.3).

A "result" is a tuple ``(home, away, home_goals, away_goals)`` — real (fixed) or simulated.
Tiebreakers fail-soft to **seeded lots** where cards would be needed (D-cards), never silent.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

Result = Tuple[str, str, int, int]


def table(teams: List[str], matches: List[Result]) -> Dict[str, dict]:
    s = {t: {"pts": 0, "gf": 0, "ga": 0, "gd": 0, "pld": 0} for t in teams}
    for h, a, hg, ag in matches:
        s[h]["gf"] += hg; s[h]["ga"] += ag; s[h]["pld"] += 1
        s[a]["gf"] += ag; s[a]["ga"] += hg; s[a]["pld"] += 1
        if hg > ag:
            s[h]["pts"] += 3
        elif hg < ag:
            s[a]["pts"] += 3
        else:
            s[h]["pts"] += 1; s[a]["pts"] += 1
    for t in teams:
        s[t]["gd"] = s[t]["gf"] - s[t]["ga"]
    return s


def _runs(order, keyfn):
    i = 0
    while i < len(order):
        j = i
        while j < len(order) and keyfn(order[j]) == keyfn(order[i]):
            j += 1
        yield order[i:j]
        i = j


def rank_group(teams: List[str], matches: List[Result], rng) -> Tuple[List[str], Dict[str, dict]]:
    """Order a group 1st..4th per §3.2: pts → GD → GS → head-to-head → (fair play→) lots."""
    s = table(teams, matches)
    key = lambda t: (s[t]["pts"], s[t]["gd"], s[t]["gf"])
    order = sorted(teams, key=key, reverse=True)
    out: List[str] = []
    for run in _runs(order, key):
        out.extend(_break_h2h(run, matches, rng) if len(run) > 1 else run)
    return out, s


def _break_h2h(tied: List[str], matches: List[Result], rng) -> List[str]:
    tset = set(tied)
    sub = [m for m in matches if m[0] in tset and m[1] in tset]
    hs = table(tied, sub)
    key = lambda t: (hs[t]["pts"], hs[t]["gd"], hs[t]["gf"])
    order = sorted(tied, key=key, reverse=True)
    out: List[str] = []
    for run in _runs(order, key):
        run = list(run)
        if len(run) > 1:
            rng.shuffle(run)  # D-cards: fair play unavailable -> seeded lots
        out.extend(run)
    return out


def rank_thirds(thirds: List[dict], fifa_proxy: Dict[str, float], rng) -> List[dict]:
    """Rank the 12 third-placed teams per §3.3: pts → GD → GS → (conduct→) FIFA ranking → lots.

    ``thirds`` items: {"group","team","pts","gd","gf"}. ``fifa_proxy`` maps team→a ranking
    score (higher = better); we reuse the Elo rating as that proxy."""
    key = lambda d: (d["pts"], d["gd"], d["gf"], fifa_proxy.get(d["team"], 0.0))
    order = sorted(thirds, key=key, reverse=True)
    out: List[dict] = []
    for run in _runs(order, key):
        run = list(run)
        if len(run) > 1:
            rng.shuffle(run)  # everything equal incl. FIFA proxy -> seeded lots
        out.extend(run)
    return out
