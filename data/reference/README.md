# data/reference — committed static truth

These files are **committed** so the format/bracket logic is testable **offline**, with no
API access. Each must record its **source URL + retrieval date + provenance**.

Planned contents (added in their phase — none yet in Phase 0):

| File | Phase | What |
|------|-------|------|
| `groups.yaml` | 1 | Groups A–L → the four teams in each, with stable internal team ids |
| `fifa_ranking_<date>.csv` | 4 | FIFA-ranking snapshot — third-place tiebreak (plan.md §3.3) + provenance |
| `r32_assignment.<fmt>` | 4 | **FIFA's official 495-combination** third-place→R32 table, verbatim |
| `bracket_skeleton.<fmt>` | 4 | Fixed R32 pairings + which 8 winner-slots receive a third-placed team |

## Rules for this directory

- **Verbatim, not approximated.** The R32 assignment table is FIFA's official table — all
  **C(12,8) = 495** combinations present. The loader asserts completeness and raises on any
  missing/duplicate combination (plan.md §3.4).
- **Provenance required.** Every file carries source URL + retrieval date (header comment or
  a sibling `.source` note). Authoritative source = FIFA official competition regulations;
  public reproductions (ESPN/Wikipedia) used only for cross-checking.
- **Market-blind.** Nothing here is derived from betting odds.
