import random

from wcpredictor.sim import standings


def test_gd_then_gs_before_head_to_head():
    # A and B both 6 pts (2W1L); B won the head-to-head, but A's overall GD is far better
    # -> A first (2026 uses overall GD/GS *before* head-to-head).
    teams = ["A", "B", "C", "D"]
    matches = [
        ("A", "C", 5, 0), ("A", "D", 5, 0),   # A: two big wins
        ("B", "A", 1, 0),                       # B beat A head-to-head
        ("B", "C", 0, 1), ("B", "D", 1, 0),     # B: 2W1L, small margins
        ("C", "D", 0, 0),
    ]
    order, s = standings.rank_group(teams, matches, random.Random(0))
    assert s["A"]["pts"] == s["B"]["pts"] == 6
    assert s["A"]["gd"] > s["B"]["gd"]
    assert order[0] == "A"            # overall GD outranks B despite losing H2H


def test_head_to_head_breaks_equal_gd_gs():
    # X and Y identical pts/GD/GS overall; X won the head-to-head -> X ranks above Y
    teams = ["X", "Y", "P", "Q"]
    matches = [
        ("X", "Y", 1, 0),   # head-to-head: X over Y
        ("P", "X", 1, 0), ("Q", "X", 1, 0),   # X also loses to P and Q
        ("P", "Y", 1, 0), ("Y", "Q", 1, 0),   # Y loses to P, beats Q
        ("P", "Q", 0, 0),
    ]
    order, s = standings.rank_group(teams, matches, random.Random(0))
    # X and Y both: 1W 1L (3 pts), GF/GA equal -> H2H decides, X above Y
    assert s["X"]["pts"] == s["Y"]["pts"] and s["X"]["gd"] == s["Y"]["gd"]
    assert order.index("X") < order.index("Y")


def test_rank_thirds_uses_fifa_proxy_on_ties():
    thirds = [
        {"group": "A", "team": "weak", "pts": 3, "gd": 0, "gf": 2},
        {"group": "B", "team": "strong", "pts": 3, "gd": 0, "gf": 2},
    ]
    proxy = {"weak": 1500.0, "strong": 1900.0}
    order = standings.rank_thirds(thirds, proxy, random.Random(0))
    assert order[0]["team"] == "strong"   # all stats equal -> higher Elo proxy wins
