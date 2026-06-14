import json
from pathlib import Path

import pytest

from wcpredictor.data.errors import DataError
from wcpredictor.ratings import prior as prior_mod

CSV = """date,home_team,away_team,home_score,away_score,tournament,city,country,neutral
2024-01-01,Aland,Bland,3,0,Friendly,X,X,TRUE
2024-02-01,Aland,Bland,2,0,Friendly,X,X,TRUE
2025-01-01,Bland,Aland,0,0,Friendly,X,X,TRUE
2026-01-01,Aland,Bland,NA,NA,Friendly,X,X,TRUE
2026-07-01,Aland,Bland,5,0,FIFA World Cup,X,X,TRUE
"""


def test_run_elo_respects_cutoff_and_na():
    rows = prior_mod.parse_rows(CSV)
    ratings, meta = prior_mod.run_elo(rows, cutoff="2026-06-11", params=prior_mod.PRIOR_PARAMS)
    # Aland beat Bland twice (the draw doesn't flip it); 2026 NA + post-cutoff rows excluded
    assert ratings["Aland"] > ratings["Bland"]
    assert meta["n_matches"] == 3          # 2 wins + 1 draw; NA and 2026-07 excluded
    assert meta["last_date"] == "2025-01-01"


def test_resolve_finalists_uses_alias_map(registry):
    # martj42 spellings for the two finalists that differ from openfootball
    ratings = {n: 1500.0 for letter in
               json.loads((Path("data/reference/groups.json")).read_text())["groups"].values()
               for n in letter}
    ratings.pop("USA"); ratings["United States"] = 1700.0
    ratings.pop("Bosnia & Herzegovina"); ratings["Bosnia and Herzegovina"] = 1600.0
    out = prior_mod.resolve_finalists(ratings, registry)
    assert len(out) == 48
    assert out["USA"] == 1700.0
    assert out["Bosnia & Herzegovina"] == 1600.0


def test_resolve_finalists_missing_team_raises(registry):
    ratings = {"Brazil": 1900.0}  # the other 47 absent
    with pytest.raises(DataError):
        prior_mod.resolve_finalists(ratings, registry)


def test_committed_prior_snapshot_is_complete():
    snap = json.loads(Path("data/reference/elo_prior_2026.json").read_text())
    assert len(snap["prior"]) == 48
    assert snap["_cutoff"] == "2026-06-11"
