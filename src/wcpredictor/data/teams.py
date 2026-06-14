"""Team identity: canonical names (openfootball) + an alias map, with fail-loud lookup.

An unmapped name RAISES ``UnknownTeam`` — we never guess an identity, because a wrong
identity would silently mis-attach a score during reconciliation (plan.md §15.5).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from .errors import UnknownTeam
from .model import Team, slugify

_REF = Path(__file__).resolve().parents[3] / "data" / "reference"


@dataclass
class TeamRegistry:
    canonical: Dict[str, str]          # slug -> canonical name
    group_of: Dict[str, Optional[str]] # canonical name -> group letter
    _alias_slug: Dict[str, str]        # variant slug -> canonical name

    @classmethod
    def load(cls, ref_dir: Path = _REF) -> "TeamRegistry":
        groups = json.loads((ref_dir / "groups.json").read_text())["groups"]
        aliases = json.loads((ref_dir / "aliases.json").read_text())["aliases"]

        canonical: Dict[str, str] = {}
        group_of: Dict[str, Optional[str]] = {}
        for letter, teams in groups.items():
            for name in teams:
                canonical[slugify(name)] = name
                group_of[name] = letter

        alias_slug: Dict[str, str] = {}
        for variant, target in aliases.items():
            if slugify(target) not in canonical:
                raise UnknownTeam(
                    f"alias {variant!r} -> {target!r}, but {target!r} is not a canonical team"
                )
            alias_slug[slugify(variant)] = target
        return cls(canonical=canonical, group_of=group_of, _alias_slug=alias_slug)

    def name(self, raw: str) -> str:
        """Resolve a raw name (from any source) to its canonical name, or RAISE."""
        s = slugify(raw)
        if s in self.canonical:
            return self.canonical[s]
        if s in self._alias_slug:
            return self._alias_slug[s]
        raise UnknownTeam(
            f"unknown team {raw!r} (slug {s!r}); add it to data/reference/aliases.json"
        )

    def team_id(self, raw: str) -> str:
        return slugify(self.name(raw))

    def team(self, raw: str) -> Team:
        n = self.name(raw)
        return Team(team_id=slugify(n), name=n, group=self.group_of.get(n))

    def all_teams(self):
        return [Team(team_id=slugify(n), name=n, group=g) for n, g in self.group_of.items()]
