"""Phase 7 — "Why this %?" explainability (plan.md §22, D7: all 48, λ-only).

The `why` block is read-only/descriptive: present for every team when the sim carries rating
details, host-edge flagged correctly, `w_live = n/(n+k_shrink)`, and — critically — adding it
never perturbs the (fixed-seed) odds or deltas. Omitted entirely when details are absent.
"""
from datetime import datetime, timezone

from wcpredictor.ratings.engine import compute_ratings, load_config
from wcpredictor.sim.engine import Sim

from test_sim_live_state import HOSTS, _group_A_decided, _inputs, _mk

AS_OF = datetime(2026, 6, 26, tzinfo=timezone.utc)   # after all of Group A has kicked off
SOURCE = {"structure": "openfootball", "results": "espn"}


def _sim_with_details(group_fixtures, groups, prior, gp, gc, specs, *, details=True):
    rconf = load_config()
    matches = _group_A_decided(group_fixtures)
    det = compute_ratings(matches, AS_OF, prior, rconf)
    ratings = {t: d.rating for t, d in det.items()}
    return Sim(matches, ratings, gp, gc, HOSTS, specs, groups=groups,
               details=(det if details else None)), rconf


def _payload(details=True):
    from wcpredictor.report.payload import build_payload
    groups, gf, specs, prior, gp, gc = _inputs()
    sim, rconf = _sim_with_details(gf, groups, prior, gp, gc, specs, details=details)
    p = build_payload(sim, sim.run(n=200, seed=1), n_sims=200, seed=1, as_of=AS_OF,
                      source=SOURCE, prev=None)
    return p, rconf


def test_why_present_for_all_48():
    p, _ = _payload()
    assert len(p["title_odds"]) == 48
    assert all("why" in r for r in p["title_odds"])             # D7a: every team
    w = p["title_odds"][0]["why"]
    assert set(w) == {"rating", "goals"}
    assert set(w["rating"]) == {"blended", "prior", "elo_live", "form_delta",
                                "squad_delta", "w_live", "n_played"}
    assert set(w["goals"]) == {"attack_lambda", "defence_lambda", "host_edge"}


def test_why_values_are_finite_and_sane():
    p, _ = _payload()
    for r in p["title_odds"]:
        g = r["why"]["goals"]
        assert g["attack_lambda"] > 0 and g["defence_lambda"] > 0  # real goal expectations
        assert isinstance(g["host_edge"], bool)
        assert 0.0 <= r["why"]["rating"]["w_live"] <= 1.0


def test_host_edge_flag_matches_hosts():
    p, _ = _payload()
    by_team = {r["team"]: r for r in p["title_odds"]}
    assert by_team["Mexico"]["why"]["goals"]["host_edge"] is True       # host
    assert by_team["Czech Republic"]["why"]["goals"]["host_edge"] is False


def test_w_live_equals_shrinkage_formula():
    p, rconf = _payload()
    k = rconf["k_shrink"]
    mex = next(r for r in p["title_odds"] if r["team"] == "Mexico")["why"]["rating"]
    assert mex["n_played"] == 3                                  # 3 group games played
    assert abs(mex["w_live"] - 3 / (3 + k)) < 1e-9


def test_why_is_descriptive_only_does_not_move_odds():
    with_why, _ = _payload(details=True)
    without, _ = _payload(details=False)
    assert all("why" not in r for r in without["title_odds"])    # graceful omit
    a = {r["team"]: (r["title"], r["title_delta"]) for r in with_why["title_odds"]}
    b = {r["team"]: (r["title"], r["title_delta"]) for r in without["title_odds"]}
    assert a == b                                               # identical odds + deltas
