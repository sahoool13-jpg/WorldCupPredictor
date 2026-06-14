"""Phase-2 point-in-time contract (plan.md §17.1): ratings learn ONLY from played matches
(FINAL, kickoff <= as_of); pending/future are ignored and a future-dated FINAL raises."""
from wcpredictor.data.errors import FutureResultLeak
from wcpredictor.data.model import Status
from wcpredictor.ratings.engine import compute_ratings

from _ratings_util import config, match, utc

import pytest

PRIOR = {"A": 1600.0, "B": 1500.0, "C": 1500.0, "D": 1400.0}


def test_scheduled_and_future_matches_are_ignored():
    m1 = match("A", "B", 2, 0, utc(2026, 6, 12))                       # FINAL, before as_of
    m2 = match("C", "D", 1, 0, utc(2026, 6, 20), status=Status.SCHEDULED)  # future, pending
    as_of = utc(2026, 6, 15)
    with_pending = compute_ratings([m1, m2], as_of, PRIOR, config())
    only_played = compute_ratings([m1], as_of, PRIOR, config())
    for t in PRIOR:
        assert with_pending[t].rating == only_played[t].rating
    assert with_pending["C"].n == 0 and with_pending["A"].n == 1


def test_future_dated_final_raises():
    leaked = match("C", "D", 1, 0, utc(2026, 6, 20))  # FINAL but after as_of
    with pytest.raises(FutureResultLeak):
        compute_ratings([leaked], utc(2026, 6, 15), PRIOR, config())


def test_earlier_result_unaffected_by_later_one():
    m1 = match("A", "B", 2, 0, utc(2026, 6, 12))
    m2 = match("C", "D", 1, 0, utc(2026, 6, 20))
    at_t1 = compute_ratings([m1], utc(2026, 6, 15), PRIOR, config())
    at_t2 = compute_ratings([m1, m2], utc(2026, 6, 21), PRIOR, config())
    assert at_t1["A"].elo_live == at_t2["A"].elo_live  # m2 doesn't touch A/B
    assert at_t2["C"].n == 1 and at_t1["C"].n == 0


def test_determinism():
    ms = [match("A", "B", 2, 0, utc(2026, 6, 12))]
    a = compute_ratings(ms, utc(2026, 6, 15), PRIOR, config())
    b = compute_ratings(ms, utc(2026, 6, 15), PRIOR, config())
    assert {t: d.rating for t, d in a.items()} == {t: d.rating for t, d in b.items()}
