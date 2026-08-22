"""Consequence-matched containment declarations and independently verified evidence.

The broker selects a verified policy match. It never launches a workload and
never converts executable presence, configuration, or self-attestation into a
claim that containment ran. Missing proof is returned as ``UNAVAILABLE``.
"""
from __future__ import annotations

import copy
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from types import MappingProxyType
from typing import Callable, Iterable, Mapping

from moduleloader.frozen_contract import FrozenContractError, FrozenContractSchemas
from moduleloader.integrity import require_aware, sha256_json, utc_now, valid_sha256


class ContainmentTier(str, Enum):
    IN_PROCESS = "in_process"
    HARDENED_CONTAINER = "hardened_container"
    MICROVM = "microvm"
    WASM_COMPONENT = "wasm_component"


class EnforcementKind(str, Enum):
    POLICY_ONLY = "policy_only"
    OS_KERNEL_BOUNDARY = "os_kernel_boundary"
    HYPERVISOR_BOUNDARY = "hypervisor_boundary"
    WASM_SANDBOX = "wasm_sandbox"


TIER_ENFORCEMENT: Mapping[ContainmentTier, EnforcementKind] = MappingProxyType({
    ContainmentTier.IN_PROCESS: EnforcementKind.POLICY_ONLY,
    ContainmentTier.HARDENED_CONTAINER: EnforcementKind.OS_KERNEL_BOUNDARY,
    ContainmentTier.MICROVM: EnforcementKind.HYPERVISOR_BOUNDARY,
    ContainmentTier.WASM_COMPONENT: EnforcementKind.WASM_SANDBOX,
})

REQUIRED_CONTROLS: Mapping[ContainmentTier, frozenset[str]] = MappingProxyType({
    ContainmentTier.IN_PROCESS: frozenset({"authority_checked_by_caller"}),
    ContainmentTier.HARDENED_CONTAINER: frozenset(
        {
            "no_ambient_credentials",
            "read_only_root",
            "network_deny_default",
            "resource_limits",
            "non_root",
            "seccomp_or_equivalent",
        }
    ),
    ContainmentTier.WASM_COMPONENT: frozenset(
        {
            "no_ambient_imports",
            "explicit_host_imports",
            "filesystem_preopens_bounded",
            "network_deny_default",
            "fuel_or_epoch_limit",
            "memory_limit",
        }
    ),
    ContainmentTier.MICROVM: frozenset(
        {
            "jailer_or_stricter",
            "namespaces",
            "cgroups",
            "privilege_drop",
            "resource_limits",
            "seccomp_filters",
            "network_deny_default",
            "immutable_root_or_snapshot",
        }
    ),
})

CONSEQUENCE_CLASSES = (
    "read_only",
    "internal_write",
    "external_contact",
    "financial",
    "irreversible",
)
TRUST_CLASSES = ("internal_trusted", "internal_untrusted", "foreign", "generated")


class ContainmentRefused(ValueError):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def required_controls(tier: ContainmentTier) -> frozenset[str]:
    """Return the immutable control floor for one declared tier."""
    if not isinstance(tier, ContainmentTier):
        raise ContainmentRefused("INVALID_REQUIREMENT", "required tier is invalid")
    return REQUIRED_CONTROLS[tier]


@dataclass(frozen=True)
class ProviderDeclaration:
    provider_id: str
    tier: ContainmentTier
    runtime_name: str
    enforcement_kind: EnforcementKind

    def validate(self) -> None:
        if not isinstance(self.provider_id, str) or not self.provider_id:
            raise ContainmentRefused("INVALID_PROVIDER", "provider_id is required")
        if not isinstance(self.runtime_name, str) or not self.runtime_name:
            raise ContainmentRefused("INVALID_PROVIDER", "runtime_name is required")
        if not isinstance(self.tier, ContainmentTier):
            raise ContainmentRefused("INVALID_PROVIDER", "tier is invalid")
        if not isinstance(self.enforcement_kind, EnforcementKind):
            raise ContainmentRefused("INVALID_PROVIDER", "enforcement kind is invalid")
        if TIER_ENFORCEMENT[self.tier] != self.enforcement_kind:
            raise ContainmentRefused(
                "ENFORCEMENT_MISMATCH",
                f"{self.tier.value} requires {TIER_ENFORCEMENT[self.tier].value}",
            )


@dataclass(frozen=True)
class ContainmentAttestation:
    provider_id: str
    verifier_id: str
    tier: ContainmentTier
    runtime_name: str
    enforcement_kind: EnforcementKind
    runtime_digest: str
    controls: frozenset[str]
    evidence_refs: tuple[str, ...]
    issued_at: datetime
    expires_at: datetime
    nonce: str
    verification_ref: str

    def canonical_claim(self) -> dict:
        return {
            "provider_id": self.provider_id,
            "verifier_id": self.verifier_id,
            "tier": self.tier.value,
            "runtime_name": self.runtime_name,
            "enforcement_kind": self.enforcement_kind.value,
            "runtime_digest": self.runtime_digest,
            "controls": sorted(self.controls),
            "evidence_refs": list(self.evidence_refs),
            "issued_at": require_aware(self.issued_at, "issued_at").isoformat(),
            "expires_at": require_aware(self.expires_at, "expires_at").isoformat(),
            "nonce": self.nonce,
            "verification_ref": self.verification_ref,
        }

    @property
    def attestation_digest(self) -> str:
        return sha256_json(self.canonical_claim())


@dataclass(frozen=True)
class ContainmentRequirement:
    module_id: str
    consequence_class: str
    trust: str
    required_tier: ContainmentTier
    additional_controls: frozenset[str] = frozenset()
    resource_limits: dict[str, object] = field(default_factory=dict)

    @property
    def controls(self) -> frozenset[str]:
        return required_controls(self.required_tier) | self.additional_controls

    def validate(self) -> None:
        if not isinstance(self.module_id, str) or not self.module_id:
            raise ContainmentRefused("INVALID_REQUIREMENT", "module_id is required")
        if self.consequence_class not in CONSEQUENCE_CLASSES:
            raise ContainmentRefused("INVALID_REQUIREMENT", "unknown consequence class")
        if self.trust not in TRUST_CLASSES:
            raise ContainmentRefused("INVALID_REQUIREMENT", "unknown trust class")
        if not isinstance(self.required_tier, ContainmentTier):
            raise ContainmentRefused("INVALID_REQUIREMENT", "required tier is invalid")
        if not isinstance(self.additional_controls, frozenset) or not all(
            isinstance(control, str) and control for control in self.additional_controls
        ):
            raise ContainmentRefused(
                "INVALID_REQUIREMENT", "additional controls must be non-empty strings"
            )
        if not isinstance(self.resource_limits, dict):
            raise ContainmentRefused("INVALID_REQUIREMENT", "resource_limits must be an object")
        if (
            self.consequence_class == "irreversible"
            and self.required_tier is not ContainmentTier.MICROVM
        ):
            raise ContainmentRefused(
                "INSUFFICIENT_TIER", "irreversible consequence requires microvm"
            )
        if self.trust in {"foreign", "generated"} and self.required_tier not in {
            ContainmentTier.MICROVM,
            ContainmentTier.WASM_COMPONENT,
        }:
            raise ContainmentRefused(
                "INSUFFICIENT_TIER", "foreign/generated code requires microvm or wasm_component"
            )
        if self.trust == "internal_untrusted" and self.required_tier == ContainmentTier.IN_PROCESS:
            raise ContainmentRefused(
                "INSUFFICIENT_TIER", "internal_untrusted code cannot run in process"
            )
        if self.consequence_class in {"external_contact", "financial", "irreversible"} and (
            self.required_tier == ContainmentTier.IN_PROCESS
        ):
            raise ContainmentRefused(
                "INSUFFICIENT_TIER", "external consequences require a real boundary"
            )


@dataclass(frozen=True)
class ContainmentDecision:
    requirement: ContainmentRequirement
    granted_tier: str
    enforcement_kind: EnforcementKind
    attested: bool
    attestation_evidence: str | None
    provider_id: str | None = None
    expires_at: datetime | None = None
    evidence_refs: tuple[str, ...] = ()
    status: str = "UNAVAILABLE"

    def as_document(self) -> dict:
        document = {
            "requirement_version": "1.0.0",
            "module_id": self.requirement.module_id,
            "consequence_class": self.requirement.consequence_class,
            "trust": self.requirement.trust,
            "required_tier": self.requirement.required_tier.value,
            "granted_tier": self.granted_tier,
            "enforcement_kind": self.enforcement_kind.value,
            "attested": self.attested,
            "attestation_evidence": self.attestation_evidence,
        }
        if self.requirement.resource_limits:
            document["resource_limits"] = copy.deepcopy(self.requirement.resource_limits)
        return document


AttestationVerifier = Callable[[ContainmentAttestation], tuple[bool, str]]
AttestationReplayKey = tuple[str, str, str]
AttestationReplayRecorder = Callable[[AttestationReplayKey, datetime], bool]


class ContainmentBroker:
    """Declaration registry plus independent, expiring verifier evidence."""

    def __init__(
        self,
        *,
        trusted_verifiers: Iterable[str],
        verify_attestation: AttestationVerifier,
        record_replay_key: AttestationReplayRecorder | None = None,
        schemas: FrozenContractSchemas | None = None,
        max_attestation_lifetime: timedelta = timedelta(hours=24),
    ):
        if isinstance(trusted_verifiers, (str, bytes)):
            raise ContainmentRefused("INVALID_POLICY", "trusted_verifiers must be IDs")
        try:
            verifiers = frozenset(trusted_verifiers)
        except TypeError as exc:
            raise ContainmentRefused("INVALID_POLICY", "trusted_verifiers are invalid") from exc
        if not verifiers or not all(isinstance(item, str) and item for item in verifiers):
            raise ContainmentRefused("INVALID_POLICY", "trusted verifier IDs are required")
        if not callable(verify_attestation):
            raise ContainmentRefused("INVALID_POLICY", "verify_attestation is required")
        if not callable(record_replay_key):
            raise ContainmentRefused(
                "INVALID_POLICY", "an atomic durable replay recorder is required"
            )
        if schemas is not None and not isinstance(schemas, FrozenContractSchemas):
            raise ContainmentRefused("INVALID_POLICY", "schemas must be FrozenContractSchemas")
        if not isinstance(max_attestation_lifetime, timedelta) or max_attestation_lifetime <= timedelta(0):
            raise ContainmentRefused("INVALID_POLICY", "attestation lifetime must be positive")
        self._trusted_verifiers = verifiers
        self._verify_attestation = verify_attestation
        self._record_replay_key = record_replay_key
        self._schemas = schemas or FrozenContractSchemas()
        self._max_lifetime = max_attestation_lifetime
        self._providers: dict[str, ProviderDeclaration] = {}
        self._attestations: dict[str, list[ContainmentAttestation]] = {}

    def register(self, declaration: ProviderDeclaration) -> None:
        if not isinstance(declaration, ProviderDeclaration):
            raise ContainmentRefused("INVALID_PROVIDER", "wrong declaration type")
        declaration.validate()
        prior = self._providers.get(declaration.provider_id)
        if prior is not None and prior != declaration:
            raise ContainmentRefused(
                "PROVIDER_DRIFT", "a provider cannot silently change its declaration"
            )
        self._providers[declaration.provider_id] = declaration

    def accept_attestation(
        self, attestation: ContainmentAttestation, *, now: datetime | None = None
    ) -> str:
        if not isinstance(attestation, ContainmentAttestation):
            raise ContainmentRefused("INVALID_ATTESTATION", "wrong attestation type")
        current = require_aware(now or utc_now(), "now")
        declaration = self._providers.get(attestation.provider_id)
        if declaration is None:
            raise ContainmentRefused("UNKNOWN_PROVIDER", attestation.provider_id)
        if attestation.verifier_id == attestation.provider_id:
            raise ContainmentRefused("SELF_ATTESTATION", attestation.provider_id)
        if attestation.verifier_id not in self._trusted_verifiers:
            raise ContainmentRefused("UNTRUSTED_VERIFIER", attestation.verifier_id)
        if (
            declaration.tier != attestation.tier
            or declaration.runtime_name != attestation.runtime_name
            or declaration.enforcement_kind != attestation.enforcement_kind
        ):
            raise ContainmentRefused("DECLARATION_MISMATCH", attestation.provider_id)
        if not valid_sha256(attestation.runtime_digest):
            raise ContainmentRefused("INVALID_ATTESTATION", "runtime digest must be sha256")
        issued = require_aware(attestation.issued_at, "issued_at")
        expires = require_aware(attestation.expires_at, "expires_at")
        if issued > current or expires <= current:
            raise ContainmentRefused("STALE_ATTESTATION", attestation.provider_id)
        if expires - issued > self._max_lifetime:
            raise ContainmentRefused("ATTESTATION_TTL_EXCEEDED", attestation.provider_id)
        if not isinstance(attestation.controls, frozenset) or not all(
            isinstance(control, str) and control for control in attestation.controls
        ):
            raise ContainmentRefused("INVALID_ATTESTATION", "controls are invalid")
        missing = required_controls(attestation.tier) - attestation.controls
        if missing:
            raise ContainmentRefused("MISSING_CONTROLS", str(sorted(missing)))
        if not isinstance(attestation.evidence_refs, tuple) or not attestation.evidence_refs or not all(
            isinstance(reference, str) and reference for reference in attestation.evidence_refs
        ):
            raise ContainmentRefused("MISSING_EVIDENCE", attestation.provider_id)
        if not isinstance(attestation.nonce, str) or len(attestation.nonce) < 16:
            raise ContainmentRefused("INVALID_ATTESTATION", "nonce is too short")
        if not isinstance(attestation.verification_ref, str) or not attestation.verification_ref:
            raise ContainmentRefused("INVALID_ATTESTATION", "verification_ref is required")
        try:
            verified, reason = self._verify_attestation(attestation)
        except Exception as exc:
            raise ContainmentRefused("VERIFIER_UNAVAILABLE", type(exc).__name__) from exc
        if verified is not True:
            raise ContainmentRefused("ATTESTATION_REFUSED", str(reason))
        replay_key: AttestationReplayKey = (
            "containment.attestation.v1",
            attestation.verifier_id,
            attestation.nonce,
        )
        try:
            claimed = self._record_replay_key(replay_key, expires)
        except Exception as exc:
            raise ContainmentRefused(
                "REPLAY_STORE_UNAVAILABLE", type(exc).__name__
            ) from exc
        if claimed is not True:
            raise ContainmentRefused("ATTESTATION_REPLAY", attestation.nonce)
        self._attestations.setdefault(attestation.provider_id, []).append(attestation)
        return attestation.attestation_digest

    def _validate_output(self, decision: ContainmentDecision) -> ContainmentDecision:
        try:
            self._schemas.validate_containment_requirement(decision.as_document())
        except FrozenContractError as exc:
            raise ContainmentRefused("FROZEN_SCHEMA_REFUSED", exc.detail) from exc
        return decision

    def select(
        self, requirement: ContainmentRequirement, *, now: datetime | None = None
    ) -> ContainmentDecision:
        if not isinstance(requirement, ContainmentRequirement):
            raise ContainmentRefused("INVALID_REQUIREMENT", "wrong requirement type")
        requirement.validate()
        # Validate the caller's requirement shape before consulting any
        # verifier.  The honest UNAVAILABLE form is the schema's neutral
        # preflight representation and carries no availability claim.
        self._validate_output(
            ContainmentDecision(
                requirement=copy.deepcopy(requirement),
                granted_tier="UNAVAILABLE",
                enforcement_kind=EnforcementKind.POLICY_ONLY,
                attested=False,
                attestation_evidence=None,
                status="UNAVAILABLE",
            )
        )
        current = require_aware(now or utc_now(), "now")
        candidates: list[ContainmentAttestation] = []
        for provider_id, declaration in self._providers.items():
            if declaration.tier != requirement.required_tier:
                continue
            for attestation in self._attestations.get(provider_id, ()):
                if require_aware(attestation.expires_at, "expires_at") <= current:
                    continue
                if not requirement.controls.issubset(attestation.controls):
                    continue
                try:
                    verified, _ = self._verify_attestation(attestation)
                except Exception:
                    continue
                if verified is True:
                    candidates.append(attestation)
        if not candidates:
            return self._validate_output(
                ContainmentDecision(
                    requirement=copy.deepcopy(requirement),
                    granted_tier="UNAVAILABLE",
                    enforcement_kind=EnforcementKind.POLICY_ONLY,
                    attested=False,
                    attestation_evidence=None,
                    status="UNAVAILABLE",
                )
            )
        candidates.sort(
            key=lambda item: (
                -item.issued_at.timestamp(),
                item.provider_id,
                item.attestation_digest,
            )
        )
        selected = candidates[0]
        return self._validate_output(
            ContainmentDecision(
                requirement=copy.deepcopy(requirement),
                granted_tier=selected.tier.value,
                enforcement_kind=selected.enforcement_kind,
                attested=True,
                attestation_evidence=selected.attestation_digest,
                provider_id=selected.provider_id,
                expires_at=selected.expires_at,
                evidence_refs=selected.evidence_refs,
                status="VERIFIED_POLICY_MATCH_NOT_EXECUTION",
            )
        )

    def attestation_history(self, provider_id: str) -> tuple[ContainmentAttestation, ...]:
        return tuple(copy.deepcopy(self._attestations.get(provider_id, ())))


def local_runtime_inventory() -> tuple[dict, ...]:
    """Observe executable names only; never claim an enforced boundary."""
    candidates = {
        ContainmentTier.HARDENED_CONTAINER: ("docker", "podman", "runc", "crun"),
        ContainmentTier.WASM_COMPONENT: ("wasmtime", "wasmer"),
        ContainmentTier.MICROVM: ("firecracker", "jailer"),
    }
    rows = [
        {
            "tier": ContainmentTier.IN_PROCESS.value,
            "observed_executables": (),
            "status": "POLICY_ONLY",
            "enforcement_kind": EnforcementKind.POLICY_ONLY.value,
            "claim_limit": "in-process policy check; not containment",
        }
    ]
    for tier, names in candidates.items():
        found = tuple((name, shutil.which(name)) for name in names if shutil.which(name))
        rows.append(
            {
                "tier": tier.value,
                "observed_executables": found,
                "status": "UNVERIFIED_EXECUTABLE_PRESENCE" if found else "UNAVAILABLE",
                "enforcement_kind": TIER_ENFORCEMENT[tier].value,
                "claim_limit": "inventory only; no enforced control or isolation proven",
            }
        )
    return tuple(rows)


__all__ = [
    "ContainmentAttestation",
    "ContainmentBroker",
    "ContainmentDecision",
    "ContainmentRefused",
    "ContainmentRequirement",
    "ContainmentTier",
    "EnforcementKind",
    "ProviderDeclaration",
    "local_runtime_inventory",
    "required_controls",
]
