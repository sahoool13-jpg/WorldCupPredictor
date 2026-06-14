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

## Current status

**Phase 0 — scaffolding + plan only. No engine code yet.** Awaiting owner sign-off on the
phase list and the format spec (decision **D0** in `plan.md` §9) before starting Phase 1.
