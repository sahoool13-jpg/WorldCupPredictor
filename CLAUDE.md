# CLAUDE.md — working agreement for this repo

This file tells Claude Code how to work in **WorldCupPredictor**. Read it before doing
anything. The canonical project plan is [`plan.md`](./plan.md) — it is the source of truth
for scope, phases, and the 2026 format spec.

## What this project is

A **live, market-blind Monte Carlo** of the 2026 FIFA World Cup title race. Title odds come
from *our own* team ratings + goal model. It auto-refreshes as real group results land and
reports each team's title probability **and the delta** vs the previous run.

## The rules (do not break these)

1. **Plan-first, per phase.** Do not write engine code for a phase until that phase's
   sub-plan is written in `plan.md` and the owner has signed off. No scope creep.
2. **Market-blind.** Never pull, fit to, calibrate against, or "sanity-check" against
   betting/bookmaker odds. They are out of scope everywhere in the pipeline.
3. **Point-in-time correctness.** Only matches that have **actually happened**
   (`status == final` and `kickoff <= as_of`) count as real. Ratings learn **only** from
   completed matches. A simulated or future result must **never** leak into a rating or be
   recorded as a fact. This is the easiest thing to get subtly wrong — guard it and test
   it (`tests/test_point_in_time.py`).
4. **Completed results are fixed.** Never re-simulate a match that has a real final result.
5. **Fail loudly.** Missing/!=4-team groups, schema drift, a `final` match with no score, a
   future-dated `final`, an unbreakable tie, an incomplete R32 table — **raise**. No silent
   defaults or stale-data fallbacks.
6. **Tests gate the build.** A phase isn't done until `make test` is green. The
   format/bracket and point-in-time suites are contracts — keep them adversarial.
7. **Get the 2026 format exactly right.** 48 teams / 12 groups / top-2 + 8 best thirds = 32.
   Tiebreakers in the exact order in `plan.md` §3. The R32 third-place assignment is the
   **official FIFA 495-combination table**, transcribed verbatim — never approximated.
8. **Walk decisions past the owner.** Anything in `plan.md` §9 (Open Decisions), or any new
   fork you hit, gets a question (use the question tool) before you build it. Don't guess on
   architecture, API choice, or model parameters.
9. **No scraping.** Data comes from a chosen free API with verified WC-2026 free-tier
   coverage (Phase 1, decision D1). Secrets via GitHub Actions secret → env var only.
10. **Reproducible & transparent.** Pin runs by `(as_of, snapshot, configs, n_sims, seed)`.
    Ratings and probabilities must be dumpable and explainable ("why is Brazil 14%?").

## Workflow conventions

- **Branch:** develop on the feature branch you were assigned; never push elsewhere without
  explicit permission. Commit with clear messages. Open a **draft** PR after pushing.
- **Entrypoints:** use the `Makefile` (`make help`). Don't invent ad-hoc scripts when a
  target exists.
- **Stack (assumed; flag if changing):** Python + `pytest`, `numpy`/`pandas`, `requests`.
- **Where things live:** see `plan.md` §5. Static truth (groups, the 495-row R32 table,
  FIFA-ranking snapshot) is **committed** under `data/reference/` so the bracket logic is
  testable offline.

## The live model property (core — gate Phase 4 on it)

Already-played matches are **fixed, real inputs**: their actual scores/cards lock the
current standings and are **never re-simulated**. Each Monte Carlo iteration seeds the group
tables from the **true current state** (real points/GD/GS/cards banked) and simulates **only
the remaining unplayed fixtures**. Tested explicitly (`plan.md` §4.1): (a) completed results
never re-rolled, (b) simulated pre-future standings exactly equal real current standings,
(c) already-decided teams show 0%/100%, (d) a new real result shifts odds correctly from the
prior state.

## Known model opinions (not bugs)

- **Colombia rates high (~5th)** in the Elo prior — this reflects their strong 2024–25 record
  (incl. the Copa América final) in the historical results, a legitimate **Elo-vs-FIFA-ranking
  divergence**, not an error. The prior is computed Elo, not FIFA consensus.
- **Near-tied priors are real, not a fallback.** Each team's prior is independently computed
  from its own match history (the 1500 seed only applies to teams with *zero* history; all 48
  have hundreds–thousands of matches). e.g. Germany 1951.23 (1031 matches) vs Netherlands
  1951.20 (879 matches) genuinely land ~0.035 apart; the 1-decimal display can make distinct
  values look identical (England 1985.06 ≠ Portugal 1984.50).

## Known calibration choice — goal-model rating scale (Phase 3)

The goal model's λ is driven by the Phase-2 **blended** rating (D3-input), but β was calibrated
on historical **Elo** gaps (no blended-rating history exists). The z-blend with a fixed 0.2
form weight means that at **cold start** (all teams 0 games, form variance = 0) the rating
spread is ~**0.8× the prior** — slightly under-weighting favorites early. **This is tied to
games-played `n` and de-compresses as teams play** (NOT a permanent 0.8×): `w_live = n/(n+
k_shrink)` climbs 0→1 so `elo*` tracks the wider-spread live Elo, and form gains real variance.
Empirically the gap/prior-gap ratio goes **0.80 at n=0 → ~1.16–1.34 after 3 games** (can
overshoot for in-form teams), so it's effectively gone by the knockouts. Accepted as honest
early-tournament humility; a clean fix (drive λ off `elo*`, or a scale correction) exists if we
later want favorites weighted harder.

## Current status

- **D0 approved** — phase list + 2026 format spec.
- **D1 RESOLVED → openfootball dataset** (`openfootball/worldcup.json`). API-Football free
  failed the live coverage gate (season-gated; `plan.md` §11). openfootball verified directly
  from the sandbox (`plan.md` §14): 12 groups × 4, 104 matches, real played scorelines, no
  cards. It's a commit-updated dataset (not a live API) — tolerate lag, record source SHA.
- **D-cards RESOLVED** — no card data in the source, so the fair-play (group) and conduct
  (3rd-place) tiebreak steps **skip to the next step (seeded lots) and emit a loud, recorded
  warning** (never silent).
- **Live-results overlay = ESPN site API** (resolved) — openfootball lags (missed Australia
  2–0 Turkey on day 1), so it's used for **static structure** + the **ESPN overlay** for
  status/score (`plan.md` §15; base `site.api.espn.com/.../soccer/fifa.world/scoreboard`, no
  key, config-driven so a supported source can swap in later). Reconcile overlay↔openfootball
  by (matchday + team-pair), **not** date; fail loudly on score conflicts / unmatched
  fixtures / future-dated finals.
- **Phase 1 data layer = BUILT, VERIFIED & MERGED** (`plan.md` §12/§15/§16). Two-source
  pipeline (openfootball structure + ESPN overlay), 20 offline tests green (R1–R4 + point-in-
  time), live Actions fetch loaded 12×4/104 + 8 played-with-real-scores incl. Australia 2–0
  Turkey. Stdlib-only.
- **Final deliverable = a live web dashboard** (not a Markdown report): static **GitHub Pages**
  page rebuilt by a **scheduled Action** that reruns the pipeline and commits web-friendly
  JSON (title odds, run-over-run deltas, standings, eliminated/through, "last updated"). No
  server. `plan.md` §6 Phase 5 — **built LAST**, after the model is correct & validated; don't
  let dashboard work distract from simulation correctness. Phase 4 must emit that JSON + deltas.
- **Phase 2 ratings = BUILT, VERIFIED & MERGED** (`plan.md` §17). Elo prior (martj42) +
  in-tournament Elo + form + squad proxy, shrinkage-blended; 62 tests green; live top ratings
  sane vs FIFA June-2026 (top-3 exact). Ratings learn **only** from played matches (point-in-
  time, no future leak); weights/k_shrink are documented tunables in `configs/ratings.json`.
- **Phase 3 goal model = BUILT, VERIFIED & MERGED** (`plan.md` §18). Dixon-Coles scoreline
  matrices driven by the blended rating; market-blind calibration on martj42 goals; 76 tests
  green; sample scorelines football-sane (Argentina–Jordan, Norway–Senegal).
- **Phase 4 tournament Monte Carlo = BUILT** (`plan.md` §19; D4 approved: N=50k, seeded RNG,
  lots=seeded-random). Loads the **verified FIFA Annex C** 495-row table from `annex_c_r32.json`
  (root; owner-supplied, machine-validated — `validate_annex_c.py` runs in the test suite),
  **never derived/refetched**; fails loud if a simulated combo misses the table. Group sim seeds
  from the true current state; ranking (§3.3) and Annex-C assignment (§19.1) are separate steps;
  bracket wiring comes from openfootball's `Wnn` refs. Live-state contract (a)–(d) tested. Title
  odds football-sane (Argentina/Spain co-favorites).
- **Host edge (calibration fix).** Hosts (USA/Canada/Mexico) get a **dedicated, modest,
  round-tapered** goal boost (`host_log_boost`≈×1.105, `host_taper` group→…→0 by SF/Final) in
  `configs/goal_model.json` — NOT the generic calibrated `gamma_home` (×1.31). The earlier
  full-strength-every-match application over-counted the host edge, compounded across ~10 games
  and **inverted the ratings** (Mexico > higher-Elo England). After the fix: England/Portugal/
  Germany sit above the hosts; Mexico 2.9% / USA 1.5% / Canada 0.2%. Documented tunable; set to a
  defensible football value, **not** fit to the market (market used only as a sanity band).
- **3rd-place FIFA-ranking tiebreaker (§3.3 step 5) reuses the martj42 Elo ordering** as the
  proxy (already committed, market-blind) — a minor approximation on the rarely-decisive 5th
  tiebreaker; avoids adding another data source.
- **Phase 4 = BUILT, VERIFIED & MERGED** (host-edge fix included). Live 50k title odds sane:
  Argentina 17% / Spain 15% co-favorites; England/Portugal/Germany above the hosts; Mexico 2.9
  / USA 1.5 / Canada 0.2. 72 tests green incl. the live-state contract.
- **Phase 5 live web dashboard = BUILT** (`plan.md` §20). Static `docs/` page (`index.html`/
  `app.js`/`style.css`) on **GitHub Pages** + scheduled the scheduled publish workflow (`.github/workflows/smoketest.yml`)
  (cron 3h + manual) that reruns the live pipeline and commits `docs/data/latest.json` (title
  odds + run-over-run deltas + standings + through/eliminated + "last updated" + matches
  reflected). Three guarantees: **fixed committed seed** (2026) so unchanged inputs give
  byte-identical odds and exactly-0 deltas; **fail-loud keeps last-good** (`publish` writes
  only on success — a fetch failure never overwrites with partial data); **cache-busted fetch**
  (`latest.json?t=<now>`, `no-store`) to beat the Pages CDN. 77 tests green. **Project
  complete** pending merge + the owner enabling Pages (serve from `docs/`).
- **CI on PRs = BUILT** (`.github/workflows/ci.yml`, `plan.md` §23). Runs the suite on every PR
  + push to `main`/`claude/**`, separate from the scheduled publisher; dashboard auto-commits
  carry `[skip ci]`. (Registers as a PR check once on `main` — new workflow files don't fire
  from a feature branch in this environment, same quirk as the old `dashboard.yml`.)
- **Phase 6 knockout-stage readiness = BUILT** (`plan.md` §21; D6 resolved: ratings frozen
  post-group, strict slot-binding, JSON-bracket-now/visual-next). Real R32→Final results are
  ingested from the **ESPN overlay** (`pipeline.split_overlay` routes non-group-pair FINALs to
  `data/knockout.extract_knockouts`; point-in-time, trusts ESPN's `winner` flag with a
  decisive-score fallback, loud on a level tie with no flag). They're **pinned** as fixed
  advancers in `bracket.simulate(..., pinned=…)` and validated **strictly** at `Sim` build (pins
  require a complete group stage; every pin must bind to a real slot or `DataError`). Completed
  KO ties are never re-simulated; the live-state contract is extended to the bracket (a)/(c)/(d).
  **Ratings stay frozen post-group for free** — `compute_ratings` keys on `m.group`, so the KO
  stream never feeds Elo. Payload gains `meta.n_ko_played`, an additive `bracket` block, and KO
  finals in `recent_results` (so they show in the ticker; **visual bracket deferred per D6c**).
  93 tests green. **Live ESPN KO field shape still to be confirmed on Actions when R32 starts**
  (egress wall) — the parser fails loud if a field differs. Same-group KO rematch is a recorded
  edge (skipped; impossible at R32 by Annex C no-rematch).
- **Phase 7 "Why this %?" explainability = BUILT** (`plan.md` §22; D7: all 48, λ-only). `build_sim`
  keeps the full `RatingDetail` (was discarded) and passes it to `Sim`; `payload._why_map` emits
  an additive per-team `why` block — rating breakdown (prior/elo*live/form/squad/`w_live`/n) +
  attack/defence λ vs an **average** side at neutral + a `host_edge` flag. **Read-only/descriptive:
  it never feeds the odds — a payload with `why` has byte-identical title/delta to one without**
  (tested), preserving the fixed-seed clean-delta property. `make explain TEAM=Brazil` prints the
  same breakdown (reuses `_why_map`). Dashboard shows it in the existing tap-to-expand row (assets
  `?v=3`); omitted gracefully when absent. 98 tests green.
