"""Outcome labels must retain empirical scope and authority refusal semantics."""
from copy import deepcopy

from greg import routing, sop
from greg.body import Body
from tests.greg_fixtures import drop, make_body, mission, signed


def test_real_numeric_appraisal_cannot_become_empirical_routing_credit(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    params = {"problem_id": "routing:scope", "operation": "calculate", "data": {"expression": "4+5"}}
    spec = mission("m:scope", checks=[{
        "check_id": "numeric", "description": "encoded exact calculation",
        "sensor": {"capability": "cognition.solve", "target": "cognition:scope", "params": params},
        "predicate": {"op": "equals", "field": "output.exact", "value": "9"}}],
        strategies=[], capabilities=["cognition.solve"], targets=("cognition:*",), ceiling="read_only")
    drop(home, signed(key, body_id, "MISSION", spec))
    with Body(home) as body:
        body.boot(); body.tick()
        appraisal = body.journal.replay("mission.appraised")[-1].payload
        assert appraisal["verdict"] == "VERIFIED" and appraisal["checks"]["world_reobserved"] is False
        # Explicit attribution fixture for the operational projection; the
        # actual result above came through a native sensor and separate worker.
        body.journal.record("mission.action", {"mission_id": "m:scope", "capability": "cognition.solve", "status": "DONE"})
        record = routing.track_record(body.journal)["cognition.solve"]
        assert record["verified"] == 0 and record["computationally_verified"] == 1
        from greg.cognition.settlement import measured_outcomes
        outcomes = measured_outcomes(body.journal)
        assert len(outcomes) == 1 and outcomes[0]["empirical_outcome"] is False
        assert "encoded computation" in outcomes[0]["evidence_tier"]
        foreign = deepcopy(appraisal)
        foreign["verdict"] = "REFUTED"
        foreign["checks"]["founder_signature_verified"] = False
        body.journal.record("mission.appraised", foreign, key="foreign-signature-fault")
        assert routing.track_record(body.journal)["cognition.solve"]["refuted"] == 0
        assert sop.compounding_metrics(body.journal)["verified_outcomes"] == 0


def test_appropriate_refusal_is_visible_without_reliability_penalty(tmp_path):
    home, _, _, _ = make_body(tmp_path)
    with Body(home) as body:
        body.journal.record("mission.action", {"mission_id": "m:refusal", "capability": "cognition.semantic",
                                               "status": "REFUSED", "reasons": ["POLICY_REFUSAL"]})
        row = routing.track_record(body.journal)["cognition.semantic"]
        assert row["refused"] == 1 and row["failed"] == 0
        assert routing.reliability(row) == routing.reliability(None)


def test_compounding_cannot_invent_zero_model_cost_from_missing_records(tmp_path):
    home, _, _, _ = make_body(tmp_path)
    with Body(home) as body:
        assert sop.compounding_metrics(body.journal)["model_calls_per_outcome"] is None
        body.journal.record("model.route", {"route": "ollama:test", "outcome": "refused"})
        body.ledger.append("receipt", {"result": {"output": {"receipts": [
            {"compute_cost": {"model_calls": 1}}, {"compute_cost": {"model_calls": 0}}
        ]}}})
        metrics = sop.compounding_metrics(body.journal)
        assert metrics["recorded_model_call_attempts"] == 2
        assert metrics["model_calls_per_outcome"] is None
        assert metrics["model_call_coverage"] == "partial retained observations; total unmeasured"


def test_explicit_reattachment_reconciles_failed_appraisal_once_without_duplicate_settlement(tmp_path):
    from greg.cognition.settlement import competence
    home, key, body_id, _ = make_body(tmp_path)
    params = {"problem_id": "routing:retry", "operation": "calculate", "data": {"expression": "4+5"}}
    spec = mission("m:retry", checks=[{
        "check_id": "numeric", "description": "retained computation",
        "sensor": {"capability": "cognition.solve", "target": "cognition:retry", "params": params},
        "predicate": {"op": "equals", "field": "output.exact", "value": "9"}}],
        strategies=[], capabilities=["cognition.solve"], targets=("cognition:*",), ceiling="read_only")
    with Body(home) as body:
        body.apply(signed(key, body_id, "MISSION", spec))
        body.boot()
        # Interrupt the canonical engine/closure boundary deterministically.
        assert body.engine.tick(body.clock())[0]["state"] == "ACHIEVED"
        body.apply(signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": "cognition.exact"}))
        body.tick()
        first = body.journal.replay("mission.appraised")[-1]
        assert first.payload["verdict"] == "REFUTED" and competence(body.journal) == {}
        receipts = len(body.ledger.by_type("receipt"))
    with Body(home) as body:
        body.boot(); body.tick()
        assert body.registry.state["cognition.exact"] == "DETACHED"
        assert len(body.journal.replay("mission.appraised")) == 1
        body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": "cognition.exact"}))
        body.tick()
        appraisals = body.journal.replay("mission.appraised")
        assert len(appraisals) == 2 and appraisals[0].event_id == first.event_id
        assert appraisals[-1].payload["verdict"] == "VERIFIED"
        assert appraisals[-1].payload["checks"]["world_reobserved"] is False
        assert len(body.ledger.by_type("receipt")) == receipts
        assert len(body.journal.replay("cognition.settled")) == 1
        body.tick()
        assert len(body.journal.replay("mission.appraised")) == 2
        assert len(body.journal.replay("cognition.settled")) == 1
