"""Shared builders for the ratings tests (pytest puts this dir on sys.path)."""
from datetime import datetime, timezone

from wcpredictor.data.model import Match, Status


def utc(y, m, d):
    return datetime(y, m, d, tzinfo=timezone.utc)


def match(home, away, hg, ag, kickoff, status=Status.FINAL, group="A"):
    hid = home.lower().replace(" ", "-")
    aid = away.lower().replace(" ", "-")
    final = status is Status.FINAL
    return Match(
        match_id=f"r|{hid}|{aid}", round="Matchday 1", group=group, home=home, away=away,
        home_id=hid, away_id=aid, kickoff_utc=kickoff, status=status,
        home_goals=hg if final else None, away_goals=ag if final else None,
        result_source="espn" if final else None,
    )


BASE_CONFIG = {
    "k": 20.0, "home_adv": 65.0, "init": 1500.0,
    "hosts": ["USA", "Canada", "Mexico"], "form_window": 5, "k_shrink": 5.0,
    "weights": {"elo": 0.60, "form": 0.20, "squad": 0.20},
}


def config(**over):
    c = {**BASE_CONFIG}
    c.update(over)
    return c
