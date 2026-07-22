"""Contract-version adapter: wire OpportunityPacket v1.1 -> canonical
OpportunityPacket (contracts/opportunity-packet.schema.json).

Doctrine (ADAPTERS): every translation declares its field mapping, what
information is lost, what is added, and every assumption made. Missing
required canonical fields are returned as explicit unresolved fields —
the adapter NEVER fabricates underwriting facts (budget_owner,
governing_bottleneck, ...) the periphery did not observe. Resolution of
unresolved fields is a separate, attributed act by an authorized actor.

Identity rule: created_by comes from the VERIFIED transport identity,
never from the payload. A packet cannot name its own author.

Source contract:  contracts/wire-opportunity-packet.schema.json
                  (DALEOBANKS services/venture_protocol.py, schema 1.1)
Dest contract:    contracts/opportunity-packet.schema.json
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

KERNEL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPIFFE_BY_TRANSPORT_IDENTITY = {
    "daleobanks": "spiffe://uniimente.internal/organ/daleobanks",
    "wealthmachine": "spiffe://uniimente.internal/organ/wealthmachine",
    "kernel": "spiffe://uniimente.internal/organ/constitutional-controller",
}

# Canonical fields the wire packet cannot supply. The wire protocol carries a
# media-side signal; the canonical contract demands underwriting answers. The
# gap is the adapter's honest output, not something to fill with guesses.
FIELD_MAPPING = {
    "packet_id": "id (regenerated as UUIDv5 over the wire id when not already a UUID)",
    "schema_version": "schema_version (pass-through)",
    "created_by": "TRANSPORT identity -> spiffe id (never from payload)",
    "created_at": "created_at (pass-through; adapter timestamp if absent)",
    "observed_failure": "observed_pain, falling back to core_thesis",
    "affected_actors": "[audience, customer_segment] (non-empty entries)",
    "pain_owner": "audience (ASSUMPTION: the described audience owns the pain)",
    "budget_owner": "buyer_type if non-empty, else UNRESOLVED",
    "payer": "buyer_type if non-empty (same observation as budget_owner)",
    "existing_workaround": "not carried on the wire -> omitted (optional)",
    "missing_proof": "derived: 'willingness to pay' when evidence list is empty -> else omitted",
    "governing_bottleneck": "not carried on the wire -> UNRESOLVED",
    "smallest_intervention": "smallest_validation_action",
    "cheapest_decisive_test": "smallest_validation_action if non-empty, else UNRESOLVED",
    "possible_business_form": "possible_offer",
    "key_risks": "risk_flags (pass-through, may be empty)",
    "evidence_refs": "sha256 of each wire evidence string (raw strings preserved in the mapping record)",
}
INFORMATION_LOST = (
    "source", "source_ref", "signal_type", "cultural_context", "language",
    "urgency", "monetization_paths", "confidence", "status",
)
INFORMATION_ADDED = (
    "created_by (from verified transport identity)",
    "evidence_refs hashes (content-addressed form of wire evidence strings)",
)


class AdapterError(ValueError):
    """Translation refused. Fails closed; nothing partial enters the kernel."""


def _uuid_for(wire_id: str) -> str:
    try:
        return str(uuid.UUID(wire_id))
    except ValueError:
        # Deterministic: the same wire id always maps to the same canonical id,
        # so idempotent redelivery cannot mint a second packet.
        return str(uuid.uuid5(uuid.NAMESPACE_URL,
                              f"https://uniimente.internal/wire-packet/{wire_id}"))


def _sha256(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


@dataclass
class AdaptationResult:
    """The honest output of a translation attempt."""
    canonical: dict | None            # complete canonical packet, or None
    unresolved: list[str]             # canonical fields awaiting an authorized answer
    partial: dict                     # everything that DID translate
    mapping: dict = field(default_factory=lambda: dict(FIELD_MAPPING))
    information_lost: tuple = INFORMATION_LOST
    information_added: tuple = INFORMATION_ADDED
    assumptions: tuple = (
        "pain_owner == wire audience",
        "budget_owner/payer == wire buyer_type when stated",
    )
    wire_evidence: list[str] = field(default_factory=list)  # raw strings behind evidence_refs

    @property
    def resolved(self) -> bool:
        return self.canonical is not None


def _validate_wire(wire: dict) -> None:
    import jsonschema
    with open(os.path.join(KERNEL_ROOT, "contracts",
                           "wire-opportunity-packet.schema.json")) as f:
        schema = json.load(f)
    try:
        jsonschema.validate(wire, schema)
    except jsonschema.ValidationError as exc:
        raise AdapterError(f"wire packet violates its own contract: {exc.message}") from exc


def _validate_canonical(packet: dict) -> None:
    import jsonschema
    with open(os.path.join(KERNEL_ROOT, "contracts",
                           "opportunity-packet.schema.json")) as f:
        schema = json.load(f)
    try:
        jsonschema.validate(packet, schema)
    except jsonschema.ValidationError as exc:
        raise AdapterError(f"adapted packet violates the canonical contract: {exc.message}") from exc


def adapt(wire: dict, *, transport_identity: str) -> AdaptationResult:
    """Translate a validated wire packet. Untranslatable required fields come
    back in `unresolved`; the caller routes them to an authorized resolver."""
    _validate_wire(wire)
    spiffe = SPIFFE_BY_TRANSPORT_IDENTITY.get(transport_identity)
    if spiffe is None:
        raise AdapterError(f"unknown transport identity {transport_identity!r}; "
                           "identity comes from verified transport, never the payload")

    partial: dict = {
        "packet_id": _uuid_for(wire["id"]),
        "schema_version": wire["schema_version"],
        "created_by": spiffe,
        "created_at": wire.get("created_at")
        or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "observed_failure": wire.get("observed_pain") or wire.get("core_thesis", ""),
        "key_risks": list(wire.get("risk_flags", [])),
        "evidence_refs": [_sha256(e) for e in wire.get("evidence", [])],
    }
    actors = [a for a in (wire.get("audience", ""), wire.get("customer_segment", "")) if a]
    if actors:
        partial["affected_actors"] = actors
    if wire.get("audience"):
        partial["pain_owner"] = wire["audience"]
    if wire.get("buyer_type"):
        partial["budget_owner"] = wire["buyer_type"]
        partial["payer"] = wire["buyer_type"]
    if wire.get("smallest_validation_action"):
        partial["smallest_intervention"] = wire["smallest_validation_action"]
        partial["cheapest_decisive_test"] = wire["smallest_validation_action"]
    if wire.get("possible_offer"):
        partial["possible_business_form"] = wire["possible_offer"]
    if not wire.get("evidence"):
        partial["missing_proof"] = "no evidence attached at source; willingness to pay unshown"

    required = ("packet_id", "schema_version", "created_by", "created_at",
                "observed_failure", "pain_owner", "budget_owner",
                "governing_bottleneck", "cheapest_decisive_test", "key_risks")
    unresolved = [f for f in required if f not in partial or partial[f] in ("", None)]

    if unresolved:
        return AdaptationResult(canonical=None, unresolved=unresolved, partial=partial,
                                wire_evidence=list(wire.get("evidence", [])))
    _validate_canonical(partial)
    return AdaptationResult(canonical=partial, unresolved=[], partial=partial,
                            wire_evidence=list(wire.get("evidence", [])))


def resolve(result: AdaptationResult, answers: dict, *, resolved_by: str) -> dict:
    """Complete an unresolved translation with attributed answers. Only the
    named unresolved fields may be supplied — the resolver cannot rewrite
    what the wire already said."""
    if result.resolved:
        raise AdapterError("nothing to resolve; the packet is already canonical")
    if not resolved_by.startswith("spiffe://uniimente.internal/"):
        raise AdapterError("resolution requires an institutional identity")
    extra = set(answers) - set(result.unresolved)
    if extra:
        raise AdapterError(f"answers outside the unresolved set refused: {sorted(extra)}")
    missing = [f for f in result.unresolved if not answers.get(f)]
    if missing:
        raise AdapterError(f"unresolved fields still unanswered: {missing}")
    packet = {**result.partial, **answers}
    _validate_canonical(packet)
    return packet
