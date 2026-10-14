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

from .contract_check import validate_record
from capabilities.router import EPISTEMIC_METHODS, HUMAN_ONLY_METHODS

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
    method: str | None = None          # epistemic method (capabilities.router.EPISTEMIC_METHODS) that produced it
    method_refused: bool = False       # a human-only method was claimed outside the founder-answer path

    @property
    def key(self) -> str:
        return f"{self.subject}.{self.attribute}"

    @property
    def establishes(self) -> str | None:
        """What this observation can count as, from the Competency Compiler's table; never self-declared."""
        return EPISTEMIC_METHODS[self.method]["establishes"] if self.method else None

    @classmethod
    def build(cls, *, subject: str, attribute: str, value: Any, confidence: float, source: str,
              observed_at: str, evidence_refs: Sequence[str] = (), trust_level: str = "untrusted",
              method: str | None = None, method_refused: bool = False) -> "Observation":
        if method is not None and method not in EPISTEMIC_METHODS:
            raise ExperienceError(f"unknown epistemic method {method!r}")
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
                   trust_level=trust_level, method=method, method_refused=bool(method_refused))

    def to_dict(self) -> dict[str, Any]:
        out = {"subject": self.subject, "attribute": self.attribute, "value": self.value,
               "confidence": self.confidence, "source": self.source, "observed_at": self.observed_at,
               "evidence_refs": list(self.evidence_refs), "trust_level": self.trust_level}
        if self.method:
            out["method"] = self.method
            out["establishes"] = self.establishes
        if self.method_refused:
            out["method_refused"] = True
        return out


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
    trust_level: str = "untrusted"
    record_hash: str | None = None   # ledger hash of the experience record that set this belief
    method: str | None = None        # epistemic method behind the current value (None = untyped)
    establishes: str | None = None   # what the current value can count as (router table)

    @property
    def key(self) -> str:
        return f"{self.subject}.{self.attribute}"

    def to_dict(self) -> dict[str, Any]:
        return {"subject": self.subject, "attribute": self.attribute, "value": self.value,
                "confidence": self.confidence, "observed_at": self.observed_at, "integrated_at": self.integrated_at,
                "source": self.source, "signal_id": self.signal_id, "evidence_refs": list(self.evidence_refs),
                "contradicted": self.contradicted, "alternatives": [canonical_copy(a) for a in self.alternatives],
                "trust_level": self.trust_level, "record_hash": self.record_hash,
                "method": self.method, "establishes": self.establishes}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Belief":
        return cls(subject=value["subject"], attribute=value["attribute"], value=value["value"],
                   confidence=value["confidence"], observed_at=value["observed_at"],
                   integrated_at=value["integrated_at"], source=value["source"], signal_id=value["signal_id"],
                   evidence_refs=tuple(value.get("evidence_refs", ())), contradicted=bool(value.get("contradicted")),
                   alternatives=tuple(canonical_copy(a) for a in value.get("alternatives", ())),
                   trust_level=value.get("trust_level", "untrusted"), record_hash=value.get("record_hash"),
                   method=value.get("method"), establishes=value.get("establishes"))


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
    effects: dict[str, Any] = None  # type: ignore[assignment]
    content_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"experience_id": self.experience_id, "signal_id": self.signal_id, "source": self.source,
                "observed_at": self.observed_at, "integrated_at": self.integrated_at,
                "observations": [canonical_copy(o) for o in self.observations],
                "goal_relevance": canonical_copy(self.goal_relevance),
                "changes": [canonical_copy(c) for c in self.changes], "context": canonical_copy(self.context),
                "effects": canonical_copy(self.effects or {}), "content_hash": self.content_hash}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ExperienceEvent":
        return cls(experience_id=value["experience_id"], signal_id=value["signal_id"], source=value["source"],
                   observed_at=value["observed_at"], integrated_at=value["integrated_at"],
                   observations=tuple(canonical_copy(o) for o in value["observations"]),
                   goal_relevance=canonical_copy(value.get("goal_relevance", {})),
                   changes=tuple(canonical_copy(c) for c in value.get("changes", ())),
                   context=canonical_copy(value.get("context", {})),
                   effects=canonical_copy(value.get("effects", {})), content_hash=value.get("content_hash", ""))


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
    CONFLICT_RECORD = "egregore.experience_conflict"
    TRUST_RANK = {"untrusted": 0, "attributed": 1, "verified": 2}

    def __init__(self, *, ledger: Any, source: str = "spiffe://uniimente.internal/egregore/goal-gravity",
                 tolerance: float = 1e-9):
        if not all(hasattr(ledger, name) for name in ("append", "by_type", "records")):
            raise ExperienceError("ledger must provide append(), by_type() and records (hydration source)")
        self.ledger = ledger
        self.source = require_text("source", source)
        self.tolerance = float(tolerance)
        self._beliefs: dict[str, Belief] = {}
        self._events: dict[str, ExperienceEvent] = {}
        self._record_hashes: dict[str, str] = {}   # signal_id -> ledger hash of its experience record
        self._contradictions: list[dict[str, Any]] = []
        # (goal_id, subject.attribute) -> the latest founder decision recorded for that goal (founder-answer path only).
        self._human: dict[tuple[str, str], dict[str, Any]] = {}
        self._folded = 0
        self._hydrate()

    @property
    def execution_authority(self) -> str:
        return "none"

    def sync(self) -> None:
        """Fold experience records other writers appended since the last fold."""
        self._hydrate()

    def _hydrate(self) -> None:
        records = getattr(self.ledger, "records", ())
        for record in records[self._folded:]:
            rtype = getattr(record, "record_type", None)
            payload = getattr(record, "payload", {})
            if rtype == self.EXPERIENCE_RECORD:
                event = ExperienceEvent.from_dict(payload["experience"])
                existing = self._events.get(event.signal_id)
                if existing is not None and existing.experience_id != event.experience_id:
                    raise IntegrityConflict("ledger contains conflicting experience for one signal")
                self._events[event.signal_id] = event
                record_hash = getattr(record, "hash", None)
                self._record_hashes[event.signal_id] = record_hash
                self._fold_human(event, record_hash)
                for belief in payload.get("beliefs", ()):
                    b = Belief.from_dict(belief)
                    if b.signal_id == event.signal_id and b.record_hash is None:
                        b = Belief(**{**b.__dict__, "record_hash": record_hash})   # restored after restart too
                    self._beliefs[b.key] = b
            elif rtype == self.CONTRADICTION_RECORD:
                self._contradictions.append(canonical_copy(payload))
        self._folded = len(records)

    def _fold_human(self, event: "ExperienceEvent", record_hash: str | None) -> None:
        """Index founder decisions by the goal they were given for. Human-only methods survive integration only
        on the founder-answer path, so every such observation on the ledger is a founder answer."""
        goals = [g for g, score in (event.goal_relevance or {}).items() if score and score > 0]
        for o in event.observations:
            if o.get("method") in HUMAN_ONLY_METHODS and not o.get("method_refused"):
                for goal_id in goals:
                    self._human[(goal_id, f"{o['subject']}.{o['attribute']}")] = {
                        "value": o["value"], "observed_at": o["observed_at"], "trust_level": o["trust_level"],
                        "method": o["method"], "establishes": EPISTEMIC_METHODS[o["method"]]["establishes"],
                        "signal_id": event.signal_id, "record_hash": record_hash}

    def human_reading(self, goal_id: str, key: str) -> dict[str, Any] | None:
        """The latest founder decision recorded for this goal under this key (a later answer supersedes)."""
        self._hydrate()
        found = self._human.get((goal_id, key))
        return canonical_copy(found) if found else None

    # ------------------------------------------------------------ observations
    @staticmethod
    def observations_from_signal(signal: SignalEnvelope, *, allow_human_methods: bool = False) -> tuple[Observation, ...]:
        """Typed observations travel in ``payload['observations']``; text stays data.

        An observation may name the epistemic method that produced it. Human-only methods
        (``human_decision``, ``legal_determination``) are accepted only on the founder-answer path;
        anywhere else the claim is stripped, the observation is marked untrusted and the refusal is kept.
        """
        raw = signal.payload.get("observations", ())
        if isinstance(raw, (str, bytes)) or not isinstance(raw, (list, tuple)):
            raise ExperienceError("payload.observations must be a list")
        out = []
        envelope_trust = signal.trust_level if signal.trust_level in TRUST_LEVELS else "untrusted"
        for item in raw:
            if not isinstance(item, Mapping):
                raise ExperienceError("each observation must be an object")
            missing = [k for k in ("subject", "attribute", "value") if k not in item]
            if missing:
                raise ExperienceError(f"observation missing {missing}")
            item_trust = item.get("trust_level", envelope_trust)
            if item_trust not in TRUST_LEVELS:
                raise ExperienceError(f"unknown trust level {item_trust!r}")
            # A payload may lower its own trust, never raise it above the envelope's.
            trust = min((item_trust, envelope_trust), key=lambda t: WorldModel.TRUST_RANK[t])
            method = item.get("method")
            refused = False
            if method is not None and method not in EPISTEMIC_METHODS:
                raise ExperienceError(f"unknown epistemic method {method!r}")
            if method in HUMAN_ONLY_METHODS and not allow_human_methods:
                method, refused, trust = None, True, "untrusted"
            out.append(Observation.build(
                subject=item["subject"], attribute=item["attribute"], value=item["value"],
                confidence=item.get("confidence", 0.5), source=signal.source,
                observed_at=item.get("observed_at", signal.observed_at),
                evidence_refs=tuple(signal.evidence_refs) + tuple(item.get("evidence_refs", ())),
                trust_level=trust, method=method, method_refused=refused))
        return tuple(out)

    # ------------------------------------------------------------ integration
    def integrate(self, signal: SignalEnvelope, *, now: datetime | str,
                  goal_relevance: Mapping[str, float] | None = None,
                  context: Mapping[str, Any] | None = None,
                  attention: Sequence[str] = (), allow_human_methods: bool = False) -> ExperienceEvent:
        """Integrate one signal. ``attention`` names the goals this signal is expected to wake."""
        if not isinstance(signal, SignalEnvelope):
            raise ExperienceError("integrate requires a SignalEnvelope")
        self._hydrate()
        existing = self._events.get(signal.signal_id)
        if existing is not None:
            if existing.content_hash and existing.content_hash != signal.content_hash:
                self.ledger.append(self.CONFLICT_RECORD, {
                    "source": self.source, "signal_id": signal.signal_id,
                    "accepted_content_hash": existing.content_hash, "conflicting_content_hash": signal.content_hash,
                    "disposition": "refused_and_retained"})
                raise IntegrityConflict("signal id reused with different content; conflict retained")
            return ExperienceEvent.from_dict(existing.to_dict())
        integrated_at = iso(parse_time(now))
        observed_at = iso(parse_time(signal.observed_at))   # a malformed timestamp never reaches the ledger
        observations = self.observations_from_signal(signal, allow_human_methods=allow_human_methods)
        changes: list[dict[str, Any]] = []
        new_beliefs: list[Belief] = []
        contradictions: list[dict[str, Any]] = []
        for obs in observations:
            previous = self._beliefs.get(obs.key)
            if previous is None:
                belief = Belief(obs.subject, obs.attribute, obs.value, obs.confidence, obs.observed_at, integrated_at,
                                obs.source, signal.signal_id, obs.evidence_refs, False, (), obs.trust_level)
                changes.append({"key": obs.key, "previous": None, "current": obs.value, "updated": True,
                                "contradiction": False, "disposition": "new_belief"})
            elif previous.source == obs.source and parse_time(obs.observed_at) < parse_time(previous.observed_at):
                # An older reading from the same source never overwrites a newer belief.
                belief = previous
                changes.append({"key": obs.key, "previous": previous.value, "current": previous.value, "updated": False,
                                "contradiction": previous.contradicted, "disposition": "stale_ignored"})
            elif previous.source == obs.source or _values_agree(previous.value, obs.value, self.tolerance):
                # Same source refines itself; agreeing sources corroborate. Alternatives that still
                # disagree with the refreshed value are kept, and the contradiction flag follows them.
                corroborated = previous.source != obs.source
                remaining = tuple(a for a in previous.alternatives
                                  if not _values_agree(a["value"], obs.value, self.tolerance) and a["source"] != obs.source)
                refs = tuple(dict.fromkeys(previous.evidence_refs + obs.evidence_refs))
                rank_o, rank_p = self.TRUST_RANK[obs.trust_level], self.TRUST_RANK[previous.trust_level]
                # Across sources one reading wins whole: value, trust and evidence type come from the more trusted
                # reading (a typed reading wins an equal-trust tie), so a low-trust corroborator can neither relabel
                # nor nudge a value a trusted source reported.
                keeps_previous = corroborated and (rank_p > rank_o or (rank_p == rank_o and previous.method and not obs.method))
                if keeps_previous:
                    belief = Belief(previous.subject, previous.attribute, previous.value,
                                    max(previous.confidence, obs.confidence), previous.observed_at, integrated_at,
                                    previous.source, previous.signal_id, refs, bool(remaining), remaining,
                                    previous.trust_level, previous.record_hash, previous.method, previous.establishes)
                else:
                    belief = Belief(obs.subject, obs.attribute, obs.value,
                                    max(previous.confidence, obs.confidence) if corroborated else obs.confidence,
                                    obs.observed_at, integrated_at, obs.source, signal.signal_id, refs,
                                    bool(remaining), remaining, obs.trust_level)
                changes.append({"key": obs.key, "previous": previous.value, "current": belief.value,
                                "updated": not _values_agree(previous.value, belief.value, self.tolerance),
                                "contradiction": bool(remaining),
                                "disposition": "corroborated" if corroborated else "refreshed"})
            else:
                # Different source, different value: retain both; never collapse.
                alternative = {"value": obs.value, "confidence": obs.confidence, "source": obs.source,
                               "observed_at": obs.observed_at, "signal_id": signal.signal_id,
                               "evidence_refs": list(obs.evidence_refs), "trust_level": obs.trust_level}
                if obs.method:
                    alternative["method"] = obs.method
                keep_new = obs.confidence > previous.confidence
                if keep_new:
                    displaced = {"value": previous.value, "confidence": previous.confidence,
                                 "source": previous.source, "observed_at": previous.observed_at,
                                 "signal_id": previous.signal_id, "trust_level": previous.trust_level,
                                 "evidence_refs": list(previous.evidence_refs)}
                    if previous.method:
                        displaced["method"] = previous.method
                    alternatives = (displaced,) + previous.alternatives
                    belief = Belief(obs.subject, obs.attribute, obs.value, obs.confidence, obs.observed_at,
                                    integrated_at, obs.source, signal.signal_id, obs.evidence_refs, True, alternatives,
                                    obs.trust_level)
                else:
                    belief = Belief(previous.subject, previous.attribute, previous.value, previous.confidence,
                                    previous.observed_at, integrated_at, previous.source, previous.signal_id,
                                    previous.evidence_refs, True, previous.alternatives + (alternative,),
                                    previous.trust_level, previous.record_hash, previous.method, previous.establishes)
                contradiction = {"source": self.source, "key": obs.key, "signal_id": signal.signal_id,
                                 "retained_belief": belief.to_dict(), "incoming": obs.to_dict(),
                                 "disposition": "both_retained_not_collapsed", "detected_at": integrated_at}
                contradictions.append(contradiction)
                changes.append({"key": obs.key, "previous": previous.value, "current": belief.value,
                                "updated": keep_new, "contradiction": True, "disposition": "contradiction_retained"})
            if belief.signal_id == signal.signal_id and belief.value == obs.value:
                # The belief now carries this observation's reading, so its evidence type follows the observation.
                # Within one source an untyped refresh of the same value keeps the earlier typed reading only when
                # that reading was at least as trusted (the type is then attested at this trust or better).
                keep_type = (previous is not None and previous.source == obs.source and previous.value == obs.value
                             and not obs.method and self.TRUST_RANK[previous.trust_level] >= self.TRUST_RANK[obs.trust_level])
                belief = Belief(**{**belief.__dict__, "method": previous.method if keep_type else obs.method,
                                   "establishes": previous.establishes if keep_type else obs.establishes})
            new_beliefs.append(belief)
        # Directive section 7: an experience may change memory, prediction, attention, learning or action.
        effects = {
            "memory": any(c["updated"] for c in changes),
            "prediction": any(c["contradiction"] for c in changes) or any(
                c["disposition"] == "corroborated" for c in changes),
            "attention": sorted(attention),
            "learning": "deferred: outcome records feed CausalMemory, not raw signals",
            "action": "deferred: the gravity turn classifies moves; a signal never acts",
        }
        event = ExperienceEvent(
            experience_id=digest({"kind": "egregore-experience", "signal_id": signal.signal_id}),
            signal_id=signal.signal_id, source=signal.source, observed_at=observed_at,
            integrated_at=integrated_at, observations=tuple(o.to_dict() for o in observations),
            goal_relevance=canonical_copy(dict(goal_relevance or {})), changes=tuple(changes),
            context=canonical_copy(dict(context or {})), effects=effects, content_hash=signal.content_hash)
        validate_record(event.to_dict(), "experience-event")
        record = self.ledger.append(self.EXPERIENCE_RECORD, {
            "source": self.source, "experience": event.to_dict(),
            "beliefs": [b.to_dict() for b in new_beliefs], "instruction_status": "data_only"})
        record_hash = getattr(record, "hash", None)
        for c in contradictions:
            self.ledger.append(self.CONTRADICTION_RECORD, c)
            self._contradictions.append(c)
        for b in new_beliefs:
            if b.signal_id == signal.signal_id:
                b = Belief(**{**b.__dict__, "record_hash": record_hash})
            self._beliefs[b.key] = b
        self._events[signal.signal_id] = event
        self._record_hashes[signal.signal_id] = record_hash
        self._fold_human(event, record_hash)
        self._folded = len(self.ledger.records)   # own records already applied in memory
        return ExperienceEvent.from_dict(event.to_dict())

    def record_hash(self, signal_id: str) -> str | None:
        """Ledger hash of the experience record for a signal: a real evidence reference."""
        self._hydrate()
        return self._record_hashes.get(signal_id)

    def evidence_for_goal(self, goal_id: str) -> tuple[list[str], float]:
        """Ledger-anchored evidence refs and relevance-weighted confidence for a goal's beliefs.

        Refs are experience-record hashes of signals relevant to the goal; confidence is the
        relevance-weighted mean confidence of the beliefs those signals set. No ref is fabricated:
        a goal nothing relevant has been observed for gets ([], 0.0).
        """
        self._hydrate()
        refs: list[str] = []
        weighted = 0.0
        weight = 0.0
        for event in self._events.values():
            score = event.goal_relevance.get(goal_id)
            if not score:
                continue
            h = self._record_hashes.get(event.signal_id)
            if h:
                refs.append(h)
            confidences = [o["confidence"] for o in event.observations]
            if confidences:
                weighted += score * (sum(confidences) / len(confidences))
                weight += score
        return refs, (weighted / weight) if weight else 0.0

    # ------------------------------------------------------------ reads
    def belief(self, subject: str, attribute: str) -> Belief | None:
        self._hydrate()
        b = self._beliefs.get(f"{subject}.{attribute}")
        return Belief.from_dict(b.to_dict()) if b else None

    def belief_by_key(self, key: str) -> Belief | None:
        self._hydrate()
        b = self._beliefs.get(key)
        return Belief.from_dict(b.to_dict()) if b else None

    def beliefs(self) -> dict[str, Belief]:
        self._hydrate()
        return {k: Belief.from_dict(v.to_dict()) for k, v in self._beliefs.items()}

    def contradictions(self) -> list[dict[str, Any]]:
        self._hydrate()
        return [canonical_copy(c) for c in self._contradictions]

    def experiences(self) -> list[ExperienceEvent]:
        self._hydrate()
        return [ExperienceEvent.from_dict(e.to_dict()) for e in self._events.values()]

    def experience_surface(self, *, goals: Sequence[GoalSpec] = (), now: datetime | str | None = None) -> dict[str, Any]:
        """Functional access to reality, measured. Not a consciousness score."""
        self._hydrate()
        beliefs = list(self._beliefs.values())
        events = list(self._events.values())
        sources = {b.source for b in beliefs if self.TRUST_RANK.get(b.trust_level, 0) >= self.TRUST_RANK["attributed"]}
        untrusted_sources = {b.source for b in beliefs} - sources
        with_provenance = sum(1 for b in beliefs if b.evidence_refs)
        latencies = []
        for e in events:
            try:
                latencies.append((parse_time(e.integrated_at) - parse_time(e.observed_at)).total_seconds())
            except Exception:
                continue   # a malformed historical record never wedges the surface
        metrics_needed = {n.sbm for g in goals for n in g.plan}
        observed = {m for m in metrics_needed if m in self._beliefs}
        relevant_events = sum(1 for e in events if e.goal_relevance)
        return {
            "trusted_modalities": len(sources),          # distinct sources with at least one attributed belief
            "untrusted_sources": len(untrusted_sources),
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
