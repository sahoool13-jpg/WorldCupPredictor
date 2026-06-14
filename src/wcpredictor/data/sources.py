"""Source configuration — kept data-driven so a source can be swapped without a rewrite
(plan.md §12.0/§15.2). openfootball = static structure; ESPN = live-results overlay.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OpenfootballConfig:
    name: str = "openfootball"
    base_url: str = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026"
    matches_path: str = "/worldcup.json"
    groups_path: str = "/worldcup.groups.json"

    def matches_url(self) -> str:
        return self.base_url + self.matches_path

    def groups_url(self) -> str:
        return self.base_url + self.groups_path


@dataclass(frozen=True)
class EspnConfig:
    name: str = "espn"
    base_url: str = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world"
    scoreboard_path: str = "/scoreboard"
    # WC-2026 window (group stage start … final). Overlay is fetched per UTC-ish day and
    # reconciled by team-pair, not date (sources bucket kickoffs by different timezones).
    window_start: str = "2026-06-11"
    window_end: str = "2026-07-19"

    def scoreboard_url(self, yyyymmdd: str) -> str:
        return f"{self.base_url}{self.scoreboard_path}?dates={yyyymmdd}"


DEFAULT_OPENFOOTBALL = OpenfootballConfig()
DEFAULT_ESPN = EspnConfig()
