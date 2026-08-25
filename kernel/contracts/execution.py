"""Execution contracts.

CommitWitness is the ONLY object that authorizes an adapter to execute
(Hard Rule 1). It binds the intent fingerprint, the exact payload hash and the
exact target, so any post-approval mutation is detectable at revalidation
(Hard Rule 2).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .base import KernelModel


class CommitWitness(KernelModel):
    intent_fingerprint: str
    policy_decision_id: str
    approval_id: str | None
    grant_id: str
    constitution_version: str
    policy_version: str
    exact_payload_hash: str
    exact_target: str
    expected_outcome: str
    expires_at: datetime
    witness_signature: str  # Ed25519 hex over all fields above


class ExecutionReceipt(KernelModel):
    witness_id: str
    adapter_id: str
    external_id: str | None = None
    provider_response_hash: str
    executed_at: datetime
    success: bool
    signature: str


class ReconciliationRecord(KernelModel):
    receipt_id: str
    expected_hash: str
    actual_hash: str
    reconciled: bool
    discrepancy: str | None = None


class OutcomeRecord(KernelModel):
    intent_fingerprint: str
    receipt_id: str
    actual_outcome: str
    matched_expected: bool
    regenerative_effect: dict[str, Any] = {}


class DecisionEpisode(KernelModel):
    intent_id: str
    decision_id: str = ""  # empty when refusal happened before EVALUATE
    approval_id: str | None = None
    witness_id: str | None = None
    receipt_id: str | None = None
    outcome_id: str | None = None
    closed: bool = False
    close_reason: str = ""
