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

import heapq
import re
import uuid
from dataclasses import dataclass, field, asdict
from types import MappingProxyType
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
        self._reset_views()
        self._refresh()

    def _reset_views(self):
        self._bindings, self._pending, self._uncertain_deliveries = {}, {}, set()
        self._seen_ids = set()
        self._outbox = []
        self._payloads = []      # every spine event payload, in ledger order (the ledger's own; never handed out)
        self._by_type = {}       # exact event type -> positions in _payloads
        self._latest = {}        # event_id -> (payload, record hash) of its last record
        self._positions = {}     # type prefix -> (payloads seen, matches counted, event_id -> position)
        self._folded, self._folded_tail = 0, None
        self._generation = object()  # a cursor from since() is honored only within one history

    @staticmethod
    def _event_from_payload(p):
        return Event(**{k: p[k] for k in Event.__dataclass_fields__})

    @staticmethod
    def _event_copy(p):
        """An Event the caller owns: its payload is a copy, so changing it changes no retained fact."""
        from provenance.ledger import copy_json
        return Event(**{k: copy_json(p[k]) if k == "payload" else p[k] for k in Event.__dataclass_fields__})

    def _spine_payloads(self):
        from provenance.ledger import copy_json
        self._refresh()
        return [copy_json(p) for p in self._payloads]

    def _refresh(self):
        """Verify new history, then fold only the records not folded yet into the views.

        The views are a left fold over the ledger, so folding the new records gives what a
        rebuild from the beginning gives. Each record is checked before any view changes, so a
        refused record is refused again on every later call (fail closed). Replaced history
        (a different record where the last folded one was) is rebuilt from the beginning.
        """
        from provenance.ledger import sha256_json
        with self.ledger._lock:  # one fold at a time, even if a spine is shared across threads
            self._fold(sha256_json)

    def _fold(self, sha256_json):
        ok, reason = self.ledger.verify_incremental()
        if not ok:
            raise EventError(reason)
        records = self.ledger._records  # the retained records themselves; only read here
        if self._folded and (self._folded > len(records)
                             or records[self._folded - 1] is not self._folded_tail):
            self._reset_views()
        for i in range(self._folded, len(records)):
            rec = records[i]
            p = rec.payload
            if rec.record_type == "event" and "event_id" in p:
                ev = self._event_from_payload(p).validate()
                digest = sha256_json(asdict(ev))
                if ev.event_id in self._bindings and self._bindings[ev.event_id] != digest:
                    raise EventError("conflicting durable event identity")
                self._bindings[ev.event_id] = digest
                self._seen_ids.add(ev.event_id)
                direction = p.get("direction")
                if direction == "outbox_staged":
                    self._pending[ev.event_id] = self._event_copy(p)  # a mediator may touch it
                elif direction == "outbox_dispatch_started":
                    self._uncertain_deliveries.add(ev.event_id)
                elif direction in ("outbox_flushed", "outbox_refused"):
                    self._uncertain_deliveries.discard(ev.event_id)
                    if direction == "outbox_flushed":
                        self._pending.pop(ev.event_id, None)
                self._by_type.setdefault(p["type"], []).append(len(self._payloads))
                self._payloads.append(p)
                self._latest[ev.event_id] = (p, rec.hash)
            self._folded, self._folded_tail = i + 1, rec
        self._outbox = list(self._pending.values())

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
        """Events in ledger order; each is the caller's own copy."""
        self._refresh()
        if not type_prefix:
            chosen = self._payloads
        else:
            lists = [positions for kind, positions in self._by_type.items() if kind.startswith(type_prefix)]
            order = lists[0] if len(lists) == 1 else heapq.merge(*lists)  # positions ascend: ledger order
            chosen = [self._payloads[i] for i in order]
        return [self._event_copy(p) for p in chosen]

    def since(self, type_prefix, cursor=None):
        """Events of this prefix retained after ``cursor``, in ledger order, each the caller's own copy.

        Returns ``(events, cursor, restarted)``. Pass the returned cursor to the next call to get
        only what was added in between; ``replay(type_prefix)`` equals the events of the first call
        followed by those of every later one. A cursor from before the history was replaced (or
        None) is not honored: the events then start from the beginning and ``restarted`` is True,
        so a caller folding them must start its projection over.
        """
        self._refresh()
        start, restarted = 0, True
        if cursor is not None and cursor[0] is self._generation:  # _payloads only grows within one
            start, restarted = cursor[1], False
        events = [self._event_copy(p) for p in self._payloads[start:] if p["type"].startswith(type_prefix)]
        return events, (self._generation, len(self._payloads)), restarted

    def positions(self, type_prefix=""):
        """event_id -> position of its last record among the events replay(type_prefix) returns.

        Exactly {e.event_id: i for i, e in enumerate(self.replay(type_prefix))}, kept up to date by
        counting only events added since the last call. Read-only.
        """
        self._refresh()
        seen, count, index = self._positions.get(type_prefix, (0, 0, {}))
        for i in range(seen, len(self._payloads)):
            p = self._payloads[i]
            if p["type"].startswith(type_prefix):
                index[p["event_id"]] = count
                count += 1
        self._positions[type_prefix] = (len(self._payloads), count, index)
        return MappingProxyType(index)

    def latest(self, event_id):
        """The last retained record of this event identity as an Event, or None."""
        self._refresh()
        found = self._latest.get(event_id)
        return None if found is None else self._event_copy(found[0])

    def record_hash(self, event_id):
        """Ledger hash of the last retained record of this event identity, or None."""
        self._refresh()
        found = self._latest.get(event_id)
        return None if found is None else found[1]

    def outbox_stage(self, event):
        return self._accept(event, "outbox_staged")

    def outbox_flush(self, mediator=None):
        from provenance.ledger import ReconciliationRequired, copy_json
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
                    # The mediator gets its own copy: what is written next is the staged fact, not
                    # whatever the mediator did to the object it was shown.
                    allowed = bool(mediator(Event(**{**{k: getattr(ev, k) for k in Event.__dataclass_fields__},
                                                     "payload": copy_json(ev.payload)})))
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
