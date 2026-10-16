"""No unbounded retry loop (Mission H, directive section 33), through the canonical Body and MissionEngine.

A retry-safe capability (read-only, idempotent) whose dispatch keeps ending with an unknown outcome may be
re-attempted, but boundedly: at most ``RETRY_LIMIT`` consecutive unknown outcomes per strategy, the first retry
at once and later ones after an exponential backoff. Then the strategy counts as failed, the mission replans,
and with no other strategy it raises exactly one NO_STRATEGY ask on the founder-ask path and waits.

Before (19bbdcb): such a capability returned RETRYING on every tick and was dispatched on every tick (12 of 12),
with no cap, no backoff and no founder ask.

In-process Body with a test clock and a per-test Ed25519 key (not Alfonso's): SANDBOX_VERIFIED.
"""
from __future__ import annotations

from datetime import datetime

from greg import missions
from greg.body import Body
from greg.capabilities import CapabilityManifest
from tests.greg_fixtures import Clock, drop, make_body, mission, signed

RETRY_LIMIT, RETRY_BACKOFF_SECONDS = 3, 60     # the bound this test pins (greg.missions owns the constants)


def _open(home, clock, calls):
    body = Body(home, clock=clock).open()
    manifest = CapabilityManifest(
        capability_id="test.flaky_read", version="1.0.0", provider="test", function="test.flaky_read",
        description="an idempotent read that keeps dying mid-call", route="api", consequence_class="read_only",
        inputs={"x": "str"}, outputs={"ok": "bool"}, strengthens=("proof",), target_prefix="probe:",
        retry_safe=True)

    def adapter(params, ctx):
        calls.append(ctx.grant_id)
        raise RuntimeError("connection reset mid-read")
    body.registry.register(manifest, adapter, state="ATTACHED")
    body.boot()
    return body


def _ticks(body, clock, n, seconds):
    states = []
    for _ in range(n):
        clock.advance(seconds)
        states.append(body.tick()["missions"][0]["state"])
    return states


def test_retry_safe_unknown_outcomes_are_bounded_backed_off_and_asked_once(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", mission("m:retry", checks=[{
        "check_id": "c", "description": "never true", "sensor": {
            "capability": "fs.read", "params": {"path": str(data / "never.txt")}, "target": "fs:never.txt"},
        "predicate": {"op": "contains", "field": "text", "value": "x"}}],
        strategies=[{"action_id": "read", "capability": "test.flaky_read", "params": {}, "target": "probe:x",
                     "advances": ["c"], "rationale": "test"}],
        capabilities=["fs.read", "test.flaky_read"], targets=("fs:*", "probe:*"), ceiling="read_only")))
    clock, calls = Clock(), []
    body = _open(home, clock, calls)
    try:
        states = _ticks(body, clock, 40, seconds=10)
        actions = [e.payload for e in body.journal.replay("mission.action")]
        assert len(calls) == RETRY_LIMIT, (states, [a["status"] for a in actions])
        assert [a["status"] for a in actions] == ["UNCERTAIN"] * 3 and len(set(calls)) == 3
        at = [datetime.fromisoformat(a["at"].replace("Z", "+00:00")) for a in actions]
        assert (at[1] - at[0]).total_seconds() == 10                          # an interrupted read: at once
        assert (at[2] - at[1]).total_seconds() >= RETRY_BACKOFF_SECONDS       # then backed off
        assert [a["retry"]["consecutive_unknown"] for a in actions] == [1, 2, 3]
        assert actions[-1]["retry"]["retry_in_seconds"] is None
        asks = [e.payload for e in body.journal.replay("decision.requested")]
        assert [a["kind"] for a in asks] == ["NO_STRATEGY"]
        assert "retry limit" in asks[0]["evidence"]["failed"]["read"]
        m = body.engine.book.missions["m:retry"]
        assert m.blocker["request_id"] == asks[0]["request_id"] and "read" in m.failed
        assert states.count("RETRYING") == 2 and "REPLANNING" in states
        assert (missions.RETRY_LIMIT, missions.RETRY_BACKOFF_SECONDS) == (RETRY_LIMIT, RETRY_BACKOFF_SECONDS)
    finally:
        body.close()
    # The bound is ledger truth, not process memory: a restart neither resets it nor asks again.
    body = _open(home, clock, calls)
    try:
        _ticks(body, clock, 20, seconds=600)
        assert len(calls) == 3
        assert len(body.journal.replay("decision.requested")) == 1
        assert body.ledger.verify_chain()[0]
    finally:
        body.close()
