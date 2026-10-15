"""The Foundry store is a projection of this mission's canonical facts (third review, measurement).

A founder reconciliation of an interrupted foundry.apply as executed anchors the store once, as a ledger
fact; compensation receipts are canonical facts too. The founder key is a per-test key, not Alfonso's.
"""
from greg.body import Body
from tests.greg_fixtures import Clock, drop, make_body, mission, signed
from tests.integration.test_greg_compensation import abandon, facts, tick
from tests.unit.test_greg_reconciliation import reconcile


def check(cid, n):
    return {"check_id": cid, "description": f">= {n} objects",
            "sensor": {"capability": "foundry.query", "params": {"system": 36, "op": "verify", "args": {}},
                       "target": "foundry:36"},
            "predicate": {"op": "gte", "field": "result.objects", "value": n}}


def put(aid, text, advances, compensate=None):
    return {"action_id": aid, "capability": "foundry.apply", "target": "foundry:36",
            "params": {"system": 36, "op": "put", "args": {"text": text}}, "advances": advances, "rationale": "store",
            **({"compensate": compensate} if compensate else {})}


def test_an_interrupted_apply_reconciled_as_executed_anchors_the_store_and_the_mission_closes(tmp_path):
    """Every later foundry call was refused forever: a receipt-less reconciliation left the expected state
    unknown. The first later call now anchors the store under the founder's reconciliation."""
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", mission(
        "m:foundry", checks=[check("stored", 1)], strategies=[put("put", "retained", ["stored"])],
        capabilities=["foundry.query", "foundry.apply"], targets=("foundry:*",))))
    clock = Clock()
    with Body(home, clock=clock) as body:
        real, calls = body.registry.adapters["foundry.apply"], []

        def adapter(params, ctx):            # the effect commits, then power is lost before the receipt
            calls.append(1)
            out = real(params, ctx)
            if len(calls) == 1:
                raise RuntimeError("power lost after the store commit")
            return out
        body.registry.adapters["foundry.apply"] = adapter
        tick(body, clock, 3)
        reconcile(body, key, body_id, clock, "reconcile_executed", after=3)
        for _ in range(4):
            body.tick()
            clock.advance(900)
        assert body.engine.book.missions["m:foundry"].status == "ACHIEVED"
        [anchor] = [e.payload for e in body.journal.replay("foundry.anchored")]
        assert anchor["mission_id"] == "m:foundry" and anchor["state"].startswith("sha256:")


def test_every_signed_foundry_compensation_runs_on_the_state_the_previous_one_left(tmp_path):
    """The projection read only mission.action, so the second compensation found the store changed by the
    first (a canonical compensation receipt) and was refused."""
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:fcomp"

    def undo(text):
        return {"capability": "foundry.apply", "target": "foundry:36",
                "params": {"system": 36, "op": "put", "args": {"text": text}}}

    drop(home, signed(key, body_id, "MISSION", mission(
        mid, checks=[check("one", 1), check("many", 9)],
        strategies=[put("s1", "first", ["one"], undo("undo first")), put("s2", "second", ["many"], undo("undo second"))],
        capabilities=["foundry.query", "foundry.apply"], targets=("foundry:*",))))
    clock = Clock()
    with Body(home, clock=clock) as body:
        for _ in range(12):
            body.tick()
            clock.advance(120)
        abandon(home, key, body_id, mid)
        tick(body, clock, 4)
        assert {r["action_id"]: r["status"] for r in facts(body, "mission.compensated", mid)} == {"s1": "DONE",
                                                                                                    "s2": "DONE"}
