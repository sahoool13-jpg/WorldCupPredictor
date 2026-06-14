"""Ratings -> expected goals (plan.md §18.2, D3-map = analytic, D3-input = blended rating).

    log lam_h = mu + beta*(R_h - R_a)/scale + gamma_h
    log lam_a = mu - beta*(R_h - R_a)/scale + gamma_a

gamma_* is the home-goal advantage applied to a side only when it is at home (a host on host
ground; 0 at neutral). Driven by the Phase-2 *blended* rating.
"""
from __future__ import annotations

import math
from typing import Tuple


def lambdas(r_h: float, r_a: float, params: dict,
            gamma_h: float = 0.0, gamma_a: float = 0.0) -> Tuple[float, float]:
    d = (r_h - r_a) / params["scale"]
    lam_h = math.exp(params["mu"] + params["beta"] * d + gamma_h)
    lam_a = math.exp(params["mu"] - params["beta"] * d + gamma_a)
    return lam_h, lam_a


def home_gammas(params: dict, host_h: bool, host_a: bool) -> Tuple[float, float]:
    """Goal-advantage offsets: the host side (if any) gets gamma_home; neutral otherwise."""
    g = params["gamma_home"]
    return (g if host_h else 0.0, g if host_a else 0.0)
