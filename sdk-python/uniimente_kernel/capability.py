"""Capability-based authority: narrow, expiring, revocable permissions.

Extracted from DALEOBANKS ``services/capability.py`` (kernel Phase 2) and
generalized onto the kernel contract ``contracts/capability-grant.schema.json``.

A grant is minted only after human approval and authorizes exact action
types against exact resources, a bounded number of times, inside a bounded
window. Validation happens at execution time, not only at approval time;
expired, revoked, mismatched, exhausted, or replayed grants fail closed,
and a broken decision-ledger chain disarms consumption entirely. Every
lifecycle event is ledgered.

This module authorizes nothing by itself. It verifies that a human did.

Generalization points versus the DALEOBANKS original:

- No ORM. Grants are plain records behind a small ``GrantStore`` protocol;
  organs adapt their storage (DALEOBANKS wraps its SQLAlchemy session).
  ``InMemoryGrantStore`` serves tests and local runs.
- Human approval is proven through an injected ``approval_verifier``
  callable. It must return True for minting to proceed; any exception or
  False fails closed.
- The crisis-pause check is an injected callable. When configured, an
  unreadable crisis state fails closed, exactly as in DALEOBANKS. When not
  configured, the check is skipped (documented, never silent).
- Grant fields follow the kernel contract. Validation order is preserved
  from the original: ledger chain, crisis, unknown, revoked, not-yet-valid,
  expired, exhausted, action mismatch, resource mismatch, target mismatch,
  cost ceiling.
- Minting enforces the constitutional child-grant rule: a grant naming a
  ``parent_grant`` must be a strict subset of its parent.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, UTC
from typing import Any, Callable, Dict, List, Optional, Protocol

from uniimente_kernel.ledger import DecisionLedger


class CapabilityError(PermissionError):
    """A grant failed validation. Execution must not proceed."""


def _now() -> datetime:
    return datetime.now(UTC)


def default_ttl_hours() -> int:
    try:
        return int(os.getenv("CAPABILITY_TTL_HOURS", "72"))
    except ValueError:
        return 72


@dataclass
class GrantRecord:
    """Kernel-native capability grant, mirroring contracts/capability-grant.schema.json."""

    grantee: str
    granted_by: str
    legal_actor: str
    objective: str
    permitted_actions: List[str]
    resource: str
    spending_limit_usd: float = 0.0
    maximum_uses: int = 1
    named_targets: List[str] = field(default_factory=list)
    prohibited: List[str] = field(default_factory=list)
    initial_stage: str = "simulate"          # simulate | shadow; executable stages require promotion
    parent_grant: Optional[str] = None
    approval_request_id: Optional[str] = None
    evidence_refs: List[str] = field(default_factory=list)
    grant_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    issued_at: datetime = field(default_factory=_now)
    not_before: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    revocable_by: List[str] = field(default_factory=list)
    uses_consumed: int = 0
    revoked: bool = False
    revoked_at: Optional[datetime] = None
    revoked_by: Optional[str] = None
    revocation_reason: str = ""


class GrantStore(Protocol):
    """Minimal storage surface an organ must adapt."""

    def get(self, grant_id: str) -> Optional[GrantRecord]: ...
    def put(self, grant: GrantRecord) -> None: ...


class InMemoryGrantStore:
    def __init__(self) -> None:
        self._grants: Dict[str, GrantRecord] = {}

    def get(self, grant_id: str) -> Optional[GrantRecord]:
        return self._grants.get(grant_id)

    def put(self, grant: GrantRecord) -> None:
        self._grants[grant.grant_id] = grant


class CapabilityService:
    def __init__(
        self,
        store: GrantStore,
        ledger: DecisionLedger,
        *,
        approval_verifier: Callable[[str], bool],
        crisis_check: Optional[Callable[[], bool]] = None,
    ) -> None:
        self.store = store
        self.ledger = ledger
        self._approval_verifier = approval_verifier
        self._crisis_check = crisis_check

    # ------------------------------------------------------------------ #
    # Minting: only behind verified human approval
    # ------------------------------------------------------------------ #
    def mint(
        self,
        grant: GrantRecord,
        *,
        approval_request_id: str,
        ttl_hours: Optional[int] = None,
    ) -> GrantRecord:
        try:
            approved = bool(self._approval_verifier(approval_request_id))
        except Exception:
            approved = False
        if not approved:
            self._reject(approval_request_id, "approval_unverified")
            raise CapabilityError("grants mint only from verified human approvals")
        if not grant.permitted_actions or not grant.resource:
            raise CapabilityError("permitted_actions and resource are required")
        if grant.initial_stage not in ("simulate", "shadow"):
            self._reject(approval_request_id, "material_authority_at_issuance")
            raise CapabilityError(
                "new grants start only at simulate or shadow; executable stages require recorded promotion"
            )
        if grant.parent_grant is not None:
            self._enforce_subset_of_parent(grant)

        grant.approval_request_id = approval_request_id
        grant.expires_at = _now() + timedelta(hours=ttl_hours or default_ttl_hours())
        self.store.put(grant)
        self.ledger.record("capability_granted", {
            "id": grant.grant_id,
            "approval_request_id": approval_request_id,
            "permitted_actions": grant.permitted_actions,
            "resource": grant.resource,
            "maximum_uses": grant.maximum_uses,
            "initial_stage": grant.initial_stage,
            "expires_at": grant.expires_at.isoformat(),
        })
        return grant

    def _enforce_subset_of_parent(self, grant: GrantRecord) -> None:
        parent = self.store.get(grant.parent_grant or "")
        if parent is None:
            self._reject(grant.grant_id, "unknown_parent_grant")
            raise CapabilityError("parent grant unknown")
        if parent.revoked:
            self._reject(grant.grant_id, "parent_revoked")
            raise CapabilityError("parent grant is revoked")
        if not set(grant.permitted_actions).issubset(set(parent.permitted_actions)):
            self._reject(grant.grant_id, "child_exceeds_parent_actions")
            raise CapabilityError("child grant exceeds parent permitted_actions")
        if grant.resource != parent.resource:
            self._reject(grant.grant_id, "child_exceeds_parent_resource")
            raise CapabilityError("child grant exceeds parent resource")
        if grant.spending_limit_usd > parent.spending_limit_usd:
            self._reject(grant.grant_id, "child_exceeds_parent_budget")
            raise CapabilityError("child grant exceeds parent spending limit")
        if parent.named_targets and not set(grant.named_targets).issubset(set(parent.named_targets)):
            self._reject(grant.grant_id, "child_exceeds_parent_targets")
            raise CapabilityError("child grant exceeds parent named targets")

    # ------------------------------------------------------------------ #
    # Execution-time validation: the load-bearing gate
    # ------------------------------------------------------------------ #
    def validate_and_consume(
        self,
        grant_id: str,
        action_type: str,
        resource: str,
        *,
        target: Optional[str] = None,
        cost: float = 0.0,
    ) -> GrantRecord:
        """Validate a grant immediately before execution and consume one use.
        Any failure raises CapabilityError; the caller must not act."""
        # A broken ledger disarms external action entirely.
        chain_ok, _ = self.ledger.verify_chain()
        if not chain_ok:
            self._reject(grant_id, "ledger_chain_broken")
            raise CapabilityError("decision ledger chain is broken — failing closed")

        # Crisis pause suspends consequential execution even for validly
        # granted acts; an unreadable crisis state fails closed, not open.
        if self._crisis_check is not None:
            try:
                paused = bool(self._crisis_check())
            except Exception:
                paused = None
            if paused is not False:
                reason = "crisis_paused" if paused else "crisis_state_unreadable"
                self._reject(grant_id, reason)
                raise CapabilityError(
                    "crisis pause active — consequential execution is suspended"
                    if paused else
                    "crisis state unreadable — failing closed"
                )

        grant = self.store.get(grant_id)
        if grant is None:
            self._reject(grant_id, "unknown_grant")
            raise CapabilityError("unknown capability grant")
        if grant.revoked:
            self._reject(grant_id, "revoked")
            raise CapabilityError("grant is revoked")
        now = _now()
        if grant.not_before and now < grant.not_before:
            self._reject(grant_id, "not_yet_valid")
            raise CapabilityError("grant is not yet valid")
        if grant.expires_at and now >= grant.expires_at:
            self._reject(grant_id, "expired")
            self.ledger.record("capability_expired", {"id": grant.grant_id})
            raise CapabilityError("grant is expired")
        if grant.uses_consumed >= grant.maximum_uses:
            self._reject(grant_id, "exhausted")
            raise CapabilityError("grant is exhausted — replay refused")
        if action_type not in grant.permitted_actions:
            self._reject(grant_id, "action_mismatch")
            raise CapabilityError(f"grant does not authorize '{action_type}'")
        if grant.resource != resource:
            self._reject(grant_id, "resource_mismatch")
            raise CapabilityError("grant does not cover this resource")
        if target is not None and grant.named_targets and target not in grant.named_targets:
            self._reject(grant_id, "target_mismatch")
            raise CapabilityError("grant does not cover this target")
        if cost and cost > grant.spending_limit_usd:
            self._reject(grant_id, "cost_exceeded")
            raise CapabilityError(
                f"cost {cost} exceeds the grant ceiling {grant.spending_limit_usd}"
            )

        grant.uses_consumed += 1
        self.store.put(grant)
        self.ledger.record("capability_consumed", {
            "id": grant.grant_id, "action_type": action_type, "resource": resource,
            "use": grant.uses_consumed, "of": grant.maximum_uses,
        })
        return grant

    def _reject(self, grant_id: str, reason: str) -> None:
        self.ledger.record("capability_rejected", {"id": grant_id, "reason": reason})

    # ------------------------------------------------------------------ #
    # Revocation: immediate, ledgered
    # ------------------------------------------------------------------ #
    def revoke(self, grant_id: str, *, revoked_by: str, reason: str = "") -> GrantRecord:
        grant = self.store.get(grant_id)
        if grant is None:
            raise CapabilityError("unknown capability grant")
        grant.revoked = True
        grant.revoked_at = _now()
        grant.revoked_by = revoked_by
        grant.revocation_reason = reason
        self.store.put(grant)
        self.ledger.record("capability_revoked", {
            "id": grant.grant_id, "by": revoked_by, "reason": reason,
        })
        return grant


__all__ = [
    "CapabilityError",
    "CapabilityService",
    "GrantRecord",
    "GrantStore",
    "InMemoryGrantStore",
    "default_ttl_hours",
]
