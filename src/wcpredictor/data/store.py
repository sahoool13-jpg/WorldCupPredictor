"""Point-in-time snapshots + provenance (plan.md §12.3). Immutable, timestamped raw bytes
plus a normalized resolved view. Deliberately simple JSON; no third-party deps.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from .model import Match

_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = _ROOT / "data" / "raw"
PROCESSED_DIR = _ROOT / "data" / "processed"


def _utcnow_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def save_raw(name: str, payload, stamp: str = "", raw_dir: Path = RAW_DIR) -> Path:
    stamp = stamp or _utcnow_stamp()
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"{stamp}.{name}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=0))
    return path


def matches_to_dicts(matches: List[Match]) -> list:
    return [
        {
            "match_id": m.match_id, "round": m.round, "group": m.group,
            "home": m.home, "away": m.away,
            "kickoff_utc": m.kickoff_utc.isoformat(),
            "status": m.status.value,
            "home_goals": m.home_goals, "away_goals": m.away_goals,
            "result_source": m.result_source,
        }
        for m in matches
    ]


def save_processed(matches: List[Match], as_of: datetime, provenance: dict,
                   stamp: str = "", processed_dir: Path = PROCESSED_DIR) -> Path:
    stamp = stamp or _utcnow_stamp()
    processed_dir.mkdir(parents=True, exist_ok=True)
    path = processed_dir / f"{stamp}.state.json"
    path.write_text(json.dumps({
        "as_of": as_of.isoformat(),
        "provenance": provenance,
        "n_final": sum(1 for m in matches if m.is_final),
        "matches": matches_to_dicts(matches),
    }, ensure_ascii=False, indent=2))
    return path
