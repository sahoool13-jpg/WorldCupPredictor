"""Two-source reconciliation + point-in-time resolution (plan.md §15.3, §15.5, §4).

Inputs: openfootball ``BaseFixture``s (the 104-fixture structure) and ESPN ``OverlayResult``s
(fresh status+score). Output: resolved ``Match``es at a given ``as_of``.

Rules (all fail loud — bias to raise over guess):
  R1  match overlay→base by **unordered team-pair** (works across the ESPN/openfootball
      date-bucketing mismatch); disambiguate a repeated pair by nearest kickoff.
  R2  an overlay **result** (FINAL) with no base fixture -> raise UnmatchedOverlay.
  R3  both sources FINAL but scores disagree -> raise ScoreConflict.
  R4  a fixture is FINAL **iff** the source says final AND kickoff_utc <= as_of; a final
      dated after as_of -> raise FutureResultLeak (the core "never leak a future result").
A resolved non-final ``Match`` carries no goals (None), so nothing future can leak in.
"""
from __future__ import annotations

import warnings
from datetime import datetime
from typing import Dict, List, Optional

from .errors import (
    AmbiguousMatch,
    FutureResultLeak,
    MissingScore,
    ScoreConflict,
    UnmatchedOverlay,
)
from .model import BaseFixture, Match, OverlayResult, Status


def _index_by_pair(fixtures: List[BaseFixture]) -> Dict[frozenset, List[BaseFixture]]:
    """Index real-team fixtures by unordered team-pair. Knockout placeholders are excluded
    (their slots aren't real teams; the bracket is resolved in Phase 4)."""
    idx: Dict[frozenset, List[BaseFixture]] = {}
    for f in fixtures:
        if f.is_placeholder:
            continue
        idx.setdefault(f.pair, []).append(f)
    return idx


def _pick(base_list: List[BaseFixture], ov: OverlayResult) -> BaseFixture:
    if len(base_list) == 1:
        return base_list[0]
    # repeated pair (e.g. group + a later knockout): disambiguate by nearest kickoff.
    base_list = sorted(base_list, key=lambda f: abs((f.kickoff_utc - ov.kickoff_utc).total_seconds()))
    nearest, second = base_list[0], base_list[1]
    d0 = abs((nearest.kickoff_utc - ov.kickoff_utc).total_seconds())
    d1 = abs((second.kickoff_utc - ov.kickoff_utc).total_seconds())
    if d0 == d1:
        raise AmbiguousMatch(
            f"overlay pair {set(ov.pair)} maps to multiple base fixtures equally near "
            f"{ov.kickoff_utc.isoformat()}"
        )
    return nearest


def reconcile(
    fixtures: List[BaseFixture],
    overlay: List[OverlayResult],
    as_of: datetime,
) -> List[Match]:
    by_pair = _index_by_pair(fixtures)
    ov_for: Dict[str, OverlayResult] = {}

    # --- attach overlay results to base fixtures (R1/R2) ---
    for ov in overlay:
        candidates = by_pair.get(ov.pair)
        if not candidates:
            if ov.status is Status.FINAL:
                raise UnmatchedOverlay(
                    f"overlay FINAL result {set(ov.pair)} has no openfootball fixture "
                    f"(kickoff {ov.kickoff_utc.isoformat()})"
                )
            warnings.warn(f"overlay non-final fixture {set(ov.pair)} unmatched; ignored")
            continue
        ov_for[_pick(candidates, ov).match_id] = ov

    resolved: List[Match] = []
    for f in fixtures:
        ov = ov_for.get(f.match_id)
        status_src, goals, src = _resolve_source(f, ov)
        match = _apply_point_in_time(f, status_src, goals, src, as_of)
        resolved.append(match)
    return resolved


def _resolve_source(f: BaseFixture, ov: Optional[OverlayResult]):
    """Decide the source-of-truth status+score (pre point-in-time). Overlay wins when
    present; openfootball's score is fallback only."""
    if ov is not None:
        if ov.status is Status.FINAL:
            hg = ov.goals_by_team.get(f.home_id)
            ag = ov.goals_by_team.get(f.away_id)
            if f.of_score is not None and (hg, ag) != tuple(f.of_score):
                raise ScoreConflict(
                    f"{f.home} v {f.away}: openfootball {tuple(f.of_score)} vs "
                    f"{ov.source} {(hg, ag)}"
                )
            return Status.FINAL, (hg, ag), ov.source
        return ov.status, (None, None), ov.source  # overlay scheduled/in-progress wins
    if f.of_score is not None:
        return Status.FINAL, (f.of_score[0], f.of_score[1]), "openfootball"
    return Status.SCHEDULED, (None, None), None


def _apply_point_in_time(f, status_src, goals, src, as_of) -> Match:
    if status_src is Status.FINAL:
        if f.kickoff_utc > as_of:
            raise FutureResultLeak(
                f"{f.home} v {f.away} is FINAL but kicks off {f.kickoff_utc.isoformat()} "
                f"> as_of {as_of.isoformat()}"
            )
        if goals[0] is None or goals[1] is None:
            raise MissingScore(f"{f.home} v {f.away} is final but has no score")
        return Match(
            match_id=f.match_id, round=f.round, group=f.group, home=f.home, away=f.away,
            home_id=f.home_id, away_id=f.away_id, kickoff_utc=f.kickoff_utc,
            status=Status.FINAL, home_goals=goals[0], away_goals=goals[1], result_source=src,
        )
    # not final -> pending; carry NO goals (never leak a future/simulated result).
    status = Status.IN_PROGRESS if status_src is Status.IN_PROGRESS else Status.SCHEDULED
    return Match(
        match_id=f.match_id, round=f.round, group=f.group, home=f.home, away=f.away,
        home_id=f.home_id, away_id=f.away_id, kickoff_utc=f.kickoff_utc,
        status=status, home_goals=None, away_goals=None, result_source=None,
    )
