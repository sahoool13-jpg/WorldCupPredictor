"""Point-in-time contract (plan.md §4 / §15.5 R4): only matches that already happened count;
a future/leaked result raises; pending fixtures carry no goals; completed results are stable.
"""
from datetime import datetime, timezone

import pytest

from wcpredictor.data.errors import FutureResultLeak
from wcpredictor.data.model import BaseFixture, OverlayResult, Status
from wcpredictor.data.reconcile import reconcile

UTC = timezone.utc


def _overlay(reg, home, away, hg, ag, status, kickoff):
    hid, aid = reg.team_id(home), reg.team_id(away)
    goals = {hid: hg, aid: ag} if status is Status.FINAL else {hid: None, aid: None}
    return OverlayResult(pair=frozenset((hid, aid)), teams={hid: home, aid: away},
                         goals_by_team=goals, status=status, kickoff_utc=kickoff, source="espn")


def _base(reg, rnd, home, away, kickoff, of_score=None):
    hid, aid = reg.team_id(home), reg.team_id(away)
    return BaseFixture(match_id=f"{rnd}|{hid}|{aid}", round=rnd, group="A", home=home,
                       away=away, home_id=hid, away_id=aid, kickoff_utc=kickoff, of_score=of_score)


def test_future_final_raises(registry):
    """R4: a FINAL dated after as_of is a future leak -> raise."""
    k = datetime(2026, 6, 14, 4, 0, tzinfo=UTC)
    base = [_base(registry, "Matchday 1", "Australia", "Turkey", k)]
    ov = [_overlay(registry, "Australia", "Turkey", 2, 0, Status.FINAL, k)]
    with pytest.raises(FutureResultLeak):
        reconcile(base, ov, as_of=datetime(2026, 6, 13, 0, 0, tzinfo=UTC))


def test_final_iff_kickoff_le_as_of_and_pending_has_no_goals(registry):
    played_k = datetime(2026, 6, 11, 19, 0, tzinfo=UTC)
    future_k = datetime(2026, 6, 20, 18, 0, tzinfo=UTC)
    base = [
        _base(registry, "Matchday 1", "Mexico", "South Africa", played_k),
        _base(registry, "Matchday 2", "Mexico", "South Korea", future_k),
    ]
    overlay = [
        _overlay(registry, "Mexico", "South Africa", 2, 0, Status.FINAL, played_k),
        _overlay(registry, "Mexico", "South Korea", None, None, Status.SCHEDULED, future_k),
    ]
    as_of = datetime(2026, 6, 12, 0, 0, tzinfo=UTC)
    matches = {m.round: m for m in reconcile(base, overlay, as_of)}

    assert matches["Matchday 1"].status is Status.FINAL
    assert (matches["Matchday 1"].home_goals, matches["Matchday 1"].away_goals) == (2, 0)
    pending = matches["Matchday 2"]
    assert pending.status is Status.SCHEDULED
    assert pending.home_goals is None and pending.away_goals is None  # no leak


def test_completed_results_are_stable_across_reconciles(registry):
    k = datetime(2026, 6, 11, 19, 0, tzinfo=UTC)
    base = [_base(registry, "Matchday 1", "Mexico", "South Africa", k)]
    ov = [_overlay(registry, "Mexico", "South Africa", 2, 0, Status.FINAL, k)]
    as_of = datetime(2026, 6, 15, tzinfo=UTC)
    a = reconcile(base, ov, as_of)[0]
    b = reconcile(base, ov, as_of)[0]
    assert (a.status, a.home_goals, a.away_goals) == (b.status, b.home_goals, b.away_goals)
    assert (a.home_goals, a.away_goals) == (2, 0)
