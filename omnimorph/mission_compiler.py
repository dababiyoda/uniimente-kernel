"""Mission-level OMNIMORPH compilation.

This is the seam above organization topology. A bounded mission is compiled
into two coupled, content-bound artifacts:

* a MissionCapabilityManifest naming the functions the mission needs; and
* the existing Phase-3 OrchestrationGenome hypotheses naming how those
  functions could be organized.

The compiler designs. It never issues a grant, creates an identity, starts a
worker, invokes a provider, calls the Consequence Gate, or claims that a
topology worked. Runtime and consequence ownership stay downstream.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from .organization_compiler import (
    CompilationResult,
    OrganizationCompilationError,
    OrganizationCompiler,
    content_digest,
)


_SCHEMA = Path(__file__).resolve().parents[1] / "contracts" / "capability-manifest.schema.json"
_NAMESPACE = UUID("48af36f4-71cf-5e7f-bc73-8f8f18d1d4db")


class MissionCompilationError(ValueError):
    """A coupled capability/organization design was not contract-valid."""


@dataclass(frozen=True)
class MissionCompilationResult:
    """The two artifacts produced for one immutable mission."""

    capability_manifest: dict[str, Any]
    organization: CompilationResult

    @property
    def mission_digest(self) -> str:
        return self.organization.mission_digest

    @property
    def problem_geometry_digest(self) -> str:
        return self.organization.problem_geometry_digest

    def genome_for(self, phenotype: str) -> dict[str, Any]:
        return self.organization.genome_for(phenotype)

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_manifest": copy.deepcopy(self.capability_manifest),
            "organization_decision": copy.deepcopy(self.organization.decision),
            "organization_genomes": copy.deepcopy(list(self.organization.genomes)),
        }


def _validator() -> Draft202012Validator:
    try:
        with _SCHEMA.open(encoding="utf-8") as handle:
            schema = json.load(handle)
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(schema, format_checker=FormatChecker())
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise MissionCompilationError(
            f"capability-manifest contract cannot be loaded: {exc}"
        ) from exc


def _validate_manifest(manifest: dict[str, Any]) -> None:
    try:
        _validator().validate(manifest)
    except ValidationError as exc:
        path = ".".join(str(part) for part in exc.absolute_path) or "<root>"
        raise MissionCompilationError(
            f"MissionCapabilityManifest refused at {path}: {exc.message}"
        ) from exc


def _manifest_for(mission: dict[str, Any], mission_digest: str) -> dict[str, Any]:
    capability_manifest: dict[str, Any] = {
        "manifest_id": str(uuid5(_NAMESPACE, mission_digest + "|capability-manifest")),
        "schema_version": "1.0",
        "record_kind": "MISSION_CAPABILITY_MANIFEST",
        "mission_ref": mission["mission_id"],
        "mission_digest": mission_digest,
        "capabilities": copy.deepcopy(mission["required_capabilities"]),
        "authority_refs": list(mission["authority_refs"]),
        "resource_envelope": copy.deepcopy(mission["resource_envelope"]),
        "evidence_requirement_refs": [
            item["requirement_id"] for item in mission["evidence_requirements"]
        ],
        "prohibited_actions": list(mission["prohibited_actions"]),
        "external_effect_policy": mission["external_effect_policy"],
        "execution_admission": "REFUSED_PENDING_SEPARATE_PHASE_DECISION",
        "authority_created": 0,
        "digest_scope": "RFC8785_CANONICAL_JSON_EXCLUDING_DIGEST",
    }
    capability_manifest["digest"] = content_digest(
        capability_manifest, excluding=("digest",)
    )
    return capability_manifest


class MissionCompiler:
    """Compile capability needs and organizational hypotheses without activation."""

    def __init__(
        self,
        *,
        organization_compiler: OrganizationCompiler | None = None,
    ) -> None:
        self.organization_compiler = organization_compiler or OrganizationCompiler()

    @property
    def policy_digest(self) -> str:
        return self.organization_compiler.policy_digest

    @property
    def zero_trust_profile_digest(self) -> str:
        return self.organization_compiler.zero_trust_profile_digest

    def compile(self, mission_contract: dict[str, Any]) -> MissionCompilationResult:
        mission = copy.deepcopy(mission_contract)
        try:
            organization = self.organization_compiler.compile(mission)
        except OrganizationCompilationError as exc:
            raise MissionCompilationError(str(exc)) from exc

        manifest = _manifest_for(mission, organization.mission_digest)
        _validate_manifest(manifest)
        if manifest["mission_digest"] != organization.mission_digest:
            raise MissionCompilationError("capability and organization mission digests differ")
        if manifest["authority_refs"] != mission["authority_refs"]:
            raise MissionCompilationError("capability manifest changed mission authority references")
        if manifest["resource_envelope"] != mission["resource_envelope"]:
            raise MissionCompilationError("capability manifest changed mission resource envelope")
        return MissionCompilationResult(
            capability_manifest=manifest,
            organization=organization,
        )


__all__ = ["MissionCompilationError", "MissionCompilationResult", "MissionCompiler"]