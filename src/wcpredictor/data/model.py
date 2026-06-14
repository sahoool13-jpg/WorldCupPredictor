"""Core data types for the WC-2026 data layer.

Point-in-time correctness (plan.md §4) lives in the reconciler, not here; these are the
plain records. A *resolved* ``Match`` only ever carries goals when its status is FINAL —
pending fixtures must have ``None`` goals so a future/simulated result can never leak in.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional


class Status(str, Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    FINAL = "final"


def slugify(name: str) -> str:
    """Deterministic identity slug for a team name.

    Folds diacritics/case, drops ``&`` and the filler words and/of/the, and collapses
    punctuation to single spaces. This normalizes *spelling* only; names that don't resolve
    to a known team still RAISE upstream (we never guess an identity).
    """
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = s.replace("&", " ")
    s = re.sub(r"\b(and|of|the)\b", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def parse_offset_time(date_str: str, time_str: Optional[str]) -> datetime:
    """openfootball kickoff: date='2026-06-11', time='13:00 UTC-6' -> aware UTC datetime.

    Missing time -> 00:00 at UTC (knockout rows occasionally omit a time).
    """
    y, m, d = (int(x) for x in date_str.split("-"))
    if not time_str:
        return datetime(y, m, d, 0, 0, tzinfo=timezone.utc)
    mt = re.match(r"\s*(\d{1,2}):(\d{2})\s*UTC\s*([+-]\d{1,2})?", time_str)
    if not mt:
        raise ValueError(f"unparseable openfootball time: {time_str!r}")
    hh, mm = int(mt.group(1)), int(mt.group(2))
    off = int(mt.group(3) or 0)
    local = datetime(y, m, d, hh, mm, tzinfo=timezone(timedelta(hours=off)))
    return local.astimezone(timezone.utc)


def parse_iso_utc(s: str) -> datetime:
    """ESPN ISO date, e.g. '2026-06-14T02:00Z' -> aware UTC datetime."""
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass(frozen=True)
class Team:
    team_id: str          # stable slug
    name: str             # canonical (openfootball) name
    group: Optional[str]  # group letter A..L (None for non-group context)


@dataclass(frozen=True)
class BaseFixture:
    """A fixture from openfootball (the static structure source).

    Knockout rows carry placeholder slots ("2A", "1E", "3A/B/C/D/F") rather than real
    teams (the bracket is filled by the Phase-4 simulator), so ``is_placeholder`` is True
    and they are excluded from overlay reconciliation.
    """
    match_id: str
    round: str
    group: Optional[str]
    home: str
    away: str
    home_id: str
    away_id: str
    kickoff_utc: datetime
    of_score: Optional[tuple]  # (home_goals, away_goals) if openfootball has a final score
    is_placeholder: bool = False

    @property
    def pair(self) -> frozenset:
        return frozenset((self.home_id, self.away_id))


@dataclass(frozen=True)
class OverlayResult:
    """A result/status from the live overlay (ESPN). Goals are keyed by team id so the
    home/away orientation need not match openfootball's.

    ``winner_id`` is the advancing team's id for a completed **knockout** match (from ESPN's
    per-competitor ``winner`` flag) — needed because a KO tie can be level after 90'/ET and
    decided on penalties, where the score alone doesn't say who went through. ``None`` for
    group games and undecided fixtures.
    """
    pair: frozenset
    teams: dict           # team_id -> name
    goals_by_team: dict   # team_id -> Optional[int]
    status: Status
    kickoff_utc: datetime
    source: str
    winner_id: Optional[str] = None


@dataclass(frozen=True)
class KnockoutResult:
    """A completed, real knockout tie ingested from the overlay (plan.md §21). The bracket
    binds it to a slot by **unordered team-pair**; ``winner`` is the team that advanced
    (fixed, never re-simulated). Goals are the displayed scoreline (post-ET aggregate as the
    source reports it); the winner is the source of truth for advancement."""
    pair: frozenset
    home: str
    away: str
    home_goals: Optional[int]
    away_goals: Optional[int]
    winner: str
    kickoff_utc: datetime
    source: str


@dataclass(frozen=True)
class Match:
    """A resolved fixture at a given ``as_of`` (the reconciler's output)."""
    match_id: str
    round: str
    group: Optional[str]
    home: str
    away: str
    home_id: str
    away_id: str
    kickoff_utc: datetime
    status: Status
    home_goals: Optional[int] = None
    away_goals: Optional[int] = None
    result_source: Optional[str] = None  # provenance: 'espn' | 'openfootball' | None

    @property
    def is_final(self) -> bool:
        return self.status is Status.FINAL
