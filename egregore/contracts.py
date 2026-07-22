"""Immutable-at-the-boundary contracts for standing cognition.

All identifiers are content-derived.  Incoming text is data, even when it is
shaped like an instruction.  Proposal contracts carry evidence and cost but
never carry execution authority.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


class ContractError(ValueError):
    """A boundary object is malformed or violates a standing invariant."""


class IntegrityConflict(ContractError):
    """A stable source identifier was reused for different content."""


def canonical_json(value: Any) -> str:
    """Return the sole canonical JSON representation used for hashing."""
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ContractError(f"value is not canonical JSON: {exc}") from exc


def canonical_copy(value: Any) -> Any:
    """Detach caller-owned mutable objects while checking JSON safety."""
    return json.loads(canonical_json(value))


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def require_text(name: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{name} must be a non-empty string")
    return value.strip()


def require_hash(name: str, value: str) -> str:
    require_text(name, value)
    if not value.startswith("sha256:") or len(value) != 71:
        raise ContractError(f"{name} must be a sha256:<64 hex> digest")
    try:
        int(value[7:], 16)
    except ValueError as exc:
        raise ContractError(f"{name} must be a sha256:<64 hex> digest") from exc
    return value.lower()


def _tuple_of_text(name: str, values: Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ContractError(f"{name} must be a sequence of strings")
    result = tuple(require_text(f"{name}[]", value) for value in values)
    return result


def _probability(name: str, value: float) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ContractError(f"{name} must be numeric")
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ContractError(f"{name} must be between 0 and 1")
    return number


@dataclass(frozen=True)
class SignalEnvelope:
    source: str
    source_event_id: str
    observed_at: str
    payload: dict[str, Any]
    evidence_refs: tuple[str, ...]
    sensitivity: str
    trust_level: str
    signal_id: str
    content_hash: str

    @classmethod
    def build(
        cls,
        *,
        source: str,
        source_event_id: str,
        observed_at: str,
        payload: Mapping[str, Any],
        evidence_refs: Sequence[str] = (),
        sensitivity: str = "internal",
        trust_level: str = "untrusted",
    ) -> "SignalEnvelope":
        source = require_text("source", source)
        source_event_id = require_text("source_event_id", source_event_id)
        observed_at = require_text("observed_at", observed_at)
        sensitivity = require_text("sensitivity", sensitivity)
        trust_level = require_text("trust_level", trust_level)
        if not isinstance(payload, Mapping):
            raise ContractError("payload must be a mapping")
        clean_payload = canonical_copy(dict(payload))
        refs = _tuple_of_text("evidence_refs", evidence_refs)
        identity = {"source": source, "source_event_id": source_event_id}
        body = {
            **identity,
            "observed_at": observed_at,
            "payload": clean_payload,
            "evidence_refs": list(refs),
            "sensitivity": sensitivity,
            "trust_level": trust_level,
        }
        return cls(
            source=source,
            source_event_id=source_event_id,
            observed_at=observed_at,
            payload=clean_payload,
            evidence_refs=refs,
            sensitivity=sensitivity,
            trust_level=trust_level,
            signal_id=digest({"kind": "egregore-signal", **identity}),
            content_hash=digest(body),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "source_event_id": self.source_event_id,
            "observed_at": self.observed_at,
            "payload": canonical_copy(self.payload),
            "evidence_refs": list(self.evidence_refs),
            "sensitivity": self.sensitivity,
            "trust_level": self.trust_level,
            "signal_id": self.signal_id,
            "content_hash": self.content_hash,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SignalEnvelope":
        rebuilt = cls.build(
            source=value["source"],
            source_event_id=value["source_event_id"],
            observed_at=value["observed_at"],
            payload=value["payload"],
            evidence_refs=value.get("evidence_refs", ()),
            sensitivity=value.get("sensitivity", "internal"),
            trust_level=value.get("trust_level", "untrusted"),
        )
        if value.get("signal_id", rebuilt.signal_id) != rebuilt.signal_id:
            raise IntegrityConflict("persisted signal_id does not match source identity")
        if value.get("content_hash", rebuilt.content_hash) != rebuilt.content_hash:
            raise IntegrityConflict("persisted content_hash does not match signal content")
        return rebuilt


@dataclass(frozen=True)
class CandidateProposal:
    proposed_by: str
    objective: str
    action_class: str
    requested_capability: str
    target: str
    consequence_class: str
    payload: dict[str, Any]
    evidence_refs: tuple[str, ...]
    confidence: float
    estimated_cost_usd: float
    expected_outcome: str
    source_signal_ids: tuple[str, ...]
    candidate_id: str

    @property
    def execution_authority(self) -> str:
        return "none"

    @classmethod
    def build(
        cls,
        *,
        proposed_by: str,
        objective: str,
        action_class: str,
        requested_capability: str,
        target: str,
        consequence_class: str,
        payload: Mapping[str, Any],
        evidence_refs: Sequence[str],
        confidence: float,
        estimated_cost_usd: float,
        expected_outcome: str,
        source_signal_ids: Sequence[str],
    ) -> "CandidateProposal":
        clean = {
            "proposed_by": require_text("proposed_by", proposed_by),
            "objective": require_text("objective", objective),
            "action_class": require_text("action_class", action_class),
            "requested_capability": require_text("requested_capability", requested_capability),
            "target": require_text("target", target),
            "consequence_class": require_text("consequence_class", consequence_class),
            "payload": canonical_copy(dict(payload)),
            "evidence_refs": list(_tuple_of_text("evidence_refs", evidence_refs)),
            "confidence": _probability("confidence", confidence),
            "estimated_cost_usd": float(estimated_cost_usd),
            "expected_outcome": require_text("expected_outcome", expected_outcome),
            "source_signal_ids": list(_tuple_of_text("source_signal_ids", source_signal_ids)),
        }
        if not math.isfinite(clean["estimated_cost_usd"]) or clean["estimated_cost_usd"] < 0:
            raise ContractError("estimated_cost_usd must be finite and non-negative")
        if not clean["source_signal_ids"]:
            raise ContractError("a candidate must cite at least one source signal")
        candidate_id = digest({"kind": "egregore-candidate", **clean})
        return cls(
            proposed_by=clean["proposed_by"],
            objective=clean["objective"],
            action_class=clean["action_class"],
            requested_capability=clean["requested_capability"],
            target=clean["target"],
            consequence_class=clean["consequence_class"],
            payload=clean["payload"],
            evidence_refs=tuple(clean["evidence_refs"]),
            confidence=clean["confidence"],
            estimated_cost_usd=clean["estimated_cost_usd"],
            expected_outcome=clean["expected_outcome"],
            source_signal_ids=tuple(clean["source_signal_ids"]),
            candidate_id=candidate_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposed_by": self.proposed_by,
            "objective": self.objective,
            "action_class": self.action_class,
            "requested_capability": self.requested_capability,
            "target": self.target,
            "consequence_class": self.consequence_class,
            "payload": canonical_copy(self.payload),
            "evidence_refs": list(self.evidence_refs),
            "confidence": self.confidence,
            "estimated_cost_usd": self.estimated_cost_usd,
            "expected_outcome": self.expected_outcome,
            "source_signal_ids": list(self.source_signal_ids),
            "candidate_id": self.candidate_id,
            "execution_authority": self.execution_authority,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CandidateProposal":
        rebuilt = cls.build(
            proposed_by=value["proposed_by"],
            objective=value["objective"],
            action_class=value["action_class"],
            requested_capability=value["requested_capability"],
            target=value["target"],
            consequence_class=value["consequence_class"],
            payload=value["payload"],
            evidence_refs=value.get("evidence_refs", ()),
            confidence=value["confidence"],
            estimated_cost_usd=value["estimated_cost_usd"],
            expected_outcome=value["expected_outcome"],
            source_signal_ids=value["source_signal_ids"],
        )
        if value.get("candidate_id", rebuilt.candidate_id) != rebuilt.candidate_id:
            raise IntegrityConflict("persisted candidate_id does not match candidate content")
        return rebuilt


@dataclass(frozen=True)
class Assessment:
    role: str
    candidate_id: str
    score: float
    confidence: float
    objections: tuple[str, ...]
    veto: bool
    evidence_refs: tuple[str, ...]

    @classmethod
    def build(
        cls,
        *,
        role: str,
        candidate_id: str,
        score: float,
        confidence: float,
        objections: Sequence[str] = (),
        veto: bool = False,
        evidence_refs: Sequence[str] = (),
    ) -> "Assessment":
        require_hash("candidate_id", candidate_id)
        if not isinstance(score, (int, float)) or isinstance(score, bool):
            raise ContractError("score must be numeric")
        score = float(score)
        if not math.isfinite(score) or not -1.0 <= score <= 1.0:
            raise ContractError("score must be between -1 and 1")
        return cls(
            role=require_text("role", role),
            candidate_id=candidate_id,
            score=score,
            confidence=_probability("confidence", confidence),
            objections=_tuple_of_text("objections", objections),
            veto=bool(veto),
            evidence_refs=_tuple_of_text("evidence_refs", evidence_refs),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "candidate_id": self.candidate_id,
            "score": self.score,
            "confidence": self.confidence,
            "objections": list(self.objections),
            "veto": self.veto,
            "evidence_refs": list(self.evidence_refs),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Assessment":
        return cls.build(
            role=value["role"],
            candidate_id=value["candidate_id"],
            score=value["score"],
            confidence=value["confidence"],
            objections=value.get("objections", ()),
            veto=value.get("veto", False),
            evidence_refs=value.get("evidence_refs", ()),
        )


@dataclass(frozen=True)
class ChangeProposal:
    proposed_by: str
    base_state_hash: str
    patch: dict[str, Any]
    rationale: str
    tests: tuple[str, ...]
    rollback: str
    change_id: str

    @property
    def execution_authority(self) -> str:
        return "none"

    @classmethod
    def build(
        cls,
        *,
        proposed_by: str,
        base_state_hash: str,
        patch: Mapping[str, Any],
        rationale: str,
        tests: Sequence[str],
        rollback: str,
    ) -> "ChangeProposal":
        clean = {
            "proposed_by": require_text("proposed_by", proposed_by),
            "base_state_hash": require_hash("base_state_hash", base_state_hash),
            "patch": canonical_copy(dict(patch)),
            "rationale": require_text("rationale", rationale),
            "tests": list(_tuple_of_text("tests", tests)),
            "rollback": require_text("rollback", rollback),
        }
        if not clean["tests"]:
            raise ContractError("change proposal must declare at least one test")
        return cls(
            proposed_by=clean["proposed_by"],
            base_state_hash=clean["base_state_hash"],
            patch=clean["patch"],
            rationale=clean["rationale"],
            tests=tuple(clean["tests"]),
            rollback=clean["rollback"],
            change_id=digest({"kind": "egregore-change", **clean}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposed_by": self.proposed_by,
            "base_state_hash": self.base_state_hash,
            "patch": canonical_copy(self.patch),
            "rationale": self.rationale,
            "tests": list(self.tests),
            "rollback": self.rollback,
            "change_id": self.change_id,
            "execution_authority": self.execution_authority,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ChangeProposal":
        rebuilt = cls.build(
            proposed_by=value["proposed_by"],
            base_state_hash=value["base_state_hash"],
            patch=value["patch"],
            rationale=value["rationale"],
            tests=value["tests"],
            rollback=value["rollback"],
        )
        if value.get("change_id", rebuilt.change_id) != rebuilt.change_id:
            raise IntegrityConflict("persisted change_id does not match change content")
        return rebuilt
