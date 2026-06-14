# src/wcpredictor — the package

**Empty in Phase 0 (no engine code yet).** Modules are created per phase, each plan-first
and test-gated. Planned layout (see `plan.md` §5–§6):

| Module | Phase | Responsibility |
|--------|-------|----------------|
| `data/` | 1 | Fetch fixtures/results/standings/discipline from the chosen free API; normalize team ids; point-in-time snapshots. No scraping. |
| `ratings/` | 2 | Elo + recent form + squad-strength proxy. Built **only** from completed matches. Inspectable. |
| `model/` | 3 | Dixon-Coles / Poisson goal model → scoreline probabilities; extra-time + penalty sub-model. |
| `sim/` | 4 | Tournament Monte Carlo: group tables + tiebreakers, third-place ranking, the official 495-row R32 assignment, R32→Final. |
| `report/` | 5 | Title odds + delta vs previous run. |

Cross-cutting (introduced as needed): an `as_of` / point-in-time partition used everywhere
(`plan.md` §4) — completed matches are fixed facts; everything else is simulated.
