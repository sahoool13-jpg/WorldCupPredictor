import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
GOLDEN = Path(__file__).resolve().parent / "golden"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))  # repo root (for validate_annex_c.py)


def load_golden(name: str) -> dict:
    return json.loads((GOLDEN / name).read_text())


@pytest.fixture(scope="session")
def registry():
    from wcpredictor.data.teams import TeamRegistry
    return TeamRegistry.load()


@pytest.fixture
def of_groups():
    return load_golden("openfootball.groups.json")


@pytest.fixture
def of_matches():
    return load_golden("openfootball.worldcup.json")


@pytest.fixture
def espn_days():
    return [load_golden("espn_20260613.json"), load_golden("espn_20260614.json")]
