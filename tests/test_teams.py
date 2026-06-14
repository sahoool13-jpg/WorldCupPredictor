import pytest

from wcpredictor.data.errors import UnknownTeam


def test_canonical_and_aliases(registry):
    assert registry.name("Türkiye") == "Turkey"
    assert registry.name("Turkiye") == "Turkey"
    assert registry.name("Czechia") == "Czech Republic"
    assert registry.name("United States") == "USA"
    assert registry.name("Korea Republic") == "South Korea"
    assert registry.name("Bosnia and Herzegovina") == "Bosnia & Herzegovina"


def test_diacritics_and_case_fold(registry):
    # folded automatically by the slug normalizer, no alias entry needed
    assert registry.name("curaçao") == "Curaçao"
    assert registry.name("CURACAO") == "Curaçao"


def test_unknown_team_raises(registry):
    with pytest.raises(UnknownTeam):
        registry.name("Wakanda")


def test_team_id_stable(registry):
    assert registry.team_id("Türkiye") == registry.team_id("Turkey")
