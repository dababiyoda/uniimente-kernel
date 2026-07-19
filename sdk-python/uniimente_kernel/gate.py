"""Consequence Gate: the one commit-time boundary for external action.

Closes the Phase 1 chain as a single composition:

    Evidence -> Policy -> Authority -> Commit Witness -> Execution
    -> Receipt -> Reconciliation -> Outcome

No consequential external effect passes except through ``execute``:

1. A ``consequence.requested`` event is emitted carrying the evidence
   references and the expected consequence (Evidence).
2. The capability grant is validated and consumed immediately before
   execution (Policy + Authority); any refusal fails closed, is ledgered,
   and is emitted as ``consequence.rejected``. Replay of an already
   committed fingerprint deduplicates *without* burning a grant use.
3. The Commit Witness executes exactly once per action fingerprint,
   receipts every path, opens reconciliation and disarms on postcondition
   failure (Commit Witness + Execution + Receipt + Reconciliation).
4. ``record_outcome`` attaches what actually happened, including negative
   and zero responses, causally chained to the commit (Outcome).

Every step is hash-chained in the decision ledger and causally linked in
the event spine, so the full path from evidence to outcome replays.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .capability import CapabilityError, CapabilityService
from .commit_witness import (
    RESULT_CLASSES,
    CommitReceipt,
    CommitWitness,
    action_fingerprint,
)
from .events import Event, EventSpine
from .ledger import DecisionLedger

VALIDATION_STATUSES = frozenset({
    "externally_verified",
    "internally_observed",
    "self_reported",
})

_FINAL_EVENT = {
    "committed": "consequence.committed",
    "failed": "consequence.failed",
    "postcondition_failed": "consequence.reconciliation_opened",
    "deduplicated": "consequence.deduplicated",
}


class GateError(ValueError):
    """Programmer-error misuse of the gate (never raised for denials)."""


@dataclass
class GateResult:
    """The gate's answer for one attempted consequence.

    ``status`` is "rejected" (authority refused), or the CommitReceipt
    status. ``executed`` is True only when the external effect actually
    happened (committed or postcondition_failed). A rejected or
    deduplicated result never re-ran the executor.
    """

    status: str
    executed: bool
    request_event: Event
    final_event: Event
    receipt: Optional[CommitReceipt] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "executed": self.executed,
            "request_event_id": self.request_event.id,
            "final_event_id": self.final_event.id,
            "receipt": self.receipt.to_dict() if self.receipt else None,
            "error": self.error,
        }


class ConsequenceGate:
    """One hardened boundary governing external action.

    Composes the capability service (authority), the commit witness
    (one-time execution), and the event spine (causal memory) over one
    shared decision ledger. Organs call ``execute`` and nothing else.
    """

    def __init__(
        self,
        ledger: DecisionLedger,
        *,
        capability: CapabilityService,
        witness: CommitWitness,
        spine: EventSpine,
    ) -> None:
        self.ledger = ledger
        self.capability = capability
        self.witness = witness
        self.spine = spine

    def execute(
        self,
        *,
        grant_id: str,
        action_type: str,
        resource: str,
        executor: Callable[[], Any],
        target: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        cost: float = 0.0,
        postconditions: Optional[Dict[str, Callable[[Any], bool]]] = None,
        evidence_refs: Optional[List[str]] = None,
        expected_consequence: Optional[str] = None,
        subject: Optional[str] = None,
    ) -> GateResult:
        """Attempt one authorized, witnessed, receipted external effect."""
        fingerprint = action_fingerprint(action_type, resource, target, parameters)
        request = self.spine.emit(
            "consequence.requested",
            subject=subject or resource,
            data={
                "grant_id": grant_id,
                "action_type": action_type,
                "resource": resource,
                "target": target,
                "fingerprint": fingerprint,
                "cost_usd": cost,
            },
            evidence_refs=evidence_refs,
            expected_consequence=expected_consequence,
        )

        # Replay defense precedes authority: an already-committed
        # fingerprint deduplicates without consuming a grant use.
        if self.witness.already_committed(fingerprint):
            receipt = self.witness.commit(
                grant_id=grant_id, action_type=action_type, resource=resource,
                target=target, parameters=parameters, executor=executor,
                postconditions=postconditions,
            )
            final = self.spine.chain(
                "consequence.deduplicated", request,
                data={
                    "fingerprint": fingerprint,
                    "witness_id": receipt.witness_id,
                    "grant_id": grant_id,
                    "note": "effect already exists; executor did not run",
                },
            )
            return GateResult(status="deduplicated", executed=False,
                              request_event=request, final_event=final,
                              receipt=receipt)

        # Authority: validate and consume the grant at commit time.
        # Every refusal path fails closed and is already ledger-rejected
        # by the capability service; the gate adds the causal event.
        try:
            grant = self.capability.validate_and_consume(
                grant_id, action_type, resource, target=target, cost=cost,
            )
        except CapabilityError as exc:
            final = self.spine.chain(
                "consequence.rejected", request,
                data={"grant_id": grant_id, "reason": str(exc),
                      "fingerprint": fingerprint},
            )
            return GateResult(status="rejected", executed=False,
                              request_event=request, final_event=final,
                              error=str(exc))

        authorized = self.spine.chain(
            "consequence.authorized", request,
            data={
                "grant_id": grant_id,
                "use": grant.uses_consumed,
                "of": grant.maximum_uses,
                "fingerprint": fingerprint,
            },
        )

        # Commit Witness: exactly one execution, receipted every path.
        receipt = self.witness.commit(
            grant_id=grant_id, action_type=action_type, resource=resource,
            target=target, parameters=parameters, executor=executor,
            postconditions=postconditions,
        )
        final = self.spine.chain(
            _FINAL_EVENT[receipt.status], authorized,
            data={
                "witness_id": receipt.witness_id,
                "fingerprint": fingerprint,
                "status": receipt.status,
                "error": receipt.error,
                "postconditions": [vars(p) for p in receipt.postconditions],
            },
        )
        return GateResult(
            status=receipt.status,
            executed=receipt.status in ("committed", "postcondition_failed"),
            request_event=request, final_event=final, receipt=receipt,
            error=receipt.error,
        )

    def record_outcome(
        self,
        parent: Event,
        *,
        external_observation: str,
        result_class: str,
        expected_vs_actual: str,
        validation_status: str,
        evidence_refs: Optional[List[str]] = None,
        learning: Optional[str] = None,
    ) -> Event:
        """Attach what actually happened to a committed consequence.

        An executed action without its outcome is incomplete and blocks
        autonomy promotion. Zero response is a negative result, never an
        absence.
        """
        if result_class not in RESULT_CLASSES:
            raise GateError(
                f"result_class must be one of {sorted(RESULT_CLASSES)}"
            )
        if validation_status not in VALIDATION_STATUSES:
            raise GateError(
                f"validation_status must be one of {sorted(VALIDATION_STATUSES)}"
            )
        return self.spine.chain(
            "consequence.outcome", parent,
            data={
                "external_observation": external_observation,
                "result_class": result_class,
                "expected_vs_actual": expected_vs_actual,
                "validation_status": validation_status,
                "learning": learning,
            },
            evidence_refs=evidence_refs,
        )


__all__ = [
    "VALIDATION_STATUSES",
    "GateError",
    "GateResult",
    "ConsequenceGate",
]
