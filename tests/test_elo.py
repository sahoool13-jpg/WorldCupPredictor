from wcpredictor.ratings import elo


def test_expected_score_symmetry():
    assert elo.expected_score(1500, 1500) == 0.5
    assert elo.expected_score(1700, 1500) > 0.5
    assert elo.expected_score(1300, 1500) < 0.5


def test_mov_multiplier():
    assert elo.mov_multiplier(1) == 1.0
    assert elo.mov_multiplier(0) == 1.0
    assert elo.mov_multiplier(2) == 1.5
    assert elo.mov_multiplier(3) == (11 + 3) / 8


def test_score_of():
    assert elo.score_of(2, 0) == (1.0, 2)
    assert elo.score_of(1, 1) == (0.5, 0)
    assert elo.score_of(0, 1) == (0.0, 1)


def test_update_conserves_total():
    ra, rb = elo.update_one(1600, 1400, 1.0, 1, k=20)
    assert round(ra + rb, 6) == 3000.0


def test_beating_stronger_moves_more():
    # win as the weaker side gains more than win as the stronger side
    up_vs_strong = elo.update_one(1500, 1700, 1.0, 1, k=20)[0] - 1500
    up_vs_weak = elo.update_one(1500, 1300, 1.0, 1, k=20)[0] - 1500
    assert up_vs_strong > up_vs_weak > 0
