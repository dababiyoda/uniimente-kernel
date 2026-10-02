"""P5 methods run only after signed laboratory attachment on the canonical Body."""
import pytest

from greg.body import Body
from greg.cognition.contracts import digest
from greg.cognition.settlement import _valid_receipt, competence
from tests.greg_fixtures import drop, make_body, mission, signed
from tests.unit.test_cognition_native_network_lp import FLOW, LP, PATH


def test_native_network_and_glop_signed_missions_survive_restart_and_detach(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    with Body(home) as body:
        for family in ("graph", "flow", "linear"):
            assert body.registry.state["cognition." + family] == "VERIFIED"
            body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": "cognition." + family}))
    for family, operation, data, field, expected in (("graph", "shortest_path", PATH, "output.cost", 3),
                                                  ("flow", "max_flow", FLOW, "output.value", 3),
                                                  ("linear", "linear_program", LP, "output.objective_value", 5)):
        params = {"problem_id": "native:" + family, "operation": operation, "data": data, "geometry": {"latency_limit": 10}}
        spec = mission("m:native-" + family, checks=[{"check_id": "native", "description": "bounded native certificate",
                       "sensor": {"capability": "cognition.solve", "target": "cognition:native", "params": params},
                       "predicate": {"op": "equals", "field": field, "value": expected}}], strategies=[],
                       capabilities=["cognition.solve"], targets=("cognition:*",), ceiling="read_only")
        drop(home, signed(key, body_id, "MISSION", spec))
    with Body(home) as body:
        body.boot()
        result = body.tick()
        assert {m["state"] for m in result["missions"]} == {"ACHIEVED"}
        appraisals = body.journal.replay("mission.appraised")
        assert len(appraisals) == 3 and all(e.payload["verdict"] == "VERIFIED" for e in appraisals), appraisals
        cognitive = [r.payload["result"].get("output") for r in body.ledger.by_type("receipt")]
        cognitive = [r for r in cognitive if isinstance(r, dict) and r.get("problem_id", "").startswith("native:")]
        assert {r["method"] for r in cognitive} == {"cognition.graph", "cognition.flow", "cognition.linear"}
        assert all(r["authority_created"] is False and r["evaluator_result"]["verdict"] == "STRUCTURALLY_VERIFIED" for r in cognitive)
        count = len(body.ledger.by_type("receipt"))
        body.apply(signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": "cognition.flow"}))
    with Body(home) as body:
        body.boot()
        body.tick()
        assert len(body.ledger.by_type("receipt")) == count
        assert body.registry.state["cognition.flow"] == "DETACHED"
        assert body.office.gate is not None


@pytest.mark.parametrize("attack", ["wrong_sign", "stationarity_residual"])
def test_native_appraisal_refutes_original_wide_bound_forgery_despite_correct_rerun(tmp_path, attack):
    home, key, body_id, _ = make_body(tmp_path)
    if attack == "wrong_sign":
        data = {"variables": {"x": [0, 1e9]}, "objective": {"coefficients": {"x": 1e-7}, "sense": "min"}}
        x, multiplier, objective = 1e9, 1e-7, 100
    else:
        data = {"variables": {"x": [-1e9, 0]}, "objective": {"coefficients": {"x": 1e-8}, "sense": "min"}}
        x, multiplier, objective = 0, 0, 0
    params = {"problem_id": "native:forged-lp", "operation": "linear_program", "data": data, "geometry": {"latency_limit": 10}}
    spec = mission("m:native-forged-lp", checks=[{
        "check_id": "native", "description": "original certificate must survive independent appraisal",
        "sensor": {"capability": "cognition.solve", "target": "cognition:native-lp", "params": params},
        "predicate": {"op": "equals", "field": "output.solver_status", "value": "OPTIMAL"}}], strategies=[],
        capabilities=["cognition.solve"], targets=("cognition:*",), ceiling="read_only")
    with Body(home) as body:
        body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": "cognition.linear"}))
    drop(home, signed(key, body_id, "MISSION", spec))
    with Body(home) as body:
        original = body.registry.adapters["cognition.solve"]
        def attacked(params, ctx):
            packet = original(params, ctx)
            packet["proof_artifact"]["claim"].update({"x": [x], "z_l": [0], "z_u": [multiplier]})
            packet["proof_artifact"].update({"bound": objective, "gap": 0})
            packet["output"].update({"solution": {"x": x}, "objective_value": objective})
            packet.pop("receipt_id")
            packet["receipt_id"] = digest(packet)
            assert _valid_receipt(packet)  # shape/rehashing cannot establish numerical truth
            return packet
        body.registry.adapters["cognition.solve"] = attacked
        body.boot()
        assert body.tick()["missions"][0]["state"] == "ACHIEVED"
        appraisal = body.journal.replay("mission.appraised")[-1].payload
        assert appraisal["verdict"] == "REFUTED", appraisal
        assert appraisal["checks"]["world_reobserved"] is False
        assert body.journal.replay("cognition.settled") == [] and competence(body.journal) == {}
