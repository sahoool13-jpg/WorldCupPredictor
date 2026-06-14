"""Prior <-> live shrinkage (plan.md §17.3): prior dominates early, live takes over as
games are played; one upset barely moves a team with a strong prior."""
from wcpredictor.ratings.engine import compute_ratings

from _ratings_util import config, match, utc

PRIOR = {"A": 1600.0, "B": 1400.0, "C": 1500.0, "D": 1500.0}


def test_zero_matches_rating_equals_prior():
    d = compute_ratings([], utc(2026, 6, 15), PRIOR, config())
    for t in PRIOR:
        assert d[t].elo_star == PRIOR[t]
        assert d[t].w_live == 0.0
        assert d[t].n == 0


def test_w_live_increases_with_games_played():
    ms = [
        match("A", "B", 1, 0, utc(2026, 6, 12)),
        match("A", "C", 1, 0, utc(2026, 6, 16)),
        match("A", "D", 1, 0, utc(2026, 6, 20)),
    ]
    d = compute_ratings(ms, utc(2026, 6, 21), PRIOR, config())
    assert d["A"].n == 3
    assert abs(d["A"].w_live - 3 / (3 + 5)) < 1e-9  # k_shrink = 5


def test_single_upset_barely_moves_strong_prior_team():
    strong = {"A": 1800.0, "B": 1400.0}
    upset = [match("A", "B", 0, 1, utc(2026, 6, 12))]  # A (strong) loses to B
    d = compute_ratings(upset, utc(2026, 6, 15), strong, config())
    drift = abs(d["A"].elo_star - 1800.0)
    live_drift = abs(d["A"].elo_live - 1800.0)
    assert drift < live_drift          # shrinkage damps the live move
    assert drift < 60.0                # prior still dominates after one game
