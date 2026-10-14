"""Personal Advancement (directive section 5): authorized trajectory versus observed trajectory.

This is a projection over records the loop already writes; it adds no authority, no new
store and no pressure. For each goal it compares the *authorized* trajectory (plan node order
and optional ``PlanNode.target_by`` dates) with the *observed* trajectory (the active node and
single-bottleneck-metric gap recorded on every gravity turn), detects a stall or a missed
target, diagnoses the dominant friction from the goal's own blockers, deficits and open founder
asks, and composes the directive's "desired mature behavior" report:

    "X remains one of your highest-priority goals. Progress has stalled. The main friction appears
    to be Y. I completed the parts within my authority, prepared Z, and identified one decision
    that still requires you. The remaining action should take approximately N effort. Here is the
    evidence."

What it never does: remind, shame, nag, escalate urgency, override a refusal, or act on
Alfonso. A paused goal or the ``minimal`` intensity produces no report (ledger only). Every
report offers no-cost options to pause or lower the goal. One report per stall episode,
re-surfacing only after the goal's review cadence. When the goal advances after a report, the
resolution and its latency are recorded so friction diagnoses can be evaluated later.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Mapping, Sequence

from .contracts import canonical_copy, digest, require_text
from .goals import GoalRegistry, iso, parse_time

STALL_TURNS = {"minimal": None, "standard": 3, "active": 2}
# Friction classes, ordered by how much of the route each blocks when present.
FRICTION_ORDER = ("reconciliation", "dependency", "capability", "relationship", "proof",
                  "founder_decision", "resource", "no_declared_move")
FRICTION_TEXT = {
    "reconciliation": "an earlier move's outcome is unknown and must be reconciled before anything else runs",
    "dependency": "a goal this one depends on is not complete",
    "capability": "a capability this gate needs does not exist yet",
    "relationship": "a relationship this gate needs has not been observed",
    "proof": "the evidence for the next move is below its floor",
    "founder_decision": "prepared work is waiting on your decision",
    "resource": "the goal's resource budget is exhausted for now",
    "no_declared_move": "no declared or proposed move attacks the active gate",
}


@dataclass(frozen=True)
class TrajectoryPoint:
    at: str
    node_index: int | None
    node_id: str | None
    gap: float | None
    satisfied: bool | None


class AdvancementMonitor:
    REPORT_RECORD = "egregore.advancement_report"
    RESOLUTION_RECORD = "egregore.advancement_resolved"

    def __init__(self, *, ledger: Any, registry: GoalRegistry, turn_record: str, prepared_record: str,
                 source: str = "spiffe://uniimente.internal/egregore/goal-gravity"):
        self.ledger = ledger
        self.registry = registry
        self.turn_record = turn_record
        self.prepared_record = prepared_record
        self.source = require_text("source", source)

    @property
    def execution_authority(self) -> str:
        return "none"

    # ------------------------------------------------------------ observed trajectory
    def trajectory(self, goal_id: str, *, pending: Mapping[str, Any] | None = None) -> list[TrajectoryPoint]:
        """Observed trajectory from recorded turns (plus the turn being processed, when given)."""
        spec = self.registry.get(goal_id)
        order = {n.node_id: i for i, n in enumerate(spec.plan)}
        points: list[TrajectoryPoint] = []
        summaries = []
        for record in self.ledger.by_type(self.turn_record):
            turn = record.payload["turn"]
            for p in turn["processed"]:
                if p["goal_id"] == goal_id:
                    summaries.append((turn["at"], p))
        if pending is not None:
            summaries.append((pending["at"], pending))
        for at, p in summaries:
            sbm = p.get("sbm") or {}
            node_id = p.get("active_node_id")
            points.append(TrajectoryPoint(at=at, node_index=order.get(node_id) if node_id else len(spec.plan),
                                          node_id=node_id, gap=sbm.get("gap"), satisfied=sbm.get("satisfied")))
        return points

    @staticmethod
    def _progressed(a: TrajectoryPoint, b: TrajectoryPoint) -> bool:
        """Did the goal move forward from a to b? A later node, a closer metric, or a newly satisfied gate."""
        if a.node_index is not None and b.node_index is not None and b.node_index > a.node_index:
            return True
        if b.node_index == a.node_index:
            if isinstance(a.gap, (int, float)) and isinstance(b.gap, (int, float)) and abs(b.gap) < abs(a.gap) - 1e-12:
                return True
            if b.satisfied and not a.satisfied:
                return True
        return False

    def stall_start(self, points: Sequence[TrajectoryPoint]) -> int:
        """Index of the first point of the current no-progress run."""
        start = 0
        for i in range(1, len(points)):
            if self._progressed(points[i - 1], points[i]):
                start = i
        return start

    def behind_target(self, goal_id: str, *, now: datetime | str) -> list[dict[str, Any]]:
        """Authorized trajectory: nodes whose target date has passed while they are not yet cleared."""
        spec = self.registry.get(goal_id)
        state = self.registry.state(goal_id)
        current = parse_time(now)
        active = state.active_node_id
        order = [n.node_id for n in spec.plan]
        active_index = order.index(active) if active in order else 0
        late = []
        for i, node in enumerate(spec.plan):
            if node.target_by and i >= active_index and parse_time(node.target_by) < current:
                late.append({"node_id": node.node_id, "target_by": node.target_by,
                             "days_late": round((current - parse_time(node.target_by)).total_seconds() / 86400, 2)})
        return late

    # ------------------------------------------------------------ friction
    def friction(self, goal_id: str, *, summary: Mapping[str, Any], open_asks: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        """Diagnose friction from the turn's structured fields (never by matching blocker wording)."""
        state = self.registry.state(goal_id)
        found: dict[str, list[str]] = {}

        def add(cls: str, detail: str) -> None:
            found.setdefault(cls, []).append(str(detail))

        decisions = list(summary.get("decisions", []))
        for route in summary.get("open_attempts", []):
            add("reconciliation", f"route {route[7:23]} outcome unknown")
        for d in decisions:
            if d.get("evidence_state") == "unknown":
                add("reconciliation", d["intervention_id"])
        for dep in summary.get("unmet_dependencies", []):
            add("dependency", dep)
        for cap in list(summary.get("missing_capabilities", [])) or list(state.missing_capabilities):
            add("capability", cap)
        routing = summary.get("routing") or {}
        if routing.get("deficit"):
            add("capability", "no registered mechanism offers " + ", ".join(routing["deficit"]["missing_methods"]))
        for rel in summary.get("missing_relationships", []):
            add("relationship", rel)
        for d in decisions:
            if d.get("decision") == "REQUEST_EVIDENCE":
                add("proof", d["intervention_id"])
        for d in summary.get("deficits", []):
            if d.get("class") == "resource":
                add("resource", d["detail"])
        for a in open_asks:
            if a["goal_id"] == goal_id and a.get("kind") == "decision":
                add("founder_decision", a["title"])
        if not decisions and not found:
            add("no_declared_move", f"gate '{summary.get('active_gate')}' has no candidate move")
        return [{"class": c, "explanation": FRICTION_TEXT[c], "details": sorted(set(found[c]))}
                for c in FRICTION_ORDER if c in found]

    # ------------------------------------------------------------ report
    def assess(self, goal_id: str, *, summary: Mapping[str, Any], now: datetime | str,
               open_asks: Sequence[Mapping[str, Any]], latest_by_route: Mapping[str, Mapping[str, Any]],
               evidence_refs: Sequence[str]) -> dict[str, Any] | None:
        """Return a report payload when the goal is stalled or behind its authorized trajectory, else None.

        Also records the resolution of an earlier report when the goal has advanced since it.
        """
        at = iso(parse_time(now))
        spec = self.registry.get(goal_id)
        state = self.registry.state(goal_id)
        intensity = state.preferences.get("intervention_intensity", "standard")
        points = self.trajectory(goal_id, pending={**summary, "at": at})
        start = self.stall_start(points)
        self._record_resolution(goal_id, points, start, at)
        if state.status in ("paused", "revoked", "superseded", "completed") or state.preferences.get("stop_pushing"):
            return None
        if intensity == "minimal":
            return None   # the founder chose no advancement reports for this goal: neither stall nor lateness surfaces
        threshold = STALL_TURNS.get(intensity)
        run = len(points) - start
        late = self.behind_target(goal_id, now=at)
        stalled = threshold is not None and run >= threshold
        if not stalled and not late:
            return None
        episode = digest({"kind": "egregore-stall-episode", "goal_id": goal_id,
                          "since": points[start].at if points else at, "node": points[-1].node_id if points else None,
                          "late": [n["node_id"] for n in late]})
        previous = [r.payload for r in self.ledger.by_type(self.REPORT_RECORD)
                    if r.payload["goal_id"] == goal_id and r.payload["episode_id"] == episode]
        if previous and parse_time(at) < parse_time(previous[-1]["reported_at"]) + timedelta(seconds=spec.review_cadence_seconds):
            return None
        friction = self.friction(goal_id, summary=summary, open_asks=open_asks)
        completed = [i["intervention"]["description"] for i in latest_by_route.values()
                     if i["evidence_state"] in ("executed", "externally_verified")]
        prepared = sorted({r.payload["intervention"]["description"] for r in self.ledger.by_type(self.prepared_record)
                           if r.payload["goal_id"] == goal_id})
        decisions = [a for a in open_asks if a["goal_id"] == goal_id and a.get("kind") == "decision"]
        refs = list(dict.fromkeys(list(evidence_refs) + [r for a in decisions for r in a.get("evidence_refs", [])]))[:8]
        effort = (f"{len(decisions)} decision(s) and about {len(refs)} evidence item(s) to read" if decisions
                  else "no action is required from you; GREG continues within its authority")
        main = friction[0] if friction else {"class": "unknown", "explanation": "no recorded friction explains the stall", "details": []}
        priority_word = "one of your highest-priority goals" if self.registry.effective_priority(goal_id) <= 2 else "an authorized goal"
        progress = (f"progress has stalled for {run} review(s) at gate '{summary.get('active_gate')}'" if stalled
                    else "progress is behind the authorized trajectory")
        if late:
            progress += "; " + ", ".join(f"{n['node_id']} was due {n['target_by']} ({n['days_late']} days ago)" for n in late)
        text = (f"'{spec.desired_state}' remains {priority_word}. {progress[0].upper() + progress[1:]}. "
                f"The main friction appears to be: {main['explanation']}"
                + (f" ({'; '.join(main['details'][:3])})" if main["details"] else "") + ". "
                f"Within my authority I completed {len(completed)} move(s)"
                + (f" ({'; '.join(completed[:3])})" if completed else "")
                + f" and prepared {len(prepared)}" + (f" ({'; '.join(prepared[:3])})" if prepared else "") + ". "
                f"{len(decisions)} decision(s) still require you. The remaining action should take approximately: {effort}. "
                f"Here is the evidence: {len(refs)} reference(s) attached.")
        report = {"source": self.source, "goal_id": goal_id, "episode_id": episode, "reported_at": at,
                  "stalled": stalled, "stall_turns": run, "intensity": intensity, "behind_target": late,
                  "friction": friction, "main_friction": main["class"], "completed": completed, "prepared": prepared,
                  "open_decisions": [a["item_id"] for a in decisions], "effort": effort, "evidence_refs": refs,
                  "text": text, "disposition": "reported_to_attention_router; no pressure, no action on the founder"}
        self.ledger.append(self.REPORT_RECORD, canonical_copy(report))
        return report

    def _record_resolution(self, goal_id: str, points: Sequence[TrajectoryPoint], start: int, at: str) -> None:
        """An earlier report whose stall has ended: record how long the goal took to move after it."""
        reports = [r.payload for r in self.ledger.by_type(self.REPORT_RECORD) if r.payload["goal_id"] == goal_id]
        if not reports or start == 0 or not points:
            return
        resolved = {r.payload["episode_id"] for r in self.ledger.by_type(self.RESOLUTION_RECORD) if r.payload["goal_id"] == goal_id}
        advanced_at = points[start].at
        for report in reports:
            if report["episode_id"] in resolved or parse_time(report["reported_at"]) > parse_time(advanced_at):
                continue
            self.ledger.append(self.RESOLUTION_RECORD, {
                "source": self.source, "goal_id": goal_id, "episode_id": report["episode_id"],
                "main_friction": report["main_friction"], "reported_at": report["reported_at"], "advanced_at": advanced_at,
                "latency_seconds": (parse_time(advanced_at) - parse_time(report["reported_at"])).total_seconds(),
                "recorded_at": at, "disposition": "friction diagnosis outcome recorded for later evaluation"})
            resolved.add(report["episode_id"])
