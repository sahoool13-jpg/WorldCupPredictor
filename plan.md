# WorldCupPredictor — Build Plan

**Status:** Phase 0 (scaffolding + plan). _No engine code yet — this document is for sign-off._
**Owner:** sahoool13
**Last updated:** 2026-06-14

---

## 1. What this is

A **live, market-blind Monte Carlo** of the 2026 FIFA World Cup title race.

- **Pure model.** Title odds come from *our own* team ratings and a goal model — not
  from bookmakers. We do **not** pull, fit to, calibrate against, or sanity-check
  against betting odds at any point. Market data is out of scope by design. (We may
  *informally* eyeball published probabilities for amusement, but nothing in the
  pipeline reads them.)
- **Live.** As real group-stage results land, the pipeline auto-refreshes, re-runs the
  simulation, and reports each team's current title probability **and the delta** versus
  the previous run (who moved, who got eliminated, whose path opened up).
- **Honest.** Completed results are fixed inputs. Ratings only ever learn from matches
  that have actually been played. Nothing simulated is allowed to leak backwards into the
  ratings or into a "completed" result. See §4.

This mirrors the discipline of the UFC project: **plan-first per phase, fail loudly on
bad/missing data, point-in-time correctness, tests gate the build, and every material
decision gets walked past the owner before code is written.**

---

## 2. Operating principles (non-negotiable)

1. **Plan-first, per phase.** Before writing engine code for any phase, the phase's
   design (data contracts, algorithms, file formats, test list) is written here and
   signed off. No "while I was in there" scope creep.
2. **Fail loudly.** Missing fixtures, a result that doesn't reconcile, a group with the
   wrong number of teams, an API shape change, a tie that can't be broken by the defined
   rules — all of these **raise**, they do not silently default. Silent fallbacks are
   bugs.
3. **Point-in-time correctness.** The single most important rule. A simulation run is
   parameterised by an `as_of` timestamp. Only matches with a real, final result whose
   kickoff is at/before `as_of` are treated as completed. Everything else is simulated.
   Ratings are computed **only** from completed matches. A future or simulated result
   must never influence a rating or be recorded as fact. Tested explicitly (§4, §7).
4. **Tests gate the build.** A phase is not "done" until its tests pass. `make test`
   (and CI) must be green before merge. The format/bracket rules get adversarial unit
   tests, not smoke tests.
5. **Market-blind.** No betting odds anywhere in the data, ratings, model, or fitting.
6. **Transparent & inspectable.** Ratings, goal expectations, and per-team probabilities
   must be dumpable and human-readable. We should be able to ask "why is Brazil at 14%?"
   and trace it.
7. **Reproducible.** A run is pinned by `(as_of, results_snapshot, ratings_config,
   model_config, n_sims, seed)`. Same inputs → same outputs.
8. **Walk decisions past the owner.** Anything in §9 (Open Decisions) gets a yes before
   it's built. New forks discovered mid-phase get added there, not silently resolved.

---

## 3. The 2026 format — exact specification

This is the spec the engine must implement. **Verified June 2026** against FIFA / ESPN /
Wikipedia / FOX Sports (see §10). The bracket logic is unit-tested against these rules.

### 3.1 Structure
- **48 teams**, **12 groups (A–L) of 4**. Each team plays **3** group matches
  (round-robin within group). 3 pts win / 1 draw / 0 loss.
- **72 group matches**, then a **32-team knockout**.
- **Advance:** top **2** of every group (24 teams) **+** the **8 best 3rd-placed teams**
  across all 12 groups = **32**. Four of the twelve third-placed teams are eliminated.
- Knockout: **R32 → R16 → QF → SF → Final**, single elimination. Draw level after 90′ →
  **extra time** (2×15′) → **penalty shootout**. (No replays. Third-place playoff exists
  but is irrelevant to title odds; we may simulate it for completeness, flagged optional.)

### 3.2 Group ranking tiebreakers — **IN ORDER**
Applied to teams level on points within a group:
1. **Goal difference** (all group matches)
2. **Goals scored** (all group matches)
3. **Head-to-head** among the still-tied teams: (a) points, (b) goal difference,
   (c) goals scored in matches **between the tied teams only**
4. **Fair play** (fewer disciplinary points — cards)
5. **Drawing of lots**

> Note the ordering quirk: 2026 uses overall **GD/GS first**, then head-to-head — not
> head-to-head first. Get this right; it changes who finishes 2nd vs 3rd, which changes
> the bracket. Head-to-head is itself a mini-table among the tied subset and can re-tie.

### 3.3 Third-place ranking tiebreakers — **IN ORDER**
Applied across the **12** third-placed teams to pick the best **8**:
1. **Points**
2. **Goal difference**
3. **Goals scored**
4. **Team conduct / fair play** (fewer cards)
5. **FIFA ranking**

### 3.4 Round-of-32 third-place assignment — **the hard part**
The 8 surviving third-placed teams are slotted into 8 specific R32 fixtures (against 8 of
the group winners). **Which** third-placed team goes to **which** fixture depends on
**which set of groups** the 8 qualifiers came from — there are **C(12,8) = 495** possible
group-combinations, and FIFA's regulations define a fixed lookup mapping each combination
to an assignment. The assignment is engineered to avoid an immediate group-stage rematch
where possible and to balance the bracket.

**Requirements:**
- Implement FIFA's **official** assignment table **verbatim** — a 495-row lookup keyed by
  the sorted set of 8 qualifying group letters → the slot each third-placed team fills.
  **Do not approximate, derive heuristically, or hand-wave it.**
- The table is committed as **static reference data** (`data/reference/`), transcribed
  from FIFA's official competition regulations, with the source URL and retrieval date
  recorded. Every one of the 495 rows is present; loading asserts completeness.
- The **fixed** part of the bracket (which group winners/runners-up meet, and which 8
  winner-slots receive a third-placed team) is also encoded and tested.

**Verified fixed skeleton (R32, to be confirmed against the official bracket diagram in
Phase 4):** 8 group winners host a third-placed team; the other matchups are
winner-vs-runner-up / runner-up-vs-runner-up pairings. The third-place-receiving winners
and their *candidate* source-group sets (illustrative, pre-allocation) are e.g.
`W(A) ← 3rd from {C,E,F,H,I}`, `W(B) ← {E,F,G,I,J}`, `W(D) ← {B,E,F,I,J}`,
`W(E) ← {A,B,C,D,F}`, `W(G) ← {A,E,H,I,J}`, `W(I) ← {C,D,F,G,H}`, `W(K) ← {D,E,I,J,L}`,
`W(L) ← {E,H,I,J,K}`. **These candidate sets are a sanity check only — the binding
artifact is the full 495-row official table, which resolves exactly one third-placed team
to each slot for any given combination.**

**Acceptance for §3.4:** unit tests assert (a) exactly 32 advance, (b) the loader rejects
a table missing any of the 495 combinations, (c) for a sampled set of combinations the
assigned matchups match FIFA's published table exactly, (d) no team is assigned to two
slots and every surviving third-placed team gets exactly one slot, (e) a known worked
example (from FIFA/Wikipedia) reproduces byte-for-byte.

---

## 4. Point-in-time correctness (how we enforce it)

- Every match record carries: `kickoff_utc`, `status` (`scheduled|live|final`), and, when
  final, `home_goals`/`away_goals` plus discipline (cards). A result is "real" only when
  `status == final` from the data source.
- A run takes `as_of` (default: now). Partition fixtures into:
  - **Completed**: `status == final` AND `kickoff_utc <= as_of`. Used as fixed facts.
  - **Pending**: everything else. Simulated.
- **Ratings** are built from the **Completed** set only — both pre-tournament priors and
  any in-tournament updates. The simulator may produce a Brazil 3–0 in iteration #7; that
  number lives only inside that iteration and is discarded. It never updates a rating and
  never becomes a "result".
- Guards (all raise): a `final` match with `kickoff_utc > as_of` (future result leak); a
  match that is `final` but missing scores; re-simulating a Completed match; a Pending
  match being read as if Completed.
- Tests: a dedicated `test_point_in_time.py` constructs a partial-tournament state, runs
  with several `as_of` values, and asserts completed results are byte-identical across
  runs and never resampled, and that ratings computed at `as_of=T` ignore all matches
  after `T`.

---

## 5. Repository layout

```
WorldCupPredictor/
├── CLAUDE.md                  # how Claude Code should work in this repo (discipline)
├── plan.md                    # this file — the source of truth for phases
├── README.md                  # human-facing summary
├── Makefile                   # entrypoints: setup, lint, test, fetch, rate, sim, report
├── .gitignore
├── data/
│   ├── reference/             # COMMITTED static truth: groups, R32 assignment table,
│   │                          #   FIFA rankings snapshot, fixture skeleton (+ source refs)
│   ├── raw/                   # API pulls (snapshots, point-in-time, committed or cached)
│   └── processed/             # cleaned/derived tables (gitignored unless a pinned run)
├── src/wcpredictor/           # the package (created per-phase; empty in Phase 0)
│   ├── data/                  # Phase 1: fetch + clean + store
│   ├── ratings/               # Phase 2: Elo + form + squad-strength
│   ├── model/                 # Phase 3: Dixon-Coles / Poisson goal model
│   ├── sim/                   # Phase 4: tournament Monte Carlo + bracket rules
│   └── report/                # Phase 5: title odds + deltas
├── tests/                     # pytest; bracket/format tests are adversarial
├── reports/                   # generated outputs + run history (for deltas)
└── .github/workflows/         # CI (lint+test gate) + scheduled live-update (Phase 5)
```

Static reference data is **committed** so the format/bracket logic is testable without any
network access. The R32 assignment table and FIFA-ranking snapshot live here with their
provenance.

---

## 6. Phases

Each phase is **plan-first**: its detailed sub-plan is appended here and signed off before
code. A phase ships only when its tests are green. Dependencies are strict (n needs n-1).

### Phase 0 — Scaffolding & plan _(this PR)_
Repo structure, `CLAUDE.md`, `Makefile`, this `plan.md`, `.gitignore`, `README.md`.
No engine code. **Deliverable:** owner sign-off on the phase list and the §3 format spec.

### Phase 1 — Data layer
- **Decision gate (D1):** pick the FREE football data API. **Before committing**, verify
  that the chosen provider's *free tier* actually covers the 2026 World Cup
  (fixtures + live results + group standings + cards/discipline if available). Candidates
  to verify: **football-data.org** (has a World Cup competition; check free-tier match &
  standings coverage and rate limits) and **API-Football** (api-football.com; check
  free-tier daily-call cap and that WC 2026 league/season is included). **Do not scrape.**
  Record the verification (endpoints hit, fields returned, limits) in this file. If
  neither free tier covers it, stop and bring options to the owner.
- Pull **fixtures, results, standings, discipline** into a clean, versioned local store
  (point-in-time snapshots in `data/raw/`, normalized tables in `data/processed/`).
- Normalize team identities to a stable internal id (handle name variants).
- API key via **GitHub Actions secret**, injected as env var — never committed (mirrors
  the Kaggle-key setup). Local dev reads from a gitignored `.env`/env var.
- **Fail loudly:** schema drift, missing groups, a group ≠ 4 teams, a fixture without two
  known teams, duplicate fixtures, non-monotonic result updates.
- **Tests:** parsing fixtures of saved fixtures→internal model; snapshot reconciliation;
  guard tests for each failure mode; a frozen sample payload as a golden file.

### Phase 2 — Team strength ratings
- **Elo-based**, blended with **recent form** and a **squad-strength proxy**. Transparent,
  per-team, inspectable. Computed **only** from completed matches (§4).
- Pre-tournament prior from historical internationals (and the squad proxy); in-tournament
  updates as group results land.
- **Decisions (D2):** Elo K-factor & margin-of-victory handling, home/neutral adjustment
  (2026 has hosts USA/Canada/Mexico — partial home advantage), form window & weighting,
  and the squad-strength proxy source (must be free & market-blind, e.g. a transparent
  squad-value/known-player metric — **not** odds-derived).
- **Tests:** rating determinism; monotonicity (beating a strong team raises rating more
  than beating a weak one); point-in-time (ratings at `as_of=T` ignore post-T matches);
  inspect/dump round-trips.

### Phase 3 — Match (goal) model
- **Dixon-Coles / Poisson** bivariate goal model driven by the team ratings, producing
  **scoreline probabilities** — not just W/D/L. Scorelines are required for the group
  GD/GS tiebreakers and for extra-time/penalty resolution.
- Dixon-Coles low-score correction; attack/defense strengths derived from ratings; home
  adjustment consistent with Phase 2.
- **Decisions (D3):** parameter estimation approach (fit on historical international goals
  vs map ratings→λ analytically), draw inflation, and how ratings map to expected goals.
- **Tests:** probabilities sum to 1; expected-goals sanity vs rating gap; symmetry on
  neutral ground for equal ratings; scoreline distribution shape; penalty/ET sub-model is
  ~coin-flip near parity and skews with rating gap.

### Phase 4 — Tournament Monte Carlo
- Simulate the **remaining** tournament many times from the **current real state**
  (Completed fixed, Pending simulated), applying **all** rules from §3 exactly:
  group tables + tiebreakers (§3.2), third-place ranking (§3.3), the **official 495-row
  R32 assignment** (§3.4), then R32→Final with ET/penalties.
- Output per team: P(advance), P(reach R16/QF/SF/Final), **P(win title)**, expected
  finish. Aggregated over N sims with a fixed seed.
- **Decisions (D4):** N sims (variance vs runtime), seeding/parallelism, drawing-of-lots
  handling (random, seeded), and FIFA-ranking source for §3.3 tiebreak (committed
  snapshot).
- **Tests (adversarial, the heart of correctness):**
  - assert **exactly 32** teams enter the knockout every simulation;
  - assert each group yields exactly top-2 + correct 3rd, with constructed tie scenarios
    that exercise GD→GS→H2H→fair-play→lots in order;
  - assert the **third-place assignment matches FIFA's official table** for sampled and
    worked-example combinations, table-completeness (495), and one-slot-per-team;
  - assert no Completed result is ever resampled;
  - end-to-end: a fully-completed historical-style bracket reproduces the known winner.

### Phase 5 — Live update + report
- GitHub **Actions** workflow on a schedule (and/or on result changes) that refreshes
  results (Phase 1), recomputes ratings (Phase 2), re-runs the sim (Phase 4), and writes a
  report: **current title odds** + the **delta vs the previous run** — who moved, who was
  eliminated, whose path opened up. Run history persisted under `reports/` for deltas.
- **Fail loudly** in CI: if data fetch fails or reconciliation breaks, the workflow fails
  (no stale/garbage report published).
- **Decisions (D5):** schedule cadence, report format (Markdown table / committed
  artifact / GitHub Pages), and what "moved" thresholds to highlight.
- **Tests:** delta computation against two canned run snapshots; report renders; workflow
  dry-run.

---

## 7. Cross-cutting test strategy

- `pytest`; CI runs `make lint` + `make test` and must be green to merge.
- **Format/bracket suite** is adversarial and treated as a contract: 32-advance,
  tiebreaker ordering, third-place ranking, the 495-row table completeness + sampled
  correctness + worked example, one-slot-per-team.
- **Point-in-time suite** (§4): no future/simulated leakage; ratings ignore post-`as_of`.
- **Golden files** for data parsing and for end-to-end run reproducibility (pinned seed).
- Determinism: identical inputs → identical title odds.

---

## 8. Data & secrets handling

- **Committed (truth):** groups A–L membership, the R32 assignment table (495 rows) + the
  fixed bracket skeleton, a FIFA-ranking snapshot, and the static fixture skeleton — each
  with source URL + retrieval date in `data/reference/`.
- **Fetched:** fixtures/results/standings/discipline via the Phase-1 API; stored as
  point-in-time snapshots in `data/raw/`.
- **Secrets:** API key only via **GitHub Actions secret** → env var at runtime; local dev
  via gitignored env. Never committed. `.gitignore` covers `.env`, keys, caches.

---

## 9. Open decisions (need owner sign-off)

| ID | Decision | Where | Default leaning |
|----|----------|-------|-----------------|
| **D0** | Approve this phase list + §3 format spec | Phase 0 | — |
| **D1** | Which free API (verify WC-2026 free-tier coverage first; no scraping) | Phase 1 | Verify football-data.org first, then API-Football |
| **D2** | Elo K / MoV, home-advantage for hosts, form window, squad-strength proxy source (market-blind) | Phase 2 | Elo+MoV, partial home edge, transparent squad-value proxy |
| **D3** | Goal-model fit (historical fit vs analytic ratings→λ), Dixon-Coles tau | Phase 3 | Dixon-Coles, ratings→λ with historical calibration |
| **D4** | N sims, seeding/parallelism, lots handling, FIFA-ranking snapshot source | Phase 4 | 50k sims, seeded, lots=seeded-random |
| **D5** | Live cadence, report format, "who moved" thresholds | Phase 5 | Daily + on-change, Markdown artifact committed to `reports/` |

> **Language/stack assumption (flag if you disagree):** Python + `pytest`, `numpy`/`pandas`
> for the sim, `requests` for the API. Chosen for fast Monte Carlo + transparent ratings.

---

## 10. Sources (format verification, June 2026)

- FIFA — World Cup 2026 groups, qualification & tie-breakers:
  https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/articles/groups-how-teams-qualify-tie-breakers
- ESPN — 2026 World Cup format, tiebreakers, schedule:
  https://www.espn.com/soccer/story/_/id/47108758/2026-fifa-world-cup-format-tiebreakers-fixtures-schedule
- FOX Sports — Group-stage tiebreakers & how third-place teams advance:
  https://www.foxsports.com/stories/soccer/fifa-world-cup-group-stage-third-place-tiebreakers
- Wikipedia — 2026 FIFA World Cup knockout stage (R32 bracket + third-place allocation):
  https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_knockout_stage

> The full 495-row third-place→R32 assignment table is to be transcribed from FIFA's
> **official competition regulations** in Phase 4 (the authoritative source), with the
> public reproductions above used for cross-checking. Provenance recorded in
> `data/reference/`.

---

_End of plan. Awaiting sign-off on D0 (and a steer on D1's verification scope) before any
Phase-1 engine code._
