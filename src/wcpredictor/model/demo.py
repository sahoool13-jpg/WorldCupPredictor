"""Print scoreline matrices for real upcoming fixtures (plan.md §18 demo / sanity check).

Uses the Phase-2 **blended** rating (D3-input) to drive lambdas, the committed calibrated
params, and the openfootball schedule to find unplayed fixtures.

  python -m wcpredictor.model.demo [--live] [--fixture "Argentina" "Jordan"]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from ..data import http
from ..data import openfootball as of_mod
from ..data.teams import TeamRegistry
from ..ratings.engine import compute_ratings, load_config as load_rconf
from ..ratings.prior import load_prior
from . import dixon_coles as dc
from .lambdas import home_gammas, lambdas as compute_lambdas
from .calibrate import load_params

_GCONF = Path(__file__).resolve().parents[3] / "configs" / "goal_model.json"


def _ratings(as_of, live) -> Dict[str, float]:
    prior = load_prior()
    rconf = load_rconf()
    matches = []
    if live:
        from ..data import pipeline
        matches = pipeline.run(as_of=as_of)
    details = compute_ratings(matches, as_of, prior, rconf)
    return {t: d.rating for t, d in details.items()}, set(rconf["hosts"])


def report(h: str, a: str, rating, hosts, gparams, gconf, label=""):
    r_h, r_a = rating[h], rating[a]
    gh, ga = home_gammas(gparams, h in hosts, a in hosts)
    lam_h, lam_a = compute_lambdas(r_h, r_a, gparams, gh, ga)
    M = dc.scoreline_matrix(lam_h, lam_a, gparams["rho"], gconf["g_max"])
    ph, pd, pa = dc.outcome_probs(M)
    eh, ea = dc.expected_goals(M)
    tot = sum(sum(row) for row in M)
    print(f"\n=== {label}{h} vs {a} ===")
    print(f"  ratings: {h} {r_h:.0f}  |  {a} {r_a:.0f}   (gap {r_h - r_a:+.0f})")
    print(f"  expected goals: {eh:.2f} - {ea:.2f}   (lambda {lam_h:.2f}/{lam_a:.2f})")
    print(f"  W/D/L: {h} {ph*100:4.1f}%  draw {pd*100:4.1f}%  {a} {pa*100:4.1f}%   "
          f"(matrix sums to {tot:.4f})")
    print("  most likely scorelines:")
    for i, j, p in dc.top_scorelines(M, 8):
        print(f"    {h} {i}-{j} {a}   {p*100:4.1f}%")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Scoreline matrices for upcoming fixtures")
    p.add_argument("--as-of", help="ISO instant (default now UTC)")
    p.add_argument("--live", action="store_true", help="fold in live played matches")
    p.add_argument("--fixture", nargs=2, metavar=("HOME", "AWAY"), action="append")
    args = p.parse_args(argv)

    as_of = (datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
             if args.as_of else datetime.now(timezone.utc))
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)

    rating, hosts = _ratings(as_of, args.live)
    gparams = load_params()
    gconf = json.loads(_GCONF.read_text())
    print(f"goal model: mu={gparams['mu']} beta={gparams['beta']} "
          f"gamma_home={gparams['gamma_home']} rho={gparams['rho']} scale={gparams['scale']}")

    if args.fixture:
        for h, a in args.fixture:
            reg = TeamRegistry.load()
            report(reg.name(h), reg.name(a), rating, hosts, gparams, gconf)
        return 0

    # default: a mismatch (Argentina v Jordan) + the closest unplayed group fixture
    reg = TeamRegistry.load()
    _, fixtures = of_mod.load_structure(*of_mod.fetch_raw(http.get_json), reg)
    unplayed = [f for f in fixtures if not f.is_placeholder and f.of_score is None
                and f.home in rating and f.away in rating]
    report("Argentina", "Jordan", rating, hosts, gparams, gconf, label="MISMATCH: ")
    closest = min(unplayed, key=lambda f: abs(rating[f.home] - rating[f.away]))
    report(closest.home, closest.away, rating, hosts, gparams, gconf, label="CLOSEST: ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
