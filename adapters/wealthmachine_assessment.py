"""Contract-version adapter: wire VentureAssessment v1.1 -> canonical
VentureAssessment (contracts/venture-assessment.schema.json).

Same discipline as the packet adapter: declared mapping, declared loss,
no fabrication, identity from verified transport only. The wire case list
maps one-to-one onto the canonical adversarial_cases object (the case
names already agree across all three repositories); severe unresolved
against-cases become capping_cases exactly as the organs compute them.

Authority rule: requires_human_approval is const true and
execution_authority is const false in the canonical contract. The adapter
asserts them; it cannot be argued out of them by any payload.

Source contract:  contracts/wire-venture-assessment.schema.json
Dest contract:    contracts/venture-assessment.schema.json
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone

from adapters.daleobanks_opportunity import (
    AdapterError,
    SPIFFE_BY_TRANSPORT_IDENTITY,
    _uuid_for,
)

KERNEL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CANONICAL_CASE_FIELDS = ("bull", "bear", "fraud_manipulation", "incumbent_response",
                         "adoption_friction", "do_nothing", "opportunity_cost")
SEVERE = "high"

FIELD_MAPPING = {
    "assessment_id": "id (regenerated as UUIDv5 when not already a UUID; minted if absent)",
    "packet_id": "opportunity_packet_id (UUIDv5-normalized with the packet adapter's rule)",
    "schema_version": "schema_version (pass-through; 1.1 default)",
    "assessed_by": "TRANSPORT identity -> spiffe id (never from payload)",
    "assessed_at": "created_at (adapter timestamp if absent)",
    "verdict": "go_no_go",
    "opportunity_score": "opportunity_score (pass-through)",
    "adversarial_cases": "cases[] arguments keyed by case name; capping_cases = severe unresolved against-cases",
    "structured_reasons": "reasons (pass-through)",
    "evidence_state.confidence": "market_alignment is NOT confidence; omitted unless caller supplies evidence",
    "requires_human_approval": "const true (asserted, not negotiated)",
    "execution_authority": "const false (asserted, not negotiated)",
}
INFORMATION_LOST = (
    "market_alignment", "expected_roi", "risk_level", "legal_readiness",
    "product_hypothesis", "pricing_hypothesis", "validation_plan",
    "monetization_paths", "recommended_next_action",
)


def _validate(payload: dict, schema_file: str, kind: str) -> None:
    import jsonschema
    with open(os.path.join(KERNEL_ROOT, "contracts", schema_file)) as f:
        schema = json.load(f)
    try:
        jsonschema.validate(payload, schema)
    except jsonschema.ValidationError as exc:
        raise AdapterError(f"{kind} violates its contract: {exc.message}") from exc


def adapt(wire: dict, *, transport_identity: str,
          evidence_state: dict | None = None) -> dict:
    """Translate a wire assessment into the canonical form. Raises
    AdapterError on any contract violation on either side."""
    _validate(wire, "wire-venture-assessment.schema.json", "wire assessment")
    spiffe = SPIFFE_BY_TRANSPORT_IDENTITY.get(transport_identity)
    if spiffe is None:
        raise AdapterError(f"unknown transport identity {transport_identity!r}; "
                           "identity comes from verified transport, never the payload")
    if wire.get("requires_human_approval") is not True:
        raise AdapterError("requires_human_approval must be true on the wire; refusing")

    cases = wire.get("cases", [])
    adversarial: dict = {}
    for c in cases:
        name = c["case"]
        if name in CANONICAL_CASE_FIELDS and name not in adversarial:
            adversarial[name] = c["argument"]
    capping = [c["case"] for c in cases
               if c["stance"] == "against" and c["severity"] == SEVERE
               and not c.get("resolved")]
    if capping:
        adversarial["capping_cases"] = capping
    # The canonical committee minimum: bull, bear, do_nothing must exist. The
    # wire committee always emits them; their absence means a foreign or
    # truncated payload and the translation refuses rather than invents.
    missing = [n for n in ("bull", "bear", "do_nothing") if n not in adversarial]
    if missing:
        raise AdapterError(f"wire assessment lacks required committee cases {missing}; "
                           "the adapter does not invent adversarial arguments")

    raw_id = wire.get("id") or ""
    try:
        assessment_id = str(uuid.UUID(raw_id)) if raw_id else str(uuid.uuid4())
    except ValueError:
        assessment_id = str(uuid.uuid5(uuid.NAMESPACE_URL,
                                       f"https://uniimente.internal/wire-assessment/{raw_id}"))

    canonical = {
        "assessment_id": assessment_id,
        "packet_id": _uuid_for(wire["opportunity_packet_id"]),
        "schema_version": wire.get("schema_version", "1.1"),
        "assessed_by": spiffe,
        "assessed_at": wire.get("created_at")
        or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "verdict": wire["go_no_go"],
        "adversarial_cases": adversarial,
        "structured_reasons": list(wire.get("reasons", [])),
        "requires_human_approval": True,
        "execution_authority": False,
    }
    if "opportunity_score" in wire:
        canonical["opportunity_score"] = wire["opportunity_score"]
    if evidence_state is not None:
        canonical["evidence_state"] = evidence_state
    _validate(canonical, "venture-assessment.schema.json", "adapted assessment")
    return canonical
