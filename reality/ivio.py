"""IVIO v1 deterministic instruction compiler and content integrity profile.

This module is deliberately smaller than a policy engine. It converts one
validated intent into one immutable, hash-bound instruction. It does not
approve, grant, execute, settle, or infer missing authority.

``UNIIMENTE-C14N-v1`` is a conservative JSON profile inspired by RFC 8785:
objects have ASCII string keys, numbers are safe-range integers, floats are
forbidden, keys are sorted, and UTF-8 is emitted without insignificant
whitespace. The narrower profile is intentional: money uses integer minor
units, and cross-language hashing never depends on floating-point rendering.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

CANONICALIZATION_PROFILE = "UNIIMENTE-C14N-v1"
MAX_SAFE_INTEGER = 9_007_199_254_740_991
MAX_TTL_SECONDS = 86_400
SPIFFE_PREFIX = "spiffe://uniimente.internal/"
ACTION_RE = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
TYPED_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{1,31}:[A-Za-z0-9._~-]{1,128}$")
LEGAL_PRINCIPAL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{1,127}$")


class CompileError(ValueError):
    """The intent cannot be lowered safely into an IVIO instruction."""


def _plain_json(value: Any, path: str = "$") -> None:
    """Enforce the deterministic, least-surprise JSON subset."""
    if value is None or isinstance(value, (str, bool)):
        return
    if isinstance(value, int) and not isinstance(value, bool):
        if abs(value) > MAX_SAFE_INTEGER:
            raise CompileError(f"{path}: integer exceeds cross-language safe range")
        return
    if isinstance(value, float):
        raise CompileError(f"{path}: floating-point values are forbidden; use integer minor units")
    if isinstance(value, list):
        for index, item in enumerate(value):
            _plain_json(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise CompileError(f"{path}: object keys must be strings")
            if not key or not key.isascii() or any(not 0x20 <= ord(ch) <= 0x7E for ch in key):
                raise CompileError(f"{path}: object keys must be printable ASCII")
            _plain_json(item, f"{path}.{key}")
        return
    raise CompileError(f"{path}: unsupported JSON value {type(value).__name__}")


def canonical_json_bytes(document: Mapping[str, Any] | list[Any]) -> bytes:
    """Return deterministic UTF-8 bytes under ``UNIIMENTE-C14N-v1``."""
    _plain_json(document)
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def content_digest(document: Mapping[str, Any], *, omit_integrity: bool = True) -> str:
    """Hash a document; by default the self-referential integrity field is omitted."""
    payload = copy.deepcopy(dict(document))
    if omit_integrity:
        payload.pop("integrity", None)
    return "sha256:" + hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def bind_integrity(document: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy bound to its canonical content digest."""
    bound = copy.deepcopy(dict(document))
    bound.pop("integrity", None)
    bound["integrity"] = {
        "canonicalization": CANONICALIZATION_PROFILE,
        "digest": content_digest(bound),
    }
    return bound


def verify_integrity(document: Mapping[str, Any]) -> bool:
    integrity = document.get("integrity")
    if not isinstance(integrity, dict):
        return False
    if integrity.get("canonicalization") != CANONICALIZATION_PROFILE:
        return False
    claimed = integrity.get("digest")
    return isinstance(claimed, str) and claimed == content_digest(document)


def _rfc3339(value: str, field: str) -> datetime:
    if not isinstance(value, str):
        raise CompileError(f"{field}: RFC 3339 timestamp required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CompileError(f"{field}: invalid RFC 3339 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise CompileError(f"{field}: UTC timestamp required")
    return parsed.astimezone(timezone.utc)


def _utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _require_nonempty_string(intent: Mapping[str, Any], field: str) -> str:
    value = intent.get(field)
    if not isinstance(value, str) or not value.strip():
        raise CompileError(f"{field}: non-empty string required")
    return value


def _require_nonempty_strings(intent: Mapping[str, Any], field: str) -> list[str]:
    value = intent.get(field)
    if not isinstance(value, list) or not value or not all(isinstance(v, str) and v.strip() for v in value):
        raise CompileError(f"{field}: non-empty string array required")
    if len(value) != len(set(value)):
        raise CompileError(f"{field}: duplicates are forbidden")
    return list(value)


def _validate_intent(intent: Mapping[str, Any]) -> None:
    required = {
        "case_id", "requested_at", "purpose", "legal_principal", "actor", "action",
        "resource", "parameters", "data_rights", "budget", "ttl_seconds",
        "evidence_requirements", "approvals_required", "expected_effect", "receipt_type",
        "reconciliation_contract", "reversibility", "compensation_path", "kill_conditions",
        "policy_version", "constitution_digest", "reality_status",
    }
    optional = {"settlement_path"}
    missing = required - set(intent)
    unknown = set(intent) - required - optional
    if missing:
        raise CompileError(f"missing required fields: {sorted(missing)}")
    if unknown:
        raise CompileError(f"unknown fields are forbidden: {sorted(unknown)}")
    _plain_json(dict(intent))

    case_id = _require_nonempty_string(intent, "case_id")
    if not TYPED_ID_RE.fullmatch(case_id) or not case_id.startswith("case:"):
        raise CompileError("case_id: typed case identifier required")
    _rfc3339(_require_nonempty_string(intent, "requested_at"), "requested_at")
    _require_nonempty_string(intent, "purpose")
    legal_principal = _require_nonempty_string(intent, "legal_principal")
    if not LEGAL_PRINCIPAL_RE.fullmatch(legal_principal):
        raise CompileError("legal_principal: opaque institutional identifier required")
    if legal_principal.strip().upper() == "UNIIMENTE":
        raise CompileError("legal_principal: UNIIMENTE is infrastructure, never the legal actor")

    actor = intent.get("actor")
    if not isinstance(actor, dict) or set(actor) - {"workload_spiffe_id", "human_delegate"}:
        raise CompileError("actor: workload_spiffe_id and optional human_delegate only")
    workload = actor.get("workload_spiffe_id")
    if not isinstance(workload, str) or not workload.startswith(SPIFFE_PREFIX):
        raise CompileError("actor.workload_spiffe_id: institutional SPIFFE identity required")
    if "human_delegate" in actor and (
        not isinstance(actor["human_delegate"], str) or not actor["human_delegate"].strip()
    ):
        raise CompileError("actor.human_delegate: non-empty string required when present")

    action = _require_nonempty_string(intent, "action")
    if not ACTION_RE.fullmatch(action):
        raise CompileError("action: namespaced lowercase action required")
    _require_nonempty_string(intent, "resource")
    if not isinstance(intent.get("parameters"), dict):
        raise CompileError("parameters: object required")

    data_rights = intent.get("data_rights")
    if not isinstance(data_rights, dict) or set(data_rights) != {"allowed", "forbidden"}:
        raise CompileError("data_rights: exact allowed and forbidden arrays required")
    allowed = data_rights["allowed"]
    forbidden = data_rights["forbidden"]
    if not isinstance(allowed, list) or not isinstance(forbidden, list):
        raise CompileError("data_rights: allowed and forbidden must be arrays")
    if not all(isinstance(v, str) and v for v in allowed + forbidden):
        raise CompileError("data_rights: every right must be a non-empty string")
    if len(allowed) != len(set(allowed)) or len(forbidden) != len(set(forbidden)):
        raise CompileError("data_rights: duplicate rights are forbidden")
    overlap = set(allowed) & set(forbidden)
    if overlap:
        raise CompileError(f"data_rights: rights cannot be both allowed and forbidden: {sorted(overlap)}")

    budget = intent.get("budget")
    if not isinstance(budget, dict) or set(budget) != {"currency", "amount_minor"}:
        raise CompileError("budget: exact currency and amount_minor required")
    if not isinstance(budget["currency"], str) or not re.fullmatch(r"[A-Z]{3}", budget["currency"]):
        raise CompileError("budget.currency: ISO-style three-letter uppercase code required")
    if isinstance(budget["amount_minor"], bool) or not isinstance(budget["amount_minor"], int) or budget["amount_minor"] < 0:
        raise CompileError("budget.amount_minor: non-negative integer required")

    ttl = intent.get("ttl_seconds")
    if isinstance(ttl, bool) or not isinstance(ttl, int) or not 1 <= ttl <= MAX_TTL_SECONDS:
        raise CompileError(f"ttl_seconds: integer from 1 through {MAX_TTL_SECONDS} required")
    _require_nonempty_strings(intent, "evidence_requirements")
    approvals = _require_nonempty_strings(intent, "approvals_required")
    if any(a.lower() == "none" for a in approvals):
        raise CompileError("approvals_required: 'none' is never an authority source")
    _require_nonempty_string(intent, "expected_effect")
    _require_nonempty_string(intent, "receipt_type")
    _require_nonempty_string(intent, "reconciliation_contract")

    reversibility = intent.get("reversibility")
    if reversibility not in {"reversible", "economic_only", "costly_to_reverse", "irreversible"}:
        raise CompileError("reversibility: unknown class")
    reality_status = intent.get("reality_status")
    if reality_status not in {"live", "sandbox", "simulated", "proposed"}:
        raise CompileError("reality_status: unknown status")
    if reality_status == "live" and reversibility == "irreversible":
        raise CompileError("IVIO v1 refuses live irreversible instructions")
    _require_nonempty_string(intent, "compensation_path")
    _require_nonempty_strings(intent, "kill_conditions")
    _require_nonempty_string(intent, "policy_version")
    constitution_digest = _require_nonempty_string(intent, "constitution_digest")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", constitution_digest):
        raise CompileError("constitution_digest: sha256 digest required")
    if "settlement_path" in intent and intent["settlement_path"] is not None:
        if not isinstance(intent["settlement_path"], str) or not intent["settlement_path"].strip():
            raise CompileError("settlement_path: non-empty string or null required")


def compile_instruction(
    intent: Mapping[str, Any], *, compiler_version: str = "ivio-compiler/0.1.0"
) -> dict[str, Any]:
    """Deterministically lower a complete intent into an IVIO v1 instruction.

    The output is a proposal artifact only. Approval must bind to its integrity
    digest, and commit-time revalidation remains mandatory.
    """
    if not isinstance(intent, Mapping):
        raise CompileError("intent must be a mapping")
    if not isinstance(compiler_version, str) or not compiler_version.strip():
        raise CompileError("compiler_version: non-empty string required")
    _validate_intent(intent)
    requested_at = _rfc3339(intent["requested_at"], "requested_at")
    source_digest = content_digest(dict(intent), omit_integrity=False)
    parameter_digest = "sha256:" + hashlib.sha256(canonical_json_bytes(intent["parameters"])).hexdigest()
    instruction_id = "instruction:" + source_digest.removeprefix("sha256:")[:32]
    compiled = {
        "object_type": "compiled_instruction",
        "version": "ivio.v1",
        "instruction_id": instruction_id,
        "case_id": intent["case_id"],
        "source_intent_digest": source_digest,
        "compiled_at": _utc(requested_at),
        "compiler_version": compiler_version,
        "purpose": intent["purpose"],
        "legal_principal": intent["legal_principal"],
        "actor": copy.deepcopy(intent["actor"]),
        "action": intent["action"],
        "resource": intent["resource"],
        "parameters": copy.deepcopy(intent["parameters"]),
        "parameter_digest": parameter_digest,
        "data_rights": copy.deepcopy(intent["data_rights"]),
        "budget": copy.deepcopy(intent["budget"]),
        "ttl_seconds": intent["ttl_seconds"],
        "not_before": _utc(requested_at),
        "expires_at": _utc(requested_at + timedelta(seconds=intent["ttl_seconds"])),
        "evidence_requirements": list(intent["evidence_requirements"]),
        "approvals_required": list(intent["approvals_required"]),
        "expected_effect": intent["expected_effect"],
        "receipt_type": intent["receipt_type"],
        "reconciliation_contract": intent["reconciliation_contract"],
        "reversibility": intent["reversibility"],
        "compensation_path": intent["compensation_path"],
        "settlement_path": intent.get("settlement_path"),
        "kill_conditions": list(intent["kill_conditions"]),
        "policy_version": intent["policy_version"],
        "constitution_digest": intent["constitution_digest"],
        "reality_status": intent["reality_status"],
    }
    return bind_integrity(compiled)
