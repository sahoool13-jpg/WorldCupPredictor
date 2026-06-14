# WorldCupPredictor — Build Plan

**Status:** D0 + D1 approved. Phase 1 sub-plan drafted (§12), awaiting sign-off. _No engine
code yet._
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

| ID | Decision | Where | Status / leaning |
|----|----------|-------|-----------------|
| **D0** | Approve this phase list + §3 format spec | Phase 0 | ✅ **APPROVED** 2026-06-14 |
| **D1** | Which free API (verify WC-2026 free-tier coverage first; no scraping) | Phase 1 | ✅ **APPROVED** 2026-06-14. Doc-level verification → **API-Football primary** (football-data.org free omits discipline/cards; see §11), football-data.org fallback; **live smoke-test is the first Phase-1 gate; STOP & escalate if neither returns the tournament** |
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

### Decision
**Primary = API-Football free tier** (it covers the tournament *and* discipline);
**fallback = football-data.org** (fixtures/results/standings if API-Football is unavailable
or over budget). **Gate:** Phase 1's first task is a live smoke-test with a real free key —
if it does not return WC-2026 fixtures + standings + card events, **STOP and bring options
to the owner** before building anything else (§12.1).

> Sources: TheStatsAPI (football-data.org free-tier limits 2026; World Cup 2026 API roundup),
> api-sports.io football API docs, `github.com/rezarahiminia/worldcup2026`,
> `github.com/openfootball/worldcup.json`. Doc pages returned HTTP 403 to automated fetch;
> findings are corroborated across multiple independent sources and will be **empirically
> confirmed** by the §12.1 live smoke-test.

---

## 12. Phase 1 — Data layer (detailed sub-plan, for sign-off)

**Goal:** a clean, versioned, point-in-time local store of WC-2026 fixtures, results,
standings, and discipline, pulled from API-Football, that downstream phases consume. No
ratings/model/sim logic here. Plan-first: this sub-plan is signed off before code.

### 12.1 Live verification gate (do this FIRST, fail loudly)
- With a free API-Football key (via env var; see 12.5), hit the WC-2026 league/season and
  confirm the response actually contains: the **12 groups × 4 teams**, the **fixtures**
  (with `kickoff_utc` + `status`), **standings**, and **card events** for a finished match.
- A tiny `make verify-source` (Phase 1) target prints what was found and **raises** if any
  required field is absent. **If WC-2026 isn't fully covered, STOP and escalate** (try
  football-data.org for the non-discipline parts and report the gap) — do **not** proceed to
  build the store on an unverified source.

### 12.2 Data model (normalized, internal)
- `Team`: stable internal `team_id`, canonical name, group, FIFA-ranking snapshot ref.
- `Match`: `match_id`, `group` (or knockout round), `home_id`, `away_id`, `kickoff_utc`,
  `status` (`scheduled|live|final`), `home_goals`, `away_goals`, `home_cards`/`away_cards`
  (yellow/red → disciplinary points), `source`, `pulled_at`.
- `StandingRow` is **derived**, never stored as source-of-truth (computed from `Match`).
- Team-name variants normalized to `team_id` via a committed alias map; an unknown team
  **raises** (no silent new team).

### 12.3 Storage & point-in-time snapshots
- Each pull writes an immutable, timestamped raw snapshot to `data/raw/` (the exact API
  payload) — so any historical `as_of` state is reproducible and auditable.
- A normalized, current view is written to `data/processed/` (gitignored except pinned
  runs). Loading reconstructs state for a given `as_of` from snapshots (§4).
- Group membership (A–L) and the alias map live in `data/reference/` (committed,
  provenance-stamped).

### 12.4 Fetch cadence & request budget (respect the 100/day cap)
- One scheduled pull = ~1 (fixtures) + ~1 (standings) + N (events for *newly-finished*
  matches only) calls. Even on a 6-match day this is well under 100. Cache aggressively;
  never re-fetch events for a match already final and stored.
- Back off and **fail the run loudly** (don't publish stale data) on HTTP 429 / quota
  exhaustion, rather than silently serving old numbers.

### 12.5 Secrets
- `API_FOOTBALL_KEY` via **GitHub Actions secret** → env var at runtime (mirrors the Kaggle
  setup). Local dev via gitignored `.env`. Never committed. Code reads from env and
  **raises** with a clear message if the key is missing.

### 12.6 Fail-loud guards (each raises, with a test)
- Schema/shape drift vs the expected payload; a group with ≠ 4 teams; a fixture missing a
  known team or a kickoff time; duplicate `match_id`; a `final` match missing scores; a
  result that *changes* after being recorded as final (non-monotonic) → raise + flag;
  unknown team name not in the alias map.

### 12.7 Tests (gate Phase 1)
- Golden-payload parse: a frozen sample API response → internal `Match`/`Team` model.
- Standings derivation from `Match` set matches a known fixture (incl. cards →
  disciplinary points), exercising the §3.2 ordering on a constructed group.
- Each guard in 12.6 has a test asserting it raises.
- Snapshot reconstruction: state at `as_of=T` uses only matches with `kickoff_utc ≤ T` and
  `status==final` (ties into §4 / §4.1(b)).
- No network in tests — everything runs off committed golden files.

### 12.8 Deliverables
- `src/wcpredictor/data/` (fetch, normalize, store, snapshot-reconstruct); `make fetch` +
  `make verify-source`; committed `data/reference/groups.yaml` + alias map + golden test
  payloads; the test suite above green.

---

_Status: **D0 approved**, **D1 approved** (API-Football primary, live smoke-test gate).
Phase 1 sub-plan above (§12) is drafted and **awaiting sign-off** — no Phase-1 engine code
until then._
