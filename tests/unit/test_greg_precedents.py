"""The institutional memory sensor is a signed GREG capability, not a second ledger."""
from dataclasses import replace

import pytest

from greg.body import Body
from greg.capabilities import BUILTINS, CapabilityError, InvocationContext
from greg.precedents import precedents
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy


def test_sensor_reobserves_a_new_receipt_even_when_wall_clock_is_frozen(tmp_path):
    home, founder, body_id, _ = make_body(tmp_path)
    note = workspace(home, "m:frozen") / "note.txt"
    drop(home, signed(founder, body_id, "MISSION", mission(
        "m:frozen", checks=[note_check("written", note, "truth")],
        strategies=[write_strategy("write", "note.txt", "truth", ["written"])],
        capabilities=["fs.read", "fs.write"])))
    # Same wall-clock value across ticks used to reuse an obsolete "absent"
    # sensor receipt, causing repeated writes instead of the real closure.
    with Body(home, clock=Clock()) as body:
        for _ in range(4):
            body.tick()
        assert body.engine.book.missions["m:frozen"].status == "ACHIEVED"
        reads = [e.payload["receipt"] for e in body.journal.replay("mission.observed")
                 if e.payload.get("mission_id") == "m:frozen"]
        writes = [e for e in body.journal.replay("mission.action")
                  if e.payload.get("mission_id") == "m:frozen"
                  and e.payload.get("capability") == "fs.write"]
        assert len(reads) >= 2 and len(reads) == len(set(reads))
        assert len(writes) == 1


def test_signed_mission_uses_past_action_and_distinct_local_appraisal_after_restart(tmp_path):
    home, founder, body_id, data = make_body(tmp_path)
    note = workspace(home, "m:history") / "note.txt"
    drop(home, signed(founder, body_id, "MISSION", mission(
        "m:history", checks=[note_check("written", note, "evidence")],
        strategies=[write_strategy("write", "note.txt", "evidence", ["written"])],
        capabilities=["fs.read", "fs.write"])))
    clock = Clock()
    with Body(home, clock=clock) as body:
        for _ in range(5):
            body.tick()
            clock.advance(1)
        assert any(e.payload.get("verdict") == "VERIFIED" for e in body.journal.replay("mission.appraised"))

    check = {"check_id": "remembered", "description": "prior locally appraised write exists",
             "sensor": {"capability": "memory.precedents", "params": {"capability": "fs.write"},
                        "target": "memory:fs.write"},
             "predicate": {"op": "gte", "field": "locally_appraised_mission_count", "value": 1}}
    drop(home, signed(founder, body_id, "MISSION", mission(
        "m:remember", checks=[check], strategies=[], capabilities=["memory.precedents"],
        targets=("memory:fs.write",), ceiling="read_only")))
    clock = Clock()
    with Body(home, clock=clock) as body:
        for _ in range(5):
            body.tick()
            clock.advance(1)
        assert body.engine.book.missions["m:remember"].status == "ACHIEVED"
        assert any(e.payload.get("mission_id") == "m:remember" and e.payload.get("verdict") == "VERIFIED"
                   for e in body.journal.replay("mission.appraised"))
        observations = [e.payload for e in body.journal.replay("mission.observed")
                        if e.payload.get("mission_id") == "m:remember"]
        assert observations
        receipt = body.ledger.find(observations[-1]["receipt"])
        result = receipt.payload["result"]["output"]
        assert result["action_evidence"]["count"] >= 1
        assert result["action_evidence"]["by_validation_and_result"]["self_reported"]["positive"] >= 1
        assert result["locally_appraised_mission_count"] == 1
        assert result["locally_appraised_missions"][0]["mission_id"] == "m:history"
        assert "external verification" in result["limitations"]
        assert "evidence" not in str(result["action_evidence"])  # no payload or target text

    with Body(home) as body:
        manifest, _ = BUILTINS["memory.precedents"]
        ctx = InvocationContext(workspace=workspace(home, "m:remember"), read_roots=(data,),
                                secrets=body.secrets, manifest=manifest, journal=body.journal,
                                target="memory:fs.write")
        again = precedents({"capability": "fs.write"}, ctx)
        assert again["locally_appraised_mission_count"] == 1
        assert again["action_evidence"]["count"] >= 1

        assert body.apply(signed(founder, body_id, "CAPABILITY_DETACH",
                                 {"capability_id": "memory.precedents"}))["status"] == "APPLIED"
        assert body.registry.usable("memory.precedents")[0] is False
    with Body(home) as body:
        assert body.registry.state["memory.precedents"] == "DETACHED"


def test_memory_refuses_target_swap_unscoped_read_and_unknown_capability(tmp_path):
    home, _, _, data = make_body(tmp_path)
    with Body(home) as body:
        manifest, adapter = BUILTINS["memory.precedents"]
        ctx = InvocationContext(workspace=tmp_path / "ws", read_roots=(data,), secrets=body.secrets,
                                manifest=manifest, journal=body.journal, target="memory:fs.read")
        with pytest.raises(CapabilityError, match="signed capability target"):
            adapter({"capability": "fs.write"}, ctx)
        with pytest.raises(CapabilityError, match="known non-memory capability"):
            adapter({"capability": "unknown"}, replace(ctx, target="memory:unknown"))
        with pytest.raises(CapabilityError, match="exactly one capability"):
            adapter({"capability": "fs.read", "target": "memory:fs.read"}, ctx)
        with pytest.raises(CapabilityError, match="unavailable"):
            adapter({"capability": "fs.read"}, replace(ctx, journal=None))
        from greg.lightcone import LightCone
        from tests.greg_fixtures import horizon
        cone = LightCone.from_dict({"capabilities": ["fs.read"], "targets": ["memory:fs.write"],
                                    "max_consequence_class": "read_only", "budget_usd": 0,
                                    "horizon": horizon()})
        grants_before = len(body.office.grants._grants)
        out = body.office.act(mission_id="m:unauthorized", cone=cone, command_digest="sha256:test",
                              manifest=manifest, adapter=adapter, ctx=ctx, params={"capability": "fs.write"},
                              target="memory:fs.write", cost_usd=0, expected_outcome="read",
                              evidence_refs=[], attempt=0, spent_usd=0, approved_scopes=set())
        assert out.status == "OUTSIDE_SCOPE" and len(body.office.grants._grants) == grants_before
