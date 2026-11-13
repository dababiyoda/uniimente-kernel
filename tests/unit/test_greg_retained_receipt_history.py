"""A dispatch the Gate recorded and the mission did not is read from the Gate's record, whatever its capability's
state is now; permission is not.

A body stopped between the Gate's record of a dispatch and the mission's record of it settles that dispatch from the
Gate's own record when it restarts. Two paths do this, and each has its section here:

- a strategy: ``MissionEngine._recover_dispatch`` finds the proposal by the intent the mission wrote before the
  dispatch;
- a signed compensation: ``MissionEngine._run_compensation`` reads the Gate's record of the compensation's own
  proposal before it looks at the capability. (Before, only ``office.act`` looked, and it is reached only when the
  capability is attached and answers its availability check first.)

The founder may detach the capability in between, or it may be attached and not runnable on this body. Two things
must then hold together:

- what already happened stays what the record says it was: a completed effect is recorded as done with its receipt
  (and, for a strategy, its cost), a refusal as that refusal with its own reason, and a dispatch with no receipt, or
  with a receipt that does not say what happened, as uncertain with one question to the founder (a reconciliation
  for a strategy, the COMPENSATION ask for a compensation). The capability's state does not turn a completed effect
  into a refusal or into "did not complete", and does not hide an unknown one;
- nothing runs because of it: no second dispatch, grant or receipt for the recovered action, and a later action of
  the detached capability is not executed.

What is not read this way, so the title is not taken further than it holds:

- a compensation is found by its exact scope, which includes its capability's consequence class. One dispatched
  before the capability was registered again under another class is not found (read from the code, not run);
- a ledger on which the earlier code already asked the founder about such a compensation keeps that open question:
  no compensation is looked up while the founder's answer to its COMPENSATION ask is awaited, and the answer is
  recorded as FOUNDER_DECIDED. A record the earlier code wrote as UNAVAILABLE stays as written. (The first was
  observed on a scratch body with the lookup switched off for one restart; it has no test here.)

Each strategy case is run twice, with and without the detach, and the recovered record must be the same; each
compensation case is run with the capability usable, detached and unavailable, against one stated expectation. Every
run is a real Body closed and opened again on the same home, in this process; ``Killed`` stands in for SIGKILL. The
founder key is a per-test key, not Alfonso's.
"""
from __future__ import annotations

import pytest

from greg import capabilities
from greg.body import Body
from greg.capabilities import CapabilityManifest
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy

MID = "m:history-detached"


class Killed(BaseException):
    """SIGKILL, as far as the body can tell: nothing after it runs."""


def tick(body, clock, n):
    for _ in range(n):
        body.tick()
        clock.advance(1)


def facts(body, kind, mid=MID):
    return [e.payload for e in body.journal.replay(kind) if e.payload.get("mission_id") == mid]


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


# -- a compensation the Gate dispatched and the body did not record ----------------------------------------------

CMID = "m:history-compensation"
RESTORE = {"capability": "fs.write", "params": {"relative_path": "note.txt", "content": "original"},
           "target": "workspace:note.txt"}
# a signed compensation the fs.write adapter refuses: its path does not name its signed target
BROKEN = {"capability": "fs.write", "params": {"relative_path": "other.txt", "content": "original"},
          "target": "workspace:note.txt"}
BROKEN_REASON = "capability refused: write path 'workspace:other.txt' does not match the signed target " \
                "'workspace:note.txt'"
NOT_RECORDED = "retained receipt of a compensation the body did not record before it stopped"
NO_RECEIPT = "dispatch claimed without receipt; the body stopped inside it, so its outcome is unknown"
UNCLASSED = "the receipt does not say whether the capability acted (result class None); its outcome is unknown and " \
            "must be reconciled"
NOT_INSTALLED = "fs.write is not available on this body (test)"


def compensation_run(tmp, monkeypatch, case: str, state: str | None) -> dict:
    """An executed write whose mission the founder abandons, with a compensation signed with it.

    ``case`` is what the Gate holds for the compensation when the body stops: "done" (it ran and restored the file: a
    positive receipt), "refused" (its capability refused it: a negative receipt), "unknown" (the body died inside the
    compensating adapter: a dispatch claim and no receipt), "unclassed" (as "unknown", and a receipt for that dispatch
    whose result names no class), or "never" (the body stopped before the mission was abandoned: the Gate holds
    nothing for the compensation). In every case but "never" the body dies before it records the compensation.

    ``state`` is the compensating capability when the body restarts: None (usable), "detached" (the founder's signed
    detach, applied by the restarted body before its first tick) or "unavailable" (attached, and its manifest says it
    cannot run on this body). The restarted body ticks four times, then restarts twice more."""
    tmp.mkdir()
    home, key, body_id, _ = make_body(tmp)
    note = workspace(home, CMID) / "note.txt"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("original")
    calls, dies = [], {"inside": case in ("unknown", "unclassed")}
    manifest, real = capabilities.BUILTINS["fs.write"]

    def counted(params, ctx):
        calls.append(params.get("content"))
        if dies["inside"] and params.get("content") == "original":
            raise Killed("SIGKILL inside the compensating adapter")
        return real(params, ctx)
    monkeypatch.setitem(capabilities.BUILTINS, "fs.write", (manifest, counted))
    drop(home, signed(key, body_id, "MISSION", mission(
        CMID, checks=[note_check("c", note, "final")], capabilities=["fs.read", "fs.write"],
        strategies=[write_strategy("w", "note.txt", "draft", ["c"],
                                   compensate=BROKEN if case == "refused" else RESTORE)])))
    abandon = signed(key, body_id, "LIFECYCLE", {"mission_id": CMID, "state": "ABANDONED", "reason": "not wanted"})
    clock = Clock()
    with Body(home, clock=clock) as body:
        tick(body, clock, 3)
        assert note.read_text() == "draft" and calls == ["draft"]
        earlier = len(body.ledger.by_type("grant_dispatch"))          # every dispatch before any compensation
        if case != "never":
            drop(home, abandon)
            if case in ("done", "refused"):
                kill_before_record(body, "mission.compensated")
            with pytest.raises(Killed):
                tick(body, clock, 3)
            assert not facts(body, "mission.compensated", CMID), "the body recorded the compensation before it died"
            assert len(body.ledger.by_type("grant_dispatch")) == earlier + 1   # the Gate claimed its one dispatch
    if case == "never":
        drop(home, abandon)
    if case == "unclassed":
        with Body(home, clock=clock) as body:   # nothing ticks: only the record another writer or version could leave
            claim = body.ledger.by_type("grant_dispatch")[-1]
            body.ledger.append("receipt", {"action_id": "unclassed", "witness_id": claim.payload["witness_id"],
                                           "grant_id": claim.payload["grant_id"],
                                           "result": {"observed_outcome": "half written"}})
    dies["inside"] = False              # a second run of the compensation would now write, and be counted
    before_restart, seen = len(calls), []

    def kept(body) -> dict:
        records = facts(body, "mission.compensated", CMID)
        asked = [r for r in body.engine.book.requests.values()
                 if r.get("mission_id") == CMID and r["kind"] == "COMPENSATION"]
        claims = body.ledger.by_type("grant_dispatch")[earlier:]
        grants = {c.payload["grant_id"] for c in claims}
        return {"compensated": [(c["status"], c["reasons"], body.ledger.find(c["receipt"]).payload["result"].get(
                                    "result_class", "no class") if c["receipt"] else None) for c in records],
                "asked": [(r["action_id"], r["evidence"]["compensation_failed"]) for r in asked],
                "open_compensation_asks": len([r for r in body.engine.book.open_requests()
                                               if r["kind"] == "COMPENSATION"]),
                "note": note.read_text(), "fs_write": body.registry.state["fs.write"],
                "compensation_claims": len(claims),
                "compensation_receipts": len([r for r in body.ledger.by_type("receipt")
                                              if r.payload["grant_id"] in grants]),
                "status": body.engine.book.missions[CMID].status}
    with monkeypatch.context() as patch:
        if state == "unavailable":
            available = CapabilityManifest.available
            patch.setattr(CapabilityManifest, "available", lambda self: (False, NOT_INSTALLED)
                          if self.capability_id == "fs.write" else available(self))
        for restart in range(3):
            with Body(home, clock=clock) as body:
                if state == "detached" and restart == 0:
                    detach = signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": "fs.write"})
                    assert body.apply(detach)["result"]["state"] == "DETACHED"
                tick(body, clock, 4)
                seen.append(kept(body))
    return {"first": seen[0], "later": seen[1:], "calls_after_restart": calls[before_restart:]}


# case -> (the one mission.compensated record, the COMPENSATION asks ever raised, the note afterwards)
RECORDED_FROM_THE_GATE = {
    "done": ([("DONE", [NOT_RECORDED], "positive")], [], "original"),
    "refused": ([("REFUSED", [BROKEN_REASON], "negative")], [("w", [BROKEN_REASON])], "draft"),
    "unknown": ([("UNCERTAIN", [NO_RECEIPT], None)], [("w", [NO_RECEIPT])], "draft"),
    "unclassed": ([("UNCERTAIN", [UNCLASSED], "no class")], [("w", [UNCLASSED])], "draft"),
}


@pytest.mark.parametrize("state", [None, "detached", "unavailable"])
@pytest.mark.parametrize("case", ["done", "refused", "unknown", "unclassed"])
def test_a_compensation_the_gate_dispatched_is_recorded_from_the_gates_record_whatever_its_capability_is_now(
        tmp_path, monkeypatch, case, state):
    """Before: a compensation was looked for in the Gate's record only by ``office.act``, which is reached only when
    the capability is attached and answers the precheck first. With the capability detached at the restart nothing
    was recorded and the founder was asked about a compensation that "did not complete", though it had completed;
    with it attached and unavailable the record said UNAVAILABLE with no receipt. Now the Gate's record of the
    compensation's own proposal is read first: once, with nothing dispatched, whatever the capability's state is."""
    compensated, asked, note = RECORDED_FROM_THE_GATE[case]
    got = compensation_run(tmp_path / "run", monkeypatch, case, state)
    first = got["first"]
    assert first["fs_write"] == ("DETACHED" if state == "detached" else "ATTACHED")
    assert [c[0] for c in first["compensated"]] == [compensated[0][0]], \
        f"the Gate holds a {case} compensation; the mission recorded {first['compensated']} and asked {first['asked']}"
    assert first["compensated"] == compensated
    assert first["asked"] == asked
    assert first["open_compensation_asks"] == len(asked)
    assert first["note"] == note
    # nothing ran because of it: no adapter call after the restart, the one dispatch claim and what it had kept
    assert got["calls_after_restart"] == []
    assert first["compensation_claims"] == 1
    assert first["compensation_receipts"] == (0 if case == "unknown" else 1)
    # and it is recorded and asked about once: two more restarts and eight more ticks change nothing
    assert got["later"] == [first, first]


@pytest.mark.parametrize("state, compensated, asked, calls, note", [
    (None, [("DONE", [], "positive")], [], ["original"], "original"),
    ("detached", [], [("w", ["compensating capability fs.write is not usable"])], [], "draft"),
    ("unavailable", [("UNAVAILABLE", [NOT_INSTALLED], None)], [("w", [NOT_INSTALLED])], [], "draft"),
])
def test_a_compensation_the_gate_never_dispatched_is_treated_as_it_was_before(
        tmp_path, monkeypatch, state, compensated, asked, calls, note):
    """The Gate's record is read first and holds nothing for this compensation, so nothing changes: it runs when its
    capability can run it, and the founder is asked when the capability is detached or unavailable. These three pass
    before the change that reads the record first."""
    got = compensation_run(tmp_path / "run", monkeypatch, "never", state)
    first = got["first"]
    assert (first["compensated"], first["asked"], first["note"]) == (compensated, asked, note)
    assert got["calls_after_restart"] == calls
    assert first["compensation_claims"] == first["compensation_receipts"] == len(calls)
    assert got["later"] == [first, first]
