"""Pre-tournament Elo prior (D2-prior, plan.md §17.3/§17.7).

Computes one Elo run over all international results **before WC-2026 kickoff** from the
public-domain ``martj42/international_results`` CSV, then reads off the 48 finalists. The
result is **committed** as ``data/reference/elo_prior_2026.json`` (provenance + params) so the
ratings engine and tests don't refetch/recompute 49k matches.

  python -m wcpredictor.ratings.prior --build [--csv <path-or-url>]
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from datetime import date
from pathlib import Path
from typing import Dict, List, Tuple

from ..data.errors import DataError
from ..data.http import get_text
from ..data.model import slugify
from ..data.teams import TeamRegistry

CSV_URL = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
WC_START = "2026-06-11"          # prior uses strictly-earlier internationals
PRIOR_PARAMS = {"k": 20.0, "home_adv": 65.0, "init": 1500.0}
_REF = Path(__file__).resolve().parents[3] / "data" / "reference"


def parse_rows(text: str) -> List[dict]:
    return list(csv.DictReader(io.StringIO(text)))


def run_elo(rows: List[dict], cutoff: str, params: dict) -> Tuple[Dict[str, float], dict]:
    from . import elo
    ratings: Dict[str, float] = {}
    n = 0
    last = ""
    for r in sorted(rows, key=lambda x: x["date"]):
        if r["date"] >= cutoff:
            break
        hs, as_ = r["home_score"], r["away_score"]
        if hs in ("", "NA", None) or as_ in ("", "NA", None):
            continue
        elo.apply_match(ratings, r["home_team"], r["away_team"], int(hs), int(as_),
                        neutral=str(r.get("neutral", "")).upper() == "TRUE",
                        k=params["k"], home_adv=params["home_adv"], default=params["init"])
        n += 1
        last = r["date"]
    return ratings, {"n_matches": n, "last_date": last}


def resolve_finalists(ratings: Dict[str, float], reg: TeamRegistry) -> Dict[str, float]:
    """Map the 48 canonical finalists to their martj42 rating (via the alias map)."""
    slug_to_raw: Dict[str, str] = {}
    for raw in ratings:
        slug_to_raw.setdefault(slugify(raw), raw)
    out: Dict[str, float] = {}
    for canonical in reg.group_of:  # the 48
        candidate_slugs = [slugify(canonical)]
        candidate_slugs += [vs for vs, target in reg._alias_slug.items() if target == canonical]
        raw = next((slug_to_raw[s] for s in candidate_slugs if s in slug_to_raw), None)
        if raw is None:
            raise DataError(f"no international history found for finalist {canonical!r}")
        out[canonical] = round(ratings[raw], 2)
    return out


def build_prior(text: str, reg: TeamRegistry, cutoff: str = WC_START,
                params: dict = PRIOR_PARAMS) -> dict:
    ratings, meta = run_elo(parse_rows(text), cutoff, params)
    prior = resolve_finalists(ratings, reg)
    return {
        "_source": "martj42/international_results (results.csv)",
        "_source_url": CSV_URL,
        "_cutoff": cutoff,
        "_params": params,
        "_meta": meta,
        "prior": prior,
    }


def load_prior(ref_dir: Path = _REF) -> Dict[str, float]:
    return json.loads((ref_dir / "elo_prior_2026.json").read_text())["prior"]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Build the committed pre-tournament Elo prior")
    p.add_argument("--build", action="store_true", required=True)
    p.add_argument("--csv", default=CSV_URL, help="path or URL to results.csv")
    p.add_argument("--out", default=str(_REF / "elo_prior_2026.json"))
    args = p.parse_args(argv)

    text = Path(args.csv).read_text() if Path(args.csv).exists() else get_text(args.csv)
    reg = TeamRegistry.load()
    snap = build_prior(text, reg)
    Path(args.out).write_text(json.dumps(snap, ensure_ascii=False, indent=2))
    pr = snap["prior"]
    top = sorted(pr.items(), key=lambda kv: -kv[1])[:15]
    print(f"prior built: {len(pr)} teams from {snap['_meta']['n_matches']} matches "
          f"(through {snap['_meta']['last_date']}). Top 15:")
    for i, (t, r) in enumerate(top, 1):
        print(f"  {i:2}. {t:<22} {r:7.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
