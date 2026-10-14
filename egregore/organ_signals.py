"""Organ outputs as experience: canonical organ contracts -> SignalEnvelope observations (directive section 8).

DALEOBANKS (perception) and WealthMachineIntelligence (assessment) already speak canonical kernel
contracts through ``adapters/``. This module is the next ring: it turns a schema-valid canonical
``opportunity-packet`` or ``venture-assessment`` into typed observations the world model can
integrate, so organ output stops being a dead record and starts changing goal state. It lives in
``egregore/`` rather than ``adapters/`` because the pinned boundary package that organs install
ships ``adapters/`` and must not depend on ``egregore``.

Rules (same as ``adapters/README.md``): declared mapping, information lost and added, assumptions;
no fabricated fields; identity from transport, never payload; no authority inflation.

* Trust is ``attributed`` only when the caller passes the result of
  ``adapters.bridge_transport.verify_headers`` together with the raw ``body`` it verified: the
  transport identity must be the producing organ, the body's digest must equal the verified digest,
  and re-adapting the body must yield the same canonical identifier. Otherwise ``untrusted``. Never
  ``verified``: an HMAC proves possession of a shared key, not an isolated identity. This is a
  consistency check on in-process inputs, not a security boundary: an in-process caller can build an
  envelope directly, which is why trust is attributed and never verified.
* Evidence types are honest. A WMI verdict and opportunity score are typed ``simulation``
  (they establish a hypothesis: the engine's market inputs are fixed constants), committee cases
  ``adversarial_review``; DALEOBANKS synthesis fields are untyped. None of it can clear a
  ``market_demand`` gate, which only an ``empirical_experiment`` outcome can.
* Signal identity includes content, so a corrected packet is a new signal, never a silent overwrite.
* Arrays become ``<name>_count`` plus ``<name>.<i>`` because observations are scalars.
"""
from __future__ import annotations

from typing import Any, Mapping

import hashlib
import json

from adapters import daleobanks_opportunity as _dop
from adapters import wealthmachine_assessment as _wva
from adapters.contract_validation import validate_contract
from adapters.daleobanks_opportunity import AdaptationResult

from .contracts import ContractError, SignalEnvelope, digest

CONFIDENCE = 0.5   # neither canonical contract carries a confidence; this declared constant is added information

PACKET_FIELD_MAPPING = {
    "subject": "opportunity:<packet_id>",
    "observed_failure|pain_owner|budget_owner|payer|governing_bottleneck|cheapest_decisive_test|smallest_intervention|"
    "possible_business_form|missing_proof|existing_workaround|mandate_capable_actor|wedge_to_control_path":
        "same-named attribute, string value, untyped (organ synthesis establishes nothing)",
    "capital_requirement_usd": "same-named attribute, number, untyped",
    "affected_actors": "affected_actor_count (deterministic_computation) + affected_actor.<i> (untyped)",
    "key_risks": "key_risk_count (deterministic_computation) + key_risk.<i> (untyped)",
    "evidence_refs": "evidence_ref_count (deterministic_computation) and the envelope's evidence_refs",
}
ASSESSMENT_FIELD_MAPPING = {
    "subject": "opportunity:<packet_id> (the assessment's packet), attributes namespaced wmi.*",
    "verdict": "wmi.recommended_verdict, typed simulation (establishes hypothesis)",
    "opportunity_score": "wmi.opportunity_score, typed simulation (establishes hypothesis)",
    "adversarial_cases.<name>": "wmi.case.<name>, typed adversarial_review (establishes objection)",
    "adversarial_cases.capping_cases": "wmi.capping_case_count + wmi.capping_case.<i>, adversarial_review",
    "structured_reasons": "wmi.reason_count + wmi.reason.<i>, untyped",
    "requires_human_approval": "wmi.requires_human_approval, deterministic_computation, confidence 1.0",
    "evidence_state.confidence": "observation confidence when present",
}
INFORMATION_LOST = (
    "array semantics (flattened to indexed scalar attributes)",
    "schema_version (kept on the envelope payload, not as an observation)",
    "everything the wire->canonical adapters already drop (see adapters/*.py INFORMATION_LOST)",
)
INFORMATION_ADDED = (
    "subject key opportunity:<packet_id>",
    f"confidence constant {CONFIDENCE} when the contract carries none",
    "content digest of the canonical object as an evidence reference and in the signal identity",
    "epistemic method typing per attribute (declared above)",
)
ASSUMPTIONS = (
    "a verified transport result bound to the raw body it verified is the only basis for attributed trust",
    "WMI scores are simulations over constant market inputs, not measurements",
)


def _validated(obj: Mapping[str, Any], contract: str) -> None:
    if not isinstance(obj, Mapping):
        raise ContractError(f"{contract} must be an object")
    try:
        validate_contract(dict(obj), contract)
    except ValueError as exc:   # one failure type for callers; the contract message is kept
        raise ContractError(str(exc)) from exc


def _trust(transport: Mapping[str, Any] | None, body: bytes | None, *, organ: str, canonical_id: str, kind: str) -> str:
    """``attributed`` only for a verify_headers result bound to the body it verified; else ``untrusted``."""
    if transport is None:
        if body is not None:
            raise ContractError("a body without its verified transport result proves nothing; pass both or neither")
        return "untrusted"
    if transport.get("signed") != "true" or not transport.get("body_digest"):
        raise ContractError("transport must be the verify_headers result for this body")
    if transport.get("identity") != organ:
        raise ContractError(f"transport identity {transport.get('identity')!r} is not the producing organ {organ!r}")
    if not isinstance(body, (bytes, bytearray)):
        raise ContractError("attributed trust needs the raw body bytes that verify_headers verified")
    if hashlib.sha256(bytes(body)).hexdigest() != transport["body_digest"]:
        raise ContractError("the body does not match the verified transport digest")
    try:
        wire = json.loads(bytes(body))
        if kind == "venture-assessment":
            adapted_id = _wva.adapt(wire, transport_identity=organ)["assessment_id"]
        else:
            adapted_id = _dop.adapt(wire, transport_identity=organ).partial.get("packet_id")
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise ContractError(f"the verified body does not adapt: {exc}") from exc
    if adapted_id != canonical_id:
        raise ContractError("the canonical object was not adapted from the verified body")
    return "attributed"


def _flatten(prefix: str, items: list, method_count: str = "deterministic_computation") -> list[dict[str, Any]]:
    out = [{"attribute": f"{prefix}_count", "value": len(items), "confidence": 1.0, "method": method_count}]
    out += [{"attribute": f"{prefix}.{i}", "value": v, "confidence": CONFIDENCE} for i, v in enumerate(items)
            if isinstance(v, (str, int, float, bool)) or v is None]
    return out


def _envelope(kind: str, obj: Mapping[str, Any], *, ident: str, source: str, observed_at: str, subject: str,
              attributes: list[dict[str, Any]], extra_refs: list[str], organ: str,
              transport: Mapping[str, Any] | None, body: bytes | None = None) -> SignalEnvelope:
    content = digest({"kind": f"egregore-organ-{kind}", "object": dict(obj)})
    observations = [{"subject": subject, **a} for a in attributes]
    return SignalEnvelope.build(
        source=source, source_event_id=f"{kind}:{ident}:{content[7:23]}", observed_at=observed_at,
        payload={"observations": observations, "domain": "venture", "tags": [kind, f"organ:{organ}"],
                 "schema_version": obj.get("schema_version")},
        evidence_refs=tuple(list(extra_refs) + [content]),
        trust_level=_trust(transport, body, organ=organ, canonical_id=ident,
                           kind="venture-assessment" if kind == "venture-assessment" else "opportunity-packet"))


def packet_signal(packet: Mapping[str, Any], *, transport: Mapping[str, Any] | None = None,
                  body: bytes | None = None) -> SignalEnvelope:
    """A schema-valid canonical OpportunityPacket as experience. Partial translations are refused."""
    if isinstance(packet, AdaptationResult):
        raise ContractError("an unresolved translation is not a packet; use unresolved_signal")
    _validated(packet, "opportunity-packet")
    attrs: list[dict[str, Any]] = []
    for name in ("observed_failure", "pain_owner", "budget_owner", "payer", "governing_bottleneck",
                 "cheapest_decisive_test", "smallest_intervention", "possible_business_form", "missing_proof",
                 "existing_workaround", "mandate_capable_actor", "wedge_to_control_path", "capital_requirement_usd"):
        if name in packet:
            attrs.append({"attribute": name, "value": packet[name], "confidence": CONFIDENCE})
    attrs += _flatten("affected_actor", list(packet.get("affected_actors", [])))
    attrs += _flatten("key_risk", list(packet.get("key_risks", [])))
    attrs.append({"attribute": "evidence_ref_count", "value": len(packet.get("evidence_refs", [])), "confidence": 1.0,
                  "method": "deterministic_computation"})
    return _envelope("opportunity-packet", packet, ident=packet["packet_id"], source=packet["created_by"],
                     observed_at=packet["created_at"], subject=f"opportunity:{packet['packet_id']}", attributes=attrs,
                     extra_refs=list(packet.get("evidence_refs", [])), organ="daleobanks", transport=transport, body=body)


def assessment_signal(assessment: Mapping[str, Any], *, transport: Mapping[str, Any] | None = None,
                  body: bytes | None = None) -> SignalEnvelope:
    """A schema-valid canonical VentureAssessment as experience, typed as the hypothesis it is."""
    _validated(assessment, "venture-assessment")
    conf = float((assessment.get("evidence_state") or {}).get("confidence", CONFIDENCE))
    attrs: list[dict[str, Any]] = [{"attribute": "wmi.recommended_verdict", "value": assessment["verdict"],
                                    "confidence": conf, "method": "simulation"}]
    if "opportunity_score" in assessment:
        attrs.append({"attribute": "wmi.opportunity_score", "value": assessment["opportunity_score"], "confidence": conf,
                      "method": "simulation"})
    cases = dict(assessment.get("adversarial_cases", {}))
    capping = list(cases.pop("capping_cases", []))
    for name, argument in sorted(cases.items()):
        attrs.append({"attribute": f"wmi.case.{name}", "value": argument, "confidence": conf, "method": "adversarial_review"})
    attrs += [{**a, "method": "adversarial_review"} for a in _flatten("wmi.capping_case", capping)]
    attrs += _flatten("wmi.reason", list(assessment.get("structured_reasons", [])))
    attrs.append({"attribute": "wmi.requires_human_approval", "value": bool(assessment["requires_human_approval"]),
                  "confidence": 1.0, "method": "deterministic_computation"})
    refs = list((assessment.get("evidence_state") or {}).get("evidence_refs", []))
    return _envelope("venture-assessment", assessment, ident=assessment["assessment_id"], source=assessment["assessed_by"],
                     observed_at=assessment["assessed_at"], subject=f"opportunity:{assessment['packet_id']}",
                     attributes=attrs, extra_refs=refs, organ="wealthmachine", transport=transport, body=body)


def unresolved_signal(result: AdaptationResult, *, transport: Mapping[str, Any] | None = None,
                  body: bytes | None = None) -> SignalEnvelope:
    """A translation that could not complete is itself knowledge: which underwriting facts are missing."""
    if not isinstance(result, AdaptationResult) or result.resolved:
        raise ContractError("unresolved_signal takes an unresolved AdaptationResult")
    partial = result.partial
    if not partial.get("packet_id") or not partial.get("created_at") or not partial.get("created_by"):
        raise ContractError("the partial translation lacks identity or observation time")
    attrs = [{"attribute": f"unresolved.{f}", "value": True, "confidence": 1.0, "method": "deterministic_computation"}
             for f in sorted(result.unresolved)]
    attrs.append({"attribute": "unresolved_count", "value": len(result.unresolved), "confidence": 1.0,
                  "method": "deterministic_computation"})
    return _envelope("opportunity-gap", {"partial": partial, "unresolved": sorted(result.unresolved)},
                     ident=partial["packet_id"], source=partial["created_by"], observed_at=partial["created_at"],
                     subject=f"opportunity:{partial['packet_id']}", attributes=attrs,
                     extra_refs=list(partial.get("evidence_refs", [])), organ="daleobanks", transport=transport, body=body)
