"""Elo core — transparent, shared by the pre-tournament prior (over historical
internationals) and the in-tournament update. World-football-Elo style: a margin-of-victory
multiplier and a home-advantage offset (skipped on neutral ground). All params are tunables.
"""
from __future__ import annotations

from typing import Dict, Tuple


def expected_score(rating_a: float, rating_b: float) -> float:
    """Expected score for A vs B given (already home-adjusted) ratings."""
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))


def mov_multiplier(goal_diff: int) -> float:
    """Margin-of-victory multiplier (eloratings.net style): bigger wins move more, with
    diminishing returns. |gd|<=1 -> 1.0; ==2 -> 1.5; >=3 -> (11+|gd|)/8."""
    g = abs(goal_diff)
    if g <= 1:
        return 1.0
    if g == 2:
        return 1.5
    return (11.0 + g) / 8.0


def update_one(rating_a: float, rating_b: float, score_a: float, goal_diff: int,
               k: float, home_adv_a: float = 0.0, home_adv_b: float = 0.0) -> Tuple[float, float]:
    """Return (rating_a', rating_b') after one match. ``score_a`` is 1/0.5/0 for A.
    ``home_adv_*`` is the home offset already decided by the caller (0 on neutral)."""
    ea = expected_score(rating_a + home_adv_a, rating_b + home_adv_b)
    delta = k * mov_multiplier(goal_diff) * (score_a - ea)
    return rating_a + delta, rating_b - delta


def score_of(home_goals: int, away_goals: int) -> Tuple[float, int]:
    """(score for home team, goal difference). 1 win / 0.5 draw / 0 loss."""
    if home_goals > away_goals:
        return 1.0, home_goals - away_goals
    if home_goals < away_goals:
        return 0.0, away_goals - home_goals
    return 0.5, 0


def apply_match(ratings: Dict[str, float], home: str, away: str, home_goals: int,
                away_goals: int, *, neutral: bool, k: float, home_adv: float,
                default: float = 1500.0) -> None:
    """Mutate ``ratings`` in place for one played match (raw team keys)."""
    ra = ratings.get(home, default)
    rb = ratings.get(away, default)
    sa, gd = score_of(home_goals, away_goals)
    ha = 0.0 if neutral else home_adv
    ratings[home], ratings[away] = update_one(ra, rb, sa, gd, k, home_adv_a=ha, home_adv_b=0.0)
