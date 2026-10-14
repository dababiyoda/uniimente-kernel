"""Opportunity package (directive sections 12 and 28): quantify a favorable intersection and prepare options.

When weak signals converge for a goal, GREG does not act on the convergence. It writes one
deterministic package per distinct factor set:

* every satisfied factor with its observed value, its ledgered evidence (experience-record hash),
  and, when the factor declares a ``baseline``, the computed delta and relative change (typed
  ``deterministic_computation``: arithmetic over recorded beliefs, not a forecast);
* threats that subtract, and contested factors (sources disagree) kept separate and never scored;
* the GPS fix (active node, gate, bottleneck metric) and a dry-run classification of every move,
  so the package states which moves GREG could do itself, which it would prepare, and which need
  Alfonso;
* nothing executes; the package is information routed through the attention router.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Sequence

from .contracts import canonical_copy, digest, require_text
from .goals import GoalSpec, GoalState, InterventionSpec, iso, parse_time
from .gps import GPSFix
from .intersections import IntersectionReport


class OpportunityPackager:
    PACKAGE_RECORD = "egregore.opportunity_package"

    def __init__(self, *, ledger: Any, world: Any, classifier: Any,
                 source: str = "spiffe://uniimente.internal/egregore/goal-gravity"):
        self.ledger = ledger
        self.world = world
        self.classifier = classifier
        self.source = require_text("source", source)

    @property
    def execution_authority(self) -> str:
        return "none"

    @staticmethod
    def quantify(factor: Any, value: Any) -> dict[str, Any] | None:
        if factor.baseline is None or isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        delta = float(value) - float(factor.baseline)
        relative = None
        if factor.baseline != 0:
            if factor.direction == "lte":     # lower is better (e.g. a cost): improvement is the drop
                relative = (float(factor.baseline) - float(value)) / abs(float(factor.baseline))
            elif factor.direction == "gte":   # higher is better
                relative = delta / abs(float(factor.baseline))
        return {"baseline": factor.baseline, "observed": value, "delta": round(delta, 6),
                "relative_improvement": round(relative, 6) if relative is not None else None,
                "method": "deterministic_computation"}

    def existing(self, goal_id: str, factor_set_hash: str) -> dict[str, Any] | None:
        for r in self.ledger.by_type(self.PACKAGE_RECORD):
            if r.payload["goal_id"] == goal_id and r.payload["factor_set_hash"] == factor_set_hash:
                return r.payload
        return None

    def package(self, spec: GoalSpec, state: GoalState, report: IntersectionReport, fix: GPSFix, *,
                moves: Sequence[InterventionSpec], evidence_refs: Sequence[str], confidence: float,
                now: datetime | str) -> dict[str, Any]:
        at = iso(parse_time(now))
        prior = self.existing(spec.goal_id, report.factor_set_hash)
        if prior is not None:
            return prior
        factors = {f.factor_id: f for f in spec.opportunity_factors}

        def entry(s: Mapping[str, Any]) -> dict[str, Any]:
            factor = factors[s["factor_id"]]
            return {"factor_id": s["factor_id"], "domain": s["domain"], "effect": s["effect"], "key": s["key"],
                    "observed": s["value"], "confidence": s["confidence"], "source": s["source"],
                    "evidence_ref": self.world.record_hash(s["signal_id"]),
                    "quantified": self.quantify(factor, s["value"])}

        contested = []
        for f in spec.opportunity_factors:
            belief = self.world.belief(f.subject, f.attribute)
            if belief is not None and belief.contradicted:
                contested.append({"factor_id": f.factor_id, "key": belief.key, "retained_value": belief.value,
                                  "alternatives": [a["value"] for a in belief.alternatives],
                                  "disposition": "contested: excluded from the score, both readings retained"})
        options = []
        for move in moves:
            c = self.classifier.classify(spec, state, move, fix=fix, grant=None, evidence_refs=list(evidence_refs),
                                         evidence_confidence=confidence, now=at, record=False)
            options.append({"intervention_id": move.intervention_id, "description": move.description,
                            "consequence_class": move.consequence_class,
                            "without_a_grant": c.decision, "reasons": list(c.reasons)})
        package = {
            "source": self.source, "package_id": digest({"kind": "egregore-opportunity-package", "goal_id": spec.goal_id,
                                                         "factor_set_hash": report.factor_set_hash}),
            "goal_id": spec.goal_id, "factor_set_hash": report.factor_set_hash, "packaged_at": at,
            "score": report.score, "threshold": report.threshold, "domains": list(report.domains),
            "expected_effects": canonical_copy(report.effects),
            "satisfied": [entry(s) for s in report.satisfied], "threats": [entry(s) for s in report.threats],
            "contested": contested,
            "position": {"active_node_id": fix.active_node_id, "active_gate": fix.active_gate, "sbm": fix.sbm,
                         "missing_capabilities": list(fix.missing_capabilities)},
            "options": options,
            "evidence_refs": [r for r in list(evidence_refs) + [e["evidence_ref"] for e in map(entry, report.satisfied)] if r],
            "disposition": "prepared_not_executed; information for the founder",
        }
        self.ledger.append(self.PACKAGE_RECORD, canonical_copy(package))
        return package
