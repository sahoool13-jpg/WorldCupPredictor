"""Knockout bracket (plan.md §19.4). The tree wiring comes from openfootball's KO fixtures
(`Wnn` references); the third-place R32 slots are filled from the committed Annex C table.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional

from ..data.errors import DataError

ROUND_MAP = {"Round of 32": "R32", "Round of 16": "R16",
             "Quarter-final": "QF", "Semi-final": "SF", "Final": "F"}
ROUND_ORDER = ["R32", "R16", "QF", "SF", "F"]


def parse_ko(matches_obj: dict) -> List[dict]:
    """openfootball KO fixtures -> specs [{num, round, ref1, ref2}] in match-number order."""
    specs = []
    for m in matches_obj.get("matches", []):
        r = m.get("round")
        if r in ROUND_MAP:
            specs.append({"num": int(m["num"]), "round": ROUND_MAP[r],
                          "ref1": m["team1"], "ref2": m["team2"]})
    specs.sort(key=lambda x: x["num"])
    if len(specs) != 31:  # 16 + 8 + 4 + 2 + 1
        raise DataError(f"expected 31 knockout matches, parsed {len(specs)}")
    return specs


def _resolve(ref: str, sibling: str, group_results: Dict[str, dict],
             assign: Dict[str, str], winners: Dict[int, str]) -> str:
    kind = ref[0]
    if kind == "1":
        return group_results[ref[1]]["1"]
    if kind == "2":
        return group_results[ref[1]]["2"]
    if kind == "3":
        # this match's winner-slot is the sibling "1X"; Annex C says which 3rd plays here
        winner_group = sibling[1]
        third_group = assign[winner_group]
        return group_results[third_group]["3"]
    if kind == "W":
        return winners[int(ref[1:])]
    raise DataError(f"unrecognized bracket ref {ref!r}")


def simulate(group_results: Dict[str, dict], assign: Dict[str, str], specs: List[dict],
             sample_winner: Callable[[str, str, str], str],
             pinned: Optional[Dict[frozenset, str]] = None) -> Dict[str, object]:
    """Play the bracket. Returns {champion, reach: {team: set(rounds)}, slots:[...], pinned_used}.

    ``pinned`` maps a real (unordered) team-pair to the team that **actually advanced** in a
    completed knockout tie. When both teams of a slot match a pinned pair, the real advancer is
    used instead of sampling — completed knockout ties are fixed, never re-simulated (§21). The
    advancer must be one of the two teams or we raise (drift). ``pinned_used`` reports which
    pinned pairs were realized, so the caller can fail loud if a real result never hit a slot.
    """
    pinned = pinned or {}
    winners: Dict[int, str] = {}
    reach: Dict[str, set] = {}
    slots: List[dict] = []
    pinned_used: set = set()
    final_num = None
    for sp in specs:
        t1 = _resolve(sp["ref1"], sp["ref2"], group_results, assign, winners)
        t2 = _resolve(sp["ref2"], sp["ref1"], group_results, assign, winners)
        reach.setdefault(t1, set()).add(sp["round"])
        reach.setdefault(t2, set()).add(sp["round"])
        pair = frozenset((t1, t2))
        if pair in pinned:
            w = pinned[pair]
            if w not in (t1, t2):
                raise DataError(f"pinned advancer {w!r} not in slot {sp['num']} ({t1} v {t2})")
            pinned_used.add(pair)
        else:
            w = sample_winner(t1, t2, sp["round"])
        winners[sp["num"]] = w
        slots.append({"num": sp["num"], "round": sp["round"], "t1": t1, "t2": t2,
                      "winner": w, "pinned": pair in pinned})
        if sp["round"] == "F":
            final_num = sp["num"]
    champion = winners[final_num]
    reach.setdefault(champion, set()).add("title")
    return {"champion": champion, "reach": reach, "slots": slots, "pinned_used": pinned_used}
