"""Orchestration + CLI for the data layer (plan.md §12.8).

  verify_source()  -> openfootball structure invariants only (network: openfootball only;
                      runnable from the sandbox).
  run(as_of)       -> full two-source pipeline: openfootball structure + ESPN overlay,
                      reconciled at as_of (ESPN egress is blocked in the sandbox -> runs on
                      Actions; see .github/workflows).

CLI:  python -m wcpredictor.data.pipeline --verify
      python -m wcpredictor.data.pipeline [--as-of 2026-06-14T12:00:00Z] [--save]
"""
from __future__ import annotations

import argparse
import dataclasses
import sys
from datetime import date, datetime, timedelta, timezone
from typing import Callable, List, Optional

from . import espn as espn_mod
from . import openfootball as of_mod
from . import store as store_mod
from .http import get_json
from .model import Match, Status
from .reconcile import reconcile
from .sources import DEFAULT_ESPN, DEFAULT_OPENFOOTBALL, EspnConfig, OpenfootballConfig
from .teams import TeamRegistry

HttpGet = Callable[[str], dict]


def _daterange(start: str, end: str):
    d0 = date.fromisoformat(start)
    d1 = date.fromisoformat(end)
    cur = d0
    while cur <= d1:
        yield cur.strftime("%Y%m%d")
        cur += timedelta(days=1)


def verify_source(http_get: HttpGet = get_json,
                  of_cfg: OpenfootballConfig = DEFAULT_OPENFOOTBALL,
                  reg: Optional[TeamRegistry] = None) -> dict:
    reg = reg or TeamRegistry.load()
    groups_obj, matches_obj = of_mod.fetch_raw(http_get, of_cfg)
    groups, fixtures = of_mod.load_structure(groups_obj, matches_obj, reg)
    of_played = sum(1 for f in fixtures if f.of_score is not None)
    return {
        "groups": len(groups),
        "group_sizes": sorted({len(v) for v in groups.values()}),
        "fixtures": len(fixtures),
        "openfootball_played": of_played,
        "ok": True,
    }


def fetch_overlay(http_get: HttpGet, reg: TeamRegistry,
                  espn_cfg: EspnConfig = DEFAULT_ESPN, dates=None):
    dates = dates or list(_daterange(espn_cfg.window_start, espn_cfg.window_end))
    overlay = []
    for ymd in dates:
        overlay.extend(espn_mod.parse_scoreboard(http_get(espn_cfg.scoreboard_url(ymd)), reg))
    return overlay


def split_overlay(fixtures, overlay):
    """Partition overlay results into (group, knockout) by team-pair (plan.md §21).

    A *group* result matches one of openfootball's group fixtures by pair; the group reconciler
    (R1–R4) owns those. A FINAL result whose pair is **not** a group fixture is a **knockout**
    result (concrete bracket teams openfootball only carries as placeholders) and is bound to a
    bracket slot in the simulator instead. Non-final unmatched overlays stay with the group
    stream (reconcile already ignores them with a warning), so nothing is silently dropped.
    """
    group_pairs = {f.pair for f in fixtures if f.group is not None and not f.is_placeholder}
    group_ov, ko_ov = [], []
    for ov in overlay:
        if ov.status is Status.FINAL and ov.pair not in group_pairs:
            ko_ov.append(ov)
        else:
            group_ov.append(ov)
    return group_ov, ko_ov


def run(as_of: Optional[datetime] = None, http_get: HttpGet = get_json,
        of_cfg: OpenfootballConfig = DEFAULT_OPENFOOTBALL,
        espn_cfg: EspnConfig = DEFAULT_ESPN,
        reg: Optional[TeamRegistry] = None, dates=None) -> List[Match]:
    as_of = as_of or datetime.now(timezone.utc)
    reg = reg or TeamRegistry.load()
    groups_obj, matches_obj = of_mod.fetch_raw(http_get, of_cfg)
    _, fixtures = of_mod.load_structure(groups_obj, matches_obj, reg)
    overlay = fetch_overlay(http_get, reg, espn_cfg, dates=dates)
    # group stage only here; knockout finals are routed to the simulator (plan.md §21).
    group_overlay, _ = split_overlay(fixtures, overlay)
    return reconcile(fixtures, group_overlay, as_of)


def _print_summary(matches: List[Match], as_of: datetime) -> None:
    finals = [m for m in matches if m.is_final]
    by_src = {}
    for m in finals:
        by_src[m.result_source] = by_src.get(m.result_source, 0) + 1
    print(f"as_of={as_of.isoformat()}  fixtures={len(matches)}  final={len(finals)}  by_source={by_src}")
    print("already-played (real scores):")
    for m in sorted(finals, key=lambda x: x.kickoff_utc):
        tag = f"[{m.result_source}]"
        print(f"  {m.kickoff_utc.date()}  Grp {m.group or '-'}  {m.home} {m.home_goals}-{m.away_goals} {m.away}  {tag}")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="WC-2026 data layer")
    p.add_argument("--verify", action="store_true", help="openfootball structure check only")
    p.add_argument("--as-of", help="ISO instant (default: now, UTC)")
    p.add_argument("--espn-start", help="override ESPN window start (YYYY-MM-DD)")
    p.add_argument("--espn-end", help="override ESPN window end (YYYY-MM-DD)")
    p.add_argument("--save", action="store_true", help="write raw+processed snapshots")
    args = p.parse_args(argv)

    if args.verify:
        s = verify_source()
        print(f"openfootball structure OK: groups={s['groups']} sizes={s['group_sizes']} "
              f"fixtures={s['fixtures']} openfootball_played={s['openfootball_played']}")
        return 0

    as_of = (datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
             if args.as_of else datetime.now(timezone.utc))
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    espn_cfg = DEFAULT_ESPN
    if args.espn_start:
        espn_cfg = dataclasses.replace(espn_cfg, window_start=args.espn_start)
    if args.espn_end:
        espn_cfg = dataclasses.replace(espn_cfg, window_end=args.espn_end)
    matches = run(as_of=as_of, espn_cfg=espn_cfg)
    _print_summary(matches, as_of)
    if args.save:
        store_mod.save_processed(matches, as_of, provenance={"openfootball": DEFAULT_OPENFOOTBALL.base_url,
                                                             "espn": DEFAULT_ESPN.base_url})
    return 0


if __name__ == "__main__":
    sys.exit(main())
