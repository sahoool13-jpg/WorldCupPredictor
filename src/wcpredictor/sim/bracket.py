"""Knockout bracket (plan.md §19.4). The tree wiring is a **committed static reference**
(`data/reference/ko_bracket_2026.json`) in placeholder form (`1X`/`2X`/`3…`/`W##`), NOT re-read
from the live feed: openfootball rewrites those refs into concrete team names as groups clinch
(e.g. `1E`→`Germany`), which breaks resolution — especially the third-place branch, which reads
the *sibling* `1X` to find the winner's group. Group RESULTS still come live; only the tree is
frozen. The third-place R32 slots are filled from the committed Annex C table.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable, Dict, List, Optional

from ..data.errors import DataError

_ROOT = Path(__file__).resolve().parents[3]
_BRACKET_FILE = _ROOT / "data" / "reference" / "ko_bracket_2026.json"

ROUND_MAP = {"Round of 32": "R32", "Round of 16": "R16",
             "Quarter-final": "QF", "Semi-final": "SF", "Final": "F"}
ROUND_ORDER = ["R32", "R16", "QF", "SF", "F"]
_ROUND_COUNTS = {"R32": 16, "R16": 8, "QF": 4, "SF": 2, "F": 1}
# the only ref forms the resolver supports — a group 1st/2nd, a third-place slot, a match winner.
_PLACEHOLDER = re.compile(r"^([12][A-L]|3[A-L](/[A-L])+|W\d+)$")


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


def load_bracket(path: Path = _BRACKET_FILE) -> List[dict]:
    """Load + validate the committed static 2026 bracket wiring (the production source).

    Fails loud on any drift: wrong count/rounds, a ref that isn't a supported placeholder (this
    is exactly the `1E`→`Germany` mutation that broke the live build), or a `W##` ref that points
    at a non-earlier match. Used by `build_sim`; tests run this same data end-to-end so a bad
    bracket fails in CI, never in publish."""
    specs = json.loads(path.read_text())["specs"]
    return validate_bracket(specs)


def validate_bracket(specs: List[dict]) -> List[dict]:
    specs = sorted(specs, key=lambda x: x["num"])
    if len(specs) != 31:
        raise DataError(f"bracket must have 31 matches, got {len(specs)}")
    counts: Dict[str, int] = {}
    nums = {sp["num"] for sp in specs}
    for sp in specs:
        counts[sp["round"]] = counts.get(sp["round"], 0) + 1
        for ref in (sp["ref1"], sp["ref2"]):
            if not _PLACEHOLDER.match(ref):
                raise DataError(
                    f"bracket match {sp['num']} has unsupported ref {ref!r} — only "
                    f"1X/2X/3.../W## are resolvable (a concrete team name means the live feed "
                    f"mutated the tree; the bracket must stay in placeholder form)")
            if ref[0] == "W" and int(ref[1:]) not in nums:
                raise DataError(f"bracket match {sp['num']} ref {ref!r} points at a missing match")
            if ref[0] == "W" and int(ref[1:]) >= sp["num"]:
                raise DataError(f"bracket match {sp['num']} ref {ref!r} is not an earlier match")
    if counts != _ROUND_COUNTS:
        raise DataError(f"bracket round counts {counts} != {_ROUND_COUNTS}")
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
