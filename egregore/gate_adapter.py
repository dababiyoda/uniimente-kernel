"""Explicit bridge from an ADE candidate to the kernel Consequence Gate."""
from __future__ import annotations

from typing import Any, Callable, Mapping

from policy.engine import Proposal

from .contracts import CandidateProposal, ContractError, canonical_copy, require_text


def bind_for_gate(
    candidate: CandidateProposal,
    *,
    actor: str,
    legal_principal: str,
    context: Mapping[str, Any] | None = None,
) -> Proposal:
    """Bind a proposal to real accountability immediately before gate review."""
    if not isinstance(candidate, CandidateProposal):
        raise ContractError("candidate must be a CandidateProposal")
    candidate = CandidateProposal.from_dict(candidate.to_dict())
    actor = require_text("actor", actor)
    legal_principal = require_text("legal_principal", legal_principal)
    if legal_principal.casefold() == "uniimente":
        raise ContractError("UNIIMENTE may never be the legal principal")
    return Proposal(
        actor=actor,
        legal_principal=legal_principal,
        action_class=candidate.action_class,
        objective=candidate.objective,
        payload=canonical_copy(candidate.payload),
        target=candidate.target,
        consequence_class=candidate.consequence_class,
        evidence_confidence=candidate.confidence,
        evidence_refs=list(candidate.evidence_refs),
        estimated_cost_usd=candidate.estimated_cost_usd,
        requested_capability=candidate.requested_capability,
        expected_outcome=candidate.expected_outcome,
        context={
            **canonical_copy(dict(context or {})),
            "egregore_candidate_id": candidate.candidate_id,
            "egregore_execution_authority": "none",
        },
        proposal_id=f"egregore:{candidate.candidate_id}",
    )


def submit_through_gate(
    gate: Any,
    candidate: CandidateProposal,
    *,
    actor: str,
    legal_principal: str,
    executor: Callable[[Proposal], dict],
    approver: Callable[[Proposal, Any], Any] | None = None,
    standing_grant: dict | None = None,
    context: Mapping[str, Any] | None = None,
) -> Any:
    """Submit to the pre-existing gate; never call an executor directly."""
    if not hasattr(gate, "run"):
        raise ContractError("gate must provide run()")
    proposal = bind_for_gate(
        candidate,
        actor=actor,
        legal_principal=legal_principal,
        context=context,
    )
    return gate.run(
        proposal,
        executor=executor,
        approver=approver,
        standing_grant=standing_grant,
    )
