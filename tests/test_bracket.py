from wcpredictor.sim import bracket

from conftest import load_golden


def test_parse_ko_structure():
    specs = bracket.parse_ko(load_golden("openfootball.worldcup.json"))
    assert len(specs) == 31
    from collections import Counter
    counts = Counter(s["round"] for s in specs)
    assert counts == {"R32": 16, "R16": 8, "QF": 4, "SF": 2, "F": 1}


def test_simulate_resolves_to_a_champion():
    specs = bracket.parse_ko(load_golden("openfootball.worldcup.json"))
    # 12 groups, each with placeholder 1/2/3 teams
    gr = {g: {"1": f"{g}1", "2": f"{g}2", "3": f"{g}3"} for g in "ABCDEFGHIJKL"}
    assign = {"A": "C", "B": "E", "D": "F", "E": "H", "G": "I", "I": "D", "K": "J", "L": "K"}
    out = bracket.simulate(gr, assign, specs, sample_winner=lambda a, b, rnd: a)  # home wins
    assert isinstance(out["champion"], str)
    # exactly 32 teams enter R32
    r32 = [t for t, rounds in out["reach"].items() if "R32" in rounds]
    assert len(r32) == 32
