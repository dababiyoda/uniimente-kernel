"""Real GREG body, signed native commands and separate-process appraisal.

The keys authenticate laboratory commands; they are not Alfonso's key and
these cases do not establish founder-device use or live consequence authority.
"""
from greg.body import Body
from tests.greg_fixtures import Clock, drop, make_body, mission, signed


def _spec(mid, system, op, args, field, value):
    target = f"foundry:{system}:{op}"
    return mission(mid, checks=[{
        "check_id": "computed", "description": "the declared bounded computation has the specified result",
        "sensor": {"capability": "foundry.query", "params": {"system": system, "op": op, "args": args}, "target": target},
        "predicate": {"op": "equals", "field": "result." + field, "value": value},
    }], strategies=[], capabilities=["foundry.query"], targets=(target,), ceiling="read_only")


def _output(body, observation):
    return body.journal.ledger.find(observation.payload["receipt"]).payload["result"]["output"]


def test_native_signed_foundry_calculation_is_receipted_appraised_and_replays(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": "foundry.query"}))
    spec = _spec("m:foundry-native-calculation", 2, "run", {"language": "pricing", "source": "base_price * units",
                                                           "inputs": {"base_price": 12, "units": 3}}, "value", 36)
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot(); clock.advance(30)
        status = body.tick()["missions"][0]
        assert status["state"] == "ACHIEVED", status
        appraisal = body.journal.replay("mission.appraised")[-1].payload
        assert appraisal["verdict"] == "VERIFIED", appraisal["findings"]
        observations = body.journal.replay("mission.observed")
        assert observations and _output(body, observations[-1])["authority_created"] is False
        before = len(body.journal.ledger.by_type("receipt"))
    with Body(home, clock=clock) as body:
        body.boot(); clock.advance(30); body.tick()
        assert len(body.journal.ledger.by_type("receipt")) == before, "closed computation never duplicates receipt delivery"
        assert body.journal.ledger.verify_chain()[0]


def test_native_unknown_scope_is_preserved_and_detach_survives_restart(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": "foundry.query"}))
    model = {"variables": {"n": [0, 1, 2]}, "initial": {"n": 0},
             "transitions": [{"name": "to1", "set": {"n": 1}}, {"name": "to2", "set": {"n": 2}}]}
    spec = _spec("m:foundry-native-unknown", 43, "check", {"model": model, "max_states": 1}, "native_status", "UNKNOWN")
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot(); clock.advance(30); body.tick()
        output = _output(body, body.journal.replay("mission.observed")[-1])
        assert output["result"]["holds"] is None and output["result"]["native_status"] == "UNKNOWN"
        before = len(body.journal.ledger.by_type("receipt"))
    drop(home, signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": "foundry.query"}))
    spec = _spec("m:foundry-after-revocation", 2, "run", {"language": "pricing", "source": "1", "inputs": {}}, "value", 1)
    drop(home, signed(key, body_id, "MISSION", spec))
    with Body(home, clock=clock) as body:
        body.boot(); clock.advance(30); status = body.tick()
        assert body.registry.state["foundry.query"] == "DETACHED"
        assert len(body.journal.ledger.by_type("receipt")) == before
        new = next(m for m in status["missions"] if m["mission_id"] == spec["mission_id"])
        assert new["state"] in ("BLOCKED", "WAITING")
