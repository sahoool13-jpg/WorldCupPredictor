# src/wcpredictor — the package

Modules are created per phase, each plan-first and test-gated. Layout (see `plan.md` §5–§6):

| Module | Phase | Responsibility |
|--------|-------|----------------|
| `data/` | 1 | **Implemented.** openfootball static structure + ESPN live-results overlay, reconciled point-in-time (`teams`, `model`, `sources`, `openfootball`, `espn`, `reconcile`, `store`, `pipeline`). Stdlib-only. |
| `ratings/` | 2 | Elo + recent form + squad-strength proxy. Built **only** from completed matches. Inspectable. |
| `model/` | 3 | Dixon-Coles / Poisson goal model → scoreline probabilities; extra-time + penalty sub-model. |
| `sim/` | 4 | Tournament Monte Carlo: group tables + tiebreakers, third-place ranking, the official 495-row R32 assignment, R32→Final. |
| `report/` | 5 | Title odds + delta vs previous run. |

Cross-cutting (introduced as needed): an `as_of` / point-in-time partition used everywhere
(`plan.md` §4) — completed matches are fixed facts; everything else is simulated.
