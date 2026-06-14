"""Dashboard entrypoint: run the live pipeline+sim and publish `docs/data/latest.json`
(plan.md §20). Fail-loud — a fetch/sim error leaves the last-good file in place.

  python -m wcpredictor.report.run --live --as-of now [--n 50000 --seed 2026 --out docs/data]
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from ..sim.engine import build_sim
from .io import publish
from .payload import build_payload

_ROOT = Path(__file__).resolve().parents[3]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Build + publish the dashboard JSON")
    p.add_argument("--as-of"); p.add_argument("--live", action="store_true")
    p.add_argument("--espn-start"); p.add_argument("--espn-end")
    p.add_argument("--n", type=int, default=50000)
    p.add_argument("--seed", type=int, default=2026)   # FIXED, committed -> clean deltas
    p.add_argument("--out", default=str(_ROOT / "docs" / "data"))
    args = p.parse_args(argv)

    as_of = (datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
             if args.as_of and args.as_of != "now" else datetime.now(timezone.utc))
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    source = {"structure": "openfootball", "results": "espn" if args.live else "openfootball"}

    def build(prev):
        sim = build_sim(as_of, args.live, args.espn_start, args.espn_end)
        probs = sim.run(args.n, args.seed)
        return build_payload(sim, probs, n_sims=args.n, seed=args.seed,
                             as_of=as_of, source=source, prev=prev)

    payload = publish(Path(args.out), build)   # fail-loud: keeps last-good on error
    top = payload["title_odds"][0]
    print(f"published {args.out}/latest.json  as_of={payload['meta']['as_of']} "
          f"n_played={payload['meta']['n_played']}  leader={top['team']} {top['title']*100:.1f}% "
          f"(Δ{top['title_delta']*100:+.2f}pp)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
