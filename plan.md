# WorldCupPredictor — Build Plan

**Status:** D0–D2 resolved. **Phases 1–2 BUILT, VERIFIED & MERGED** (data layer §12/§15/§16;
ratings §17 — 62 tests green; live ratings sane vs FIFA June-2026 top-3). **Phase 3 goal-model
sub-plan (§18) drafted — awaiting sign-off** (D3-map/calib/etp/input). Dashboard = final phase,
built LAST (§6 Phase 5). No Phase-3 engine code until §18 is signed off.
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
- **Final deliverable = a live web dashboard** (not a Markdown report): a **static GitHub
  Pages** page rebuilt by a **scheduled Action** that reruns the pipeline and commits
  web-friendly JSON, so the page auto-refreshes as results land (title odds, run-over-run
  deltas, standings, eliminated/through, "last updated"). Static + scheduled rebuild, no
  server. Specified in §6 Phase 5 — **built LAST**, after the model is correct and validated.

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
4. **Fair play** (fewer disciplinary points — cards) — _our source (openfootball) has no
   card data; per **D-cards** this step is skipped with a loud, recorded warning and we fall
   through to lots._
5. **Drawing of lots**

> Note the ordering quirk: 2026 uses overall **GD/GS first**, then head-to-head — not
> head-to-head first. Get this right; it changes who finishes 2nd vs 3rd, which changes
> the bracket. Head-to-head is itself a mini-table among the tied subset and can re-tie.

### 3.3 Third-place ranking tiebreakers — **IN ORDER**
Applied across the **12** third-placed teams to pick the best **8**:
1. **Points**
2. **Goal difference**
3. **Goals scored**
4. **Team conduct / fair play** (fewer cards) — _no card data in our source; per **D-cards**
   skipped with a recorded warning, falling through to FIFA ranking._
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

## 4. Point-in-time correctness & the live "real-results-fixed" property

This is a **live, mid-tournament** model. **Matches that have already been played are
FIXED, REAL inputs.** Their actual scores (and cards) lock the current group standings and
are **never re-simulated**. Each Monte Carlo simulation seeds the group tables from the
**true current state** — real points, real goal difference, real goals scored, real cards
already banked — and simulates **only the remaining unplayed fixtures**. This
real-results-fixed / only-future-simulated property is the **core of the whole model** and
**Phase 4 is gated on it** (§6, §4.1).

- Every match record carries: `kickoff_utc`, `status` (`scheduled|live|final`), and, when
  final, `home_goals`/`away_goals` plus discipline (cards). A result is "real" only when
  `status == final` from the data source.
- A run takes `as_of` (default: now). Partition fixtures into:
  - **Completed**: `status == final` AND `kickoff_utc <= as_of`. Used as fixed facts.
  - **Pending**: everything else. Simulated.
- **Current state is computed once** from the Completed set: per-team banked points, GD,
  GS, cards, and head-to-head — the real standings. Every simulation iteration **starts
  from this exact state** and only adds the outcomes of Pending fixtures.
- **Ratings** are built from the **Completed** set only — both pre-tournament priors and
  any in-tournament updates. The simulator may produce a Brazil 3–0 in iteration #7; that
  number lives only inside that iteration and is discarded. It never updates a rating,
  never changes the banked standings, and never becomes a "result".
- Guards (all raise): a `final` match with `kickoff_utc > as_of` (future result leak); a
  match that is `final` but missing scores; re-simulating a Completed match; a Pending
  match being read as if Completed; a simulated standings table whose banked (pre-future)
  component diverges from the real current standings.

### 4.1 The live-state test contract (gates Phase 4)

`tests/test_live_state.py` + `tests/test_point_in_time.py` assert, against constructed
partial-tournament states and several `as_of` values:

- **(a) Completed results are never re-rolled.** Across many sim iterations, every
  Completed match's score is byte-identical to the real input; no Completed fixture is ever
  resampled. (Instrument the RNG/draw path: it is only ever invoked for Pending fixtures.)
- **(b) Simulated standings before any future match == real current standings.** Take the
  per-iteration group table contribution from already-played matches and assert it exactly
  equals the standings computed directly from the real Completed results — points, GD, GS,
  cards, ordering — for every group, every iteration.
- **(c) Already-decided teams show 0% / 100%.** A team mathematically eliminated given the
  real current state shows **P(advance)=0** (and P(title)=0); a team mathematically already
  through shows **P(advance)=100%**. Constructed scenarios for both, plus an
  already-qualified-as-group-winner case.
- **(d) New real result shifts from the prior state correctly.** Re-running after an
  additional real result moves probabilities in the correct direction and re-seeds from the
  updated true state (the newly-played fixture leaves Pending and joins the banked
  standings; downstream odds reflect it).
- Plus: ratings computed at `as_of=T` ignore all matches after `T`; identical inputs →
  identical odds (seeded).

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
- **Emit web-friendly JSON** (title odds, per-team advancement odds, group standings with
  live results folded in, eliminated/through flags) **+ the run-over-run deltas**, persisted
  under `reports/` — this is the data contract the Phase-5 dashboard reads (§6 Phase 5).
- **Decisions (D4):** N sims (variance vs runtime), seeding/parallelism, drawing-of-lots
  handling (random, seeded), and FIFA-ranking source for §3.3 tiebreak (committed
  snapshot).
- **Tests (adversarial, the heart of correctness — Phase 4 ships only when all pass):**
  - **The live-state contract §4.1 (a)–(d)** — completed results never re-rolled; simulated
    pre-future standings exactly equal the real current standings; already-decided teams
    show 0%/100%; a new real result shifts correctly from the prior state. **This gates the
    phase.**
  - assert **exactly 32** teams enter the knockout every simulation;
  - assert each group yields exactly top-2 + correct 3rd, with constructed tie scenarios
    that exercise GD→GS→H2H→fair-play→lots in order;
  - assert the **third-place assignment matches FIFA's official table** for sampled and
    worked-example combinations, table-completeness (495), and one-slot-per-team;
  - end-to-end: a fully-completed historical-style bracket reproduces the known winner.

### Phase 5 — Live web dashboard (the final deliverable; build LAST)
**The end-state is a live web dashboard, not a Markdown report.** A **static page on GitHub
Pages**, regenerated by a **scheduled GitHub Action** (e.g. every few hours through the
tournament) that runs the whole pipeline (Phase 1 → 2 → 3 → 4), writes **web-friendly JSON**,
and **commits** it so the page auto-refreshes as results land. **No live server, no paid
hosting** — static files + scheduled rebuild.
- **The page shows:** current **title-win probability** per team; how each **MOVED** since the
  last run (the run-over-run **deltas** — who's rising/falling); **group standings** with live
  results folded in; which teams are **mathematically eliminated / through**; and a clear
  **"last updated" timestamp + which matches are reflected**.
- **Point-in-time on the page too:** it only ever renders the point-in-time-correct state
  (played results fixed, future simulated).
- **Data contract:** Phase 4 emits the odds/advancement/standings + deltas as **JSON** that
  the dashboard reads; run history persisted under `reports/` for the run-over-run deltas.
- **Fail loudly** in the scheduled job: if fetch/reconcile/sim breaks, the job fails and does
  **not** publish a stale/garbage page.
- **Decisions (D5):** schedule cadence, page tech (plain HTML+JS reading JSON vs a small
  static-site generator), JSON schema, and "who moved" highlight thresholds.
- **Build LAST.** Do not let dashboard work distract from getting the simulation correct and
  validated first; this phase starts only after Phase 4 is green.
- **Tests:** delta computation against two canned run snapshots; JSON-schema validation;
  the page renders the canned JSON; scheduled-workflow dry-run.

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

| ID | Decision | Where | Status / leaning |
|----|----------|-------|-----------------|
| **D0** | Approve this phase list + §3 format spec | Phase 0 | ✅ **APPROVED** 2026-06-14 |
| **D1** | WC-2026 data source (verify coverage first; no scraping) | Phase 1 | ✅ **RESOLVED** 2026-06-14 → **openfootball dataset** (`openfootball/worldcup.json`). API-Football free failed the live gate (§11); openfootball verified directly (§14): 12×4 groups, 104 matches, real played scorelines, no cards. |
| **D-cards** | How cards-based tiebreakers behave with no card data (group fair-play; 3rd-place conduct) | Phase 1/4 | ✅ **RESOLVED** 2026-06-14 → **skip to the next defined step (drawing of lots, seeded) + emit a loud warning and record it** (never silent). Triggers only when a tie is otherwise unresolved before the conduct step. |
| **D1-overlay** | Which fresh live-results source overlays openfootball (which lags) | Phase 1 | ✅ **RESOLVED** 2026-06-14 → **ESPN site API** (free, no key, proven fresh — had Australia 2–0 Türkiye; §15). Unofficial-endpoint caveat accepted; config-driven client allows swapping to football-data.org later. |
| **D2** | Elo K / MoV, home-advantage for hosts, form window, squad-strength proxy source (market-blind) | Phase 2 | Elo+MoV, partial home edge, transparent squad-value proxy |
| **D3** | Goal-model: ratings→λ mapping (D3-map), calibration source/method (D3-calib), ET+penalty model (D3-etp), which Phase-2 number drives λ (D3-input) | Phase 3 | §18 drafted: analytic ratings→λ, calibrated on martj42 goals (Poisson reg + DC ρ MLE), committed params; ET scaled-Poisson + logistic penalties; driven by blended rating. **Awaiting sign-off.** |
| **D4** | N sims, seeding/parallelism, lots handling, FIFA-ranking snapshot source | Phase 4 | 50k sims, seeded, lots=seeded-random |
| **D5** | **Live web dashboard:** schedule cadence, page tech (plain HTML+JS vs static-site generator), JSON schema, "who moved" thresholds | Phase 5 | Static GitHub Pages + scheduled Action (every few hours) committing web-friendly JSON; plain HTML+JS reading it; build LAST |

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

## 11. D1 — free-API verification record (2026-06-14)

Verification at the **documentation/source level** (no live key hit yet — that is the first
Phase-1 gate, §12.1). No scraping considered. Findings:

### football-data.org (free tier) — checked first, per the rule
- ✅ Covers the **FIFA World Cup** competition; provides **fixtures, results, standings,
  top scorers**.
- ❌ **No discipline/cards, lineups, or squads on the free tier** — those require paid
  access. **Scores are delayed (not real-time).** Rate limit **10 requests/min**.
- **Verdict: falls short.** Our group **fair-play** tiebreaker (§3.2) and third-place
  **conduct/cards** tiebreaker (§3.3) need disciplinary data, which the free tier does not
  provide. Per D1's rule ("verify ... discipline ... then API-Football if it falls short"),
  we move on. Retained as a **fallback / cross-check** for fixtures/results/standings.

### API-Football (api-football.com / api-sports.io, free plan) — recommended primary
- ✅ Covers **World Cup 2026** (league/season present; confirmed by multiple sources incl. a
  public repo built specifically to pull WC-2026 from this API).
- ✅ Free plan exposes **all endpoints** — fixtures, **events (yellow/red cards)**,
  standings, statistics, lineups — i.e. the **discipline data we need**.
- ⚠️ **Hard cap of 100 requests/day** (resets 00:00 UTC). Acceptable for our cadence: we are
  **not** doing in-play polling — we re-pull on a schedule and after matchdays, fetching the
  fixtures list + standings + events only for **newly-finished** matches. Budget is modeled
  in §12.

### Cross-check / reference sources (not the live pipeline)
- `openfootball/worldcup.json` (public-domain JSON incl. Canada/USA/Mexico 2026) and
  football-data.org standings — usable to **validate** parsed results offline. Not used as
  the live source (static/community-maintained; doesn't meet the live auto-pull requirement,
  and using it as primary would be closer to scraping a dump than a supported live API).

### Decision (doc-level, SUPERSEDED by the empirical result below)
~~Primary = API-Football free tier~~ — overturned by the live smoke-test.

### Empirical result — 2026-06-14 Actions smoke-test — ❌ GATE FAILED for API-Football free
Ran `.github/workflows/smoketest.yml` on GitHub Actions with the real `API_FOOTBALL_KEY`
(plan = **Free**, 100/day, key valid). Findings:
- League discovery **works**: `id=1 | World Cup [Cup] | World | seasons=2010,2014,2018,2022,2026`
  — WC-2026 exists in the catalog as league 1.
- **But the data is paywalled on free:** `/standings?league=1&season=2026` and
  `/fixtures?league=1&season=2026` both returned
  **`{"plan":"Free plans do not have access to this season, try from 2022 to 2024."}`** →
  0 groups, 0 fixtures, 0 results.
- **Conclusion: API-Football's *free* plan does NOT cover WC-2026 match data** (season-gated
  to 2022–2024). Verdict per D1's STOP rule: **do not build on it.** D1 is **re-opened** —
  see §13 for the fallback options put to the owner.

> Sources: TheStatsAPI (football-data.org free-tier limits 2026; World Cup 2026 API roundup),
> api-sports.io football API docs, `github.com/rezarahiminia/worldcup2026`,
> `github.com/openfootball/worldcup.json`. Doc pages returned HTTP 403 to automated fetch;
> findings are corroborated across multiple independent sources and will be **empirically
> confirmed** by the §12.1 live smoke-test.

---

## 12. Phase 1 — Data layer (detailed sub-plan, for sign-off)

**Goal:** a clean, versioned, point-in-time local store of WC-2026 fixtures and results,
sourced from the **openfootball** dataset (D1 resolved — §14), that downstream phases
consume. No ratings/model/sim logic here. Plan-first: this sub-plan is signed off before
code.

### 12.0 Source target (pinned)
- **Source:** `openfootball/worldcup.json` — public-domain dataset on GitHub. No key.
- **Files (raw):** `https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/`
  - `worldcup.json` — the 104 matches (fixtures + results).
  - `worldcup.groups.json` — the 12 groups × 4 teams.
  - `worldcup.teams.json`, `worldcup.squads.json`, `worldcup.stadiums.json` — reference.
- **Reachable from both sandbox and Actions** (verified — `raw.githubusercontent.com`,
  `api.github.com` are allowlisted). Fetch via a thin, **source-config-driven** client
  (base URL + paths from config) so a different mirror/source is a config change.
- **Caveat (accepted by owner):** this is a **commit-updated dataset, not a live API** —
  matchday freshness depends on maintainer commits and may lag. The pipeline must record the
  source commit SHA per snapshot (provenance) and tolerate lag (don't crash on "no new
  results"; just report unchanged).
- **No discipline/cards** in this source (matches carry scorers, not bookings) — see the
  cards-tiebreak decision (D-cards, §3.2/§3.3).

### 12.1 Verification gate — ✅ DONE 2026-06-14 (evidence in §14)
Verified **directly from the sandbox** (no key needed): 12 groups × 4 teams, 104 matches,
played matches carry real `score.ft` scorelines (+ scorers/minutes), future matches have no
score (clean point-in-time split), no cards. A Phase-1 `make verify-source` target
re-asserts these invariants on every fetch and **raises** if any fail (≠12 groups, any
group ≠4, missing the 2026 files, a schema change).

### 12.2 openfootball match schema → internal model
Observed match shape:
```json
{ "round": "Matchday 1", "date": "2026-06-11", "time": "13:00 UTC-6",
  "team1": "Mexico", "team2": "South Africa",
  "score": { "ft": [2,0], "ht": [1,0] },
  "goals1": [{"name":"…","minute":"9"}], "goals2": [],
  "group": "Group A", "ground": "Mexico City" }
```
Normalize to:
- `Team`: stable internal `team_id`, canonical name, group, FIFA-ranking snapshot ref.
- `Match`: `match_id` (derived stable key, e.g. round+teams), `group` or knockout `round`,
  `home_id`/`away_id`, `kickoff_utc` (parsed from `date`+`time`, converting the UTC offset),
  `status` ∈ `{scheduled, final}` (**`final` iff `score.ft` present**), `home_goals`/
  `away_goals` (from `score.ft`), `source`, `source_sha`, `pulled_at`.
- **No cards** → `disciplinary_points` defaults to 0/unknown; the §3.2/§3.3 cards step is
  governed by D-cards (skip to next tiebreaker + loud warning).
- `StandingRow` is **derived**, never stored as truth (computed from `Match`).
- Team names → `team_id` via a committed alias map (e.g. "USA", "South Korea",
  "Bosnia & Herzegovina", "Curaçao", "Ivory Coast", "Türkiye/Turkey"); an unknown name
  **raises** (no silent new team).

### 12.3 Storage & point-in-time snapshots
- Each fetch writes an immutable, timestamped raw snapshot (exact bytes + source commit SHA)
  to `data/raw/` — any historical `as_of` state is reproducible and auditable.
- A normalized current view goes to `data/processed/` (gitignored except pinned runs).
  Loading reconstructs state for a given `as_of` from snapshots (§4).
- Groups + alias map live in `data/reference/` (committed, provenance-stamped). The 2026
  group membership is sourced from `worldcup.groups.json` and committed for offline tests.

### 12.4 Fetch cadence & politeness
- No rate cap to manage (static files). Use conditional GET (ETag / `If-None-Match`) and
  only rewrite a snapshot when the source SHA changes. Schedule cadence is a Phase-5 detail.
- **Fail loudly** on fetch error / malformed JSON / schema drift — never publish on stale or
  partial data.

### 12.5 Secrets
- **None required** (public dataset, no key). The earlier `API_FOOTBALL_KEY` plumbing is not
  needed for the data layer. (Kept in mind only if D1 is ever revisited toward a paid API.)

### 12.6 Fail-loud guards (each raises, with a test)
- Schema/shape drift vs the expected openfootball shape; ≠12 groups; any group ≠4 teams; a
  match referencing a team not in the group set / alias map; a match with a populated
  `score.ft` but `date`/kickoff **after** `as_of` (future-result leak, §4); duplicate
  `match_id`; a previously-`final` result that **changes** on a later fetch (non-monotonic)
  → raise + flag; the 2026 files missing/empty.

### 12.7 Tests (gate Phase 1)
- Golden-file parse: a **committed** frozen copy of `2026/worldcup.json` +
  `worldcup.groups.json` → internal `Match`/`Team` model (no network in tests).
- Point-in-time split: `final` iff `score.ft` present **and** `kickoff_utc ≤ as_of`;
  constructed future-dated-score input **raises** (ties into §4 / §4.1(b)).
- Standings derivation from `Match` set matches a hand-computed group table, exercising the
  §3.2 ordering (GD→GS→H2H→…); with no cards, the fair-play step triggers the D-cards
  degradation and emits the warning (asserted).
- Each guard in §12.6 has a test asserting it raises.
- kickoff parsing: `date`+`time`+offset → correct `kickoff_utc`.

### 12.8 Deliverables
- `src/wcpredictor/data/` (fetch, normalize, store, snapshot-reconstruct); `make fetch` +
  `make verify-source`; committed `data/reference/groups.yaml` (from openfootball) + alias
  map + golden frozen payloads; the §12.7 suite green.

---

## 14. D1 RESOLVED — openfootball dataset (verification evidence, 2026-06-14)

**Owner decision:** use **`openfootball/worldcup.json`** (Option C, §13) as the WC-2026 data
source; handle the cards tiebreaker via **skip-to-next-step + loud warning** (D-cards).

Verified **directly from the sandbox** (no key; `raw.githubusercontent.com` reachable):
- `2026/worldcup.groups.json` → **12 groups (A–L), every group exactly 4 teams.** ✅
- `2026/worldcup.json` → **104 matches** (full tournament schedule). ✅
- **Played matches carry real scorelines:** `score.ft` (+ `ht` and `goals1/goals2` scorers
  with minutes). Example: `Mexico 2–0 South Africa` (2026-06-11, Group A). **7 matches with
  populated scores** in the current data — the already-played results with real scores. ✅
- **Future matches have no `score`** → clean Completed/Pending partition for point-in-time
  (§4): `final` iff `score.ft` present and `kickoff_utc ≤ as_of`. ✅
- **No cards/discipline** in the data (scorers only) → D-cards degradation applies. ✅ (known)
- **Liveness caveat:** commit-updated dataset, not a live API; freshness may lag — accepted.

> Provenance: fetched from `raw.githubusercontent.com/openfootball/worldcup.json/master/2026/`
> on 2026-06-14. Phase 1 commits a frozen golden copy + records the source commit SHA per
> snapshot. This **supersedes** the API-Football pick (§11); §12 is rewritten accordingly.

---

## 15. Live-results overlay (openfootball lags — owner chose structure + overlay)

**Why:** openfootball was already missing a real completed result on day 1
(**Australia 2–0 Turkey**, Group D, 2026-06-13). It's a commit-updated dump, not a live
feed. Owner decision: keep **openfootball for the static structure** (groups, the full
104-match schedule, team list) and layer a **fresh live-results overlay** on top for match
**status + score**.

### 15.1 Overlay candidate smoke-test — Actions run #3, 2026-06-14
| Source | Key? | Result |
|--------|------|--------|
| **ESPN site API** (`site.api.espn.com/.../soccer/fifa.world/scoreboard?dates=YYYYMMDD`) | none | ✅ **FRESH.** Returned June-13 FTs **and `Australia 2–0 Türkiye [FT]`** (the result openfootball lacks) + June-14 scheduled fixtures. **Winner.** |
| TheSportsDB (free key `3`) | free key | ⚠️ Sparse/incomplete — only a partial result or two, **no** Australia–Turkey. Rejected. |
| football-data.org v4 (`/competitions/WC/matches`) | `FOOTBALL_DATA_TOKEN` | ◻️ **Untested** — no token in secrets. The *officially supported* alternative; needs a free token to verify 2026 coverage + freshness. |

### 15.2 Decision — ✅ ESPN site API (owner-confirmed 2026-06-14)
**Overlay = ESPN site API** (free, no key, proven fresh). Accepted caveat: unofficial/
undocumented endpoint (JSON, not HTML scraping; no published redistribution ToS; may change
without notice). Mitigated by a **config-driven client** so a supported source
(e.g. football-data.org) can swap in later without a rewrite.

**Pinned ESPN client config:**
- **Base:** `https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world`
- **Endpoint:** `/scoreboard?dates=YYYYMMDD` (per UTC-ish day). Fetch each day across the
  tournament window (2026-06-11 … 2026-07-19), dedupe, and reconcile by match key (§15.3).
- **No auth.** Polite caching / conditional GET where possible.
- **Fields used:** `events[].competitions[0].competitors[]` → team `displayName` + `score`;
  `status.type.shortDetail`/`.state`/`.completed` → status (FT/scheduled/in-progress);
  event date → `kickoff_utc`. (Cards not needed — D-cards.)
- **No-rewrite swap:** base URL + path + response-mapping live in source config; a
  football-data.org adapter (`/v4/competitions/WC/matches`, header `X-Auth-Token`) can be
  added behind the same interface if a `FOOTBALL_DATA_TOKEN` is later provided.

### 15.3 Overlay architecture (point-in-time preserved)
- **openfootball = canonical structure:** the 12×4 groups, the 104-fixture skeleton (teams,
  round, scheduled kickoff), team list. Committed for offline tests.
- **Overlay = authoritative for status + score** of each fixture. Reconcile to openfootball
  by a **stable match key** = (matchday/round + unordered team-pair), via the team alias map
  — **not** by date (sources bucket kickoffs by different timezones; e.g. ESPN files
  Australia–Türkiye under 06-14, openfootball under 06-13).
- A match is **`final`** iff the **overlay** marks it final (FT) **and** `kickoff_utc ≤ as_of`
  (§4). openfootball's own score is a **fallback** only if the overlay lacks that fixture.
- **Fail loudly:** overlay fixture that can't be matched to an openfootball fixture; both
  sources `final` but **scores disagree**; an overlay `final` with `kickoff_utc > as_of`
  (future leak); team name not in the alias map. Record **which source** supplied each result
  (provenance) in the snapshot.
- **Team-name normalization** spans both sources (e.g. `Türkiye`/`Turkey`, `Curaçao`,
  `Ivory Coast`/`Côte d'Ivoire`, `South Korea`/`Korea Republic`, `USA`).

### 15.4 Impact on §12
§12 (Phase 1) gains a second **source-config-driven** fetcher (the overlay) + the §15.3
reconciliation layer and its guards/tests. Both sources are smoke-tested on Actions (egress
blocks them from the sandbox); openfootball is also fetchable directly. **D1-overlay** (which
overlay source) is the only open item before Phase-1 build.

### 16. Phase 1 — first live two-source fetch (verified 2026-06-14, Actions run #4)
Pipeline run (`--as-of 2026-06-15T00:00:00Z`, ESPN window 06-11…06-15) after `pytest`
(20 passed) and `--verify` (groups=12, sizes=[4], fixtures=104):
```
as_of=2026-06-15T00:00:00+00:00  fixtures=104  final=8  by_source={'espn': 8}
already-played (real scores):
  2026-06-11  Grp A  Mexico 2-0 South Africa
  2026-06-12  Grp A  South Korea 2-1 Czech Republic
  2026-06-12  Grp B  Canada 1-1 Bosnia & Herzegovina
  2026-06-13  Grp D  USA 4-1 Paraguay
  2026-06-13  Grp B  Qatar 1-1 Switzerland
  2026-06-13  Grp C  Brazil 1-1 Morocco
  2026-06-14  Grp C  Haiti 0-1 Scotland
  2026-06-14  Grp D  Australia 2-0 Turkey      <- ESPN overlay; openfootball was missing it
```
All 8 finals came from the ESPN overlay (authoritative when present); no score conflicts
(ESPN agreed with openfootball on the 7 it had), no unmatched results, no future-leak, no
unknown teams. The two-source design works end-to-end on real data.

### 15.5 Reconciliation & point-in-time test contract (GATES Phase 1 — owner-required)
The two-source reconciliation is the new risk surface (a wrong team-pair match silently
attaches the wrong score — same error class as a bad odds-match in the UFC project). These
**offline golden-file tests must be green before any live run is trusted**, and they bias to
**fail-loud over guess** everywhere:
- **(R1) Cross-bucket match:** the (matchday + unordered-team-pair) key matches an ESPN
  fixture to its openfootball fixture **despite the date-bucketing mismatch** (ESPN files
  Australia–Türkiye under 06-14, openfootball under 06-13) — asserted on golden payloads.
- **(R2) Unmatched overlay → raise:** an ESPN result with no corresponding openfootball
  fixture **fails loud** (never silently dropped).
- **(R3) Score conflict → raise:** a fixture where both sources are `final` but the **scores
  disagree** raises.
- **(R4) Future-leak guard (core point-in-time):** `final` iff **ESPN FT _and_
  `kickoff_utc ≤ as_of`**; a `final` with `kickoff_utc > as_of` **must raise**. This is the
  "count only matches that already happened; never leak a future result" gate — it stays
  green as a contract.
- Plus ambiguity guard: if a team-pair maps to >1 base fixture (group + a later knockout),
  disambiguate by nearest kickoff; raise if still ambiguous.

---

## 13. D1 re-opened — fallback options (awaiting owner decision)

The smoke-test (§11) proved API-Football's **free** plan does **not** serve WC-2026 match
data. We need a new source decision before any Phase-1 build. Options:

| # | Option | Free? | Live? | Cards/discipline? | Notes |
|---|--------|-------|-------|-------------------|-------|
| **A** | **football-data.org** free tier | ✅ | delayed (not in-play) | ❌ paid-only | Covers the WC competition (fixtures/results/standings/top-scorers). **Must be smoke-tested** to confirm it isn't *also* season-gated for 2026. No card data on free → the fair-play (group) and conduct (3rd-place) tiebreakers can't be sourced. |
| **B** | **API-Football paid** (lowest tier unlocking current seasons) | ❌ (paid) | ✅ | ✅ (events) | Everything we want incl. cards. Breaks the "free" constraint; needs a budget OK. Client already targets this exact API, so only the plan/key changes. |
| **C** | **openfootball/worldcup.json** (public-domain GitHub dataset, incl. 2026) | ✅ | lags (commit-driven) | likely ❌ | No key. Not a live API — a community-maintained JSON dump; timeliness during matchdays is not guaranteed; closer to consuming a dataset than a supported live feed. |
| **D** | Another free API (TheStatsAPI, Highlightly, …) | ? | ? | ? | Each needs its own Actions smoke-test to confirm real WC-2026 free coverage before we commit. |

**Cross-cutting cards problem:** the only confirmed way to get real per-match cards is a
**paid** tier (Option B). All free options likely lack discipline data. If we stay free, we
need a rule for the rare cases the cards tiebreaker would decide (groups: after GD/GS/H2H;
3rd-place: after pts/GD/GS). Proposed market-blind handling: when a tie is unresolved
*before* the fair-play step, **skip conduct and go to the defined next step (drawing of lots,
seeded)** — and **emit a loud warning / record it** so it is never silent (consistent with
"fail loudly"). This keeps us free and correct ~always, with a documented, rarely-triggered,
auditable degradation. (Revisit if Option B is chosen.)

**Recommendation:** ~~A (football-data.org free)~~. **OWNER CHOSE → C (openfootball dataset)**
with the cards-tiebreaker degradation (D-cards). Verified directly — see **§14**. D1 is now
**resolved**; §12 is rewritten for openfootball.

---

## 17. Phase 2 — Team strength ratings (detailed sub-plan, for sign-off)

**Goal:** one **transparent, inspectable per-team rating** at any `as_of`, blending an
**Elo base**, **recent form**, and a **squad-strength proxy**, learning **only** from matches
that have actually been played (point-in-time), and **blending a pre-tournament prior with
the limited 2026 results so far** so we don't overreact to one or two games. No goal model or
simulation here (those are Phases 3–4). Plan-first: signed off before any code.

### 17.1 Inputs — point-in-time, played-only (CRITICAL, plan.md §4)
- Consumes the **Phase-1 resolved `Match` list at `as_of`**. Ratings use **only**
  `status == FINAL` matches (ESPN FT **and** `kickoff_utc ≤ as_of`). **Pending, placeholder,
  and (by construction) simulated fixtures are never fed in.** The ratings layer sits
  *upstream* of the simulator, so a simulated scoreline can never reach it.
- **Defense in depth:** the ratings builder itself re-asserts the guard — it ignores any
  non-FINAL match and **raises** on a FINAL with `kickoff_utc > as_of` (a future leak should
  never reach it; if it does, fail loud). Matches are folded in **kickoff order**.
- Pre-tournament **prior** input: a committed snapshot (see D2-prior) — does not change with
  `as_of`.

### 17.2 The three components (each transparent, dumpable)
1. **Elo base** `R_elo`: standard Elo, **started from the pre-tournament prior** (17.3) and
   updated match-by-match over played WC matches. Tunables: **K-factor**, a **margin-of-
   victory** multiplier (bigger wins move more, with diminishing returns), and a
   **home/neutral** adjustment — 2026 hosts **USA/Canada/Mexico** get a *partial* home edge,
   everyone else neutral.
2. **Recent form** `R_form`: performance over the last *W* matches **vs expectation** (e.g.
   points- or goal-difference-above-expected given the opponent), normalized. Captures
   momentum the slow Elo misses. Tunable: **form window `W`** and decay.
3. **Squad-strength proxy** `R_squad`: a **transparent, market-blind** per-team strength
   signal (see D2-squad) — **never** odds-derived. Defaults to the prior if no proxy source is
   adopted, so the blend degrades gracefully.

### 17.3 Prior ↔ live blend — don't overreact early (shrinkage)
Only a few group games are played, so the live Elo is blended with the prior via a weight
that **shifts toward live results as more matches accumulate** (a shrinkage / pseudo-count):

```
n        = number of played matches for the team (at as_of)
w_live   = n / (n + k_shrink)            # 0 when n=0, ->1 as n grows
R_elo*   = w_live * R_elo_live + (1 - w_live) * R_prior
```

- `k_shrink` is a **documented tunable** (≈ the number of "phantom" prior matches; default
  e.g. 5). At 1–2 games the **prior dominates**; by the late group stage + knockouts the
  **live results dominate**. Explicit, inspectable, and reproducible.

### 17.4 The blend → one rating (explicit, tunable weights)
On a common scale (z-scored across the 48 teams, or Elo points):

```
R_team = w_elo * Z(R_elo*) + w_form * Z(R_form) + w_squad * Z(R_squad)
```

- `(w_elo, w_form, w_squad)` are a **documented tunable** in `configs/ratings.json`
  (default proposal **0.60 / 0.20 / 0.20**), pinned per run for reproducibility. The plan is
  explicit that these are knobs, not magic constants.

### 17.5 Transparency / inspectability (plan.md §10)
- `explain(team)` dumps: `prior`, `R_elo_live`, `n`, `w_live`, `R_elo*`, `R_form`, `R_squad`,
  the three weighted contributions, and the final `R_team` — so **"why is Brazil rated X?"**
  is answerable and auditable. JSON-dumpable (also feeds the eventual dashboard).

### 17.6 Config & reproducibility
- `configs/ratings.json`: `K`, `mov`, `home_edge`, `form_window`, blend weights, `k_shrink`,
  prior source. A run is pinned by `(as_of, results_snapshot, ratings_config)`.

### 17.7 Decisions — RESOLVED 2026-06-14
- **D2-prior → computed pre-tournament Elo** from **`martj42/international_results`** (public-
  domain CSV on GitHub; 49,478 matches with scores **and a neutral-venue flag**; current
  through 2026; reachable from the sandbox — a dataset fetch like openfootball, **not**
  scraping). Chosen over FIFA ranking because it's a better predictor *and* cheap to source.
  Computed once over all internationals **before WC kickoff** (date `< 2026-06-11`) and
  **committed** as `data/reference/elo_prior_2026.json` (with provenance + params) for
  reproducibility and offline tests. Only **2 of 48** names differ from openfootball's
  (`USA`↔"United States", `Bosnia & Herzegovina`↔"Bosnia and Herzegovina") — both already in
  the alias map.
- **D2-squad → optional, defaults into the prior** for now; flagged a later enhancement.
- **D2-hist-data → deferred** (the martj42 prior supersedes the need).
- **D2-params → documented defaults accepted as tunables.** **Host home-edge applies to ALL
  THREE hosts** — `hosts = {USA, Canada, Mexico}` in config, never hardcoded to one (asserted
  by a test).

### 17.8 Tests (gate Phase 2)
- **Point-in-time (the critical one):** a rating computed at `as_of=T` uses **only** matches
  with `kickoff_utc ≤ T`; injecting a later FINAL does **not** change the `as_of=T` rating;
  feeding a future-dated FINAL **raises**; identical inputs → identical ratings (determinism).
- **Shrinkage:** with `n=0` the rating **equals the prior**; `w_live` is monotonic increasing
  in `n`; a single upset barely moves a team with a strong prior (no overreaction).
- **Elo behavior:** beating a stronger team raises the rating more than beating a weaker one;
  the host home-edge is applied to USA/Canada/Mexico and not to neutral games.
- **Blend:** weights are honored; z-scoring is correct; `explain()` round-trips and its
  contributions reconstruct `R_team`.

### 17.9 Deliverables
- `src/wcpredictor/ratings/` (prior, elo, form, squad, blend, explain); `make rate`;
  `configs/ratings.json`; committed prior snapshot (`data/reference/`); the §17.8 suite green.

---

## 18. Phase 3 — Match (goal) model (detailed sub-plan, for sign-off)

**Goal:** a **Dixon-Coles / Poisson scoreline model** driven by the Phase-2 ratings that,
for any two teams at an `as_of`, produces a full **scoreline probability matrix** `P(i,j)`.
Scorelines (not just W/D/L) are required for the group **GD/GS tiebreakers** and for knockout
**extra-time/penalty** resolution. The matrix is what the Phase-4 simulator samples per match.
Plan-first: signed off before any code. **Market-blind** — calibrated only on historical
goals, never odds.

### 18.1 Inputs
- Phase-2 **ratings at `as_of`** (the Elo-scaled blended rating, or `elo*`; pinned by D3-map).
  Point-in-time is inherited from Phase 2 (ratings use only played matches).
- A **committed snapshot of fitted global params** (D3-calib) so runs are reproducible and
  tests are offline.

### 18.2 The model
- **Expected goals from ratings.** For home `H`, away `A`:
  `log λ_H = μ + β·(R_H − R_A)/S + γ_home·home(H)` and
  `log λ_A = μ + β·(R_A − R_H)/S + γ_home·home(A)`, where `μ` = baseline log-goals,
  `β` = rating sensitivity, `S` = rating scale, `γ_home` = home-advantage in goal terms
  (applied per §17 host rule on host ground; 0 at neutral). Transparent, few params.
- **Independent Poisson with the Dixon-Coles low-score correction** `τ(i,j; ρ)` that adjusts
  the dependence in the 0-0 / 1-0 / 0-1 / 1-1 cells (`ρ` fitted). Scoreline matrix over
  `i,j ∈ 0..G_max` (truncated, then **renormalized to sum to 1**).
- **Derived:** `P(win/draw/loss)`, `E[goals]`, and the full matrix for tiebreakers.

### 18.3 Extra time + penalties (knockouts)
- If level after 90′: **extra time** as a scaled-down Poisson (`λ·et_frac` over 30′), then a
  **penalty shootout** modeled as ~**0.5 at parity**, skewed by rating gap
  (a gentle logistic in `R_H − R_A`). Resolves every knockout to a winner. (D3-etp.)

### 18.4 Calibration (market-blind, committed)
- Fit `μ, β, γ_home, ρ` on **historical internationals** from `martj42/international_results`
  (it has goals + a neutral flag), using each match's **pre-match Elo** (the Phase-2 Elo
  engine) as the rating input — Poisson regression for `μ/β/γ_home`, then a Dixon-Coles MLE
  for `ρ`. **Commit the fitted params** as `data/reference/goal_model_2026.json` (provenance +
  data cutoff). `make calibrate` rebuilds it. No betting data anywhere.

### 18.5 Config & reproducibility
- `configs/goal_model.json`: `S` (rating scale), `g_max` (truncation), `et_frac`, penalty
  params, and a pointer to the fitted-params snapshot. A scoreline distribution is pinned by
  `(as_of ratings, fitted params, config)`.

### 18.6 Open decisions (need sign-off before code)
- **D3-map:** ratings→λ mapping — **analytic, globally-calibrated** (the §18.2 form; *lean*,
  reuses the rating, few transparent params) vs a full per-team Dixon-Coles attack/defense fit
  (more params, needs enough per-team goals). *Lean: analytic.*
- **D3-calib:** confirm martj42 as the calibration source and the fit method (Poisson
  regression + DC `ρ` MLE); commit the params snapshot.
- **D3-etp:** extra-time scaling `et_frac` and the penalty-shootout model (logistic-in-rating,
  0.5 at parity).
- **D3-input:** which Phase-2 number drives λ — the blended `rating` (Elo-scaled) or `elo*`.
  *Lean: the blended `rating`.*

### 18.7 Tests (gate Phase 3)
- **Proper distribution:** every scoreline matrix is non-negative and sums to 1 (within tol)
  after DC correction + truncation.
- **Monotonicity / symmetry:** stronger team has higher `λ` and higher `P(win)`; equal ratings
  on neutral ground give `λ_H == λ_A` and `P(win)==P(loss)`; home edge raises home `λ`.
- **Dixon-Coles effect:** non-zero `ρ` shifts the 0-0/1-0/0-1/1-1 cells in the expected
  direction while the matrix still sums to 1.
- **ET/penalties:** shootout ≈ 0.5 at parity and skews with the gap; a drawn 90′ always
  resolves to a winner.
- **Reproducibility / point-in-time:** fixed params + `as_of` ratings → identical matrices;
  no future leak (inherited from Phase 2).

### 18.8 Deliverables
- `src/wcpredictor/model/` (dixon_coles, calibrate, etp); `make model` + `make calibrate`;
  `configs/goal_model.json`; committed `data/reference/goal_model_2026.json`; the §18.7 suite
  green. No simulation here (that's Phase 4).

---

_Status: **D0 approved; D1/D-cards/D1-overlay/D2 resolved; Phases 1–2 merged & verified.**
**Phase 3 goal-model sub-plan (§18) drafted — awaiting sign-off** (decisions D3-map / D3-calib
/ D3-etp / D3-input). Dashboard scope acknowledged (§1, §6 Phase 5) — built LAST. **No Phase-3
engine code until §18 is signed off.**_
