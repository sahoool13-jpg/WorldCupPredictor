"""WC-2026 data layer: openfootball (static structure) + ESPN overlay, reconciled with
point-in-time correctness (plan.md §12 + §15)."""
from .errors import (
    AmbiguousMatch,
    DataError,
    FutureResultLeak,
    MissingScore,
    ScoreConflict,
    StructureError,
    UnknownTeam,
    UnmatchedOverlay,
)
from .model import BaseFixture, Match, OverlayResult, Status, Team
from .reconcile import reconcile
from .teams import TeamRegistry

__all__ = [
    "Status", "Team", "BaseFixture", "OverlayResult", "Match",
    "TeamRegistry", "reconcile",
    "DataError", "UnknownTeam", "StructureError", "UnmatchedOverlay",
    "AmbiguousMatch", "ScoreConflict", "FutureResultLeak", "MissingScore",
]
