"""§26 — full R32->Final bracket payload: every slot RESOLVED (real, point-in-time) or PROJECTED
(most-likely team + prob from the existing Monte Carlo). Additive/optional; resolved state comes
from real completed matches + the committed Annex C wiring, never from sampling."""
from datetime import datetime, timezone

from wcpredictor.data.model import KnockoutResult
from wcpredictor.report.payload import _bracket_view, build_payload

from test_sim_live_state import _group_A_decided, _inputs, _mk, _sim
from test_knockout import _all_groups_decided, _decided_sim, _first_r32, HOSTS
from wcpredictor.sim.engine import Sim

AS_OF = datetime(2026, 7, 1, tzinfo=timezone.utc)
SOURCE = {"structure": "openfootball", "results": "espn"}


def _payload(sim, **kw):
    return build_payload(sim, sim.run(n=kw.pop("n", 150), seed=1), n_sims=150, seed=1,
                         as_of=AS_OF, source=SOURCE, prev=None)


def test_bracket_empty_before_run():
    groups, gf, specs, ratings, gp, gc = _inputs()
    sim = _sim([_mk(f, 0, 0, False) for f in gf], groups, ratings, gp, gc, specs)
    assert _bracket_view(sim) == []                       # no slot_stats yet -> graceful


def test_bracket_structure_full_tree():
    groups, gf, specs, ratings, gp, gc = _inputs()
    sim = _sim([_mk(f, 0, 0, False) for f in gf], groups, ratings, gp, gc, specs)
    br = _payload(sim)["bracket"]
    assert len(br) == 31
    counts = {}
    for b in br:
        counts[b["round"]] = counts.get(b["round"], 0) + 1
        assert set(b) == {"num", "round", "slot1", "slot2", "winner", "result"}
        for s in (b["slot1"], b["slot2"], b["winner"]):
            assert set(s) == {"team", "prob", "state"} and 0.0 <= s["prob"] <= 1.0
    assert counts == {"R32": 16, "R16": 8, "QF": 4, "SF": 2, "F": 1}


def test_nothing_played_is_all_projected():
    groups, gf, specs, ratings, gp, gc = _inputs()
    sim = _sim([_mk(f, 0, 0, False) for f in gf], groups, ratings, gp, gc, specs)
    br = _payload(sim)["bracket"]
    # point-in-time: with no completed matches NOTHING resolves, even a Monte-Carlo 100% favorite
    assert all(s["state"] == "projected"
               for b in br for s in (b["slot1"], b["slot2"], b["winner"]))
    assert all(b["result"] is None for b in br)
    assert all(b["slot1"]["team"] in ratings for b in br)     # a real favorite is named


def test_decided_groups_resolve_r32_via_annex_c():
    sim, _ = _decided_sim()                                   # all 12 groups decided
    br = _payload(sim, n=80)["bracket"]
    r32 = [b for b in br if b["round"] == "R32"]
    # group winners/runners-up AND the Annex-C third-place slots are all real now
    assert all(b["slot1"]["state"] == "resolved" and b["slot2"]["state"] == "resolved"
               for b in r32)
    assert all(b["slot1"]["prob"] == 1.0 and b["slot2"]["prob"] == 1.0 for b in r32)
    # later rounds: no KO played yet -> projected favorites
    later = [b for b in br if b["round"] != "R32"]
    assert all(b["slot1"]["state"] == "projected" for b in later)


def test_partial_only_completed_group_resolves():
    # only Group A is fully played; its R32 positions resolve, the rest stay projected
    groups, gf, specs, ratings, gp, gc = _inputs()
    sim = _sim(_group_A_decided(gf), groups, ratings, gp, gc, specs)
    br = _payload(sim)["bracket"]
    resolved = {b["slot1"]["team"] for b in br if b["slot1"]["state"] == "resolved"}
    resolved |= {b["slot2"]["team"] for b in br if b["slot2"]["state"] == "resolved"}
    assert "Mexico" in resolved                               # Group A winner, real
    assert any(b["slot1"]["state"] == "projected" or b["slot2"]["state"] == "projected"
               for b in br)                                   # undecided groups still projected
    # third-place slots can't resolve until ALL groups are done (Annex C undetermined)
    assert all(b["slot2"]["state"] == "projected"
               for b in br if str(b.get("num")) and b["round"] == "R32"
               and b["slot1"]["state"] == "projected")


def test_played_ko_resolves_result_and_advances_winner():
    base, _ = _decided_sim()
    slot = _first_r32(base)
    t1, t2 = slot["t1"], slot["t2"]
    kr = KnockoutResult(pair=frozenset((t1, t2)), home=t1, away=t2, home_goals=3, away_goals=0,
                        winner=t1, kickoff_utc=datetime(2026, 6, 30, tzinfo=timezone.utc),
                        source="espn")
    sim, _ = _decided_sim(ko_results=[kr])
    br = _payload(sim, n=80)["bracket"]
    # the played R32 tie carries its result + a resolved winner
    played = [b for b in br if b["result"] is not None]
    assert len(played) == 1 and played[0]["winner"] == {"team": t1, "prob": 1.0, "state": "resolved"}
    # the winner advances: it appears as a RESOLVED slot in its R16 match
    adv = [b for b in br if b["round"] == "R16" and t1 in
           (b["slot1"]["team"], b["slot2"]["team"])
           and "resolved" in (b["slot1"]["state"], b["slot2"]["state"])]
    assert len(adv) == 1


def test_bracket_descriptive_only_titles_unchanged():
    # the bracket reuses the run; building it must not alter the title odds
    sim, _ = _decided_sim()
    probs = sim.run(n=100, seed=1)
    a = build_payload(sim, probs, n_sims=100, seed=1, as_of=AS_OF, source=SOURCE, prev=None)
    b = build_payload(sim, probs, n_sims=100, seed=1, as_of=AS_OF, source=SOURCE, prev=None)
    assert [r["title"] for r in a["title_odds"]] == [r["title"] for r in b["title_odds"]]
    assert len(a["bracket"]) == 31
