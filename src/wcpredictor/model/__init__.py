"""Phase 3 — Dixon-Coles goal model (plan.md §18)."""
from .dixon_coles import expected_goals, outcome_probs, scoreline_matrix, top_scorelines
from .lambdas import home_gammas, lambdas

__all__ = ["scoreline_matrix", "outcome_probs", "expected_goals", "top_scorelines",
           "lambdas", "home_gammas"]
