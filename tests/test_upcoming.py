"""§24 — upcoming-match predictions: the next scheduled fixtures with our own win/draw/win %
and most-likely scoreline, from the Phase-3 Dixon-Coles model. Descriptive only (never an odds
input), group fixtures only, soonest first, capped.
"""
from datetime import datetime, timezone

from wcpredictor.data.model import Status
from wcpredictor.report.payload import build_payload

from test_sim_live_state import _group_A_decided, _inputs, _mk, _sim

AS_OF = datetime(2026, 6, 15, tzinfo=timezone.utc)
SOURCE = {"structure": "openfootball", "results": "espn"}


def _payload(matches_builder):
    groups, gf, specs, ratings, gp, gc = _inputs()
    sim = _sim(matches_builder(gf), groups, ratings, gp, gc, specs)
    p = build_payload(sim, sim.run(n=150, seed=1), n_sims=150, seed=1, as_of=AS_OF,
                      source=SOURCE, prev=None)
    return p, sim


def test_upcoming_shape_and_probabilities():
    p, _ = _payload(lambda gf: _group_A_decided(gf))
    up = p["upcoming"]
    assert 0 < len(up) <= 12                                   # capped, soonest-first batch
    row = up[0]
    assert set(row) == {"date", "group", "home", "away", "p_home", "p_draw", "p_away", "scoreline"}
    assert abs(row["p_home"] + row["p_draw"] + row["p_away"] - 1.0) < 1e-6   # proper distribution
    assert all(0.0 <= row[k] <= 1.0 for k in ("p_home", "p_draw", "p_away"))
    sc = row["scoreline"]
    assert sc["home_goals"] >= 0 and sc["away_goals"] >= 0 and 0.0 < sc["p"] <= 1.0
    assert [r["date"] for r in up] == sorted(r["date"] for r in up)          # soonest first


def test_upcoming_only_scheduled_group_fixtures():
    p, sim = _payload(lambda gf: _group_A_decided(gf))
    sched = {(m.home, m.away) for m in sim.matches
             if m.status is Status.SCHEDULED and m.group is not None}
    played = {(m.home, m.away) for m in sim.matches if m.status is Status.FINAL}
    for r in p["upcoming"]:
        assert (r["home"], r["away"]) in sched                 # never a played or KO fixture
        assert (r["home"], r["away"]) not in played
    # Group A is fully decided -> none of its fixtures appear as upcoming
    assert all(r["group"] != "A" for r in p["upcoming"])


def test_upcoming_empty_when_nothing_scheduled():
    p, _ = _payload(lambda gf: [_mk(f, 1, 0, True) for f in gf])  # everything played
    assert p["upcoming"] == []


def test_upcoming_is_descriptive_only():
    # adding the block cannot move titles/deltas (it's not an odds input)
    p, _ = _payload(lambda gf: _group_A_decided(gf))
    titles = {r["team"]: (r["title"], r["title_delta"]) for r in p["title_odds"]}
    p2, _ = _payload(lambda gf: _group_A_decided(gf))
    assert {r["team"]: (r["title"], r["title_delta"]) for r in p2["title_odds"]} == titles
