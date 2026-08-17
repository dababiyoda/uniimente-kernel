"""Exact-version MCP/A2A admission into inert proposals.

Acceptance authenticates and normalizes an envelope.  It never authorizes,
routes to an executor, invokes a tool, calls the Consequence Gate, or creates a
grant.  Durable replay storage and sender resolution are mandatory injected
dependencies so outages fail closed.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Protocol

from moduleloader.frozen_contract import FrozenContractError, FrozenContractSchemas
from moduleloader.integrity import canonical_json, sha256_bytes


class BoundaryRefused(ValueError):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


class CapabilityAdvertisementLike(Protocol):
    capability_id: str

    def within(self, consequence_class: str) -> bool: ...


class CapabilityDirectoryLike(Protocol):
    def lookup(self, capability_id: str) -> CapabilityAdvertisementLike: ...


SenderResolver = Callable[[str], tuple[bool, str]]
ReplayRecorder = Callable[[tuple[str, str, str, str]], bool]


@dataclass(frozen=True)
class AdmittedProposal:
    """Immutable normalized evidence, deliberately lacking an execute method."""

    proposal_id: str
    protocol: str
    protocol_version: str
    envelope_id: str
    sender_identity: str
    payload_kind: str
    envelope_canonical_json: bytes
    identity_evidence: str
    replay_evidence: str
    disposition: str = "PROPOSAL"
    confers_authority: bool = False
    execution_eligible: bool = False
    requires_kernel_validation: bool = True

    @property
    def envelope(self) -> dict:
        return json.loads(self.envelope_canonical_json)

    @property
    def payload(self) -> dict:
        return copy.deepcopy(self.envelope["payload"])


def _aware_timestamp(value: str) -> datetime:
    if not isinstance(value, str):
        raise BoundaryRefused("INVALID_TIMESTAMP", "issued_at must be a string")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise BoundaryRefused("INVALID_TIMESTAMP", value) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise BoundaryRefused("INVALID_TIMESTAMP", "timezone is required")
    return parsed.astimezone(timezone.utc)


class ProposalBoundary:
    """Protocol-neutral admission core used by the narrow MCP/A2A adapters."""

    def __init__(
        self,
        *,
        capability_directory: CapabilityDirectoryLike,
        resolve_sender: SenderResolver,
        record_replay_key: ReplayRecorder,
        schemas: FrozenContractSchemas | None = None,
        max_age: timedelta = timedelta(minutes=5),
        max_future_skew: timedelta = timedelta(seconds=30),
    ):
        if not callable(getattr(capability_directory, "lookup", None)):
            raise BoundaryRefused("INVALID_POLICY", "directory.lookup is required")
        if not callable(resolve_sender):
            raise BoundaryRefused("INVALID_POLICY", "resolve_sender is required")
        if not callable(record_replay_key):
            raise BoundaryRefused("INVALID_POLICY", "durable replay recorder is required")
        if schemas is not None and not isinstance(schemas, FrozenContractSchemas):
            raise BoundaryRefused("INVALID_POLICY", "schemas must be FrozenContractSchemas")
        if not isinstance(max_age, timedelta) or max_age <= timedelta(0):
            raise BoundaryRefused("INVALID_POLICY", "max_age must be positive")
        if not isinstance(max_future_skew, timedelta) or max_future_skew < timedelta(0):
            raise BoundaryRefused("INVALID_POLICY", "max_future_skew cannot be negative")
        self._directory = capability_directory
        self._resolve_sender = resolve_sender
        self._record_replay_key = record_replay_key
        self._schemas = schemas or FrozenContractSchemas()
        self._max_age = max_age
        self._max_future_skew = max_future_skew

    def admit(
        self,
        document: dict,
        *,
        expected_protocol: str,
        now: datetime | None = None,
    ) -> AdmittedProposal:
        if expected_protocol not in {"mcp", "a2a"}:
            raise BoundaryRefused("UNKNOWN_PROTOCOL", str(expected_protocol))
        if not isinstance(document, dict):
            raise BoundaryRefused("INVALID_ENVELOPE", "top level must be an object")
        version = document.get("protocol_version")
        if version != "1.0.0":
            raise BoundaryRefused(
                "UNSUPPORTED_PROTOCOL_VERSION", f"expected 1.0.0, got {version!r}"
            )
        if document.get("protocol") != expected_protocol:
            raise BoundaryRefused(
                "PROTOCOL_MISMATCH",
                f"expected {expected_protocol!r}, got {document.get('protocol')!r}",
            )
        try:
            envelope = self._schemas.validate_boundary_envelope(document)
        except FrozenContractError as exc:
            raise BoundaryRefused("ENVELOPE_SCHEMA_REFUSED", exc.detail) from exc

        sender = envelope["sender"]
        method = sender.get("authentication_method")
        isolated = sender.get("identity_is_isolated")
        if sender["authenticated"] is not True:
            raise BoundaryRefused("SENDER_NOT_AUTHENTICATED", sender["identity"])
        if method == "hmac_shared_secret" and isolated is not False:
            raise BoundaryRefused(
                "SHARED_SECRET_NOT_ISOLATED",
                "shared HMAC identity must explicitly report identity_is_isolated=false",
            )
        if method == "mtls" and isolated is not True:
            raise BoundaryRefused(
                "ISOLATION_EVIDENCE_REQUIRED", "mTLS identity must report isolation"
            )
        if method in {None, "none"}:
            raise BoundaryRefused(
                "AUTHENTICATION_METHOD_REQUIRED", "authenticated identity needs evidence"
            )

        current = now or datetime.now(timezone.utc)
        if not isinstance(current, datetime) or current.tzinfo is None or current.utcoffset() is None:
            raise BoundaryRefused("INVALID_TIMESTAMP", "now must be timezone-aware")
        current = current.astimezone(timezone.utc)
        issued = _aware_timestamp(envelope["issued_at"])
        if issued > current + self._max_future_skew:
            raise BoundaryRefused("FUTURE_ENVELOPE", envelope["issued_at"])
        if current - issued > self._max_age:
            raise BoundaryRefused("STALE_ENVELOPE", envelope["issued_at"])

        try:
            identity_ok, identity_evidence = self._resolve_sender(sender["identity"])
        except Exception as exc:
            raise BoundaryRefused("IDENTITY_RESOLVER_UNAVAILABLE", type(exc).__name__) from exc
        if identity_ok is not True:
            raise BoundaryRefused("UNKNOWN_SENDER", str(identity_evidence))
        if not isinstance(identity_evidence, str) or not identity_evidence:
            raise BoundaryRefused(
                "IDENTITY_RESOLVER_INVALID", "success needs an evidence reference"
            )

        if envelope["payload_kind"] == "capability_request":
            try:
                request = self._schemas.validate_capability_request(envelope["payload"])
            except FrozenContractError as exc:
                raise BoundaryRefused("CAPABILITY_REQUEST_REFUSED", exc.detail) from exc
            if request["requested_by"] != sender["identity"]:
                raise BoundaryRefused(
                    "REQUESTER_IDENTITY_MISMATCH", request["requested_by"]
                )
            try:
                advertisement = self._directory.lookup(request["capability_id"])
                within = advertisement.within(request["consequence_class"])
            except Exception as exc:
                raise BoundaryRefused(
                    "UNKNOWN_CAPABILITY", request["capability_id"]
                ) from exc
            if within is not True:
                raise BoundaryRefused(
                    "CAPABILITY_CEILING_EXCEEDED", request["capability_id"]
                )

        replay_key = (
            expected_protocol,
            sender["identity"],
            envelope["envelope_id"],
            envelope["nonce"],
        )
        try:
            claimed = self._record_replay_key(replay_key)
        except Exception as exc:
            raise BoundaryRefused("REPLAY_STORE_UNAVAILABLE", type(exc).__name__) from exc
        if claimed is not True:
            raise BoundaryRefused("REPLAY_REFUSED", envelope["envelope_id"])

        canonical = canonical_json(envelope)
        return AdmittedProposal(
            proposal_id=sha256_bytes(canonical),
            protocol=expected_protocol,
            protocol_version="1.0.0",
            envelope_id=envelope["envelope_id"],
            sender_identity=sender["identity"],
            payload_kind=envelope["payload_kind"],
            envelope_canonical_json=canonical,
            identity_evidence=identity_evidence,
            replay_evidence=f"claimed:{expected_protocol}:{envelope['envelope_id']}",
        )


__all__ = ["AdmittedProposal", "BoundaryRefused", "ProposalBoundary"]
