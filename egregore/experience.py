"""Experience integration: signals become a provenance-backed world model (target F).

An ``ExperienceEvent`` is not raw telemetry. It is a signal that has been
attributed, interpreted into typed observations, related to goals, and
integrated into persistent beliefs. Contradictions between sources are
retained side by side; they are never averaged away.

No model calls. Deterministic. Ledger-hydrated.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence

from .contracts import ContractError, IntegrityConflict, SignalEnvelope, canonical_copy, digest, require_text
from .goals import GoalSpec, iso, parse_time

TRUST_LEVELS = ("untrusted", "attributed", "verified")


class ExperienceError(ContractError):
    """Malformed observation or integration request."""


@dataclass(frozen=True)
class Observation:
    subject: str
    attribute: str
    value: Any
    confidence: float
    source: str
    observed_at: str
    evidence_refs: tuple[str, ...]
    trust_level: str

    @property
    def key(self) -> str:
        return f"{self.subject}.{self.attribute}"

    @classmethod
    def build(cls, *, subject: str, attribute: str, value: Any, confidence: float, source: str,
              observed_at: str, evidence_refs: Sequence[str] = (), trust_level: str = "untrusted") -> "Observation":
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0.0 <= float(confidence) <= 1.0:
            raise ExperienceError("confidence must be between 0 and 1")
        if trust_level not in TRUST_LEVELS:
            raise ExperienceError(f"unknown trust level {trust_level!r}")
        if isinstance(value, (dict, list)):
            raise ExperienceError("observation values must be scalars")
        return cls(subject=require_text("subject", subject), attribute=require_text("attribute", attribute),
                   value=canonical_copy(value), confidence=float(confidence), source=require_text("source", source),
                   observed_at=iso(parse_time(observed_at)),
                   evidence_refs=tuple(require_text("evidence_refs[]", r) for r in evidence_refs),
                   trust_level=trust_level)

    def to_dict(self) -> dict[str, Any]:
        return {"subject": self.subject, "attribute": self.attribute, "value": self.value,
                "confidence": self.confidence, "source": self.source, "observed_at": self.observed_at,
                "evidence_refs": list(self.evidence_refs), "trust_level": self.trust_level}


@dataclass(frozen=True)
class Belief:
    subject: str
    attribute: str
    value: Any
    confidence: float
    observed_at: str
    integrated_at: str
    source: str
    signal_id: str
    evidence_refs: tuple[str, ...]
    contradicted: bool
    alternatives: tuple[dict[str, Any], ...]

    @property
    def key(self) -> str:
        return f"{self.subject}.{self.attribute}"

    def to_dict(self) -> dict[str, Any]:
        return {"subject": self.subject, "attribute": self.attribute, "value": self.value,
                "confidence": self.confidence, "observed_at": self.observed_at, "integrated_at": self.integrated_at,
                "source": self.source, "signal_id": self.signal_id, "evidence_refs": list(self.evidence_refs),
                "contradicted": self.contradicted, "alternatives": [canonical_copy(a) for a in self.alternatives]}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Belief":
        return cls(subject=value["subject"], attribute=value["attribute"], value=value["value"],
                   confidence=value["confidence"], observed_at=value["observed_at"],
                   integrated_at=value["integrated_at"], source=value["source"], signal_id=value["signal_id"],
                   evidence_refs=tuple(value.get("evidence_refs", ())), contradicted=bool(value.get("contradicted")),
                   alternatives=tuple(canonical_copy(a) for a in value.get("alternatives", ())))


@dataclass(frozen=True)
class ExperienceEvent:
    experience_id: str
    signal_id: str
    source: str
    observed_at: str
    integrated_at: str
    observations: tuple[dict[str, Any], ...]
    goal_relevance: dict[str, float]
    changes: tuple[dict[str, Any], ...]
    context: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"experience_id": self.experience_id, "signal_id": self.signal_id, "source": self.source,
                "observed_at": self.observed_at, "integrated_at": self.integrated_at,
                "observations": [canonical_copy(o) for o in self.observations],
                "goal_relevance": canonical_copy(self.goal_relevance),
                "changes": [canonical_copy(c) for c in self.changes], "context": canonical_copy(self.context)}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ExperienceEvent":
        return cls(experience_id=value["experience_id"], signal_id=value["signal_id"], source=value["source"],
                   observed_at=value["observed_at"], integrated_at=value["integrated_at"],
                   observations=tuple(canonical_copy(o) for o in value["observations"]),
                   goal_relevance=canonical_copy(value.get("goal_relevance", {})),
                   changes=tuple(canonical_copy(c) for c in value.get("changes", ())),
                   context=canonical_copy(value.get("context", {})))


def _values_agree(a: Any, b: Any, tolerance: float) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= tolerance
    return a == b


class WorldModel:
    """Persistent beliefs with provenance; contradictions preserved."""

    EXPERIENCE_RECORD = "egregore.experience_integrated"
    CONTRADICTION_RECORD = "egregore.experience_contradiction"

    def __init__(self, *, ledger: Any, source: str = "spiffe://uniimente.internal/egregore/goal-gravity",
                 tolerance: float = 1e-9):
        if not hasattr(ledger, "append") or not hasattr(ledger, "by_type"):
            raise ExperienceError("ledger must provide append() and by_type()")
        self.ledger = ledger
        self.source = require_text("source", source)
        self.tolerance = float(tolerance)
        self._beliefs: dict[str, Belief] = {}
        self._events: dict[str, ExperienceEvent] = {}
        self._contradictions: list[dict[str, Any]] = []
        self._hydrate()

    @property
    def execution_authority(self) -> str:
        return "none"

    def _hydrate(self) -> None:
        for record in getattr(self.ledger, "records", ()):
            rtype = getattr(record, "record_type", None)
            payload = getattr(record, "payload", {})
            if rtype == self.EXPERIENCE_RECORD:
                event = ExperienceEvent.from_dict(payload["experience"])
                existing = self._events.get(event.signal_id)
                if existing is not None and existing.experience_id != event.experience_id:
                    raise IntegrityConflict("ledger contains conflicting experience for one signal")
                self._events[event.signal_id] = event
                for belief in payload.get("beliefs", ()):
                    b = Belief.from_dict(belief)
                    self._beliefs[b.key] = b
            elif rtype == self.CONTRADICTION_RECORD:
                self._contradictions.append(canonical_copy(payload))

    # ------------------------------------------------------------ observations
    @staticmethod
    def observations_from_signal(signal: SignalEnvelope) -> tuple[Observation, ...]:
        """Typed observations travel in ``payload['observations']``; text stays data."""
        raw = signal.payload.get("observations", ())
        if isinstance(raw, (str, bytes)) or not isinstance(raw, (list, tuple)):
            raise ExperienceError("payload.observations must be a list")
        out = []
        for item in raw:
            if not isinstance(item, Mapping):
                raise ExperienceError("each observation must be an object")
            out.append(Observation.build(
                subject=item["subject"], attribute=item["attribute"], value=item["value"],
                confidence=item.get("confidence", 0.5), source=signal.source,
                observed_at=item.get("observed_at", signal.observed_at),
                evidence_refs=tuple(signal.evidence_refs) + tuple(item.get("evidence_refs", ())),
                trust_level=item.get("trust_level", signal.trust_level if signal.trust_level in TRUST_LEVELS else "untrusted")))
        return tuple(out)

    # ------------------------------------------------------------ integration
    def integrate(self, signal: SignalEnvelope, *, now: datetime | str,
                  goal_relevance: Mapping[str, float] | None = None,
                  context: Mapping[str, Any] | None = None) -> ExperienceEvent:
        if not isinstance(signal, SignalEnvelope):
            raise ExperienceError("integrate requires a SignalEnvelope")
        existing = self._events.get(signal.signal_id)
        if existing is not None:
            return ExperienceEvent.from_dict(existing.to_dict())
        integrated_at = iso(parse_time(now))
        observations = self.observations_from_signal(signal)
        changes: list[dict[str, Any]] = []
        new_beliefs: list[Belief] = []
        contradictions: list[dict[str, Any]] = []
        for obs in observations:
            previous = self._beliefs.get(obs.key)
            if previous is None:
                belief = Belief(obs.subject, obs.attribute, obs.value, obs.confidence, obs.observed_at, integrated_at,
                                obs.source, signal.signal_id, obs.evidence_refs, False, ())
                changes.append({"key": obs.key, "previous": None, "current": obs.value, "updated": True,
                                "contradiction": False, "disposition": "new_belief"})
            elif previous.source == obs.source or _values_agree(previous.value, obs.value, self.tolerance):
                # Same source refines itself; agreeing sources corroborate.
                corroborated = previous.source != obs.source
                belief = Belief(obs.subject, obs.attribute, obs.value,
                                max(previous.confidence, obs.confidence) if corroborated else obs.confidence,
                                obs.observed_at, integrated_at, obs.source, signal.signal_id,
                                tuple(dict.fromkeys(previous.evidence_refs + obs.evidence_refs)),
                                False if corroborated else previous.contradicted and previous.source != obs.source,
                                () if corroborated else previous.alternatives)
                changes.append({"key": obs.key, "previous": previous.value, "current": obs.value,
                                "updated": not _values_agree(previous.value, obs.value, self.tolerance),
                                "contradiction": False,
                                "disposition": "corroborated" if corroborated else "refreshed"})
            else:
                # Different source, different value: retain both; never collapse.
                alternative = {"value": obs.value, "confidence": obs.confidence, "source": obs.source,
                               "observed_at": obs.observed_at, "signal_id": signal.signal_id,
                               "evidence_refs": list(obs.evidence_refs)}
                keep_new = obs.confidence > previous.confidence
                if keep_new:
                    alternatives = ({"value": previous.value, "confidence": previous.confidence,
                                     "source": previous.source, "observed_at": previous.observed_at,
                                     "signal_id": previous.signal_id,
                                     "evidence_refs": list(previous.evidence_refs)},) + previous.alternatives
                    belief = Belief(obs.subject, obs.attribute, obs.value, obs.confidence, obs.observed_at,
                                    integrated_at, obs.source, signal.signal_id, obs.evidence_refs, True, alternatives)
                else:
                    belief = Belief(previous.subject, previous.attribute, previous.value, previous.confidence,
                                    previous.observed_at, integrated_at, previous.source, previous.signal_id,
                                    previous.evidence_refs, True, previous.alternatives + (alternative,))
                contradiction = {"source": self.source, "key": obs.key, "signal_id": signal.signal_id,
                                 "retained_belief": belief.to_dict(), "incoming": obs.to_dict(),
                                 "disposition": "both_retained_not_collapsed", "detected_at": integrated_at}
                contradictions.append(contradiction)
                changes.append({"key": obs.key, "previous": previous.value, "current": belief.value,
                                "updated": keep_new, "contradiction": True, "disposition": "contradiction_retained"})
            new_beliefs.append(belief)
        event = ExperienceEvent(
            experience_id=digest({"kind": "egregore-experience", "signal_id": signal.signal_id}),
            signal_id=signal.signal_id, source=signal.source, observed_at=signal.observed_at,
            integrated_at=integrated_at, observations=tuple(o.to_dict() for o in observations),
            goal_relevance=canonical_copy(dict(goal_relevance or {})), changes=tuple(changes),
            context=canonical_copy(dict(context or {})))
        self.ledger.append(self.EXPERIENCE_RECORD, {
            "source": self.source, "experience": event.to_dict(),
            "beliefs": [b.to_dict() for b in new_beliefs], "instruction_status": "data_only"})
        for c in contradictions:
            self.ledger.append(self.CONTRADICTION_RECORD, c)
            self._contradictions.append(c)
        for b in new_beliefs:
            self._beliefs[b.key] = b
        self._events[signal.signal_id] = event
        return ExperienceEvent.from_dict(event.to_dict())

    # ------------------------------------------------------------ reads
    def belief(self, subject: str, attribute: str) -> Belief | None:
        b = self._beliefs.get(f"{subject}.{attribute}")
        return Belief.from_dict(b.to_dict()) if b else None

    def belief_by_key(self, key: str) -> Belief | None:
        b = self._beliefs.get(key)
        return Belief.from_dict(b.to_dict()) if b else None

    def beliefs(self) -> dict[str, Belief]:
        return {k: Belief.from_dict(v.to_dict()) for k, v in self._beliefs.items()}

    def contradictions(self) -> list[dict[str, Any]]:
        return [canonical_copy(c) for c in self._contradictions]

    def experiences(self) -> list[ExperienceEvent]:
        return [ExperienceEvent.from_dict(e.to_dict()) for e in self._events.values()]

    def experience_surface(self, *, goals: Sequence[GoalSpec] = (), now: datetime | str | None = None) -> dict[str, Any]:
        """Functional access to reality, measured. Not a consciousness score."""
        beliefs = list(self._beliefs.values())
        events = list(self._events.values())
        sources = {b.source for b in beliefs}
        with_provenance = sum(1 for b in beliefs if b.evidence_refs)
        latencies = []
        for e in events:
            latencies.append((parse_time(e.integrated_at) - parse_time(e.observed_at)).total_seconds())
        metrics_needed = {n.sbm for g in goals for n in g.plan}
        observed = {m for m in metrics_needed if m in self._beliefs}
        relevant_events = sum(1 for e in events if e.goal_relevance)
        return {
            "trusted_modalities": len(sources),
            "beliefs": len(beliefs),
            "provenance_coverage": (with_provenance / len(beliefs)) if beliefs else 0.0,
            "contradiction_rate": (len(self._contradictions) / len(beliefs)) if beliefs else 0.0,
            "contradictions_retained": len(self._contradictions),
            "mean_integration_latency_seconds": (sum(latencies) / len(latencies)) if latencies else None,
            "goal_metric_observability": (len(observed) / len(metrics_needed)) if metrics_needed else None,
            "experiences": len(events),
            "goal_relevant_experiences": relevant_events,
            "is_consciousness_score": False,
            "measured_at": iso(parse_time(now)) if now is not None else None,
        }
