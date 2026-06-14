"""Load the committed FIFA Annex C R32 third-place assignment (plan.md §19.1).

The table is the source of truth (`annex_c_r32.json` at repo root) — **loaded, never
fetched/derived**. `assign[X] = Y` means Winner(X) plays the third-placed team of Group Y.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable

from ..data.errors import DataError

_ROOT = Path(__file__).resolve().parents[3]
_TABLE_PATH = _ROOT / "annex_c_r32.json"

WINNER_SLOTS = ("A", "B", "D", "E", "G", "I", "K", "L")  # winners that face a third


@lru_cache(maxsize=1)
def load_table(path: Path = _TABLE_PATH) -> dict:
    data = json.loads(Path(path).read_text())
    table = data["table"]
    if len(table) != 495:
        raise DataError(f"Annex C table has {len(table)} rows, expected 495")
    return table


def combo_key(qualified_groups: Iterable[str]) -> str:
    groups = sorted(qualified_groups)
    if len(groups) != 8 or len(set(groups)) != 8:
        raise DataError(f"need exactly 8 distinct qualifying groups, got {groups}")
    return "".join(groups)


def assign_thirds(qualified_groups: Iterable[str]) -> Dict[str, str]:
    """The 8 third-placed groups (whose thirds qualified) -> {winner_group: third_group}.

    FAILS LOUD if the combination is missing (impossible — all 495 are present)."""
    key = combo_key(qualified_groups)
    table = load_table()
    row = table.get(key)
    if row is None:
        raise DataError(f"Annex C: no row for combination {key!r} (should be impossible)")
    return dict(row["assign"])
