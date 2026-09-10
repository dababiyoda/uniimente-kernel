"""Successor subject and migration controls; frozen experiments stay sealed."""
import copy
from dataclasses import replace
from pathlib import Path

import pytest

from events.spine import EventSpine, WorkflowStep, DurableWorkflow, WorkflowKilled, EventError
from evolution.migration.migrate import to_current_checkpoint
from evolution.repair.harness import ReplacementExperiment
from evolution.repair.subjects import FROZEN, SR001
from provenance.ledger import EvidenceLedger

ROOT = Path(__file__).resolve().parents[2]


def legacy():
    return dict(workflow_id="p4x-reviewed", cursor=1, state={"first": 1},
                status="interrupted", note="killed_before:second", actor="fixture",
                legal_principal="alfonso_lopez", at="2026-09-08T00:00:00Z")


def harmless(calls):
    return [WorkflowStep(name, lambda s, n=name: calls.append(n) or {n: 1},
                         retry_safe=True) for name in ("first", "second")]


def test_current_binding_does_not_revalidate_the_old_subject():
    assert SR001.matches(ROOT)
    assert not FROZEN.matches(ROOT)
    with pytest.raises(ValueError, match="unreviewed"):
        ReplacementExperiment(subject=replace(SR001, source_commit="invented"))


def test_changed_source_fails_instead_of_learning_a_new_fingerprint(tmp_path):
    for relative, _ in SR001.artifacts:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    assert SR001.matches(tmp_path)
    with (tmp_path / "policy/consequence_gate.py").open("a") as handle:
        handle.write("\n# source changed after review\n")
    assert not SR001.matches(tmp_path)


def test_migration_preserves_identity_time_state_and_append_before_resume(tmp_path):
    original = legacy()
    saved = copy.deepcopy(original)
    calls = []
    steps = harmless(calls)
    result = to_current_checkpoint(original, steps)
    assert original == saved
    assert result.payload is not None
    assert all(result.payload[k] == v for k, v in original.items())
    ledger = EvidenceLedger("sha256:" + "a" * 64, str(tmp_path / "history.jsonl"))
    ledger.append("workflow", original)
    ledger.append("workflow", result.payload)
    ledger.close()
    ledger = EvidenceLedger("sha256:" + "a" * 64, str(tmp_path / "history.jsonl"))
    recovered = DurableWorkflow.resume(EventSpine(ledger), original["workflow_id"], steps)
    recovered.execute()
    assert calls == ["second"]
    assert recovered.state == {"first": 1, "second": 1}
    ledger.close()


@pytest.mark.parametrize("change", [
    {"status": "completed"}, {"status": "running", "note": "step_started:second"},
    {"note": "killed_during:second"}, {"note": "rolled_back"},
    {"cursor": 99}, {"at": "not-a-date"}, {"legal_principal": "UNIIMENTE"},
])
def test_migration_refuses_uncertainty_invalid_state_or_identity(change):
    original = {**legacy(), **change}
    saved = copy.deepcopy(original)
    result = to_current_checkpoint(original, harmless([]))
    assert result.payload is None
    assert original == saved


def test_legacy_omitted_execution_contract_cannot_gain_retry_permission():
    steps = harmless([])
    steps[1].retry_safe = False
    assert to_current_checkpoint(legacy(), steps).payload is None


def test_existing_workflow_still_refuses_contract_change_after_restart():
    calls = []
    steps = harmless(calls)
    spine = EventSpine(EvidenceLedger("sha256:" + "a" * 64))
    workflow = DurableWorkflow(spine, "original", steps, actor="fixture", legal_principal="alfonso_lopez")
    with pytest.raises(WorkflowKilled):
        workflow.execute(kill_at_step="second")
    steps[1].retry_safe = False
    with pytest.raises(EventError, match="changed workflow step contract"):
        DurableWorkflow.resume(spine, "original", steps)
    assert calls == ["first"]
