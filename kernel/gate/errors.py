"""GateRefusal hierarchy — Hard Rule 4: fail closed on ANY ambiguity.

Every refusal carries the pipeline stage that raised it and a human-readable
reason. The gate never permits on doubt: anything unexpected becomes a
GateRefusal, the episode is closed with the reason, and the refusal event is
appended to the spine (best effort if the spine itself is lost).
"""
from __future__ import annotations


class GateRefusal(Exception):
    """Base refusal. The gate fails closed: refusal, never silent permission."""

    def __init__(self, reason: str, *, stage: str = "UNKNOWN"):
        super().__init__(reason)
        self.reason = reason
        self.stage = stage

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"[{self.stage}] {self.reason}"


class IdentityRefusal(GateRefusal):
    """IDENTIFY: legal_principal missing or empty."""


class ClassificationRefusal(GateRefusal):
    """CLASSIFY: consequence_class missing or unknown."""


class StaleEvidence(GateRefusal):
    """EVALUATE/REAUTHORIZE: evidence stale, past freshness_deadline, or unknown."""


class PolicyDenial(GateRefusal):
    """EVALUATE: policy effect == DENY."""


class PolicyRefusal(GateRefusal):
    """EVALUATE: policy_fn returned an invalid or mismatched PolicyDecision."""


class ApprovalRefusal(GateRefusal):
    """APPROVE/REAUTHORIZE: approval missing, forged, expired, mismatched or replayed."""


class BudgetRefusal(GateRefusal):
    """RESERVE: budget unknown, over per-intent cap, or split-budget evasion."""


class GrantRefusal(GateRefusal):
    """REAUTHORIZE: grant missing, wrong, or not one_use."""


class GrantExpired(GrantRefusal):
    """REAUTHORIZE: grant expired before commit."""


class GrantRevoked(GrantRefusal):
    """REAUTHORIZE: grant revoked before commit."""


class DuplicateExecution(GateRefusal):
    """REAUTHORIZE/EXECUTE: one_use grant or witness reused; double execution refused."""


class WitnessRefusal(GateRefusal):
    """EXECUTE: witness invalid, forged, or expired."""


class WitnessMissing(WitnessRefusal):
    """EXECUTE: no CommitWitness supplied (Hard Rule 1)."""


class ReauthorizationRefusal(GateRefusal):
    """REAUTHORIZE: intent mutated after approval (payload/target/fingerprint)."""


class ExecutionRefusal(GateRefusal):
    """EXECUTE: no adapter, unregistered adapter, or adapter reported failure."""


class ReceiptForgery(GateRefusal):
    """RECEIPT: receipt signature/binding invalid."""


class VerificationRefusal(GateRefusal):
    """VERIFY: postcondition check failed."""


class ReconciliationRefusal(GateRefusal):
    """RECONCILE: actual outcome hash differs from expected outcome hash."""


class SpineRefusal(GateRefusal):
    """Any stage: the spine could not record an event (spine loss mid-pipeline)."""
