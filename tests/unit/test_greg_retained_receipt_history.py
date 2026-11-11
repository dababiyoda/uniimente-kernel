"""History is read whatever the capability's state is now; permission is not.

A body stopped between the Gate's record of a dispatch and the mission's record of it settles that dispatch from the
Gate's own record when it restarts (``MissionEngine._recover_dispatch``). The founder may detach the capability in
between. Two things must then hold together:

- what already happened stays what the record says it was: a completed effect is recorded as done with its receipt
  and its cost, a refusal as that refusal with its own reason, and a dispatch with no receipt, or with a receipt
  that does not say what happened, as uncertain with one reconciliation ask. Detaching a capability does not turn a completed effect into a refusal or hide an unknown one;
- nothing runs because of it: no second dispatch, grant or receipt for the recovered action, and a later action of
  the detached capability is not executed.

Each case is run twice, with and without the detach, and the recovered record must be the same. Every run is a real
Body closed and opened again on the same home, in this process; ``Killed`` stands in for SIGKILL. The founder key is a
per-test key, not Alfonso's.
"""
from __future__ import annotations

import pytest

from greg import capabilities
from greg.body import Body
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy

MID = "m:history-detached"


class Killed(BaseException):
    """SIGKILL, as far as the body can tell: nothing after it runs."""


def tick(body, clock, n):
    for _ in range(n):
        body.tick()
        clock.advance(1)


def facts(body, kind):
    return [e.payload for e in body.journal.replay(kind) if e.payload.get("mission_id") == MID]


def gate_kept(body, action_id: str) -> dict:
    """The Gate's own record of one action's dispatch: its claims and the receipts under their grants."""
    proposals = {i["proposal_id"] for i in facts(body, "mission.dispatching") if i["action_id"] == action_id}
    claims = [r for r in body.ledger.by_type("grant_dispatch") if r.payload["proposal_id"] in proposals]
    grants = {c.payload["grant_id"] for c in claims}
    return {"claims": len(claims),
            "receipts": len([r for r in body.ledger.by_type("receipt") if r.payload["grant_id"] in grants])}


def kill_before_record(body, kind: str):
    record = body.journal.record

    def dies(name, data, **kw):
        if name == kind:
            raise Killed(f"SIGKILL before {kind}")
        return record(name, data, **kw)
    body.journal.record = dies


def run(tmp, monkeypatch, case: str, detach: str | None) -> dict:
    """``case``: "done" (the write completed), "refused" (its capability refused it), "unknown" (the body died
    inside the adapter: a dispatch claim and no receipt) or "unclassed" (as "unknown", and a receipt for that
    dispatch whose result names no class: not one this office's executor writes, so it does not say whether the
    write happened). The body dies before the action is recorded. ``detach``:
    None, "inbox" (the founder's signed detach is waiting when the body restarts) or "applied" (applied by the
    restarted body before its first tick). A second write, ``later``, is signed in the same mission and has not run."""
    tmp.mkdir()
    home, key, body_id, _ = make_body(tmp)
    note, other = workspace(home, MID) / "note.txt", workspace(home, MID) / "later.txt"
    first = write_strategy("w", "note.txt", "draft", ["c"])
    if case == "refused":   # the write names another path than its signed target: fs.write refuses it
        first = {**first, "params": {"relative_path": "elsewhere.txt", "content": "draft"}}
    calls = []
    manifest, real = capabilities.BUILTINS["fs.write"]

    def counted(params, ctx):
        calls.append(params.get("relative_path"))
        if case in ("unknown", "unclassed") and len(calls) == 1:
            raise Killed("SIGKILL inside the adapter")
        return real(params, ctx)
    monkeypatch.setitem(capabilities.BUILTINS, "fs.write", (manifest, counted))
    drop(home, signed(key, body_id, "MISSION", mission(
        MID, checks=[note_check("c", note, "draft"), note_check("d", other, "second")],
        strategies=[first, write_strategy("later", "later.txt", "second", ["d"])],
        capabilities=["fs.read", "fs.write"])))
    clock = Clock()
    with Body(home, clock=clock) as body:
        if case in ("done", "refused"):
            kill_before_record(body, "mission.action")
        with pytest.raises(Killed):
            tick(body, clock, 3)
        assert not facts(body, "mission.action"), "the body recorded the action before it died"
        before = gate_kept(body, "w")
    assert calls == [first["params"]["relative_path"]]
    assert before == {"claims": 1, "receipts": 0 if case in ("unknown", "unclassed") else 1}
    if case == "unclassed":
        with Body(home, clock=clock) as body:   # nothing ticks: only the record another writer or version could leave
            claim = [r for r in body.ledger.by_type("grant_dispatch")
                     if r.payload["proposal_id"] in {i["proposal_id"] for i in facts(body, "mission.dispatching")
                                                     if i["action_id"] == "w"}][-1]
            body.ledger.append("receipt", {"action_id": "unclassed", "witness_id": claim.payload["witness_id"],
                                           "grant_id": claim.payload["grant_id"],
                                           "result": {"observed_outcome": "half written"}})
            before = gate_kept(body, "w")
    detach_command = signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": "fs.write"})
    if detach == "inbox":
        drop(home, detach_command)
    with Body(home, clock=clock) as body:
        if detach == "applied":
            assert body.apply(detach_command)["result"]["state"] == "DETACHED"
        tick(body, clock, 4)
        recovered = [a for a in facts(body, "mission.action") if a["action_id"] == "w"]
        state = body.engine.book.missions[MID]
        return {
            "w": [(a["attempt"], a["status"], a["reasons"], a["cost_usd"], bool(a.get("receipt"))) for a in recovered],
            "w_receipt_class": [body.ledger.find(a["receipt"]).payload["result"].get("result_class")
                                for a in recovered if a.get("receipt")],
            "note": note.read_text() if note.exists() else None,
            "later_ran": "later.txt" in calls, "later_written": other.exists(),
            "later_records": [(a["status"]) for a in facts(body, "mission.action") if a["action_id"] == "later"],
            "fs_write_state": body.registry.state["fs.write"],
            "reconciliation_asks": len([r for r in body.engine.book.open_requests() if r["kind"] == "RECONCILIATION"]),
            "gate_kept_for_w": gate_kept(body, "w"), "gate_kept_before": before,
            "adapter_calls_for_w": len([c for c in calls if c == first["params"]["relative_path"]]),
            "status": state.status,
        }


EXPECTED_W = {
    "done": ([(0, "DONE", ["retained receipt of a dispatch the body did not record before it stopped"], 0.0, True)],
             ["positive"]),
    "refused": ([(0, "REFUSED", ["capability refused: write path 'workspace:elsewhere.txt' does not match the signed "
                                 "target 'workspace:note.txt'"], 0.0, True)], ["negative"]),
    "unknown": ([(0, "UNCERTAIN", ["dispatch claimed without receipt; the body stopped inside it, so its outcome is "
                                   "unknown"], 0.0, False)], []),
    "unclassed": ([(0, "UNCERTAIN", ["the receipt does not say whether the capability acted (result class None); its "
                                     "outcome is unknown and must be reconciled"], 0.0, True)], [None]),
}


@pytest.mark.parametrize("detach", ["inbox", "applied"])
@pytest.mark.parametrize("case", ["done", "refused", "unknown", "unclassed"])
def test_what_happened_before_a_detach_is_recorded_as_it_was_and_runs_nothing(tmp_path, monkeypatch, case, detach):
    control = run(tmp_path / "control", monkeypatch, case, None)
    assert (control["w"], control["w_receipt_class"]) == EXPECTED_W[case], "the run without a detach"
    detached = run(tmp_path / "detached", monkeypatch, case, detach)
    assert detached["fs_write_state"] == "DETACHED"
    # history: the recovered record is the one the Gate's own record supports, detached or not
    assert (detached["w"], detached["w_receipt_class"]) == (control["w"], control["w_receipt_class"])
    assert detached["note"] == control["note"] == ("draft" if case == "done" else None)
    assert detached["reconciliation_asks"] == control["reconciliation_asks"] == (case in ("unknown", "unclassed"))
    # nothing ran because of the recovery: one dispatch claim and one adapter call for the action, as before the kill
    assert detached["adapter_calls_for_w"] == control["adapter_calls_for_w"] == 1
    assert detached["gate_kept_for_w"] == detached["gate_kept_before"] == control["gate_kept_for_w"]
    # permission: the later write of the detached capability is not executed, though the same mission signed it
    # (and it does run when nothing was detached, unless the mission is waiting on a reconciliation)
    assert control["later_ran"] == control["later_written"] == (case in ("done", "refused"))
    assert not detached["later_ran"] and not detached["later_written"]
    assert "DONE" not in detached["later_records"]
