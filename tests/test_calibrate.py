import json
import math
from pathlib import Path

from wcpredictor.model import calibrate


def test_solve3():
    H = [[2.0, 0.0, 0.0], [0.0, 3.0, 0.0], [0.0, 0.0, 4.0]]
    assert calibrate._solve3(H, [2.0, 9.0, 8.0]) == [1.0, 3.0, 2.0]


def test_poisson_glm_recovers_known_params():
    true = (0.1, 0.2, 0.3)  # mu, beta, gamma
    obs = []
    for d in (-2.0, -1.0, 0.0, 1.0, 2.0):
        for hf in (0.0, 1.0):
            y = math.exp(true[0] + true[1] * d + true[2] * hf)
            obs.append((y, d, hf))   # y == lambda_true -> MLE sits at the true params
    mu, beta, gamma = calibrate.fit_poisson_glm(obs)
    assert abs(mu - true[0]) < 1e-6
    assert abs(beta - true[1]) < 1e-6
    assert abs(gamma - true[2]) < 1e-6


def test_committed_params_snapshot_is_sane():
    p = json.loads(Path("data/reference/goal_model_2026.json").read_text())
    for k in ("mu", "beta", "gamma_home", "rho", "scale"):
        assert k in p
    assert math.exp(p["mu"]) > 0.5            # plausible baseline goals
    assert p["beta"] > 0                      # stronger team scores more
    assert p["gamma_home"] > 0                # home edge positive
    assert p["scale"] == 100.0
