"""Host home-edge must apply to ALL THREE hosts (USA, Canada, Mexico), not be hardcoded to
one (plan.md §17.7 D2-params)."""
import json
from pathlib import Path

from wcpredictor.ratings.engine import compute_ratings

from _ratings_util import config, match, utc

PRIOR = {"USA": 1500.0, "Canada": 1500.0, "Mexico": 1500.0,
         "Brazil": 1500.0, "Argentina": 1500.0}


def test_all_three_hosts_get_the_edge():
    # equal ratings: a host drawing 0-0 at home underperforms its (edge-boosted) expectation
    for host in ("USA", "Canada", "Mexico"):
        d = compute_ratings([match(host, "Brazil", 0, 0, utc(2026, 6, 12))],
                            utc(2026, 6, 15), PRIOR, config())
        assert d[host].form < 0          # expected > 0.5 due to home edge -> negative form
        assert d["Brazil"].form > 0


def test_non_hosts_get_no_edge():
    d = compute_ratings([match("Brazil", "Argentina", 0, 0, utc(2026, 6, 12))],
                        utc(2026, 6, 15), PRIOR, config())
    assert abs(d["Brazil"].form) < 1e-9
    assert abs(d["Argentina"].form) < 1e-9


def test_config_lists_all_three_hosts():
    cfg = json.loads(Path("configs/ratings.json").read_text())
    assert set(cfg["hosts"]) == {"USA", "Canada", "Mexico"}
