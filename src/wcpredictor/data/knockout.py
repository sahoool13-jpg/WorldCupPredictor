"""Ingest completed **knockout** results from the live overlay (plan.md §21).

The group stage reconciles overlay→openfootball by team-pair (``reconcile.py``). Knockout
fixtures in openfootball are *placeholders* ("W73", "2A"), so a real R32→Final result has no
concrete openfootball row to match — instead it is bound to a **bracket slot** later, inside
the simulator, by unordered team-pair. This module only does the **point-in-time-correct
extraction**: which finished, real KO ties have happened as of ``as_of``, and who advanced.

Discipline (all loud):
  * a KO final dated **after** ``as_of`` -> ``FutureResultLeak`` (never leak a future result);
  * a KO final with **no advancer** (no ``winner`` flag and a level score) -> ``UndecidedKnockout``;
  * group results (pair present among the group fixtures) are **not** treated as KO here.

Known limitation (recorded, not silently handled): a knockout tie between two teams who also
shared a group is classified by pair alone and would be skipped here. The 2026 Annex C R32
assignment never pairs same-group teams (no-rematch), and a same-group rematch only becomes
possible deep in the bracket; if the overlay ever exposes a per-event round we should switch to
round-aware classification. Until then this is a documented edge, not a silent default.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Set

from .errors import FutureResultLeak, UndecidedKnockout
from .model import KnockoutResult, OverlayResult, Status


def extract_knockouts(
    group_pairs: Set[frozenset],
    overlay: List[OverlayResult],
    as_of: datetime,
) -> List[KnockoutResult]:
    """Completed, real KO ties from the overlay, point-in-time-correct, newest-last by kickoff."""
    out: List[KnockoutResult] = []
    for ov in overlay:
        if ov.status is not Status.FINAL:
            continue
        if ov.pair in group_pairs:
            continue  # a group game (or a documented same-group rematch) — not handled here
        if ov.kickoff_utc > as_of:
            raise FutureResultLeak(
                f"knockout {set(ov.teams.values())} is FINAL but kicks off "
                f"{ov.kickoff_utc.isoformat()} > as_of {as_of.isoformat()}"
            )
        ids = list(ov.teams.keys())  # ESPN competitor order -> home, away (display only)
        home_id, away_id = ids[0], ids[1]
        winner_id = _advancer(ov, home_id, away_id)
        out.append(KnockoutResult(
            # pair keyed by canonical team NAMES (not ids) — the bracket resolves slots to names,
            # so the sim binds a pin by name-pair. (ov.pair above is id-keyed for group matching.)
            pair=frozenset(ov.teams.values()),
            home=ov.teams[home_id], away=ov.teams[away_id],
            home_goals=ov.goals_by_team.get(home_id),
            away_goals=ov.goals_by_team.get(away_id),
            winner=ov.teams[winner_id],
            kickoff_utc=ov.kickoff_utc, source=ov.source,
        ))
    out.sort(key=lambda k: k.kickoff_utc)
    return out


def _advancer(ov: OverlayResult, home_id: str, away_id: str) -> str:
    """Who went through. Trust the overlay's winner flag; fall back to a decisive score; never
    guess a level tie."""
    if ov.winner_id is not None:
        if ov.winner_id not in ov.pair:
            raise UndecidedKnockout(
                f"knockout {set(ov.teams.values())}: winner id {ov.winner_id!r} is not a competitor"
            )
        return ov.winner_id
    hg, ag = ov.goals_by_team.get(home_id), ov.goals_by_team.get(away_id)
    if hg is not None and ag is not None and hg != ag:
        return home_id if hg > ag else away_id
    raise UndecidedKnockout(
        f"knockout {set(ov.teams.values())} is final but has no advancer "
        f"(no winner flag; score {hg}-{ag})"
    )
