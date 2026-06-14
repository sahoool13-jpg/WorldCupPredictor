from wcpredictor.model.lambdas import home_gammas, lambdas

PARAMS = {"mu": 0.11, "beta": 0.215, "gamma_home": 0.27, "scale": 100.0}


def test_equal_ratings_neutral_are_symmetric():
    lh, la = lambdas(1800, 1800, PARAMS)
    assert abs(lh - la) < 1e-12


def test_stronger_team_has_higher_lambda():
    lh, la = lambdas(2000, 1700, PARAMS)
    assert lh > la
    # monotonic in the gap
    lh2, _ = lambdas(2100, 1700, PARAMS)
    assert lh2 > lh


def test_host_gamma_raises_home_lambda():
    gh, ga = home_gammas(PARAMS, host_h=True, host_a=False)
    assert gh == PARAMS["gamma_home"] and ga == 0.0
    lh_home, _ = lambdas(1800, 1800, PARAMS, gh, ga)
    lh_neutral, _ = lambdas(1800, 1800, PARAMS, 0.0, 0.0)
    assert lh_home > lh_neutral


def test_neutral_both_gammas_zero():
    assert home_gammas(PARAMS, False, False) == (0.0, 0.0)
