"""The single canonical authority issuer.

One object in the whole institution may turn a proposal into a signed
Authorization Certificate. Everything else proposes, verifies, refuses, or
executes. That is what makes the authority singular even though verification is
distributed everywhere.

Three of the verified defects in the previous engines are structurally
impossible here rather than merely tested against:

- An actor cannot exercise a capability it was never granted, because
  `capability_id` is checked against the actor's declared capabilities BEFORE a
  certificate exists, and is then inside the signature.
- A commit-time REQUIRE_HUMAN cannot be discarded, because REQUIRE_HUMAN is not
  a value this issuer can convert into a certificate at all. There is no code
  path from REQUIRE_HUMAN to a signature without an approval record.
- A certificate issued to actor A cannot be redeemed by actor B, because
  actor_id, organ_id and workload_identity are three of the twenty signed
  fields.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from .certificate import (AuthorizationCertificate, CertificateError,
                          build_certificate, hash_evidence_set, hash_payload)
from .keys import SigningProvider

# Ordered weakest to strongest. A certificate may never carry a consequence
# class above the ceiling its principal is entitled to.
CONSEQUENCE_ORDER = ("internal_read", "internal_write", "external_contact",
                     "financial", "irreversible")


class PolicyRefusal(CertificateError):
    pass


class ApprovalRequired(CertificateError):
    """REQUIRE_HUMAN. Deliberately a refusal type, not a status value.

    Raising rather than returning is the point: a caller cannot accidentally
    treat this as permission by ignoring a return value.
    """


class ScopeRefusal(CertificateError):
    pass


class UnknownEntity(CertificateError):
    pass


class BudgetRefusal(CertificateError):
    pass


@dataclass
class Principal:
    """Who is asking. Identity is registered, never self-asserted."""
    actor_id: str
    organ_id: str
    workload_identity: str
    legal_principal: str
    declared_capabilities: tuple[str, ...]
    consequence_ceiling: str
    budget_ceiling_usd: float


@dataclass
class ApprovalRecord:
    """Evidence that an authorized human decided. Bound to the request."""
    approval_id: str
    request_id: str
    approver_id: str
    granted: bool
    issued_at: str


@dataclass
class Proposal:
    request_id: str
    capability_id: str
    action_class: str
    target_id: str
    payload: Any
    consequence_class: str
    evidence_refs: list[str]
    estimated_cost_usd: float = 0.0
    expected_outcome: str = ""


class BudgetOffice:
    """Reserve before, commit after, release on every refusal path."""

    def __init__(self) -> None:
        self._res: dict[str, dict] = {}
        self._n = 0

    def reserve(self, principal: str, amount: float, ceiling: float) -> str:
        if amount > ceiling:
            raise BudgetRefusal(
                f"cost {amount} exceeds the principal ceiling {ceiling}",
                code="budget_exceeded")
        self._n += 1
        rid = f"res-{self._n:06d}"
        self._res[rid] = {"principal": principal, "amount": amount,
                          "state": "reserved"}
        return rid

    def commit(self, rid: str) -> None:
        self._res[rid]["state"] = "committed"

    def release(self, rid: str) -> None:
        if rid in self._res and self._res[rid]["state"] == "reserved":
            self._res[rid]["state"] = "released"

    def state(self, rid: str) -> str:
        return self._res[rid]["state"]


class AuthorityIssuer:
    """The one canonical issuance mechanism."""

    def __init__(
        self,
        *,
        signer: SigningProvider,
        policy_version: str,
        constitution_version: str,
        policy_evaluator: Callable[[Principal, Proposal], str],
        known_capabilities: set[str],
        known_targets: set[str],
        budget: Optional[BudgetOffice] = None,
        certificate_ttl_seconds: int = 900,
    ) -> None:
        self.signer = signer
        self.policy_version = policy_version
        self.constitution_version = constitution_version
        self.policy_evaluator = policy_evaluator
        self.known_capabilities = set(known_capabilities)
        self.known_targets = set(known_targets)
        self.budget = budget or BudgetOffice()
        self.ttl = certificate_ttl_seconds
        self._principals: dict[str, Principal] = {}
        self._issued: dict[str, AuthorizationCertificate] = {}
        self._n = 0

    # -- identity ---------------------------------------------------------
    def register_principal(self, p: Principal) -> Principal:
        self._principals[p.actor_id] = p
        return p

    def _principal(self, actor_id: str) -> Principal:
        p = self._principals.get(actor_id)
        if p is None:
            raise UnknownEntity(
                f"actor {actor_id!r} is not a registered principal; refusing",
                code="unknown_actor")
        return p

    # -- issuance ---------------------------------------------------------
    def issue(
        self,
        *,
        actor_id: str,
        proposal: Proposal,
        approval: Optional[ApprovalRecord] = None,
    ) -> AuthorizationCertificate:
        """Turn a proposal into a signed certificate, or refuse.

        Every refusal raises. There is no return value that means "denied",
        because a returned status can be ignored and a raised refusal cannot.
        """
        principal = self._principal(actor_id)

        # Unknown entities fail closed, before anything else is considered.
        if proposal.capability_id not in self.known_capabilities:
            raise UnknownEntity(
                f"capability {proposal.capability_id!r} is not in the capability "
                "registry", code="unknown_capability")
        if proposal.target_id not in self.known_targets:
            raise UnknownEntity(
                f"target {proposal.target_id!r} is not a registered target",
                code="unknown_target")
        if proposal.consequence_class not in CONSEQUENCE_ORDER:
            raise UnknownEntity(
                f"unknown consequence class {proposal.consequence_class!r}",
                code="unknown_consequence_class")

        # Exact scope: the capability must have been granted to THIS principal.
        # This is the defect that let draft.publish authority execute
        # funds.transfer.
        if proposal.capability_id not in principal.declared_capabilities:
            raise ScopeRefusal(
                f"principal {actor_id!r} holds {list(principal.declared_capabilities)!r} "
                f"and did not receive {proposal.capability_id!r}",
                code="capability_not_held")

        # Consequence ceiling: never issue above what the principal may reach.
        if (CONSEQUENCE_ORDER.index(proposal.consequence_class)
                > CONSEQUENCE_ORDER.index(principal.consequence_ceiling)):
            raise ScopeRefusal(
                f"consequence class {proposal.consequence_class!r} exceeds the "
                f"principal ceiling {principal.consequence_ceiling!r}",
                code="consequence_ceiling_exceeded")

        # Policy. REQUIRE_HUMAN has no path to a signature without an approval.
        verdict = self.policy_evaluator(principal, proposal)
        if verdict == "DENY":
            raise PolicyRefusal("policy denied the proposal", code="policy_denied")
        if verdict == "REQUIRE_HUMAN":
            if approval is None:
                raise ApprovalRequired(
                    "policy requires a human decision and no approval record was "
                    "supplied", code="approval_required")
            if approval.request_id != proposal.request_id:
                raise ApprovalRequired(
                    f"approval {approval.approval_id!r} is bound to request "
                    f"{approval.request_id!r}, not {proposal.request_id!r}",
                    code="approval_request_mismatch")
            if not approval.granted:
                raise PolicyRefusal(
                    f"human {approval.approver_id!r} refused", code="human_refused")
        elif verdict != "PERMIT":
            raise PolicyRefusal(f"unrecognised policy verdict {verdict!r}",
                                code="policy_unrecognised")

        # Budget reserved BEFORE the certificate exists, so a refusal after this
        # point has something to unwind.
        reservation = self.budget.reserve(
            actor_id, proposal.estimated_cost_usd, principal.budget_ceiling_usd)

        try:
            self._n += 1
            cert = build_certificate(
                request_id=proposal.request_id,
                authority_record_id=f"auth-{self._n:06d}",
                actor_id=principal.actor_id,
                organ_id=principal.organ_id,
                workload_identity=principal.workload_identity,
                legal_principal=principal.legal_principal,
                capability_id=proposal.capability_id,
                action_class=proposal.action_class,
                target_id=proposal.target_id,
                payload=proposal.payload,
                consequence_class=proposal.consequence_class,
                policy_version=self.policy_version,
                constitution_version=self.constitution_version,
                evidence_refs=proposal.evidence_refs,
                budget_reservation_id=reservation,
                consequence_ceiling=principal.budget_ceiling_usd,
                ttl_seconds=self.ttl,
                use_limit=1,
            )
            cert.algorithm = self.signer.algorithm
            cert.key_id = self.signer.key_id
            cert.signature = self.signer.sign(cert.signing_input())
        except Exception:
            self.budget.release(reservation)
            raise

        self._issued[cert.authority_record_id] = cert
        return cert
