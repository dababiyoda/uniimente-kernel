"""Cognition through signed missions, the real Gate, retained receipts and restart."""
from greg.body import Body
from greg.cognition.settlement import competence
from tests.greg_fixtures import drop, make_body, mission, signed


def test_cognition_is_durable_receipted_and_reobserved_on_the_existing_body(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    params = {"problem_id": "real:numeric", "operation": "calculate", "data": {"expression": "0.1+0.2"}}
    spec = mission("m:cognition", checks=[{
        "check_id": "exact", "description": "independently checked exact arithmetic",
        "sensor": {"capability": "cognition.solve", "target": "cognition:arithmetic", "params": params},
        "predicate": {"op": "equals", "field": "output.exact", "value": "3/10"}}],
        strategies=[{"action_id": "recompute", "capability": "cognition.solve", "target": "cognition:arithmetic",
                     "params": params, "advances": ["exact"], "rationale": "recompute the exact numerical answer"}],
        capabilities=["cognition.solve"], targets=("cognition:*",), ceiling="read_only")
    drop(home, signed(key, body_id, "MISSION", spec))
    with Body(home) as body:
        body.boot()
        outcome = body.tick()
        assert outcome["missions"][0]["state"] == "ACHIEVED"
        receipts = [r.payload["result"].get("output") for r in body.ledger.by_type("receipt")]
        cognitive = next(r for r in receipts if isinstance(r, dict) and r.get("problem_id") == "real:numeric")
        assert cognitive["method"] == "cognition.exact" and cognitive["authority_created"] is False
        appraised = body.journal.replay("mission.appraised")[-1].payload
        assert appraised["verdict"] == "VERIFIED", appraised
        assert len(competence(body.journal)) == 1
        assert len(body.journal.replay("cognition.settled")) == 1
        from greg.cognition.cells import cells
        cell = cells(body.journal, body.registry)[0]
        assert cell["local_state"]["observed"] == 1 and cell["local_state"]["correct"] == 1
        assert cell["authority_ceiling"] == "read_only"
        cell_id = cell["cell_id"]
        count = len(body.ledger.by_type("receipt"))
    with Body(home) as body:
        body.boot()
        body.tick()
        assert len(body.ledger.by_type("receipt")) == count
        assert len(body.journal.replay("cognition.settled")) == 1
        assert next(iter(competence(body.journal).values()))["count"] == 1
        assert cells(body.journal, body.registry)[0]["cell_id"] == cell_id
        assert body.office.gate is not None
        body.journal.record("mission.appraised", {"mission_id": "m:cognition", "verdict": "REFUTED", "checks": {}},
                            key="later-independent-refutation")
        assert competence(body.journal) == {} and cells(body.journal, body.registry) == []


def test_detachment_survives_restart_and_solver_cannot_bypass_it(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    with Body(home) as body:
        body.apply(signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": "cognition.exact"}))
    with Body(home) as body:
        manifest, adapter = body.registry.manifests["cognition.solve"], body.registry.adapters["cognition.solve"]
        from greg.capabilities import InvocationContext
        ctx = InvocationContext(workspace=tmp_path, read_roots=(), secrets=None, manifest=manifest,
                                target="cognition:test", capability_registry=body.registry)
        out = adapter({"problem_id": "detached", "operation": "calculate", "data": {"expression": "1+1"}}, ctx)
        assert out["abstention_state"] == "CAPABILITY_DEFICIT" and out["output"] is None
