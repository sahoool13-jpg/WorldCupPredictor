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
- **Phase 3 (Dixon-Coles goal model) sub-plan** (`plan.md` §18) is **drafted, awaiting
  sign-off** (D3-map / D3-calib / D3-etp / D3-input). Produces a scoreline probability matrix
  per fixture (needed for GD/GS tiebreakers + ET/penalties), driven by Phase-2 ratings,
  calibrated **market-blind** on martj42 goals. **No Phase-3 engine code until §18 signed off.**
