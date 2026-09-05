"""CMC-002: actual unit/subprocess tests; all mission episodes are SIMULATION."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from egregore.mission_commands import refuse_runtime_command
from events.task_fabric import AuthorityViolation, BudgetExceeded, TaskFabricError
from governance.manual_direction import validate_direction_record
from omnimorph.organization_compiler import content_digest
from routing.mission_resolution import FAMILIES, MissionResolutionRouter, ResolutionFacts
from tests.experiments.cathedral_metabolism_probe import (
    ROOT, TASK_ID, LEASE_ID, WORKER, COORDINATOR, EVALUATOR,
    Simulation, open_simulation, load_fixture, snapshot_sources,
)
from verifier.mission_audit import appraise


def record():
    return json.loads((ROOT / "docs/collaboration/FOUNDER-DIRECTION-CMC-SCOPE-002.json").read_text())


def command(sim):
    return {"evidence_mode": "SYNTHETIC_TEST_FIXTURE", "decision": "retain_pins_close_audit",
        "mission_digest": content_digest(sim.mission),
        "exception_digest": sim.data("AWAITING_DIRECTION")["exception_digest"],
        "source_text": "SYNTHETIC FIXTURE ONLY; not a founder message or authorization."}


def process(directory, *args, expected=0):
    result = subprocess.run([sys.executable, "-m", "tests.experiments.cathedral_metabolism_probe",
        "--simulation-only", "--state-dir", str(directory), *args], cwd=ROOT,
        capture_output=True, text=True, timeout=30)
    assert result.returncode == expected, result.stdout + result.stderr
    return result


def test_record_is_content_bound_and_is_not_authentication():
    r = validate_direction_record(record())
    assert r["runtime_execution_authorized"] is False
    assert r["source_timestamp"] is None
    assert r["cryptographic_founder_authentication"] is False
    assert "it may not directly authorize runtime execution" in r["source_text"]


@pytest.mark.parametrize("field,value", [
    ("runtime_execution_authorized", True), ("authority_created", 1),
    ("cryptographic_founder_authentication", True), ("scope", "runtime"),
    ("signature", "claimed-cryptographic-proof"), ("source_text", "altered"),
    ("source_timestamp", "2026-09-05T00:00:00Z"),
])
def test_record_rejects_forgery_unknown_fields_or_scope_expansion(field, value):
    r = record()
    r[field] = value
    with pytest.raises(Exception):
        validate_direction_record(r)


@pytest.mark.parametrize("input", [None, {}, {"authorized_by": "Alfonso Lopez"},
    {"signature": "claimed-valid"}, {"authenticated": True}, {"action": "continue"}])
def test_runtime_boundary_refuses_every_command(input):
    with pytest.raises(AuthorityViolation, match="NEEDS_FOUNDER_DECISION"):
        refuse_runtime_command(input)


def test_even_valid_manual_record_cannot_authorize_runtime():
    r = validate_direction_record(record())
    with pytest.raises(AuthorityViolation):
        refuse_runtime_command(r)


def test_router_keeps_eight_families_and_subordinate_compiler():
    result = MissionResolutionRouter().route(load_fixture("mission.json"), ResolutionFacts())
    assert [c["family"] for c in result["comparisons"]] == list(FAMILIES)
    assert result["selected_family"] == "direct_existing_capability"
    assert result["authority_created"] == 0 and result["execution_authority"] == "none"
    assert result["organization_decision"]["recommendation"]["automatic_instantiation"] is False
    assert result["digest"] == content_digest(result, excluding=("digest",))


@pytest.mark.parametrize("changes,expected", [
    ({"goal_pending": False}, "no_action_wait_refusal"),
    ({"human_direction_required": True}, "human_escalation"),
    ({"direct_capability_available": False}, "single_model_or_tool"),
    ({"direct_capability_available": False, "single_tool_available": False}, "human_escalation"),
    ({"direct_capability_available": False, "matching_workflow_available": True}, "existing_workflow"),
])
def test_material_route_changes(changes, expected):
    assert MissionResolutionRouter().route(load_fixture("mission.json"), ResolutionFacts(**changes))["selected_family"] == expected


def test_multi_step_prefers_static_and_budget_pressure_refuses():
    mission = load_fixture("mission.json")
    mission["problem_geometry"]["expected_task_volume"] = 4
    assert MissionResolutionRouter().route(mission, ResolutionFacts())["selected_family"] == "static_durable_workflow"
    mission["resource_envelope"]["model_call_ceiling"] = 0
    assert MissionResolutionRouter().route(mission, ResolutionFacts())["selected_family"] == "no_action_wait_refusal"


def test_unknown_mission_or_fact_field_refused():
    mission = load_fixture("mission.json")
    mission["allow_runtime"] = True
    with pytest.raises(ValueError):
        MissionResolutionRouter().route(mission, ResolutionFacts())
    with pytest.raises(TypeError):
        ResolutionFacts(unknown=True)
    with pytest.raises(ValueError):
        ResolutionFacts(goal_pending="yes")


@pytest.mark.parametrize("scenario", ["direct", "static"])
def test_abrupt_process_exit_restart_no_redispatch_pause_and_synthetic_close(tmp_path, scenario):
    process(tmp_path, "--scenario", scenario, "--interrupt-after-submit", expected=75)
    with open_simulation(tmp_path) as sim:
        assert sim.phase == "ROUTED"
        assert sim.fabric.tasks()[TASK_ID] == "SUBMITTED"
        assert sim.summary()["audit_invocations"] == 1
    resumed = json.loads(process(tmp_path, "--scenario", scenario).stdout)
    assert resumed["phase"] == "AWAITING_DIRECTION"
    assert resumed["audit_invocations"] == 1
    before = (tmp_path / "ledger.jsonl").read_bytes()
    process(tmp_path, "--scenario", scenario)
    assert (tmp_path / "ledger.jsonl").read_bytes() == before
    closed = json.loads(process(tmp_path, "--scenario", scenario, "--synthetic-continue").stdout)
    assert closed["phase"] == "CLOSED"
    assert closed["actual_mission_closures"] == 0 and closed["authenticated_founder_commands"] == 0
    assert closed["audit_invocations"] == 1 and closed["ledger_records"] <= 100
    sealed = (tmp_path / "ledger.jsonl").read_bytes()
    process(tmp_path, "--scenario", scenario, "--synthetic-continue")
    assert (tmp_path / "ledger.jsonl").read_bytes() == sealed


def test_hypotheses_dissent_lineage_and_dissolution(tmp_path):
    with open_simulation(tmp_path) as sim:
        sim.admit()
        sim.advance()
        cycle = sim.data("COGNIZED")["cycle"]
        assert len({c["payload"]["hypothesis"] for c in cycle["candidates"]}) == 2
        assert all(a["objections"] for a in cycle["assessments"])
        assert sim.data("EVALUATED")["assessment"]["dissent"]
        ready, reasons = sim.fabric.dissolution_readiness(sim.mission["mission_id"],
            open_obligation_refs=(sim.data("AWAITING_DIRECTION")["exception_digest"],))
        assert not ready and "mission has open obligations" in reasons
        sim.synthetic_continue(command(sim))
        assert sim.spine.ledger.verify_chain()[0]
        assert sim.data("CLOSED")["closure_receipt"]["founder_accepted"] is False
        assert sim.fabric.dissolution_readiness(sim.mission["mission_id"])[0]


def test_manual_direction_and_stale_synthetic_command_cannot_close(tmp_path):
    with open_simulation(tmp_path) as sim:
        sim.admit()
        sim.advance()
        for bad in [record(), {**command(sim), "exception_digest": "sha256:" + "0" * 64},
                    {**command(sim), "mission_digest": "sha256:" + "0" * 64},
                    {**command(sim), "decision": "activate_runtime"},
                    {**command(sim), "authority": "Alfonso"}]:
            with pytest.raises(ValueError):
                sim.synthetic_continue(bad)
            assert sim.phase == "AWAITING_DIRECTION"


def test_poison_output_is_not_self_certifying(tmp_path, monkeypatch):
    with open_simulation(tmp_path) as sim:
        sim.admit()
        good = sim.audit()
        assert appraise(snapshot_sources(), good)["accepted"]
        poisoned = {**good, "actual_organ_execution": True}
        monkeypatch.setattr(sim, "audit", lambda: poisoned)
        with pytest.raises(ValueError, match="independent evaluation failed"):
            sim.advance()
        assert sim.fabric.tasks()[TASK_ID] == "QUARANTINED"
        assert sim.phase != "CLOSED"


def test_missing_corrupt_or_extra_evidence_refused(tmp_path):
    with open_simulation(tmp_path) as sim:
        sim.admit()
        result = sim.audit()
        assert not appraise(snapshot_sources(), {**result, "override": True})["accepted"]
        snapshot = snapshot_sources()
        snapshot["source_texts"].pop(next(iter(snapshot["source_texts"])))
        assert not appraise(snapshot, result)["accepted"]


def test_evaluator_cannot_be_injected_or_bypassed(tmp_path):
    with open_simulation(tmp_path) as sim:
        with pytest.raises(TypeError):
            Simulation(sim.spine, evaluator=lambda: True)
        sim.admit()
        sim.cognize()
        sim.route()
        sim.execute()
        for actor in [WORKER, COORDINATOR]:
            with pytest.raises(AuthorityViolation):
                sim.fabric.transition(TASK_ID, "VERIFIED", actor=actor, transition_key="bad-verify",
                    assessment_refs=("forged",), dissent_preserved=True)
        with pytest.raises(TaskFabricError):
            sim.fabric.transition(TASK_ID, "VERIFIED", actor=EVALUATOR, transition_key="no-dissent",
                assessment_refs=("forged",), dissent_preserved=False)
        with pytest.raises(ValueError):
            sim.emit("CLOSED", {"learning": {}, "closure_receipt": {}})


def test_duplicate_trigger_and_conflicting_replay(tmp_path):
    with open_simulation(tmp_path) as sim:
        sim.admit()
        before = sim.spine.ledger.head
        sim.admit()
        assert sim.spine.ledger.head == before
        with pytest.raises(ValueError):
            sim.admit("static")
        with pytest.raises(ValueError):
            sim.admit(trigger="stale-other-trigger")


def test_corrupt_ledger_fails_closed(tmp_path):
    process(tmp_path)
    ledger = tmp_path / "ledger.jsonl"
    # Deliberate isolated test corruption, never alteration of retained evidence.
    raw = ledger.read_text()
    ledger.write_text(raw.replace("Declared route only", "FORGED route claim", 1))
    with pytest.raises(ValueError):
        with open_simulation(tmp_path):
            pass


def test_single_writer_lock(tmp_path):
    with open_simulation(tmp_path):
        result = subprocess.run([sys.executable, "-m", "tests.experiments.cathedral_metabolism_probe",
            "--simulation-only", "--state-dir", str(tmp_path)], cwd=ROOT,
            capture_output=True, text=True, timeout=30)
        assert result.returncode != 0 and "BlockingIOError" in result.stderr


def test_manual_composition_requires_more_harness_actions(tmp_path):
    with open_simulation(tmp_path / "manual") as sim:
        sim.admit()
        calls = 0
        while sim.phase != "AWAITING_DIRECTION":
            sim.advance(one_step=True)
            calls += 1
        manual = sim.data("EVALUATED")["assessment"]
    with open_simulation(tmp_path / "automatic") as sim:
        sim.admit()
        sim.advance()
        assert sim.data("EVALUATED")["assessment"] == manual
        assert calls == 5  # harness actions, NOT measured human time saved


@pytest.mark.parametrize("imports", [
    "from omnimorph.organization_compiler import OrganizationCompiler; from foundry import FoundryPipeline",
    "from foundry import FoundryPipeline; from omnimorph.organization_compiler import OrganizationCompiler",
])
def test_fresh_process_import_order(imports):
    result = subprocess.run([sys.executable, "-c", imports], cwd=ROOT,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
