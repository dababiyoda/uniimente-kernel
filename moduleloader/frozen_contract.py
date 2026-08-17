"""Read-only access to the digest-sealed Part 1 handoff schemas.

The schema files remain Claude-owned.  Part 2 verifies their exact bytes before
using them and never edits, widens, or shadows them.  This module contains no
import or execution mechanism for candidate modules.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


BUNDLE_DIGEST = "fe1556048a9ca60f5956388adb9ddb81cbf060491b1fc8f38c6e2892e42d2c0c"

SCHEMA_DIGESTS = {
    "boundary-envelope": "3e8e74667f29a5242b142f971cde7746cff220df2310150e2bfa19b7ddf6d5da",
    "capability-request": "db990caf58975adfd0931f9a8f84be1291d0d8fb860f535f06343ea13ef09145",
    "containment-requirement": "618a17cbc8f0b67c707969a265b49222dd0a5f72a003f35389a917c4e166ed1b",
    "evidence-record": "e04ccede64c32f369f58b61531f2e9bbb87b8fac8dbec1e82ab77e6e7ce92de9",
}


class FrozenContractError(ValueError):
    """The frozen contract is unavailable, altered, or rejects a document."""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _canonical_json(value: Any) -> bytes:
    try:
        return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    except (TypeError, ValueError, RecursionError) as exc:
        raise FrozenContractError("INVALID_JSON", type(exc).__name__) from exc


class FrozenContractSchemas:
    """Lazy, hash-pinned validators for the four frozen Part 2 schemas."""

    def __init__(self, repository_root: str | Path | None = None):
        root = Path(repository_root) if repository_root else Path(__file__).resolve().parents[1]
        self._schema_root = root / "handoff" / "schemas"
        self._validators: dict[str, Draft202012Validator] = {}

    def _validator(self, schema_name: str) -> Draft202012Validator:
        if schema_name not in SCHEMA_DIGESTS:
            raise FrozenContractError("UNKNOWN_SCHEMA", schema_name)
        existing = self._validators.get(schema_name)
        if existing is not None:
            return existing
        path = self._schema_root / f"{schema_name}.schema.json"
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise FrozenContractError("SCHEMA_UNAVAILABLE", str(path)) from exc
        actual = hashlib.sha256(raw).hexdigest()
        expected = SCHEMA_DIGESTS[schema_name]
        if actual != expected:
            raise FrozenContractError(
                "SCHEMA_DIGEST_MISMATCH",
                f"{schema_name}: expected {expected}, got {actual}",
            )
        try:
            schema = json.loads(raw)
            Draft202012Validator.check_schema(schema)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise FrozenContractError("INVALID_SCHEMA", schema_name) from exc
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        self._validators[schema_name] = validator
        return validator

    def validate(self, schema_name: str, document: Any) -> dict[str, Any]:
        if not isinstance(document, dict):
            raise FrozenContractError("INVALID_DOCUMENT", "top level must be an object")
        try:
            frozen = json.loads(_canonical_json(document))
        except json.JSONDecodeError as exc:  # pragma: no cover, canonical JSON is valid
            raise FrozenContractError("INVALID_JSON", "round-trip failed") from exc
        errors = sorted(
            self._validator(schema_name).iter_errors(frozen),
            key=lambda error: (tuple(str(part) for part in error.absolute_path), error.message),
        )
        if errors:
            error = errors[0]
            location = ".".join(str(part) for part in error.absolute_path) or "$"
            raise FrozenContractError(
                "SCHEMA_REFUSED", f"{schema_name} at {location}: {error.message}"
            )
        return copy.deepcopy(frozen)

    def validate_capability_request(self, document: Any) -> dict[str, Any]:
        return self.validate("capability-request", document)

    def validate_boundary_envelope(self, document: Any) -> dict[str, Any]:
        return self.validate("boundary-envelope", document)

    def validate_containment_requirement(self, document: Any) -> dict[str, Any]:
        return self.validate("containment-requirement", document)

    def validate_evidence_record(self, document: Any) -> dict[str, Any]:
        return self.validate("evidence-record", document)


__all__ = [
    "BUNDLE_DIGEST",
    "FrozenContractError",
    "FrozenContractSchemas",
    "SCHEMA_DIGESTS",
]
