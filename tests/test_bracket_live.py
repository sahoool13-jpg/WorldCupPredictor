"""Gate: the production knockout bracket must resolve end-to-end (regression for the publish
crash where the live feed mutated a placeholder into a concrete team — `1E` -> `"Germany"` —
and `_resolve` raised `DataError: unrecognized bracket ref`).

Why this exists: the old tests only exercised the *test golden* bracket, never the data the live
build loaded, so the drift slipped through to publish. Production now loads a **committed static
bracket** (`data/reference/ko_bracket_2026.json`); these tests run that *exact* file through the
full sim with the fixed seed, so any bracket/resolver drift fails here instead of in publish.
"""
import pytest

from wcpredictor.data.errors import DataError
from wcpredictor.sim import bracket
from wcpredictor.sim.engine import Sim

from test_sim_live_state import HOSTS, _inputs
from test_knockout import _all_groups_decided


def test_committed_bracket_loads_and_validates():
    specs = bracket.load_bracket()                      # production source of truth
    assert len(specs) == 31
    counts = {}
    for s in specs:
        counts[s["round"]] = counts.get(s["round"], 0) + 1
    assert counts == {"R32": 16, "R16": 8, "QF": 4, "SF": 2, "F": 1}


def test_production_bracket_resolves_end_to_end():
    """The live build path: load_bracket() + a fully decided group stage, run through the sim.
    Would raise DataError on any unresolvable ref (the original failure)."""
    groups, gf, _golden, ratings, gp, gc = _inputs()
    matches = _all_groups_decided(gf, groups)           # every group decided -> bracket resolves
    specs = bracket.load_bracket()                      # <-- exact production bracket, not golden
    sim = Sim(matches, ratings, gp, gc, HOSTS, specs, groups=groups)
    probs = sim.run(n=30, seed=2026)
    assert len(probs) == 32                             # 32 teams reach R32, none lost to a crash
    assert any(p["title"] > 0 for p in probs.values())  # a champion emerges
    slots = sim.bracket_state()
    assert len(slots) == 31
    assert all(s["t1"] in ratings and s["t2"] in ratings for s in slots)  # every ref -> real team


def test_validate_rejects_concrete_team_ref():
    """Exactly the mutation that broke publish: a group-winner placeholder becomes a real team."""
    specs = bracket.load_bracket()
    for s in specs:
        if s["ref1"] == "1E":
            s["ref1"] = "Germany"
    with pytest.raises(DataError):
        bracket.validate_bracket(specs)


def test_validate_rejects_bad_counts_and_winner_refs():
    good = bracket.load_bracket()
    with pytest.raises(DataError):
        bracket.validate_bracket(good[:-1])             # 30 matches != 31
    broken = [dict(s) for s in good]
    for s in broken:
        if s["round"] == "F":
            s["ref1"] = "W999"                          # winner ref to a missing match
    with pytest.raises(DataError):
        bracket.validate_bracket(broken)
