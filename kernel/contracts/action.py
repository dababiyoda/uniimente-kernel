"""Action contracts.

Implements Hard Rule 2 (approvals bind to the intent fingerprint) and
Hard Rule 3 (REQUIRE_HUMAN is unbypassable): ActionIntent carries exactly the
fields the fingerprint binds, and ApprovalRecord is signed over
fingerprint+approver+nonce.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from .base import KernelModel

ConsequenceClass = Literal["C0", "C1", "C2", "C3", "C4", "C5"]
AutonomyStage = Literal["A0", "A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9"]


class ActionIntent(KernelModel):
    actor_id: str
    organ_id: str
    legal_principal: str
    objective: str
    action_type: str
    resource: str
    target: str
    payload: dict[str, Any]
    consequence_class: ConsequenceClass
    evidence_ids: list[str] = []
    expected_outcome: str
    rollback: str | None = None
    expiry_minutes: int = 60


class PolicyDecision(KernelModel):
    intent_fingerprint: str
    effect: Literal["PERMIT", "DENY", "REQUIRE_HUMAN"]
    governing_clauses: list[str]
    policy_version: str
    constitution_version: str
    decision_trace: list[str]


class ApprovalRecord(KernelModel):
    intent_fingerprint: str
    approver_id: str
    signature: str  # Ed25519 hex over fingerprint+approver+nonce
    nonce: str
    expires_at: datetime


class CapabilityGrant(KernelModel):
    grant_id: str
    intent_fingerprint: str
    allowed_tools: list[str]
    allowed_targets: list[str]
    budget: dict[str, float]  # keys: cpu_seconds, memory_mb, cost_usd
    one_use: bool = True
    expires_at: datetime
    revoked: bool = False
    signature: str


class AutonomyLicense(KernelModel):
    capability_id: str
    domain: str
    action_type: str
    resource: str
    target_class: str
    consequence_class: ConsequenceClass
    budget: dict[str, float]
    duration: int  # seconds
    stage: AutonomyStage
