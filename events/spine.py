"""Layer 4: durable institutional nervous system.

Doctrine (EVENTS):
    Every state change is an event. Events are facts: append-only,
    schema-validated, sensitivity-classified, and replayable. The event
    spine is the kernel's nervous system — organs react to facts, never
    to each other's private state.

    Durability contract: a workflow killed at any point resumes from its
    last checkpoint without manual restatement. Compensation runs in
    reverse order. The inbox is idempotent; the outbox is staged and
    flushed only through mediation (in production, the consequence gate).

    No event names UNIIMENTE as a legal principal. The institution is
    infrastructure, never a contracting party.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

EVENT_TYPE_RE = re.compile(r"^[a-z]+(\.[a-z_]+)+$")
SENSITIVITY = ("public", "internal", "confidential", "restricted")
SPIFFE_PREFIX = "spiffe://uniimente.internal/"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class EventError(ValueError):
    """Invalid event or spine operation. Fails closed."""


@dataclass
class Event:
    """One fact. CloudEvents-compatible envelope."""
    type: str                                # e.g. "workflow.step_completed"
    source: str                              # spiffe id (internal) or explicit external origin
    actor: str                               # who caused it (passport id / human id)
    payload: dict
    legal_principal: str                     # never "UNIIMENTE"
    sensitivity: str = "internal"
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: str = field(default_factory=_now)
    causal_parent: str | None = None         # event_id of the fact that caused this one
    policy_version: str | None = None        # constitution/policy version in force

    def validate(self) -> "Event":
        if not EVENT_TYPE_RE.match(self.type):
            raise EventError(f"event type must be namespaced lowercase: {self.type!r}")
        if self.sensitivity not in SENSITIVITY:
            raise EventError(f"unknown sensitivity: {self.sensitivity!r}")
        if self.legal_principal == "UNIIMENTE":
            raise EventError("UNIIMENTE is never a legal principal")
        if not self.source or not self.actor:
            raise EventError("event requires source and actor")
        return self


class EventSpine:
    """Canonical transition truth; one ledger writer, views reconstructed on read.

    Derived from #87's replay/outbox recovery, without importing its runtime.
    Dispatch is at least once. A started but unacknowledged external delivery
    is reconciliation-required, not permission for blind retry.
    """

    def __init__(self, ledger):
        self.ledger = ledger
        self._subscribers = {}
        self._seen_ids = set()
        self._outbox = []
        self._refresh()

    @staticmethod
    def _event_from_payload(p):
        return Event(**{k: p[k] for k in Event.__dataclass_fields__})

    def _spine_payloads(self):
        ok, reason = self.ledger.verify_chain()
        if not ok:
            raise EventError(reason)
        return [r.payload for r in self.ledger.by_type("event")
                if "event_id" in r.payload]

    def _refresh(self):
        from provenance.ledger import sha256_json
        self._bindings, pending, self._uncertain_deliveries = {}, {}, set()
        for p in self._spine_payloads():
            ev = self._event_from_payload(p).validate()
            digest = sha256_json(asdict(ev))
            if ev.event_id in self._bindings and self._bindings[ev.event_id] != digest:
                raise EventError("conflicting durable event identity")
            self._bindings[ev.event_id] = digest
            direction = p.get("direction")
            if direction == "outbox_staged":
                pending[ev.event_id] = ev
            elif direction == "outbox_dispatch_started":
                self._uncertain_deliveries.add(ev.event_id)
            elif direction in ("outbox_flushed", "outbox_refused"):
                self._uncertain_deliveries.discard(ev.event_id)
                if direction == "outbox_flushed":
                    pending.pop(ev.event_id, None)
        self._seen_ids = set(self._bindings)
        self._outbox = list(pending.values())

    def _accept(self, event, direction):
        from provenance.ledger import sha256_json
        event.validate()
        with self.ledger._lock:
            self._refresh()
            if event.event_id in self._bindings:
                if self._bindings[event.event_id] != sha256_json(asdict(event)):
                    raise EventError("event id reused with different content")
                return None
            self.ledger.append("event", {**asdict(event), "direction": direction})
            self._refresh()
        # Dispatch failure cannot undo durable acceptance; replay explicitly.
        if direction != "outbox_staged":
            self._dispatch(event)
        return event

    def emit(self, event):
        if not event.source.startswith(SPIFFE_PREFIX):
            raise EventError("internal emission needs SPIFFE source; use ingest")
        return self._accept(event, "emitted")

    def ingest(self, event):
        return self._accept(event, "ingested")

    def subscribe(self, type_prefix, handler):
        self._subscribers.setdefault(type_prefix, []).append(handler)

    def _dispatch(self, event):
        for prefix, handlers in self._subscribers.items():
            if event.type.startswith(prefix):
                for handler in handlers:
                    handler(event)

    def replay(self, type_prefix=None):
        return [self._event_from_payload(p) for p in self._spine_payloads()
                if type_prefix is None or p["type"].startswith(type_prefix)]

    def outbox_stage(self, event):
        return self._accept(event, "outbox_staged")

    def outbox_flush(self, mediator=None):
        from provenance.ledger import ReconciliationRequired
        if mediator is None:
            raise EventError("explicit consequence mediator required")
        flushed = []
        with self.ledger._lock:
            self._refresh()
            for ev in list(self._outbox):
                if ev.event_id in self._uncertain_deliveries:
                    raise ReconciliationRequired("unacknowledged dispatch; inspect effect before retry")
                self.ledger.append("event", {**asdict(ev), "direction": "outbox_dispatch_started"})
                # Any exception leaves the durable pending claim intact.
                try:
                    allowed = bool(mediator(ev))
                except Exception as exc:
                    raise ReconciliationRequired("dispatch outcome unknown") from exc
                self.ledger.append("event", {**asdict(ev), "direction":
                                            "outbox_flushed" if allowed else "outbox_refused"})
                if allowed:
                    flushed.append(ev)
            self._refresh()
        return flushed


# ---------------------------------------------------------------------------
# Durable workflows

@dataclass
class WorkflowStep:
    name: str
    run: callable                        # (state) -> state delta dict
    compensate: callable | None = None   # (state) -> None, best-effort
    max_retries: int = 2
    approval_wait: bool = False          # requires approver() -> bool before run
    retry_safe: bool = False             # explicit declaration: harmless/idempotent computation only


class WorkflowKilled(RuntimeError):
    """Raised to simulate/force an interruption; the workflow is resumable."""


class WorkflowFailed(RuntimeError):
    """Retries exhausted and compensation complete (or impossible)."""


class DurableWorkflow:
    """A sequence of steps checkpointed on the ledger.

    Status machine: running -> completed | interrupted | failed | compensated.
    Checkpoints are ledger records of type "workflow"; resume() rebuilds
    cursor+state from them, so a killed workflow continues without any
    manual restatement of what already happened.
    """

    def __init__(self, spine: EventSpine, workflow_id: str, steps: list[WorkflowStep],
                 *, actor: str, legal_principal: str):
        if legal_principal == "UNIIMENTE":
            raise EventError("workflow legal principal is never UNIIMENTE")
        self.spine = spine
        self.workflow_id = workflow_id
        self.steps = steps
        if len({s.name for s in steps}) != len(steps):
            raise EventError("duplicate workflow step identity")
        self.actor = actor
        self.legal_principal = legal_principal
        self.cursor = 0                  # next step to execute
        self.state: dict = {}            # accumulated step outputs
        self.status = "running"
        self._owns_checkpoint = False

    def _step_contract(self):
        return [{"name": s.name, "max_retries": s.max_retries,
                 "approval_wait": s.approval_wait, "retry_safe": s.retry_safe}
                for s in self.steps]

    # ------------------------------------------------------------ durability
    def _checkpoint(self, note: str) -> None:
        from adapters.contract_validation import validate_contract
        payload = {"schema_version": "2",
            "workflow_id": self.workflow_id, "cursor": self.cursor,
            "status": self.status, "state": dict(self.state), "note": note,
            "actor": self.actor, "legal_principal": self.legal_principal,
            "step_contract": self._step_contract(), "at": _now()}
        validate_contract(payload, 'workflow-execution')
        self.spine.ledger.append("workflow", payload)
        self._owns_checkpoint = True

    @staticmethod
    def resume(spine: EventSpine, workflow_id: str, steps: list[WorkflowStep]) -> "DurableWorkflow":
        """Reconstruct from the ledger. Steps must be the same definitions."""
        cps = [r for r in spine.ledger.by_type("workflow")
               if r.payload.get("workflow_id") == workflow_id]
        if not cps:
            raise EventError(f"no checkpoints for workflow {workflow_id!r}")
        last = cps[-1].payload
        from adapters.contract_validation import validate_contract
        validate_contract(last, 'workflow-execution')
        if last['cursor'] > len(steps):
            raise EventError("checkpoint cursor exceeds task contract")
        if last["status"] in ("completed", "compensated", "failed"):
            raise EventError(f"workflow is {last['status']}; nothing to resume")
        wf = DurableWorkflow(spine, workflow_id, steps,
                             actor=last["actor"], legal_principal=last["legal_principal"])
        if last.get("step_contract") != wf._step_contract():
            raise EventError("unsupported or changed workflow step contract; reconcile migration")
        from provenance.ledger import ReconciliationRequired
        uncertain = last["note"].startswith(("step_started:", "killed_during:", "uncertain:"))
        if (last["status"] == "reconciliation_required" or uncertain) and (
                last["cursor"] >= len(steps) or not steps[last["cursor"]].retry_safe):
            raise ReconciliationRequired("unfinished step may have completed; no blind retry")
        wf.cursor = last["cursor"]
        wf.state = dict(last["state"])
        wf.status = "running"
        wf._checkpoint("resumed")
        return wf

    # ------------------------------------------------------------ execution
    def execute(self, *, kill_at_step: str | None = None, approver=None) -> "DurableWorkflow":
        from provenance.ledger import ReconciliationRequired
        if self.status != "running":
            raise EventError("reconstruct interrupted state before execution")
        with self.spine.ledger._lock:
            if not self._owns_checkpoint and any(
                    r.payload.get("workflow_id") == self.workflow_id
                    for r in self.spine.ledger.by_type("workflow")):
                raise EventError("workflow identity already retained; use resume")
            self._checkpoint("execute_enter")
        while self.cursor < len(self.steps):
            step = self.steps[self.cursor]
            if step.name == kill_at_step:
                self.status = "interrupted"
                self._checkpoint(f"killed_before:{step.name}")
                raise WorkflowKilled(f"interrupted before step {step.name!r}")
            if step.approval_wait:
                ok = bool(approver(step)) if approver else False
                self.spine.emit(Event(
                    type="workflow.approval_wait", source=SPIFFE_PREFIX + "workflow/" + self.workflow_id,
                    actor=self.actor, legal_principal=self.legal_principal,
                    payload={"workflow_id": self.workflow_id, "step": step.name, "approved": ok}))
                if not ok:
                    self.status = "interrupted"
                    self._checkpoint(f"approval_pending:{step.name}")
                    raise WorkflowKilled(f"approval pending at step {step.name!r}")
            attempts = 0
            while True:
                # Durable intent precedes invocation. An uncertain completion is
                # not permission to repeat a potentially consequential step.
                self._checkpoint(f"step_started:{step.name}")
                try:
                    delta = step.run(self.state) or {}
                except WorkflowKilled:
                    self.status = "interrupted"
                    self._checkpoint(f"killed_during:{step.name}")
                    raise
                except Exception as exc:                       # step failure
                    if not step.retry_safe:
                        self.status = "reconciliation_required"
                        self._checkpoint(f"uncertain:{step.name}")
                        raise ReconciliationRequired("step outcome unknown; reconcile retained state") from exc
                    attempts += 1
                    self.spine.emit(Event(
                        type="workflow.step_failed", source=SPIFFE_PREFIX + "workflow/" + self.workflow_id,
                        actor=self.actor, legal_principal=self.legal_principal,
                        sensitivity="confidential",
                        payload={"workflow_id": self.workflow_id, "step": step.name,
                                 "attempt": attempts, "error": str(exc)[:200]}))
                    if attempts > step.max_retries:
                        self._compensate(failed_step=step.name)
                        self.status = "compensated" if self.cursor > 0 else "failed"
                        self._checkpoint(f"retries_exhausted:{step.name}")
                        raise WorkflowFailed(
                            f"step {step.name!r} failed after {attempts} attempts; "
                            f"workflow {self.status}") from exc
                    continue
                self.state.update(delta)
                self.cursor += 1
                # Outside the retry handler: even a definite failed append after
                # computation must not invoke that computation again blindly.
                try:
                    self._checkpoint(f"step_completed:{step.name}")
                except Exception as exc:
                    self.status = "reconciliation_required"
                    raise ReconciliationRequired("completion checkpoint not acknowledged") from exc
                break
        self.status = "completed"
        self._checkpoint("completed")
        return self

    def _compensate(self, *, failed_step: str) -> None:
        """Undo completed steps in reverse order. Best-effort; every attempt ledgered."""
        for step in reversed(self.steps[: self.cursor]):
            if step.compensate is None:
                continue
            try:
                step.compensate(self.state)
                note, ok = "compensated", True
            except Exception as exc:                           # compensation itself failed
                note, ok = f"compensation_failed:{str(exc)[:120]}", False
            self.spine.emit(Event(
                type="workflow.compensation", source=SPIFFE_PREFIX + "workflow/" + self.workflow_id,
                actor=self.actor, legal_principal=self.legal_principal,
                sensitivity="confidential",
                payload={"workflow_id": self.workflow_id, "step": step.name,
                         "failed_step": failed_step, "ok": ok, "note": note}))


# ---------------------------------------------------------------------------
# Governed engine seam (Package 4, founder decision 1)
#
# The canonical construction sites call these factories instead of the class
# directly, so a governed replacement can take over at the real boundary. The
# DurableWorkflow class above remains the default: with no
# replacement active, `resolve` returns it and the untouched spine, so these
# factories are exactly equivalent to constructing it directly.
#
# Direct construction of DurableWorkflow remains valid and is still used by
# existing tests — the seam adds a governed path, it does not remove the plain
# one.

def durable_workflow(spine, workflow_id: str, steps: list[WorkflowStep], *,
                     actor: str, legal_principal: str):
    """Construct the workflow through the governed engine seam."""
    from events.engine import resolve

    engine, resolved_spine = resolve(spine, workflow_id)
    return engine(resolved_spine, workflow_id, steps,
                  actor=actor, legal_principal=legal_principal)


def resume_workflow(spine, workflow_id: str, steps: list[WorkflowStep]):
    """Resume through the governed engine seam.

    Resolution happens per workflow id, so a resume can legitimately land on a
    different engine than the one that wrote the checkpoint. That IS the
    stateful-replacement case, and it is exactly why the checkpoint must carry
    enough state to be read by an engine that did not write it.
    """
    from events.engine import resolve

    engine, resolved_spine = resolve(spine, workflow_id)
    return engine.resume(resolved_spine, workflow_id, steps)
