"""Blend mechanics (plan.md §17.4): documented weights honored; z-scoring; explain() round
-trips and reconstructs the blend."""
import statistics

from wcpredictor.ratings.engine import compute_ratings

from _ratings_util import config, match, utc

PRIOR = {"A": 1700.0, "B": 1550.0, "C": 1500.0, "D": 1400.0}
MS = [match("A", "B", 2, 0, utc(2026, 6, 12)), match("C", "D", 1, 1, utc(2026, 6, 13))]
ASOF = utc(2026, 6, 15)


def test_weights_honored():
    only_elo = compute_ratings(MS, ASOF, PRIOR, config(weights={"elo": 1.0, "form": 0.0, "squad": 0.0}))
    for t, d in only_elo.items():
        assert abs(d.blend_z - d.z_elo) < 1e-9
    only_form = compute_ratings(MS, ASOF, PRIOR, config(weights={"elo": 0.0, "form": 1.0, "squad": 0.0}))
    for t, d in only_form.items():
        assert abs(d.blend_z - d.z_form) < 1e-9


def test_zscores_normalized():
    d = compute_ratings(MS, ASOF, PRIOR, config())
    zs = [x.z_elo for x in d.values()]
    assert abs(statistics.fmean(zs)) < 1e-9
    assert abs(statistics.pstdev(zs) - 1.0) < 1e-9


def test_explain_reconstructs_blend():
    d = compute_ratings(MS, ASOF, PRIOR, config())
    w = config()["weights"]
    mu = statistics.fmean([x.elo_star for x in d.values()])
    sd = statistics.pstdev([x.elo_star for x in d.values()])
    for t, det in d.items():
        # exact reconstruction from the unrounded z-scores
        recon = w["elo"] * det.z_elo + w["form"] * det.z_form + w["squad"] * det.z_squad
        assert abs(recon - det.blend_z) < 1e-9
        assert abs((mu + sd * det.blend_z) - det.rating) < 1e-6
        # explain() exposes the same contributions (rounded for display)
        e = det.explain()
        assert e["contrib"]["elo"] == round(det.z_elo, 3)
