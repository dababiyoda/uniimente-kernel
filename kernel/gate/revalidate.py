"""Commit-time revalidation — Hard Rules 1, 2 and 4.

Immediately before execution (REAUTHORIZE), everything is re-checked:
fingerprint binding (payload, target, budget, legal_principal, policy_version,
consequence_class), grant state (revoked / expired / spent), witness expiry,
approval validity and evidence freshness. The durable duplicate-execution
guard scans the spine so replay after a restart still refuses to double-execute.

Anything ambiguous raises a GateRefusal subclass — never a silent permit.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Mapping

from ..contracts.action import ActionIntent, ApprovalRecord, CapabilityGrant, PolicyDecision
from ..contracts.execution import CommitWitness
from ..contracts.institutional import EvidencePacket
from ..crypto.hashing import content_hash
from . import errors
from .fingerprint import intent_fingerprint


def check_evidence_freshness(
    evidence_ids: list[str],
    evidence_store: Mapping[str, EvidencePacket],
    now: datetime,
    *,
    stage: str = "EVALUATE",
) -> None:
    """Fail closed on unknown or stale evidence."""
    for eid in evidence_ids:
        pkt = evidence_store.get(eid)
        if pkt is None:
            raise errors.StaleEvidence(
                f"unknown evidence id {eid!r}; ambiguity fails closed", stage=stage
            )
        if now >= pkt.freshness_deadline:
            raise errors.StaleEvidence(
                f"evidence {eid!r} is stale: freshness_deadline "
                f"{pkt.freshness_deadline.isoformat()} has passed",
                stage=stage,
            )


def revalidate(
    *,
    intent: ActionIntent,
    fingerprint: str,
    decision: PolicyDecision,
    approval: ApprovalRecord | None,
    grant: CapabilityGrant,
    witness: CommitWitness,
    now: datetime,
    spine_records: Iterable[dict[str, Any]],
    grant_store,
    evidence_store: Mapping[str, EvidencePacket],
    policy_version: str,
    constitution_version: str,
) -> None:
    """Re-validate everything immediately before execute. Raises GateRefusal."""
    stage = "REAUTHORIZE"

    # 1. Fingerprint binding (Hard Rule 2): any mutation invalidates.
    if intent_fingerprint(intent, policy_version) != witness.intent_fingerprint:
        raise errors.ReauthorizationRefusal(
            "intent mutated after approval: fingerprint mismatch", stage=stage
        )
    if content_hash(intent.payload) != witness.exact_payload_hash:
        raise errors.ReauthorizationRefusal(
            "payload mutated after approval: exact_payload_hash mismatch", stage=stage
        )
    if intent.target != witness.exact_target:
        raise errors.ReauthorizationRefusal(
            "target substituted after approval: exact_target mismatch", stage=stage
        )
    if fingerprint != witness.intent_fingerprint:
        raise errors.ReauthorizationRefusal("fingerprint drift between PROPOSE and commit", stage=stage)
    if witness.policy_version != policy_version or witness.constitution_version != constitution_version:
        raise errors.ReauthorizationRefusal("policy/constitution version drift", stage=stage)

    # 2. Grant state: present, not revoked, not expired, not spent, bound.
    stored = grant_store.get(grant.grant_id)
    if stored is None:
        raise errors.GrantRefusal("grant not found in store", stage=stage)
    if stored.revoked:
        raise errors.GrantRevoked("capability grant was revoked before commit", stage=stage)
    if now >= stored.expires_at:
        raise errors.GrantExpired("capability grant expired before commit", stage=stage)
    if grant_store.is_spent(stored.grant_id):
        raise errors.DuplicateExecution("one_use grant already spent", stage=stage)
    if stored.intent_fingerprint != witness.intent_fingerprint:
        raise errors.GrantRefusal(
            "grant fingerprint mismatch (cross-intent capability use refused)", stage=stage
        )
    if not stored.one_use:
        raise errors.GrantRefusal("grants in this slice must be one_use", stage=stage)

    # 3. Witness expiry.
    if now >= witness.expires_at:
        raise errors.WitnessRefusal("commit witness expired before execution", stage=stage)

    # 4. Approval still valid when the policy required a human (Hard Rule 3).
    if decision.effect == "REQUIRE_HUMAN":
        if approval is None or witness.approval_id != approval.id:
            raise errors.ApprovalRefusal(
                "required approval missing at commit time", stage=stage
            )
        if now >= approval.expires_at:
            raise errors.ApprovalRefusal("approval expired before commit", stage=stage)

    # 5. Evidence freshness re-check at commit time.
    check_evidence_freshness(intent.evidence_ids, evidence_store, now, stage=stage)

    # 6. Durable duplicate-execution guard (survives restarts via the spine).
    for rec in spine_records:
        if rec.get("kind") == "EXECUTE_BEGIN" and rec.get("refs", {}).get("intent_fingerprint") == fingerprint:
            raise errors.DuplicateExecution(
                "an EXECUTE_BEGIN for this intent fingerprint is already sealed on "
                "the spine; refusing to double-execute",
                stage=stage,
            )
