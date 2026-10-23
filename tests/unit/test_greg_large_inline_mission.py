"""A founder-signed mission carries a large numeric request inline and closes on the solver's answer.

The integration record had claimed that a signed mission binds at most 16 KiB of inline data, so it could not carry
the QPs the solver accepts since the stdin transport fix. Measured, that was wrong: the 16 KiB default limits only a
value bound from one action's receipt into another, which is refused once the receipt cut it. This keeps the
measured fact true, and bounds its ledger cost: the spec is kept twice (the signed envelope on ``command.accepted``,
the validated spec on ``mission.registered``), no longer three times (docs/collaboration/LEDGER-DEDUP-2026-10-23.md)."""
from __future__ import annotations

import json

from greg.body import Body
from greg.cognition.contracts import canonical
from greg.cognition.genomes import library
from tests.greg_fixtures import Clock, make_body, mission, signed


def test_a_half_megabyte_qp_mission_is_solved_and_achieved(tmp_path):
    item = library.executables()["convex_qp_dual"]
    data, _ = item.instance(5)                                  # development seed, never a held-out one
    params = {"problem_id": "qp:inline", "operation": item.genome.operation, "data": data,
              "geometry": {"latency_limit": 30}}
    assert len(canonical(params).encode()) > 256 * 1024       # past the old argv ceiling, far past 16 KiB
    spec = mission("m:qp-inline", checks=[{
        "check_id": "solved", "description": "the cortex answered",
        "sensor": {"capability": "cognition.solve", "target": "cognition:qp", "params": params},
        "predicate": {"op": "equals", "field": "abstention_state", "value": "NONE"}}],
        strategies=[{"action_id": "solve", "capability": "cognition.solve", "target": "cognition:qp",
                     "params": params, "advances": ["solved"], "rationale": "solve the founder's QP"}],
        capabilities=["cognition.solve"], targets=("cognition:*",), ceiling="read_only")
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    ledger = home / "ledger.jsonl"
    with Body(home, clock=clock) as body:
        body.boot()
        body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": "cognition.convex_qp_dual"}))
        before = ledger.stat().st_size
        assert body.apply(signed(key, body_id, "MISSION", spec))["status"] == "APPLIED"
        for _ in range(4):
            body.tick()
            clock.advance(31)
        assert [e.payload["mission_id"] for e in body.journal.replay("mission.achieved")] == ["m:qp-inline"]
    # measured 2026-10-23: 3,241,260 bytes with three copies of the 1,068,706-byte spec, 2,172,544 with two
    grown, spec_bytes = ledger.stat().st_size - before, len(json.dumps(spec).encode())
    assert grown <= 2 * spec_bytes + 64 * 1024, f"the mission grew the ledger by {grown} bytes"
