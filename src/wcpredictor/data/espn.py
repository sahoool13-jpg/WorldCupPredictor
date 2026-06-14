"""ESPN site-API scoreboard parsing — the live-results overlay (plan.md §15.2).

Goals are keyed by team id (``OverlayResult.goals_by_team``) so the home/away orientation
need not match openfootball's; the reconciler re-attributes by identity.
"""
from __future__ import annotations

from typing import List

from .errors import DataError
from .model import OverlayResult, Status, parse_iso_utc, slugify
from .teams import TeamRegistry


def _status(comp_status: dict) -> Status:
    t = (comp_status or {}).get("type", {})
    state = t.get("state")
    if t.get("completed") or state == "post":
        return Status.FINAL
    if state == "in":
        return Status.IN_PROGRESS
    return Status.SCHEDULED


def parse_scoreboard(day_obj: dict, reg: TeamRegistry, source: str = "espn") -> List[OverlayResult]:
    results: List[OverlayResult] = []
    for ev in day_obj.get("events", []):
        comps = ev.get("competitions") or []
        if not comps:
            continue
        comp = comps[0]
        competitors = comp.get("competitors") or []
        if len(competitors) != 2:
            raise DataError(f"ESPN event {ev.get('id')} has {len(competitors)} competitors")
        status = _status(ev.get("status") or comp.get("status"))
        teams, goals = {}, {}
        for c in competitors:
            name = reg.name(c["team"]["displayName"])
            tid = slugify(name)
            teams[tid] = name
            raw = c.get("score")
            goals[tid] = int(raw) if (raw not in (None, "") and status is Status.FINAL) else None
        kickoff = parse_iso_utc(ev["date"])
        results.append(OverlayResult(
            pair=frozenset(teams.keys()), teams=teams, goals_by_team=goals,
            status=status, kickoff_utc=kickoff, source=source,
        ))
    return results
