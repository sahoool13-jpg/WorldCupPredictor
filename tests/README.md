# tests

`pytest`. **Tests gate the build** — a phase ships only when `make test` is green, and CI
must pass to merge. Empty in Phase 0; suites are added per phase.

The format/bracket and point-in-time suites are **contracts**, written adversarially
(`plan.md` §4, §7):

- `test_format_bracket.py` (Phase 4) — assert **exactly 32 advance**; group tiebreakers
  applied in the exact order GD→GS→H2H→fair-play→lots with constructed tie scenarios;
  third-place ranking (points→GD→GS→conduct→FIFA-rank); the **495-row** R32 assignment
  table complete + sampled correctness + a known worked example + one-slot-per-team.
- `test_point_in_time.py` (Phase 2+) — no future/simulated result leaks into ratings or
  becomes a fact; completed results are byte-identical across runs and never resampled;
  ratings at `as_of=T` ignore everything after `T`.
- `test_data.py` (Phase 1) — fixtures parsing from golden payloads; fail-loud guards
  (schema drift, group ≠ 4 teams, `final` without score, future-dated `final`).
- Determinism — identical inputs → identical title odds (pinned seed).
