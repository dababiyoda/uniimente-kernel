"""Wake schedule: when a host trigger should next call ``GoalGravityLoop.turn``.

Directive section 3 asks for dormant states, wake conditions, event triggers, priority queues, review
cadences and urgency classes so that "a long-horizon objective may sleep for months; a relevant event
may wake it instantly". The founder-loop entry gate (``docs/founder-loop-entry-gate.json``, G5 and P1)
requires that a *bounded host-owned trigger* discover a due obligation without a human tick, and it
forbids building a new scheduler before the founder selects one.

This module is therefore not a scheduler. It is the read-only view any scheduler needs: for every goal
that may wake by cadence, and for every founder ``defer`` that re-surfaces, the due time computed from
durable state, plus the earliest of them and a stable ``trigger_id`` for it. Calling it appends nothing
and runs nothing. A host (cron, APScheduler as DALEOBANKS already runs, Temporal, a test) decides.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .attention import FounderAttentionRouter
from .goals import iso, parse_time

SLEEPING = ("dormant", "blocked")


class WakeSchedule:
    """Due times folded from goal state and founder deferrals. Zero execution authority; appends nothing."""

    def __init__(self, loop: Any):
        self.loop = loop

    @property
    def execution_authority(self) -> str:
        return "none"

    @staticmethod
    def trigger_id_for(at: datetime | str, *, clock: str = "cadence") -> str:
        """A globally stable trigger id for a host that fires at ``at``: retrying it replays the recorded turn."""
        return f"{clock}:{iso(parse_time(at))}"

    def entries(self, now: datetime | str) -> list[dict[str, Any]]:
        self.loop._sync()
        current = parse_time(now)
        registry = self.loop.registry
        out: list[dict[str, Any]] = []
        for goal_id in registry.goals():
            spec = registry.get(goal_id)
            state = registry.state(goal_id)
            if state.status not in SLEEPING or state.preferences.get("stop_pushing"):
                continue
            anchor = state.last_reviewed_at or state.last_woken_at
            due = parse_time(anchor) + timedelta(seconds=spec.review_cadence_seconds) if anchor else current
            out.append({"kind": "review_cadence", "goal_id": goal_id, "due_at": iso(due), "overdue": due <= current,
                        "priority": registry.effective_priority(goal_id), "goal_status": state.status,
                        "anchor": anchor, "cadence_seconds": spec.review_cadence_seconds,
                        "wake_reason_expected": "review cadence elapsed"})
        latest: dict[str, tuple[str, dict[str, Any]]] = {}
        for record in self.loop.ledger.records:
            if record.record_type == FounderAttentionRouter.ASK_RECORD:
                latest[record.payload["item"]["item_id"]] = ("ask", record.payload)
            elif record.record_type == FounderAttentionRouter.ANSWER_RECORD:
                latest[record.payload["item_id"]] = ("answer", record.payload)
        for item_id, (kind, payload) in latest.items():
            if kind != "answer" or payload.get("decision") != "defer" or not payload.get("resurface_after"):
                continue
            goal_id = payload["goal_id"]
            status = registry.state(goal_id).status if goal_id in registry.goals() else "unknown"
            due = parse_time(payload["resurface_after"])
            out.append({"kind": "deferred_ask", "goal_id": goal_id, "item_id": item_id, "due_at": iso(due),
                        "overdue": due <= current, "priority": registry.effective_priority(goal_id) if status != "unknown" else 5,
                        "goal_status": status, "anchor": payload.get("answered_at"),
                        "wake_reason_expected": "deferred ask re-surfaces when the goal next wakes"})
        out.sort(key=lambda e: (e["due_at"], e["kind"], e["goal_id"], e.get("item_id", "")))
        return out

    def next_trigger(self, now: datetime | str) -> dict[str, Any]:
        """The earliest due entry and a trigger id for it. Overdue work means 'now'. Nothing here fires."""
        current = parse_time(now)
        entries = self.entries(current)
        overdue = [e for e in entries if e["overdue"]]
        upcoming = [e for e in entries if not e["overdue"]]
        if overdue:
            next_due = iso(current)
        elif upcoming:
            next_due = upcoming[0]["due_at"]
        else:
            next_due = None
        return {
            "as_of": iso(current),
            "entries": entries,
            "overdue": [{k: e[k] for k in ("kind", "goal_id", "item_id", "due_at") if k in e} for e in overdue],
            "next_due_at": next_due,
            "suggested_trigger_id": self.trigger_id_for(next_due) if next_due else None,
            "note": "a host-owned scheduler calls turn(trigger_id=suggested_trigger_id, now=next_due_at); nothing here runs "
                    "on its own (founder-loop entry gate G5/P1)",
            "execution_authority": "none",
        }
