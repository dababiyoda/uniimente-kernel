"""Commit Witness: one-time execution with receipt and reconciliation.

The execution half of the kernel invariant. An authorized action crosses
this boundary exactly once per exact fingerprint:

    authorized action -> exact fingerprint -> Commit Witness -> one-time
    execution -> receipt -> postcondition check -> reconciliation.

- **Exact fingerprint**: canonical sha256 of action type, resource, target,
  and parameters. The same intent executed twice is detected by identity,
  not by convention.
- **One-time execution**: a fingerprint already committed returns its
  recorded receipt; the executor never runs twice. The dedupe set is
  rebuilt from the ledger on startup, so it survives process restarts.
- **Receipt**: what reality returned (result or error), timing included.
- **Postcondition**: expected consequences checked against observation.
  A failed postcondition is not quietly logged; it opens reconciliation
  and, by default, fails toward silence by disarming the kill switch.
- **Reconciliation**: every divergence is ledgered for the outcome
  record and the causal chain. An executed action without its receipt
  and reconciliation is incomplete and blocks autonomy promotion.

The witness never authorizes anything. Authorization already happened
upstream (capability grant + policy). This boundary only guarantees that
what was authorized happens exactly once and is honestly recorded.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any, Callable, Dict, List, Optional

from uniimente_kernel.ledger import DecisionLedger, KillSwitch

# Outcome vocabulary aligned with contracts/outcome.schema.json.
RESULT_CLASSES = frozenset({"positive", "negative", "zero_response", "inconclusive", "harm"})


def action_fingerprint(
    action_type: str,
    resource: str,
    target: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None,
) -> str:
    """Canonical sha256 of the exact act. Identity, not convention."""
    canonical = json.dumps(
        {"action_type": action_type, "resource": resource,
         "target": target, "parameters": parameters or {}},
        sort_keys=True, separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class PostconditionResult:
    name: str
    expected: str
    observed: str
    ok: bool


@dataclass
class CommitReceipt:
    witness_id: str
    fingerprint: str
    grant_id: str
    action_type: str
    resource: str
    status: str  # committed | failed | postcondition_failed | deduplicated
    executed_at: Optional[str]
    completed_at: Optional[str]
    result: Any = None
    error: Optional[str] = None
    postconditions: List[PostconditionResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "witness_id": self.witness_id,
            "fingerprint": self.fingerprint,
            "grant_id": self.grant_id,
            "action_type": self.action_type,
            "resource": self.resource,
            "status": self.status,
            "executed_at": self.executed_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error,
            "postconditions": [vars(p) for p in self.postconditions],
        }


class CommitWitness:
    """Guarantees one-time execution and honest recording of authorized acts."""

    def __init__(
        self,
        ledger: DecisionLedger,
        *,
        kill_switch: Optional[KillSwitch] = None,
        disarm_on_postcondition_failure: bool = True,
    ) -> None:
        self.ledger = ledger
        self.kill_switch = kill_switch
        self.disarm_on_postcondition_failure = disarm_on_postcondition_failure
        # Rebuild the dedupe set from the ledger: witnessed fingerprints
        # survive process restarts, so a retried deploy cannot re-execute.
        # Only effects that actually happened dedupe: "committed" (verified)
        # and "postcondition_failed" (executed but unverified; repair runs
        # through reconciliation, never blind re-execution). A "failed"
        # commit produced no effect, so repair-and-retry must execute.
        self._committed: Dict[str, Dict[str, Any]] = {}
        for entry in self.ledger.replay(event="commit_executed"):
            payload = entry["payload"]
            if payload.get("status") in ("committed", "postcondition_failed"):
                self._committed[payload["fingerprint"]] = payload

    def already_committed(self, fingerprint: str) -> bool:
        return fingerprint in self._committed

    def commit(
        self,
        *,
        grant_id: str,
        action_type: str,
        resource: str,
        target: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        executor: Callable[[], Any],
        postconditions: Optional[Dict[str, Callable[[Any], bool]]] = None,
    ) -> CommitReceipt:
        """Execute `executor` exactly once per fingerprint.

        `postconditions` maps a name to a predicate over the executor's
        result; every predicate must hold or reconciliation opens.
        """
        fingerprint = action_fingerprint(action_type, resource, target, parameters)
        witness_id = str(uuid.uuid4())

        if fingerprint in self._committed:
            prior = self._committed[fingerprint]
            self.ledger.record("commit_deduplicated", {
                "fingerprint": fingerprint,
                "original_witness_id": prior.get("witness_id"),
                "repeated_grant_id": grant_id,
            })
            return CommitReceipt(
                witness_id=prior.get("witness_id", witness_id),
                fingerprint=fingerprint,
                grant_id=prior.get("grant_id", grant_id),
                action_type=action_type,
                resource=resource,
                status="deduplicated",
                executed_at=prior.get("executed_at"),
                completed_at=prior.get("completed_at"),
                result=prior.get("result"),
            )

        self.ledger.record("commit_witnessed", {
            "witness_id": witness_id,
            "fingerprint": fingerprint,
            "grant_id": grant_id,
            "action_type": action_type,
            "resource": resource,
            "target": target,
        })

        executed_at = datetime.now(UTC).isoformat()
        result, error, status = None, None, "committed"
        try:
            result = executor()
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            status = "failed"
        completed_at = datetime.now(UTC).isoformat()

        receipt = CommitReceipt(
            witness_id=witness_id,
            fingerprint=fingerprint,
            grant_id=grant_id,
            action_type=action_type,
            resource=resource,
            status=status,
            executed_at=executed_at,
            completed_at=completed_at,
            result=result,
            error=error,
        )

        if status == "committed":
            for name, predicate in (postconditions or {}).items():
                try:
                    ok = bool(predicate(result))
                except Exception as exc:
                    ok = False
                    receipt.postconditions.append(PostconditionResult(
                        name=name, expected="predicate holds",
                        observed=f"predicate raised: {exc}", ok=False))
                    continue
                receipt.postconditions.append(PostconditionResult(
                    name=name, expected="predicate holds",
                    observed="holds" if ok else "violated", ok=ok))
            if any(not p.ok for p in receipt.postconditions):
                receipt.status = "postcondition_failed"

        self.ledger.record("commit_executed", {
            "witness_id": witness_id,
            "fingerprint": fingerprint,
            "grant_id": grant_id,
            "status": receipt.status,
            "executed_at": executed_at,
            "completed_at": completed_at,
            "result": result if status != "failed" else None,
            "error": error,
        })
        if receipt.status in ("committed", "postcondition_failed"):
            # The effect happened (verified or not); never re-execute it.
            self._committed[fingerprint] = {
                "witness_id": witness_id, "grant_id": grant_id,
                "executed_at": executed_at, "completed_at": completed_at,
                "result": result,
            }

        if receipt.status == "postcondition_failed":
            self.ledger.record("reconciliation_opened", {
                "witness_id": witness_id,
                "fingerprint": fingerprint,
                "failed_postconditions": [p.name for p in receipt.postconditions if not p.ok],
            })
            if self.disarm_on_postcondition_failure and self.kill_switch is not None:
                self.kill_switch.set_armed(False, reason="postcondition_failed")

        return receipt


__all__ = [
    "RESULT_CLASSES",
    "action_fingerprint",
    "PostconditionResult",
    "CommitReceipt",
    "CommitWitness",
]
