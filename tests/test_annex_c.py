"""The committed Annex C table is re-validated on every test run (plan.md §19.1)."""
import importlib.util
from pathlib import Path

import pytest

from wcpredictor.sim.annex_c import assign_thirds, load_table

ROOT = Path(__file__).resolve().parent.parent


def test_validate_annex_c_passes():
    """Run the committed validator (495 rows / all combos / bijection / no-rematch / slots)."""
    spec = importlib.util.spec_from_file_location("validate_annex_c", ROOT / "validate_annex_c.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        mod.main(str(ROOT / "annex_c_r32.json"))   # raises SystemExit(1) on any failure
    except SystemExit as e:
        assert e.code in (0, None), "validate_annex_c reported failures"


def test_table_has_495_rows():
    assert len(load_table()) == 495


def test_assign_is_bijection_and_no_rematch():
    combo = "EFGHIJKL"
    assign = assign_thirds(combo)
    assert set(assign) == {"A", "B", "D", "E", "G", "I", "K", "L"}
    assert sorted(assign.values()) == sorted(combo)         # bijection onto the 8 groups
    assert all(slot != third for slot, third in assign.items())  # no same-group rematch


def test_unknown_combo_raises():
    from wcpredictor.data.errors import DataError
    with pytest.raises(DataError):
        assign_thirds("ABCDEFG")   # only 7 groups
