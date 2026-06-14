# WorldCupPredictor

A **live, market-blind Monte Carlo** of the 2026 FIFA World Cup title race.

Title odds are produced entirely from **our own** team ratings and goal model — **no
betting odds** are pulled, fitted to, or referenced anywhere. As real group-stage results
land, the pipeline auto-refreshes, re-runs the simulation, and reports each team's current
**title probability** plus the **delta** versus the previous run (who moved, who got
eliminated, whose path opened up).

> **Status: Phase 0 — scaffolding + plan only. No engine code yet.**
> See **[`plan.md`](./plan.md)** for the full phased build plan and the exact 2026 format
> spec, and **[`CLAUDE.md`](./CLAUDE.md)** for the working rules.

## Why it's built this way

Mirrors the discipline of the UFC project:

- **Plan-first, per phase** — every phase is designed and signed off before code.
- **Point-in-time correct** — ratings learn only from matches that have *actually* happened;
  no future/simulated result ever leaks backward. Completed results are fixed inputs.
- **Fail loudly** — bad/missing data raises; no silent fallbacks.
- **Tests gate the build** — the 2026 format and bracket rules are unit-tested as contracts
  (assert 32 advance; assert the third-place R32 assignment matches FIFA's official table).
- **Market-blind** — bookmaker odds are out of scope by design.

## The 2026 format (modeled natively)

48 teams · 12 groups of 4 · top 2 + the 8 best third-placed teams = a 32-team knockout ·
R32 → R16 → QF → SF → Final with extra time + penalties. The Round-of-32 placement of the 8
third-placed qualifiers uses FIFA's **official 495-combination assignment table**,
implemented verbatim. Full spec and tiebreaker ordering: [`plan.md`](./plan.md) §3.

## Phases

0. Scaffolding & plan _(current)_
1. Data layer (free API, verified WC-2026 coverage; no scraping)
2. Team strength ratings (Elo + form + squad-strength proxy)
3. Match model (Dixon-Coles / Poisson scoreline probabilities)
4. Tournament Monte Carlo (all group + third-place + bracket rules)
5. Live update + report (Actions workflow; odds + deltas)

## Usage

```bash
make help     # list entrypoints
make test     # run the test suite (gates the build)
```

Pipeline targets (`fetch`, `rate`, `model`, `simulate`, `report`, `live`) are placeholders
until their phase ships — they fail loudly by design.
