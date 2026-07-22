"""Context-scoped reputation derived only from reconciled settlements.

This module deliberately does not emit a universal score.  A delivery record
for one action class, legal principal, or reality status is not silently
portable into another risk context.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from provenance.ledger import EvidenceLedger
from trustrail.credentials import TrustRailRefused
from trustrail.models import (
    SettlementIntent,
    SettlementReceipt,
    SettlementState,
    VerifiedOutcomeCredential,
    object_hash,
    rfc3339,
)


@dataclass
class ReputationSnapshot:
    actor_id: str
    action_class: str
    legal_principal: str
    reality_status: str
    reconciled_count: int = 0
    disputed_count: int = 0
    credential_ids: list[str] = field(default_factory=list)
    evidence_hashes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "action_class": self.action_class,
            "legal_principal": self.legal_principal,
            "reality_status": self.reality_status,
            "reconciled_count": self.reconciled_count,
            "disputed_count": self.disputed_count,
            "credential_ids": list(self.credential_ids),
            "evidence_hashes": list(self.evidence_hashes),
        }


class ScopedReputationLedger:
    """Evidence-indexed history, never a cross-context social-credit score."""

    def __init__(self, ledger: EvidenceLedger):
        self.ledger = ledger
        self._settlements: dict[str, dict[str, Any]] = {}
        self._disputes: set[str] = set()

    @staticmethod
    def _scope(credential: VerifiedOutcomeCredential) -> tuple[str, str, str, str]:
        return (
            credential.actor_id,
            credential.action_class,
            credential.legal_principal,
            credential.reality_status.value,
        )

    def record_reconciled(self, credential: VerifiedOutcomeCredential,
                          intent: SettlementIntent,
                          receipt: SettlementReceipt) -> dict[str, Any]:
        if intent.state != SettlementState.RECONCILED or not receipt.reconciled:
            raise TrustRailRefused("reputation requires a reconciled settlement")
        if intent.credential_id != credential.credential_id:
            raise TrustRailRefused("reputation credential binding mismatch")
        prior = self._settlements.get(intent.intent_id)
        if prior:
            return prior
        payload = {
            "type": "reputation.evidence_added",
            "intent_id": intent.intent_id,
            "credential_id": credential.credential_id,
            "actor_id": credential.actor_id,
            "action_class": credential.action_class,
            "legal_principal": credential.legal_principal,
            "reality_status": credential.reality_status.value,
            "settlement_receipt_hash": object_hash(receipt.to_dict()),
            "at": rfc3339(),
        }
        record = self.ledger.append("reputation_evidence", payload)
        payload = {**payload, "ledger_record_hash": record.hash}
        self._settlements[intent.intent_id] = payload
        return payload

    def mark_disputed(self, *, dispute_id: str, intent_id: str | None,
                      credential: VerifiedOutcomeCredential) -> None:
        if dispute_id in self._disputes:
            return
        self._disputes.add(dispute_id)
        self.ledger.append("reputation_dispute", {
            "type": "reputation.evidence_disputed",
            "dispute_id": dispute_id,
            "intent_id": intent_id,
            "credential_id": credential.credential_id,
            "actor_id": credential.actor_id,
            "action_class": credential.action_class,
            "legal_principal": credential.legal_principal,
            "reality_status": credential.reality_status.value,
            "at": rfc3339(),
        })

    def snapshot(self, *, actor_id: str, action_class: str,
                 legal_principal: str, reality_status: str) -> ReputationSnapshot:
        if not all((actor_id, action_class, legal_principal, reality_status)):
            raise TrustRailRefused("reputation queries require an exact risk scope")
        wanted = (actor_id, action_class, legal_principal, reality_status)
        matching = [p for p in self._settlements.values() if (
            p["actor_id"], p["action_class"], p["legal_principal"], p["reality_status"]
        ) == wanted]
        disputed_credentials = {
            r.payload["credential_id"]
            for r in self.ledger.by_type("reputation_dispute")
            if (
                r.payload.get("actor_id"),
                r.payload.get("action_class"),
                r.payload.get("legal_principal"),
                r.payload.get("reality_status"),
            ) == wanted
        }
        return ReputationSnapshot(
            actor_id=actor_id,
            action_class=action_class,
            legal_principal=legal_principal,
            reality_status=reality_status,
            reconciled_count=len(matching),
            disputed_count=len(disputed_credentials),
            credential_ids=sorted({p["credential_id"] for p in matching}),
            evidence_hashes=sorted(p["ledger_record_hash"] for p in matching),
        )
