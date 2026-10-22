"""Real Gate pointers are projected into the bounded runtime, never self-created."""
from greg.body import Body
from greg.cognition.contracts import digest
from tests.greg_fixtures import drop, make_body, mission, signed


def test_cognition_budget_references_actual_signed_mission_grant_and_witness(tmp_path, monkeypatch):
    from greg.capabilities import BUILTINS
    manifest, adapter = BUILTINS["cognition.solve"]
    contexts = []
    def capture(params, ctx):
        contexts.append(ctx)
        return adapter(params, ctx)
    monkeypatch.setitem(BUILTINS, "cognition.solve", (manifest, capture))
    home, key, body_id, _ = make_body(tmp_path)
    params = {"problem_id": "budget:canonical", "operation": "calculate", "data": {"expression": "2+3"}}
    spec = mission("m:budget-canonical", checks=[{
        "check_id": "sum", "description": "native arithmetic", "sensor": {
            "capability": "cognition.solve", "target": "cognition:budget", "params": params},
        "predicate": {"op": "equals", "field": "output.exact", "value": "5"}}],
        strategies=[], capabilities=["cognition.solve"], targets=("cognition:*",), ceiling="read_only")
    drop(home, signed(key, body_id, "MISSION", spec))
    with Body(home) as body:
        body.boot()
        assert body.tick()["missions"][0]["state"] == "ACHIEVED"
        receipt = next(record.payload["result"]["output"] for record in body.ledger.by_type("receipt")
                       if record.payload["result"].get("output", {}).get("problem_id") == params["problem_id"])
        refs = receipt["authority_refs"]
        assert contexts
        for ctx in contexts:
            assert ctx.mission_id == spec["mission_id"] == ctx.cognition_budget.mission_id
            assert ctx.authority_ref == ctx.cognition_budget.authority_ref
            assert ctx.grant_id == ctx.cognition_budget.grant_id
            assert ctx.policy_version == body.office.compiled.constitution_version
        assert refs["live_grant"] is True and refs["new_authority"] is False
        assert refs["mission_id"] == spec["mission_id"] and refs["problem_id"] == params["problem_id"]
        assert refs["authority_ref"] == body.engine.book.missions[spec["mission_id"]].command_digest
        dispatch = next(record.payload for record in body.ledger.by_type("grant_dispatch")
                        if record.payload["grant_id"] == refs["grant_id"])
        witness = next(record.payload for record in body.ledger.by_type("witness")
                       if record.payload["witness_id"] == refs["witness_id"])
        assert dispatch["proposal_id"] == refs["proposal_id"]
        assert dispatch["witness_id"] == refs["witness_id"]
        assert dispatch["effect_digest"] == refs["dispatch_effect_digest"]
        assert witness["grant_id"] == refs["grant_id"]
        assert refs["grant_digest"] == digest(body.office.grants._grants[refs["grant_id"]])
        plan = receipt["compute_cost"]["budget_plan"]
        assert plan["money_ceiling_usd"] == 0 and plan["mandatory_verification_invoked"] is True
        assert body.journal.replay("mission.appraised")[-1].payload["verdict"] == "VERIFIED"
