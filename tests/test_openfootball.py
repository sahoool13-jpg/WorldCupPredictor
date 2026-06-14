import pytest

from wcpredictor.data import openfootball as of
from wcpredictor.data.errors import StructureError


def test_structure_invariants(registry, of_groups, of_matches):
    groups, fixtures = of.load_structure(of_groups, of_matches, registry)
    assert len(groups) == 12
    assert sorted({len(v) for v in groups.values()}) == [4]
    assert len(fixtures) == 104


def test_of_score_fallback(registry, of_groups, of_matches):
    _, fixtures = of.load_structure(of_groups, of_matches, registry)
    by_pair = {f.pair: f for f in fixtures}
    mex = registry.team_id("Mexico"); rsa = registry.team_id("South Africa")
    aus = registry.team_id("Australia"); tur = registry.team_id("Turkey")
    assert by_pair[frozenset((mex, rsa))].of_score == (2, 0)        # played
    assert by_pair[frozenset((aus, tur))].of_score is None          # openfootball lags here


def test_wrong_group_count_raises(registry, of_matches):
    bad = {"groups": [{"name": "Group A", "teams": ["Mexico", "South Africa", "South Korea", "Czech Republic"]}]}
    with pytest.raises(StructureError):
        of.parse_groups(bad, registry)
