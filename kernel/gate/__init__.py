"""The Consequence Gate — 15-step pipeline from ActionIntent to DecisionEpisode.

Enforces the constitutional hard rules: no execution without a verified
CommitWitness (Rule 1), approvals bound to the intent fingerprint (Rule 2),
REQUIRE_HUMAN unbypassable (Rule 3), append-only spine and fail-closed
behavior on any ambiguity (Rule 4), deterministic hashing (Rule 5).
"""
from . import errors
from .fingerprint import intent_fingerprint
from .pipeline import (
    BudgetLedger,
    Gate,
    GrantStore,
    PipelineContext,
    default_policy_evaluator,
)
from .revalidate import check_evidence_freshness, revalidate

__all__ = [
    "errors",
    "intent_fingerprint",
    "BudgetLedger",
    "Gate",
    "GrantStore",
    "PipelineContext",
    "default_policy_evaluator",
    "check_evidence_freshness",
    "revalidate",
]
