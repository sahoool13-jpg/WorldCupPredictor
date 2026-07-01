"""Phase 6 — knockout-stage readiness (plan.md §21).

Covers: (1) point-in-time-correct ingestion of real KO results from the overlay; (2) the
bracket pinning a completed tie to its real advancer; (3) the live-state contract extended to
the knockouts — a completed KO tie is never re-rolled, the loser drops to 0%, the winner is
guaranteed through, and the odds shift from the prior; (4) strict slot-binding (a KO result
that can't be placed raises); (5) KO finals surface in the payload + bracket block.
"""
import random
from datetime import datetime, timezone

import pytest

from wcpredictor.data.errors import DataError, FutureResultLeak, UndecidedKnockout
from wcpredictor.data.knockout import extract_knockouts
from wcpredictor.data.model import KnockoutResult, OverlayResult, Status
from wcpredictor.data.teams import TeamRegistry
from wcpredictor.report.payload import build_payload
from wcpredictor.sim import bracket
from wcpredictor.sim.engine import Sim

from test_sim_live_state import HOSTS, _inputs, _mk, _sim

UTC = timezone.utc
AS_OF = datetime(2026, 7, 1, tzinfo=UTC)
BEFORE = datetime(2026, 6, 30, tzinfo=UTC)
KO_DAY = datetime(2026, 6, 30, 20, tzinfo=UTC)


# ----------------------------------------------------------------- (1) ingestion
def _ov(reg, a, b, ga, gb, *, status=Status.FINAL, winner=None, kickoff=KO_DAY):
    aid, bid = reg.team_id(a), reg.team_id(b)
    goals = {aid: ga, bid: gb} if status is Status.FINAL else {aid: None, bid: None}
    wid = reg.team_id(winner) if winner else None
    return OverlayResult(pair=frozenset((aid, bid)), teams={aid: a, bid: b},
                         goals_by_team=goals, status=status, kickoff_utc=kickoff,
                         source="espn", winner_id=wid)


def test_extract_uses_winner_flag_and_excludes_groups(registry):
    a, b = "Argentina", "France"
    group_pairs = {frozenset((registry.team_id("Mexico"), registry.team_id("Canada")))}
    # a group-pair final is NOT a knockout; the KO final (winner flag) is ingested
    ko = extract_knockouts(group_pairs, [
        _ov(registry, "Mexico", "Canada", 1, 0),                 # excluded (group pair)
        _ov(registry, a, b, 1, 1, winner=a),                     # level, but flag -> Argentina
    ], AS_OF)
    assert len(ko) == 1 and ko[0].winner == a
    assert {ko[0].home, ko[0].away} == {a, b}


def test_extract_score_fallback_when_no_flag(registry):
    ko = extract_knockouts(set(), [_ov(registry, "Brazil", "Croatia", 2, 1)], AS_OF)
    assert ko[0].winner == "Brazil"


def test_extract_future_ko_raises(registry):
    fut = _ov(registry, "Spain", "Germany", 2, 0, kickoff=datetime(2026, 7, 2, tzinfo=UTC))
    with pytest.raises(FutureResultLeak):
        extract_knockouts(set(), [fut], AS_OF)


def test_extract_level_without_flag_raises(registry):
    with pytest.raises(UndecidedKnockout):
        extract_knockouts(set(), [_ov(registry, "Spain", "Germany", 1, 1)], AS_OF)


def test_extract_skips_non_final(registry):
    live = _ov(registry, "Spain", "Germany", 0, 0, status=Status.IN_PROGRESS)
    assert extract_knockouts(set(), [live], AS_OF) == []


# ----------------------------------------------------------------- (2) bracket pinning
def _mini_specs():
    return [{"num": 1, "round": "SF", "ref1": "1A", "ref2": "1B"},
            {"num": 2, "round": "SF", "ref1": "1C", "ref2": "1D"},
            {"num": 3, "round": "F", "ref1": "W1", "ref2": "W2"}]


_GR = {g: {"1": n} for g, n in zip("ABCD", ["Alpha", "Beta", "Gamma", "Delta"])}


def test_bracket_pin_overrides_sampler():
    # sampler always picks the first team; pin forces Gamma to win the final over Alpha
    out = bracket.simulate(_GR, {}, _mini_specs(), lambda a, b, r: a,
                           pinned={frozenset(("Alpha", "Gamma")): "Gamma"})
    assert out["champion"] == "Gamma"
    assert out["pinned_used"] == {frozenset(("Alpha", "Gamma"))}
    final = next(s for s in out["slots"] if s["round"] == "F")
    assert final["winner"] == "Gamma" and final["pinned"] is True


def test_bracket_pin_advancer_not_in_slot_raises():
    with pytest.raises(DataError):
        bracket.simulate(_GR, {}, _mini_specs(), lambda a, b, r: a,
                         pinned={frozenset(("Alpha", "Beta")): "Zeta"})  # Zeta not in SF1


# ----------------------------------------------------------------- (3)+(4) Sim contract
def _all_groups_decided(group_fixtures, groups):
    """Every group fully played, ranked by the team's index in its group list (index 0 wins
    all -> 1st; index 3 loses all -> 4th). Deterministic 1/2/3/4 in all 12 groups."""
    out = []
    for f in group_fixtures:
        order = groups[f.group]
        ih, ia = order.index(f.home), order.index(f.away)
        hg, ag = (2, 0) if ih < ia else (0, 2)
        out.append(_mk(f, hg, ag, True))
    return out


def _decided_sim(ko_results=None):
    groups, gf, specs, ratings, gp, gc = _inputs()
    matches = _all_groups_decided(gf, groups)
    return Sim(matches, ratings, gp, gc, HOSTS, specs, groups=groups, ko_results=ko_results), \
        (groups, gf, specs, ratings, gp, gc)


def _first_r32(sim):
    return next(s for s in sim.bracket_state() if s["round"] == "R32")


def test_groups_complete_bracket_is_determined():
    sim, _ = _decided_sim()
    slots = sim.bracket_state()
    assert len(slots) == 31                                   # full tree
    assert sum(1 for s in slots if s["round"] == "R32") == 16
    assert all(s["pinned"] is False for s in slots)           # nothing played yet


def test_ko_pin_is_fixed_and_shifts_odds():
    base, _ = _decided_sim()
    slot = _first_r32(base)
    t1, t2 = slot["t1"], slot["t2"]
    p_no = base.run(n=600, seed=3)
    # pin the model's underdog (lower R16 chance) as the real winner -> a genuine upset
    r16 = lambda t: p_no.get(t, {}).get("R16", 0.0)
    underdog, favorite = (t1, t2) if r16(t1) <= r16(t2) else (t2, t1)
    kr = KnockoutResult(pair=frozenset((t1, t2)), home=t1, away=t2, home_goals=1,
                        away_goals=0, winner=underdog, kickoff_utc=KO_DAY, source="espn")
    pinned, _ = _decided_sim(ko_results=[kr])

    # (a) the completed tie is never re-rolled: that slot's advancer is the real one, always
    pslot = next(s for s in pinned.bracket_state() if {s["t1"], s["t2"]} == {t1, t2})
    assert pslot["pinned"] is True and pslot["winner"] == underdog
    p = pinned.run(n=600, seed=3)
    # (c) loser drops to 0% beyond R32 (but DID reach R32); winner is guaranteed through
    assert p[underdog]["R32"] == 1.0 and p[underdog]["R16"] == 1.0
    assert p.get(favorite, {}).get("R16", 0.0) == 0.0 and p[favorite]["R32"] == 1.0
    # (d) the odds moved from the prior: underdog up, favorite down at R16
    assert p[underdog]["R16"] > r16(underdog) and 0.0 < r16(favorite)
    assert p.get(favorite, {}).get("title", 0.0) == 0.0       # eliminated -> no title


def test_ko_result_unbindable_skips_with_warning():
    # a 4th-placed team never enters the bracket; an unbindable pin is SKIPPED with a loud,
    # recorded warning rather than crashing the whole publish (one odd KO result must not black
    # out the live site).
    groups, gf, specs, ratings, gp, gc = _inputs()
    matches = _all_groups_decided(gf, groups)
    fourth = groups["A"][3]                                    # loses all of Group A
    winner = groups["B"][0]
    kr = KnockoutResult(pair=frozenset((fourth, winner)), home=fourth, away=winner,
                        home_goals=0, away_goals=1, winner=winner, kickoff_utc=KO_DAY,
                        source="espn")
    with pytest.warns(UserWarning, match="did not bind"):
        sim = Sim(matches, ratings, gp, gc, HOSTS, specs, groups=groups, ko_results=[kr])
    assert sim.pinned == {}                                    # the bad pin was dropped
    assert len(sim.run(n=40, seed=1)) == 32                    # ...and the run still publishes


def test_production_ko_path_binds_by_name():
    # END-TO-END like production (ESPN overlay -> extract_knockouts -> Sim). Guards the name/slug
    # mismatch that crashed publish once R32 started: KnockoutResult.pair must be team NAMES to
    # bind to the (name-keyed) bracket. The old tests built KnockoutResult with name-pairs by hand
    # and never ran this path, so the bug reached publish.
    base, _ = _decided_sim()
    slot = _first_r32(base)
    t1, t2 = slot["t1"], slot["t2"]                           # real names in an R32 slot
    reg = TeamRegistry.load()
    h, a = reg.team_id(t1), reg.team_id(t2)
    ov = OverlayResult(pair=frozenset((h, a)), teams={h: t1, a: t2},   # id-keyed, like espn.py
                       goals_by_team={h: 2, a: 0}, status=Status.FINAL,
                       kickoff_utc=KO_DAY, source="espn", winner_id=h)
    ko = extract_knockouts(set(), [ov], AS_OF)
    assert set(ko[0].pair) == {t1, t2}                        # NAMES, not slugs
    groups, gf, specs, ratings, gp, gc = _inputs()
    matches = _all_groups_decided(gf, groups)
    sim = Sim(matches, ratings, gp, gc, HOSTS, specs, groups=groups, ko_results=ko)  # binds, no crash
    assert sim.pinned == {frozenset((t1, t2)): t1}
    p = sim.run(n=40, seed=1)
    assert p[t1]["R16"] == 1.0 and p.get(t2, {}).get("R16", 0.0) == 0.0


def test_ko_before_groups_complete_raises():
    groups, gf, specs, ratings, gp, gc = _inputs()
    incomplete = [_mk(f, 0, 0, False) for f in gf]             # nothing played
    kr = KnockoutResult(pair=frozenset((groups["A"][0], groups["B"][0])),
                        home=groups["A"][0], away=groups["B"][0], home_goals=1, away_goals=0,
                        winner=groups["A"][0], kickoff_utc=KO_DAY, source="espn")
    with pytest.raises(DataError):
        Sim(incomplete, ratings, gp, gc, HOSTS, specs, groups=groups, ko_results=[kr])


# ----------------------------------------------------------------- (5) payload surfacing
def test_payload_bracket_and_ticker_reflect_ko():
    base, _ = _decided_sim()
    slot = _first_r32(base)
    t1, t2 = slot["t1"], slot["t2"]
    kr = KnockoutResult(pair=frozenset((t1, t2)), home=t1, away=t2, home_goals=2,
                        away_goals=1, winner=t1, kickoff_utc=KO_DAY, source="espn")
    sim, _ = _decided_sim(ko_results=[kr])
    p = build_payload(sim, sim.run(n=200, seed=1), n_sims=200, seed=1, as_of=AS_OF,
                      source={"structure": "openfootball", "results": "espn"}, prev=None)
    assert p["meta"]["n_ko_played"] == 1
    assert len(p["bracket"]) == 31
    # groups fully decided -> every R32 slot is RESOLVED (real teams, prob 1.0)
    r32 = [b for b in p["bracket"] if b["round"] == "R32"]
    assert len(r32) == 16
    assert all(b["slot1"]["state"] == "resolved" and b["slot2"]["state"] == "resolved"
               for b in r32)
    # the one played tie carries its real result + a RESOLVED winner
    played = [b for b in p["bracket"] if b["result"] is not None]
    assert len(played) == 1
    assert played[0]["result"] == {"home": t1, "away": t2, "home_goals": 2,
                                   "away_goals": 1, "winner": t1}
    assert played[0]["winner"] == {"team": t1, "prob": 1.0, "state": "resolved"}
    # the KO final shows up in the recent-results ticker (newest entries)
    assert any(r["home"] == t1 and r["away"] == t2 and r["home_goals"] == 2
               for r in p["recent_results"])
