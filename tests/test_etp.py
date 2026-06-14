from wcpredictor.model.etp import knockout_home_advance_prob, penalty_home_prob

PARAMS = {"scale": 100.0, "rho": -0.05}


def test_penalty_half_at_parity_and_skews():
    assert abs(penalty_home_prob(1800, 1800, PARAMS, 0.6) - 0.5) < 1e-12
    assert penalty_home_prob(1900, 1700, PARAMS, 0.6) > 0.5
    assert penalty_home_prob(1700, 1900, PARAMS, 0.6) < 0.5


def test_knockout_always_resolves():
    # P(home advances) + P(away advances, roles + pens swapped) == 1
    lh, la = 1.4, 1.1
    pen_h = penalty_home_prob(1850, 1800, PARAMS, 0.6)
    home_adv = knockout_home_advance_prob(lh, la, PARAMS["rho"], pen_h, et_frac=0.3333)
    away_adv = knockout_home_advance_prob(la, lh, PARAMS["rho"], 1 - pen_h, et_frac=0.3333)
    assert 0.0 < home_adv < 1.0
    assert abs(home_adv + away_adv - 1.0) < 1e-9


def test_stronger_side_advances_more():
    even = knockout_home_advance_prob(1.2, 1.2, -0.05, 0.5, 0.3333)
    strong = knockout_home_advance_prob(2.2, 0.7, -0.05, 0.7, 0.3333)
    assert abs(even - 0.5) < 1e-9
    assert strong > even
