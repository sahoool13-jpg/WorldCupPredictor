"""Loud failures for the data layer (plan.md §5/§12.6/§15.5).

Every one of these is a *bug or data problem we refuse to paper over*. No silent defaults.
"""


class DataError(Exception):
    """Base for all data-layer failures."""


class UnknownTeam(DataError):
    """A team name did not resolve to a known canonical team (no guessing)."""


class StructureError(DataError):
    """openfootball structure invariant broken (≠12 groups, group ≠4, ≠104 fixtures, …)."""


class UnmatchedOverlay(DataError):
    """An overlay *result* could not be matched to an openfootball fixture (R2)."""


class AmbiguousMatch(DataError):
    """A team-pair maps to >1 base fixture and could not be disambiguated."""


class ScoreConflict(DataError):
    """Both sources are final for a fixture but the scores disagree (R3)."""


class FutureResultLeak(DataError):
    """A final result is dated after ``as_of`` — a future/leaked result (R4, plan.md §4)."""


class MissingScore(DataError):
    """A fixture is final but has no score."""


class UndecidedKnockout(DataError):
    """A final knockout tie from the overlay gives no advancer (no winner flag and the score
    is level) — we refuse to guess who went through (plan.md §21)."""
