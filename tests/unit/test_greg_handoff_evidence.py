"""What a receipt did not keep whole is never handed on, inspected or judged as if it were (directive of 2026-10-22,
section VI: no mission predicate may manufacture certainty from incomplete or truncated data; review of #196's
judge, findings J3, J4 and J6).

- J3: pipeline.inspect handed on a producer's field without the producer's ``complete: false``, so ``not_contains``
  passed on a partly read document. The judge read incompleteness only at the top of the judged output.
- J4: a ``$from_action`` handoff bound a list the receipt kept to its first 1000 items, or an object holding a string
  kept as a prefix, as the producer's whole value. Bind edges have refused that since #201's review (5b).
- J6: a NaN or an infinity in an action's output passed the receipt bound and made the ledger's strict JSON raise
  after the action had run, out of every tick.

In-process Body with a per-test founder key, not Alfonso's (SANDBOX).
"""
from __future__ import annotations

import math

import pytest

from greg.body import Body
from greg.missions import FALSE, INSUFFICIENT, TRUE, judge, judge_receipt
from greg.pipeline import BindingError, inspect, resolve
from tests.greg_fixtures import make_body, mission, note_check, signed, write_strategy

FILLER = "proof settlement notice delivery party shall net due. " * 400       # about 22 KiB


def _body_with(tmp_path, mid="m:hand"):
    home, key, body_id, data = make_body(tmp_path)
    page = data / "page.txt"
    page.write_text("page one")
    spec = mission(mid, checks=[note_check("c", page, "page one")],
                   strategies=[write_strategy("w", "w.txt", "x", ["c"])], capabilities=["fs.read", "fs.write"])
    return home, key, body_id, spec


def _produce(body, state, action_id, output):
    """Run one action whose adapter returns ``output``, through the real Gate, and record it as the mission's
    completed action, as the engine does."""
    manifest, _, _ = body.engine._resolve({"capability": "fs.read"})
    outcome = body.office.act(
        mission_id=state.mission_id, cone=state.cone, command_digest=state.command_digest, manifest=manifest,
        adapter=lambda params, ctx: output, ctx=body.engine._context(state, manifest),
        params={"path": action_id}, target="fs:" + action_id, cost_usd=0.0, expected_outcome="strategy executed",
        evidence_refs=[], attempt=0, spent_usd=0.0, approved_scopes=set())
    assert outcome.status == "DONE", outcome.reasons
    body.journal.record("mission.action", {
        "mission_id": state.mission_id, "action_id": action_id, "attempt": 0, "status": "DONE",
        "capability": "fs.read", "receipt": outcome.receipt_hash, "scope_digest": outcome.scope_digest},
        key=[state.mission_id, action_id, 0])
    return outcome


def _ref(action_id, field, kind):
    return {"action_id": action_id, "field": field, "type": kind}


def _inspect(body, state, ref):
    manifest, _, _ = body.engine._resolve({"capability": "pipeline.inspect"})
    ctx = body.engine._context(state, manifest)
    ctx.target, ctx.journal, ctx.mission_id = "pipeline:" + ref["action_id"], body.journal, state.mission_id
    return inspect(ref, ctx)


# -- J4 ------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("output, field, kind, why", [
    ({"rows": list(range(1500))}, "rows", "array", "item limit"),
    ({"doc": {"title": "t", "body": FILLER}}, "doc", "object", "kept as a prefix"),
    ({"text": FILLER}, "text", "object", "kept as a prefix"),
])
def test_a_value_the_receipt_did_not_keep_whole_is_never_handed_on(tmp_path, output, field, kind, why):
    home, key, body_id, spec = _body_with(tmp_path)
    with Body(home) as body:
        body.apply(signed(key, body_id, "MISSION", spec), channel="inbox")
        state = body.engine.book.missions["m:hand"]
        _produce(body, state, "make", output)
        with pytest.raises(BindingError, match=why):          # before: bound 1000 rows, or the receipt's wrapper
            resolve({"content": {"$from_action": _ref("make", field, kind)}}, body.journal, "m:hand")


def test_a_value_kept_whole_is_handed_on_as_before(tmp_path):
    home, key, body_id, spec = _body_with(tmp_path)
    with Body(home) as body:
        body.apply(signed(key, body_id, "MISSION", spec), channel="inbox")
        state = body.engine.book.missions["m:hand"]
        _produce(body, state, "make", {"rows": list(range(999)), "doc": {"title": "t"}})
        assert resolve({"content": {"$from_action": _ref("make", "rows", "array")}}, body.journal,
                       "m:hand")[0]["content"] == list(range(999))
        assert resolve({"content": {"$from_action": _ref("make", "doc", "object")}}, body.journal,
                       "m:hand")[0]["content"] == {"title": "t"}
        # inspection reports the receipt's record as it is: an observation, judged by what it kept
        inspected = _inspect(body, state, _ref("make", "rows", "array"))
        assert inspected["available"] is True and "complete" not in inspected


# -- J3 ------------------------------------------------------------------------------------------------------------

def test_an_inspected_value_keeps_its_producers_incompleteness(tmp_path):
    """A partly scanned contract: text from page one only, the producer says complete: false. Inspected, the clause
    could still be on page two, so not_contains cannot pass (before: TRUE, the mission closed and was verified)."""
    home, key, body_id, spec = _body_with(tmp_path)
    with Body(home) as body:
        body.apply(signed(key, body_id, "MISSION", spec), channel="inbox")
        state = body.engine.book.missions["m:hand"]
        _produce(body, state, "scan", {"text": "page one", "complete": False, "pages_without_text": [2],
                                       "decided": ["pages_without_text"]})
        text = _inspect(body, state, _ref("scan", "text", "string"))
        pages = _inspect(body, state, _ref("scan", "pages_without_text", "array"))
    assert text["complete"] is False
    assert judge({"op": "not_contains", "field": "value", "value": "terminate"}, text)[0] == INSUFFICIENT
    assert judge({"op": "contains", "field": "value", "value": "page one"}, text)[0] == TRUE   # monotone: kept
    assert judge({"op": "equals", "field": "available", "value": True}, text)[0] == TRUE      # stated in full
    assert judge({"op": "equals", "field": "value", "value": [2]}, pages)[0] == TRUE          # the producer vouched


def test_incompleteness_declared_inside_an_output_limits_the_fields_below_it():
    nested = {"doc": {"text": "page one", "complete": False}, "status": "ok"}
    assert judge({"op": "not_contains", "field": "doc.text", "value": "terminate"}, nested)[0] == INSUFFICIENT
    assert judge({"op": "absent", "field": "doc.clause"}, nested)[0] == INSUFFICIENT         # not reached yet
    assert judge({"op": "equals", "field": "status", "value": "ok"}, nested)[0] == TRUE      # outside it
    assert judge({"op": "equals", "field": "doc.complete", "value": False}, nested)[0] == TRUE
    vouched = {"doc": {"text": "page one", "complete": False, "decided": ["text"]}}
    assert judge({"op": "not_contains", "field": "doc.text", "value": "terminate"}, vouched)[0] == TRUE
    both = {"complete": False, "decided": ["doc.text"], "doc": {"text": "a", "complete": False}}
    assert judge({"op": "not_contains", "field": "doc.text", "value": "x"}, both)[0] == INSUFFICIENT  # inner unvouched


# -- J6 ------------------------------------------------------------------------------------------------------------

def test_a_number_that_is_not_finite_is_receipted_and_measures_nothing(tmp_path):
    """Before: the Gate ran the action, then the ledger's strict JSON raised ValueError out of AuthorityOffice.act
    and Body.tick; a read-only sensor re-dispatched on every boot crashed every boot."""
    home, key, body_id, spec = _body_with(tmp_path)
    with Body(home) as body:
        body.apply(signed(key, body_id, "MISSION", spec), channel="inbox")
        state = body.engine.book.missions["m:hand"]
        outcome = _produce(body, state, "probe", {"ratio": float("nan"), "peak": float("inf"), "count": 3})
        receipt = body.office.ledger.find(outcome.receipt_hash).payload["result"]
        artifacts = body.engine.artifact_root
    assert receipt["output"]["ratio"] == {"non_finite": "NaN"} and receipt["output"]["peak"] == {"non_finite": "Infinity"}
    assert judge_receipt({"op": "gte", "field": "ratio", "value": 0}, receipt, artifacts)[0] == INSUFFICIENT
    assert judge_receipt({"op": "lte", "field": "ratio", "value": 0}, receipt, artifacts)[0] == INSUFFICIENT
    assert judge_receipt({"op": "gte", "field": "peak", "value": 10}, receipt, artifacts)[0] == TRUE   # over the whole
    assert judge_receipt({"op": "gte", "field": "count", "value": 3}, receipt, artifacts)[0] == TRUE
    assert judge({"op": "gte", "field": "ratio", "value": 0}, {"ratio": math.nan}, whole=True)[0] == INSUFFICIENT
    with pytest.raises(BindingError, match="not finite"):
        resolve({"content": {"$from_action": _ref("probe", "ratio", "object")}}, body.journal, "m:hand")


def test_a_sensor_reading_nan_retries_and_asks_instead_of_crashing_the_body(tmp_path, monkeypatch):
    """The whole tick: a read-only sensor whose output holds NaN. The body keeps running; the check is unmeasured
    (SENSOR_RETRY, then the founder is asked), never failed or passed."""
    import greg.capabilities as caps
    manifest, adapter = caps.BUILTINS["fs.read"]
    monkeypatch.setitem(caps.BUILTINS, "fs.read", (manifest, lambda params, ctx: {"text": float("nan")}))
    from tests.greg_fixtures import Clock
    from tests.unit.test_greg_missions import events, run, submit
    home, key, body_id, spec = _body_with(tmp_path)
    submit(home, key, body_id, "MISSION", spec)
    run(home, Clock(), ticks=5, step=600.0)
    observed = [e for e in events(home, "mission.observed") if e["mission_id"] == "m:hand"]
    assert observed and all(e["detail"].startswith("sensor inconclusive") for e in observed)
    assert [r["kind"] for r in events(home, "decision.requested") if r.get("mission_id") == "m:hand"] == \
        ["SENSOR_FAILURE"]
