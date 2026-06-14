import pytest

from wcpredictor.model import dixon_coles as dc


@pytest.mark.parametrize("lh,la,rho", [(1.4, 1.1, 0.0), (2.2, 0.6, -0.05), (0.8, 0.8, 0.1)])
def test_matrix_is_a_proper_distribution(lh, la, rho):
    m = dc.scoreline_matrix(lh, la, rho, g_max=10)
    assert all(c >= 0 for row in m for c in row)
    assert abs(sum(c for row in m for c in row) - 1.0) < 1e-9
    assert abs(sum(dc.outcome_probs(m)) - 1.0) < 1e-9


def test_symmetry_for_equal_lambdas():
    m = dc.scoreline_matrix(1.3, 1.3, -0.04, g_max=10)
    ph, pd, pa = dc.outcome_probs(m)
    assert abs(ph - pa) < 1e-9


def test_stronger_side_wins_more():
    weak = dc.outcome_probs(dc.scoreline_matrix(1.3, 1.3, 0.0))[0]
    strong = dc.outcome_probs(dc.scoreline_matrix(2.4, 0.7, 0.0))[0]
    assert strong > weak


def test_dixon_coles_shifts_low_score_cells():
    base = dc.scoreline_matrix(1.2, 1.0, 0.0)
    corr = dc.scoreline_matrix(1.2, 1.0, 0.10)
    # the four low-score cells change; matrix still normalized
    assert base[0][0] != corr[0][0]
    assert base[1][1] != corr[1][1]
    assert abs(sum(c for row in corr for c in row) - 1.0) < 1e-9


def test_expected_goals_match_lambdas_when_rho_zero():
    eh, ea = dc.expected_goals(dc.scoreline_matrix(1.8, 0.9, 0.0, g_max=12))
    assert abs(eh - 1.8) < 1e-3 and abs(ea - 0.9) < 1e-3
