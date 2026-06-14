"""Dixon-Coles scoreline model (plan.md §18.2).

Independent Poisson goals for each side with the Dixon-Coles low-score correction tau on the
0-0/1-0/0-1/1-1 cells, truncated at g_max and renormalized to a proper distribution.
"""
from __future__ import annotations

import math
from typing import List, Tuple

Matrix = List[List[float]]


def poisson_pmf(k: int, lam: float) -> float:
    return math.exp(-lam) * lam ** k / math.factorial(k)


def dc_tau(i: int, j: int, lam_h: float, lam_a: float, rho: float) -> float:
    """Dixon-Coles dependence correction for the four low-score cells."""
    if i == 0 and j == 0:
        return 1.0 - lam_h * lam_a * rho
    if i == 0 and j == 1:
        return 1.0 + lam_h * rho
    if i == 1 and j == 0:
        return 1.0 + lam_a * rho
    if i == 1 and j == 1:
        return 1.0 - rho
    return 1.0


def scoreline_matrix(lam_h: float, lam_a: float, rho: float = 0.0, g_max: int = 10) -> Matrix:
    """P(home i, away j) over 0..g_max, DC-corrected and normalized to sum to 1.

    tau can dip slightly negative for extreme lambdas; we floor cells at 0 before
    renormalizing so the result is always a proper distribution.
    """
    ph = [poisson_pmf(i, lam_h) for i in range(g_max + 1)]
    pa = [poisson_pmf(j, lam_a) for j in range(g_max + 1)]
    m = [[max(0.0, ph[i] * pa[j] * dc_tau(i, j, lam_h, lam_a, rho))
          for j in range(g_max + 1)] for i in range(g_max + 1)]
    total = sum(sum(row) for row in m)
    if total <= 0:
        raise ValueError("degenerate scoreline matrix")
    return [[c / total for c in row] for row in m]


def outcome_probs(m: Matrix) -> Tuple[float, float, float]:
    """(P home win, P draw, P away win)."""
    home = draw = away = 0.0
    for i, row in enumerate(m):
        for j, p in enumerate(row):
            if i > j:
                home += p
            elif i == j:
                draw += p
            else:
                away += p
    return home, draw, away


def expected_goals(m: Matrix) -> Tuple[float, float]:
    eh = sum(i * p for i, row in enumerate(m) for p in row)
    ea = sum(j * p for row in m for j, p in enumerate(row))
    return eh, ea


def top_scorelines(m: Matrix, n: int = 6) -> List[Tuple[int, int, float]]:
    cells = [(i, j, p) for i, row in enumerate(m) for j, p in enumerate(row)]
    return sorted(cells, key=lambda c: -c[2])[:n]
