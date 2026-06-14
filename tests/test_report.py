"""Dashboard payload + publisher (plan.md §20.6): schema, clean (fixed-seed) deltas, status,
and fail-loud-keeps-last-good."""
import json
from datetime import datetime, timezone

import pytest

from wcpredictor.report.io import load_prev, publish, write_latest
from wcpredictor.report.payload import build_payload

from test_sim_live_state import _group_A_decided, _inputs, _sim  # reuse offline builders

AS_OF = datetime(2026, 6, 15, tzinfo=timezone.utc)
SOURCE = {"structure": "openfootball", "results": "espn"}


def _payload(prev=None, seed=1):
    groups, gf, specs, ratings, gp, gc = _inputs()
    sim = _sim(_group_A_decided(gf), groups, ratings, gp, gc, specs)
    probs = sim.run(n=300, seed=seed)
    return build_payload(sim, probs, n_sims=300, seed=seed, as_of=AS_OF, source=SOURCE, prev=prev)


def test_schema_and_status():
    p = _payload()
    assert set(p) == {"meta", "title_odds", "groups"}
    assert p["meta"]["n_sims"] == 300 and p["meta"]["seed"] == 1
    assert p["meta"]["n_played"] == 6 and len(p["meta"]["matches_reflected"]) == 6
    titles = [r["title"] for r in p["title_odds"]]
    assert titles == sorted(titles, reverse=True)               # sorted desc
    assert all(0.0 <= r["title"] <= 1.0 for r in p["title_odds"])
    by_team = {r["team"]: r for r in p["title_odds"]}
    assert by_team["Mexico"]["status"] == "through"             # 1st in a decided group
    assert by_team["Czech Republic"]["status"] == "eliminated"  # 4th
    grp_a = next(g for g in p["groups"] if g["group"] == "A")
    mex = next(r for r in grp_a["table"] if r["team"] == "Mexico")
    assert mex["pld"] == 3 and mex["pts"] == 9


def test_deltas_zero_when_unchanged():
    first = _payload(prev=None)
    assert all(r["title_delta"] == 0.0 for r in first["title_odds"])   # no prev -> 0
    again = _payload(prev=first, seed=1)                                # same seed/inputs
    assert all(r["title_delta"] == 0.0 for r in again["title_odds"])   # byte-identical odds


def test_delta_nonzero_when_prev_differs():
    p = _payload()
    leader = p["title_odds"][0]["team"]
    fake_prev = {"title_odds": [{"team": leader, "title": 0.0}]}
    p2 = _payload(prev=fake_prev)
    row = next(r for r in p2["title_odds"] if r["team"] == leader)
    assert row["title_delta"] > 0.0


def test_write_latest_and_history(tmp_path):
    p = _payload()
    write_latest(p, tmp_path)
    assert load_prev(tmp_path / "latest.json")["meta"]["seed"] == 1
    assert list((tmp_path / "history").glob("*.json"))


def test_publish_failloud_keeps_last_good(tmp_path):
    good = _payload()
    write_latest(good, tmp_path)
    before = (tmp_path / "latest.json").read_text()

    def boom(prev):
        raise RuntimeError("simulated live-fetch failure")

    with pytest.raises(RuntimeError):
        publish(tmp_path, boom)
    assert (tmp_path / "latest.json").read_text() == before    # last-good untouched
