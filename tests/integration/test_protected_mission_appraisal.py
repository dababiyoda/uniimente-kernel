"""CMC-002 narrow repair controls. Local simulations, never founder authentication."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from egregore.cathedral_runtime import CathedralMetabolismRuntime, MissionRuntimeError
from events.spine import Event, EventSpine
from events.task_fabric import TaskFabric, TaskFabricError
from provenance.ledger import EvidenceLedger
from omnimorph.organization_compiler import content_digest
from tests.integration.test_cathedral_metabolism_runtime import (
    mission, direct_route, SOURCE, WORKER, TASK_ID, CONSTITUTION,
)
from tests.experiments.retained_appraisal_fixture import worker_result
from verifier import retained_appraisal as protected
from verifier.mission_audit import LIMITATION, PIN_DISSENT


def open_runtime(path):
    ledger = EvidenceLedger(CONSTITUTION, path=str(path))
    spine = EventSpine(ledger)
    return CathedralMetabolismRuntime(spine=spine,
        task_fabric=TaskFabric(spine, source_identity=SOURCE), source_identity=SOURCE)


def submitted(tmp_path, *, fabricated=False, poison=False):
    runtime = open_runtime(tmp_path / "retained.jsonl")
    m = mission()
    runtime.admit(m, trigger_id="cmc-repair-fixture", founder_direction_ref="CMC-MANUAL-DIRECTION-002")
    runtime.route(m["mission_id"], candidates=(direct_route(),))
    runtime.create_task(m["mission_id"], task_id=TASK_ID)
    source = runtime.retain_task_sources(TASK_ID)
    lease = runtime.lease_task(TASK_ID, capability_grant_ref="simulation:not-a-grant",
        worker_identity=WORKER, lease_seconds=120)
    runtime.start_task(TASK_ID, worker_identity=WORKER, lease_id=lease.lease_id)
    result = worker_result()
    if poison:
        result["declared_route_present"] = False
    refs = ("DOES_NOT_EXIST",) if fabricated else (source.event_id,)
    runtime.submit_task(TASK_ID, worker_identity=WORKER, lease_id=lease.lease_id,
                        result=result, evidence_refs=refs)
    return runtime, refs


@pytest.mark.parametrize("claim", ["accepted", "worker", "different_string", "caller_dissent"])
def test_identity_or_acceptance_claim_is_not_appraisal(tmp_path, claim):
    runtime, refs = submitted(tmp_path, fabricated=claim == "accepted")
    args = {
        "accepted": {"accepted": True},
        "worker": {"verifier_identity": WORKER},
        "different_string": {"verifier_identity": "spiffe://uniimente.internal/evaluator/not-protected"},
        "caller_dissent": {"dissent_refs": ("caller says pass",)},
    }[claim]
    with pytest.raises(MissionRuntimeError):
        runtime.verify_task(TASK_ID, evidence_refs=refs, **args)
    assert runtime.task_fabric.tasks()[TASK_ID] == "QUARANTINED"
    assert not list(runtime.spine.replay("mission.appraised"))


def test_fabricated_reference_rejected_without_legacy_flag(tmp_path):
    runtime, refs = submitted(tmp_path, fabricated=True)
    with pytest.raises(MissionRuntimeError, match="missing, fabricated"):
        runtime.verify_task(TASK_ID, evidence_refs=refs)
    assert runtime.task_fabric.tasks()[TASK_ID] == "QUARANTINED"


def test_valid_sources_are_readonly_appraised_and_dissent_survives_closure(tmp_path):
    runtime, refs = submitted(tmp_path)
    before = protected.frozen_snapshot()
    verified = runtime.verify_task(TASK_ID, evidence_refs=refs)
    event = list(runtime.spine.replay("mission.appraised"))[0]
    assert event.payload["receipt"]["process_id"] != os.getpid()
    assert event.payload["receipt"]["appraisal_performed"] is True
    assert event.payload["receipt"]["report"]["accepted"] is True
    assert verified.assessment_refs == (event.event_id,)
    assert verified.dissent_refs == (LIMITATION, PIN_DISSENT)
    assert protected.frozen_snapshot() == before
    runtime.close_task(TASK_ID)
    closure = runtime.finalize(mission()["mission_id"], evidence_refs=(event.event_id,))
    assert closure.payload["verified_durable_mission_closure"] is False
    assert closure.payload["closure_status"] == "SIMULATED_UNVERIFIED"
    assert protected.resolve(runtime.spine, event.event_id, "mission.appraised").payload[
        "receipt"]["report"]["dissent"] == [LIMITATION, PIN_DISSENT]


@pytest.mark.parametrize("target", ["result_digest", "source_digest", "policy", "parent", "task_digest", "mission_digest"])
def test_altered_or_incomplete_lineage_cannot_verify_or_close(tmp_path, target):
    runtime, refs = submitted(tmp_path)
    # Append a hash-valid competing record: integrity alone is not truth.
    kind = "mission.result" if target in {"result_digest", "parent"} else "mission.evidence.retained"
    original = list(runtime.spine.replay(kind))[0]
    payload = copy.deepcopy(original.payload)
    if target == "policy":
        payload["policy"]["version"] = "stale"
    elif target != "parent":
        key = "digest" if target == "source_digest" else target
        payload[key] = "sha256:" + "f" * 64
    runtime.spine.emit(Event(type=kind, source=original.source, actor=original.actor,
        legal_principal=original.legal_principal, causal_parent="missing" if target == "parent" else original.causal_parent,
        payload=payload))
    with pytest.raises(MissionRuntimeError):
        runtime.verify_task(TASK_ID, evidence_refs=refs)
    assert runtime.task_fabric.tasks()[TASK_ID] == "QUARANTINED"
    with pytest.raises((TaskFabricError, protected.AppraisalRefused)):
        runtime.close_task(TASK_ID)


def test_worker_lie_produces_durable_evaluator_disagreement(tmp_path):
    runtime, refs = submitted(tmp_path, poison=True)
    with pytest.raises(MissionRuntimeError, match="disagreement"):
        runtime.verify_task(TASK_ID, evidence_refs=refs)
    reopened = open_runtime(tmp_path / "retained.jsonl")
    event = list(reopened.spine.replay("mission.appraised"))[0]
    assert event.payload["receipt"]["report"]["accepted"] is False
    assert event.payload["receipt"]["report"]["dissent"] == [LIMITATION, PIN_DISSENT]
    assert reopened.task_fabric.tasks()[TASK_ID] == "QUARANTINED"
    assert "NEEDS_FOUNDER_DECISION" in reopened.founder_inbox(mission()["mission_id"])
    with pytest.raises(TaskFabricError):
        reopened.dissolve(mission()["mission_id"], evidence_refs=(event.event_id,))


def test_direct_transition_cannot_bypass_or_suppress_appraiser(tmp_path):
    runtime, refs = submitted(tmp_path)
    with pytest.raises(TaskFabricError, match="protected appraisal"):
        runtime.task_fabric.transition(TASK_ID, "VERIFIED", actor=protected.IDENTITY,
            transition_key="bypass", assessment_refs=("fake",), dissent_preserved=True)
    verified = runtime.verify_task(TASK_ID, evidence_refs=refs)
    with pytest.raises(TaskFabricError, match="dissent"):
        runtime.task_fabric.transition(TASK_ID, "VERIFIED", actor=protected.IDENTITY,
            transition_key="suppress", assessment_refs=verified.assessment_refs, dissent_preserved=True)


def test_interrupted_appraiser_is_not_blindly_retried(tmp_path, monkeypatch):
    runtime, refs = submitted(tmp_path)
    def interrupted(*args, **kwargs):
        raise subprocess.TimeoutExpired("fixed-appraiser", 15)
    monkeypatch.setattr(protected.subprocess, "run", interrupted)
    with pytest.raises(MissionRuntimeError, match="no fallback"):
        runtime.verify_task(TASK_ID, evidence_refs=refs)
    reopened = open_runtime(tmp_path / "retained.jsonl")
    with pytest.raises(MissionRuntimeError):
        reopened.verify_task(TASK_ID, evidence_refs=refs)
    assert len(list(reopened.spine.replay("mission.appraisal.started"))) == 1
    assert not list(reopened.spine.replay("mission.appraised"))


def test_successful_appraisal_replay_after_real_process_exit(tmp_path):
    runtime, refs = submitted(tmp_path)
    ledger_path = str(tmp_path / "retained.jsonl")
    script = """
import os, sys
from tests.integration.test_protected_mission_appraisal import open_runtime, TASK_ID
r = open_runtime(sys.argv[1])
r.verify_task(TASK_ID, evidence_refs=(sys.argv[2],))
os._exit(75)
"""
    process = subprocess.run([sys.executable, "-c", script, ledger_path, refs[0]],
                             capture_output=True, text=True)
    assert process.returncode == 75, process.stderr
    reopened = open_runtime(ledger_path)
    verified = reopened.verify_task(TASK_ID, evidence_refs=refs)
    assert reopened.verify_task(TASK_ID, evidence_refs=refs) == verified
    reopened.close_task(TASK_ID)
    again = open_runtime(ledger_path)
    assert again.verify_task(TASK_ID, evidence_refs=refs) == verified
    assert len(list(again.spine.replay("mission.appraised"))) == 1
    assert len(list(again.spine.replay("mission.appraisal.started"))) == 1
    assert len(list(again.spine.replay("mission.result"))) == 1
    assert again.spine.ledger.verify_chain()[0]
    # Same ledger behind an old reader must fail, not append a competing history.
    with pytest.raises(protected.AppraisalRefused, match="stale"):
        runtime.verify_task(TASK_ID, evidence_refs=refs)


def test_policy_drift_after_submission_fails_closed(tmp_path, monkeypatch):
    runtime, refs = submitted(tmp_path)
    before = protected.policy()
    monkeypatch.setattr(protected, "policy", lambda: {**before, "version": "new"})
    with pytest.raises(MissionRuntimeError, match="stale"):
        runtime.verify_task(TASK_ID, evidence_refs=refs)
    assert runtime.task_fabric.tasks()[TASK_ID] == "QUARANTINED"


@pytest.mark.parametrize("kind,field", [
    ("mission.result", "result_digest"), ("mission.evidence.retained", "digest"),
])
def test_in_place_record_tampering_is_not_verified(tmp_path, kind, field):
    runtime, refs = submitted(tmp_path)
    for record in runtime.spine.ledger.records:
        event = record.payload
        if event.get("type") == kind:
            event["payload"][field] = "sha256:" + "f" * 64
            break
    else:
        pytest.fail("negative-control mutation did not reach a real retained event")
    assert not runtime.spine.ledger.verify_chain()[0]
    with pytest.raises(MissionRuntimeError, match="integrity"):
        runtime.verify_task(TASK_ID, evidence_refs=refs)
    assert runtime.task_fabric.tasks()[TASK_ID] != "VERIFIED"


def test_missing_appraisal_blocks_close_after_fabric_projection(tmp_path):
    runtime, refs = submitted(tmp_path)
    with pytest.raises(protected.AppraisalRefused, match="no protected appraisal"):
        runtime.close_task(TASK_ID)


def test_fixed_child_denies_write_after_appraisal(tmp_path):
    runtime, refs = submitted(tmp_path)
    envelope = runtime.task_fabric.envelope(TASK_ID)
    receipt = runtime.task_fabric.receipts(TASK_ID)[-1]
    request = protected._request(runtime.spine, mission(), envelope, receipt)
    target = tmp_path / "forbidden-child-output"
    script = """
import runpy, sys
runpy.run_path("verifier/appraisal_worker.py", run_name="__main__")
open(sys.argv[1], "w").write("must not exist")
"""
    proc = subprocess.run([sys.executable, "-B", "-c", script, str(target)],
        input=json.dumps(request), text=True, capture_output=True)
    assert proc.returncode != 0
    assert "appraiser is read-only" in proc.stderr
    assert not target.exists()
