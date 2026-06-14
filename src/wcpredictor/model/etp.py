"""Knockout resolution: extra time + penalties (plan.md §18.3).

If level after 90', extra time is a scaled-down Poisson (lambdas * et_frac over 30'); if still
level, a penalty shootout ~0.5 at parity, skewed by the rating gap (logistic). Every knockout
resolves to a winner.
"""
from __future__ import annotations

import math

from . import dixon_coles as dc


def penalty_home_prob(r_h: float, r_a: float, params: dict, pen_slope: float) -> float:
    """Shootout win prob for home: 0.5 at parity, gently skewed by rating gap."""
    d = (r_h - r_a) / params["scale"]
    return 1.0 / (1.0 + math.exp(-pen_slope * d))


def knockout_home_advance_prob(lam_h: float, lam_a: float, rho: float,
                               pen_home: float, et_frac: float, g_max: int = 10) -> float:
    """P(home advances) = win in 90' + draw90 * (win in ET + drawET * pen_home)."""
    ph, pd, pa = dc.outcome_probs(dc.scoreline_matrix(lam_h, lam_a, rho, g_max))
    ph_et, pd_et, pa_et = dc.outcome_probs(
        dc.scoreline_matrix(lam_h * et_frac, lam_a * et_frac, rho, g_max))
    return ph + pd * (ph_et + pd_et * pen_home)
