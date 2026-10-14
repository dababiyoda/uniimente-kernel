"""Goal Relevance Router (target B): which goals might an incoming signal affect?

Deterministic matching of a signal's observations, tags and domain against
each goal's declared wake conditions. The score is the sum of matched
condition weights; a goal wakes when the score reaches its wake threshold.
Founder mutes (``do_not_monitor``) and ``stop_pushing`` are respected; completed, revoked,
paused and superseded goals never wake.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from .contracts import SignalEnvelope
from .experience import Observation, WorldModel
from .goals import GoalRegistry, GoalSpec


@dataclass(frozen=True)
class RelevanceVerdict:
    goal_id: str
    signal_id: str
    score: float
    matched: tuple[str, ...]
    wake: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"goal_id": self.goal_id, "signal_id": self.signal_id, "score": self.score,
                "matched": list(self.matched), "wake": self.wake, "reason": self.reason}


def _metric_crosses(direction: str, threshold: float, value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    if direction == "gte":
        return float(value) >= threshold
    if direction == "lte":
        return float(value) <= threshold
    return float(value) == threshold


def score_signal(spec: GoalSpec, signal: SignalEnvelope, observations: Sequence[Observation]) -> tuple[float, tuple[str, ...]]:
    tags = signal.payload.get("tags", ())
    tags = {t for t in tags if isinstance(t, str)} if isinstance(tags, (list, tuple)) else set()
    domain = signal.payload.get("domain")
    subjects = {o.subject for o in observations}
    by_key = {o.key: o for o in observations}
    score, matched = 0.0, []
    for cond in spec.wake_conditions:
        hit = False
        if cond.kind == "subject" and (cond.match in subjects or cond.match in spec.relevant_entities and cond.match in subjects):
            hit = True
        elif cond.kind == "tag" and cond.match in tags:
            hit = True
        elif cond.kind == "domain" and domain == cond.match:
            hit = True
        elif cond.kind == "metric" and cond.match in by_key and _metric_crosses(cond.direction, cond.threshold, by_key[cond.match].value):
            hit = True
        if hit:
            score += cond.weight
            matched.append(f"{cond.kind}:{cond.match}")
    # Plain relevant-entity mentions count a little even without a declared condition.
    entity_hits = [s for s in subjects if s in spec.relevant_entities]
    for s in entity_hits:
        if f"subject:{s}" not in matched:
            score += 0.25
            matched.append(f"entity:{s}")
    return score, tuple(matched)


class GoalRelevanceRouter:
    def __init__(self, registry: GoalRegistry):
        self.registry = registry

    @property
    def execution_authority(self) -> str:
        return "none"

    def route(self, signal: SignalEnvelope, *, observations: Sequence[Observation] | None = None) -> dict[str, RelevanceVerdict]:
        if observations is None:
            observations = WorldModel.observations_from_signal(signal)
        domain = signal.payload.get("domain")
        verdicts: dict[str, RelevanceVerdict] = {}
        for goal_id in self.registry.goals():
            spec = self.registry.get(goal_id)
            state = self.registry.state(goal_id)
            score, matched = score_signal(spec, signal, observations)
            if score <= 0:
                continue
            if self.registry.domain_muted(goal_id, domain):
                verdicts[goal_id] = RelevanceVerdict(goal_id, signal.signal_id, score, matched, False, "domain muted by founder")
                continue
            # A superseded goal is closed like a revoked one: its replacement carries the founder's intent,
            # and GoalRegistry.wake refuses it (waking it would fault the turn for every other goal).
            if state.status in ("completed", "revoked", "paused", "superseded") or state.preferences.get("stop_pushing"):
                verdicts[goal_id] = RelevanceVerdict(goal_id, signal.signal_id, score, matched, False, f"goal is {state.status}")
                continue
            wake = score >= spec.wake_threshold
            verdicts[goal_id] = RelevanceVerdict(goal_id, signal.signal_id, score, matched, wake,
                                                 "wake threshold reached" if wake else "below wake threshold")
        return verdicts
