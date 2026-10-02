"""Original proposal packets are challenged independently of new answers.

The body/witness/appraiser are real; semantic extraction is an explicit fixture.
No test establishes factual truth, participant benefit or founder-device use.
"""
import pytest

from greg.body import Body
from greg.cognition.contracts import digest
from greg.cognition.settlement import _valid_receipt
from tests.greg_fixtures import drop, make_body, mission, signed
from tests.integration.test_greg_composition_appraisal import request as composition_request, refresh_nested_identity
from tests.unit.test_cognition_advantage_review import review
from tests.unit.test_greg_semantic_appraisal import fixture_semantic, semantic_params


PATHS = ("generic", "numeric", "semantic", "composed_numeric", "composed_semantic")


def signed_check(path, source_ref):
    proposal = review([source_ref])
    if path.startswith("composed_"):
        params = composition_request()
        index = 1 if path == "composed_numeric" else 0
        params["requests"][index]["proposal_review"] = proposal
        params["requests"][index]["geometry"] = {"latency_limit": 10}
        cap, field, expected = "cognition.compose", "receipts.1.output.objective_value", 3
    else:
        index = None
        params = semantic_params() if path == "semantic" else {
            "problem_id": "appraisal:original-review", "operation": "calculate", "data": {"expression": "4+5"}}
        params.update(proposal_review=proposal, geometry={"latency_limit": 10})
        cap = {"generic": "cognition.solve", "numeric": "cognition.exact", "semantic": "cognition.semantic"}[path]
        field, expected = ("output.claims.0.text", params["data"]["sources"][0]["text"]) if path == "semantic" else ("output.exact", "9")
    return {"check_id": "retained-review", "description": "native result plus original signed inert proposal",
            "sensor": {"capability": cap, "target": "cognition:original-review", "params": params},
            "predicate": {"op": "equals", "field": field, "value": expected}}, index


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("attack", (None, "option_benefit", "custody", "proposal"))
def test_canonical_appraisal_binds_original_review_not_a_recomputed_replacement(tmp_path, monkeypatch, path, attack):
    monkeypatch.setattr("greg.cognition.cortex._semantic", fixture_semantic)
    home, key, body_id, _ = make_body(tmp_path)
    with Body(home) as body:
        source = body.journal.record("review.source", {"observation": "supplied bounded test record"}, sensitivity="restricted")
        source_ref = body.journal.event_hash(source.event_id)
        check, nested_index = signed_check(path, source_ref)
        cap = check["sensor"]["capability"]
        spec = mission("m:original-review", checks=[check], strategies=[], capabilities=[cap],
                       targets=("cognition:*",), ceiling="read_only")
        drop(home, signed(key, body_id, "MISSION", spec))
        if attack is not None:
            original = body.registry.adapters[cap]

            def attacked(params, ctx):
                output = original(params, ctx)
                retained = output if nested_index is None else output["receipts"][nested_index]
                assert _valid_receipt(retained)
                if attack == "option_benefit":
                    retained["advantage_case"]["options"][0]["benefit_range"] = [100000, 100001]
                elif attack == "custody":
                    retained["selective_disclosure"]["observations"][0]["sequence"] += 100
                else:
                    retained["advantage_case"]["desired_outcome"] = "a substituted consequential objective"
                retained.pop("receipt_id")
                retained["receipt_id"] = digest(retained)
                # These attacks pass the structural schema and the native
                # answer predicate. Only original input/custody correspondence
                # can challenge them; a fresh correct answer cannot do that.
                assert _valid_receipt(retained)
                if nested_index is not None:
                    refresh_nested_identity(output, nested_index)
                return output

            body.registry.adapters[cap] = attacked
        body.boot()
        assert body.tick()["missions"][0]["state"] == "ACHIEVED"
        appraisal = body.journal.replay("mission.appraised")[-1].payload
        assert appraisal["verdict"] == ("VERIFIED" if attack is None else "REFUTED"), appraisal
        if attack is not None:
            expected = {"option_benefit": "substituted scenario inputs", "custody": "custody differs", "proposal": "substituted a material source requirement"}[attack]
            assert any(expected in finding for finding in appraisal["findings"]), appraisal
            assert not appraisal["checks"]["world_reobserved"]
            assert body.journal.replay("cognition.settled") == []
        elif path == "semantic" or path.startswith("composed_"):
            assert not appraisal["checks"]["world_reobserved"]
            assert appraisal["checks"]["applicable_observations_revalidated"]
            assert body.journal.replay("cognition.settled") == []
        else:
            assert not appraisal["checks"]["world_reobserved"]
            assert appraisal["checks"]["applicable_observations_revalidated"]
