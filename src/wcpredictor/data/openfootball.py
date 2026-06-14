"""openfootball parsing — the canonical static structure (groups + 104-fixture schedule).

We do NOT trust openfootball for liveness (it lags; it missed Australia 2-0 Turkey on day
1). Its scores are carried only as a *fallback* (``BaseFixture.of_score``) used when the
overlay has no entry for a fixture. Status/score authority is the overlay (plan.md §15).
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .errors import StructureError
from .model import BaseFixture, parse_offset_time, slugify
from .sources import DEFAULT_OPENFOOTBALL, OpenfootballConfig
from .teams import TeamRegistry

EXPECTED_GROUPS = 12
EXPECTED_GROUP_SIZE = 4
EXPECTED_FIXTURES = 104


def parse_groups(groups_obj: dict, reg: TeamRegistry) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for grp in groups_obj.get("groups", []):
        letter = grp["name"].replace("Group", "").strip()
        out[letter] = [reg.name(t) for t in grp["teams"]]
    if len(out) != EXPECTED_GROUPS:
        raise StructureError(f"expected {EXPECTED_GROUPS} groups, found {len(out)}")
    for letter, teams in out.items():
        if len(teams) != EXPECTED_GROUP_SIZE:
            raise StructureError(f"group {letter} has {len(teams)} teams (expected 4)")
    return out


def _of_score(match: dict) -> Optional[Tuple[int, int]]:
    sc = match.get("score")
    if isinstance(sc, dict) and isinstance(sc.get("ft"), (list, tuple)) and len(sc["ft"]) == 2:
        return (int(sc["ft"][0]), int(sc["ft"][1]))
    return None


def _is_group_match(m: dict) -> bool:
    return isinstance(m.get("group"), str) and m["group"].startswith("Group")


def parse_matches(matches_obj: dict, reg: TeamRegistry) -> List[BaseFixture]:
    fixtures: List[BaseFixture] = []
    for m in matches_obj.get("matches", []):
        rnd = m.get("round", "")
        kickoff = parse_offset_time(m["date"], m.get("time"))
        if _is_group_match(m):
            # real teams — canonicalize (an unknown name RAISES, never guessed)
            home, away = reg.name(m["team1"]), reg.name(m["team2"])
            hid, aid = slugify(home), slugify(away)
            group = m["group"].replace("Group", "").strip()
            placeholder = False
        else:
            # knockout placeholder slot — keep the raw label, do NOT canonicalize
            home, away = m["team1"], m["team2"]
            hid, aid = slugify(home), slugify(away)
            group, placeholder = None, True
        fixtures.append(BaseFixture(
            match_id=f"{slugify(rnd)}|{hid}|{aid}", round=rnd, group=group,
            home=home, away=away, home_id=hid, away_id=aid,
            kickoff_utc=kickoff, of_score=_of_score(m), is_placeholder=placeholder,
        ))
    if len(fixtures) != EXPECTED_FIXTURES:
        raise StructureError(f"expected {EXPECTED_FIXTURES} fixtures, found {len(fixtures)}")
    return fixtures


def fetch_raw(http_get, cfg: OpenfootballConfig = DEFAULT_OPENFOOTBALL):
    return http_get(cfg.groups_url()), http_get(cfg.matches_url())


def load_structure(groups_obj: dict, matches_obj: dict, reg: TeamRegistry):
    """Returns (groups: dict[letter -> [names]], fixtures: list[BaseFixture])."""
    groups = parse_groups(groups_obj, reg)
    fixtures = parse_matches(matches_obj, reg)
    return groups, fixtures
