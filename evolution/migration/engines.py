"""The three replacement workflow engines. W0 is the original, untouched.

Each implements the same construction and resume interface as
`events.spine.DurableWorkflow`, so the canonical construction sites can build
any of them without knowing which they got. None imports the original: these are
independent implementations, not wrappers, or they would inherit its correctness
and prove nothing.

MATERIAL DIFFERENCE, frozen in spec.MATERIAL_DIFFERENCE_CLAIMS:

  W1-projection  stores no position. cursor and state are DERIVED by folding the
                 checkpoint stream on every resume, where the original reads the
                 last snapshot.
  W2-token       position by step NAME. Different state schema; the only
                 candidate requiring a real migration and reverse migration.
  W3-journal     carries an explicit undo stack IN STATE, which the original
                 recomputes from the step list at compensation time.

W3's claim was frozen before implementation and is implemented faithfully,
including its consequence: an undo stack living in the checkpointed `state`
namespace is visible in the compared state. If that fails the exactness gate,
that is the frozen design's real result, not a bug to quietly relocate.
"""
from __future__ import annotations

from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class EngineError(RuntimeError):
    """Base for engine-level refusals that mirror the original's semantics."""


TERMINAL = ("completed", "failed", "compensated")


# ==========================================================================
# W1 — projection: no stored position, folded from the stream
# ==========================================================================

class ProjectionEngine:
    """State is a projection over the checkpoint stream, never a snapshot read.

    `resume` does not read the last checkpoint's cursor. It replays every
    `step_completed` note for this workflow and counts them. The position is
    therefore derived, and a corrupted final snapshot cannot mislead it — but it
    is order-sensitive, which is the risk recorded in the frozen prediction.
    """

    candidate_id = "W1-projection"
    schema_id = "W0"

    def __init__(self, spine, workflow_id, steps, *, actor, legal_principal):
        if legal_principal == "UNIIMENTE":
            raise EngineError("workflow legal principal is never UNIIMENTE")
        self.spine, self.workflow_id, self.steps = spine, workflow_id, steps
        self.actor, self.legal_principal = actor, legal_principal
        self.cursor, self.state, self.status = 0, {}, "running"

    # -- projection ---------------------------------------------------------
    @staticmethod
    def _fold(spine, workflow_id):
        """Derive (cursor, state, status, actor, principal) from the stream."""
        records = [r.payload for r in spine.ledger.by_type("workflow")
                   if r.payload.get("workflow_id") == workflow_id]
        if not records:
            return None
        completed, state = 0, {}
        for payload in records:
            note = payload.get("note", "")
            if note.startswith("step_completed:"):
                completed += 1
                state = dict(payload.get("state") or {})
        return {"cursor": completed, "state": state,
                "status": records[-1].get("status"),
                "actor": records[-1].get("actor"),
                "legal_principal": records[-1].get("legal_principal")}

    def _checkpoint(self, note):
        self.spine.ledger.append("workflow", {
            "workflow_id": self.workflow_id, "cursor": self.cursor,
            "status": self.status, "state": dict(self.state), "note": note,
            "actor": self.actor, "legal_principal": self.legal_principal,
            "at": _now()})

    @staticmethod
    def resume(spine, workflow_id, steps):
        from events.spine import EventError

        folded = ProjectionEngine._fold(spine, workflow_id)
        if folded is None:
            raise EventError(f"no checkpoints for workflow {workflow_id!r}")
        if folded["status"] in TERMINAL:
            raise EventError(f"workflow is {folded['status']}; nothing to resume")
        wf = ProjectionEngine(spine, workflow_id, steps, actor=folded["actor"],
                              legal_principal=folded["legal_principal"])
        wf.cursor, wf.state, wf.status = folded["cursor"], folded["state"], "running"
        wf._checkpoint("resumed")
        return wf

    # -- execution ----------------------------------------------------------
    def execute(self, *, kill_at_step=None, approver=None):
        from events.spine import Event, SPIFFE_PREFIX, WorkflowFailed, WorkflowKilled

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
                    type="workflow.approval_wait",
                    source=SPIFFE_PREFIX + "workflow/" + self.workflow_id,
                    actor=self.actor, legal_principal=self.legal_principal,
                    payload={"workflow_id": self.workflow_id, "step": step.name,
                             "approved": ok}))
                if not ok:
                    self.status = "interrupted"
                    self._checkpoint(f"approval_pending:{step.name}")
                    raise WorkflowKilled(f"approval pending at step {step.name!r}")
            attempts = 0
            while True:
                try:
                    self.state.update(step.run(self.state) or {})
                    self.cursor += 1
                    self._checkpoint(f"step_completed:{step.name}")
                    break
                except WorkflowKilled:
                    self.status = "interrupted"
                    self._checkpoint(f"killed_during:{step.name}")
                    raise
                except Exception as exc:
                    attempts += 1
                    self.spine.emit(Event(
                        type="workflow.step_failed",
                        source=SPIFFE_PREFIX + "workflow/" + self.workflow_id,
                        actor=self.actor, legal_principal=self.legal_principal,
                        sensitivity="confidential",
                        payload={"workflow_id": self.workflow_id, "step": step.name,
                                 "attempt": attempts, "error": str(exc)[:200]}))
                    if attempts > step.max_retries:
                        self._compensate(step.name)
                        self.status = "compensated" if self.cursor > 0 else "failed"
                        self._checkpoint(f"retries_exhausted:{step.name}")
                        raise WorkflowFailed(
                            f"step {step.name!r} failed after {attempts} attempts; "
                            f"workflow {self.status}") from exc
        self.status = "completed"
        self._checkpoint("completed")
        return self

    def _compensate(self, failed_step):
        from events.spine import Event, SPIFFE_PREFIX

        for step in reversed(self.steps[: self.cursor]):
            if step.compensate is None:
                continue
            try:
                step.compensate(self.state)
                note, ok = "compensated", True
            except Exception as exc:
                note, ok = f"compensation_failed:{str(exc)[:120]}", False
            self.spine.emit(Event(
                type="workflow.compensation",
                source=SPIFFE_PREFIX + "workflow/" + self.workflow_id,
                actor=self.actor, legal_principal=self.legal_principal,
                sensitivity="confidential",
                payload={"workflow_id": self.workflow_id, "step": step.name,
                         "failed_step": failed_step, "ok": ok, "note": note}))


# ==========================================================================
# W2 — token: position by name. The schema-changing candidate.
# ==========================================================================

class TokenEngine:
    """Position is a step NAME, not an index.

    Checkpoints carry `completed_steps` and `next_step` instead of `cursor`, so
    reading a W0 checkpoint requires a real migration and writing one requires
    the reverse. This is the candidate the experiment is actually about.
    """

    candidate_id = "W2-token"
    schema_id = "W2"

    def __init__(self, spine, workflow_id, steps, *, actor, legal_principal):
        if legal_principal == "UNIIMENTE":
            raise EngineError("workflow legal principal is never UNIIMENTE")
        self.spine, self.workflow_id, self.steps = spine, workflow_id, steps
        self.actor, self.legal_principal = actor, legal_principal
        self.completed_steps: list[str] = []
        self.state, self.status = {}, "running"

    # Positional identity is by name; `cursor` is a derived view kept only so
    # the comparison harness can read every engine the same way.
    @property
    def cursor(self) -> int:
        return len(self.completed_steps)

    @property
    def next_step(self):
        names = [s.name for s in self.steps]
        return names[self.cursor] if self.cursor < len(names) else None

    def _checkpoint(self, note):
        self.spine.ledger.append("workflow", {
            "workflow_id": self.workflow_id,
            "completed_steps": list(self.completed_steps),
            "next_step": self.next_step,
            "status": self.status, "state": dict(self.state), "note": note,
            "actor": self.actor, "legal_principal": self.legal_principal,
            "at": _now()})

    @staticmethod
    def resume(spine, workflow_id, steps):
        from events.spine import EventError
        from evolution.migration.migrate import forward

        records = [r.payload for r in spine.ledger.by_type("workflow")
                   if r.payload.get("workflow_id") == workflow_id]
        if not records:
            raise EventError(f"no checkpoints for workflow {workflow_id!r}")
        last = records[-1]
        if last["status"] in TERMINAL:
            raise EventError(f"workflow is {last['status']}; nothing to resume")

        names = [s.name for s in steps]
        if "completed_steps" not in last:
            # A W0 checkpoint written by the original. Migrate it, refusing
            # rather than guessing if the step names are ambiguous.
            result = forward(last, names)
            if result.payload is None:
                raise EventError(f"migration refused: {result.reason}")
            last = result.payload

        wf = TokenEngine(spine, workflow_id, steps, actor=last["actor"],
                         legal_principal=last["legal_principal"])
        wf.completed_steps = list(last["completed_steps"])
        wf.state, wf.status = dict(last["state"]), "running"
        wf._checkpoint("resumed")
        return wf

    def execute(self, *, kill_at_step=None, approver=None):
        from events.spine import Event, SPIFFE_PREFIX, WorkflowFailed, WorkflowKilled

        self._checkpoint("execute_enter")
        while self.next_step is not None:
            step = self.steps[self.cursor]
            if step.name == kill_at_step:
                self.status = "interrupted"
                self._checkpoint(f"killed_before:{step.name}")
                raise WorkflowKilled(f"interrupted before step {step.name!r}")
            if step.approval_wait:
                ok = bool(approver(step)) if approver else False
                self.spine.emit(Event(
                    type="workflow.approval_wait",
                    source=SPIFFE_PREFIX + "workflow/" + self.workflow_id,
                    actor=self.actor, legal_principal=self.legal_principal,
                    payload={"workflow_id": self.workflow_id, "step": step.name,
                             "approved": ok}))
                if not ok:
                    self.status = "interrupted"
                    self._checkpoint(f"approval_pending:{step.name}")
                    raise WorkflowKilled(f"approval pending at step {step.name!r}")
            attempts = 0
            while True:
                try:
                    self.state.update(step.run(self.state) or {})
                    self.completed_steps.append(step.name)
                    self._checkpoint(f"step_completed:{step.name}")
                    break
                except WorkflowKilled:
                    self.status = "interrupted"
                    self._checkpoint(f"killed_during:{step.name}")
                    raise
                except Exception as exc:
                    attempts += 1
                    self.spine.emit(Event(
                        type="workflow.step_failed",
                        source=SPIFFE_PREFIX + "workflow/" + self.workflow_id,
                        actor=self.actor, legal_principal=self.legal_principal,
                        sensitivity="confidential",
                        payload={"workflow_id": self.workflow_id, "step": step.name,
                                 "attempt": attempts, "error": str(exc)[:200]}))
                    if attempts > step.max_retries:
                        self._compensate(step.name)
                        self.status = "compensated" if self.completed_steps else "failed"
                        self._checkpoint(f"retries_exhausted:{step.name}")
                        raise WorkflowFailed(
                            f"step {step.name!r} failed after {attempts} attempts; "
                            f"workflow {self.status}") from exc
        self.status = "completed"
        self._checkpoint("completed")
        return self

    def _compensate(self, failed_step):
        from events.spine import Event, SPIFFE_PREFIX

        by_name = {s.name: s for s in self.steps}
        for name in reversed(self.completed_steps):
            step = by_name[name]
            if step.compensate is None:
                continue
            try:
                step.compensate(self.state)
                note, ok = "compensated", True
            except Exception as exc:
                note, ok = f"compensation_failed:{str(exc)[:120]}", False
            self.spine.emit(Event(
                type="workflow.compensation",
                source=SPIFFE_PREFIX + "workflow/" + self.workflow_id,
                actor=self.actor, legal_principal=self.legal_principal,
                sensitivity="confidential",
                payload={"workflow_id": self.workflow_id, "step": name,
                         "failed_step": failed_step, "ok": ok, "note": note}))


# ==========================================================================
# W3 — journal: explicit undo stack carried in state
# ==========================================================================

UNDO_KEY = "__undo__"


class JournalEngine:
    """Maintains an explicit undo stack instead of recomputing it in reverse.

    The frozen claim says the stack is carried IN STATE, and it is. That is the
    honest implementation of what was predicted, and it has a consequence: the
    stack is visible in the checkpointed `state` namespace that the exactness
    gate compares. Whether that disqualifies W3 is the experiment's finding,
    not something to engineer away after seeing the gate.
    """

    candidate_id = "W3-journal"
    schema_id = "W0"

    def __init__(self, spine, workflow_id, steps, *, actor, legal_principal):
        if legal_principal == "UNIIMENTE":
            raise EngineError("workflow legal principal is never UNIIMENTE")
        self.spine, self.workflow_id, self.steps = spine, workflow_id, steps
        self.actor, self.legal_principal = actor, legal_principal
        self.cursor, self.status = 0, "running"
        self.state = {UNDO_KEY: []}

    def _checkpoint(self, note):
        self.spine.ledger.append("workflow", {
            "workflow_id": self.workflow_id, "cursor": self.cursor,
            "status": self.status, "state": dict(self.state), "note": note,
            "actor": self.actor, "legal_principal": self.legal_principal,
            "at": _now()})

    @staticmethod
    def resume(spine, workflow_id, steps):
        from events.spine import EventError

        records = [r.payload for r in spine.ledger.by_type("workflow")
                   if r.payload.get("workflow_id") == workflow_id]
        if not records:
            raise EventError(f"no checkpoints for workflow {workflow_id!r}")
        last = records[-1]
        if last["status"] in TERMINAL:
            raise EventError(f"workflow is {last['status']}; nothing to resume")
        wf = JournalEngine(spine, workflow_id, steps, actor=last["actor"],
                           legal_principal=last["legal_principal"])
        wf.cursor = last["cursor"]
        wf.state = dict(last["state"])
        wf.state.setdefault(UNDO_KEY, [s.name for s in steps[: wf.cursor]])
        wf.status = "running"
        wf._checkpoint("resumed")
        return wf

    def execute(self, *, kill_at_step=None, approver=None):
        from events.spine import Event, SPIFFE_PREFIX, WorkflowFailed, WorkflowKilled

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
                    type="workflow.approval_wait",
                    source=SPIFFE_PREFIX + "workflow/" + self.workflow_id,
                    actor=self.actor, legal_principal=self.legal_principal,
                    payload={"workflow_id": self.workflow_id, "step": step.name,
                             "approved": ok}))
                if not ok:
                    self.status = "interrupted"
                    self._checkpoint(f"approval_pending:{step.name}")
                    raise WorkflowKilled(f"approval pending at step {step.name!r}")
            attempts = 0
            while True:
                try:
                    delta = step.run(self.state) or {}
                    self.state.update(delta)
                    self.state[UNDO_KEY] = list(self.state.get(UNDO_KEY, [])) + [step.name]
                    self.cursor += 1
                    self._checkpoint(f"step_completed:{step.name}")
                    break
                except WorkflowKilled:
                    self.status = "interrupted"
                    self._checkpoint(f"killed_during:{step.name}")
                    raise
                except Exception as exc:
                    attempts += 1
                    self.spine.emit(Event(
                        type="workflow.step_failed",
                        source=SPIFFE_PREFIX + "workflow/" + self.workflow_id,
                        actor=self.actor, legal_principal=self.legal_principal,
                        sensitivity="confidential",
                        payload={"workflow_id": self.workflow_id, "step": step.name,
                                 "attempt": attempts, "error": str(exc)[:200]}))
                    if attempts > step.max_retries:
                        self._compensate(step.name)
                        self.status = "compensated" if self.cursor > 0 else "failed"
                        self._checkpoint(f"retries_exhausted:{step.name}")
                        raise WorkflowFailed(
                            f"step {step.name!r} failed after {attempts} attempts; "
                            f"workflow {self.status}") from exc
        self.status = "completed"
        self._checkpoint("completed")
        return self

    def _compensate(self, failed_step):
        from events.spine import Event, SPIFFE_PREFIX

        by_name = {s.name: s for s in self.steps}
        # The whole point of W3: pop the explicit stack rather than recompute it.
        stack = list(self.state.get(UNDO_KEY, []))
        while stack:
            name = stack.pop()
            step = by_name.get(name)
            if step is None or step.compensate is None:
                continue
            try:
                step.compensate(self.state)
                note, ok = "compensated", True
            except Exception as exc:
                note, ok = f"compensation_failed:{str(exc)[:120]}", False
            self.spine.emit(Event(
                type="workflow.compensation",
                source=SPIFFE_PREFIX + "workflow/" + self.workflow_id,
                actor=self.actor, legal_principal=self.legal_principal,
                sensitivity="confidential",
                payload={"workflow_id": self.workflow_id, "step": name,
                         "failed_step": failed_step, "ok": ok, "note": note}))


ENGINES = {"W1-projection": ProjectionEngine, "W2-token": TokenEngine,
           "W3-journal": JournalEngine}
