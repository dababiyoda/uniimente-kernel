"""Adversarial probes of claude/retained-negative-receipt-20261111 (reviewer's scratch; not for the branch).
Each test prints what it observed; an assertion is what the change's own stated rule would require."""
from __future__ import annotations

import collections

import pytest

from greg import capabilities
from greg.body import Body
from greg.missions import MissionEngine
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy


class Killed(BaseException):
    pass


def tick(body, clock, n):
    for _ in range(n):
        body.tick()
        clock.advance(1)


def facts(body, kind, mid):
    return [e.payload for e in body.journal.replay(kind) if e.payload.get("mission_id") == mid]


def kill_before_record(body, kind):
    record = body.journal.record

    def dies(name, data, **kw):
        if name == kind:
            raise Killed(f"SIGKILL before {kind}")
        return record(name, data, **kw)
    body.journal.record = dies


def census(body):
    c = collections.Counter()
    for r in body.ledger.records() if hasattr(body.ledger, "records") else []:
        c[r.record_type] += 1
    return c


def ledger_len(body):
    return sum(len(body.ledger.by_type(t)) for t in ("event", "receipt", "grant_dispatch", "witness", "outcome"))


def kinds(body):
    c = collections.Counter(e.type for e in body.journal.replay(""))
    return c


BROKEN = {"capability": "fs.write", "params": {"relative_path": "other.txt", "content": "original"},
          "target": "workspace:note.txt"}
RESTORE = {"capability": "fs.write", "params": {"relative_path": "note.txt", "content": "original"},
           "target": "workspace:note.txt"}


def setup(tmp, compensate, mid="m:adv"):
    home, key, body_id, data = make_body(tmp)
    note = workspace(home, mid) / "note.txt"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("original")
    spec = mission(mid, checks=[note_check("c", note, "final")],
                   strategies=[write_strategy("w", "note.txt", "draft", ["c"], compensate=compensate)],
                   capabilities=["fs.read", "fs.write"])
    drop(home, signed(key, body_id, "MISSION", spec))
    return home, key, body_id, note, mid


def abandon(home, key, body_id, mid, state="ABANDONED"):
    drop(home, signed(key, body_id, "LIFECYCLE", {"mission_id": mid, "state": state, "reason": "not wanted"}))


# ---------------------------------------------------------------------------------------------------------------
def test_p1_refused_compensation_many_ticks_and_restarts_no_flood_then_answer(tmp_path, capsys):
    home, key, body_id, note, mid = setup(tmp_path, BROKEN)
    clock = Clock()
    with Body(home, clock=clock) as body:
        tick(body, clock, 3)
        abandon(home, key, body_id, mid)
        kill_before_record(body, "mission.compensated")
        with pytest.raises(Killed):
            tick(body, clock, 3)
    with Body(home, clock=clock) as body:
        tick(body, clock, 3)
        base_kinds, base_len = kinds(body), ledger_len(body)
        comp = facts(body, "mission.compensated", mid)
        asks_ = [r for r in body.engine.book.open_requests() if r["kind"] == "COMPENSATION"]
        assert [c["status"] for c in comp] == ["REFUSED"] and len(asks_) == 1
    for _ in range(3):                      # three more restarts, 20 ticks each
        with Body(home, clock=clock) as body:
            tick(body, clock, 20)
            now_kinds, now_len = kinds(body), ledger_len(body)
    grown = {k: now_kinds[k] - base_kinds.get(k, 0) for k in now_kinds if now_kinds[k] != base_kinds.get(k, 0)}
    with capsys.disabled():
        print("\nP1 growth over 60 ticks / 3 restarts (unanswered ask):", grown, "ledger", base_len, "->", now_len)
    assert not {k: v for k, v in grown.items() if k.startswith(("greg.decision", "greg.mission.comp"))}
    rid = asks_[0]["request_id"]
    drop(home, signed(key, body_id, "DECISION", {"request_id": rid, "answer": "approve", "reason": "handled it"}))
    with Body(home, clock=clock) as body:
        tick(body, clock, 3)
        mid_kinds = kinds(body)
    for _ in range(2):
        with Body(home, clock=clock) as body:
            tick(body, clock, 20)
            end_kinds = kinds(body)
            comp = facts(body, "mission.compensated", mid)
            open_ = [r["kind"] for r in body.engine.book.open_requests()]
            asked = [e.payload["kind"] for e in body.journal.replay("decision.requested")]
    grown = {k: end_kinds[k] - mid_kinds.get(k, 0) for k in end_kinds if end_kinds[k] != mid_kinds.get(k, 0)}
    with capsys.disabled():
        print("P1 after answer: growth over 40 ticks:", grown, "| compensated:", [(c["status"]) for c in comp],
              "| open asks:", open_, "| all asks:", asked)
    assert [c["status"] for c in comp] == ["REFUSED"]
    assert asked.count("COMPENSATION") == 1
    assert "COMPENSATION" not in open_


def test_p2_positive_compensation_killed_before_record_is_done_once(tmp_path, monkeypatch, capsys):
    calls = []
    manifest, real = capabilities.BUILTINS["fs.write"]

    def counted(params, ctx):
        calls.append((params.get("relative_path"), params.get("content")))
        return real(params, ctx)
    monkeypatch.setitem(capabilities.BUILTINS, "fs.write", (manifest, counted))
    home, key, body_id, note, mid = setup(tmp_path, RESTORE)
    clock = Clock()
    with Body(home, clock=clock) as body:
        tick(body, clock, 3)
        assert note.read_text() == "draft"
        abandon(home, key, body_id, mid)
        kill_before_record(body, "mission.compensated")
        with pytest.raises(Killed):
            tick(body, clock, 3)
        assert note.read_text() == "original"
    note.write_text("changed by someone after the compensation")     # a second run would overwrite this
    with Body(home, clock=clock) as body:
        tick(body, clock, 5)
        comp = facts(body, "mission.compensated", mid)
        open_ = [r["kind"] for r in body.engine.book.open_requests()]
    with capsys.disabled():
        print("\nP2:", [(c["status"], c["reasons"]) for c in comp], calls, note.read_text(), open_)
    assert [(c["status"], c["reasons"]) for c in comp] == [("DONE", ["retained receipt reused after restart"])]
    assert calls == [("note.txt", "draft"), ("note.txt", "original")]
    assert note.read_text() == "changed by someone after the compensation"
    assert "COMPENSATION" not in open_


@pytest.mark.parametrize("unclassed", [False, True])
def test_p3_compensation_killed_inside_adapter_is_uncertain_asked_and_never_rerun(tmp_path, monkeypatch, capsys, unclassed):
    calls = []
    manifest, real = capabilities.BUILTINS["fs.write"]

    def counted(params, ctx):
        calls.append((params.get("relative_path"), params.get("content")))
        if params.get("content") == "original":
            raise Killed("SIGKILL inside the compensating adapter")
        return real(params, ctx)
    monkeypatch.setitem(capabilities.BUILTINS, "fs.write", (manifest, counted))
    home, key, body_id, note, mid = setup(tmp_path, RESTORE)
    clock = Clock()
    with Body(home, clock=clock) as body:
        tick(body, clock, 3)
        abandon(home, key, body_id, mid)
        with pytest.raises(Killed):
            tick(body, clock, 3)
        claims = body.ledger.by_type("grant_dispatch")
        if unclassed:
            body.ledger.append("receipt", {"action_id": "x", "witness_id": claims[-1].payload["witness_id"],
                                           "grant_id": claims[-1].payload["grant_id"],
                                           "result": {"observed_outcome": "half"}})
    n_claims = len(claims)
    for _ in range(2):
        with Body(home, clock=clock) as body:
            tick(body, clock, 6)
            comp = facts(body, "mission.compensated", mid)
            open_ = [(r["kind"], (r.get("evidence") or {}).get("compensation_failed")) for r in body.engine.book.open_requests()]
            claims_after = len(body.ledger.by_type("grant_dispatch"))
    with capsys.disabled():
        print("\nP3 unclassed=%s:" % unclassed, [(c["status"], c["reasons"], bool(c["receipt"])) for c in comp], open_, calls)
    assert [c["status"] for c in comp] == ["UNCERTAIN"]
    assert claims_after == n_claims and len([c for c in calls if c[1] == "original"]) == 1
    assert [k for k, _ in open_].count("COMPENSATION") == 1


@pytest.mark.parametrize("compensate, kept", [(RESTORE, "positive"), (BROKEN, "negative")])
@pytest.mark.parametrize("detach", [False, True])
def test_p5_compensation_history_against_a_detach(tmp_path, capsys, compensate, kept, detach):
    """The branch's history file says: what happened before a detach is recorded as it was. For compensations?"""
    home, key, body_id, note, mid = setup(tmp_path, compensate)
    clock = Clock()
    with Body(home, clock=clock) as body:
        tick(body, clock, 3)
        abandon(home, key, body_id, mid)
        kill_before_record(body, "mission.compensated")
        with pytest.raises(Killed):
            tick(body, clock, 3)
        classes = [r.payload["result"]["result_class"] for r in body.ledger.by_type("receipt")]
    if detach:
        drop(home, signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": "fs.write"}))
    with Body(home, clock=clock) as body:
        tick(body, clock, 5)
        comp = facts(body, "mission.compensated", mid)
        open_ = [(r["kind"], (r.get("evidence") or {}).get("compensation_failed")) for r in body.engine.book.open_requests()]
        why = [r["why_now"] for r in body.engine.book.open_requests()]
    with capsys.disabled():
        print(f"\nP5 kept={kept} detach={detach}: receipts {classes[-1:]} note={note.read_text()!r} compensated="
              f"{[(c['status'], c['reasons']) for c in comp]} open={open_} why={why}")
    if kept == "positive":
        assert [c["status"] for c in comp] == ["DONE"], "a completed compensation is not on the record as done"
    else:
        assert [c["status"] for c in comp] == ["REFUSED"]


def test_p7_an_uncertain_compensations_lost_question_is_asked_after_the_restart(tmp_path, monkeypatch, capsys):
    """Kill 1: inside the compensating adapter (claim, no receipt). Kill 2: between the UNCERTAIN record and its ask."""
    calls = []
    manifest, real = capabilities.BUILTINS["fs.write"]

    def counted(params, ctx):
        calls.append((params.get("relative_path"), params.get("content")))
        if params.get("content") == "original":
            raise Killed("SIGKILL inside the compensating adapter")
        return real(params, ctx)
    monkeypatch.setitem(capabilities.BUILTINS, "fs.write", (manifest, counted))
    home, key, body_id, note, mid = setup(tmp_path, RESTORE)
    clock = Clock()
    with Body(home, clock=clock) as body:
        tick(body, clock, 3)
        abandon(home, key, body_id, mid)
        with pytest.raises(Killed):
            tick(body, clock, 3)
    real_ask, armed = MissionEngine._compensation_ask, {"on": True}

    def dies(self, *a, **k):
        if armed["on"]:
            armed["on"] = False
            raise Killed("SIGKILL before the ask")
        return real_ask(self, *a, **k)
    monkeypatch.setattr(MissionEngine, "_compensation_ask", dies)
    with Body(home, clock=clock) as body:
        with pytest.raises(Killed):
            tick(body, clock, 3)
        assert [c["status"] for c in facts(body, "mission.compensated", mid)] == ["UNCERTAIN"]
        assert "COMPENSATION" not in [r["kind"] for r in body.engine.book.open_requests()]
    with Body(home, clock=clock) as body:
        tick(body, clock, 4)
        open_ = [(r["kind"], (r.get("evidence") or {}).get("compensation_failed")) for r in body.engine.book.open_requests()]
    with capsys.disabled():
        print("\nP7:", open_, calls)
    assert [k for k, _ in open_].count("COMPENSATION") == 1, "the founder is never asked about the uncertain compensation"
    assert len([c for c in calls if c[1] == "original"]) == 1


def test_p8_killed_twice_in_a_row_first_before_the_record_then_before_the_ask(tmp_path, monkeypatch, capsys):
    home, key, body_id, note, mid = setup(tmp_path, BROKEN)
    clock = Clock()
    with Body(home, clock=clock) as body:
        tick(body, clock, 3)
        abandon(home, key, body_id, mid)
        kill_before_record(body, "mission.compensated")
        with pytest.raises(Killed):
            tick(body, clock, 3)
    with Body(home, clock=clock) as body:                # second kill at the same point
        kill_before_record(body, "mission.compensated")
        with pytest.raises(Killed):
            tick(body, clock, 3)
    real_ask, armed = MissionEngine._compensation_ask, {"on": True}

    def dies(self, *a, **k):
        if armed["on"]:
            armed["on"] = False
            raise Killed("SIGKILL before the ask")
        return real_ask(self, *a, **k)
    monkeypatch.setattr(MissionEngine, "_compensation_ask", dies)
    with Body(home, clock=clock) as body:                # third kill: after the record, before the ask
        with pytest.raises(Killed):
            tick(body, clock, 3)
    with Body(home, clock=clock) as body:
        tick(body, clock, 4)
        comp = [(c["status"], body.ledger.find(c["receipt"]).payload["result"]["result_class"])
                for c in facts(body, "mission.compensated", mid)]
        open_ = sorted(r["kind"] for r in body.engine.book.open_requests())
        negatives = len([r for r in body.ledger.by_type("receipt") if r.payload["result"]["result_class"] == "negative"])
        comp_claims = len([e for e in body.ledger.by_type("event")
                           if e.payload.get("type") == "greg.authority.grant_issued"])
    with capsys.disabled():
        print("\nP8:", comp, open_, "negative receipts", negatives, "grants issued", comp_claims, note.read_text())
    assert comp == [("REFUSED", "negative")] and open_.count("COMPENSATION") == 1 and negatives == 1
