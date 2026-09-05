"""Mission Resolution Router: choose what to do before choosing an organization.

UNIIMENTE is not an organization compiler. It is the persistent institution
that decides whether a discrepancy deserves work and, if so, which smallest
sufficient mechanism should carry it.

This module is deliberately a selector only. It compares no-action, direct
capabilities, single tools/models, existing workflows, the protected static
DurableWorkflow, fixed specialists, an OMNIMORPH organization hypothesis and
human escalation. It invokes none of them, grants nothing, and cannot cross
the Consequence Gate.

All scores are declared hypotheses until they are compared with executed
episodes. A content digest binds the record; it does not make the record true
or authorized.
"""
from __future__ import annotations

import copy
import json
import math
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import UUID, uuid5

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from omnimorph.organization_compiler import content_digest


_SCHEMA = Path(__file__).resolve().parents[1] / "contracts" / "mission-resolution.schema.json"
_NAMESPACE = UUID("d5b25ef8-c87e-56fb-a9eb-2a9cf2a8af90")

RESOLUTION_CLASSES = (
    "no_action",
    "direct_capability",
    "single_model_or_tool",
    "existing_workflow",
    "static_durable_workflow",
    "fixed_specialist_configuration",
    "compiled_temporary_organization",
    "human_escalation",
)
EVIDENCE_MATURITY = ("NONE", "DECLARED", "TESTED", "VERIFIED")

# Static remains the protected tie winner. The order is a tie-break only; it
# never rescues an ineligible candidate.
_TIE_PRIORITY = {
    "static_durable_workflow": 0,
    "direct_capability": 1,
    "single_model_or_tool": 2,
    "existing_workflow": 3,
    "fixed_specialist_configuration": 4,
    "compiled_temporary_organization": 5,
    "no_action": 6,
    "human_escalation": 7,
}


class MissionResolutionError(ValueError):
    """A route could not be computed without violating the closed contract."""


class ResolutionClass(str, Enum):
    NO_ACTION = "no_action"
    DIRECT_CAPABILITY = "direct_capability"
    SINGLE_MODEL_OR_TOOL = "single_model_or_tool"
    EXISTING_WORKFLOW = "existing_workflow"
    STATIC_DURABLE_WORKFLOW = "static_durable_workflow"
    FIXED_SPECIALIST_CONFIGURATION = "fixed_specialist_configuration"
    COMPILED_TEMPORARY_ORGANIZATION = "compiled_temporary_organization"
    HUMAN_ESCALATION = "human_escalation"


@dataclass(frozen=True)
class ResolutionCandidate:
    """One mechanism that could carry a mission, without permission to use it."""

    candidate_id: str
    resolution_class: str
    description: str
    available: bool
    execution_eligible: bool
    evidence_maturity: str
    expected_quality: float
    estimated_cost_usd: float
    coordination_units: float
    founder_attention_minutes: float
    reversible: bool
    authority_delta: int = 0
    external_effects: int = 0
    reason: str = ""
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.candidate_id, str) or not self.candidate_id.strip():
            raise MissionResolutionError("candidate_id must be non-empty")
        if self.resolution_class not in RESOLUTION_CLASSES:
            raise MissionResolutionError(
                f"unknown resolution class {self.resolution_class!r}"
            )
        if self.evidence_maturity not in EVIDENCE_MATURITY:
            raise MissionResolutionError(
                f"unknown evidence maturity {self.evidence_maturity!r}"
            )
        for name in (
            "expected_quality",
            "estimated_cost_usd",
            "coordination_units",
            "founder_attention_minutes",
        ):
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise MissionResolutionError(f"{name} must be non-negative")
        if self.expected_quality > 1:
            raise MissionResolutionError("expected_quality must be at most 1")
        for name in ("available", "execution_eligible", "reversible"):
            if type(getattr(self, name)) is not bool:
                raise MissionResolutionError(f"{name} must be a boolean")
        if type(self.authority_delta) is not int or self.authority_delta != 0:
            raise MissionResolutionError("a route cannot create or widen authority")
        if type(self.external_effects) is not int or self.external_effects != 0:
            raise MissionResolutionError("a route cannot create external effects")
        if not self.reason.strip():
            raise MissionResolutionError("candidate reason must be explicit")
        if len(set(self.evidence_refs)) != len(self.evidence_refs):
            raise MissionResolutionError("evidence_refs must be unique")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ResolutionCandidate":
        allowed = {
            "candidate_id", "resolution_class", "description", "available",
            "execution_eligible", "evidence_maturity", "expected_quality",
            "estimated_cost_usd", "coordination_units",
            "founder_attention_minutes", "reversible", "authority_delta",
            "external_effects", "reason", "evidence_refs",
        }
        unknown = set(value) - allowed
        missing = {
            "candidate_id", "resolution_class", "description", "available",
            "execution_eligible", "evidence_maturity", "expected_quality",
            "estimated_cost_usd", "coordination_units",
            "founder_attention_minutes", "reversible", "reason",
        } - set(value)
        if unknown:
            raise MissionResolutionError(
                f"candidate has unknown fields: {sorted(unknown)}"
            )
        if missing:
            raise MissionResolutionError(
                f"candidate is missing fields: {sorted(missing)}"
            )
        return cls(
            candidate_id=str(value["candidate_id"]),
            resolution_class=str(value["resolution_class"]),
            description=str(value["description"]),
            available=value["available"],
            execution_eligible=value["execution_eligible"],
            evidence_maturity=str(value["evidence_maturity"]),
            expected_quality=value["expected_quality"],
            estimated_cost_usd=value["estimated_cost_usd"],
            coordination_units=value["coordination_units"],
            founder_attention_minutes=value["founder_attention_minutes"],
            reversible=value["reversible"],
            authority_delta=value.get("authority_delta", 0),
            external_effects=value.get("external_effects", 0),
            reason=str(value["reason"]),
            evidence_refs=tuple(str(item) for item in value.get("evidence_refs", ())),
        )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["evidence_refs"] = list(self.evidence_refs)
        return value


@dataclass(frozen=True)
class MissionResolution:
    """Complete ranked route record. It confers no execution admission."""

    resolution_id: str
    schema_version: str
    record_kind: str
    mission_ref: str
    mission_digest: str
    problem_geometry_digest: str
    candidates: tuple[ResolutionCandidate, ...]
    ranking: tuple[dict[str, Any], ...]
    selected_candidate_id: str | None
    decision_status: str
    execution_admission: str
    authority_created: int
    external_effects: int
    losers_preserved: bool
    digest_scope: str
    digest: str

    @property
    def execution_authority(self) -> str:
        return "none"

    @property
    def selected(self) -> ResolutionCandidate | None:
        for candidate in self.candidates:
            if candidate.candidate_id == self.selected_candidate_id:
                return candidate
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "resolution_id": self.resolution_id,
            "schema_version": self.schema_version,
            "record_kind": self.record_kind,
            "mission_ref": self.mission_ref,
            "mission_digest": self.mission_digest,
            "problem_geometry_digest": self.problem_geometry_digest,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "ranking": copy.deepcopy(list(self.ranking)),
            "selected_candidate_id": self.selected_candidate_id,
            "decision_status": self.decision_status,
            "execution_admission": self.execution_admission,
            "authority_created": self.authority_created,
            "external_effects": self.external_effects,
            "losers_preserved": self.losers_preserved,
            "digest_scope": self.digest_scope,
            "digest": self.digest,
        }


def _schema_validate(value: dict[str, Any]) -> None:
    try:
        with _SCHEMA.open(encoding="utf-8") as handle:
            schema = json.load(handle)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        validator.validate(value)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise MissionResolutionError(f"MissionResolution refused: {exc}") from exc


def _default_candidate(
    resolution_class: str,
    *,
    available: bool,
    reason: str,
    evidence_maturity: str = "NONE",
    expected_quality: float = 0.0,
    estimated_cost_usd: float = 0.0,
    coordination_units: float = 0.0,
    founder_attention_minutes: float = 0.0,
    reversible: bool = True,
    execution_eligible: bool = False,
    evidence_refs: Sequence[str] = (),
) -> ResolutionCandidate:
    return ResolutionCandidate(
        candidate_id="route:" + resolution_class,
        resolution_class=resolution_class,
        description=resolution_class.replace("_", " "),
        available=available,
        execution_eligible=execution_eligible,
        evidence_maturity=evidence_maturity,
        expected_quality=expected_quality,
        estimated_cost_usd=estimated_cost_usd,
        coordination_units=coordination_units,
        founder_attention_minutes=founder_attention_minutes,
        reversible=reversible,
        reason=reason,
        evidence_refs=tuple(evidence_refs),
    )


def _score(candidate: ResolutionCandidate, *, forced_refusal: bool) -> tuple[int, dict[str, int]]:
    if candidate.resolution_class == "no_action":
        quality = 6000 if forced_refusal else 0
    else:
        quality = round(candidate.expected_quality * 5000)
    evidence = {
        "NONE": 0,
        "DECLARED": 700,
        "TESTED": 1400,
        "VERIFIED": 2100,
    }[candidate.evidence_maturity]
    simplicity = 1500
    coordination_penalty = round(candidate.coordination_units * 300)
    cost_penalty = round(candidate.estimated_cost_usd * 100)
    attention_penalty = round(candidate.founder_attention_minutes * 50)
    components = {
        "quality": quality,
        "evidence": evidence,
        "simplicity": simplicity,
        "coordination_penalty": coordination_penalty,
        "cost_penalty": cost_penalty,
        "attention_penalty": attention_penalty,
    }
    return (
        quality + evidence + simplicity
        - coordination_penalty - cost_penalty - attention_penalty,
        components,
    )


class MissionResolutionRouter:
    """Rank mechanisms for one mission. No invocation, grant or activation surface."""

    def __init__(self) -> None:
        self._resolutions: list[MissionResolution] = []

    @property
    def execution_authority(self) -> str:
        return "none"

    def _candidate_set(
        self,
        mission: Mapping[str, Any],
        supplied: Sequence[ResolutionCandidate | Mapping[str, Any]],
        *,
        static_baseline_available: bool,
        unresolved_reasons: Sequence[str],
        compiled_organization: Any | None,
    ) -> tuple[ResolutionCandidate, ...]:
        if "mission_id" not in mission or "problem_geometry" not in mission:
            raise MissionResolutionError("mission_id and problem_geometry are required")
        supplied_candidates = [
            item if isinstance(item, ResolutionCandidate)
            else ResolutionCandidate.from_mapping(item)
            for item in supplied
        ]
        by_class: dict[str, ResolutionCandidate] = {
            item.resolution_class: item for item in supplied_candidates
        }
        if len(by_class) != len(supplied_candidates):
            raise MissionResolutionError("one candidate per resolution class is required")

        defaults = {
            "no_action": _default_candidate(
                "no_action",
                available=True,
                execution_eligible=True,
                evidence_maturity="VERIFIED",
                reason=(
                    "refusal/wait is always retained; it wins only when no safe "
                    "mechanism is admissible or the mission is forced to refuse"
                ),
            ),
            "direct_capability": _default_candidate(
                "direct_capability",
                available=False,
                reason="no direct existing capability was supplied",
            ),
            "single_model_or_tool": _default_candidate(
                "single_model_or_tool",
                available=False,
                reason="no bounded single model/tool capability was supplied",
            ),
            "existing_workflow": _default_candidate(
                "existing_workflow",
                available=False,
                reason="no existing workflow was supplied",
            ),
            "static_durable_workflow": _default_candidate(
                "static_durable_workflow",
                available=static_baseline_available,
                execution_eligible=static_baseline_available,
                evidence_maturity="TESTED" if static_baseline_available else "NONE",
                expected_quality=0.75 if static_baseline_available else 0.0,
                coordination_units=1.0,
                reason=(
                    "protected conventional baseline; it wins exact ties and "
                    "remains the safe fallback"
                ) if static_baseline_available else "static baseline unavailable",
                evidence_refs=("baseline:static-durable-workflow",)
                if static_baseline_available else (),
            ),
            "fixed_specialist_configuration": _default_candidate(
                "fixed_specialist_configuration",
                available=False,
                reason="no fixed specialist configuration was supplied",
            ),
            "compiled_temporary_organization": _default_candidate(
                "compiled_temporary_organization",
                available=False,
                reason=(
                    "OMNIMORPH is not invoked until the resolver establishes "
                    "that simpler mechanisms are insufficient"
                ),
            ),
            "human_escalation": _default_candidate(
                "human_escalation",
                available=bool(unresolved_reasons),
                execution_eligible=False,
                evidence_maturity="TESTED" if unresolved_reasons else "NONE",
                expected_quality=0.7 if unresolved_reasons else 0.0,
                founder_attention_minutes=1.0 if unresolved_reasons else 0.0,
                reason=(
                    "an unresolved authority, evidence or consequence question "
                    "requires Alfonso's reserved decision"
                ) if unresolved_reasons else "no unresolved founder question",
                evidence_refs=tuple(sorted(set(unresolved_reasons))),
            ),
        }
        if compiled_organization is not None:
            organization = getattr(compiled_organization, "organization", compiled_organization)
            decision = getattr(organization, "decision", {}) or {}
            genome_digest = (
                decision.get("recommendation", {}).get("genome_digest")
                or "unavailable"
            )
            defaults["compiled_temporary_organization"] = ResolutionCandidate(
                candidate_id="route:compiled-temporary-organization",
                resolution_class="compiled_temporary_organization",
                description="OMNIMORPH mission-bounded organization hypothesis",
                available=True,
                execution_eligible=False,
                evidence_maturity="DECLARED",
                expected_quality=0.55,
                estimated_cost_usd=0.0,
                coordination_units=4.0,
                founder_attention_minutes=0.0,
                reversible=True,
                reason=(
                    "genome "
                    + genome_digest
                    + " is a design hypothesis; activation is refused until "
                      "an executed comparative episode and separate admission"
                ),
                evidence_refs=("omnimorph:design-hypothesis",),
            )
        defaults.update(by_class)
        ordered = []
        for resolution_class in RESOLUTION_CLASSES:
            ordered.append(defaults[resolution_class])
        ids = [candidate.candidate_id for candidate in ordered]
        if len(ids) != len(set(ids)):
            raise MissionResolutionError("candidate ids must be unique")
        return tuple(ordered)

    @staticmethod
    def _refusal(candidate: ResolutionCandidate, *, forced_refusal: bool) -> str | None:
        if not candidate.available:
            return "candidate is unavailable"
        if candidate.authority_delta != 0:
            return "candidate claims an authority delta"
        if candidate.external_effects != 0:
            return "candidate claims an external effect"
        if candidate.resolution_class == "compiled_temporary_organization":
            return "organization activation is disabled at the mission-resolution seam"
        if candidate.resolution_class not in {"no_action", "human_escalation"}:
            if not candidate.execution_eligible:
                return "candidate is not execution-eligible"
            if forced_refusal:
                return "mission consequence policy requires human/Gate handling"
        return None

    def route(
        self,
        mission_contract: Mapping[str, Any],
        *,
        candidates: Sequence[ResolutionCandidate | Mapping[str, Any]] = (),
        static_baseline_available: bool = True,
        unresolved_reasons: Sequence[str] = (),
        compiled_organization: Any | None = None,
    ) -> MissionResolution:
        mission = copy.deepcopy(dict(mission_contract))
        if mission.get("external_effect_policy") not in {
            "none", "proposal_only", "gate_required"
        }:
            raise MissionResolutionError("mission external_effect_policy is unknown")
        pool = self._candidate_set(
            mission,
            candidates,
            static_baseline_available=static_baseline_available,
            unresolved_reasons=unresolved_reasons,
            compiled_organization=compiled_organization,
        )
        forced_refusal = (
            mission.get("external_effect_policy") != "none"
            or mission.get("consequence_ceiling")
            in {"external_contact", "financial", "irreversible"}
        )
        rows = []
        eligible_rows = []
        for candidate in pool:
            refusal = self._refusal(candidate, forced_refusal=forced_refusal)
            if refusal is None:
                score, components = _score(candidate, forced_refusal=forced_refusal and not unresolved_reasons)
                eligible = True
                reason = candidate.reason
                eligible_rows.append((candidate, score, components))
            else:
                score = 0
                components = {
                    "quality": 0,
                    "evidence": 0,
                    "simplicity": 0,
                    "coordination_penalty": 0,
                    "cost_penalty": 0,
                    "attention_penalty": 0,
                }
                eligible = False
                reason = refusal + "; " + candidate.reason
            rows.append({
                "candidate_id": candidate.candidate_id,
                "resolution_class": candidate.resolution_class,
                "rank": 0,
                "eligible": eligible,
                "score_basis_points": score,
                "score_components": components,
                "reason": reason,
            })
        eligible_rows.sort(
            key=lambda item: (
                -item[1],
                _TIE_PRIORITY[item[0].resolution_class],
                item[0].candidate_id,
            )
        )
        # Refused candidates are retained after admissible candidates. Their
        # rank is still explicit, so absence cannot masquerade as a loss.
        ordered_ids = [item[0].candidate_id for item in eligible_rows]
        ordered_ids.extend(
            row["candidate_id"] for row in rows
            if row["candidate_id"] not in ordered_ids
        )
        by_id = {row["candidate_id"]: row for row in rows}
        ranking = []
        for rank, candidate_id in enumerate(ordered_ids, start=1):
            row = copy.deepcopy(by_id[candidate_id])
            row["rank"] = rank
            ranking.append(row)

        selected = eligible_rows[0][0] if eligible_rows else None
        mission_digest = content_digest(mission)
        geometry_digest = content_digest(mission["problem_geometry"])
        resolution_seed = {
            "mission_digest": mission_digest,
            "candidate_ids": ordered_ids,
            "unresolved_reasons": list(unresolved_reasons),
        }
        resolution_id = str(uuid5(_NAMESPACE, content_digest(resolution_seed)))
        raw = {
            "resolution_id": resolution_id,
            "schema_version": "1.0",
            "record_kind": "MISSION_RESOLUTION",
            "mission_ref": mission["mission_id"],
            "mission_digest": mission_digest,
            "problem_geometry_digest": geometry_digest,
            "candidates": [candidate.to_dict() for candidate in pool],
            "ranking": ranking,
            "selected_candidate_id": selected.candidate_id if selected else None,
            "decision_status": "HYPOTHESIS_ONLY",
            "execution_admission": "REFUSED_PENDING_SEPARATE_PHASE_DECISION",
            "authority_created": 0,
            "external_effects": 0,
            "losers_preserved": True,
            "digest_scope": "RFC8785_CANONICAL_JSON_EXCLUDING_DIGEST",
        }
        raw["digest"] = content_digest(raw, excluding=("digest",))
        _schema_validate(raw)
        result = MissionResolution(
            resolution_id=raw["resolution_id"],
            schema_version=raw["schema_version"],
            record_kind=raw["record_kind"],
            mission_ref=raw["mission_ref"],
            mission_digest=raw["mission_digest"],
            problem_geometry_digest=raw["problem_geometry_digest"],
            candidates=pool,
            ranking=tuple(ranking),
            selected_candidate_id=raw["selected_candidate_id"],
            decision_status=raw["decision_status"],
            execution_admission=raw["execution_admission"],
            authority_created=raw["authority_created"],
            external_effects=raw["external_effects"],
            losers_preserved=raw["losers_preserved"],
            digest_scope=raw["digest_scope"],
            digest=raw["digest"],
        )
        self._resolutions.append(result)
        return result

    @property
    def resolutions(self) -> tuple[MissionResolution, ...]:
        return tuple(self._resolutions)


__all__ = [
    "EVIDENCE_MATURITY",
    "MissionResolution",
    "MissionResolutionError",
    "MissionResolutionRouter",
    "RESOLUTION_CLASSES",
    "ResolutionCandidate",
    "ResolutionClass",
]
