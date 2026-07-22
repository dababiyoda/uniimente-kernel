"""Phase Zero -> Advantage Foundry intake boundary.

Canonical Opportunity Packets and Venture Assessments remain untrusted data.
This adapter validates both contracts, requires a GO recommendation, preserves
human-approval and no-execution boundaries, rejects unresolved capping cases,
and requires explicit supplemental commercial facts rather than fabricating
fields the upstream contracts do not contain.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Mapping

import jsonschema

from .advantage import AdvantageRefused, OpportunitySpec

KERNEL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass(frozen=True)
class FoundryIntakeSupplement:
    buyer: str
    beneficiary: str
    recurring_transaction: str
    accepted_artifact: str
    external_consequence: str
    lawful_path: str
    legal_operator: str
    trapped_value_usd: float
    human_approval_record_hash: str
    constraints: tuple[str, ...] = ()
    prohibitions: tuple[str, ...] = ()

    def validate(self) -> None:
        required = (
            self.buyer, self.beneficiary, self.recurring_transaction,
            self.accepted_artifact, self.external_consequence, self.lawful_path,
            self.legal_operator, self.human_approval_record_hash,
        )
        if any(not value for value in required):
            raise AdvantageRefused("Foundry intake supplement is incomplete")
        if self.legal_operator == "UNIIMENTE":
            raise AdvantageRefused("UNIIMENTE is never the legal operator")
        if self.trapped_value_usd < 0:
            raise AdvantageRefused("trapped value cannot be negative")
        _require_hash(self.human_approval_record_hash, "human_approval_record_hash")


def _schema(filename: str) -> dict:
    with open(os.path.join(KERNEL_ROOT, "contracts", filename), encoding="utf-8") as handle:
        return json.load(handle)


def _validate(payload: Mapping[str, Any], filename: str, name: str) -> None:
    try:
        jsonschema.validate(dict(payload), _schema(filename), format_checker=jsonschema.FormatChecker())
    except jsonschema.ValidationError as exc:
        raise AdvantageRefused(f"{name} violates its canonical contract: {exc.message}") from exc


def _require_text(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AdvantageRefused(f"{key} is required for Foundry intake")
    return value.strip()


def _require_hash(value: Any, field_name: str) -> str:
    value = str(value or "")
    if not value.startswith("sha256:") or len(value) != 71:
        raise AdvantageRefused(f"{field_name} must be a canonical sha256 reference")
    return value


def opportunity_from_canonical(
    packet: Mapping[str, Any],
    assessment: Mapping[str, Any],
    supplement: FoundryIntakeSupplement,
) -> OpportunitySpec:
    """Convert validated Phase Zero data into a governing transaction.

    No field is inferred from a model score. Missing commercial facts require an
    explicit supplement bound to a human approval record.
    """
    if not isinstance(packet, Mapping) or not isinstance(assessment, Mapping):
        raise AdvantageRefused("packet and assessment must be objects")
    _validate(packet, "opportunity-packet.schema.json", "Opportunity Packet")
    _validate(assessment, "venture-assessment.schema.json", "Venture Assessment")
    supplement.validate()

    if assessment["packet_id"] != packet["packet_id"]:
        raise AdvantageRefused("assessment does not belong to the Opportunity Packet")
    if assessment["verdict"] != "go":
        raise AdvantageRefused("only a GO assessment may enter the Advantage Foundry")
    if assessment.get("requires_human_approval") is not True:
        raise AdvantageRefused("human approval boundary is mandatory")
    if assessment.get("execution_authority") is not False:
        raise AdvantageRefused("Venture Assessment must carry zero execution authority")
    capping = tuple((assessment.get("adversarial_cases") or {}).get("capping_cases") or ())
    if capping:
        raise AdvantageRefused(f"unresolved capping cases block Foundry intake: {list(capping)}")

    pain_owner = _require_text(packet, "pain_owner")
    budget_owner = _require_text(packet, "budget_owner")
    mandate_actor = _require_text(packet, "mandate_capable_actor")
    packet_evidence = tuple(str(ref) for ref in packet.get("evidence_refs") or ())
    assessment_evidence = tuple(
        str(ref) for ref in ((assessment.get("evidence_state") or {}).get("evidence_refs") or ())
    )
    evidence_refs = tuple(dict.fromkeys(
        packet_evidence + assessment_evidence + (supplement.human_approval_record_hash,)
    ))
    if not evidence_refs:
        raise AdvantageRefused("Foundry intake requires external evidence")
    for ref in evidence_refs:
        _require_hash(ref, "evidence reference")

    assessment_id = _require_text(assessment, "assessment_id")
    opportunity = OpportunitySpec(
        opportunity_id=f"{packet['packet_id']}:{assessment_id}",
        buyer=supplement.buyer,
        beneficiary=supplement.beneficiary,
        pain_owner=pain_owner,
        budget_owner=budget_owner,
        mandate_actor=mandate_actor,
        recurring_transaction=supplement.recurring_transaction,
        broken_state=_require_text(packet, "observed_failure"),
        trapped_value_usd=float(supplement.trapped_value_usd),
        accepted_artifact=supplement.accepted_artifact,
        external_consequence=supplement.external_consequence,
        lawful_path=supplement.lawful_path,
        evidence_refs=evidence_refs,
        legal_operator=supplement.legal_operator,
        constraints=tuple(dict.fromkeys(
            supplement.constraints + (
                f"packet_created_by={packet['created_by']}",
                f"assessment_assessed_by={assessment['assessed_by']}",
                f"human_approval_record_hash={supplement.human_approval_record_hash}",
                f"governing_bottleneck={packet['governing_bottleneck']}",
                f"cheapest_decisive_test={packet['cheapest_decisive_test']}",
            )
        )),
        prohibitions=tuple(dict.fromkeys(
            supplement.prohibitions + tuple(str(risk) for risk in packet.get("key_risks") or ())
        )),
    )
    opportunity.validate()
    return opportunity
