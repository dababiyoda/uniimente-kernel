"""Validation boundary for WealthMachine -> Foundry underwriting envelopes."""
from __future__ import annotations

from typing import Any, Mapping

from .contracts import FoundryError, OpportunitySpec

UNDERWRITING_SCHEMA_VERSION = "0.1"


def _require_text(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise FoundryError(f"{key} is required")
    return value.strip()


def _require_sha256(payload: Mapping[str, Any], key: str) -> str:
    value = _require_text(payload, key)
    if not value.startswith("sha256:") or len(value) != 71:
        raise FoundryError(f"{key} must be a canonical sha256 reference")
    return value


def opportunity_from_underwriting_wire(payload: Mapping[str, Any]) -> OpportunitySpec:
    """Convert a ready, proposal-only underwriting envelope into Foundry data.

    The wire is untrusted. A model score, a `go` recommendation, or a claimed
    readiness bit can never compensate for missing commercial facts, blocking
    cases, absent evidence, missing human approval provenance, or a widened
    execution boundary.
    """
    if not isinstance(payload, Mapping):
        raise FoundryError("underwriting payload must be an object")
    if payload.get("schema_version") != UNDERWRITING_SCHEMA_VERSION:
        raise FoundryError("unsupported underwriting schema version")
    if payload.get("source_organ") != "WealthMachineIntelligence":
        raise FoundryError("unexpected source organ")
    if payload.get("requires_human_approval") is not True:
        raise FoundryError("human approval boundary is mandatory")
    if payload.get("execution_authority") != "none":
        raise FoundryError("underwriting envelopes carry no execution authority")
    if payload.get("ready_for_foundry") is not True:
        raise FoundryError("underwriting envelope is not ready for Foundry intake")
    if tuple(payload.get("missing_fields") or ()):
        raise FoundryError("underwriting envelope still has missing fields")
    if tuple(payload.get("blocking_reasons") or ()):
        raise FoundryError("underwriting envelope still has blocking reasons")
    if payload.get("go_no_go") != "go":
        raise FoundryError("only a go recommendation may enter architecture compilation")

    packet_id = _require_text(payload, "opportunity_packet_id")
    assessment_id = _require_text(payload, "assessment_id")
    packet_digest = _require_sha256(payload, "packet_digest")
    assessment_digest = _require_sha256(payload, "assessment_digest")
    approval_record_hash = _require_sha256(payload, "human_approval_record_hash")
    observed_pain = str(payload.get("observed_pain") or "").strip()
    core_thesis = str(payload.get("core_thesis") or "").strip()
    if not observed_pain and not core_thesis:
        raise FoundryError("observed pain or core thesis is required")

    evidence = payload.get("evidence_refs")
    if not isinstance(evidence, (list, tuple)) or not evidence:
        raise FoundryError("evidence_refs must be a non-empty sequence")
    evidence_refs = tuple(str(ref).strip() for ref in evidence if str(ref).strip())
    if not evidence_refs:
        raise FoundryError("evidence_refs cannot be empty")

    trapped_value = payload.get("trapped_value_usd")
    try:
        trapped_value = float(trapped_value)
    except (TypeError, ValueError) as exc:
        raise FoundryError("trapped_value_usd must be numeric") from exc
    if trapped_value < 0:
        raise FoundryError("trapped_value_usd cannot be negative")

    legal_operator = _require_text(payload, "legal_operator")
    if legal_operator == "UNIIMENTE":
        raise FoundryError("UNIIMENTE is never the legal operator")

    opportunity = OpportunitySpec(
        opportunity_id=f"{packet_id}:{assessment_id}",
        buyer=_require_text(payload, "buyer"),
        beneficiary=_require_text(payload, "beneficiary"),
        pain_owner=_require_text(payload, "pain_owner"),
        budget_owner=_require_text(payload, "budget_owner"),
        recurring_transaction=_require_text(payload, "recurring_transaction"),
        broken_state=observed_pain or core_thesis,
        trapped_value_usd=trapped_value,
        accepted_artifact=_require_text(payload, "accepted_artifact"),
        external_consequence=_require_text(payload, "external_consequence"),
        lawful_path=_require_text(payload, "lawful_path"),
        evidence_refs=evidence_refs,
        legal_operator=legal_operator,
        constraints=(
            f"packet_digest={packet_digest}",
            f"assessment_digest={assessment_digest}",
            f"human_approval_record_hash={approval_record_hash}",
            f"risk_level={str(payload.get('risk_level') or 'unknown')}",
            f"legal_readiness={str(payload.get('legal_readiness') or 'unknown')}",
        ),
    )
    opportunity.validate()
    return opportunity


__all__ = ["UNDERWRITING_SCHEMA_VERSION", "opportunity_from_underwriting_wire"]
