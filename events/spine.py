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
    """Append-only event log on the evidence ledger + pub/sub + outbox.

    The ledger is the durable store; the spine is its event interface.
    Every emitted/ingested event is ledgered first, then dispatched —
    a crash between the two is healed by replay (subscribers are
    re-notified from the log, never from memory).
    """

    def __init__(self, ledger):
        self.ledger = ledger
        self._subscribers: dict[str, list] = {}      # type prefix -> [callables]
        #: Transactional outbox, REBUILT from the ledger for the same reason the
        #: inbox below is. Found 2026-08-23 while composing `runtime/`, by the
        #: probe that the inbox fix suggested: if one in-process view of the
        #: ledger was wrong, look at the others.
        #:
        #: An outbox exists precisely so that a delivery survives the crash
        #: between deciding to send and sending. This one was a plain list, so a
        #: staged-but-unflushed event was ledgered as owed and then forgotten by
        #: the only object that could act on it — the durable record said the
        #: institution owed a delivery and nothing was left holding the debt.
        #: Demonstrated before it was fixed (stage, reload, depth 0 against one
        #: unsettled `outbox_staged` record) and pinned by
        #: `test_a_staged_delivery_survives_a_restart`.
        self._outbox: list[Event] = self._outbox_from_ledger()
        #: Idempotent inbox, REBUILT from the ledger rather than started empty.
        #:
        #: Fixed 2026-08-23 while establishing restart/resume. The inbox was an
        #: empty set at construction, so replay protection lived only in process
        #: memory: a durable ledger reloaded after a restart came back with a
        #: fresh spine that had never seen anything, and re-ingesting a
        #: byte-identical peer event was accepted and ledgered a second time.
        #:
        #: Demonstrated before it was fixed — ingest, reload, ingest the same
        #: event, two records — and pinned by
        #: `test_replay_protection_survives_a_restart`.
        #:
        #: This makes the inbox what every other reader here already is: a view
        #: derived from the ledger. `CausalMemory` and `replay()` were already
        #: built that way, which is why they survived a restart and this did not.
        self._seen_ids: set[str] = self._seen_from_ledger()

    def _seen_from_ledger(self) -> set[str]:
        """Every event id the ledger already carries, emitted or ingested.

        Both directions count. An emitted event whose id later arrived as an
        ingested one would be the institution accepting its own claim back from
        a peer as an external fact — the authority laundering the emit/ingest
        split exists to prevent.
        """
        return {p["event_id"] for p in self._spine_payloads()}

    @staticmethod
    def _is_spine_event(payload) -> bool:
        """Is this ledger record one of *this* spine's events?

        `record_type="event"` is a shared namespace. `ConsequenceGate._transition`
        writes action-lifecycle records under it too — `{"type": "action.refused",
        "action_id": ..., "proposal_id": ...}` — with no `source`, `actor` or
        `event_id`, because they are a different kind of thing that happens to
        share a bucket.

        Every view here must therefore identify its own records POSITIVELY.
        `_seen_from_ledger` and `CausalMemory._events` both did; `replay()` did
        not, and raised `KeyError: 'source'` the first time a gate and a spine
        shared one ledger — which is to say, the first time anything composed
        them, which is `runtime/`. Demonstrated on unmodified main before it was
        fixed here.

        Renaming the gate's record type would be the tidier fix and is the wrong
        one: those records are already on disk in existing chains, and changing
        what a historical record is called rewrites what it meant. The reader
        adapts to the record, not the record to the reader.
        """
        return isinstance(payload, dict) and "event_id" in payload

    def _spine_payloads(self) -> list[dict]:
        return [r.payload for r in self.ledger.by_type("event")
                if self._is_spine_event(r.payload)]

    @staticmethod
    def _event_from_payload(p: dict) -> Event:
        """One reconstruction, used by every view. Memory is never truth."""
        return Event(type=p["type"], source=p["source"], actor=p["actor"],
                     payload=p["payload"], legal_principal=p["legal_principal"],
                     sensitivity=p["sensitivity"], event_id=p["event_id"],
                     occurred_at=p["occurred_at"],
                     causal_parent=p.get("causal_parent"),
                     policy_version=p.get("policy_version"))

    def _outbox_from_ledger(self) -> list[Event]:
        """Staged deliveries the ledger has not yet seen settled, in order.

        Only a flush settles a debt. A refusal is deliberately *not* settlement:
        `outbox_flush` re-keeps a refused event, because the mediator declining
        today does not mean the institution stopped owing the delivery. Rebuild
        must preserve that or a restart would silently discharge everything the
        gate had ever refused — turning a refusal into a delivery that never
        happens and is never owed again.
        """
        staged: list[Event] = []
        for p in self._spine_payloads():
            direction = p.get("direction")
            if direction == "outbox_staged":
                staged.append(self._event_from_payload(p))
            elif direction == "outbox_flushed":
                for i, pending in enumerate(staged):
                    if pending.event_id == p["event_id"]:
                        del staged[i]
                        break
        return staged

    # ------------------------------------------------------------ write
    def emit(self, event: Event) -> Event:
        event.validate()
        if not event.source.startswith(SPIFFE_PREFIX):
            raise EventError("internal emissions require a spiffe source; use ingest() for external facts")
        self.ledger.append("event", {**asdict(event), "direction": "emitted"})
        self._seen_ids.add(event.event_id)
        self._dispatch(event)
        return event

    def ingest(self, event: Event) -> Event | None:
        """External fact entering the institution. Idempotent by event_id."""
        event.validate()
        if event.event_id in self._seen_ids:
            return None                               # duplicate: dropped, not re-ledgered
        self._seen_ids.add(event.event_id)
        self.ledger.append("event", {**asdict(event), "direction": "ingested"})
        self._dispatch(event)
        return event

    # ------------------------------------------------------------ read
    def subscribe(self, type_prefix: str, handler) -> None:
        self._subscribers.setdefault(type_prefix, []).append(handler)

    def _dispatch(self, event: Event) -> None:
        for prefix, handlers in self._subscribers.items():
            if event.type.startswith(prefix):
                for h in handlers:
                    h(event)

    def replay(self, type_prefix: str | None = None) -> list[Event]:
        """Rebuild the event stream from the ledger. Memory is never truth."""
        out = []
        for p in self._spine_payloads():
            if type_prefix and not p["type"].startswith(type_prefix):
                continue
            out.append(self._event_from_payload(p))
        return out

    # ------------------------------------------------------------ outbox
    def outbox_stage(self, event: Event) -> Event:
        """Stage an external-bound event. Staging is not sending."""
        event.validate()
        self._outbox.append(event)
        self.ledger.append("event", {**asdict(event), "direction": "outbox_staged"})
        return event

    def outbox_flush(self, mediator=None) -> list[Event]:
        """Deliver staged events through the mediator (production: the gate).

        Each event is flushed individually; a refused event stays staged,
        is ledgered as refused, and does not block the rest of the batch.
        """
        flushed, kept = [], []
        for ev in self._outbox:
            allowed = True if mediator is None else bool(mediator(ev))
            if allowed:
                self.ledger.append("event", {**asdict(ev), "direction": "outbox_flushed"})
                flushed.append(ev)
            else:
                self.ledger.append("event", {**asdict(ev), "direction": "outbox_refused"})
                kept.append(ev)
        self._outbox = kept
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
        self.actor = actor
        self.legal_principal = legal_principal
        self.cursor = 0                  # next step to execute
        self.state: dict = {}            # accumulated step outputs
        self.status = "running"

    # ------------------------------------------------------------ durability
    def _checkpoint(self, note: str) -> None:
        self.spine.ledger.append("workflow", {
            "workflow_id": self.workflow_id, "cursor": self.cursor,
            "status": self.status, "state": dict(self.state), "note": note,
            "actor": self.actor, "legal_principal": self.legal_principal,
            "at": _now()})

    @staticmethod
    def resume(spine: EventSpine, workflow_id: str, steps: list[WorkflowStep]) -> "DurableWorkflow":
        """Reconstruct from the ledger. Steps must be the same definitions."""
        cps = [r for r in spine.ledger.by_type("workflow")
               if r.payload.get("workflow_id") == workflow_id]
        if not cps:
            raise EventError(f"no checkpoints for workflow {workflow_id!r}")
        last = cps[-1].payload
        if last["status"] in ("completed", "compensated", "failed"):
            raise EventError(f"workflow is {last['status']}; nothing to resume")
        wf = DurableWorkflow(spine, workflow_id, steps,
                             actor=last["actor"], legal_principal=last["legal_principal"])
        wf.cursor = last["cursor"]
        wf.state = dict(last["state"])
        wf.status = "running"
        wf._checkpoint("resumed")
        return wf

    # ------------------------------------------------------------ execution
    def execute(self, *, kill_at_step: str | None = None, approver=None) -> "DurableWorkflow":
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
                try:
                    delta = step.run(self.state) or {}
                    self.state.update(delta)
                    self.cursor += 1
                    self._checkpoint(f"step_completed:{step.name}")
                    break
                except WorkflowKilled:
                    self.status = "interrupted"
                    self._checkpoint(f"killed_during:{step.name}")
                    raise
                except Exception as exc:                       # step failure
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
# DurableWorkflow class above is UNCHANGED and remains the default: with no
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
