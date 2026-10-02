"""A real signed GREG mission produces and replays the one inert review receipt."""
from greg.body import Body
from tests.greg_fixtures import drop, make_body, mission, signed
from tests.unit.test_cognition_advantage_review import review


def test_advantage_case_is_receipted_through_existing_authority_and_restart(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    params = {"problem_id": "mission:advantage", "operation": "calculate", "data": {"expression": "4+5"},
              "proposal_review": review(), "geometry": {"latency_limit": 10}}
    spec = mission("m:advantage", checks=[{"check_id": "native", "description": "native arithmetic and inert proposal",
                   "sensor": {"capability": "cognition.solve", "target": "cognition:advantage", "params": params},
                   "predicate": {"op": "equals", "field": "output.exact", "value": "9"}}], strategies=[],
                   capabilities=["cognition.solve"], targets=("cognition:*",), ceiling="read_only")
    drop(home, signed(key, body_id, "MISSION", spec))
    with Body(home) as body:
        body.boot()
        result = body.tick()
        assert result["missions"][0]["state"] == "ACHIEVED"
        output = next(r.payload["result"]["output"] for r in body.ledger.by_type("receipt")
                      if r.payload["result"].get("output", {}).get("problem_id") == "mission:advantage")
        assert output["advantage_case"]["conditional_scenario_frontier"] == ["safe"]
        assert output["selective_disclosure"]["institutional_acceptance"]["state"] == "UNPROVEN"
        assert output["authority_created"] is False
        count = len(body.ledger.by_type("receipt"))
        assert body.journal.replay("mission.appraised")[-1].payload["verdict"] == "VERIFIED"
        from greg.presentation import cognitive_summaries
        card = cognitive_summaries(body.journal)[0]
        assert card['proposal_review']['options_for_review'] == ['safe']
        assert card['proposal_review']['acceptance'] == 'UNPROVEN'
        assert card['proposal_review']['authority_created'] is False
        assert 'protection_case' not in card['proposal_review']
        assert 'observations' not in card['proposal_review']
    with Body(home) as body:
        body.boot()
        body.tick()
        assert len(body.ledger.by_type("receipt")) == count
        assert body.office.gate is not None
