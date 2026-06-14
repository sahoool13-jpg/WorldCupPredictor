from wcpredictor.data import espn
from wcpredictor.data.model import Status


def test_parse_final_and_scheduled(registry, espn_days):
    results = []
    for day in espn_days:
        results.extend(espn.parse_scoreboard(day, registry))

    by_pair = {r.pair: r for r in results}
    aus = registry.team_id("Australia"); tur = registry.team_id("Turkey")
    r = by_pair[frozenset((aus, tur))]
    assert r.status is Status.FINAL
    assert r.goals_by_team[aus] == 2 and r.goals_by_team[tur] == 0

    ger = registry.team_id("Germany"); cur = registry.team_id("Curaçao")
    s = by_pair[frozenset((ger, cur))]
    assert s.status is Status.SCHEDULED
    assert s.goals_by_team[ger] is None


def test_orientation_independent_attribution(registry, espn_days):
    # ESPN lists Scotland(home) 1 - Haiti(away) 0; attribution is by team identity
    results = [r for day in espn_days for r in espn.parse_scoreboard(day, registry)]
    by_pair = {r.pair: r for r in results}
    hai = registry.team_id("Haiti"); sco = registry.team_id("Scotland")
    r = by_pair[frozenset((hai, sco))]
    assert r.goals_by_team[hai] == 0 and r.goals_by_team[sco] == 1
