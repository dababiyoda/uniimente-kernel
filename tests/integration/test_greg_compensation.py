"""Compensation obligations when a mission is abandoned or superseded with executed effects (Defect 7).

An abandoned mission's executed workspace write is undone by the compensating action signed with its
strategy, through the same AuthorityOffice/Gate path as every action and bound to the original receipt,
exactly once across restarts. An external effect with no signed compensation becomes one founder
COMPENSATION decision and nothing is executed for it. The founder key is a per-test key, not Alfonso's;
the external_contact capability is a test double that contacts no one.
"""
from datetime import datetime, timedelta, timezone
import time

import pytest

from greg import asks
from greg.body import Body
from greg.capabilities import CapabilityManifest
from greg.missions import MissionError, validate_mission
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy

RESTORE = {"capability": "fs.write", "params": {"relative_path": "note.txt", "content": "original"},
           "target": "workspace:note.txt"}
CONTACT = CapabilityManifest(
    capability_id="test.contact", version="1.0.0", provider="test-double", function="test.contact",
    description="test double of an external contact: it contacts no one", route="api",
    consequence_class="external_contact", inputs={"to": "str"}, outputs={"sent": "bool"},
    target_prefix="test-contact:", strengthens=("settlement",))


def tick(body, clock, n):
    for _ in range(n):
        body.tick()
        clock.advance(1)


def facts(body, kind, mid):
    return [e.payload for e in body.journal.replay(kind) if e.payload.get("mission_id") == mid]


def dispatches(body):
    return len(body.ledger.by_type("grant_dispatch"))


def abandon(home, key, body_id, mid, state="ABANDONED"):
    drop(home, signed(key, body_id, "LIFECYCLE", {"mission_id": mid, "state": state, "reason": "not wanted"}))


def write_mission(home, mid, *, check_text, strategies=None, closure=None):
    note = workspace(home, mid) / "note.txt"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("original")
    return note, mission(mid, checks=[note_check("c", note, check_text)], closure=closure,
                         strategies=strategies or [write_strategy("w", "note.txt", "draft", ["c"], compensate=RESTORE)],
                         capabilities=["fs.read", "fs.write"])


@pytest.mark.parametrize("state", ["ABANDONED", "SUPERSEDED"])
def test_an_abandoned_write_is_compensated_once_through_the_gate_and_never_repeated(tmp_path, state):
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:compensate-write"
    note, spec = write_mission(home, mid, check_text="final")       # the write never closes the mission
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        tick(body, clock, 3)
        [done] = [a for a in facts(body, "mission.action", mid) if a["status"] == "DONE"]
        assert note.read_text() == "draft" and not facts(body, "mission.compensated", mid)
        abandon(home, key, body_id, mid, state)
        tick(body, clock, 3)
        if state == "SUPERSEDED":
            # A successor may rely on the effect: the signed compensation runs only on an exact-scope approval.
            [request] = [r for r in body.engine.book.open_requests() if r["kind"] == "APPROVAL"]
            assert request["action_id"] == "w" and "superseded" in request["why_now"]
            assert note.read_text() == "draft" and not facts(body, "mission.compensated", mid)
            drop(home, signed(key, body_id, "DECISION", {"request_id": request["request_id"], "answer": "approve",
                                                         "reason": "the successor does not need it"}))
            tick(body, clock, 2)
        [required] = facts(body, "mission.compensation_required", mid)
        [compensated] = facts(body, "mission.compensated", mid)
        assert required["action_id"] == "w" and required["consequence_class"] == "internal_write"
        assert required["lifecycle"] == state
        assert required["original_receipt"] == compensated["original_receipt"] == done["receipt"]
        assert compensated["status"] == "DONE" and compensated["receipt"] not in (None, done["receipt"])
        assert note.read_text() == "original"                        # restored per the signed compensation
        receipt = body.ledger.find(compensated["receipt"])
        [witness] = [w for w in body.ledger.by_type("witness")
                     if w.payload["witness_id"] == receipt.payload["witness_id"]]
        assert done["receipt"] in witness.payload["evidence_refs"]   # the Gate bound the original receipt
        assert not [r for r in body.engine.book.open_requests() if r["kind"] == "COMPENSATION"]
        before = dispatches(body)
    note.write_text("edited after compensation")
    with Body(home, clock=clock) as body:                             # a restart does not compensate again
        tick(body, clock, 3)
        assert len(facts(body, "mission.compensated", mid)) == 1 and dispatches(body) == before
        assert len(facts(body, "mission.compensation_required", mid)) == 1
    assert note.read_text() == "edited after compensation"


def test_a_compensation_outside_the_scope_by_then_runs_only_after_an_exact_scope_approval(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:compensate-late"
    note, spec = write_mission(home, mid, check_text="final")
    horizon = datetime.now(timezone.utc) + timedelta(seconds=4)     # the Gate judges the horizon on the wall clock
    spec["light_cone"]["horizon"] = horizon.isoformat().replace("+00:00", "Z")
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        tick(body, clock, 3)
        assert note.read_text() == "draft"
        while datetime.now(timezone.utc) <= horizon:
            time.sleep(0.1)
        abandon(home, key, body_id, mid)
        tick(body, clock, 2)
        [request] = [r for r in body.engine.book.open_requests() if r["kind"] == "APPROVAL"]
        assert request["action_id"] == "w" and "horizon" in request["why_now"]
        assert note.read_text() == "draft" and not facts(body, "mission.compensated", mid)
        drop(home, signed(key, body_id, "DECISION", {"request_id": request["request_id"], "answer": "approve",
                                                     "reason": "undo it"}))
        tick(body, clock, 2)
        [compensated] = facts(body, "mission.compensated", mid)
        assert compensated["status"] == "DONE" and compensated["scope_digest"] == request["scope_digest"]
    assert note.read_text() == "original"


def test_an_uncompensable_external_effect_is_put_to_the_founder_and_nothing_runs(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:compensate-contact"
    calls = []
    note = workspace(home, mid) / "reply.txt"
    drop(home, signed(key, body_id, "MISSION", mission(
        mid, checks=[note_check("c", note, "reply")], ceiling="external_contact",
        targets=("fs:*", "workspace:*", "test-contact:*"), capabilities=["fs.read", "test.contact"],
        strategies=[{"action_id": "contact", "capability": "test.contact", "params": {"to": "nobody"},
                     "target": "test-contact:nobody", "advances": ["c"], "rationale": "test double contact"}])))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.registry.register(CONTACT, lambda params, ctx: calls.append(params) or {"sent": False}, state="ATTACHED")
        tick(body, clock, 3)
        assert len(calls) == 1 and [a["status"] for a in facts(body, "mission.action", mid)] == ["DONE"]
        before = dispatches(body)
        abandon(home, key, body_id, mid)
        tick(body, clock, 3)
        [required] = facts(body, "mission.compensation_required", mid)
        assert required["consequence_class"] == "external_contact" and required["compensate"] is None
        assert required["reason"].startswith("no compensation declared")
        [request] = [r for r in body.engine.book.open_requests() if r["kind"] == "COMPENSATION"]
        assert request["action_id"] == "contact"
        assert request["evidence"]["original_receipt"] == required["original_receipt"]
        asks.validate(request)
        assert "answer_effect" in asks.surface(request) and "wording_withheld" not in request
        assert len(calls) == 1 and dispatches(body) == before and not facts(body, "mission.compensated", mid)


def test_a_failed_compensation_is_put_to_the_founder_and_never_blind_retried(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:compensate-fails"
    broken = {**RESTORE, "params": {"relative_path": "note.txt", "content": 7}}   # fs.write refuses non-text
    note, spec = write_mission(home, mid, check_text="final",
                               strategies=[write_strategy("w", "note.txt", "draft", ["c"], compensate=broken)])
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        tick(body, clock, 3)
        abandon(home, key, body_id, mid)
        tick(body, clock, 3)
        [compensated] = facts(body, "mission.compensated", mid)
        [request] = [r for r in body.engine.book.open_requests() if r["kind"] == "COMPENSATION"]
        assert compensated["status"] == "REFUSED" and request["evidence"]["compensation_failed"]
        before = dispatches(body)
    with Body(home, clock=clock) as body:
        tick(body, clock, 3)
        assert len(facts(body, "mission.compensated", mid)) == 1 and dispatches(body) == before
    assert note.read_text() == "draft"


def test_an_internal_write_without_a_signed_compensation_stays_an_open_obligation(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:compensate-none"
    note, spec = write_mission(home, mid, check_text="final",
                               strategies=[write_strategy("w", "note.txt", "draft", ["c"])])
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        tick(body, clock, 3)
        abandon(home, key, body_id, mid)
        tick(body, clock, 3)
        [required] = facts(body, "mission.compensation_required", mid)
        assert required["reason"] == "no compensation declared" and not facts(body, "mission.compensated", mid)
        assert not [r for r in body.engine.book.open_requests() if r["kind"] == "COMPENSATION"]
    assert note.read_text() == "draft"


def test_a_compensation_outside_the_light_cone_is_refused_at_registration(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    _, spec = write_mission(home, "m:compensate-escape", check_text="final", strategies=[
        write_strategy("w", "note.txt", "draft", ["c"], compensate={**RESTORE, "target": "deliver:note.txt"})])
    with pytest.raises(MissionError, match="compensation"):
        validate_mission(spec)
    _, spec = write_mission(home, "m:compensate-class", check_text="final", strategies=[
        write_strategy("w", "note.txt", "draft", ["c"], compensate={
            "capability": "test.contact", "params": {"to": "x"}, "target": "workspace:x"})])
    spec["light_cone"]["capabilities"].append("test.contact")
    with Body(home) as body:
        body.registry.register(CONTACT, lambda params, ctx: {"sent": False}, state="ATTACHED")
        with pytest.raises(MissionError, match="external_contact exceeds scope ceiling internal_write"):
            body.engine.register(spec, "sha256:test")


def test_the_abandon_option_states_that_executed_effects_are_compensated_or_escalated(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:compensate-ask"
    _, spec = write_mission(home, mid, check_text="final", strategies=[
        write_strategy("w", "note.txt", "draft", ["c"]),
        {"action_id": "x", "function": "no.such.function", "params": {}, "target": "workspace:note.txt",
         "advances": ["c"], "rationale": "a function this body lacks"}])
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        tick(body, clock, 4)
        [request] = [r for r in body.engine.book.open_requests() if r["kind"] == "CAPABILITY_ATTACH"]
    asks.validate(request)
    [option] = [o for o in request["options"] if o["option"] == "abandon"]
    assert option["cost"].startswith("none in money") and "1 executed effect" in option["cost"]
    assert "compensat" in option["expected_effect"]


def test_the_appraisal_counts_compensating_receipts_in_its_exactly_once_check(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:compensate-held"
    note, spec = write_mission(home, mid, check_text="draft", closure={"kind": "infinite", "cadence_seconds": 60})
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        tick(body, clock, 3)
        [held] = [e for e in body.journal.replay("mission.held") if e.payload["mission_id"] == mid]
        abandon(home, key, body_id, mid)
        tick(body, clock, 2)
        [compensated] = facts(body, "mission.compensated", mid)
        assert note.read_text() == "original"
        verdict = body.appraise(mid, closure_event=held.event_id)
        assert verdict["checks"]["exactly_once"] is True
        # a second compensation of the same action, presenting the original receipt as its own
        body.journal.record("mission.compensated", {**compensated, "receipt": compensated["original_receipt"]},
                            key=[mid, "w", "forged"])
        verdict = body.appraise(mid, closure_event=held.event_id)
    assert verdict["checks"]["exactly_once"] is False
    assert any("compensat" in f for f in verdict["findings"])


def test_a_signed_compensation_never_runs_after_the_founder_answered_its_compensation_ask(tmp_path):
    """Third review (spend): the compensating capability was detached, so the founder was asked; the founder
    answered 'the effect stands'; once the capability was re-attached for other work the compensation ran
    anyway. The founder's answer now closes the obligation."""
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:compensate-answered"
    note, spec = write_mission(home, mid, check_text="final")
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        tick(body, clock, 3)
        drop(home, signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": "fs.write"}))
        tick(body, clock, 1)
        abandon(home, key, body_id, mid)
        tick(body, clock, 2)
        [ask] = [r for r in body.engine.book.open_requests() if r["kind"] == "COMPENSATION"]
        drop(home, signed(key, body_id, "DECISION", {"request_id": ask["request_id"], "answer": "reject",
                                                     "reason": "the effect stands"}))
        tick(body, clock, 1)
        drop(home, signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": "fs.write"}))
        tick(body, clock, 2)
        [closed] = facts(body, "mission.compensated", mid)
        assert closed["status"] == "FOUNDER_DECIDED" and closed["answer"] == "reject" and closed["receipt"] is None
    assert note.read_text() == "draft"


def test_compensations_dispatch_one_per_step_and_a_stop_mid_tick_admits_no_more(tmp_path):
    """Third review (spend): every signed compensation of a mission dispatched in one step, past a founder STOP
    that arrived while the first ran. One compensation is dispatched per step, under the tick's STOP check."""
    stopper = CapabilityManifest(
        capability_id="test.undo", version="1.0.0", provider="test-double", function="test.undo",
        description="test double of a slow undo during which the founder presses STOP", route="api",
        consequence_class="internal_write", inputs={"x": "str"}, outputs={"ok": "bool"},
        target_prefix="workspace:", strengthens=("settlement",))
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:compensate-stop"
    ws = workspace(home, mid)
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "a.txt").write_text("original")
    restore_a = {"capability": "fs.write", "params": {"relative_path": "a.txt", "content": "original"},
                 "target": "workspace:a.txt"}
    undo_b = {"capability": "test.undo", "params": {"x": "b"}, "target": "workspace:b.txt"}
    spec = mission(mid, checks=[note_check("c", ws / "a.txt", "final"), note_check("d", ws / "b.txt", "final")],
                   strategies=[write_strategy("a", "a.txt", "draft", ["c"], compensate=restore_a),
                               write_strategy("b", "b.txt", "draft", ["d"], compensate=undo_b)],
                   capabilities=["fs.read", "fs.write", "test.undo"])
    clock = Clock()
    with Body(home, clock=clock) as body:
        stop_file = body.layout.stop_file

        def undo(params, ctx):
            stop_file.write_text("founder STOP")                   # pressed while this undo runs
            return {"ok": True}
        body.registry.register(stopper, undo, state="ATTACHED")
        drop(home, signed(key, body_id, "MISSION", spec))
        tick(body, clock, 6)
        abandon(home, key, body_id, mid)
        body.tick()
        assert [(c["action_id"], c["status"]) for c in facts(body, "mission.compensated", mid)] == [("b", "DONE")]
    assert (ws / "a.txt").read_text() == "draft"                  # nothing ran after the STOP


def test_a_compensation_through_a_capability_that_spends_money_is_refused_at_signing():
    """Third review (spend): compensation runs at cost 0, so a metered capability (worker.commission) could
    spend unbooked money after the cone was exhausted. Such a compensation is refused when the mission is
    validated; the founder handles that effect through a COMPENSATION decision instead."""
    from pathlib import Path
    spec = mission("m:paid-undo", checks=[note_check("c", Path("/nonexistent/note.txt"), "final")],
                   strategies=[write_strategy(
        "w", "note.txt", "draft", ["c"], compensate={"capability": "worker.commission", "params": {},
                                                     "target": "workspace:undo"})],
        capabilities=["fs.read", "fs.write", "worker.commission"], ceiling="internal_write")
    with pytest.raises(MissionError, match="spends money"):
        validate_mission(spec)


def test_a_compensation_waits_for_the_founder_once_asked_even_if_its_capability_returns(tmp_path):
    """Fix verification (closure 7): once a COMPENSATION ask promised that nothing runs, re-attaching the
    compensating capability before the founder answered still ran the compensation."""
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:compensate-reattached"
    note, spec = write_mission(home, mid, check_text="final")
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        tick(body, clock, 3)
        drop(home, signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": "fs.write"}))
        tick(body, clock, 1)
        abandon(home, key, body_id, mid)
        tick(body, clock, 2)
        [ask] = [r for r in body.engine.book.open_requests() if r["kind"] == "COMPENSATION"]
        drop(home, signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": "fs.write"}))
        tick(body, clock, 2)
        assert note.read_text() == "draft" and not facts(body, "mission.compensated", mid)
        drop(home, signed(key, body_id, "DECISION", {"request_id": ask["request_id"], "answer": "approve",
                                                     "reason": "I undid it myself"}))
        tick(body, clock, 2)
        [closed] = facts(body, "mission.compensated", mid)
        assert closed["status"] == "FOUNDER_DECIDED"
    assert note.read_text() == "draft"


def test_an_overrun_cone_does_not_stop_a_free_compensation(tmp_path):
    """Fix verification (closure 6): a founder-approved overrun left the cone spent, and every compensation
    was then refused on budget with a false reason. Compensation is unpaid by construction."""
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:compensate-overrun"
    note = workspace(home, mid) / "note.txt"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("original")
    spec = mission(mid, checks=[note_check("c", note, "final")], budget=0.5,
                   strategies=[write_strategy("w", "note.txt", "draft", ["c"], cost_usd=1.0, compensate=RESTORE)],
                   capabilities=["fs.read", "fs.write"])
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        tick(body, clock, 2)
        [approval] = [r for r in body.engine.book.open_requests() if r["kind"] == "APPROVAL"]
        drop(home, signed(key, body_id, "DECISION", {"request_id": approval["request_id"], "answer": "approve",
                                                     "reason": "worth the overrun"}))
        tick(body, clock, 3)
        assert note.read_text() == "draft" and body.engine.book.missions[mid].spent_usd == 1.0
        abandon(home, key, body_id, mid)
        tick(body, clock, 3)
        [compensated] = facts(body, "mission.compensated", mid)
        assert compensated["status"] == "DONE"
        assert not [r for r in body.engine.book.open_requests() if r["kind"] == "APPROVAL"]
    assert note.read_text() == "original"


@pytest.mark.parametrize("same_tick", [True, False])
def test_an_interrupted_dispatch_is_reconciled_before_anything_is_compensated(tmp_path, same_tick):
    """Fix verification (closure 10): an answer arriving with or after the abandon was never recorded, so the
    executed effect was neither compensated nor put to the founder. Compensation now waits for the answer,
    which is recorded even for an ended mission."""
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:compensate-uncertain"
    note, spec = write_mission(home, mid, check_text="final")
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        real, calls = body.registry.adapters["fs.write"], []

        def adapter(params, ctx):        # the write lands, then power is lost before the receipt
            calls.append(1)
            out = real(params, ctx)
            if len(calls) == 1:
                raise RuntimeError("power lost after the write")
            return out
        body.registry.adapters["fs.write"] = adapter
        tick(body, clock, 3)
        [request] = [r for r in body.engine.book.open_requests() if r["kind"] == "RECONCILIATION"]
        answer = signed(key, body_id, "DECISION", {"request_id": request["request_id"],
                                                   "answer": "reconcile_executed", "reason": "it landed"})
        if same_tick:
            drop(home, answer)
            abandon(home, key, body_id, mid)
        else:
            abandon(home, key, body_id, mid)
            tick(body, clock, 2)
            assert not facts(body, "mission.compensated", mid) and note.read_text() == "draft"
            drop(home, answer)
        tick(body, clock, 3)
        [compensated] = facts(body, "mission.compensated", mid)
        assert compensated["status"] == "DONE"
    assert note.read_text() == "original"


def test_a_self_spending_compensation_signed_before_the_check_is_refused_when_it_would_run(tmp_path, monkeypatch):
    """Fix verification (closure 9): the signing check does not reach missions signed before it existed; the
    run-time path refuses a self-spending compensating capability too, and puts the effect to the founder."""
    from greg import missions as missions_mod
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:compensate-metered"
    note, spec = write_mission(home, mid, check_text="final", strategies=[write_strategy(
        "w", "note.txt", "draft", ["c"], compensate={"capability": "fs.write",
                                                     "params": {"relative_path": "note.txt", "content": "original"},
                                                     "target": "workspace:note.txt"})])
    monkeypatch.setattr(missions_mod, "METERED_SPEND", {})            # as signed before the signing check
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        tick(body, clock, 3)
        monkeypatch.setattr(missions_mod, "METERED_SPEND", {"fs.write": "written"})   # fs.write stands in as metered
        abandon(home, key, body_id, mid)
        tick(body, clock, 2)
        [ask] = [r for r in body.engine.book.open_requests() if r["kind"] == "COMPENSATION"]
        assert "spends money by itself" in str(ask.get("evidence"))
    assert note.read_text() == "draft"
