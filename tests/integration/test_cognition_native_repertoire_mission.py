"""Native repertoire is attached by signed laboratory commands, then computed by GREG."""
from copy import deepcopy

import pytest

from greg.body import Body, status
from greg.cognition.contracts import digest
from greg.cognition.settlement import _valid_receipt, competence
from tests.greg_fixtures import drop, make_body, mission, signed
from tests.unit.test_cognition_native_repertoire import CASES


@pytest.mark.parametrize("family,operation,data", CASES[:9])
def test_native_method_runs_through_signed_body_and_revocation_survives_restart(tmp_path, family, operation, data):
    home, key, body_id, _ = make_body(tmp_path)
    capability = "cognition." + family
    params = {"problem_id": "native:repertoire:" + family, "operation": operation, "data": data,
              "geometry": {"latency_limit": 10, "compute_limit": 100000}}
    spec = mission("m:repertoire-" + family, checks=[{
        "check_id": "encoded", "description": "independently checked bounded computation, no world truth",
        "sensor": {"capability": capability, "target": "cognition:repertoire", "params": params},
        "predicate": {"op": "equals", "field": "evaluator_result.verdict", "value": "STRUCTURALLY_VERIFIED"}}],
        strategies=[], capabilities=[capability], targets=("cognition:*",), ceiling="read_only")
    with Body(home) as body:
        assert body.registry.state[capability] == "VERIFIED"
        body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": capability}))
    drop(home, signed(key, body_id, "MISSION", spec))
    with Body(home) as body:
        body.boot()
        assert body.tick()["missions"][0]["state"] == "ACHIEVED"
        appraisal = body.journal.replay("mission.appraised")[-1].payload
        assert appraisal["verdict"] == "VERIFIED", appraisal
        assert appraisal["checks"]["world_reobserved"] is False
        assert appraisal["checks"]["applicable_observations_revalidated"] is True
        receipts = [row.payload["result"]["output"] for row in body.ledger.by_type("receipt")]
        original = next(row for row in receipts if isinstance(row, dict) and row.get("problem_id") == params["problem_id"])
        assert original["authority_created"] is False and original["empirical_validity"] == "WORLD_UNVERIFIED"
        assert original["method"] == capability and original["method_version"] == "0.3.0"
        assert original["evaluator_result"]["execution_contract"].startswith("separate network-denied")
        count = len(body.ledger.by_type("receipt"))
        body.apply(signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": capability}))
    with Body(home) as body:
        body.boot(); body.tick()
        assert body.registry.state[capability] == "DETACHED"
        assert len(body.ledger.by_type("receipt")) == count
        assert next(row for row in status(home)["capabilities"] if row["capability_id"] == capability)["state"] == "DETACHED"


@pytest.mark.parametrize("family,operation,data", [CASES[0], CASES[6]])
def test_original_source_bound_forgery_cannot_settle_when_fresh_solver_is_correct(tmp_path, family, operation, data):
    home, key, body_id, _ = make_body(tmp_path)
    capability = "cognition." + family
    params = {"problem_id": "native:forged:" + family, "operation": operation, "data": data,
              "geometry": {"latency_limit": 10, "compute_limit": 100000}}
    spec = mission("m:forged-" + family, checks=[{
        "check_id": "encoded", "description": "original proof must survive challenge",
        "sensor": {"capability": capability, "target": "cognition:forged", "params": params},
        "predicate": {"op": "equals", "field": "evaluator_result.verdict", "value": "STRUCTURALLY_VERIFIED"}}],
        strategies=[], capabilities=[capability], targets=("cognition:*",), ceiling="read_only")
    with Body(home) as body:
        body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": capability}))
    drop(home, signed(key, body_id, "MISSION", spec))
    with Body(home) as body:
        real = body.registry.adapters[capability]
        def forge(params, ctx):
            packet = deepcopy(real(params, ctx))
            if family == "probabilistic":
                packet["output"]["mean"] = packet["proof_artifact"]["posterior"]["mean"] = .99
            else:
                packet["output"]["values"]["s"] = packet["proof_artifact"]["value_trace"][-1]["s"] = 100
            packet.pop("receipt_id")
            packet["receipt_id"] = digest(packet)
            assert _valid_receipt(packet)  # shape and digest do not establish its claim
            return packet
        body.registry.adapters[capability] = forge
        body.boot()
        assert body.tick()["missions"][0]["state"] == "ACHIEVED"
        appraisal = body.journal.replay("mission.appraised")[-1].payload
        assert appraisal["verdict"] == "REFUTED", appraisal
        assert appraisal["checks"]["world_reobserved"] is False
        assert body.journal.replay("cognition.settled") == [] and competence(body.journal) == {}


@pytest.mark.parametrize("forged", [False, True])
def test_polynomial_real_root_certificate_runs_in_actual_body_and_original_omission_refutes(tmp_path, forged):
    home, key, body_id, _ = make_body(tmp_path)
    params = {"problem_id": "native:polynomial", "operation": "polynomial", "data": {"polynomial": [-2, 0, 1]},
              "geometry": {"latency_limit": 10, "compute_limit": 100000}}
    spec = mission("m:polynomial-roots", checks=[{
        "check_id": "encoded", "description": "all real roots of the supplied polynomial are isolated",
        "sensor": {"capability": "cognition.exact", "target": "cognition:roots", "params": params},
        "predicate": {"op": "equals", "field": "evaluator_result.verdict", "value": "STRUCTURALLY_VERIFIED"}}],
        strategies=[], capabilities=["cognition.exact"], targets=("cognition:*",), ceiling="read_only")
    drop(home, signed(key, body_id, "MISSION", spec))
    with Body(home) as body:
        if forged:
            real = body.registry.adapters["cognition.exact"]
            def omit(params, ctx):
                packet = deepcopy(real(params, ctx))
                packet["proof_artifact"]["isolated_real_roots"].pop()
                packet["output"]["real_roots"].pop()
                packet["proof_artifact"]["result"] = deepcopy(packet["output"])
                packet.pop("receipt_id"); packet["receipt_id"] = digest(packet)
                assert _valid_receipt(packet)
                return packet
            body.registry.adapters["cognition.exact"] = omit
        body.boot()
        assert body.tick()["missions"][0]["state"] == "ACHIEVED"
        appraisal = body.journal.replay("mission.appraised")[-1].payload
        assert appraisal["verdict"] == ("REFUTED" if forged else "VERIFIED"), appraisal
        assert appraisal["checks"]["world_reobserved"] is False
        if forged:
            assert body.journal.replay("cognition.settled") == []
