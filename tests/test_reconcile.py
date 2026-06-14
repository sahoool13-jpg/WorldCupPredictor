from datetime import datetime, timezone

import pytest

from wcpredictor.data import espn, openfootball as of
from wcpredictor.data.errors import AmbiguousMatch, ScoreConflict, UnmatchedOverlay
from wcpredictor.data.model import BaseFixture, OverlayResult, Status
from wcpredictor.data.reconcile import reconcile

UTC = timezone.utc
AFTER_ALL = datetime(2026, 7, 20, tzinfo=UTC)


def _overlay(reg, home, away, hg, ag, status, kickoff):
    hid, aid = reg.team_id(home), reg.team_id(away)
    goals = {hid: hg, aid: ag} if status is Status.FINAL else {hid: None, aid: None}
    return OverlayResult(pair=frozenset((hid, aid)), teams={hid: home, aid: away},
                         goals_by_team=goals, status=status, kickoff_utc=kickoff, source="espn")


def _base(reg, rnd, home, away, kickoff, of_score=None, group=None):
    hid, aid = reg.team_id(home), reg.team_id(away)
    return BaseFixture(match_id=f"{rnd}|{hid}|{aid}", round=rnd, group=group, home=home,
                       away=away, home_id=hid, away_id=aid, kickoff_utc=kickoff, of_score=of_score)


# --- R1: end-to-end cross-bucket match on real golden structure ---
def test_e2e_cross_bucket_and_provenance(registry, of_groups, of_matches, espn_days):
    _, fixtures = of.load_structure(of_groups, of_matches, registry)
    overlay = [r for day in espn_days for r in espn.parse_scoreboard(day, registry)]
    matches = reconcile(fixtures, overlay, AFTER_ALL)
    by_pair = {frozenset((m.home_id, m.away_id)): m for m in matches}

    aus = registry.team_id("Australia"); tur = registry.team_id("Turkey")
    au = by_pair[frozenset((aus, tur))]
    # openfootball dates this 06-13, ESPN 06-14 — matched by team-pair regardless (R1)
    assert au.status is Status.FINAL
    assert (au.home_goals, au.away_goals) == (2, 0)
    assert au.result_source == "espn"

    finals = [m for m in matches if m.is_final]
    by_src = {}
    for m in finals:
        by_src[m.result_source] = by_src.get(m.result_source, 0) + 1
    # 7 openfootball-played; ESPN overrides 3 of them + adds Australia-Turkey
    assert len(finals) == 8
    assert by_src == {"espn": 4, "openfootball": 4}

    # orientation: openfootball home=Haiti; resolved score stays Haiti 0-1 Scotland
    hai = registry.team_id("Haiti"); sco = registry.team_id("Scotland")
    h = by_pair[frozenset((hai, sco))]
    assert {h.home_id: h.home_goals, h.away_id: h.away_goals} == {hai: 0, sco: 1}


# --- R2: an unmatched FINAL overlay fails loud (never silently dropped) ---
def test_unmatched_overlay_raises(registry, of_groups, of_matches):
    _, fixtures = of.load_structure(of_groups, of_matches, registry)
    # Mexico (Grp A) v Brazil (Grp C) never meet in the group stage -> no base fixture
    rogue = _overlay(registry, "Mexico", "Brazil", 1, 0, Status.FINAL,
                     datetime(2026, 6, 20, tzinfo=UTC))
    with pytest.raises(UnmatchedOverlay):
        reconcile(fixtures, [rogue], AFTER_ALL)


# --- R3: both sources final but scores disagree -> raise ---
def test_score_conflict_raises(registry):
    k = datetime(2026, 6, 11, 19, 0, tzinfo=UTC)
    base = [_base(registry, "Matchday 1", "Mexico", "South Africa", k, of_score=(2, 1), group="A")]
    ov = [_overlay(registry, "Mexico", "South Africa", 2, 0, Status.FINAL, k)]
    with pytest.raises(ScoreConflict):
        reconcile(base, ov, AFTER_ALL)


# --- ambiguity: a repeated pair equidistant from the overlay kickoff -> raise ---
def test_ambiguous_repeated_pair_raises(registry):
    ov_k = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
    base = [
        _base(registry, "Group", "Spain", "Portugal", datetime(2026, 6, 15, 11, 0, tzinfo=UTC)),
        _base(registry, "R32", "Spain", "Portugal", datetime(2026, 6, 15, 13, 0, tzinfo=UTC)),
    ]
    ov = [_overlay(registry, "Spain", "Portugal", 1, 0, Status.FINAL, ov_k)]
    with pytest.raises(AmbiguousMatch):
        reconcile(base, ov, AFTER_ALL)
