"""The first composed UNIIMENTE mission metabolism.

This module is the durable, consequence-inert Phase 4 seam:

    founder-intent record
      -> mission admission
      -> standing cognition
      -> mission resolution
      -> canonical task fabric
      -> bounded worker lease
      -> independent evidence appraisal
      -> mission-state reconciliation
      -> founder inbox
      -> retained event history

It composes existing owners. EventSpine remains the only durable transition
truth; TaskFabric remains the task reducer; StandingCognition remains
proposal/evaluation only; MissionResolutionRouter selects without invoking;
OMNIMORPH supplies capability and organization hypotheses.

The implementation intentionally has no daemon, scheduler, socket, model
provider, credential issuer, grant issuer, or external-effect path. It is
therefore useful as an executable seam and not evidence of autonomous,
production, hardened, commercial, or cryptographically founder-authenticated
operation.

A simulation admission is visibly different from an actual founder command.
The actual command surface refuses every command until canonical founder
authentication exists.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence
from uuid import UUID, uuid4

from events.spine import Event, EventSpine, SPIFFE_PREFIX
from events.task_fabric import TaskFabric, TaskReceipt
from omnimorph.mission_compiler import MissionCompilationResult, MissionCompiler
from omnimorph.organization_compiler import content_digest

from .contracts import SignalEnvelope
from .mission_resolution import (
    MissionResolution,
    MissionResolutionRouter,
    ResolutionCandidate,
)
from .resources import ResourceGovernor
from .runtime import CognitionCycle, StandingCognitionRuntime


SOURCE_IDENTITY = "spiffe://uniimente.internal/egregore/cathedral-metabolism"
DEFAULT_EVALUATOR_IDENTITY = (
    "spiffe://uniimente.internal/evaluator/phase4-independent"
)
SIMULATION_WORKER_PREFIX = "spiffe://uniimente.internal/worker/phase4-simulation"


class MissionRuntimeError(ValueError):
    """The mission seam refused an invalid or unsafe operation."""


class FounderAuthenticationRequired(PermissionError):
    """No runtime command is accepted without canonical founder authentication."""


@dataclass(frozen=True)
class MissionAdmission:
    mission_id: str
    mission_digest: str
    event_id: str
    trigger_id: str
    founder_direction_ref: str
    evidence_mode: str
    compilation: MissionCompilationResult

    @property
    def runtime_execution_authorized(self) -> bool:
        return False


@dataclass(frozen=True)
class MissionSnapshot:
    mission_id: str
    mission_digest: str
    status: str
    trigger_id: str
    route_id: str | None
    selected_candidate_id: str | None
    task_states: dict[str, str]
    exception_refs: tuple[str, ...]
    closure_status: str | None
    evidence_mode: str
    external_effects: int = 0
    authority_created: int = 0


class FounderCommandSurface:
    """An explicit refusal boundary for real founder commands."""

    def submit(self, command: Mapping[str, Any], *, authentication: Any = None):
        del command, authentication
        raise FounderAuthenticationRequired(
            "runtime command refused: canonical cryptographic founder "
            "authentication is not implemented"
        )

    @property
    def cryptographic_authentication_available(self) -> bool:
        return False

    @property
    def execution_authority(self) -> str:
        return "none"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _future(seconds: int) -> str:
    return (
        datetime.now(timezone.utc) + timedelta(seconds=seconds)
    ).isoformat().replace("+00:00", "Z")


def _uuid(value: str, label: str) -> None:
    try:
        UUID(value)
    except (ValueError, TypeError, AttributeError) as exc:
        raise MissionRuntimeError(f"{label} must be a UUID") from exc


def _identity(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.startswith(SPIFFE_PREFIX):
        raise MissionRuntimeError(
            f"{label} must be an institutional SPIFFE identity"
        )


def _sensitivity(mission: Mapping[str, Any]) -> str:
    allowed = set(mission["data_constraints"]["allowed_classifications"])
    for value in ("internal", "confidential", "restricted", "public"):
        if value in allowed:
            return value
    return "internal"


def _task_consequence(mission: Mapping[str, Any]) -> str:
    ceiling = mission["consequence_ceiling"]
    if ceiling == "read_only":
        return "internal_read"
    if ceiling == "internal_write":
        return "internal_write"
    return "external"


class CathedralMetabolismRuntime:
    """A replayable mission coordinator with no autonomous authority."""

    def __init__(
        self,
        *,
        spine: EventSpine,
        task_fabric: TaskFabric,
        router: MissionResolutionRouter | None = None,
        cognition: StandingCognitionRuntime | None = None,
        compiler: MissionCompiler | None = None,
        source_identity: str = SOURCE_IDENTITY,
        evidence_mode: str = "SIMULATION",
    ) -> None:
        _identity(source_identity, "source_identity")
        if not isinstance(spine, EventSpine):
            raise MissionRuntimeError("spine must be the canonical EventSpine")
        if not isinstance(task_fabric, TaskFabric):
            raise MissionRuntimeError("task_fabric must be the canonical TaskFabric")
        if task_fabric.spine is not spine:
            raise MissionRuntimeError(
                "TaskFabric must use the same canonical EventSpine"
            )
        if evidence_mode != "SIMULATION":
            raise FounderAuthenticationRequired(
                "actual mission execution is disabled until canonical founder "
                "authentication and a new founder ruling exist"
            )
        self.spine = spine
        self.task_fabric = task_fabric
        self.router = router or MissionResolutionRouter()
        self.cognition = cognition
        self.compiler = compiler or MissionCompiler()
        self.source_identity = source_identity
        self.evidence_mode = evidence_mode
        self.command_surface = FounderCommandSurface()

    @classmethod
    def from_institutional_runtime(
        cls,
        institution: Any,
        *,
        cognition: StandingCognitionRuntime | None = None,
        router: MissionResolutionRouter | None = None,
        compiler: MissionCompiler | None = None,
        source_identity: str = SOURCE_IDENTITY,
    ) -> "CathedralMetabolismRuntime":
        """Compose over the existing runtime's spine; create no second store."""
        if not hasattr(institution, "spine"):
            raise MissionRuntimeError(
                "institution must expose the canonical EventSpine"
            )
        fabric = TaskFabric(institution.spine, source_identity=source_identity)
        return cls(
            spine=institution.spine,
            task_fabric=fabric,
            router=router,
            cognition=cognition,
            compiler=compiler,
            source_identity=source_identity,
        )

    @property
    def execution_authority(self) -> str:
        return "none"

    @property
    def external_effects(self) -> int:
        return 0

    # --------------------------------------------------------------- records
    def _emit(self, event_type: str, payload: Mapping[str, Any],
              *, legal_principal: str, sensitivity: str = "internal") -> Event:
        return self.spine.emit(Event(
            type=event_type,
            source=self.source_identity,
            actor=self.source_identity,
            payload=copy.deepcopy(dict(payload)),
            legal_principal=legal_principal,
            sensitivity=sensitivity,
        ))

    def _admission_event(self, mission_id: str) -> Event:
        matches = [
            event for event in self.spine.replay("mission.admitted")
            if event.payload.get("mission", {}).get("mission_id") == mission_id
        ]
        if not matches:
            raise MissionRuntimeError(f"unknown mission {mission_id}")
        return matches[-1]

    def _mission(self, mission_id: str) -> dict[str, Any]:
        event = self._admission_event(mission_id)
        mission = copy.deepcopy(event.payload["mission"])
        if content_digest(mission) != event.payload["mission_digest"]:
            raise MissionRuntimeError(
                "mission admission digest no longer matches its contract"
            )
        return mission

    def _mission_events(self, mission_id: str, event_type: str | None = None):
        prefix = "mission." if event_type is None else event_type
        return [
            event for event in self.spine.replay(prefix)
            if event.payload.get("mission_id") == mission_id
        ]

    def admit(
        self,
        mission_contract: Mapping[str, Any],
        *,
        trigger_id: str,
        founder_direction_ref: str,
        evidence_mode: str = "SIMULATION",
    ) -> MissionAdmission:
        """Admit a bounded simulation, never an actual founder command."""
        if evidence_mode != "SIMULATION":
            raise FounderAuthenticationRequired(
                "only visibly synthetic simulation admission is enabled"
            )
        if not isinstance(founder_direction_ref, str) or not founder_direction_ref.strip():
            raise MissionRuntimeError("founder_direction_ref is required")
        if not isinstance(trigger_id, str) or not trigger_id.strip():
            raise MissionRuntimeError("trigger_id is required")

        mission = copy.deepcopy(dict(mission_contract))
        compilation = self.compiler.compile(mission)
        mission_id = mission["mission_id"]
        existing_events = [
            event for event in self.spine.replay("mission.admitted")
            if event.payload.get("mission", {}).get("mission_id") == mission_id
        ]
        if existing_events:
            existing = existing_events[-1]
            if existing.payload["mission_digest"] != compilation.mission_digest:
                raise MissionRuntimeError(
                    "mission_id was reused for different content"
                )
            if existing.payload["trigger_id"] != trigger_id:
                raise MissionRuntimeError(
                    "mission_id was reused with a different trigger"
                )
            return MissionAdmission(
                mission_id=mission_id,
                mission_digest=compilation.mission_digest,
                event_id=existing.event_id,
                trigger_id=trigger_id,
                founder_direction_ref=existing.payload["founder_direction_ref"],
                evidence_mode=existing.payload["evidence_mode"],
                compilation=compilation,
            )

        event = self._emit(
            "mission.admitted",
            {
                "mission_id": mission_id,
                "mission": mission,
                "mission_digest": compilation.mission_digest,
                "trigger_id": trigger_id,
                "founder_direction_ref": founder_direction_ref,
                "evidence_mode": "SIMULATION",
                "capability_manifest_digest": compilation.capability_manifest["digest"],
                "organization_hypothesis_digests": [
                    genome["digest"] for genome in compilation.organization.genomes
                ],
                "runtime_execution_authorized": False,
                "authority_created": 0,
                "external_effects": 0,
                "manual_relay_is_not_authentication": True,
            },
            legal_principal=mission["legal_principal"],
            sensitivity=_sensitivity(mission),
        )
        return MissionAdmission(
            mission_id=mission_id,
            mission_digest=compilation.mission_digest,
            event_id=event.event_id,
            trigger_id=trigger_id,
            founder_direction_ref=founder_direction_ref,
            evidence_mode="SIMULATION",
            compilation=compilation,
        )

    # -------------------------------------------------------------- cognition
    def run_cognition(
        self,
        mission_id: str,
        signal: SignalEnvelope,
        *,
        trigger_id: str,
        resources: ResourceGovernor,
        context: Mapping[str, Any] | None = None,
        call_costs: Mapping[str, float] | None = None,
        attention_telemetry: float | None = None,
    ) -> CognitionCycle:
        """Use the existing standing-cognition organ, with explicit replay."""
        mission = self._mission(mission_id)
        if self.cognition is None:
            raise MissionRuntimeError("standing cognition dependency is required")
        if not isinstance(signal, SignalEnvelope):
            raise MissionRuntimeError("signal must be a SignalEnvelope")

        prior = [
            event for event in self._mission_events(mission_id, "mission.cognition")
            if event.payload.get("trigger_id") == trigger_id
        ]
        if prior:
            cycle_data = prior[-1].payload["cycle"]
            return CognitionCycle.from_dict(cycle_data)

        signal_id = self.cognition.ingest(signal)
        cycle = self.cognition.tick(
            trigger_id=trigger_id,
            signal_ids=(signal_id,),
            resources=resources,
            context=context,
            call_costs=call_costs,
            attention_telemetry=attention_telemetry,
        )
        self._emit(
            "mission.cognition",
            {
                "mission_id": mission_id,
                "trigger_id": trigger_id,
                "cycle": cycle.to_dict(),
                "evidence_mode": self.evidence_mode,
                "authority_created": 0,
                "external_effects": 0,
            },
            legal_principal=mission["legal_principal"],
            sensitivity=_sensitivity(mission),
        )
        return cycle

    # ---------------------------------------------------------------- route
    def route(
        self,
        mission_id: str,
        *,
        candidates: Sequence[ResolutionCandidate | Mapping[str, Any]] = (),
        static_baseline_available: bool = True,
        unresolved_reasons: Sequence[str] = (),
    ) -> MissionResolution:
        """Resolve the mechanism before any task or organization is admitted."""
        mission = self._mission(mission_id)
        compilation = self.compiler.compile(mission)
        resolution = self.router.route(
            mission,
            candidates=candidates,
            static_baseline_available=static_baseline_available,
            unresolved_reasons=unresolved_reasons,
            compiled_organization=compilation,
        )
        previous = [
            event for event in self._mission_events(mission_id, "mission.routed")
            if event.payload.get("resolution_id") == resolution.resolution_id
        ]
        if previous:
            if previous[-1].payload["resolution_digest"] != resolution.digest:
                raise MissionRuntimeError(
                    "resolution id was reused for different route content"
                )
            return resolution
        self._emit(
            "mission.routed",
            {
                "mission_id": mission_id,
                "resolution_id": resolution.resolution_id,
                "resolution_digest": resolution.digest,
                "resolution": resolution.to_dict(),
                "capability_manifest_digest": compilation.capability_manifest["digest"],
                "organization_decision_digest": compilation.organization.decision["digest"],
                "evidence_mode": self.evidence_mode,
                "authority_created": 0,
                "external_effects": 0,
            },
            legal_principal=mission["legal_principal"],
            sensitivity=_sensitivity(mission),
        )
        return resolution

    def _latest_resolution(self, mission_id: str) -> MissionResolution:
        events = self._mission_events(mission_id, "mission.routed")
        if not events:
            raise MissionRuntimeError("mission has no routed resolution")
        raw = events[-1].payload["resolution"]
        # Re-run the deterministic selector against the retained candidate
        # descriptors rather than introducing a second deserializer/record
        # authority. The stored digest must match the recomputed result.
        reconstructed = self.router.route(
            self._mission(mission_id),
            candidates=tuple(raw["candidates"]),
            static_baseline_available=False,
            unresolved_reasons=(),
            compiled_organization=None,
        )
        if reconstructed.digest != raw["digest"]:
            # The stored route may include a compiled organization candidate,
            # which is intentionally unavailable when reconstructed without
            # compilation. Recompute with the current compilation.
            compilation = self.compiler.compile(self._mission(mission_id))
            reconstructed = self.router.route(
                self._mission(mission_id),
                candidates=tuple(raw["candidates"]),
                static_baseline_available=False,
                unresolved_reasons=(),
                compiled_organization=compilation,
            )
        if reconstructed.digest != raw["digest"]:
            raise MissionRuntimeError("persisted route digest no longer verifies")
        return reconstructed

    # --------------------------------------------------------------- task seam
    def _selected_for_work(self, mission_id: str) -> MissionResolution:
        resolution = self._latest_resolution(mission_id)
        selected = resolution.selected
        if selected is None:
            raise MissionRuntimeError("mission resolution selected no mechanism")
        if selected.resolution_class in {"no_action", "human_escalation"}:
            raise MissionRuntimeError(
                f"selected route {selected.resolution_class} cannot create work"
            )
        if selected.resolution_class == "compiled_temporary_organization":
            raise MissionRuntimeError(
                "OMNIMORPH organization activation is disabled at this seam"
            )
        return resolution

    def create_task(
        self,
        mission_id: str,
        *,
        task_id: str | None = None,
        subgoal_ref: str = "subgoal:phase4",
        required_capability: str | None = None,
        objective: str | None = None,
        idempotency_key: str | None = None,
    ) -> tuple[str, tuple[TaskReceipt, ...]]:
        """Create one mission-bounded task through the canonical reducer."""
        resolution = self._selected_for_work(mission_id)
        mission = self._mission(mission_id)
        selected = resolution.selected
        assert selected is not None
        if _task_consequence(mission) != "internal_read":
            raise FounderAuthenticationRequired(
                "consequence-inert Phase 4 seam admits read-only tasks only"
            )
        task_id = task_id or str(uuid4())
        _uuid(task_id, "task_id")
        required_capability = required_capability or selected.candidate_id
        objective = objective or mission["objective"]
        idempotency_key = idempotency_key or "mission:" + mission_id + ":task:" + task_id
        envelope = {
            "schema_version": "1.0",
            "task_id": task_id,
            "mission_id": mission_id,
            "founder_intent_ref": mission["founder_intent_ref"],
            "subgoal_ref": subgoal_ref,
            "parent_task_id": None,
            "idempotency_key": idempotency_key,
            "objective": objective,
            "required_capability": required_capability,
            "created_by": self.source_identity,
            "legal_principal": mission["legal_principal"],
            "authority_refs": list(mission["authority_refs"]),
            "consequence_class": "internal_read",
            "external_effect_policy": "none",
            "resource_budget": {
                "budget_ceiling_usd": mission["resource_envelope"]["budget_ceiling_usd"],
                "compute_ceiling": mission["resource_envelope"]["compute_ceiling"],
                "model_call_ceiling": mission["resource_envelope"]["model_call_ceiling"],
            },
            "context_policy": {
                "permitted_data_classes": list(
                    mission["data_constraints"]["allowed_classifications"]
                ),
                "context_refs": [mission["founder_intent_ref"]],
                "prohibited_context": list(
                    mission["data_constraints"]["prohibited_data"]
                ),
            },
            "tool_policy": {
                "permitted_tools": [required_capability],
                "prohibited_tools": [
                    "external_network",
                    "publishing",
                    "payments",
                    "credential_issuance",
                ],
            },
            "evidence_requirements": [
                item["requirement_id"] for item in mission["evidence_requirements"]
            ],
            "prohibited_actions": list(mission["prohibited_actions"]),
            "sensitivity": _sensitivity(mission),
            "created_at": _now(),
            "acceptance_authority_ref": mission["acceptance_authority"]["identity_ref"],
            "independent_evaluation_required": True,
            "authority_invariants": {
                "organization_may_create_authority": False,
                "worker_may_inherit_authority": False,
                "consequence_gate_bypass_permitted": False,
            },
        }
        created = self.task_fabric.create_task(
            envelope,
            transition_key="task:create:" + task_id,
            actor=self.source_identity,
        )
        admitted = self.task_fabric.transition(
            task_id,
            "ADMITTED",
            actor=self.source_identity,
            transition_key="task:admit:" + task_id,
        )
        queued = self.task_fabric.transition(
            task_id,
            "QUEUED",
            actor=self.source_identity,
            transition_key="task:queue:" + task_id,
        )
        return task_id, (created, admitted, queued)

    def lease_task(
        self,
        task_id: str,
        *,
        capability_grant_ref: str,
        worker_identity: str | None = None,
        lease_id: str | None = None,
        lease_seconds: int = 60,
        transition_key: str | None = None,
    ) -> TaskReceipt:
        """Narrow an already-authorized reference into one simulation lease."""
        if not capability_grant_ref or not capability_grant_ref.strip():
            raise MissionRuntimeError("capability_grant_ref must be explicit")
        if lease_seconds < 1:
            raise MissionRuntimeError("lease_seconds must be positive")
        envelope = self.task_fabric.envelope(task_id)
        mission = self._mission(envelope["mission_id"])
        worker_identity = worker_identity or (
            SIMULATION_WORKER_PREFIX + "/" + task_id
        )
        _identity(worker_identity, "worker_identity")
        lease_id = lease_id or str(uuid4())
        _uuid(lease_id, "lease_id")
        issued_at = _now()
        lease = {
            "schema_version": "1.0",
            "lease_id": lease_id,
            "task_id": task_id,
            "mission_id": envelope["mission_id"],
            "worker_identity": worker_identity,
            "issued_by": self.source_identity,
            "capability": envelope["required_capability"],
            "capability_grant_ref": capability_grant_ref,
            "authority_refs": list(envelope["authority_refs"]),
            "permitted_tools": list(envelope["tool_policy"]["permitted_tools"]),
            "permitted_data_classes": list(
                envelope["context_policy"]["permitted_data_classes"]
            ),
            "context_refs": list(envelope["context_policy"]["context_refs"]),
            "resource_budget": copy.deepcopy(envelope["resource_budget"]),
            "issued_at": issued_at,
            "expires_at": _future(lease_seconds),
            "consequence_ceiling": "internal_read",
            "output_contract_ref": "contract:task-receipt-v1",
            "heartbeat_interval_seconds": max(1, min(lease_seconds, 10)),
            "termination_condition": "task terminal, lease expiry or mission kill condition",
            "replaces_lease_id": None,
            "one_task_only": True,
            "authority_inheritance": False,
        }
        return self.task_fabric.issue_lease(
            lease,
            transition_key=transition_key or "task:lease:" + task_id + ":" + lease_id,
        )

    def start_task(
        self,
        task_id: str,
        *,
        worker_identity: str,
        lease_id: str,
        observed_at: str | None = None,
        transition_key: str | None = None,
    ) -> TaskReceipt:
        return self.task_fabric.transition(
            task_id,
            "RUNNING",
            actor=worker_identity,
            transition_key=transition_key or "task:start:" + task_id + ":" + lease_id,
            worker_identity=worker_identity,
            lease_id=lease_id,
            observed_at=observed_at or _now(),
        )

    def submit_task(
        self,
        task_id: str,
        *,
        worker_identity: str,
        lease_id: str,
        result: Mapping[str, Any],
        evidence_refs: Sequence[str],
        tool_refs: Sequence[str] = (),
        transition_key: str | None = None,
    ) -> TaskReceipt:
        if not isinstance(result, Mapping):
            raise MissionRuntimeError("result must be a mapping")
        if not evidence_refs:
            raise MissionRuntimeError("a submitted result needs evidence_refs")
        receipt = self.task_fabric.transition(
            task_id,
            "SUBMITTED",
            actor=worker_identity,
            transition_key=transition_key or "task:submit:" + task_id + ":" + lease_id,
            worker_identity=worker_identity,
            lease_id=lease_id,
            evidence_refs=tuple(evidence_refs),
            tool_refs=tuple(tool_refs),
            result_digest=content_digest(
                {"task_id": task_id, "result": copy.deepcopy(dict(result))}
            ),
        )
        mission_id = self.task_fabric.envelope(task_id)["mission_id"]
        self._emit(
            "mission.result",
            {
                "mission_id": mission_id,
                "task_id": task_id,
                "result_digest": receipt.result_digest,
                "evidence_refs": list(evidence_refs),
                "evidence_mode": self.evidence_mode,
                "authority_created": 0,
                "external_effects": 0,
            },
            legal_principal=self._mission(mission_id)["legal_principal"],
        )
        return receipt

    def verify_task(
        self,
        task_id: str,
        *,
        evidence_refs: Sequence[str],
        dissent_refs: Sequence[str],
        verifier_identity: str = DEFAULT_EVALUATOR_IDENTITY,
        accepted: bool = True,
        transition_key: str | None = None,
    ) -> TaskReceipt | None:
        """Appraise raw references independently of the worker's claim."""
        if not evidence_refs:
            raise MissionRuntimeError("verification needs evidence_refs")
        if not dissent_refs:
            raise MissionRuntimeError("verification needs preserved dissent_refs")
        _identity(verifier_identity, "verifier_identity")
        envelope = self.task_fabric.envelope(task_id)
        receipts = self.task_fabric.receipts(task_id)
        if not receipts or receipts[-1].state != "SUBMITTED":
            raise MissionRuntimeError("verification requires a submitted task")
        worker_identity = receipts[-1].worker_identity
        if verifier_identity in {worker_identity, envelope["created_by"]}:
            raise MissionRuntimeError(
                "verifier must be independent from worker and coordinator"
            )
        mission_id = envelope["mission_id"]
        assessment = {
            "task_id": task_id,
            "result_digest": receipts[-1].result_digest,
            "evidence_refs": sorted(set(evidence_refs)),
            "dissent_refs": sorted(set(dissent_refs)),
            "verifier_identity": verifier_identity,
            "accepted": bool(accepted),
            "model_prediction": False,
        }
        assessment_ref = content_digest(assessment)
        if not accepted:
            self.record_exception(
                mission_id,
                kind="evaluator_disagreement",
                details={
                    "task_id": task_id,
                    "assessment_ref": assessment_ref,
                    "dissent_refs": sorted(set(dissent_refs)),
                    "status": "NEEDS_FOUNDER_DECISION",
                },
                evidence_refs=tuple(evidence_refs),
            )
            return None
        return self.task_fabric.transition(
            task_id,
            "VERIFIED",
            actor=verifier_identity,
            transition_key=transition_key or "task:verify:" + task_id + ":" + assessment_ref,
            evidence_refs=tuple(evidence_refs),
            assessment_refs=(assessment_ref,),
            dissent_refs=tuple(dissent_refs),
            dissent_preserved=True,
        )

    def close_task(
        self,
        task_id: str,
        *,
        transition_key: str | None = None,
    ) -> TaskReceipt:
        envelope = self.task_fabric.envelope(task_id)
        return self.task_fabric.transition(
            task_id,
            "CLOSED",
            actor=self.source_identity,
            transition_key=transition_key or "task:close:" + task_id,
            evidence_refs=("task:" + task_id + ":verified",),
        )

    # -------------------------------------------------------- exceptions/end
    def record_exception(
        self,
        mission_id: str,
        *,
        kind: str,
        details: Mapping[str, Any],
        evidence_refs: Sequence[str] = (),
    ) -> Event:
        mission = self._mission(mission_id)
        if not kind.strip():
            raise MissionRuntimeError("exception kind is required")
        payload = {
            "mission_id": mission_id,
            "exception_id": content_digest({
                "mission_id": mission_id,
                "kind": kind,
                "details": copy.deepcopy(dict(details)),
                "evidence_refs": sorted(set(evidence_refs)),
            }),
            "kind": kind,
            "details": copy.deepcopy(dict(details)),
            "evidence_refs": sorted(set(evidence_refs)),
            "status": "NEEDS_FOUNDER_DECISION",
            "requires_canonical_founder_authentication": True,
            "evidence_mode": self.evidence_mode,
            "authority_created": 0,
            "external_effects": 0,
        }
        existing = [
            event for event in self._mission_events(mission_id, "mission.exception")
            if event.payload.get("exception_id") == payload["exception_id"]
        ]
        if existing:
            return existing[-1]
        return self._emit(
            "mission.exception",
            payload,
            legal_principal=mission["legal_principal"],
            sensitivity=_sensitivity(mission),
        )

    def finalize(self, mission_id: str, *, evidence_refs: Sequence[str]) -> Event:
        mission = self._mission(mission_id)
        tasks = {
            task_id: state
            for task_id, state in self.task_fabric.tasks().items()
            if self.task_fabric.envelope(task_id)["mission_id"] == mission_id
        }
        if not tasks:
            raise MissionRuntimeError("cannot finalize a mission without a task")
        if any(state != "CLOSED" for state in tasks.values()):
            raise MissionRuntimeError("all mission tasks must be CLOSED before finalization")
        if not evidence_refs:
            raise MissionRuntimeError("finalization needs durable evidence_refs")
        exceptions = self._mission_events(mission_id, "mission.exception")
        closure_status = "INCOMPLETE" if exceptions else "SIMULATED_UNVERIFIED"
        payload = {
            "mission_id": mission_id,
            "closure_status": closure_status,
            "verified_durable_mission_closure": False,
            "evidence_refs": sorted(set(evidence_refs)),
            "task_states": tasks,
            "evidence_mode": self.evidence_mode,
            "founder_attention_measurement": "NOT_MEASURED",
            "founder_interventions_per_verified_outcome": "NOT_MEASURED",
            "authority_created": 0,
            "external_effects": 0,
            "retained_learning": {
                "status": "episode_not_validated",
                "losers_preserved": True,
                "organizational_knowledge_claim": False,
            },
        }
        previous = [
            event for event in self._mission_events(mission_id, "mission.closure_recorded")
            if event.payload.get("closure_status") == closure_status
        ]
        if previous:
            return previous[-1]
        return self._emit(
            "mission.closure_recorded",
            payload,
            legal_principal=mission["legal_principal"],
            sensitivity=_sensitivity(mission),
        )

    def dissolve(
        self,
        mission_id: str,
        *,
        evidence_refs: Sequence[str],
        open_obligation_refs: Sequence[str] = (),
        transition_key: str = "mission:dissolve",
    ) -> Event:
        mission = self._mission(mission_id)
        return self.task_fabric.dissolve_mission(
            mission_id,
            actor=self.source_identity,
            transition_key=transition_key,
            evidence_refs=tuple(evidence_refs),
            open_obligation_refs=tuple(open_obligation_refs),
        )

    # --------------------------------------------------------------- operator
    def snapshot(self, mission_id: str) -> MissionSnapshot:
        mission = self._mission(mission_id)
        admissions = self._admission_event(mission_id)
        routes = self._mission_events(mission_id, "mission.routed")
        cognition = self._mission_events(mission_id, "mission.cognition")
        exceptions = self._mission_events(mission_id, "mission.exception")
        closures = self._mission_events(mission_id, "mission.closure_recorded")
        dissolved = self._mission_events(mission_id, "mission.organization_dissolved")
        task_states = {
            task_id: state
            for task_id, state in self.task_fabric.tasks().items()
            if self.task_fabric.envelope(task_id)["mission_id"] == mission_id
        }
        if dissolved:
            status = "DISSOLVED"
        elif closures:
            status = closures[-1].payload["closure_status"]
        elif exceptions:
            status = "NEEDS_FOUNDER_DECISION"
        elif task_states:
            status = "TASKS_IN_FLIGHT"
        elif routes:
            status = "ROUTED"
        elif cognition:
            status = "COGNIZED"
        else:
            status = "ADMITTED"
        route = routes[-1].payload if routes else {}
        return MissionSnapshot(
            mission_id=mission_id,
            mission_digest=admissions.payload["mission_digest"],
            status=status,
            trigger_id=admissions.payload["trigger_id"],
            route_id=route.get("resolution_id"),
            selected_candidate_id=(
                route.get("resolution", {}).get("selected_candidate_id")
            ),
            task_states=task_states,
            exception_refs=tuple(
                event.payload["exception_id"] for event in exceptions
            ),
            closure_status=closures[-1].payload["closure_status"] if closures else None,
            evidence_mode=admissions.payload["evidence_mode"],
        )

    def founder_inbox(self, mission_id: str) -> str:
        """One concise owner-facing status; it is not a command channel."""
        snapshot = self.snapshot(mission_id)
        if snapshot.status == "NEEDS_FOUNDER_DECISION":
            latest = self._mission_events(mission_id, "mission.exception")[-1]
            return (
                "NEEDS_FOUNDER_DECISION: "
                + latest.payload["kind"]
                + "; "
                + str(latest.payload["details"])
                + ". Runtime commands remain refused until canonical "
                  "founder authentication exists."
            )
        if snapshot.closure_status:
            return (
                snapshot.closure_status
                + ": mission "
                + mission_id
                + " retained in EventSpine; no external effect occurred."
            )
        return (
            snapshot.status
            + ": mission "
            + mission_id
            + "; selected="
            + str(snapshot.selected_candidate_id)
            + "; no external effect occurred."
        )


__all__ = [
    "CathedralMetabolismRuntime",
    "DEFAULT_EVALUATOR_IDENTITY",
    "FounderAuthenticationRequired",
    "FounderCommandSurface",
    "MissionAdmission",
    "MissionRuntimeError",
    "MissionSnapshot",
    "SIMULATION_WORKER_PREFIX",
    "SOURCE_IDENTITY",
]