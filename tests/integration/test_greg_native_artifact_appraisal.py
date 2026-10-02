"""Fresh numerical reruns cannot launder an invalid original proof."""
from copy import deepcopy

import pytest

from greg.body import Body
from greg.cognition.contracts import digest
from greg.cognition.settlement import _valid_receipt, competence
from tests.greg_fixtures import drop, make_body, mission, signed
from tests.integration.test_greg_composition_appraisal import OPTIMIZATION


@pytest.mark.parametrize("capability,attack", [
    ("cognition.solve", "expression"), ("cognition.exact", "expression"),
    ("cognition.solve", "objective"), ("cognition.optimization", "objective"),
    ("cognition.solve", "assignment"), ("cognition.optimization", "assignment"),
    ("cognition.optimization", "constraint_omission"),
])
def test_original_numeric_source_and_certificate_must_survive_independent_appraisal(tmp_path, capability, attack):
    home, key, body_id, _ = make_body(tmp_path)
    params = ({"problem_id": "direct:proof", "operation": "calculate", "data": {"expression": "4+5"}}
              if attack == "expression" else deepcopy(OPTIMIZATION))
    field, expected = ("output.exact", "9") if attack == "expression" else ("output.solver_status", "OPTIMAL")
    spec = mission("m:direct-proof", checks=[{
        "check_id": "native", "description": "challenge the original numeric proof as well as its answer",
        "sensor": {"capability": capability, "target": "cognition:direct-proof", "params": params},
        "predicate": {"op": "equals", "field": field, "value": expected}}], strategies=[],
        capabilities=[capability], targets=("cognition:*",), ceiling="read_only")
    drop(home, signed(key, body_id, "MISSION", spec))
    with Body(home) as body:
        original = body.registry.adapters[capability]

        def attacked(params, ctx):
            output = original(params, ctx)
            if attack == "expression":
                output["proof_artifact"]["expression"] = "1+1"
            elif attack == "objective":
                output["proof_artifact"]["objective"]["sense"] = "max"
            elif attack == "constraint_omission":
                output["proof_artifact"]["constraints"] = []
            else:
                # Preserve objective/proof/output coherence so the original
                # source's feasibility condition is the decisive gate.
                output["output"]["solution"]["x"] = 0
                output["output"]["objective_value"] = 0
                output["proof_artifact"]["solution"]["x"] = 0
            output.pop("receipt_id")
            output["receipt_id"] = digest(output)
            assert _valid_receipt(output)  # structural validity alone is insufficient
            return output

        body.registry.adapters[capability] = attacked
        body.boot()
        assert body.tick()["missions"][0]["state"] == "ACHIEVED"
        appraisal = body.journal.replay("mission.appraised")[-1].payload
        assert appraisal["verdict"] == "REFUTED", appraisal
        assert appraisal["checks"]["world_reobserved"] is False
        assert any("retained source/proof/output checks refuted" in finding for finding in appraisal["findings"])
        assert body.journal.replay("cognition.settled") == [] and competence(body.journal) == {}
