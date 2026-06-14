"""Write the dashboard JSON, fail-loud, keeping the last-good file (plan.md §20.4).

``publish`` builds the payload first; if the build raises (e.g. a live fetch failure), the
existing ``latest.json`` is **left untouched** and the error propagates — never an empty/partial
overwrite. The page's "last updated" stamp then surfaces the staleness.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Optional


def load_prev(latest_path: Path) -> Optional[dict]:
    return json.loads(latest_path.read_text()) if latest_path.exists() else None


def write_latest(payload: dict, data_dir: Path) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    latest = data_dir / "latest.json"
    latest.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    # compact history snapshot (team -> title) for run-over-run inspection
    hist = data_dir / "history"
    hist.mkdir(exist_ok=True)
    stamp = "".join(c for c in payload["meta"]["generated_at"] if c.isdigit())[:14]
    (hist / f"{stamp}.json").write_text(json.dumps({
        "generated_at": payload["meta"]["generated_at"],
        "as_of": payload["meta"]["as_of"],
        "title": {r["team"]: r["title"] for r in payload["title_odds"]},
    }, ensure_ascii=False))
    return latest


def publish(data_dir: Path, build_fn: Callable[[Optional[dict]], dict]) -> dict:
    """Build (passing the previous payload for deltas) then write. On build failure, the
    previous latest.json is preserved and the exception is re-raised (fail loud)."""
    prev = load_prev(data_dir / "latest.json")
    payload = build_fn(prev)          # may raise -> nothing is written below
    write_latest(payload, data_dir)
    return payload
