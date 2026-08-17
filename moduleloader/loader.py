"""Inert governed module-lifecycle core.

The loader stores descriptors, artifact bytes, lifecycle eligibility, state
snapshots, comparisons, and append-only evidence.  It never imports module
code, invokes a module, calls the Consequence Gate, or mints a grant.  The
``activate`` state means only "eligible for an independently governed caller to
consider"; it is not execution authority.
"""
from __future__ import annotations

import base64
import copy
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Iterable, Protocol

from .integrity import (
    canonical_json,
    require_aware,
    sha256_bytes,
    sha256_json,
    utc_now,
    valid_sha256,
)
from .frozen_contract import FrozenContractError, FrozenContractSchemas


class LoaderRefused(ValueError):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


class Lifecycle(str, Enum):
    INSTALLED = "installed"
    ATTACHED = "attached"
    SHADOW = "shadow"
    ACTIVE = "active"
    PAUSED = "paused"
    SUPERSEDED = "superseded"
    DETACHED = "detached"
    ARCHIVED = "archived"


@dataclass(frozen=True)
class ModuleDescriptor:
    module_id: str
    module_principal: str
    version: str
    artifact_digest: str
    genome_ref: str
    state_schema_digest: str
    requested_consequence_class: str
    containment_tier: str
    capability_ids: tuple[str, ...]
    capability_requests: tuple[dict, ...] = ()

    @property
    def key(self) -> str:
        return f"{self.module_id}@{self.version}"

    @property
    def descriptor_digest(self) -> str:
        return sha256_json(
            {
                "module_id": self.module_id,
                "module_principal": self.module_principal,
                "version": self.version,
                "artifact_digest": self.artifact_digest,
                "genome_ref": self.genome_ref,
                "state_schema_digest": self.state_schema_digest,
                "requested_consequence_class": self.requested_consequence_class,
                "containment_tier": self.containment_tier,
                "capability_ids": list(self.capability_ids),
                "capability_requests": list(self.capability_requests),
            }
        )

    def validate_shape(self) -> list[str]:
        problems = []
        for name in (
            "module_id",
            "module_principal",
            "version",
            "genome_ref",
            "requested_consequence_class",
            "containment_tier",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                problems.append(f"{name} must be a non-empty string")
        for name in ("artifact_digest", "state_schema_digest"):
            if not valid_sha256(getattr(self, name)):
                problems.append(f"{name} must be a sha256 digest")
        if not isinstance(self.capability_ids, tuple) or not self.capability_ids:
            problems.append("capability_ids must be a non-empty tuple")
        elif not all(
            isinstance(capability_id, str) and capability_id
            for capability_id in self.capability_ids
        ):
            problems.append("capability_ids must contain non-empty strings")
        elif len(self.capability_ids) != len(set(self.capability_ids)):
            problems.append("capability_ids must be unique")
        if not isinstance(self.capability_requests, tuple):
            problems.append("capability_requests must be a tuple")
        elif len(self.capability_requests) != len(self.capability_ids):
            problems.append("one capability request is required per capability id")
        elif not all(isinstance(request, dict) for request in self.capability_requests):
            problems.append("capability_requests must contain objects")
        return problems


@dataclass(frozen=True)
class PinnedModule:
    """One predeclared artifact and descriptor pair.

    The allowlist is checked before any artifact is stored.  The loader never
    imports candidate code, so passing this check creates eligibility only.
    """

    module_key: str
    descriptor_digest: str
    artifact_digest: str

    def validate(self) -> None:
        if not isinstance(self.module_key, str) or not self.module_key:
            raise LoaderRefused("INVALID_ALLOWLIST", "module_key is required")
        if not valid_sha256(self.descriptor_digest):
            raise LoaderRefused("INVALID_ALLOWLIST", "descriptor_digest must be sha256")
        if not valid_sha256(self.artifact_digest):
            raise LoaderRefused("INVALID_ALLOWLIST", "artifact_digest must be sha256")


class CapabilityAdvertisementLike(Protocol):
    capability_id: str
    organ_status: str

    def within(self, consequence_class: str) -> bool: ...


class CapabilityDirectoryLike(Protocol):
    def lookup(self, capability_id: str) -> CapabilityAdvertisementLike: ...

    def offers(self, query: object | None = None) -> tuple[CapabilityAdvertisementLike, ...]: ...


@dataclass(frozen=True)
class ValidationReceipt:
    descriptor_digest: str
    artifact_digest: str
    genome_evidence: str
    validated_at: datetime
    receipt_digest: str

    def canonical_claim(self) -> dict:
        return {
            "descriptor_digest": self.descriptor_digest,
            "artifact_digest": self.artifact_digest,
            "genome_evidence": self.genome_evidence,
            "validated_at": require_aware(
                self.validated_at, "validated_at"
            ).isoformat(),
        }

    def verify(self) -> bool:
        try:
            return self.receipt_digest == sha256_json(self.canonical_claim())
        except (AttributeError, TypeError, ValueError):
            return False


@dataclass(frozen=True)
class ComparisonEvidence:
    incumbent_key: str
    candidate_key: str
    qualified: bool
    evidence_refs: tuple[str, ...]
    comparison_digest: str

    @classmethod
    def create(
        cls,
        *,
        incumbent_key: str,
        candidate_key: str,
        qualified: bool,
        evidence_refs: tuple[str, ...],
    ) -> "ComparisonEvidence":
        if not isinstance(incumbent_key, str) or not incumbent_key:
            raise LoaderRefused("INVALID_COMPARISON", "incumbent_key is required")
        if not isinstance(candidate_key, str) or not candidate_key:
            raise LoaderRefused("INVALID_COMPARISON", "candidate_key is required")
        if not isinstance(qualified, bool):
            raise LoaderRefused("INVALID_COMPARISON", "qualified must be a boolean")
        if not isinstance(evidence_refs, tuple) or not evidence_refs:
            raise LoaderRefused("MISSING_EVIDENCE", "comparison needs evidence refs")
        if not all(isinstance(ref, str) and ref for ref in evidence_refs):
            raise LoaderRefused(
                "INVALID_COMPARISON", "evidence refs must be non-empty strings"
            )
        digest = sha256_json(
            {
                "incumbent_key": incumbent_key,
                "candidate_key": candidate_key,
                "qualified": qualified,
                "evidence_refs": list(evidence_refs),
            }
        )
        return cls(incumbent_key, candidate_key, qualified, evidence_refs, digest)

    def verify(self) -> bool:
        try:
            return self.comparison_digest == sha256_json(
                {
                    "incumbent_key": self.incumbent_key,
                    "candidate_key": self.candidate_key,
                    "qualified": self.qualified,
                    "evidence_refs": list(self.evidence_refs),
                }
            )
        except (AttributeError, TypeError, ValueError):
            return False


@dataclass(frozen=True)
class StateSnapshot:
    snapshot_digest: str
    module_key: str
    state_schema_digest: str
    payload_b64: str
    created_by: str
    created_at: datetime

    def verify(self) -> bool:
        try:
            payload = base64.b64decode(self.payload_b64, validate=True)
            expected = sha256_json(
                {
                    "module_key": self.module_key,
                    "state_schema_digest": self.state_schema_digest,
                    "payload_digest": sha256_bytes(payload),
                    "created_by": self.created_by,
                    "created_at": require_aware(
                        self.created_at, "created_at"
                    ).isoformat(),
                }
            )
        except (AttributeError, TypeError, ValueError):
            return False
        return expected == self.snapshot_digest


@dataclass
class ModuleRecord:
    descriptor: ModuleDescriptor
    lifecycle: Lifecycle
    attachments: set[str] = field(default_factory=set)
    containment_attestation_ref: str | None = None
    fallback_key: str | None = None
    superseded_by: str | None = None
    comparison: ComparisonEvidence | None = None
    snapshots: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class LifecycleEvent:
    seq: int
    operation: str
    actor: str
    module_key: str
    before: str | None
    after: str | None
    detail: dict
    at: datetime
    previous_hash: str
    event_hash: str


AuthorityVerifier = Callable[[str, str, str, str], tuple[bool, str]]
GenomeVerifier = Callable[[ModuleDescriptor], tuple[bool, str]]
ContainmentResolver = Callable[[ModuleDescriptor], tuple[bool, str]]
Clock = Callable[[], datetime]


class GovernedModuleLoader:
    """Lifecycle controls eligibility, never authority or execution."""

    def __init__(
        self,
        *,
        verify_authority: AuthorityVerifier,
        verify_genome: GenomeVerifier,
        resolve_containment: ContainmentResolver,
        capability_directory: CapabilityDirectoryLike,
        allowlist: Iterable[PinnedModule],
        schemas: FrozenContractSchemas | None = None,
        validation_receipt_ttl: timedelta = timedelta(minutes=10),
        clock: Clock = utc_now,
    ):
        if not callable(verify_authority):
            raise LoaderRefused("INVALID_POLICY", "verify_authority must be callable")
        if not callable(verify_genome):
            raise LoaderRefused("INVALID_POLICY", "verify_genome must be callable")
        if not callable(resolve_containment):
            raise LoaderRefused("INVALID_POLICY", "resolve_containment must be callable")
        if not callable(clock):
            raise LoaderRefused("INVALID_POLICY", "clock must be callable")
        if not callable(getattr(capability_directory, "lookup", None)) or not callable(
            getattr(capability_directory, "offers", None)
        ):
            raise LoaderRefused(
                "INVALID_POLICY", "capability_directory must expose lookup and offers"
            )
        if isinstance(allowlist, (str, bytes)):
            raise LoaderRefused("INVALID_ALLOWLIST", "allowlist must contain pinned modules")
        try:
            pinned = tuple(allowlist)
        except TypeError as exc:
            raise LoaderRefused("INVALID_ALLOWLIST", "allowlist is not iterable") from exc
        if not pinned:
            raise LoaderRefused("INVALID_ALLOWLIST", "allowlist cannot be empty")
        for entry in pinned:
            if not isinstance(entry, PinnedModule):
                raise LoaderRefused("INVALID_ALLOWLIST", "wrong allowlist entry type")
            entry.validate()
        if len({entry.module_key for entry in pinned}) != len(pinned):
            raise LoaderRefused("INVALID_ALLOWLIST", "module keys must be unique")
        if schemas is not None and not isinstance(schemas, FrozenContractSchemas):
            raise LoaderRefused("INVALID_POLICY", "schemas must be FrozenContractSchemas")
        if not isinstance(validation_receipt_ttl, timedelta):
            raise LoaderRefused(
                "INVALID_POLICY", "validation receipt TTL must be a timedelta"
            )
        if validation_receipt_ttl <= timedelta(0):
            raise LoaderRefused("INVALID_POLICY", "validation receipt TTL must be positive")
        self._verify_authority = verify_authority
        self._verify_genome = verify_genome
        self._resolve_containment = resolve_containment
        self._capability_directory = capability_directory
        self._allowlist = {entry.module_key: entry for entry in pinned}
        self._schemas = schemas or FrozenContractSchemas()
        self._validation_receipt_ttl = validation_receipt_ttl
        self._clock = clock
        self._records: dict[str, ModuleRecord] = {}
        self._artifacts: dict[str, bytes] = {}
        self._snapshots: dict[str, StateSnapshot] = {}
        self._validation_receipts: dict[str, ValidationReceipt] = {}
        self._events: list[LifecycleEvent] = []
        self._event_head = "sha256:" + "0" * 64

    def _validate_pinned(self, descriptor: ModuleDescriptor, artifact_digest: str) -> None:
        pinned = self._allowlist.get(descriptor.key)
        if pinned is None:
            raise LoaderRefused("MODULE_NOT_ALLOWLISTED", descriptor.key)
        if pinned.descriptor_digest != descriptor.descriptor_digest:
            raise LoaderRefused(
                "ALLOWLIST_DESCRIPTOR_MISMATCH",
                f"{descriptor.key} descriptor differs from the pinned declaration",
            )
        if pinned.artifact_digest != artifact_digest:
            raise LoaderRefused(
                "ALLOWLIST_ARTIFACT_MISMATCH",
                f"{descriptor.key} artifact differs from the pinned declaration",
            )

    def _validate_requests_and_directory(self, descriptor: ModuleDescriptor) -> None:
        validated: list[dict] = []
        for request in descriptor.capability_requests:
            try:
                validated.append(self._schemas.validate_capability_request(request))
            except FrozenContractError as exc:
                raise LoaderRefused("CAPABILITY_REQUEST_REFUSED", exc.detail) from exc
        request_ids = tuple(request["capability_id"] for request in validated)
        if request_ids != descriptor.capability_ids:
            raise LoaderRefused(
                "CAPABILITY_REQUEST_MISMATCH",
                "request order and ids must exactly match capability_ids",
            )
        try:
            attached = {advertisement.capability_id for advertisement in self._capability_directory.offers()}
        except Exception as exc:
            raise LoaderRefused("DISCOVERY_UNAVAILABLE", type(exc).__name__) from exc
        for request in validated:
            capability_id = request["capability_id"]
            if request["requested_by"] != descriptor.module_principal:
                raise LoaderRefused(
                    "CAPABILITY_REQUESTER_MISMATCH", capability_id
                )
            if request["consequence_class"] != descriptor.requested_consequence_class:
                raise LoaderRefused(
                    "CONSEQUENCE_CLASS_MISMATCH", capability_id
                )
            try:
                advertisement = self._capability_directory.lookup(capability_id)
                within = advertisement.within(descriptor.requested_consequence_class)
            except Exception as exc:
                raise LoaderRefused("UNKNOWN_CAPABILITY", capability_id) from exc
            if capability_id not in attached:
                raise LoaderRefused("CAPABILITY_NOT_ATTACHED", capability_id)
            if within is not True:
                raise LoaderRefused("CAPABILITY_CEILING_EXCEEDED", capability_id)

    def _event(
        self,
        operation: str,
        actor: str,
        module_key: str,
        before: Lifecycle | None,
        after: Lifecycle | None,
        detail: dict | None = None,
        *,
        at: datetime,
    ) -> LifecycleEvent:
        detail = copy.deepcopy(detail or {})
        at = require_aware(at, "event time")
        body = {
            "seq": len(self._events),
            "operation": operation,
            "actor": actor,
            "module_key": module_key,
            "before": before.value if before else None,
            "after": after.value if after else None,
            "detail": detail,
            "at": at.isoformat(),
            "previous_hash": self._event_head,
        }
        event_hash = sha256_json(body)
        event = LifecycleEvent(
            seq=len(self._events),
            operation=operation,
            actor=actor,
            module_key=module_key,
            before=body["before"],
            after=body["after"],
            detail=detail,
            at=at,
            previous_hash=self._event_head,
            event_hash=event_hash,
        )
        self._events.append(event)
        self._event_head = event_hash
        return event

    def _event_time(self) -> datetime:
        try:
            return require_aware(self._clock(), "clock")
        except Exception as exc:
            raise LoaderRefused("CLOCK_UNAVAILABLE", type(exc).__name__) from exc

    def _record(self, key: str) -> ModuleRecord:
        if not isinstance(key, str) or not key:
            raise LoaderRefused("INVALID_MODULE_KEY", "module key must be a string")
        try:
            return self._records[key]
        except KeyError as exc:
            raise LoaderRefused("UNKNOWN_MODULE", key) from exc

    def _verify_artifact(self, record: ModuleRecord) -> None:
        artifact = self._artifacts.get(record.descriptor.artifact_digest)
        if artifact is None:
            raise LoaderRefused("ARTIFACT_MISSING", record.descriptor.artifact_digest)
        actual = sha256_bytes(artifact)
        if actual != record.descriptor.artifact_digest:
            raise LoaderRefused(
                "ARTIFACT_DIGEST_MISMATCH",
                f"declared {record.descriptor.artifact_digest}, actual {actual}",
            )

    @staticmethod
    def _deny_self(actor: str, descriptor: ModuleDescriptor) -> None:
        if actor in {descriptor.module_id, descriptor.module_principal, descriptor.key}:
            raise LoaderRefused(
                "SELF_MANAGEMENT_REFUSED",
                f"{descriptor.key} cannot manage its own lifecycle",
            )

    def _authorize(
        self,
        *,
        actor: str,
        authority_ref: str,
        operation: str,
        target: str,
        descriptor: ModuleDescriptor,
    ) -> None:
        if not isinstance(actor, str) or not actor:
            raise LoaderRefused("INVALID_ACTOR", operation)
        if not isinstance(authority_ref, str) or not authority_ref:
            raise LoaderRefused("MISSING_AUTHORITY_REFERENCE", operation)
        self._deny_self(actor, descriptor)
        try:
            allowed, reason = self._verify_authority(
                actor, authority_ref, operation, target
            )
        except Exception as exc:
            raise LoaderRefused(
                "AUTHORITY_VERIFIER_FAILED", type(exc).__name__
            ) from exc
        if allowed is not True:
            raise LoaderRefused("AUTHORITY_REFUSED", reason)

    def _verify_genome_claim(self, descriptor: ModuleDescriptor) -> str:
        try:
            genome_ok, genome_evidence = self._verify_genome(descriptor)
        except Exception as exc:
            raise LoaderRefused("GENOME_VERIFIER_FAILED", type(exc).__name__) from exc
        if genome_ok is not True:
            raise LoaderRefused("GENOME_REFUSED", str(genome_evidence))
        if not isinstance(genome_evidence, str) or not genome_evidence:
            raise LoaderRefused(
                "GENOME_VERIFIER_FAILED",
                "successful verification requires a non-empty evidence reference",
            )
        return genome_evidence

    def _containment_evidence(self, descriptor: ModuleDescriptor) -> str:
        try:
            containment_ok, containment_evidence = self._resolve_containment(descriptor)
        except Exception as exc:
            raise LoaderRefused(
                "CONTAINMENT_VERIFIER_FAILED", type(exc).__name__
            ) from exc
        if containment_ok is not True:
            raise LoaderRefused("CONTAINMENT_UNAVAILABLE", str(containment_evidence))
        if not isinstance(containment_evidence, str) or not containment_evidence:
            raise LoaderRefused(
                "CONTAINMENT_VERIFIER_FAILED",
                "successful selection requires a non-empty evidence reference",
            )
        return containment_evidence

    def validate(
        self, descriptor: ModuleDescriptor, artifact: bytes
    ) -> ValidationReceipt:
        if not isinstance(descriptor, ModuleDescriptor):
            raise LoaderRefused("INVALID_DESCRIPTOR", "wrong descriptor type")
        problems = descriptor.validate_shape()
        if problems:
            raise LoaderRefused("INVALID_DESCRIPTOR", str(problems))
        if not isinstance(artifact, (bytes, bytearray, memoryview)):
            raise LoaderRefused("INVALID_ARTIFACT", "artifact must be bytes-like")
        artifact_bytes = bytes(artifact)
        actual_digest = sha256_bytes(artifact_bytes)
        if descriptor.artifact_digest != actual_digest:
            raise LoaderRefused(
                "ARTIFACT_DIGEST_MISMATCH",
                f"declared {descriptor.artifact_digest}, actual {actual_digest}",
            )
        # The predeclared allowlist and discovery contract are checked before
        # storage and before any lifecycle eligibility is issued.  This loader
        # has no candidate-code import primitive at any later point either.
        self._validate_pinned(descriptor, actual_digest)
        self._validate_requests_and_directory(descriptor)
        genome_evidence = self._verify_genome_claim(descriptor)
        validated_at = self._event_time()
        claim = {
            "descriptor_digest": descriptor.descriptor_digest,
            "artifact_digest": actual_digest,
            "genome_evidence": genome_evidence,
            "validated_at": validated_at.isoformat(),
        }
        receipt = ValidationReceipt(
            descriptor_digest=descriptor.descriptor_digest,
            artifact_digest=actual_digest,
            genome_evidence=genome_evidence,
            validated_at=validated_at,
            receipt_digest=sha256_json(claim),
        )
        self._validation_receipts[receipt.receipt_digest] = receipt
        return receipt

    def install(
        self,
        descriptor: ModuleDescriptor,
        artifact: bytes,
        receipt: ValidationReceipt,
        *,
        actor: str,
        authority_ref: str,
    ) -> ModuleRecord:
        if not isinstance(descriptor, ModuleDescriptor):
            raise LoaderRefused("INVALID_DESCRIPTOR", "wrong descriptor type")
        problems = descriptor.validate_shape()
        if problems:
            raise LoaderRefused("INVALID_DESCRIPTOR", str(problems))
        if not isinstance(artifact, (bytes, bytearray, memoryview)):
            raise LoaderRefused("INVALID_ARTIFACT", "artifact must be bytes-like")
        if not isinstance(receipt, ValidationReceipt):
            raise LoaderRefused(
                "INVALID_VALIDATION_RECEIPT", "receipt has the wrong type"
            )
        artifact_bytes = bytes(artifact)
        actual_digest = sha256_bytes(artifact_bytes)
        self._validate_pinned(descriptor, actual_digest)
        self._validate_requests_and_directory(descriptor)
        self._authorize(
            actor=actor,
            authority_ref=authority_ref,
            operation="module.install",
            target=descriptor.key,
            descriptor=descriptor,
        )
        if not receipt.verify():
            raise LoaderRefused(
                "INVALID_VALIDATION_RECEIPT", "receipt digest does not match its claim"
            )
        issued_receipt = self._validation_receipts.get(receipt.receipt_digest)
        if issued_receipt != receipt:
            raise LoaderRefused(
                "UNKNOWN_VALIDATION_RECEIPT",
                "receipt was not issued by this loader instance",
            )
        if receipt.descriptor_digest != descriptor.descriptor_digest:
            raise LoaderRefused("STALE_VALIDATION", "descriptor changed after validation")
        if receipt.artifact_digest != sha256_bytes(artifact_bytes):
            raise LoaderRefused("STALE_VALIDATION", "artifact changed after validation")
        validated_at = require_aware(receipt.validated_at, "validated_at")
        now = self._event_time()
        if validated_at > now or now - validated_at > self._validation_receipt_ttl:
            raise LoaderRefused("STALE_VALIDATION", "validation receipt is not current")
        genome_evidence = self._verify_genome_claim(descriptor)
        prior = self._records.get(descriptor.key)
        if prior is not None:
            if prior.descriptor != descriptor:
                raise LoaderRefused(
                    "VERSION_COLLISION", "same module version has different descriptor"
                )
            return copy.deepcopy(prior)
        self._artifacts[descriptor.artifact_digest] = artifact_bytes
        record = ModuleRecord(
            descriptor=copy.deepcopy(descriptor), lifecycle=Lifecycle.INSTALLED
        )
        self._records[descriptor.key] = record
        self._event(
            "install",
            actor,
            descriptor.key,
            None,
            Lifecycle.INSTALLED,
            {
                "descriptor_digest": descriptor.descriptor_digest,
                "artifact_digest": descriptor.artifact_digest,
                "genome_evidence": receipt.genome_evidence,
                "install_genome_evidence": genome_evidence,
                "validated_at": validated_at.isoformat(),
                "execution": "none",
            },
            at=now,
        )
        return copy.deepcopy(record)

    def inspect(self, key: str) -> ModuleRecord:
        return copy.deepcopy(self._record(key))

    def attach(
        self, key: str, target: str, *, actor: str, authority_ref: str
    ) -> ModuleRecord:
        record = self._record(key)
        if not isinstance(target, str) or not target:
            raise LoaderRefused("MISSING_TARGET", key)
        self._authorize(
            actor=actor,
            authority_ref=authority_ref,
            operation="module.attach",
            target=f"{key}:{target}",
            descriptor=record.descriptor,
        )
        if record.lifecycle not in {Lifecycle.INSTALLED, Lifecycle.DETACHED}:
            raise LoaderRefused("ILLEGAL_TRANSITION", f"{record.lifecycle} -> attached")
        event_at = self._event_time()
        before = record.lifecycle
        record.attachments.add(target)
        record.comparison = None
        record.lifecycle = Lifecycle.ATTACHED
        self._event(
            "attach",
            actor,
            key,
            before,
            record.lifecycle,
            {"target": target},
            at=event_at,
        )
        return copy.deepcopy(record)

    def activate(self, key: str, *, actor: str, authority_ref: str) -> ModuleRecord:
        record = self._record(key)
        self._authorize(
            actor=actor,
            authority_ref=authority_ref,
            operation="module.activate_eligibility",
            target=key,
            descriptor=record.descriptor,
        )
        if record.lifecycle not in {Lifecycle.ATTACHED, Lifecycle.PAUSED}:
            raise LoaderRefused("ILLEGAL_TRANSITION", f"{record.lifecycle} -> active")
        self._verify_artifact(record)
        containment_evidence = self._containment_evidence(record.descriptor)
        event_at = self._event_time()
        before = record.lifecycle
        record.lifecycle = Lifecycle.ACTIVE
        record.containment_attestation_ref = containment_evidence
        self._event(
            "activate_eligibility",
            actor,
            key,
            before,
            record.lifecycle,
            {
                "containment_attestation_ref": containment_evidence,
                "authority_created": False,
                "execution": "none",
            },
            at=event_at,
        )
        return copy.deepcopy(record)

    def pause(self, key: str, *, actor: str, authority_ref: str) -> ModuleRecord:
        record = self._record(key)
        self._authorize(
            actor=actor,
            authority_ref=authority_ref,
            operation="module.pause",
            target=key,
            descriptor=record.descriptor,
        )
        if record.lifecycle != Lifecycle.ACTIVE:
            raise LoaderRefused("ILLEGAL_TRANSITION", f"{record.lifecycle} -> paused")
        event_at = self._event_time()
        record.lifecycle = Lifecycle.PAUSED
        self._event(
            "pause",
            actor,
            key,
            Lifecycle.ACTIVE,
            Lifecycle.PAUSED,
            at=event_at,
        )
        return copy.deepcopy(record)

    def shadow(self, key: str, *, actor: str, authority_ref: str) -> ModuleRecord:
        record = self._record(key)
        self._authorize(
            actor=actor,
            authority_ref=authority_ref,
            operation="module.shadow_eligibility",
            target=key,
            descriptor=record.descriptor,
        )
        if record.lifecycle not in {Lifecycle.ATTACHED, Lifecycle.PAUSED}:
            raise LoaderRefused("ILLEGAL_TRANSITION", f"{record.lifecycle} -> shadow")
        self._verify_artifact(record)
        containment_evidence = self._containment_evidence(record.descriptor)
        event_at = self._event_time()
        before = record.lifecycle
        record.comparison = None
        record.lifecycle = Lifecycle.SHADOW
        record.containment_attestation_ref = containment_evidence
        self._event(
            "shadow_eligibility",
            actor,
            key,
            before,
            Lifecycle.SHADOW,
            {"execution": "none", "containment_attestation_ref": containment_evidence},
            at=event_at,
        )
        return copy.deepcopy(record)

    def compare(
        self,
        evidence: ComparisonEvidence,
        *,
        actor: str,
        authority_ref: str,
    ) -> ComparisonEvidence:
        if not isinstance(evidence, ComparisonEvidence):
            raise LoaderRefused("INVALID_COMPARISON", "wrong evidence type")
        incumbent = self._record(evidence.incumbent_key)
        candidate = self._record(evidence.candidate_key)
        if not evidence.verify():
            raise LoaderRefused("COMPARISON_DIGEST_MISMATCH", evidence.candidate_key)
        self._authorize(
            actor=actor,
            authority_ref=authority_ref,
            operation="module.compare_record",
            target=f"{evidence.incumbent_key}->{evidence.candidate_key}",
            descriptor=candidate.descriptor,
        )
        if incumbent.lifecycle != Lifecycle.ACTIVE:
            raise LoaderRefused("INCUMBENT_NOT_ACTIVE", evidence.incumbent_key)
        if candidate.lifecycle != Lifecycle.SHADOW:
            raise LoaderRefused("CANDIDATE_NOT_SHADOW", evidence.candidate_key)
        event_at = self._event_time()
        candidate.comparison = evidence
        self._event(
            "compare_record",
            actor,
            candidate.descriptor.key,
            Lifecycle.SHADOW,
            Lifecycle.SHADOW,
            {
                "incumbent": incumbent.descriptor.key,
                "qualified": evidence.qualified,
                "comparison_digest": evidence.comparison_digest,
                "evidence_refs": list(evidence.evidence_refs),
            },
            at=event_at,
        )
        return evidence

    def replace(
        self,
        incumbent_key: str,
        candidate_key: str,
        *,
        actor: str,
        authority_ref: str,
    ) -> tuple[ModuleRecord, ModuleRecord]:
        incumbent = self._record(incumbent_key)
        candidate = self._record(candidate_key)
        self._authorize(
            actor=actor,
            authority_ref=authority_ref,
            operation="module.replace_eligibility",
            target=f"{incumbent_key}->{candidate_key}",
            descriptor=candidate.descriptor,
        )
        if incumbent.lifecycle != Lifecycle.ACTIVE:
            raise LoaderRefused("INCUMBENT_NOT_ACTIVE", incumbent_key)
        if candidate.lifecycle != Lifecycle.SHADOW:
            raise LoaderRefused("CANDIDATE_NOT_SHADOW", candidate_key)
        if candidate.comparison is None or not candidate.comparison.qualified:
            raise LoaderRefused("COMPARISON_NOT_QUALIFIED", candidate_key)
        if not candidate.comparison.verify():
            raise LoaderRefused("COMPARISON_DIGEST_MISMATCH", candidate_key)
        if candidate.comparison.incumbent_key != incumbent_key:
            raise LoaderRefused("COMPARISON_TARGET_MISMATCH", incumbent_key)
        if incumbent.descriptor.module_id != candidate.descriptor.module_id:
            raise LoaderRefused("MODULE_ID_MISMATCH", candidate_key)
        if incumbent.attachments != candidate.attachments:
            raise LoaderRefused("ATTACHMENT_SCOPE_MISMATCH", candidate_key)
        if (
            incumbent.descriptor.state_schema_digest
            != candidate.descriptor.state_schema_digest
        ):
            raise LoaderRefused(
                "STATE_ADAPTER_REQUIRED",
                "schema-changing replacement needs an explicit, exact, reversible "
                "adapter bound by the frozen contract",
            )
        self._verify_artifact(candidate)
        containment_evidence = self._containment_evidence(candidate.descriptor)
        event_at = self._event_time()
        incumbent.lifecycle = Lifecycle.SUPERSEDED
        incumbent.superseded_by = candidate_key
        candidate.lifecycle = Lifecycle.ACTIVE
        candidate.fallback_key = incumbent_key
        candidate.containment_attestation_ref = containment_evidence
        self._event(
            "replace_eligibility",
            actor,
            candidate_key,
            Lifecycle.SHADOW,
            Lifecycle.ACTIVE,
            {
                "fallback_key": incumbent_key,
                "predecessor_preserved": True,
                "comparison_digest": candidate.comparison.comparison_digest,
                "execution": "none",
            },
            at=event_at,
        )
        return copy.deepcopy(incumbent), copy.deepcopy(candidate)

    def rollback(self, key: str, *, actor: str, authority_ref: str) -> tuple[ModuleRecord, ModuleRecord]:
        candidate = self._record(key)
        if candidate.lifecycle != Lifecycle.ACTIVE or not candidate.fallback_key:
            raise LoaderRefused("NO_ROLLBACK_TARGET", key)
        fallback = self._record(candidate.fallback_key)
        self._authorize(
            actor=actor,
            authority_ref=authority_ref,
            operation="module.rollback_eligibility",
            target=f"{key}->{fallback.descriptor.key}",
            descriptor=candidate.descriptor,
        )
        if fallback.lifecycle != Lifecycle.SUPERSEDED:
            raise LoaderRefused("ROLLBACK_TARGET_NOT_PRESERVED", fallback.descriptor.key)
        self._verify_artifact(fallback)
        containment_evidence = self._containment_evidence(fallback.descriptor)
        event_at = self._event_time()
        candidate.lifecycle = Lifecycle.SUPERSEDED
        candidate.superseded_by = fallback.descriptor.key
        fallback.lifecycle = Lifecycle.ACTIVE
        fallback.superseded_by = None
        fallback.containment_attestation_ref = containment_evidence
        self._event(
            "rollback_eligibility",
            actor,
            key,
            Lifecycle.ACTIVE,
            Lifecycle.SUPERSEDED,
            {
                "restored_key": fallback.descriptor.key,
                "failed_candidate_preserved": True,
                "execution": "none",
            },
            at=event_at,
        )
        return copy.deepcopy(candidate), copy.deepcopy(fallback)

    def detach(self, key: str, *, actor: str, authority_ref: str) -> ModuleRecord:
        record = self._record(key)
        self._authorize(
            actor=actor,
            authority_ref=authority_ref,
            operation="module.detach",
            target=key,
            descriptor=record.descriptor,
        )
        if record.lifecycle == Lifecycle.DETACHED:
            return copy.deepcopy(record)
        if record.lifecycle not in {
            Lifecycle.INSTALLED,
            Lifecycle.ATTACHED,
            Lifecycle.ACTIVE,
            Lifecycle.PAUSED,
            Lifecycle.SHADOW,
            Lifecycle.SUPERSEDED,
        }:
            raise LoaderRefused("ILLEGAL_TRANSITION", f"{record.lifecycle} -> detached")
        event_at = self._event_time()
        before = record.lifecycle
        prior_targets = sorted(record.attachments)
        record.attachments.clear()
        record.comparison = None
        record.lifecycle = Lifecycle.DETACHED
        self._event(
            "detach",
            actor,
            key,
            before,
            Lifecycle.DETACHED,
            {
                "prior_targets": prior_targets,
                "artifact_preserved": True,
                "forced_quiescence": before == Lifecycle.ACTIVE,
                "module_veto_available": False,
            },
            at=event_at,
        )
        return copy.deepcopy(record)

    def export_state(
        self,
        key: str,
        payload: bytes,
        *,
        actor: str,
        authority_ref: str,
    ) -> StateSnapshot:
        record = self._record(key)
        if not isinstance(payload, (bytes, bytearray, memoryview)):
            raise LoaderRefused("INVALID_STATE", "state payload must be bytes-like")
        payload_bytes = bytes(payload)
        self._authorize(
            actor=actor,
            authority_ref=authority_ref,
            operation="module.export_state",
            target=key,
            descriptor=record.descriptor,
        )
        if record.lifecycle not in {Lifecycle.PAUSED, Lifecycle.DETACHED}:
            raise LoaderRefused("QUIESCENCE_REQUIRED", record.lifecycle.value)
        created_at = self._event_time()
        digest = sha256_json(
            {
                "module_key": key,
                "state_schema_digest": record.descriptor.state_schema_digest,
                "payload_digest": sha256_bytes(payload_bytes),
                "created_by": actor,
                "created_at": created_at.isoformat(),
            }
        )
        snapshot = StateSnapshot(
            snapshot_digest=digest,
            module_key=key,
            state_schema_digest=record.descriptor.state_schema_digest,
            payload_b64=base64.b64encode(payload_bytes).decode("ascii"),
            created_by=actor,
            created_at=created_at,
        )
        self._snapshots[digest] = snapshot
        if digest not in record.snapshots:
            record.snapshots.append(digest)
        self._event(
            "export_state",
            actor,
            key,
            record.lifecycle,
            record.lifecycle,
            {"snapshot_digest": digest, "content_addressed": True},
            at=created_at,
        )
        return snapshot

    def import_state(
        self,
        key: str,
        snapshot: StateSnapshot,
        *,
        actor: str,
        authority_ref: str,
    ) -> bytes:
        record = self._record(key)
        if not isinstance(snapshot, StateSnapshot):
            raise LoaderRefused("INVALID_STATE", "snapshot has the wrong type")
        self._authorize(
            actor=actor,
            authority_ref=authority_ref,
            operation="module.import_state",
            target=key,
            descriptor=record.descriptor,
        )
        if record.lifecycle not in {Lifecycle.PAUSED, Lifecycle.DETACHED}:
            raise LoaderRefused("QUIESCENCE_REQUIRED", record.lifecycle.value)
        if not snapshot.verify():
            raise LoaderRefused("SNAPSHOT_DIGEST_MISMATCH", snapshot.snapshot_digest)
        if snapshot.module_key != key:
            raise LoaderRefused("SNAPSHOT_MODULE_MISMATCH", snapshot.module_key)
        if snapshot.state_schema_digest != record.descriptor.state_schema_digest:
            raise LoaderRefused("STATE_SCHEMA_MISMATCH", snapshot.state_schema_digest)
        if snapshot.snapshot_digest not in self._snapshots:
            raise LoaderRefused("UNKNOWN_SNAPSHOT", snapshot.snapshot_digest)
        event_at = self._event_time()
        self._event(
            "import_state",
            actor,
            key,
            record.lifecycle,
            record.lifecycle,
            {"snapshot_digest": snapshot.snapshot_digest, "execution": "none"},
            at=event_at,
        )
        return base64.b64decode(snapshot.payload_b64, validate=True)

    def archive(self, key: str, *, actor: str, authority_ref: str) -> ModuleRecord:
        record = self._record(key)
        self._authorize(
            actor=actor,
            authority_ref=authority_ref,
            operation="module.archive",
            target=key,
            descriptor=record.descriptor,
        )
        if record.lifecycle != Lifecycle.DETACHED:
            raise LoaderRefused("DETACH_REQUIRED", record.lifecycle.value)
        event_at = self._event_time()
        record.lifecycle = Lifecycle.ARCHIVED
        self._event(
            "archive",
            actor,
            key,
            Lifecycle.DETACHED,
            Lifecycle.ARCHIVED,
            {"artifact_preserved": True, "snapshots_preserved": list(record.snapshots)},
            at=event_at,
        )
        return copy.deepcopy(record)

    def restore(self, key: str, *, actor: str, authority_ref: str) -> ModuleRecord:
        record = self._record(key)
        self._authorize(
            actor=actor,
            authority_ref=authority_ref,
            operation="module.restore",
            target=key,
            descriptor=record.descriptor,
        )
        if record.lifecycle != Lifecycle.ARCHIVED:
            raise LoaderRefused("ILLEGAL_TRANSITION", f"{record.lifecycle} -> detached")
        self._verify_artifact(record)
        event_at = self._event_time()
        record.lifecycle = Lifecycle.DETACHED
        self._event(
            "restore",
            actor,
            key,
            Lifecycle.ARCHIVED,
            Lifecycle.DETACHED,
            {"activation": False, "artifact_preserved": True},
            at=event_at,
        )
        return copy.deepcopy(record)

    def verify_event_chain(self) -> tuple[bool, str]:
        previous = "sha256:" + "0" * 64
        for seq, event in enumerate(self._events):
            if event.seq != seq or event.previous_hash != previous:
                return False, f"chain break at {seq}"
            body = {
                "seq": event.seq,
                "operation": event.operation,
                "actor": event.actor,
                "module_key": event.module_key,
                "before": event.before,
                "after": event.after,
                "detail": event.detail,
                "at": event.at.isoformat(),
                "previous_hash": event.previous_hash,
            }
            if sha256_json(body) != event.event_hash:
                return False, f"payload mismatch at {seq}"
            previous = event.event_hash
        return True, f"chain intact: {len(self._events)} events"

    @property
    def events(self) -> tuple[LifecycleEvent, ...]:
        return tuple(copy.deepcopy(self._events))
