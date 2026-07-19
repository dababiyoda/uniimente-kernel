"""Layer 4 acceptance tests: durable event spine + resumable workflows.

The durability contract under test: a workflow killed mid-flight resumes
from its last checkpoint and completes WITHOUT re-executing finished
steps and without any manual restatement of state.
"""
import pytest

from events.spine import (Event, EventError, EventSpine, DurableWorkflow,
                          WorkflowStep, WorkflowKilled, WorkflowFailed,
                          SPIFFE_PREFIX)
from provenance.ledger import EvidenceLedger

GENESIS = "sha256:" + "0" * 64
SRC = SPIFFE_PREFIX + "workflow/test"


def _spine():
    return EventSpine(EvidenceLedger(GENESIS))


def _event(**kw):
    base = dict(type="draft.published", source=SRC, actor="alfonso",
                legal_principal="alfonso_lopez", payload={"x": 1})
    base.update(kw)
    return Event(**base)


# ---------------------------------------------------------------- event schema
class TestEventSchema:
    def test_type_must_be_namespaced(self):
        with pytest.raises(EventError):
            _event(type="NoNamespace").validate()
        with pytest.raises(EventError):
            _event(type="UPPER.case").validate()

    def test_uniimente_never_principal(self):
        with pytest.raises(EventError):
            _event(legal_principal="UNIIMENTE").validate()

    def test_sensitivity_enum(self):
        with pytest.raises(EventError):
            _event(sensitivity="top_secret").validate()

    def test_emit_requires_spiffe_source(self):
        spine = _spine()
        with pytest.raises(EventError):
            spine.emit(_event(source="https://external.example"))


# ---------------------------------------------------------------- spine behavior
class TestSpine:
    def test_emit_ledgers_and_dispatches(self):
        spine = _spine()
        got = []
        spine.subscribe("draft.", got.append)
        ev = spine.emit(_event())
        assert got == [ev]
        assert len(spine.ledger.by_type("event")) == 1

    def test_ingest_is_idempotent(self):
        spine = _spine()
        ev = _event(source="ext:partner-webhook")
        assert spine.ingest(ev) is ev
        assert spine.ingest(ev) is None               # duplicate dropped
        assert len(spine.ledger.by_type("event")) == 1

    def test_replay_rebuilds_stream_from_ledger(self):
        spine = _spine()
        spine.emit(_event(payload={"n": 1}))
        spine.emit(_event(type="settlement.completed", payload={"n": 2}))
        spine.emit(_event(payload={"n": 3}))
        all_events = spine.replay()
        drafts = spine.replay("draft.")
        assert [e.payload["n"] for e in all_events] == [1, 2, 3]
        assert [e.payload["n"] for e in drafts] == [1, 3]

    def test_event_carries_identity_principal_causal_parent_policy_version(self):
        """Issue #4 exit evidence: every event carries identity, legal
        principal, causal parent, and policy version."""
        spine = _spine()
        parent = spine.emit(_event(payload={"n": "parent"}))
        child = spine.emit(_event(payload={"n": "child"}, causal_parent=parent.event_id,
                                  policy_version="1.0.0"))
        replayed = {e.event_id: e for e in spine.replay()}
        c = replayed[child.event_id]
        assert c.actor == "alfonso"                        # identity
        assert c.legal_principal == "alfonso_lopez"        # legal principal
        assert c.causal_parent == parent.event_id          # causal parent
        assert c.policy_version == "1.0.0"                 # policy version

    def test_outbox_refused_stays_staged(self):
        spine = _spine()
        a, b = _event(payload={"n": "a"}), _event(payload={"n": "b"})
        spine.outbox_stage(a)
        spine.outbox_stage(b)
        flushed = spine.outbox_flush(mediator=lambda ev: ev.payload["n"] == "a")
        assert [e.payload["n"] for e in flushed] == ["a"]
        # refused event remains staged and is flushed by a later, permissive flush
        flushed2 = spine.outbox_flush()
        assert [e.payload["n"] for e in flushed2] == ["b"]
        kinds = [r.payload["direction"] for r in spine.ledger.by_type("event")]
        assert "outbox_refused" in kinds and "outbox_flushed" in kinds


# ---------------------------------------------------------------- durability
def _three_step_workflow(spine, calls, boom_at=None):
    def mk(name):
        def run(state):
            calls.append(name)
            if boom_at == name:
                raise RuntimeError(f"{name} exploded")
            return {name: "done"}
        def compensate(state):
            calls.append(f"undo:{name}")
            state.pop(name, None)
        return WorkflowStep(name=name, run=run, compensate=compensate)
    return DurableWorkflow(spine, "wf-1", [mk("s1"), mk("s2"), mk("s3")],
                           actor="alfonso", legal_principal="alfonso_lopez")


class TestDurability:
    def test_kill_and_resume_without_restatement(self):
        spine = _spine()
        calls = []
        wf = _three_step_workflow(spine, calls)
        with pytest.raises(WorkflowKilled):
            wf.execute(kill_at_step="s2")
        assert calls == ["s1"]                          # s1 ran, s2/s3 did not

        fresh_calls = []
        resumed = DurableWorkflow.resume(spine, "wf-1",
                                         steps=_three_step_workflow(spine, fresh_calls).steps)
        assert resumed.cursor == 1 and resumed.state == {"s1": "done"}
        resumed.execute()
        assert resumed.status == "completed"
        assert fresh_calls == ["s2", "s3"]              # s1 NOT re-executed
        assert resumed.state == {"s1": "done", "s2": "done", "s3": "done"}

    def test_resume_rejects_terminal_workflow(self):
        spine = _spine()
        wf = _three_step_workflow(spine, [])
        wf.execute()
        with pytest.raises(EventError):
            DurableWorkflow.resume(spine, "wf-1", steps=wf.steps)

    def test_retries_exhausted_compensates_in_reverse(self):
        spine = _spine()
        calls = []
        wf = _three_step_workflow(spine, calls, boom_at="s3")
        with pytest.raises(WorkflowFailed):
            wf.execute()
        # s3 never succeeded; compensation undoes s2 then s1 (reverse order)
        assert calls[-2:] == ["undo:s2", "undo:s1"]
        assert wf.status == "compensated"
        comp = [e for e in spine.replay("workflow.compensation")]
        assert [e.payload["step"] for e in comp] == ["s2", "s1"]

    def test_approval_wait_blocks_without_approver(self):
        spine = _spine()
        step = WorkflowStep(name="pay", run=lambda s: {"paid": True},
                            compensate=lambda s: None, approval_wait=True)
        wf = DurableWorkflow(spine, "wf-pay", [step],
                             actor="alfonso", legal_principal="alfonso_lopez")
        with pytest.raises(WorkflowKilled):             # no approver -> waits, never executes
            wf.execute()
        assert "paid" not in wf.state
        resumed = DurableWorkflow.resume(spine, "wf-pay", steps=[step])
        resumed.execute(approver=lambda s: True)        # human ratifies -> proceeds
        assert resumed.state["paid"] is True

    def test_workflow_never_names_uniimente(self):
        spine = _spine()
        with pytest.raises(EventError):
            DurableWorkflow(spine, "wf-x", [], actor="a", legal_principal="UNIIMENTE")
