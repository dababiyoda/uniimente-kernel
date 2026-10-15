"""Unknown completion through the canonical Body, MissionEngine, AuthorityOffice and ConsequenceGate.

Mission H (directive section 33): "no unbounded retry loop, no duplicate irreversible consequence, and truthful
handling of unknown completion". A dispatch whose completion is unknown (UNCERTAIN) is reconciled by a signed
founder answer, never blindly retried; one answer settles exactly one dispatch; and the dispatch's worst case
(its signed cap) counts against the signed budget until it is settled.

Before (19bbdcb): the RECONCILIATION request id was derived from mission, kind and exact scope only, so after
one signed ``reconcile_not_executed`` every later UNCERTAIN dispatch of the same scope found the old answer and
was redispatched on every tick with no new ask (9 dispatches of a $0.40 action under a $1.00 budget), and
UNCERTAIN spend was booked as $0.00, so the budget never bounded it.

In-process Body with a test clock and a per-test Ed25519 key (not Alfonso's): SANDBOX_VERIFIED.
"""
from __future__ import annotations

from greg.body import Body
from greg.capabilities import CapabilityManifest
from tests.greg_fixtures import Clock, drop, make_body, mission, signed


def _capability(body, effects: list, *, retry_safe: bool):
    """A capability that performs its effect and then loses power before the Gate's receipt."""
    manifest = CapabilityManifest(
        capability_id="test.flaky", version="1.0.0", provider="test", function="test.flaky",
        description="writes, then dies before its receipt", route="api",
        consequence_class="read_only" if retry_safe else "internal_write", inputs={"x": "str"},
        outputs={"ok": "bool"}, strengthens=("proof",), target_prefix="probe:", retry_safe=retry_safe)

    def adapter(params, ctx):
        effects.append(ctx.grant_id)
        raise RuntimeError("power lost mid-effect")
    body.registry.register(manifest, adapter, state="ATTACHED")


def _spec(data, *, retry_safe: bool, cost: float, budget: float):
    ceiling = "read_only" if retry_safe else "internal_write"
    return mission("m:unknown", checks=[{
        "check_id": "c", "description": "never true", "sensor": {
            "capability": "fs.read", "params": {"path": str(data / "never.txt")}, "target": "fs:never.txt"},
        "predicate": {"op": "contains", "field": "text", "value": "x"}}],
        strategies=[{"action_id": "act", "capability": "test.flaky", "params": {}, "target": "probe:x",
                     "advances": ["c"], "rationale": "test", "cost_usd": cost}],
        capabilities=["fs.read", "test.flaky"], targets=("fs:*", "probe:*"), ceiling=ceiling, budget=budget)


def _open(home, clock, effects, *, retry_safe):
    body = Body(home, clock=clock).open()
    _capability(body, effects, retry_safe=retry_safe)
    body.boot()
    return body


def _ticks(body, clock, n, seconds=60):
    states = []
    for _ in range(n):
        clock.advance(seconds)
        states.append(body.tick()["missions"][0]["state"])
    return states


def _requests(body, kind="RECONCILIATION"):
    return [e.payload for e in body.journal.replay("decision.requested") if e.payload["kind"] == kind]


def _actions(body):
    return [(e.payload["status"], e.payload["attempt"]) for e in body.journal.replay("mission.action")]


def test_one_reconciliation_answer_settles_exactly_one_dispatch(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _spec(data, retry_safe=False, cost=0.4, budget=1.0)))
    clock, effects = Clock(), []
    body = _open(home, clock, effects, retry_safe=False)
    try:
        assert _ticks(body, clock, 6) == ["BLOCKED"] + ["WAITING"] * 5
        assert len(effects) == 1 and _actions(body) == [("UNCERTAIN", 0)]
        first = _requests(body)
        assert len(first) == 1
        reserved_before = body.engine.book.missions["m:unknown"].__dict__.get("reserved")

        drop(home, signed(key, body_id, "DECISION", {"request_id": first[0]["request_id"],
                                                     "answer": "reconcile_not_executed", "reason": "test"}))
        states = _ticks(body, clock, 11)
        # The answer settles attempt 0 only: exactly one redispatch, which is UNCERTAIN again and opens its own
        # reconciliation, bound to attempt 1 and its own grant. Nothing else is dispatched while it waits.
        assert len(effects) == 2, (states, _actions(body))
        assert first[0]["authority_requested"]["attempt"] == 0
        assert reserved_before == {("act", 0): 0.4}                                  # unknown spend, not zero
        assert _actions(body) == [("UNCERTAIN", 0), ("RECONCILED_NOT_EXECUTED", 0), ("UNCERTAIN", 1)]
        second = _requests(body)
        assert len(second) == 2 and second[1]["request_id"] != first[0]["request_id"]
        assert second[1]["authority_requested"]["attempt"] == 1
        assert second[1]["authority_requested"]["grant_id"] == effects[1] != effects[0]
        assert states[0] == "BLOCKED" and set(states[1:]) == {"WAITING"}
        m = body.engine.book.missions["m:unknown"]
        assert m.blocker["type"] == "reconciliation" and m.blocker["request_id"] == second[1]["request_id"]
        assert (m.spent_usd, m.reserved_usd) == (0.0, 0.4)                          # attempt 0 released
    finally:
        body.close()

    # A restart rebuilds the same truth from the ledger: still one open reconciliation, still no dispatch.
    body = _open(home, clock, effects, retry_safe=False)
    try:
        assert set(_ticks(body, clock, 5)) == {"WAITING"} and len(effects) == 2
        assert body.engine.book.missions["m:unknown"].reserved_usd == 0.4
        drop(home, signed(key, body_id, "DECISION", {"request_id": second[1]["request_id"],
                                                     "answer": "reconcile_executed", "reason": "test"}))
        _ticks(body, clock, 6)
        m = body.engine.book.missions["m:unknown"]
        done = [e.payload for e in body.journal.replay("mission.action") if e.payload["status"] == "DONE"]
        assert len(done) == 1 and done[0]["attempt"] == 1 and done[0]["reconciles"]["grant_id"] == effects[1]
        # It executed and its spend was never measured: the signed cap is booked, not zero.
        assert done[0]["cost_usd"] == 0.4 and done[0]["spend_basis"].startswith("signed_cap")
        assert (m.spent_usd, m.reserved_usd) == (0.4, 0.0)
        assert len(effects) == 2                     # an executed dispatch is never dispatched again
        assert len(_requests(body)) == 2
        assert body.ledger.verify_chain()[0]
    finally:
        body.close()


def test_unknown_spend_is_reserved_at_its_worst_case_and_bounds_dispatch(tmp_path):
    """A retry-safe dispatch is re-attempted, but each unknown outcome may have spent its cap: two reserved
    $0.40 dispatches leave $0.20 of a signed $1.00, so a third is not dispatched; the mission asks instead."""
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _spec(data, retry_safe=True, cost=0.4, budget=1.0)))
    clock, effects = Clock(), []
    body = _open(home, clock, effects, retry_safe=True)
    try:
        _ticks(body, clock, 8, seconds=120)
        m = body.engine.book.missions["m:unknown"]
        assert len(effects) == 2, _actions(body)
        assert _actions(body) == [("UNCERTAIN", 0), ("UNCERTAIN", 1)]
        assert (m.spent_usd, m.reserved_usd) == (0.0, 0.8)
        asks = _requests(body, "APPROVAL")
        assert len(asks) == 1 and any("exceeds budget" in r for r in asks[0]["evidence"]["policy"])
        assert asks[0]["evidence"]["budget"] == {"spent_usd": 0.0, "budget_usd": 1.0, "reserved_usd": 0.8}
        uncertain = [e.payload for e in body.journal.replay("mission.action")]
        assert all(a["cost_usd"] == 0.0 and a["reserved_usd"] == 0.4 for a in uncertain)
    finally:
        body.close()
    body = _open(home, clock, effects, retry_safe=True)
    try:
        _ticks(body, clock, 4, seconds=120)
        assert len(effects) == 2 and body.engine.book.missions["m:unknown"].committed_usd == 0.8
    finally:
        body.close()
