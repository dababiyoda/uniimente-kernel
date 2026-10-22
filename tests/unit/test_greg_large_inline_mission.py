"""A founder-signed mission carries a large numeric request inline and closes on the solver's answer.

The integration record had claimed that a signed mission binds at most 16 KiB of inline data, so it could not carry
the QPs the solver accepts since the stdin transport fix. Measured, that was wrong: the 16 KiB default limits only a
value bound from one action's receipt into another, which is refused once the receipt cut it. This keeps the
measured fact true. Its ledger cost (the spec is stored three times) is recorded in the integration record, not
asserted here, so a later deduplication is not a test failure."""
from __future__ import annotations

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
    with Body(home, clock=clock) as body:
        body.boot()
        body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": "cognition.convex_qp_dual"}))
        assert body.apply(signed(key, body_id, "MISSION", spec))["status"] == "APPLIED"
        for _ in range(4):
            body.tick()
            clock.advance(31)
        assert [e.payload["mission_id"] for e in body.journal.replay("mission.achieved")] == ["m:qp-inline"]
