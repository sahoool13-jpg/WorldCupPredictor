"""Live-state contract (plan.md §19.5 / §4.1): completed results are fixed and never
re-simulated; the played slate reproduces real standings; mathematically through=100% /
eliminated=0%; a new real result re-seeds and shifts the odds. Offline (golden + Elo prior).
"""
import json
import random

from wcpredictor.data import openfootball as of_mod
from wcpredictor.data.model import Match, Status
from wcpredictor.data.teams import TeamRegistry
from wcpredictor.model.calibrate import load_params
from wcpredictor.ratings.prior import load_prior
from wcpredictor.sim import bracket, standings
from wcpredictor.sim.engine import Sim

from conftest import ROOT, load_golden

HOSTS = {"USA", "Canada", "Mexico"}


def _inputs():
    reg = TeamRegistry.load()
    g_obj = load_golden("openfootball.groups.json")
    m_obj = load_golden("openfootball.worldcup.json")
    groups, fixtures = of_mod.load_structure(g_obj, m_obj, reg)
    specs = bracket.parse_ko(m_obj)
    gconf = json.loads((ROOT / "configs" / "goal_model.json").read_text())
    group_fixtures = [f for f in fixtures if f.group is not None]
    return groups, group_fixtures, specs, load_prior(), load_params(), gconf


def _mk(f, hg, ag, final):
    return Match(f.match_id, f.round, f.group, f.home, f.away, f.home_id, f.away_id,
                 f.kickoff_utc, Status.FINAL if final else Status.SCHEDULED,
                 hg if final else None, ag if final else None, "test" if final else None)


def _sim(matches, groups, ratings, gparams, gconf, specs):
    return Sim(matches, ratings, gparams, gconf, HOSTS, specs, groups=groups)


def _group_A_decided(group_fixtures):
    """Mexico wins all (1st, through); Czech Republic loses all (4th, eliminated)."""
    out = []
    for f in group_fixtures:
        if f.group == "A":
            if "Mexico" in (f.home, f.away):
                hg, ag = (2, 0) if f.home == "Mexico" else (0, 2)
            elif "Czech Republic" in (f.home, f.away):
                hg, ag = (0, 1) if f.home == "Czech Republic" else (1, 0)
            else:
                hg, ag = (1, 0)
            out.append(_mk(f, hg, ag, True))
        else:
            out.append(_mk(f, 0, 0, False))
    return out


def test_a_completed_results_never_re_rolled():
    groups, gf, specs, ratings, gp, gc = _inputs()
    sim = _sim(_group_A_decided(gf), groups, ratings, gp, gc, specs)
    seen = set()
    for k in range(25):
        gr, _ = sim._group_results(random.Random(k))
        seen.add((gr["A"]["1"], gr["A"]["2"], gr["A"]["3"]))
    assert len(seen) == 1                     # fully-played group is deterministic
    assert next(iter(seen))[0] == "Mexico"


def test_b_played_slate_reproduces_real_standings():
    groups, gf, specs, ratings, gp, gc = _inputs()
    sim = _sim(_group_A_decided(gf), groups, ratings, gp, gc, specs)
    tbl = standings.table(groups["A"], sim.played["A"])
    assert tbl["Mexico"]["pts"] == 9 and tbl["Mexico"]["gd"] == 6
    assert tbl["Czech Republic"]["pts"] == 0
    order, _ = standings.rank_group(groups["A"], sim.played["A"], random.Random(0))
    assert order[0] == "Mexico" and order[3] == "Czech Republic"


def test_c_through_is_100_and_eliminated_is_0():
    groups, gf, specs, ratings, gp, gc = _inputs()
    sim = _sim(_group_A_decided(gf), groups, ratings, gp, gc, specs)
    probs = sim.run(n=400, seed=1)
    assert probs["Mexico"]["R32"] == 1.0                       # 1st -> through
    assert probs.get("Czech Republic", {}).get("R32", 0.0) == 0.0  # 4th -> eliminated


def test_d_new_real_result_shifts_odds():
    groups, gf, specs, ratings, gp, gc = _inputs()
    baseline = [_mk(f, 0, 0, False) for f in gf]               # nothing played yet
    p1 = _sim(baseline, groups, ratings, gp, gc, specs).run(n=1200, seed=7)["Mexico"]["R32"]

    updated, wins = [], 0
    for f in gf:
        if f.group == "A" and "Mexico" in (f.home, f.away) and wins < 2:
            hg, ag = (3, 0) if f.home == "Mexico" else (0, 3)
            updated.append(_mk(f, hg, ag, True)); wins += 1
        else:
            updated.append(_mk(f, 0, 0, False))
    p2 = _sim(updated, groups, ratings, gp, gc, specs).run(n=1200, seed=7)["Mexico"]["R32"]
    assert p2 > p1                                             # two real wins lift Mexico
