"""The founder's second achievement, measured: a different, later mission is cheaper because an earlier one formed a capability.

Mission A asks for a function GREG does not have. Capability Genesis builds it (one wrong candidate is refused,
the second passes the founder-frozen held-out vectors), attaches it and A closes. The body restarts. Mission B is
a different mission (another document, another check) that needs the same function: it closes with no deficit and
no builder call, and ``greg.compounding`` prices what A paid that B did not. The counterfactual is run, not
assumed: B alone on a body that never formed the capability opens the deficit and calls the builder. Negative
controls cover a rerun of A's procedure, a B registered before the capability existed, a B that formed its own,
and a quarantined capability. Test keys: the result is a structural candidate, never the founder's tier.
"""
from __future__ import annotations

import json

from greg import builders, compounding, tribunal
from greg.body import Body
from tests.greg_fixtures import Clock, drop, make_body, mission, signed
from tests.unit.test_greg_genesis_builder import CONTRACT, FUNCTION, GOOD, WRONG, _mission as mission_a


def mission_b(data, mid="m:release", doc="RELEASE.md", check_id="release-blockers-counted", expected=2):
    path = data / doc
    path.write_text("# Release\n- [ ] sign notes\n- [x] tag\n+ [ ] publish checksums\n")
    check = {"check_id": check_id, "description": "the release blockers still open are known",
             "sensor": {"function": FUNCTION, "params": {"path": str(path)}, "target": f"fs:{doc}"},
             "predicate": {"op": "equals", "field": "unchecked", "value": expected}}
    spec = mission(mid, checks=[check], strategies=[], ceiling="read_only", budget=1.0,
                   capabilities=["fs.read", f"built.{FUNCTION}.*"], auto_attach=True)
    spec["capability_specs"] = [dict(CONTRACT)]
    return spec


def run(home, builder, ticks=4):
    clock = Clock()
    body = Body(home, clock=clock, builder=builder).open()
    body.boot()
    for _ in range(ticks):
        clock.advance(30)
        body.tick()
    return body


def states(body):
    return {m["mission_id"]: m["state"] for m in body.tick()["missions"]}


def test_a_different_later_mission_reuses_the_formed_capability_and_pays_none_of_its_acquisition(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", mission_a(data)))
    first = builders.StaticBuilder(WRONG, GOOD, identity="static-test")
    body = run(home, first)
    assert states(body)["m:runbook"] == "ACHIEVED" and len(first.calls) == 2
    body.close()

    drop(home, signed(key, body_id, "MISSION", mission_b(data)))
    second = builders.StaticBuilder(GOOD, identity="static-test")     # would build; must not be called
    body = run(home, second)
    assert states(body)["m:release"] == "ACHIEVED"
    assert second.calls == []
    j = body.journal
    assert not [e for e in j.replay("deficit.opened") if e.payload["mission_id"] == "m:release"]

    measured = compounding.retained_reuse(j)
    [reuse] = measured["reuses"]
    assert (reuse["formed_in"], reuse["reused_in"], reuse["function"]) == ("m:runbook", "m:release", FUNCTION)
    assert reuse["capability_id"].startswith(f"built.{FUNCTION}.")
    assert reuse["avoided"]["builder_calls"] == 2 and reuse["avoided"]["verifications"] == 2
    assert reuse["avoided"]["build_cost_known"] is True
    assert reuse["avoided"]["blocked_seconds"] is not None
    assert reuse["paid_in_reuse"] == {"builder_calls": 0, "build_cost_usd": 0.0, "verifications": 0,
                                      "blocked_seconds": 0.0, "deficits_opened": 0}
    assert measured["refused"] == [] and measured["compounding"] is True

    tiered = compounding.capability_compounding(j)
    assert tiered["structurally_met"] is True and tiered["met"] is False          # test keys: never founder tier
    assert tiered["evidence_level"] == "STRUCTURAL_CANDIDATE" and tiered["structural_value"] == 1

    report = tribunal.morning_report(j)
    assert [r["reused_in"] for r in report["q9_learned"]["capabilities_reused"]] == ["m:release"]
    body.close()


def test_the_counterfactual_body_without_the_capability_pays_the_acquisition_itself(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", mission_b(data)))
    builder = builders.StaticBuilder(WRONG, GOOD, identity="static-test")
    body = run(home, builder)
    assert states(body)["m:release"] == "ACHIEVED"
    assert len(builder.calls) == 2                                       # the same detour A paid
    assert [e.payload["mission_id"] for e in body.journal.replay("deficit.opened")] == ["m:release"]
    measured = compounding.retained_reuse(body.journal)
    assert measured["reuses"] == [] and measured["compounding"] is False
    assert [f["mission_id"] for f in measured["formed"]] == ["m:release"]
    body.close()


def test_a_rerun_of_the_same_procedure_is_not_a_different_mission(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", mission_a(data)))
    body = run(home, builders.StaticBuilder(WRONG, GOOD, identity="static-test"))
    body.close()
    again = mission_a(data)
    again["mission_id"] = "m:runbook-again"
    drop(home, signed(key, body_id, "MISSION", again))
    body = run(home, builders.StaticBuilder(GOOD, identity="static-test"))
    assert states(body)["m:runbook-again"] == "ACHIEVED"
    measured = compounding.retained_reuse(body.journal)
    assert measured["reuses"] == []
    [refused] = measured["refused"]
    assert refused["reused_in"] == "m:runbook-again"
    assert any("same procedure" in w for w in refused["why_not"])
    body.close()


def test_a_mission_registered_before_the_capability_existed_is_not_credited(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", mission_a(data)))
    drop(home, signed(key, body_id, "MISSION", mission_b(data)))
    body = run(home, builders.StaticBuilder(WRONG, GOOD, identity="static-test"), ticks=6)
    assert set(states(body).values()) == {"ACHIEVED"}
    measured = compounding.retained_reuse(body.journal)
    assert measured["reuses"] == []
    [refused] = measured["refused"]                  # whichever mission formed it, the other was already waiting
    assert refused["why_not"] == ["registered before the capability was formed"]
    body.close()


def test_a_quarantined_capability_is_rebuilt_and_its_later_use_is_not_credited_to_a(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", mission_a(data)))
    body = run(home, builders.StaticBuilder(WRONG, GOOD, identity="static-test"))
    digest = [e.payload for e in body.journal.replay("genesis.built")][-1]["source_sha256"]
    body.close()
    stored = home / "capabilities" / "built" / f"{digest}.py"
    stored.write_text(stored.read_text() + "\nimport os\n")             # tampered: the body quarantines it
    drop(home, signed(key, body_id, "MISSION", mission_b(data)))
    rebuild = builders.StaticBuilder(GOOD, identity="static-test-2")
    body = run(home, rebuild)
    j = body.journal
    assert any(e.payload.get("state") == "QUARANTINED" for e in j.replay("capability.state"))
    measured = compounding.retained_reuse(j)
    assert len(rebuild.calls) == 1 and measured["reuses"] == [], json.dumps(measured["reuses"])
    # B formed the function again itself (same content, same id), so its use belongs to that formation, not A's
    assert sorted(f["mission_id"] for f in measured["formed"]) == ["m:release", "m:runbook"]
    assert measured["refused"] == []
    body.close()
