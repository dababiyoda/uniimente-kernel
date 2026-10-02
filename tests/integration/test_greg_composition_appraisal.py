"""Heterogeneous canonical composition, scoped artifact appraisal and attacks."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from greg.appraisal import _revalidate_composition
from greg.body import Body
from greg.capabilities import BUILTINS, InvocationContext
from greg.cognition.contracts import digest
from greg.cognition.cortex import compose
from greg.cognition.settlement import competence
from greg.cognition.verification import metaconsensus
from provenance.commit_witness import sha256_obj
from tests.greg_fixtures import drop, make_body, mission, signed
from tests.unit.test_greg_semantic_appraisal import fixture_semantic, semantic_params


OPTIMIZATION = {"problem_id": "subclaim:allocation", "operation": "optimize", "data": {
    "variables": {"x": [0, 8]}, "constraints": [{"coefficients": {"x": 1}, "op": ">=", "rhs": 3}],
    "objective": {"coefficients": {"x": 1}, "sense": "min"}}}
ESTIMATION = {"problem_id": "subclaim:scenario", "operation": "estimate", "data": {
    "factors": [{"name": "count", "low": 2, "central": 3, "high": 4, "units": {"items": 1}}],
    "expected_units": {"items": 1}}}


def request():
    return {"requests": [semantic_params(), deepcopy(OPTIMIZATION), deepcopy(ESTIMATION)]}


def check_for(params):
    return {"check_id": "scoped-allocation", "description": "independently check allocation and every composed subclaim",
            "sensor": {"capability": "cognition.compose", "target": "cognition:bounded-plan", "params": params},
            "predicate": {"op": "equals", "field": "receipts.1.output.objective_value", "value": 3}}


def refresh_nested_identity(output, index):
    row = output["receipts"][index]
    row.pop("receipt_id", None)
    row["receipt_id"] = digest(row)
    output["metaconsensus"] = metaconsensus(output["receipts"])


def submit(home, key, body_id, params, *, marker_only=False):
    check = check_for(params)
    if marker_only:
        check["predicate"] = {"op": "equals", "field": "metaconsensus.state", "value": "RECOMMENDATION_ONLY"}
    spec = mission("m:heterogeneous-plan", checks=[check], strategies=[],
                   capabilities=["cognition.compose"], targets=("cognition:*",), ceiling="read_only")
    drop(home, signed(key, body_id, "MISSION", spec))
    return spec


def test_real_body_heterogeneous_composition_checks_each_artifact_and_preserves_scope(tmp_path, monkeypatch):
    # The semantic reply is explicitly a fixture; CP-SAT/estimation, Kernel
    # witness and separate-process appraisal execute real implementation paths.
    monkeypatch.setattr("greg.cognition.cortex._semantic", fixture_semantic)
    home, key, body_id, _ = make_body(tmp_path)
    spec = submit(home, key, body_id, request())
    with Body(home) as body:
        body.boot()
        assert body.tick()["missions"][0]["state"] == "ACHIEVED"
        appraisal = body.journal.replay("mission.appraised")[-1].payload
        assert appraisal["verdict"] == "VERIFIED", appraisal["findings"]
        assert appraisal["checks"]["world_reobserved"] is False
        assert appraisal["checks"]["applicable_observations_revalidated"] is True
        scope = appraisal["composition_artifact_verification"][0]
        assert scope["verified"] and len(scope["components"]) == 3
        assert [part["problem_id"] for part in scope["components"]] == [p["problem_id"] for p in request()["requests"]]
        assert all(part["verified"] and part["model_reexecuted"] is False for part in scope["components"])
        assert scope["components"][1]["artifact_verification"]["checks"]["integer_domain"]
        assert scope["components"][2]["artifact_verification"]["checks"]["independent_products"]
        assert scope["reconciled_state"] == "RECOMMENDATION_ONLY"
        assert scope["outcome_credit"] is False and "no composition utility/net lift" in scope["scope"]
        assert competence(body.journal) == {} and body.journal.replay("cognition.settled") == []
        assert body.appraise(spec["mission_id"])["verdict"] == "VERIFIED"


@pytest.mark.parametrize("attack", ["source", "assignment", "proof", "swap_subclaims", "omit_subclaim", "reconciliation"])
def test_forged_nested_artifacts_do_not_pass_a_real_body_closure(tmp_path, monkeypatch, attack):
    monkeypatch.setattr("greg.cognition.cortex._semantic", fixture_semantic)
    home, key, body_id, _ = make_body(tmp_path)
    submit(home, key, body_id, request(), marker_only=attack == "assignment")
    with Body(home) as body:
        original_adapter = body.registry.adapters["cognition.compose"]
        def attacked(params, ctx):
            output = original_adapter(params, ctx)
            if attack == "source":
                output["receipts"][0]["proof_artifact"]["sources"][0]["digest"] = "sha256:" + "0" * 64
                refresh_nested_identity(output, 0)
            elif attack == "assignment":
                row = output["receipts"][1]
                # The marker-only engine predicate still passes. Keep the
                # objective consistent so only independent feasibility catches
                # the missing material constraint.
                row["output"]["solution"]["x"] = 0
                row["output"]["objective_value"] = 0
                row["proof_artifact"]["solution"]["x"] = 0
                refresh_nested_identity(output, 1)
            elif attack == "proof":
                output["receipts"][1]["proof_artifact"]["objective"]["sense"] = "max"
                refresh_nested_identity(output, 1)
            elif attack == "swap_subclaims":
                output["receipts"][0], output["receipts"][2] = output["receipts"][2], output["receipts"][0]
                output["metaconsensus"] = metaconsensus(output["receipts"])
            elif attack == "omit_subclaim":
                output["receipts"].pop(2)
                output["metaconsensus"] = metaconsensus(output["receipts"])
            else:
                output["metaconsensus"]["dissent"] = []
            return output
        body.registry.adapters["cognition.compose"] = attacked
        body.boot()
        assert body.tick()["missions"][0]["state"] == "ACHIEVED"
        appraisal = body.journal.replay("mission.appraised")[-1].payload
        assert appraisal["verdict"] == "REFUTED", appraisal
        assert appraisal["checks"]["world_reobserved"] is False
        assert not appraisal["checks"]["applicable_observations_revalidated"]
        assert appraisal["findings"]
        assert competence(body.journal) == {} and body.journal.replay("cognition.settled") == []


def test_unknown_and_nonidentification_are_preserved_by_composition_snapshot_appraisal(tmp_path):
    params = {"requests": [
        {"problem_id": "subclaim:unknown", "operation": "constraints", "geometry": {"compute_limit": 1},
         "data": deepcopy(OPTIMIZATION["data"])},
        {"problem_id": "subclaim:unidentified", "operation": "treatment_effect",
         "data": {"design": "observational", "treated": [2, 3], "control": [0, 1], "synthetic": True}}]}
    manifest = BUILTINS["cognition.compose"][0]
    context = InvocationContext(workspace=tmp_path, read_roots=(), secrets=None, manifest=manifest, target="cognition:bounded-plan")
    output = compose(params, context)
    assert [r["abstention_state"] for r in output["receipts"]] == ["UNKNOWN", "UNIDENTIFIED"]
    assert output["metaconsensus"]["state"] == "ABSTAIN"
    check = check_for(params)
    receipt = SimpleNamespace(payload={"witness_id": "w1", "result": {"output": output}})
    witness = SimpleNamespace(payload={"witness_id": "w1", "capability": "cognition.compose", "target": "cognition:bounded-plan",
        "constitution_hash": "test-constitution", "evidence_refs": ["signed-mission"],
        "payload_hash": sha256_obj({"capability": "cognition.compose", "params": params, "manifest_digest": manifest.digest()})})
    journal = SimpleNamespace(ledger=SimpleNamespace(constitution_hash="test-constitution", by_type=lambda kind: [witness]))
    scope = _revalidate_composition(check, receipt, journal, "signed-mission")
    assert scope["verified"] and scope["reconciled_state"] == "ABSTAIN"
    assert [part["abstention_state"] for part in scope["components"]] == ["UNKNOWN", "UNIDENTIFIED"]
    assert all(part["dissent"] for part in scope["components"])
    assert scope["outcome_credit"] is False
