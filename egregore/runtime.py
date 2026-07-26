"""Deterministic, proposal-only standing cognition.

An external scheduler may call :meth:`tick` as often as required.  A tick can
ingest evidence, ask proposer/evaluator organs for bounded judgments, retain
dissent, and select a candidate.  It cannot publish, transact, move funds, or
apply its own changes.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Mapping, Sequence

from .contracts import (
    Assessment,
    CandidateProposal,
    ChangeProposal,
    ContractError,
    IntegrityConflict,
    SignalEnvelope,
    canonical_copy,
    digest,
    require_hash,
    require_text,
)
from .resources import ResourceExhausted, ResourceGovernor, ResourceMode


class CycleStatus(str, Enum):
    SILENT = "silent"
    PROPOSED = "proposed"
    CONSERVING = "conserving"
    HIBERNATING = "hibernating"
    SUSPENDED = "suspended"
    REFUSED = "refused"


@dataclass(frozen=True)
class CognitionCycle:
    cycle_id: str
    trigger_id: str
    request_hash: str
    status: CycleStatus
    signal_ids: tuple[str, ...]
    candidates: tuple[CandidateProposal, ...]
    assessments: tuple[Assessment, ...]
    failures: tuple[dict[str, Any], ...]
    selected_candidate_id: str | None
    resource_snapshot: dict[str, Any]

    @property
    def execution_authority(self) -> str:
        return "none"

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "trigger_id": self.trigger_id,
            "request_hash": self.request_hash,
            "status": self.status.value,
            "signal_ids": list(self.signal_ids),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "assessments": [assessment.to_dict() for assessment in self.assessments],
            "failures": canonical_copy(list(self.failures)),
            "selected_candidate_id": self.selected_candidate_id,
            "resource_snapshot": canonical_copy(self.resource_snapshot),
            "execution_authority": self.execution_authority,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CognitionCycle":
        trigger_id = require_text("trigger_id", value["trigger_id"])
        expected_cycle_id = digest({"kind": "egregore-cycle", "trigger_id": trigger_id})
        if value["cycle_id"] != expected_cycle_id:
            raise IntegrityConflict("persisted cycle_id does not match trigger_id")
        return cls(
            cycle_id=expected_cycle_id,
            trigger_id=trigger_id,
            request_hash=require_hash("request_hash", value["request_hash"]),
            status=CycleStatus(value["status"]),
            signal_ids=tuple(value.get("signal_ids", ())),
            candidates=tuple(CandidateProposal.from_dict(item) for item in value.get("candidates", ())),
            assessments=tuple(Assessment.from_dict(item) for item in value.get("assessments", ())),
            failures=tuple(canonical_copy(value.get("failures", ()))),
            selected_candidate_id=value.get("selected_candidate_id"),
            resource_snapshot=canonical_copy(value.get("resource_snapshot", {})),
        )


Proposer = Callable[
    [tuple[SignalEnvelope, ...], dict[str, Any]],
    CandidateProposal | Sequence[CandidateProposal] | None,
]
Evaluator = Callable[[CandidateProposal, tuple[SignalEnvelope, ...], dict[str, Any]], Assessment]


class StandingCognitionRuntime:
    """A restartable deliberation organ with zero execution authority."""

    SIGNAL_RECORD = "egregore.signal_ingested"
    SIGNAL_CONFLICT_RECORD = "egregore.signal_conflict"
    CYCLE_RECORD = "egregore.cognition_cycle"
    CYCLE_CONFLICT_RECORD = "egregore.cycle_conflict"
    SUSPEND_RECORD = "egregore.suspended"
    RESUME_RECORD = "egregore.resumed"
    CHANGE_RECORD = "egregore.change_proposed"

    def __init__(
        self,
        *,
        ledger: Any,
        proposers: Mapping[str, Proposer],
        evaluators: Mapping[str, Evaluator],
        required_evaluators: Sequence[str] = ("guardian", "treasury"),
        source: str = "spiffe://uniimente.internal/egregore/standing-cognition",
    ):
        if not hasattr(ledger, "append") or not hasattr(ledger, "by_type"):
            raise ContractError("ledger must provide append() and by_type()")
        self.ledger = ledger
        self.source = require_text("source", source)
        self.proposers = self._validated_organs("proposers", proposers)
        self.evaluators = self._validated_organs("evaluators", evaluators)
        self.required_evaluators = tuple(
            require_text("required_evaluators[]", role) for role in required_evaluators
        )
        if not self.required_evaluators:
            raise ContractError("at least one required evaluator must be declared")
        if len(set(self.required_evaluators)) != len(self.required_evaluators):
            raise ContractError("required_evaluators must be unique")
        self._signals: dict[str, SignalEnvelope] = {}
        self._cycles: dict[str, CognitionCycle] = {}
        self._suspended = False
        self._hydrate()

    @staticmethod
    def _validated_organs(name: str, organs: Mapping[str, Callable]) -> dict[str, Callable]:
        if not isinstance(organs, Mapping):
            raise ContractError(f"{name} must be a mapping")
        result: dict[str, Callable] = {}
        for role, organ in organs.items():
            role = require_text(f"{name} role", role)
            if not callable(organ):
                raise ContractError(f"{name}[{role!r}] must be callable")
            result[role] = organ
        return result

    @property
    def is_suspended(self) -> bool:
        return self._suspended

    @property
    def execution_authority(self) -> str:
        return "none"

    def _hydrate(self) -> None:
        records = getattr(self.ledger, "records", ())
        for record in records:
            record_type = getattr(record, "record_type", None)
            payload = getattr(record, "payload", {})
            if record_type == self.SIGNAL_RECORD:
                signal = SignalEnvelope.from_dict(payload["signal"])
                existing = self._signals.get(signal.signal_id)
                if existing and existing.content_hash != signal.content_hash:
                    raise IntegrityConflict("ledger contains conflicting signal content")
                self._signals[signal.signal_id] = signal
            elif record_type == self.CYCLE_RECORD:
                cycle = CognitionCycle.from_dict(payload["cycle"])
                existing = self._cycles.get(cycle.trigger_id)
                if existing and existing.request_hash != cycle.request_hash:
                    raise IntegrityConflict("ledger contains conflicting cycle requests")
                self._cycles[cycle.trigger_id] = cycle
            elif record_type == self.SUSPEND_RECORD:
                self._suspended = True
            elif record_type == self.RESUME_RECORD:
                self._suspended = False

    def ingest(self, signal: SignalEnvelope) -> str:
        if not isinstance(signal, SignalEnvelope):
            raise ContractError("ingest requires a SignalEnvelope")
        # Rebuild from canonical content so caller-owned nested dictionaries
        # cannot mutate institutional memory after acceptance.
        signal = SignalEnvelope.from_dict(signal.to_dict())
        existing = self._signals.get(signal.signal_id)
        if existing:
            if existing.content_hash == signal.content_hash:
                return signal.signal_id
            self.ledger.append(
                self.SIGNAL_CONFLICT_RECORD,
                {
                    "source": self.source,
                    "signal_id": signal.signal_id,
                    "accepted_content_hash": existing.content_hash,
                    "conflicting_content_hash": signal.content_hash,
                    "conflicting_signal": signal.to_dict(),
                    "disposition": "refused_and_retained",
                },
            )
            raise IntegrityConflict("source_event_id was reused for different content")
        self.ledger.append(
            self.SIGNAL_RECORD,
            {"source": self.source, "signal": signal.to_dict(), "instruction_status": "data_only"},
        )
        self._signals[signal.signal_id] = signal
        return signal.signal_id

    def tick(
        self,
        *,
        trigger_id: str,
        signal_ids: Sequence[str],
        resources: ResourceGovernor,
        context: Mapping[str, Any] | None = None,
        call_costs: Mapping[str, float] | None = None,
        attention_telemetry: float | None = None,
    ) -> CognitionCycle:
        """Run one idempotent cognition tick and persist its complete trace."""
        trigger_id = require_text("trigger_id", trigger_id)
        if not isinstance(resources, ResourceGovernor):
            raise ContractError("resources must be a ResourceGovernor")
        clean_context = canonical_copy(dict(context or {}))
        clean_costs = canonical_copy(dict(call_costs or {}))
        ordered_signal_ids = tuple(sorted(set(signal_ids)))
        unknown = [signal_id for signal_id in ordered_signal_ids if signal_id not in self._signals]
        if unknown:
            raise ContractError(f"unknown signal ids: {unknown}")
        request_hash = digest(
            {
                "kind": "egregore-cycle-request",
                "trigger_id": trigger_id,
                "signal_ids": list(ordered_signal_ids),
                "context": clean_context,
                "call_costs": clean_costs,
                "attention_telemetry": attention_telemetry,
                "resource_limits": {
                    "max_model_calls": resources.max_model_calls,
                    "max_estimated_cost_usd": resources.max_estimated_cost_usd,
                    "conservation_threshold": resources.conservation_threshold,
                },
            }
        )
        existing = self._cycles.get(trigger_id)
        if existing:
            if existing.request_hash == request_hash:
                return CognitionCycle.from_dict(existing.to_dict())
            self.ledger.append(
                self.CYCLE_CONFLICT_RECORD,
                {
                    "source": self.source,
                    "trigger_id": trigger_id,
                    "accepted_request_hash": existing.request_hash,
                    "conflicting_request_hash": request_hash,
                    "disposition": "refused_and_retained",
                },
            )
            raise IntegrityConflict("trigger_id was reused for a different cognition request")

        signals = tuple(self._signals[signal_id] for signal_id in ordered_signal_ids)
        candidates: list[CandidateProposal] = []
        assessments: list[Assessment] = []
        failures: list[dict[str, Any]] = []

        if self._suspended:
            return self._finish_cycle(
                trigger_id=trigger_id,
                request_hash=request_hash,
                status=CycleStatus.SUSPENDED,
                signal_ids=ordered_signal_ids,
                candidates=candidates,
                assessments=assessments,
                failures=failures,
                selected_candidate_id=None,
                resources=resources,
                attention_telemetry=attention_telemetry,
            )
        if resources.mode == ResourceMode.HIBERNATE:
            return self._finish_cycle(
                trigger_id=trigger_id,
                request_hash=request_hash,
                status=CycleStatus.HIBERNATING,
                signal_ids=ordered_signal_ids,
                candidates=candidates,
                assessments=assessments,
                failures=failures,
                selected_candidate_id=None,
                resources=resources,
                attention_telemetry=attention_telemetry,
            )

        for proposer_name in sorted(self.proposers):
            component = f"proposer:{proposer_name}"
            try:
                resources.consume_call(
                    component=component,
                    estimated_cost_usd=self._call_cost(clean_costs, component),
                )
                produced = self.proposers[proposer_name](
                    self._copy_signals(signals),
                    canonical_copy(clean_context),
                )
                proposed = self._normalize_candidates(produced)
                for raw_candidate in proposed:
                    candidate = CandidateProposal.from_dict(raw_candidate.to_dict())
                    if candidate.proposed_by != proposer_name:
                        raise ContractError(
                            f"candidate proposed_by {candidate.proposed_by!r} does not match organ {proposer_name!r}"
                        )
                    if not set(candidate.source_signal_ids).issubset(ordered_signal_ids):
                        raise ContractError("candidate cites a signal outside this cognition tick")
                    candidates.append(candidate)
            except ResourceExhausted as exc:
                failures.append(self._failure(component, exc, disposition="budget_refusal"))
                break
            except Exception as exc:  # one organ cannot erase the others' trace
                failures.append(self._failure(component, exc))

        unique_candidates = {candidate.candidate_id: candidate for candidate in candidates}
        candidates = [unique_candidates[key] for key in sorted(unique_candidates)]

        for candidate in candidates:
            for role in sorted(self.evaluators):
                component = f"evaluator:{role}"
                try:
                    resources.consume_call(
                        component=component,
                        estimated_cost_usd=self._call_cost(clean_costs, component),
                    )
                    assessment = self.evaluators[role](
                        CandidateProposal.from_dict(candidate.to_dict()),
                        self._copy_signals(signals),
                        canonical_copy(clean_context),
                    )
                    if not isinstance(assessment, Assessment):
                        raise ContractError("evaluator must return Assessment")
                    if assessment.role != role:
                        raise ContractError("assessment role does not match evaluator role")
                    if assessment.candidate_id != candidate.candidate_id:
                        raise ContractError("assessment references a different candidate")
                    assessments.append(Assessment.from_dict(assessment.to_dict()))
                except ResourceExhausted as exc:
                    failures.append(
                        self._failure(component, exc, candidate_id=candidate.candidate_id, disposition="budget_refusal")
                    )
                    break
                except Exception as exc:
                    failures.append(self._failure(component, exc, candidate_id=candidate.candidate_id))

        selected_candidate_id = self._select(candidates, assessments)
        if selected_candidate_id:
            status = CycleStatus.PROPOSED
        elif resources.mode == ResourceMode.HIBERNATE:
            status = CycleStatus.HIBERNATING
        elif resources.mode == ResourceMode.CONSERVE:
            status = CycleStatus.CONSERVING
        elif candidates or failures:
            status = CycleStatus.REFUSED
        else:
            status = CycleStatus.SILENT
        return self._finish_cycle(
            trigger_id=trigger_id,
            request_hash=request_hash,
            status=status,
            signal_ids=ordered_signal_ids,
            candidates=candidates,
            assessments=assessments,
            failures=failures,
            selected_candidate_id=selected_candidate_id,
            resources=resources,
            attention_telemetry=attention_telemetry,
        )

    @staticmethod
    def _normalize_candidates(
        value: CandidateProposal | Sequence[CandidateProposal] | None,
    ) -> tuple[CandidateProposal, ...]:
        if value is None:
            return ()
        if isinstance(value, CandidateProposal):
            return (value,)
        if isinstance(value, (str, bytes)):
            raise ContractError("proposer returned text instead of proposal contracts")
        result = tuple(value)
        if not all(isinstance(item, CandidateProposal) for item in result):
            raise ContractError("proposer returned a non-CandidateProposal value")
        return result

    @staticmethod
    def _copy_signals(signals: Sequence[SignalEnvelope]) -> tuple[SignalEnvelope, ...]:
        return tuple(SignalEnvelope.from_dict(signal.to_dict()) for signal in signals)

    @staticmethod
    def _call_cost(costs: Mapping[str, Any], component: str) -> float:
        value = costs.get(component, 0.0)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ContractError(f"call cost for {component} must be numeric")
        return float(value)

    @staticmethod
    def _failure(component: str, exc: Exception, **extra: Any) -> dict[str, Any]:
        return {
            "component": component,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "disposition": extra.pop("disposition", "isolated_and_retained"),
            **extra,
        }

    def _select(
        self,
        candidates: Sequence[CandidateProposal],
        assessments: Sequence[Assessment],
    ) -> str | None:
        eligible: list[tuple[float, str]] = []
        for candidate in candidates:
            candidate_assessments = [
                item for item in assessments if item.candidate_id == candidate.candidate_id
            ]
            by_role = {item.role: item for item in candidate_assessments}
            if not all(role in by_role for role in self.required_evaluators):
                continue
            if any(item.veto for item in candidate_assessments):
                continue
            total_confidence = sum(item.confidence for item in candidate_assessments)
            if total_confidence <= 0:
                continue
            score = sum(item.score * item.confidence for item in candidate_assessments) / total_confidence
            if score >= 0:
                eligible.append((score, candidate.candidate_id))
        if not eligible:
            return None
        # A content digest breaks equal-score ties, independent of organ order.
        return sorted(eligible, key=lambda item: (-item[0], item[1]))[0][1]

    def _finish_cycle(
        self,
        *,
        trigger_id: str,
        request_hash: str,
        status: CycleStatus,
        signal_ids: Sequence[str],
        candidates: Sequence[CandidateProposal],
        assessments: Sequence[Assessment],
        failures: Sequence[dict[str, Any]],
        selected_candidate_id: str | None,
        resources: ResourceGovernor,
        attention_telemetry: float | None,
    ) -> CognitionCycle:
        cycle = CognitionCycle(
            cycle_id=digest({"kind": "egregore-cycle", "trigger_id": trigger_id}),
            trigger_id=trigger_id,
            request_hash=request_hash,
            status=status,
            signal_ids=tuple(signal_ids),
            candidates=tuple(candidates),
            assessments=tuple(assessments),
            failures=tuple(canonical_copy(list(failures))),
            selected_candidate_id=selected_candidate_id,
            resource_snapshot=resources.snapshot(attention_telemetry=attention_telemetry).to_dict(),
        )
        self.ledger.append(
            self.CYCLE_RECORD,
            {
                "source": self.source,
                "cycle": cycle.to_dict(),
                "disposition": "proposal_only",
            },
        )
        # Keep an internal canonical copy separate from the caller's return
        # value, whose nested JSON fields are necessarily mutable Python data.
        self._cycles[trigger_id] = CognitionCycle.from_dict(cycle.to_dict())
        return cycle

    def selected_candidate(self, cycle: CognitionCycle) -> CandidateProposal | None:
        if cycle.selected_candidate_id is None:
            return None
        candidate = next(
            candidate
            for candidate in cycle.candidates
            if candidate.candidate_id == cycle.selected_candidate_id
        )
        return CandidateProposal.from_dict(candidate.to_dict())

    def suspend(self, *, actor: str, reason: str) -> str:
        """Stop future cognition unconditionally; no grant is needed to stop."""
        record = self.ledger.append(
            self.SUSPEND_RECORD,
            {
                "source": self.source,
                "actor": require_text("actor", actor),
                "reason": require_text("reason", reason),
                "previously_suspended": self._suspended,
            },
        )
        self._suspended = True
        return record.hash

    def resume(self, *, actor: str, authorization_hash: str) -> str:
        """Resume only from an externally issued, hash-bound authorization."""
        if not self._suspended:
            raise ContractError("runtime is not suspended")
        record = self.ledger.append(
            self.RESUME_RECORD,
            {
                "source": self.source,
                "actor": require_text("actor", actor),
                "authorization_hash": require_hash("authorization_hash", authorization_hash),
            },
        )
        self._suspended = False
        return record.hash

    def propose_change(self, change: ChangeProposal) -> str:
        """Record a patch proposal.  There is intentionally no apply method."""
        if not isinstance(change, ChangeProposal):
            raise ContractError("propose_change requires a ChangeProposal")
        change = ChangeProposal.from_dict(change.to_dict())
        record = self.ledger.append(
            self.CHANGE_RECORD,
            {"source": self.source, "change": change.to_dict(), "disposition": "awaiting_external_review"},
        )
        return record.hash
