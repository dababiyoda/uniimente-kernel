"""Declared faults and stress models execute through native GREG, not live services."""
import pytest
from greg.body import Body
from tests.greg_fixtures import drop, make_body, signed
from tests.integration.test_greg_foundry_extraction import _spec, _output
from tests.unit.test_foundry_fault_simulation import strategy


@pytest.mark.parametrize("system,op,args,field,value", [
    (20, "compare", {"script": ["timeout", "partial_write", "ok"], "honours_idempotency": True,
                      "key": "case", "amount": 900}, "bounded_reconciliation.truth.charges", 1),
    (22, "tribunal", {"strategies": {"independent": strategy()}, "runs": 64},
     "table.independent.platform_loss.survival", 1),
])
def test_simulated_mechanism_runs_on_signed_mission_path_without_outcome_laundering(tmp_path, system, op, args, field, value):
    home, key, body_id, _ = make_body(tmp_path)
    with Body(home) as body:
        body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": "foundry.query"}))
        spec = _spec(f"m:simulated-{system}", system, op, args, field, value)
        drop(home, signed(key, body_id, "MISSION", spec))
        body.boot()
        assert body.tick()["missions"][0]["state"] == "ACHIEVED"
        out = _output(body, body.journal.replay("mission.observed")[-1])
        assert out["result"]["evidence_kind"] == "simulation"
        assert not out["external_effect"] and not out["authority_created"]
        appraisal = body.journal.replay("mission.appraised")[-1].payload
        assert appraisal["verdict"] == "VERIFIED", appraisal
        assert not appraisal["checks"]["world_reobserved"]
        assert not body.journal.replay("cognition.settled")
