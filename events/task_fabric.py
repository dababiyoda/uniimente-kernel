"""Phase-2 durable organizational task fabric.

This module is deliberately a reducer, not a scheduler or workflow engine.
It appends explicit task transitions to the existing EventSpine and rebuilds
all state from replay. DurableWorkflow remains the default execution baseline.

A WorkerLease narrows references already present on its immutable TaskEnvelope.
It never issues authority. Unknown external-effect state can only enter
RECONCILIATION_REQUIRED and cannot become retry-eligible without evidence that
the effect was reconciled.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from events.spine import Event, EventSpine, SPIFFE_PREFIX


SCHEMA_VERSION = "1.0"
FABRIC_VERSION = "1.0"

TASK_STATES = (
    "CREATED",
    "ADMITTED",
    "QUEUED",
    "LEASED",
    "RUNNING",
    "SUBMITTED",
    "VERIFIED",
    "CLOSED",
    "FAILED",
    "RETRY_ELIGIBLE",
    "RECONCILIATION_REQUIRED",
    "QUARANTINED",
    "TERMINATED",
)

TERMINAL_STATES = frozenset({"CLOSED", "TERMINATED"})

_ALLOWED_TRANSITIONS = {
    "CREATED": frozenset({"ADMITTED", "TERMINATED"}),
    "ADMITTED": frozenset({"QUEUED", "TERMINATED"}),
    "QUEUED": frozenset({"LEASED", "QUARANTINED", "TERMINATED"}),
    "LEASED": frozenset({"RUNNING", "RETRY_ELIGIBLE", "QUARANTINED", "TERMINATED"}),
    "RUNNING": frozenset({
        "SUBMITTED", "FAILED", "RETRY_ELIGIBLE",
        "RECONCILIATION_REQUIRED", "QUARANTINED", "TERMINATED",
    }),
    "FAILED": frozenset({
        "RETRY_ELIGIBLE", "RECONCILIATION_REQUIRED", "QUARANTINED", "TERMINATED",
    }),
    "RETRY_ELIGIBLE": frozenset({"QUEUED", "TERMINATED"}),
    "RECONCILIATION_REQUIRED": frozenset({"RETRY_ELIGIBLE", "TERMINATED"}),
    "SUBMITTED": frozenset({"VERIFIED", "QUARANTINED", "TERMINATED"}),
    "VERIFIED": frozenset({"CLOSED"}),
    "QUARANTINED": frozenset({"TERMINATED"}),
    "CLOSED": frozenset(),
    "TERMINATED": frozenset(),
}

_CONSEQUENCE_RANK = {"internal_read": 0, "internal_write": 1, "external": 2}

_ENVELOPE_FIELDS = frozenset({
    "schema_version", "task_id", "mission_id", "founder_intent_ref",
    "subgoal_ref", "parent_task_id", "idempotency_key", "objective",
    "required_capability", "created_by", "legal_principal", "authority_refs",
    "consequence_class", "external_effect_policy", "resource_budget",
    "context_policy", "tool_policy", "evidence_requirements",
    "prohibited_actions", "sensitivity", "created_at",
    "acceptance_authority_ref", "independent_evaluation_required",
    "authority_invariants",
})

_LEASE_FIELDS = frozenset({
    "schema_version", "lease_id", "task_id", "mission_id", "worker_identity",
    "issued_by", "capability", "capability_grant_ref", "authority_refs",
    "permitted_tools", "permitted_data_classes", "context_refs",
    "resource_budget", "issued_at", "expires_at", "consequence_ceiling",
    "output_contract_ref", "heartbeat_interval_seconds",
    "termination_condition", "replaces_lease_id", "one_task_only",
    "authority_inheritance",
})

_ZERO_USAGE = {"cost_usd": 0.0, "compute_used": 0.0, "model_calls": 0}


class TaskFabricError(ValueError):
    """A task command or replay violates a fail-closed invariant."""


class InvalidTransition(TaskFabricError):
    """The requested state transition is not valid from current state."""


class AuthorityViolation(TaskFabricError):
    """A task or lease attempted to create, widen or inherit authority."""


class BudgetExceeded(TaskFabricError):
    """Recorded task resource use would exceed the immutable envelope."""


class ReconciliationRequired(TaskFabricError):
    """Retry was requested while an external effect remains uncertain."""


@dataclass(frozen=True)
class TaskReceipt:
    """Replay-derived proof of one canonical task transition."""

    schema_version: str
    record_kind: str
    receipt_id: str
    task_id: str
    mission_id: str
    founder_intent_ref: str
    transition_index: int
    previous_state: str | None
    state: str
    transition_key: str
    request_fingerprint: str
    event_id: str
    event_type: str
    actor: str
    legal_principal: str
    worker_identity: str | None
    lease_id: str | None
    authority_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    tool_refs: tuple[str, ...]
    result_digest: str | None
    assessment_refs: tuple[str, ...]
    dissent_refs: tuple[str, ...]
    dissent_preserved: bool
    resource_usage: dict[str, float | int]
    consequence_status: str
    occurred_at: str
    causal_parent_event_id: str | None
    model_prediction: bool = False

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        for name in (
            "authority_refs", "evidence_refs", "tool_refs",
            "assessment_refs", "dissent_refs",
        ):
            value[name] = list(value[name])
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TaskReceipt":
        data = dict(value)
        for name in (
            "authority_refs", "evidence_refs", "tool_refs",
            "assessment_refs", "dissent_refs",
        ):
            data[name] = tuple(data[name])
        data["resource_usage"] = dict(data["resource_usage"])
        return cls(**data)


@dataclass
class _TaskView:
    envelope: dict[str, Any]
    state: str
    receipts: list[TaskReceipt]
    lease_history: dict[str, dict[str, Any]]
    active_lease: dict[str, Any] | None
    last_worker_identity: str | None


def _timestamp(value: str) -> datetime:
    if not isinstance(value, str):
        raise TaskFabricError("timestamp must be an RFC 3339 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TaskFabricError(f"invalid timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise TaskFabricError("timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def _uuid(value: str, label: str) -> None:
    try:
        uuid.UUID(value)
    except (TypeError, ValueError, AttributeError) as exc:
        raise TaskFabricError(f"{label} must be a UUID") from exc


def _identity(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.startswith(SPIFFE_PREFIX):
        raise TaskFabricError(f"{label} must be an institutional SPIFFE identity")


def _hash(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _digest(value: str | None, label: str, *, required: bool = False) -> None:
    if value is None and not required:
        return
    if not isinstance(value, str) or len(value) != 71 or not value.startswith("sha256:"):
        raise TaskFabricError(f"{label} must be a sha256 digest")
    try:
        int(value[7:], 16)
    except ValueError as exc:
        raise TaskFabricError(f"{label} must be a lowercase hexadecimal sha256 digest") from exc
    if value[7:] != value[7:].lower():
        raise TaskFabricError(f"{label} must be a lowercase hexadecimal sha256 digest")


def _exact_fields(value: dict[str, Any], fields: frozenset[str], label: str) -> None:
    if not isinstance(value, dict):
        raise TaskFabricError(f"{label} must be an object")
    missing = fields - value.keys()
    unknown = value.keys() - fields
    if missing:
        raise TaskFabricError(f"{label} missing fields: {sorted(missing)}")
    if unknown:
        raise TaskFabricError(f"{label} has unknown fields: {sorted(unknown)}")


def _budget(value: dict[str, Any], label: str) -> None:
    required = {"budget_ceiling_usd", "compute_ceiling", "model_call_ceiling"}
    if not isinstance(value, dict) or set(value) != required:
        raise TaskFabricError(f"{label} must contain exactly {sorted(required)}")
    for key in ("budget_ceiling_usd", "compute_ceiling"):
        if isinstance(value[key], bool) or not isinstance(value[key], (int, float)) or value[key] < 0:
            raise TaskFabricError(f"{label}.{key} must be non-negative")
    calls = value["model_call_ceiling"]
    if isinstance(calls, bool) or not isinstance(calls, int) or calls < 0:
        raise TaskFabricError(f"{label}.model_call_ceiling must be a non-negative integer")


def _usage(value: dict[str, Any]) -> dict[str, float | int]:
    required = {"cost_usd", "compute_used", "model_calls"}
    if not isinstance(value, dict) or set(value) != required:
        raise TaskFabricError(f"resource_usage must contain exactly {sorted(required)}")
    for key in ("cost_usd", "compute_used"):
        if isinstance(value[key], bool) or not isinstance(value[key], (int, float)) or value[key] < 0:
            raise TaskFabricError(f"resource_usage.{key} must be non-negative")
    if isinstance(value["model_calls"], bool) or not isinstance(value["model_calls"], int) or value["model_calls"] < 0:
        raise TaskFabricError("resource_usage.model_calls must be a non-negative integer")
    return dict(value)


def _validate_envelope(envelope: dict[str, Any]) -> dict[str, Any]:
    _exact_fields(envelope, _ENVELOPE_FIELDS, "TaskEnvelope")
    if envelope["schema_version"] != SCHEMA_VERSION:
        raise TaskFabricError("unsupported TaskEnvelope schema_version")
    _uuid(envelope["task_id"], "task_id")
    _uuid(envelope["mission_id"], "mission_id")
    if envelope["parent_task_id"] is not None:
        _uuid(envelope["parent_task_id"], "parent_task_id")
        if envelope["parent_task_id"] == envelope["task_id"]:
            raise TaskFabricError("task cannot be its own parent")
    _identity(envelope["created_by"], "created_by")
    if envelope["legal_principal"] == "UNIIMENTE" or not envelope["legal_principal"]:
        raise AuthorityViolation("UNIIMENTE is never the task legal principal")
    refs = envelope["authority_refs"]
    if not isinstance(refs, list) or not refs or len(refs) != len(set(refs)):
        raise TaskFabricError("authority_refs must be a non-empty unique list")
    if envelope["consequence_class"] not in _CONSEQUENCE_RANK:
        raise TaskFabricError("unknown consequence_class")
    if envelope["external_effect_policy"] not in ("none", "gate_required"):
        raise TaskFabricError("unknown external_effect_policy")
    if envelope["consequence_class"] == "external" and envelope["external_effect_policy"] != "gate_required":
        raise AuthorityViolation("external tasks require canonical consequence mediation")
    _budget(envelope["resource_budget"], "resource_budget")
    for name, fields in (
        ("context_policy", {"permitted_data_classes", "context_refs", "prohibited_context"}),
        ("tool_policy", {"permitted_tools", "prohibited_tools"}),
    ):
        value = envelope[name]
        if not isinstance(value, dict) or set(value) != fields:
            raise TaskFabricError(f"{name} must contain exactly {sorted(fields)}")
        for field_name in fields:
            if not isinstance(value[field_name], list) or len(value[field_name]) != len(set(value[field_name])):
                raise TaskFabricError(f"{name}.{field_name} must be a unique list")
    if not isinstance(envelope["evidence_requirements"], list) or not envelope["evidence_requirements"]:
        raise TaskFabricError("evidence_requirements must be non-empty")
    _timestamp(envelope["created_at"])
    invariants = envelope["authority_invariants"]
    expected = {
        "organization_may_create_authority": False,
        "worker_may_inherit_authority": False,
        "consequence_gate_bypass_permitted": False,
    }
    if invariants != expected:
        raise AuthorityViolation("TaskEnvelope authority invariants are immutable false")
    return json.loads(json.dumps(envelope))


def _validate_lease(lease: dict[str, Any], envelope: dict[str, Any],
                    prior_leases: dict[str, dict[str, Any]]) -> dict[str, Any]:
    _exact_fields(lease, _LEASE_FIELDS, "WorkerLease")
    if lease["schema_version"] != SCHEMA_VERSION:
        raise TaskFabricError("unsupported WorkerLease schema_version")
    _uuid(lease["lease_id"], "lease_id")
    _uuid(lease["task_id"], "task_id")
    _uuid(lease["mission_id"], "mission_id")
    _identity(lease["worker_identity"], "worker_identity")
    _identity(lease["issued_by"], "issued_by")
    if lease["issued_by"] != envelope["created_by"]:
        raise AuthorityViolation("only the task's bounded coordinator may issue its lease")
    if lease["lease_id"] in prior_leases:
        raise TaskFabricError("replacement requires a fresh lease_id")
    if lease["task_id"] != envelope["task_id"] or lease["mission_id"] != envelope["mission_id"]:
        raise TaskFabricError("lease task/mission lineage does not match TaskEnvelope")
    if lease["capability"] != envelope["required_capability"]:
        raise TaskFabricError("lease capability does not match required capability")
    if not lease["capability_grant_ref"]:
        raise AuthorityViolation("lease must reference an existing capability grant")
    if not set(lease["authority_refs"]).issubset(set(envelope["authority_refs"])):
        raise AuthorityViolation("lease cannot add authority absent from TaskEnvelope")
    if lease["authority_inheritance"] is not False or lease["one_task_only"] is not True:
        raise AuthorityViolation("leases are one-task and never inherit authority")
    if not set(lease["permitted_tools"]).issubset(
        set(envelope["tool_policy"]["permitted_tools"])
    ):
        raise AuthorityViolation("lease cannot widen permitted tools")
    if not set(lease["permitted_data_classes"]).issubset(
        set(envelope["context_policy"]["permitted_data_classes"])
    ):
        raise AuthorityViolation("lease cannot widen permitted data classes")
    if not set(lease["context_refs"]).issubset(
        set(envelope["context_policy"]["context_refs"])
    ):
        raise AuthorityViolation("lease cannot widen task context")
    _budget(lease["resource_budget"], "lease.resource_budget")
    for lease_key, envelope_key in (
        ("budget_ceiling_usd", "budget_ceiling_usd"),
        ("compute_ceiling", "compute_ceiling"),
        ("model_call_ceiling", "model_call_ceiling"),
    ):
        if lease["resource_budget"][lease_key] > envelope["resource_budget"][envelope_key]:
            raise BudgetExceeded("lease resource budget exceeds TaskEnvelope")
    if lease["consequence_ceiling"] not in _CONSEQUENCE_RANK:
        raise TaskFabricError("unknown lease consequence_ceiling")
    if _CONSEQUENCE_RANK[lease["consequence_ceiling"]] > _CONSEQUENCE_RANK[envelope["consequence_class"]]:
        raise AuthorityViolation("lease consequence ceiling exceeds TaskEnvelope")
    issued = _timestamp(lease["issued_at"])
    expires = _timestamp(lease["expires_at"])
    if expires <= issued:
        raise TaskFabricError("lease expires_at must be after issued_at")
    if isinstance(lease["heartbeat_interval_seconds"], bool) or not isinstance(lease["heartbeat_interval_seconds"], int) or lease["heartbeat_interval_seconds"] < 1:
        raise TaskFabricError("heartbeat_interval_seconds must be a positive integer")
    replaced = lease["replaces_lease_id"]
    if replaced is not None:
        _uuid(replaced, "replaces_lease_id")
        if replaced not in prior_leases:
            raise AuthorityViolation("replacement lease must name a prior lease for this task")
        if set(lease["authority_refs"]) - set(envelope["authority_refs"]):
            raise AuthorityViolation("replacement authority inheritance is prohibited")
    return json.loads(json.dumps(lease))


class TaskFabric:
    """Explicit task commands reduced from the canonical EventSpine.

    There is no worker loop, scheduling policy, retry loop or queue service
    here. Callers choose commands; this class validates and records them.
    """

    def __init__(self, spine: EventSpine, *, source_identity: str):
        _identity(source_identity, "source_identity")
        self.spine = spine
        self.source_identity = source_identity

    def _project(self) -> dict[str, _TaskView]:
        tasks: dict[str, _TaskView] = {}
        for event in self.spine.replay("task."):
            wrapper = event.payload
            if not isinstance(wrapper, dict) or wrapper.get("fabric_version") != FABRIC_VERSION:
                continue
            raw = wrapper.get("receipt")
            if not isinstance(raw, dict):
                raise TaskFabricError(f"task event {event.event_id} has no receipt")
            receipt = TaskReceipt.from_dict(raw)
            if receipt.event_id != event.event_id or receipt.event_type != event.type:
                raise TaskFabricError("receipt/event binding mismatch")
            task_id = receipt.task_id
            if receipt.state == "CREATED":
                if task_id in tasks:
                    raise TaskFabricError(f"task {task_id} was created more than once")
                envelope = wrapper.get("task_envelope")
                if not isinstance(envelope, dict):
                    raise TaskFabricError("task.created must carry TaskEnvelope")
                envelope = _validate_envelope(envelope)
                if envelope["task_id"] != task_id or envelope["mission_id"] != receipt.mission_id:
                    raise TaskFabricError("created receipt lineage does not match TaskEnvelope")
                if receipt.transition_index != 0 or receipt.previous_state is not None:
                    raise TaskFabricError("CREATED must be transition zero with no previous state")
                tasks[task_id] = _TaskView(
                    envelope=envelope,
                    state="CREATED",
                    receipts=[receipt],
                    lease_history={},
                    active_lease=None,
                    last_worker_identity=None,
                )
                continue
            if task_id not in tasks:
                raise TaskFabricError(f"transition precedes task creation: {task_id}")
            view = tasks[task_id]
            if receipt.transition_index != len(view.receipts):
                raise TaskFabricError("non-monotonic task transition index")
            if receipt.previous_state != view.state:
                raise TaskFabricError("stale or out-of-order task transition")
            if receipt.state not in _ALLOWED_TRANSITIONS[view.state]:
                raise TaskFabricError(
                    f"illegal replay transition {view.state} -> {receipt.state}"
                )
            if any(r.transition_key == receipt.transition_key for r in view.receipts):
                raise TaskFabricError("duplicate transition key reached canonical ledger")
            if receipt.state == "LEASED":
                lease = wrapper.get("worker_lease")
                if not isinstance(lease, dict):
                    raise TaskFabricError("task.leased must carry WorkerLease")
                lease = _validate_lease(lease, view.envelope, view.lease_history)
                view.lease_history[lease["lease_id"]] = lease
                view.active_lease = lease
                view.last_worker_identity = lease["worker_identity"]
            if receipt.state in {
                "SUBMITTED", "RETRY_ELIGIBLE", "RECONCILIATION_REQUIRED",
                "QUARANTINED", "TERMINATED", "CLOSED",
            }:
                view.active_lease = None
            view.state = receipt.state
            view.receipts.append(receipt)
        return tasks

    def tasks(self) -> dict[str, str]:
        """Current task states, reconstructed from canonical replay."""
        return {task_id: view.state for task_id, view in self._project().items()}

    def envelope(self, task_id: str) -> dict[str, Any]:
        try:
            return json.loads(json.dumps(self._project()[task_id].envelope))
        except KeyError as exc:
            raise TaskFabricError(f"unknown task: {task_id}") from exc

    def receipts(self, task_id: str) -> tuple[TaskReceipt, ...]:
        try:
            return tuple(self._project()[task_id].receipts)
        except KeyError as exc:
            raise TaskFabricError(f"unknown task: {task_id}") from exc

    @staticmethod
    def _prior_by_key(view: _TaskView | None, transition_key: str,
                      fingerprint: str) -> TaskReceipt | None:
        if view is None:
            return None
        for receipt in view.receipts:
            if receipt.transition_key == transition_key:
                if receipt.request_fingerprint != fingerprint:
                    raise TaskFabricError(
                        "idempotency key was reused with different command content"
                    )
                return receipt
        return None

    @staticmethod
    def _total_usage(view: _TaskView) -> dict[str, float | int]:
        return {
            "cost_usd": sum(float(r.resource_usage["cost_usd"]) for r in view.receipts),
            "compute_used": sum(float(r.resource_usage["compute_used"]) for r in view.receipts),
            "model_calls": sum(int(r.resource_usage["model_calls"]) for r in view.receipts),
        }

    @staticmethod
    def _check_budget(view: _TaskView, additional: dict[str, float | int]) -> None:
        total = TaskFabric._total_usage(view)
        total = {key: total[key] + additional[key] for key in total}
        ceiling = view.envelope["resource_budget"]
        if (
            total["cost_usd"] > ceiling["budget_ceiling_usd"]
            or total["compute_used"] > ceiling["compute_ceiling"]
            or total["model_calls"] > ceiling["model_call_ceiling"]
        ):
            raise BudgetExceeded("task resource envelope would be exceeded")

    def _emit(
        self,
        *,
        view: _TaskView | None,
        envelope: dict[str, Any],
        state: str,
        transition_key: str,
        actor: str,
        command: dict[str, Any],
        worker_identity: str | None = None,
        lease_id: str | None = None,
        evidence_refs: tuple[str, ...] = (),
        tool_refs: tuple[str, ...] = (),
        result_digest: str | None = None,
        assessment_refs: tuple[str, ...] = (),
        dissent_refs: tuple[str, ...] = (),
        dissent_preserved: bool = False,
        resource_usage: dict[str, float | int] | None = None,
        consequence_status: str = "none",
        worker_lease: dict[str, Any] | None = None,
    ) -> TaskReceipt:
        _identity(actor, "actor")
        if not transition_key or len(transition_key) > 200:
            raise TaskFabricError("transition_key must be non-empty and bounded")
        usage = _usage(resource_usage or dict(_ZERO_USAGE))
        fingerprint = _hash(command)
        prior = self._prior_by_key(view, transition_key, fingerprint)
        if prior is not None:
            return prior
        if view is not None:
            self._check_budget(view, usage)
        event_type = "task." + state.lower()
        previous = None if view is None else view.state
        index = 0 if view is None else len(view.receipts)
        parent_event_id = None if view is None else view.receipts[-1].event_id
        event = Event(
            type=event_type,
            source=self.source_identity,
            actor=actor,
            payload={},
            legal_principal=envelope["legal_principal"],
            sensitivity=envelope["sensitivity"],
            causal_parent=parent_event_id,
        )
        receipt = TaskReceipt(
            schema_version=SCHEMA_VERSION,
            record_kind="TASK_TRANSITION_RECEIPT",
            receipt_id=str(uuid.uuid4()),
            task_id=envelope["task_id"],
            mission_id=envelope["mission_id"],
            founder_intent_ref=envelope["founder_intent_ref"],
            transition_index=index,
            previous_state=previous,
            state=state,
            transition_key=transition_key,
            request_fingerprint=fingerprint,
            event_id=event.event_id,
            event_type=event_type,
            actor=actor,
            legal_principal=envelope["legal_principal"],
            worker_identity=worker_identity,
            lease_id=lease_id,
            authority_refs=tuple(envelope["authority_refs"]),
            evidence_refs=tuple(evidence_refs),
            tool_refs=tuple(tool_refs),
            result_digest=result_digest,
            assessment_refs=tuple(assessment_refs),
            dissent_refs=tuple(dissent_refs),
            dissent_preserved=dissent_preserved,
            resource_usage=usage,
            consequence_status=consequence_status,
            occurred_at=event.occurred_at,
            causal_parent_event_id=parent_event_id,
            model_prediction=False,
        )
        event.payload = {
            "fabric_version": FABRIC_VERSION,
            "receipt": receipt.to_dict(),
        }
        if state == "CREATED":
            event.payload["task_envelope"] = envelope
        if worker_lease is not None:
            event.payload["worker_lease"] = worker_lease
        self.spine.emit(event)
        return receipt

    def create_task(self, envelope: dict[str, Any], *, transition_key: str,
                    actor: str | None = None) -> TaskReceipt:
        envelope = _validate_envelope(envelope)
        command = {"command": "create_task", "task_envelope": envelope}
        fingerprint = _hash(command)
        current = self._project().get(envelope["task_id"])
        prior = self._prior_by_key(current, transition_key, fingerprint)
        if prior is not None:
            return prior
        if current is not None:
            raise TaskFabricError(f"task already exists: {envelope['task_id']}")
        return self._emit(
            view=None,
            envelope=envelope,
            state="CREATED",
            transition_key=transition_key,
            actor=actor or envelope["created_by"],
            command=command,
        )

    def issue_lease(self, lease: dict[str, Any], *, transition_key: str) -> TaskReceipt:
        tasks = self._project()
        try:
            view = tasks[lease.get("task_id")]
        except (KeyError, TypeError) as exc:
            raise TaskFabricError("lease references an unknown task") from exc
        command = {"command": "issue_lease", "worker_lease": lease}
        fingerprint = _hash(command)
        prior = self._prior_by_key(view, transition_key, fingerprint)
        if prior is not None:
            return prior
        if view.state != "QUEUED":
            raise InvalidTransition(f"lease requires QUEUED, found {view.state}")
        validated = _validate_lease(lease, view.envelope, view.lease_history)
        return self._emit(
            view=view,
            envelope=view.envelope,
            state="LEASED",
            transition_key=transition_key,
            actor=validated["issued_by"],
            command={"command": "issue_lease", "worker_lease": validated},
            worker_identity=validated["worker_identity"],
            lease_id=validated["lease_id"],
            worker_lease=validated,
        )

    def transition(
        self,
        task_id: str,
        state: str,
        *,
        actor: str,
        transition_key: str,
        worker_identity: str | None = None,
        lease_id: str | None = None,
        evidence_refs: tuple[str, ...] = (),
        tool_refs: tuple[str, ...] = (),
        result_digest: str | None = None,
        assessment_refs: tuple[str, ...] = (),
        dissent_refs: tuple[str, ...] = (),
        dissent_preserved: bool = False,
        resource_usage: dict[str, float | int] | None = None,
        consequence_status: str = "none",
        observed_at: str | None = None,
    ) -> TaskReceipt:
        tasks = self._project()
        try:
            view = tasks[task_id]
        except KeyError as exc:
            raise TaskFabricError(f"unknown task: {task_id}") from exc
        if state not in TASK_STATES or state in {"CREATED", "LEASED"}:
            raise InvalidTransition("use create_task/issue_lease for CREATED or LEASED")
        command = {
            "command": "transition",
            "task_id": task_id,
            "state": state,
            "actor": actor,
            "worker_identity": worker_identity,
            "lease_id": lease_id,
            "evidence_refs": list(evidence_refs),
            "tool_refs": list(tool_refs),
            "result_digest": result_digest,
            "assessment_refs": list(assessment_refs),
            "dissent_refs": list(dissent_refs),
            "dissent_preserved": dissent_preserved,
            "resource_usage": resource_usage or dict(_ZERO_USAGE),
            "consequence_status": consequence_status,
            "observed_at": observed_at,
        }
        fingerprint = _hash(command)
        prior = self._prior_by_key(view, transition_key, fingerprint)
        if prior is not None:
            return prior
        if state not in _ALLOWED_TRANSITIONS[view.state]:
            raise InvalidTransition(f"{view.state} -> {state} is not permitted")
        coordinator_states = {"ADMITTED", "QUEUED", "CLOSED", "TERMINATED"}
        if state in coordinator_states and actor != view.envelope["created_by"]:
            raise AuthorityViolation(
                f"{state} requires the task's bounded coordinator identity"
            )
        if consequence_status not in {
            "none", "not_attempted", "confirmed", "reconciled", "uncertain"
        }:
            raise TaskFabricError("unknown consequence_status")
        if consequence_status == "uncertain" and state != "RECONCILIATION_REQUIRED":
            raise ReconciliationRequired(
                "uncertain external effect must enter RECONCILIATION_REQUIRED"
            )
        if state == "RECONCILIATION_REQUIRED":
            if consequence_status != "uncertain" or not evidence_refs:
                raise ReconciliationRequired(
                    "reconciliation requires uncertainty evidence"
                )
        if view.state == "RECONCILIATION_REQUIRED" and state in {
            "RETRY_ELIGIBLE", "TERMINATED"
        }:
            if consequence_status != "reconciled" or not evidence_refs:
                raise ReconciliationRequired(
                    "uncertain effect must be reconciled with evidence before retry or termination"
                )
        active = view.active_lease
        if state in {"RUNNING", "SUBMITTED"}:
            if active is None:
                raise TaskFabricError(f"{state} requires an active WorkerLease")
            if (
                actor != active["worker_identity"]
                or worker_identity != active["worker_identity"]
                or lease_id != active["lease_id"]
            ):
                raise AuthorityViolation("worker actor/identity/lease mismatch")
        if state == "RUNNING":
            if observed_at is None:
                raise TaskFabricError("RUNNING requires explicit observed_at")
            observed = _timestamp(observed_at)
            if observed < _timestamp(active["issued_at"]):
                raise TaskFabricError("work cannot start before lease issuance")
            if observed >= _timestamp(active["expires_at"]):
                raise TaskFabricError("expired lease cannot start work")
        if state == "SUBMITTED":
            _digest(result_digest, "result_digest", required=True)
        else:
            _digest(result_digest, "result_digest")
        if state == "VERIFIED":
            result_worker = view.last_worker_identity
            if actor in {result_worker, view.envelope["created_by"]}:
                raise AuthorityViolation(
                    "verification must be independent from worker and coordinator"
                )
            if not assessment_refs:
                raise TaskFabricError("VERIFIED requires an independent assessment")
            if not dissent_preserved:
                raise TaskFabricError("VERIFIED must preserve dissent")
            worker_identity = result_worker
            lease_id = view.receipts[-1].lease_id
        if state == "CLOSED":
            if not view.receipts[-1].assessment_refs:
                raise TaskFabricError("CLOSED requires prior verification evidence")
            worker_identity = view.last_worker_identity
        if state == "QUARANTINED":
            if actor == view.last_worker_identity:
                raise AuthorityViolation("worker cannot quarantine its own output")
            if not evidence_refs:
                raise TaskFabricError("QUARANTINED requires poison/failure evidence")
        if state == "RETRY_ELIGIBLE" and view.state == "RECONCILIATION_REQUIRED":
            if actor in {view.last_worker_identity, view.envelope["created_by"]}:
                raise AuthorityViolation(
                    "reconciled retry requires an identity independent from worker and coordinator"
                )
        if state == "RETRY_ELIGIBLE" and view.state != "RECONCILIATION_REQUIRED":
            if consequence_status == "uncertain":
                raise ReconciliationRequired("blind retry of uncertain effect is prohibited")
            if not evidence_refs:
                raise TaskFabricError("RETRY_ELIGIBLE requires failure/expiry evidence")
        if active is not None and worker_identity is None:
            worker_identity = active["worker_identity"]
            lease_id = active["lease_id"]
        return self._emit(
            view=view,
            envelope=view.envelope,
            state=state,
            transition_key=transition_key,
            actor=actor,
            command=command,
            worker_identity=worker_identity,
            lease_id=lease_id,
            evidence_refs=evidence_refs,
            tool_refs=tool_refs,
            result_digest=result_digest,
            assessment_refs=assessment_refs,
            dissent_refs=dissent_refs,
            dissent_preserved=dissent_preserved,
            resource_usage=resource_usage,
            consequence_status=consequence_status,
        )

    def expire_lease(self, task_id: str, *, observed_at: str,
                     transition_key: str, evidence_ref: str) -> TaskReceipt:
        tasks = self._project()
        try:
            view = tasks[task_id]
        except KeyError as exc:
            raise TaskFabricError(f"unknown task: {task_id}") from exc
        lease = view.active_lease
        if lease is None:
            raise TaskFabricError("task has no active lease")
        if _timestamp(observed_at) < _timestamp(lease["expires_at"]):
            raise TaskFabricError("lease has not expired")
        return self.transition(
            task_id,
            "RETRY_ELIGIBLE",
            actor=lease["issued_by"],
            transition_key=transition_key,
            worker_identity=lease["worker_identity"],
            lease_id=lease["lease_id"],
            evidence_refs=(evidence_ref,),
            consequence_status="none",
        )

    def dissolution_readiness(self, mission_id: str,
                              *, open_obligation_refs: tuple[str, ...] = ()) -> tuple[bool, tuple[str, ...]]:
        views = [v for v in self._project().values()
                 if v.envelope["mission_id"] == mission_id]
        reasons: list[str] = []
        if not views:
            reasons.append("mission has no task records")
        if any(v.state not in TERMINAL_STATES for v in views):
            reasons.append("mission has non-terminal tasks")
        if any(v.state == "RECONCILIATION_REQUIRED" for v in views):
            reasons.append("mission has unreconciled effects")
        if any(v.active_lease is not None for v in views):
            reasons.append("mission has active worker leases")
        if open_obligation_refs:
            reasons.append("mission has open obligations")
        return not reasons, tuple(reasons)

    def dissolve_mission(
        self,
        mission_id: str,
        *,
        actor: str,
        transition_key: str,
        evidence_refs: tuple[str, ...],
        open_obligation_refs: tuple[str, ...] = (),
    ) -> Event:
        _identity(actor, "actor")
        ready, reasons = self.dissolution_readiness(
            mission_id, open_obligation_refs=open_obligation_refs
        )
        if not ready:
            raise TaskFabricError("mission cannot dissolve: " + "; ".join(reasons))
        if not evidence_refs:
            raise TaskFabricError("dissolution requires preserved evidence refs")
        views = [v for v in self._project().values()
                 if v.envelope["mission_id"] == mission_id]
        command = {
            "mission_id": mission_id,
            "transition_key": transition_key,
            "evidence_refs": list(evidence_refs),
            "task_terminal_states": {
                v.envelope["task_id"]: v.state for v in views
            },
        }
        fingerprint = _hash(command)
        for event in self.spine.replay("mission.organization_dissolved"):
            payload = event.payload
            if payload.get("transition_key") == transition_key:
                if payload.get("request_fingerprint") != fingerprint:
                    raise TaskFabricError(
                        "dissolution idempotency key reused with different content"
                    )
                return event
        principal = views[0].envelope["legal_principal"]
        event = Event(
            type="mission.organization_dissolved",
            source=self.source_identity,
            actor=actor,
            legal_principal=principal,
            payload={
                "fabric_version": FABRIC_VERSION,
                "mission_id": mission_id,
                "transition_key": transition_key,
                "request_fingerprint": fingerprint,
                "evidence_refs": list(evidence_refs),
                "task_terminal_states": command["task_terminal_states"],
                "resource_release_required": True,
                "credentials_revocation_required": True,
                "model_prediction": False,
            },
        )
        return self.spine.emit(event)
