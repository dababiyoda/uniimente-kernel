"""Phase 4 acceptance tests: the Automation Loom.

The machine authors workflow patterns as data; the human ratifies; only
then does the spine execute. Ratification binds to the content hash —
an edited pattern is an unratified pattern. All three canonical
workflows run end-to-end, one surviving a mid-flight kill.
"""
import pytest

from events.spine import EventSpine, WorkflowKilled
from loom.canonical import CANONICAL, daily_reconciliation, evidence_floor_review
from loom.pattern import StepSpec, WorkflowPattern
from loom.ratify import Ratifier
from loom.weaver import LoomRefused, Operation, Weaver
from provenance.ledger import EvidenceLedger

GENESIS = "sha256:" + "0" * 64


def _stack():
    ledger = EvidenceLedger(GENESIS)
    spine = EventSpine(ledger)
    ratifier = Ratifier(ledger)
    return ledger, spine, ratifier


def _operations(calls):
    """Every canonical action name -> a recording no-op operation."""
    def mk(name):
        def run(state, params):
            calls.append(name)
            state[name] = {"done": True, "params": params}
            return {name: state[name]}
        return Operation(run=run)
    names = ["gather_outcomes", "compare_expectations", "publish_report", "retract_report",
             "archive", "replay_corpus", "measure_weak", "draft_floor_proposal",
             "present_to_founder", "record_recommendation", "retract_proposal",
             "validate_packet", "prescreen_packet", "record_decision", "void_decision"]
    return {n: mk(n) for n in names}


# ---------------------------------------------------------------- patterns
class TestPatternContract:
    def test_irreversible_step_requires_approval_gate(self):
        p = daily_reconciliation()
        p.steps.append(StepSpec(name="nuke", action="x", capability="c",
                                consequence_class="irreversible"))
        problems = p.validate()
        assert any("approval gate" in pr for pr in problems)

    def test_side_effect_step_requires_compensation(self):
        p = daily_reconciliation()
        p.steps.append(StepSpec(name="leak", action="x", capability="c",
                                consequence_class="internal_write"))
        assert any("compensation" in pr for pr in p.validate())

    def test_uniimente_never_principal(self):
        p = daily_reconciliation()
        p.legal_principal = "UNIIMENTE"
        assert any("UNIIMENTE" in pr for pr in p.validate())

    def test_hash_binds_exact_content(self):
        a, b = daily_reconciliation(), daily_reconciliation()
        b.steps[0].params = {"window": "7d"}
        assert a.hash() != b.hash()                     # any edit -> new hash


# ---------------------------------------------------------------- ratification
class TestRatification:
    def test_unratified_pattern_never_weaves(self):
        _, spine, ratifier = _stack()
        weaver = Weaver(spine, ratifier, _operations([]))
        with pytest.raises(LoomRefused, match="not ratified"):
            weaver.weave(daily_reconciliation(), workflow_id="w1")

    def test_edit_after_ratification_invalidates_it(self):
        _, spine, ratifier = _stack()
        weaver = Weaver(spine, ratifier, _operations([]))
        p = daily_reconciliation()
        h = ratifier.submit(p)
        ratifier.decide(h, ratified=True, reason="looks safe")
        assert ratifier.is_ratified(p.hash())
        p.steps[0].params = {"window": "30d"}            # machine edits after ratify
        assert not ratifier.is_ratified(p.hash())
        with pytest.raises(LoomRefused):
            weaver.weave(p, workflow_id="w2")

    def test_rejection_preserved_and_binding(self):
        ledger, _, ratifier = _stack()
        p = daily_reconciliation()
        h = ratifier.submit(p)
        ratifier.decide(h, ratified=False, reason="too much founder attention")
        assert ratifier.status(h) == "rejected"
        types = [r.payload["type"] for r in ledger.by_type("event")]
        assert "loom.pattern_rejected" in types          # negative evidence kept


# ---------------------------------------------------------------- execution
class TestCanonicalExecution:
    def test_all_three_canonical_workflows_execute_end_to_end(self):
        _, spine, ratifier = _stack()
        calls = []
        weaver = Weaver(spine, ratifier, _operations(calls))
        for name, make in CANONICAL.items():
            p = make()
            ratifier.decide(ratifier.submit(p), ratified=True, reason="ratified for production")
            wf = weaver.weave(p, workflow_id=f"wf-{name}")
            wf.execute(approver=lambda step: True)
            assert wf.status == "completed"
        # every step of every pattern actually ran
        for make in CANONICAL.values():
            for s in make().steps:
                assert s.name in calls or s.action in calls

    def test_canonical_workflow_survives_midflight_kill(self):
        _, spine, ratifier = _stack()
        calls = []
        weaver = Weaver(spine, ratifier, _operations(calls))
        p = daily_reconciliation()
        ratifier.decide(ratifier.submit(p), ratified=True, reason="ok")
        wf = weaver.weave(p, workflow_id="wf-kill")
        with pytest.raises(WorkflowKilled):
            wf.execute(kill_at_step="publish_report")
        assert calls == ["gather_outcomes", "compare_expectations"]
        from events.spine import DurableWorkflow
        resumed = DurableWorkflow.resume(spine, "wf-kill", steps=wf.steps)
        resumed.execute()
        assert resumed.status == "completed"
        assert calls == ["gather_outcomes", "compare_expectations",
                         "publish_report", "archive"]   # no re-execution

    def test_approval_gate_blocks_until_human_ratifies(self):
        _, spine, ratifier = _stack()
        calls = []
        weaver = Weaver(spine, ratifier, _operations(calls))
        p = evidence_floor_review()
        ratifier.decide(ratifier.submit(p), ratified=True, reason="ok")
        wf = weaver.weave(p, workflow_id="wf-gate")
        with pytest.raises(WorkflowKilled):              # no approver -> waits at human_gate
            wf.execute()
        assert "record_recommendation" not in calls      # gated step never ran
        from events.spine import DurableWorkflow
        resumed = DurableWorkflow.resume(spine, "wf-gate", steps=wf.steps)
        resumed.execute(approver=lambda step: True)
        assert "record_recommendation" in calls

    def test_unknown_operation_refused(self):
        _, spine, ratifier = _stack()
        weaver = Weaver(spine, ratifier, {})             # empty registry
        p = daily_reconciliation()
        ratifier.decide(ratifier.submit(p), ratified=True, reason="ok")
        with pytest.raises(LoomRefused, match="unknown operation"):
            weaver.weave(p, workflow_id="wf-x")
