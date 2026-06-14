# src/wcpredictor — the package

Modules are created per phase, each plan-first and test-gated. Layout (see `plan.md` §5–§6):

| Module | Phase | Responsibility |
|--------|-------|----------------|
| `data/` | 1 | **Implemented.** openfootball static structure + ESPN live-results overlay, reconciled point-in-time (`teams`, `model`, `sources`, `openfootball`, `espn`, `reconcile`, `store`, `pipeline`). Stdlib-only. |
| `ratings/` | 2 | **Implemented.** Pre-tournament Elo prior (`prior`, from martj42) + in-tournament Elo + recent form + squad proxy, blended with shrinkage (`elo`, `engine`). Built **only** from played matches; inspectable via `explain()`. |
| `model/` | 3 | **Implemented.** Dixon-Coles / Poisson scoreline matrices (`dixon_coles`) driven by Phase-2 blended ratings (`lambdas`), calibrated market-blind on martj42 goals (`calibrate`), + extra-time/penalty knockout resolution (`etp`). `make model` / `make calibrate`. |
| `sim/` | 4 | **Implemented.** Tournament Monte Carlo from the true current state: group sim + tiebreakers + third-place ranking (`standings`), verbatim Annex C R32 assignment (`annex_c`), bracket R32→Final with ET/penalties (`bracket`), aggregation → title/advancement odds (`engine`). `make simulate`. |
| `report/` | 5 | **Implemented.** Builds the dashboard `latest.json` (title odds + run-over-run deltas + standings + through/eliminated + "last updated"; `payload`) and publishes it fail-loud, keeping last-good (`io`, `run`). Static page in `docs/`; scheduled by `.github/workflows/dashboard.yml`. |

Cross-cutting (introduced as needed): an `as_of` / point-in-time partition used everywhere
(`plan.md` §4) — completed matches are fixed facts; everything else is simulated.
