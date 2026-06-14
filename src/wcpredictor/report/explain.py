"""`make explain TEAM=Brazil` — dump one team's "why this %?" breakdown to the terminal
(plan.md §22, the "dumpable" half of CLAUDE.md rule 10). Reuses the payload's `_why_map`, so
the CLI and the dashboard explain a number the *same* way (no duplicate logic).

  python -m wcpredictor.report.explain --team Brazil [--live --as-of now --espn-start …]
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from ..data.errors import UnknownTeam
from ..sim.engine import build_sim
from .payload import _why_map


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Explain a team's rating + goal expectation")
    p.add_argument("--team", required=True)
    p.add_argument("--as-of"); p.add_argument("--live", action="store_true")
    p.add_argument("--espn-start"); p.add_argument("--espn-end")
    args = p.parse_args(argv)

    as_of = (datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
             if args.as_of and args.as_of != "now" else datetime.now(timezone.utc))
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)

    sim = build_sim(as_of, args.live, args.espn_start, args.espn_end)
    why = _why_map(sim)
    if args.team not in why:
        raise UnknownTeam(f"unknown team {args.team!r}; known: {', '.join(sorted(why))}")

    w = why[args.team]; r, g = w["rating"], w["goals"]
    print(f"why {args.team} (as_of={as_of.date()}):")
    print(f"  rating   blended={r['blended']}  (prior={r['prior']}  elo*live={r['elo_live']}  "
          f"n={r['n_played']}  w_live={r['w_live']})")
    print(f"  form Δ   {r['form_delta']:+}     squad={r['squad_delta']}")
    print(f"  goals    attack λ={g['attack_lambda']}  defence λ={g['defence_lambda']}  "
          f"(vs an average side, neutral){'  +host edge' if g['host_edge'] else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
