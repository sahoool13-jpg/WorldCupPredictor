"""Market-blind calibration of the goal model (plan.md §18.4).

Replays the Phase-2 Elo over historical internationals (martj42), then fits the analytic
ratings->goals map: a Poisson GLM (Newton) for (mu, beta, gamma_home) using each match's
**pre-match** Elo, and a 1-D MLE grid for the Dixon-Coles rho. Calibrated only on real goals
(never odds). Result committed as data/reference/goal_model_2026.json.

  python -m wcpredictor.model.calibrate --build [--csv <path-or-url>]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

from ..data.http import get_text
from ..ratings import elo
from ..ratings.prior import PRIOR_PARAMS, parse_rows
from . import dixon_coles as dc

CSV_URL = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
CALIB_START = "1994-01-01"   # modern era (Elo is replayed over ALL history regardless)
_REF = Path(__file__).resolve().parents[3] / "data" / "reference"


def replay_and_collect(rows: List[dict], calib_start: str, scale: float, elo_params: dict):
    """Run Elo in date order; collect (y, d_signed, home_flag) regression observations and
    per-match records (for the rho fit) for matches on/after calib_start."""
    ratings: Dict[str, float] = {}
    obs: List[Tuple[float, float, float]] = []   # (goals, d_signed, home_flag)
    matches: List[Tuple[float, float, int, int]] = []  # (lam-feature d, neutral?, hs, as)
    for r in sorted(rows, key=lambda x: x["date"]):
        hs, as_ = r["home_score"], r["away_score"]
        if hs in ("", "NA", None) or as_ in ("", "NA", None):
            continue
        h, a = r["home_team"], r["away_team"]
        rh = ratings.get(h, elo_params["init"])
        ra = ratings.get(a, elo_params["init"])
        neutral = str(r.get("neutral", "")).upper() == "TRUE"
        if r["date"] >= calib_start:
            d = (rh - ra) / scale
            hflag = 0.0 if neutral else 1.0
            obs.append((float(int(hs)), d, hflag))      # home observation
            obs.append((float(int(as_)), -d, 0.0))      # away observation
            matches.append((d, 1 if neutral else 0, int(hs), int(as_)))
        elo.apply_match(ratings, h, a, int(hs), int(as_), neutral=neutral,
                        k=elo_params["k"], home_adv=elo_params["home_adv"],
                        default=elo_params["init"])
    return obs, matches


def _solve3(H: List[List[float]], g: List[float]) -> List[float]:
    """Solve 3x3 H x = g by Gaussian elimination."""
    M = [row[:] + [g[i]] for i, row in enumerate(H)]
    for c in range(3):
        piv = max(range(c, 3), key=lambda r: abs(M[r][c]))
        M[c], M[piv] = M[piv], M[c]
        pivot = M[c][c]
        for j in range(c, 4):
            M[c][j] /= pivot
        for r in range(3):
            if r != c:
                f = M[r][c]
                for j in range(c, 4):
                    M[r][j] -= f * M[c][j]
    return [M[i][3] for i in range(3)]


def fit_poisson_glm(obs, iters: int = 30) -> Tuple[float, float, float]:
    """Newton-Raphson MLE for log lam = mu + beta*d + gamma*home_flag."""
    theta = [math.log(1.4), 0.0, 0.0]
    for _ in range(iters):
        g = [0.0, 0.0, 0.0]
        H = [[0.0] * 3 for _ in range(3)]
        for y, d, hf in obs:
            x = (1.0, d, hf)
            lam = math.exp(theta[0] + theta[1] * d + theta[2] * hf)
            r = y - lam
            for a in range(3):
                g[a] += r * x[a]
                for b in range(3):
                    H[a][b] += lam * x[a] * x[b]
        step = _solve3(H, g)
        theta = [theta[i] + step[i] for i in range(3)]
        if max(abs(s) for s in step) < 1e-9:
            break
    return theta[0], theta[1], theta[2]


def fit_rho(matches, mu: float, beta: float, gamma: float,
            grid=None) -> float:
    grid = grid if grid is not None else [x / 200.0 for x in range(-30, 31)]  # -0.15..0.15
    best_rho, best_ll = 0.0, -1e18
    for rho in grid:
        ll = 0.0
        ok = True
        for d, neutral, hs, as_ in matches:
            gh = 0.0 if neutral else gamma
            lam_h = math.exp(mu + beta * d + gh)
            lam_a = math.exp(mu - beta * d)
            tau = dc.dc_tau(hs, as_, lam_h, lam_a, rho)
            if tau <= 0:
                ok = False
                break
            ll += (math.log(dc.poisson_pmf(min(hs, 12), lam_h))
                   + math.log(dc.poisson_pmf(min(as_, 12), lam_a)) + math.log(tau))
        if ok and ll > best_ll:
            best_ll, best_rho = ll, rho
    return best_rho


def build(text: str, scale: float = 100.0, calib_start: str = CALIB_START,
          elo_params: dict = PRIOR_PARAMS) -> dict:
    rows = parse_rows(text)
    obs, matches = replay_and_collect(rows, calib_start, scale, elo_params)
    mu, beta, gamma = fit_poisson_glm(obs)
    rho = fit_rho(matches, mu, beta, gamma)
    return {
        "_source": "martj42/international_results (results.csv)",
        "_source_url": CSV_URL,
        "_calib_start": calib_start,
        "_elo_params": elo_params,
        "_meta": {"n_obs": len(obs), "n_matches": len(matches)},
        "scale": scale, "mu": round(mu, 6), "beta": round(beta, 6),
        "gamma_home": round(gamma, 6), "rho": round(rho, 4),
    }


def load_params(ref_dir: Path = _REF) -> dict:
    return json.loads((ref_dir / "goal_model_2026.json").read_text())


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Calibrate the goal model from martj42 goals")
    p.add_argument("--build", action="store_true", required=True)
    p.add_argument("--csv", default=CSV_URL)
    p.add_argument("--out", default=str(_REF / "goal_model_2026.json"))
    args = p.parse_args(argv)
    text = Path(args.csv).read_text() if Path(args.csv).exists() else get_text(args.csv)
    params = build(text)
    Path(args.out).write_text(json.dumps(params, ensure_ascii=False, indent=2))
    print(f"calibrated on {params['_meta']['n_matches']} matches "
          f"(since {params['_calib_start']}):")
    print(f"  mu={params['mu']} beta={params['beta']} gamma_home={params['gamma_home']} "
          f"rho={params['rho']} scale={params['scale']}")
    print(f"  => baseline goals exp(mu)={math.exp(params['mu']):.2f}, "
          f"home edge x{math.exp(params['gamma_home']):.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
