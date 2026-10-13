"""Favorable Intersection Detector (target G).

Several individually weak signals, observed across different domains inside
a goal's window, combine into one strong opportunity when their combined
weight crosses the goal's threshold. Detection is a recorded observation
about feasibility, cost, timing, risk or upside. It wakes a goal; it does
not act. This is persistent goal-directed preparation, not chance control.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from .contracts import canonical_copy, digest, require_text
from .experience import WorldModel
from .goals import GoalSpec, OpportunityFactor, iso, parse_time


@dataclass(frozen=True)
class IntersectionReport:
    goal_id: str
    detected_at: str
    score: float
    threshold: float
    satisfied: tuple[dict[str, Any], ...]
    unsatisfied: tuple[str, ...]
    domains: tuple[str, ...]
    cross_domain: bool
    favorable: bool
    effects: dict[str, float]
    factor_set_hash: str

    @property
    def execution_authority(self) -> str:
        return "none"

    def to_dict(self) -> dict[str, Any]:
        return {"goal_id": self.goal_id, "detected_at": self.detected_at, "score": self.score,
                "threshold": self.threshold, "satisfied": [canonical_copy(s) for s in self.satisfied],
                "unsatisfied": list(self.unsatisfied), "domains": list(self.domains),
                "cross_domain": self.cross_domain, "favorable": self.favorable,
                "effects": canonical_copy(self.effects), "factor_set_hash": self.factor_set_hash,
                "execution_authority": "none"}


def _condition_holds(factor: OpportunityFactor, value: Any) -> bool:
    if factor.direction == "present":
        return value is not None
    if isinstance(value, bool) or isinstance(factor.threshold, bool):
        return factor.direction == "eq" and value == factor.threshold
    if not isinstance(value, (int, float)):
        return False
    v, t = float(value), float(factor.threshold)
    return {"gte": v >= t, "lte": v <= t, "eq": v == t}[factor.direction]


class FavorableIntersectionDetector:
    INTERSECTION_RECORD = "egregore.intersection_detected"

    def __init__(self, *, ledger: Any, world: WorldModel,
                 source: str = "spiffe://uniimente.internal/egregore/goal-gravity"):
        self.ledger = ledger
        self.world = world
        self.source = require_text("source", source)
        self._recorded: set[tuple[str, str]] = set()
        for record in getattr(ledger, "records", ()):
            if getattr(record, "record_type", None) == self.INTERSECTION_RECORD:
                p = record.payload.get("report", {})
                self._recorded.add((p.get("goal_id"), p.get("factor_set_hash")))

    @property
    def execution_authority(self) -> str:
        return "none"

    def detect(self, spec: GoalSpec, *, now: datetime | str, record: bool = True) -> IntersectionReport:
        current = parse_time(now)
        window = timedelta(seconds=spec.intersection_window_seconds)
        satisfied: list[dict[str, Any]] = []
        unsatisfied: list[str] = []
        effects: dict[str, float] = {}
        score = 0.0
        for factor in spec.opportunity_factors:
            belief = self.world.belief(factor.subject, factor.attribute)
            if belief is None or belief.contradicted:
                unsatisfied.append(factor.factor_id)
                continue
            observed = parse_time(belief.observed_at)
            if observed > current or current - observed > window:
                unsatisfied.append(factor.factor_id)
                continue
            if not _condition_holds(factor, belief.value):
                unsatisfied.append(factor.factor_id)
                continue
            score += factor.weight * belief.confidence
            effects[factor.effect] = effects.get(factor.effect, 0.0) + factor.weight * belief.confidence
            satisfied.append({"factor_id": factor.factor_id, "domain": factor.domain, "key": belief.key,
                              "value": belief.value, "confidence": belief.confidence,
                              "observed_at": belief.observed_at, "source": belief.source,
                              "signal_id": belief.signal_id, "weight": factor.weight, "effect": factor.effect})
        domains = tuple(sorted({s["domain"] for s in satisfied}))
        cross_domain = len(domains) >= 2
        favorable = score >= spec.intersection_threshold and cross_domain and bool(satisfied)
        report = IntersectionReport(
            goal_id=spec.goal_id, detected_at=iso(current), score=score, threshold=spec.intersection_threshold,
            satisfied=tuple(satisfied), unsatisfied=tuple(unsatisfied), domains=domains, cross_domain=cross_domain,
            favorable=favorable, effects=effects,
            factor_set_hash=digest({"kind": "egregore-intersection", "goal_id": spec.goal_id,
                                    "factors": sorted(s["factor_id"] for s in satisfied)}))
        key = (spec.goal_id, report.factor_set_hash)
        if record and favorable and key not in self._recorded:
            self.ledger.append(self.INTERSECTION_RECORD, {"source": self.source, "report": report.to_dict(),
                                                          "disposition": "observed_not_acted"})
            self._recorded.add(key)
        return report
