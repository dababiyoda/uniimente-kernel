"""More adversarial probes (reviewer's scratch): paid recovery, reconciliation after an unreadable receipt,
a non-worker output that says UNCERTAIN, founder-declined compensation."""
from __future__ import annotations

import pytest

from greg import capabilities
from greg.body import Body
from greg.capabilities import CapabilityManifest
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy

MID = "m:adv2"


class Killed(BaseException):
    pass


def tick(body, clock, n):
    for _ in range(n):
        body.tick()
        clock.advance(1)


def facts(body, kind, mid=MID):
    return [e.payload for e in body.journal.replay(kind) if e.payload.get("mission_id") == mid]


def kill_before_record(body, kind):
    record = body.journal.record

    def dies(name, data, **kw):
        if name == kind:
            raise Killed(f"SIGKILL before {kind}")
        return record(name, data, **kw)
    body.journal.record = dies


def paid_body(adapter, calls):
    class PaidBody(Body):
        def open(self):
            super().open()
            self.registry.register(CapabilityManifest(
                capability_id="test.paid", version="1.0.0", provider="test", function="test.paid",
                description="a paid read (test double)", route="api", consequence_class="read_only",
                inputs={"n": "str"}, outputs={"text": "str"}, strengthens=("proof",), target_prefix="paid:",
                retry_safe=False), adapter, state="ATTACHED")
            return self
    return PaidBody


def paid_run(tmp, kill, output=None):
    tmp.mkdir()
    calls = []

    def adapter(params, ctx):
        calls.append(params)
        return output or {"text": "paid for"}
    home, key, body_id, _ = make_body(tmp)
    home_data = tmp / "data"
    note = home_data / "note.txt"
    spec = mission(MID, checks=[note_check("c", note, "never")],
                   strategies=[{"action_id": "p", "capability": "test.paid", "params": {"n": "1"}, "target": "paid:x",
                                "advances": ["c"], "rationale": "pay once", "cost_usd": 0.25}],
                   capabilities=["fs.read", "test.paid"], targets=("fs:*", "paid:*"), budget=1.0)
    drop(home, signed(key, body_id, "MISSION", spec))
    TheBody, clock = paid_body(adapter, calls), Clock()
    with TheBody(home, clock=clock) as body:
        if kill:
            kill_before_record(body, "mission.action")
            try:
                tick(body, clock, 3)
            except Killed:
                pass
        else:
            tick(body, clock, 3)
        asks_ = sorted(r["kind"] for r in body.engine.book.open_requests())
    with TheBody(home, clock=clock) as body:
        tick(body, clock, 3)
        m = body.engine.book.missions[MID]
        return {"actions": [(a["action_id"], a["attempt"], a["status"], a["cost_usd"]) for a in facts(body, "mission.action")],
                "spent": m.spent_usd, "reserved": m.reserved_usd, "calls": len(calls),
                "asks": sorted(r["kind"] for r in body.engine.book.open_requests()), "asks_before": asks_}


def test_q1_a_recovered_receipt_of_a_paid_action_books_its_signed_cost(tmp_path, capsys):
    control = paid_run(tmp_path / "control", False)
    killed = paid_run(tmp_path / "killed", True)
    with capsys.disabled():
        print("\nQ1 control", control, "\nQ1 killed ", killed)
    assert control["calls"] == 1, control
    assert killed["calls"] == 1
    assert killed["spent"] == control["spent"] and [a[3] for a in killed["actions"]] == [a[3] for a in control["actions"]]


def test_q3_a_completed_non_worker_output_that_says_uncertain_is_still_done(tmp_path, capsys):
    control = paid_run(tmp_path / "control", False, output={"text": "x", "status": "UNCERTAIN"})
    killed = paid_run(tmp_path / "killed", True, output={"text": "x", "status": "UNCERTAIN"})
    with capsys.disabled():
        print("\nQ3 control", control, "\nQ3 killed ", killed)
    assert [a[2] for a in control["actions"]][:1] == ["DONE"] and [a[2] for a in killed["actions"]][:1] == ["DONE"]


@pytest.mark.parametrize("answer", ["reconcile_executed", "reconcile_not_executed"])
def test_q6_an_unreadable_receipt_is_reconciled_by_the_founder_and_nothing_loops(tmp_path, monkeypatch, capsys, answer):
    home, key, body_id, _ = make_body(tmp_path)
    note = workspace(home, MID) / "note.txt"
    calls = []
    manifest, real = capabilities.BUILTINS["fs.write"]

    def counted(params, ctx):
        calls.append(params.get("relative_path"))
        if len(calls) == 1:
            raise Killed("SIGKILL inside the adapter")
        return real(params, ctx)
    monkeypatch.setitem(capabilities.BUILTINS, "fs.write", (manifest, counted))
    drop(home, signed(key, body_id, "MISSION", mission(
        MID, checks=[note_check("c", note, "draft")], strategies=[write_strategy("w", "note.txt", "draft", ["c"])],
        capabilities=["fs.read", "fs.write"])))
    clock = Clock()
    with Body(home, clock=clock) as body:
        with pytest.raises(Killed):
            tick(body, clock, 3)
        claim = body.ledger.by_type("grant_dispatch")[-1]
        body.ledger.append("receipt", {"action_id": "unclassed", "witness_id": claim.payload["witness_id"],
                                       "grant_id": claim.payload["grant_id"], "result": {"observed_outcome": "half"}})
    with Body(home, clock=clock) as body:
        tick(body, clock, 4)
        asks_ = [r for r in body.engine.book.open_requests() if r["kind"] == "RECONCILIATION"]
        assert len(asks_) == 1, [r["kind"] for r in body.engine.book.open_requests()]
        drop(home, signed(key, body_id, "DECISION", {"request_id": asks_[0]["request_id"], "answer": answer,
                                                     "reason": "looked"}))
        tick(body, clock, 6)
    with Body(home, clock=clock) as body:
        tick(body, clock, 6)
        acts = [(a["attempt"], a["status"], a.get("route"), bool(a.get("receipt"))) for a in facts(body, "mission.action")]
        out = {"actions": acts, "calls": calls, "claims": len([c for c in body.ledger.by_type("grant_dispatch")
                                                               if c.payload["proposal_id"] in
                                                               {i["proposal_id"] for i in facts(body, "mission.dispatching")}]),
               "status": body.engine.book.missions[MID].status, "note": note.read_text() if note.exists() else None,
               "asks": sorted(r["kind"] for r in body.engine.book.open_requests())}
    with capsys.disabled():
        print(f"\nQ6 {answer}:", out)
    if answer == "reconcile_executed":
        assert out["calls"] == ["note.txt"], "an act the founder said executed was dispatched again"
    else:
        assert out["calls"] == ["note.txt", "note.txt"] and out["note"] == "draft"


RESTORE = {"capability": "fs.write", "params": {"relative_path": "note.txt", "content": "original"},
           "target": "workspace:note.txt"}


def test_q4_a_compensation_the_founder_declined_is_not_asked_about_again(tmp_path, capsys):
    """SUPERSEDED: the compensation needs an exact-scope approval; the founder rejects it -> DECLINED (settled)."""
    home, key, body_id, _ = make_body(tmp_path)
    note = workspace(home, MID) / "note.txt"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("original")
    drop(home, signed(key, body_id, "MISSION", mission(
        MID, checks=[note_check("c", note, "final")],
        strategies=[write_strategy("w", "note.txt", "draft", ["c"], compensate=RESTORE)],
        capabilities=["fs.read", "fs.write"])))
    clock = Clock()
    with Body(home, clock=clock) as body:
        tick(body, clock, 3)
        drop(home, signed(key, body_id, "LIFECYCLE", {"mission_id": MID, "state": "SUPERSEDED", "reason": "replaced"}))
        tick(body, clock, 3)
        approval = [r for r in body.engine.book.open_requests() if r["kind"] == "APPROVAL"]
        assert len(approval) == 1, [r["kind"] for r in body.engine.book.open_requests()]
        drop(home, signed(key, body_id, "DECISION", {"request_id": approval[0]["request_id"], "answer": "reject",
                                                     "reason": "the successor needs it"}))
        tick(body, clock, 4)
    with Body(home, clock=clock) as body:
        tick(body, clock, 6)
        comp = [(c["status"], c["reasons"]) for c in facts(body, "mission.compensated")]
        kinds = [e.payload["kind"] for e in body.journal.replay("decision.requested")]
    with capsys.disabled():
        print("\nQ4:", comp, kinds, note.read_text())
    assert [c[0] for c in comp] == ["DECLINED"] and "COMPENSATION" not in kinds and note.read_text() == "draft"
