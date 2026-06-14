# WorldCupPredictor — entrypoints
# Phase 0: scaffolding only. Engine targets are placeholders that fail loudly until
# their phase ships (see plan.md). They intentionally exit non-zero so nothing silently
# "succeeds" before it exists.

.DEFAULT_GOAL := help
PY ?= python3

# ---- meta -------------------------------------------------------------------
.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

# ---- environment ------------------------------------------------------------
.PHONY: setup
setup: ## Install dependencies (Phase 1+: pip install -r requirements.txt)
	@if [ -f requirements.txt ]; then \
		$(PY) -m pip install -r requirements.txt; \
	else \
		echo "[setup] no requirements.txt yet (Phase 0). Nothing to install."; \
	fi

# ---- quality gates ----------------------------------------------------------
.PHONY: lint
lint: ## Lint (ruff if available, else skip cleanly)
	@if command -v ruff >/dev/null 2>&1; then \
		ruff check . ; \
	else \
		echo "[lint] ruff not installed; skipping (no engine code in Phase 0)."; \
	fi

.PHONY: test
test: ## Run the test suite (tests gate the build — see plan.md §7)
	@if command -v pytest >/dev/null 2>&1; then \
		pytest -q ; \
	else \
		$(PY) -m pytest -q ; \
	fi

# ---- pipeline ---------------------------------------------------------------
.PHONY: verify-source
verify-source: ## (Phase 1) Verify openfootball structure invariants (12x4, 104 fixtures)
	@PYTHONPATH=src $(PY) -m wcpredictor.data.pipeline --verify

.PHONY: fetch
fetch: ## (Phase 1) Fetch openfootball + ESPN overlay, reconcile at now, print summary
	@PYTHONPATH=src $(PY) -m wcpredictor.data.pipeline $(ARGS)

.PHONY: rate
rate: ## (Phase 2) Compute team strength ratings from completed matches only
	@echo "[rate] Phase 2 not yet implemented. See plan.md §6." >&2; exit 2

.PHONY: model
model: ## (Phase 3) Fit/build the Dixon-Coles goal model
	@echo "[model] Phase 3 not yet implemented. See plan.md §6." >&2; exit 2

.PHONY: simulate
simulate: ## (Phase 4) Run the tournament Monte Carlo from current real state
	@echo "[simulate] Phase 4 not yet implemented. See plan.md §6." >&2; exit 2

.PHONY: report
report: ## (Phase 5) Title odds + delta vs previous run
	@echo "[report] Phase 5 not yet implemented. See plan.md §6." >&2; exit 2

.PHONY: live
live: ## (Phase 5) Full live refresh: fetch -> rate -> model -> simulate -> report
	@echo "[live] Phase 5 not yet implemented. See plan.md §6." >&2; exit 2

# ---- housekeeping -----------------------------------------------------------
.PHONY: clean
clean: ## Remove derived/processed artifacts (keeps committed reference data)
	@rm -rf data/processed/* reports/*.tmp 2>/dev/null || true
	@find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	@echo "[clean] done."
