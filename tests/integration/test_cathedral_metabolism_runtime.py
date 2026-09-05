"""Integration tests for the first composed mission metabolism.

These tests exercise canonical EventSpine and TaskFabric objects in simulation.
They do not claim a production runtime, cryptographic founder authentication or
Verified Durable Mission Closure.
"""

from __future__ import annotations

import copy

import pytest

from egregore import (
    CathedralMetabolismRuntime,
    FounderAuthenticationRequired,
    MissionRuntimeError,
    ResolutionCandidate,
    SignalEnvelope,
    StandingCognitionRuntime,
)
from egregore.contracts import Assessment, CandidateProposal
from egregore.resources import ResourceGovernor
from events.spine import EventSpine
from events.task_fabric import TaskFabric, TaskFabricError
from provenance.ledger import EvidenceLedger
from tests.unit.test_organizational_morphogenesis_contracts import valid_mission


CONSTITUTION = "sha256:" + "0" * 64
SOURCE = "spiffe://uniimente.internal/egregore/cathedral-metabolism"
WORKER = "spiffe://uniimente.internal/worker/phase4-test"
EVALUATOR = "spiffe://uniimente.internal/evaluator/phase4-test"
TASK_ID = "0f3d0f77-0e3f-4f08-9a1f-40e6a4c5b7d1"


def mission():
    value = copy.deepcopy(valid_mission())
    value["consequence_ceiling"] = "read_only"
    return value


def cognition_for(ledger):
    def propose(signals, context):
        signal = signals[0]
        return CandidateProposal.build(
            proposed_by="planner",
            objective="retain one bounded audit hypothesis",
            action_class="read_only_audit",
            requested_capability="opportunity.evaluate",
            target="internal://phase4",
            consequence_class="read_only",
            payload={"context_keys": sorted(context)},
            evidence_refs=("evidence:signal",),
            confidence=0.8,
            estimated_cost_usd=0.1,
            expected_outcome="typed internal result",
            source_signal_ids=(signal.signal_id,),
        )

    def assess(role, candidate, signals, context):
        return Assessment.build(
            role=role,
            candidate_id=candidate.candidate_id,
            score=0.8 if role == "guardian" else 0.7,
            confidence=0.8,
            objections=("static workflow remains the protected comparator",),
            veto=False,
            evidence_refs=("evidence:" + role,),
        )

    return StandingCognitionRuntime(
        ledger=ledger,
        proposers={"planner": propose},
        evaluators={
            "guardian": lambda c, s, x: assess("guardian", c, s, x),
            "treasury": lambda c, s, x: assess("treasury", c, s, x),
        },
        required_evaluators=("guardian", "treasury"),
        source="spiffe://uniimente.internal/egregore/standing-cognition-test",
    )


def direct_route() -> ResolutionCandidate:
    return ResolutionCandidate(
        candidate_id="capability:internal-audit",
        resolution_class="direct_capability",
        description="one existing read-only capability",
        available=True,
        execution_eligible=True,
        evidence_maturity="TESTED",
        expected_quality=0.95,
        estimated_cost_usd=0.1,
        coordination_units=0.1,
        founder_attention_minutes=0,
        reversible=True,
        reason="the direct capability is sufficient for this one-task mission",
        evidence_refs=("evidence:direct",),
    )


def build_runtime():
    ledger = EvidenceLedger(CONSTITUTION)
    spine = EventSpine(ledger)
    fabric = TaskFabric(spine, source_identity=SOURCE)
    cognition = cognition_for(ledger)
    runtime = CathedralMetabolismRuntime(
        spine=spine,
        task_fabric=fabric,
        cognition=cognition,
        source_identity=SOURCE,
    )
    return runtime, ledger, spine


def test_one_simulated_mission_crosses_the_canonical_seams_and_restarts():
    runtime, ledger, spine = build_runtime()
    current_mission = mission()

    admission = runtime.admit(
        current_mission,
        trigger_id="founder-trigger:phase4-test",
        founder_direction_ref="CMC-MANUAL-DIRECTION-002",
    )
    signal = SignalEnvelope.build(
        source="daleobanks:test",
        source_event_id="signal-001",
        observed_at="2026-09-05T00:00:00Z",
        payload={"kind": "opportunity", "instruction_status": "data_only"},
        evidence_refs=("evidence:source",),
        sensitivity="internal",
        trust_level="untrusted",
    )
    cycle = runtime.run_cognition(
        admission.mission_id,
        signal,
        trigger_id="cognition-trigger:phase4-test",
        resources=ResourceGovernor(
            max_model_calls=3,
            max_estimated_cost_usd=1.0,
        ),
        context={"mission": admission.mission_id},
    )
    assert cycle.execution_authority == "none"

    resolution = runtime.route(
        admission.mission_id,
        candidates=(direct_route(),),
        unresolved_reasons=(),
    )
    assert resolution.selected_candidate_id == "capability:internal-audit"

    task_id, created_receipts = runtime.create_task(
        admission.mission_id,
        task_id=TASK_ID,
        required_capability="opportunity.evaluate",
        objective="read and assess the frozen internal fixture",
    )
    assert task_id == TASK_ID
    assert [receipt.state for receipt in created_receipts] == [
        "CREATED",
        "ADMITTED",
        "QUEUED",
    ]

    lease = runtime.lease_task(
        task_id,
        capability_grant_ref="simulation:grant-not-issued",
        worker_identity=WORKER,
        lease_seconds=120,
    )
    runtime.start_task(
        task_id,
        worker_identity=WORKER,
        lease_id=lease.lease_id,
    )
    from tests.experiments.retained_appraisal_fixture import worker_result
    source = runtime.retain_task_sources(task_id)
    result = worker_result()
    submitted = runtime.submit_task(
        task_id,
        worker_identity=WORKER,
        lease_id=lease.lease_id,
        result=result,
        evidence_refs=(source.event_id,),
        tool_refs=("tool:read-only-inspection",),
    )

    # Object reconstruction only. Fresh-process durable restart has a separate test.
    restarted_fabric = TaskFabric(spine, source_identity=SOURCE)
    restarted = CathedralMetabolismRuntime(
        spine=spine,
        task_fabric=restarted_fabric,
        cognition=cognition_for(ledger),
        source_identity=SOURCE,
    )
    resumed = restarted.snapshot(admission.mission_id)
    assert resumed.task_states[task_id] == "SUBMITTED"

    duplicate = restarted.submit_task(
        task_id,
        worker_identity=WORKER,
        lease_id=lease.lease_id,
        result=result,
        evidence_refs=(source.event_id,),
        tool_refs=("tool:read-only-inspection",),
    )
    assert duplicate.receipt_id == submitted.receipt_id
    result_events = [
        event for event in spine.replay("mission.result")
        if event.payload.get("task_id") == task_id
    ]
    assert len(result_events) == 1

    verified = restarted.verify_task(
        task_id,
        evidence_refs=(source.event_id,),
    )
    assert verified is not None
    closed = restarted.close_task(task_id)
    assert closed.state == "CLOSED"

    closure = restarted.finalize(
        admission.mission_id,
        evidence_refs=(verified.assessment_refs[0],),
    )
    assert closure.payload["closure_status"] == "SIMULATED_UNVERIFIED"
    assert closure.payload["verified_durable_mission_closure"] is False

    dissolved = restarted.dissolve(
        admission.mission_id,
        evidence_refs=(verified.assessment_refs[0],),
    )
    assert dissolved.payload["resource_release_required"] is True
    assert restarted.snapshot(admission.mission_id).status == "DISSOLVED"
    assert restarted.execution_authority == "none"
    assert restarted.external_effects == 0
    assert ledger.verify_chain()[0] is True


def test_runtime_commands_and_actual_mode_fail_closed():
    runtime, _ledger, _spine = build_runtime()

    with pytest.raises(FounderAuthenticationRequired):
        runtime.command_surface.submit({"command": "continue"})

    with pytest.raises(FounderAuthenticationRequired):
        CathedralMetabolismRuntime(
            spine=runtime.spine,
            task_fabric=runtime.task_fabric,
            evidence_mode="ACTUAL",
            source_identity=SOURCE,
        )


def test_evaluator_disagreement_is_an_exception_and_blocks_dissolution():
    runtime, _ledger, _spine = build_runtime()
    admission = runtime.admit(
        mission(),
        trigger_id="founder-trigger:exception-test",
        founder_direction_ref="CMC-MANUAL-DIRECTION-002",
    )
    runtime.route(admission.mission_id, candidates=(direct_route(),))
    exception = runtime.record_exception(
        admission.mission_id,
        kind="manifest_pin_drift",
        details={"observed": "main", "declared": "older"},
        evidence_refs=("evidence:pin-drift",),
    )

    assert "NEEDS_FOUNDER_DECISION" in runtime.founder_inbox(admission.mission_id)
    assert exception.payload["requires_canonical_founder_authentication"] is True
    with pytest.raises(TaskFabricError):
        runtime.dissolve(
            admission.mission_id,
            evidence_refs=("evidence:exception",),
            open_obligation_refs=(exception.payload["exception_id"],),
        )


def test_persisted_route_replays_with_unresolved_reasons():
    runtime, ledger, _spine = build_runtime()
    admission = runtime.admit(
        mission(),
        trigger_id="founder-trigger:route-replay",
        founder_direction_ref="CMC-MANUAL-DIRECTION-002",
    )
    first = runtime.route(
        admission.mission_id,
        candidates=(direct_route(),),
        unresolved_reasons=("founder must review a source-pin discrepancy",),
    )
    shared_spine = EventSpine(ledger)
    restarted = CathedralMetabolismRuntime(
        spine=shared_spine,
        task_fabric=TaskFabric(shared_spine, source_identity=SOURCE),
        source_identity=SOURCE,
    )
    replayed = restarted._latest_resolution(admission.mission_id)
    assert replayed.digest == first.digest
