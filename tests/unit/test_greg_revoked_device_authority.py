"""Founder policy 2026-11-11, on a real body: a revoked device's unused authority authorizes no new effect.

"My preferred policy is that revoking a device should immediately invalidate its unused authority to authorize
future execution. Actions already legitimately completed must remain in the evidence ledger. Revocation must not
erase history or pretend an external effect never happened. A suspected key compromise should trigger a separate
retrospective integrity review. Distinguish historical validity of a signature from its continuing authority to
approve a new effect." (docs/intent/sources/REVOKED-DEVICE-AUTHORITY-2026-11-11-source.md)

Every body here is a real ``greg.body.Body`` with its own ledger; every key is a per-test Ed25519 key, never
Alfonso's. The first test is the reproduction: on the integration head 8d205324 the write ran on the revoked
phone's approval.
"""
from datetime import timedelta
import json

import pytest

from greg import asks, goal_gravity
from greg.body import Body, status
from greg.founder import generate_founder_key, key_id, load_founder_key, sign_command, stamp
from greg.missions import MissionBook, MissionError
from provenance.ledger import sha256_json
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, workspace, write_strategy

try:                        # absent on the integration head 8d205324, where this file is copied to show what fails there
    from greg import revocation
except ImportError:
    revocation = None


class World:
    """One body, its founder key, and device keys the founder delegates."""

    def __init__(self, tmp_path):
        self.tmp = tmp_path
        self.home, self.key, self.body_id, _ = make_body(tmp_path)
        self.clock = Clock()
        self.devices = {}

    def body(self) -> Body:
        return Body(self.home, clock=self.clock)

    def sign(self, kind, payload, *, key=None):
        self.clock.advance(1)                       # every command has its own instant, in order
        return sign_command(key or self.key, kind, payload, body_id=self.body_id, now=self.clock())

    def grant(self, name, kinds=("DECISION",)):
        if name not in self.devices:
            public = generate_founder_key(self.tmp / f"{name}.pem", None)
            self.devices[name] = (load_founder_key(self.tmp / f"{name}.pem", None), public)
        return {"public_key": self.devices[name][1], "label": name, "kinds": list(kinds),
                "expires_at": stamp(self.clock() + timedelta(days=30))}

    def enroll(self, body, name, kinds=("DECISION",)):
        body.apply(self.sign("DEVICE_ENROLL", self.grant(name, kinds)))
        return self.devices[name][0]

    def kid(self, name) -> str:
        return key_id(self.devices[name][1])

    def revoke(self, name, **extra):
        return self.sign("DEVICE_REVOKE", {"device_key_id": self.kid(name), **extra})

    def gated(self, body, mid, *, text="approved", **extra):
        """A mission whose only strategy, a workspace write, lies outside its read-only cone: it asks first."""
        note = workspace(self.home, mid) / "n.txt"
        body.apply(self.sign("MISSION", mission(mid, checks=[note_check("n", note, text)],
                                                strategies=[write_strategy("w", "n.txt", text, ["n"], **extra)],
                                                capabilities=["fs.read"], ceiling="read_only",
                                                **({"budget": 1.0} if extra.get("cost_usd") else {}))))
        return note

    def tick(self, body, n=1):
        out = None
        for _ in range(n):
            out = body.tick()
            self.clock.advance(1)
        return out

    def approve(self, rid, *, key=None, answer="approve"):
        return self.sign("DECISION", {"request_id": rid, "answer": answer, "reason": "ok"}, key=key)


def open_asks(body, mid=None, kind="APPROVAL"):
    return [r for r in body.engine.book.open_requests() if r["kind"] == kind and (mid is None or r["mission_id"] == mid)]


def actions(body, mid):
    return [e.payload for e in body.journal.replay("mission.action") if e.payload["mission_id"] == mid]


def trail(body, rid=None):
    return [e.payload for e in body.journal.replay("decision.withdrawn")
            if e.payload.get("voided_by") and (rid is None or e.payload["request_id"] == rid)]


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


def asked(world, body, mid="m:gated", **extra):
    """A gated mission that has asked; returns (note path, the open APPROVAL)."""
    note = world.gated(body, mid, **extra)
    world.tick(body, 2)
    [ask] = open_asks(body, mid)
    return note, ask


# -- a. unused authority authorizes nothing from the revocation on --------------------------------------------------

def test_an_approval_from_a_device_revoked_before_the_act_runs_authorizes_nothing(world):
    """The reproduction. The phone approves; the founder revokes the phone; both reach the body before its next
    turn. On 8d205324 the write ran, with a grant marked founder-approved."""
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = asked(world, body)
        decision = world.approve(ask["request_id"], key=phone)
        drop(world.home, decision, "a-decision.json")
        drop(world.home, world.revoke("phone"), "b-revoke.json")
        turn = world.tick(body)
        assert [c["status"] for c in turn["commands"]] == ["APPLIED", "APPLIED"]
        world.tick(body, 3)
        assert not note.exists() and actions(body, "m:gated") == []
        assert not [r for r in body.ledger.by_type("event") if r.payload.get("type") == "greg.authority.grant_issued"
                    and r.payload.get("founder_approved_scope")]
        m = body.engine.book.missions["m:gated"]
        assert m.approved_scopes == set() and m.status == "ACTIVE"
        # the mission needs a decision again: one new ask for the same exact scope, the voided one closed
        [again] = open_asks(body, "m:gated")
        assert again["request_id"] != ask["request_id"] and again["scope_digest"] == ask["scope_digest"]
        assert m.blocker["request_id"] == again["request_id"]
        # the ledger says the approval was voided, by which revocation, and keeps the original records
        [void] = trail(body, ask["request_id"])
        [revoked] = body.journal.replay("device.revoked")
        assert void["voids_approval"] is True and void["answer"] == "approve"
        assert void["voided_by"] == {"device_key_id": world.kid("phone"), "signer": "device:phone",
                                     "revocation_event": revoked.event_id,
                                     "revocation_command": revoked.payload["command_digest"]}
        assert void["answer_command"] == sha256_json(decision)
        [answered] = [e.payload for e in body.journal.replay("decision.answered")]
        assert answered["request_id"] == ask["request_id"] and answered["answer"] == "approve"
        assert [e.payload["digest"] for e in body.journal.replay("command.accepted")
                if e.payload["kind"] == "DECISION"] == [sha256_json(decision)]
        assert body.ledger.verify_chain()[0]
    shown = [r["request_id"] for r in status(world.home)["decisions_required"]]
    assert shown == [again["request_id"]]


@pytest.mark.parametrize("who", ["founder", "laptop"])
def test_the_founder_or_another_enrolled_device_answers_the_new_ask(world, who):
    with world.body() as body:
        phone, laptop = world.enroll(body, "phone"), world.enroll(body, "laptop")
        note, ask = asked(world, body)
        body.apply(world.approve(ask["request_id"], key=phone))
        body.apply(world.revoke("phone"))
        world.tick(body, 2)
        [again] = open_asks(body, "m:gated")
        with pytest.raises(MissionError, match="request withdrawn"):      # the voided request takes no answer
            body.apply(world.approve(ask["request_id"]))
        body.apply(world.approve(again["request_id"], key=None if who == "founder" else laptop))
        world.tick(body, 3)
        assert note.read_text() == "approved"
        assert [a["status"] for a in actions(body, "m:gated")] == ["DONE"]
        assert body.engine.book.missions["m:gated"].status == "ACHIEVED"


def test_the_fold_alone_voids_the_approval_whatever_else_was_written(world, monkeypatch):
    """The rule is derived from the device.revoked record itself: with the trail never written, the scope is gone."""
    monkeypatch.setattr(revocation, "settle", lambda journal, book: {"voided": [], "reviews": []})
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = asked(world, body)
        body.apply(world.approve(ask["request_id"], key=phone))
        assert body.engine.book.missions["m:gated"].approved_scopes == {ask["scope_digest"]}
        body.apply(world.revoke("phone"))
        assert trail(body) == []
        body.engine.book.rebuild()               # as the engine does at the start of every tick
        for book in (body.engine.book, MissionBook(body.journal), goal_gravity.founder_facts(body.ledger).book):
            assert book.missions["m:gated"].approved_scopes == set()
            assert ask["request_id"] in book.voided and ask["request_id"] in book.consumed
            assert book.answers[ask["request_id"]]["answer"] == "approve"       # history stays
        world.tick(body, 3)
        assert not note.exists() and actions(body, "m:gated") == []


def test_a_paused_body_voids_the_approval_and_acts_on_nothing_when_it_is_resumed(world):
    """A paused body still reads its inbox: the phone's approval and the phone's revocation both land while no
    mission steps. Resuming it must not run what the revoked phone approved."""
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = asked(world, body)
        body.apply(world.sign("BODY_PAUSE", {}))
        drop(world.home, world.approve(ask["request_id"], key=phone), "a-decision.json")
        turn = world.tick(body)
        assert turn["paused"] and body.engine.book.missions["m:gated"].approved_scopes == {ask["scope_digest"]}
        drop(world.home, world.revoke("phone"), "b-revoke.json")
        assert world.tick(body)["paused"]
        assert len(trail(body, ask["request_id"])) == 1            # the trail is a record, written while paused
        # while the pause holds, the founder is told the ask was withdrawn, never that an approval is about to run
        from greg import blockers
        [typed] = blockers.open_blockers(body.journal, engine=body.engine)
        assert "founder answered approve" not in json.dumps(typed) and "revoked" in json.dumps(typed)
        body.apply(world.sign("BODY_RESUME", {}))
        world.tick(body, 4)
        assert not note.exists() and actions(body, "m:gated") == []
        assert [r["request_id"] for r in open_asks(body, "m:gated")] != [ask["request_id"]]


def sensor_outside_the_cone(world, body, mid="m:scope"):
    """A standing mission whose check reads with a capability outside its cone: it asks (SENSOR_SCOPE) first."""
    folder = world.tmp / "data" / "d"
    folder.mkdir(exist_ok=True)
    check = {"check_id": "listed", "description": "the folder is listed", "predicate": {"op": "exists",
             "field": "entries"}, "sensor": {"capability": "fs.list", "params": {"path": str(folder)}, "target": "fs:d"}}
    body.apply(world.sign("MISSION", mission(mid, checks=[check], strategies=[], capabilities=["fs.read"],
                                             ceiling="read_only",
                                             closure={"kind": "infinite", "ladder": [["listed"]], "cadence_seconds": 60})))
    world.tick(body, 2)
    [ask] = open_asks(body, mid, kind="SENSOR_SCOPE")
    return ask


def approved_grants(body):
    return [r.payload for r in body.ledger.by_type("event")
            if r.payload.get("type") == "greg.authority.grant_issued" and r.payload.get("founder_approved_scope")]


def test_a_sensor_scope_approval_of_a_revoked_device_admits_no_further_observation(world):
    """An approve of a SENSOR_SCOPE ask puts the observation's exact scope where the Gate honours it, for the
    mission's lifetime. Reproduced on the first draft of this change, which voided APPROVAL asks only: the Gate
    granted two more out-of-cone reads after the revocation."""
    with world.body() as body:
        phone = world.enroll(body, "phone")
        ask = sensor_outside_the_cone(world, body)
        body.apply(world.approve(ask["request_id"], key=phone))
        world.tick(body, 2)
        read = approved_grants(body)
        assert len(read) == 1 and read[0]["scope_digest"] == ask["scope_digest"]
        observed = [e.payload for e in body.journal.replay("mission.observed")]
        result = body.apply(world.revoke("phone", suspected_compromise=True))["result"]
        assert result["voided_requests"] == [ask["request_id"]]
        for _ in range(3):                                       # the cadence passes: the mission would read again
            world.clock.advance(61)
            world.tick(body, 2)
        assert approved_grants(body) == read                     # nothing more was granted on the voided approval
        assert [e.payload for e in body.journal.replay("mission.observed")] == observed   # and the reading stays
        m = body.engine.book.missions["m:scope"]
        assert m.approved_scopes == set()
        [again] = open_asks(body, "m:scope", kind="SENSOR_SCOPE")
        assert again["request_id"] != ask["request_id"] and again["scope_digest"] == ask["scope_digest"]
        assert m.blocker["request_id"] == again["request_id"]
        [void] = trail(body, ask["request_id"])
        assert void["voids_approval"] is True and void["kind"] == "SENSOR_SCOPE"
        # the review lists the observation that was read under the approval, with its receipt
        [review] = [e.payload for e in body.journal.replay(revocation.REVIEW_RECORD)]
        [command] = review["commands"]
        assert command["request_kind"] == "SENSOR_SCOPE" and command["standing"].startswith("VOIDED_BY_THIS_REVOCATION")
        [effect] = review["effects"]
        assert effect["effect"] == "an observation read under its approval" and effect["check_id"] == "listed"
        assert effect["receipt"] == observed[-1]["receipt"] and effect["grant_id"] == read[0]["grant_id"]
        assert review["receipts"] == [effect["receipt"]]
        body.apply(world.approve(again["request_id"]))            # the founder's own approval stands again
        world.clock.advance(61)
        world.tick(body, 2)
        assert len(approved_grants(body)) == 2
        assert body.ledger.verify_chain()[0]


def test_every_kind_of_founder_ask_is_classified_for_revocation():
    """A revocation voids the answers that still authorize something, by the kind of ask they answer. Every kind
    raised anywhere in greg/ is in exactly one class, so a new kind cannot be added without deciding it (the first
    draft of this change missed SENSOR_SCOPE, whose approve the Gate honours)."""
    import re
    from pathlib import Path
    from greg import missions
    from greg.body import HOLD_ASK
    from greg.founder import COMMAND_KINDS
    root = Path(__file__).resolve().parents[2] / "greg"
    raised = {HOLD_ASK, revocation.REVIEW_ASK}
    for path in root.rglob("*.py"):
        raised |= set(re.findall(r'''(?:\bkind\s*=\s*|["']kind["']\s*:\s*)["']([A-Z][A-Z_]+)["']''',
                                 path.read_text(encoding="utf-8")))
    raised -= set(COMMAND_KINDS) - {"CAPABILITY_ATTACH"}        # CAPABILITY_ATTACH is a command and an ask
    assert {"APPROVAL", "SENSOR_SCOPE", "RECONCILIATION", "HUMAN_JUDGMENT", "COMPUTE"} <= raised   # the scan finds them
    classes = [set(missions.GATE_SCOPE_ASKS), set(missions.RECONCILIATION_ASKS), set(missions.NO_AUTHORITY_ASKS),
               set(asks.ANSWER_ONLY_RECORDS), set(missions.NOT_ANSWERABLE)]
    assert sorted(raised - set().union(*classes)) == []         # every kind is decided
    assert sum(len(c) for c in classes) == len(set().union(*classes))   # in exactly one class
    # what the classes mean, on the rule itself
    for kind in sorted(raised):
        request, approve = {"kind": kind}, {"answer": "approve"}
        expected = "approval" if kind in missions.GATE_SCOPE_ASKS else None
        assert missions.unused_authority(request, approve, consumed=False, reconciled=False) == expected, kind
        assert missions.unused_authority(request, approve, consumed=True, reconciled=False) is None
        assert missions.unused_authority(request, {"answer": "reject"}, consumed=False, reconciled=False) is None
        settles = "reconciliation" if kind in missions.RECONCILIATION_ASKS else None
        for answer in ("reconcile_executed", "reconcile_not_executed"):
            assert missions.unused_authority(request, {"answer": answer}, consumed=False, reconciled=False) == settles
            assert missions.unused_authority(request, {"answer": answer}, consumed=False, reconciled=True) is None


# -- b. what was completed keeps its receipts ----------------------------------------------------------------------

def test_an_act_completed_before_the_revocation_keeps_its_receipt_and_its_closure(world):
    with world.body() as body:
        body.boot()
        phone = world.enroll(body, "phone")
        note, ask = asked(world, body)
        body.apply(world.approve(ask["request_id"], key=phone))
        world.tick(body, 4)
        assert body.engine.book.missions["m:gated"].status == "ACHIEVED"
        [done] = actions(body, "m:gated")
        receipt = body.ledger.find(done["receipt"])
        [appraised] = [e.payload for e in body.journal.replay("mission.appraised")]
        assert appraised["verdict"] == "VERIFIED"
        before = [r.hash for r in body.ledger.records]
        body.apply(world.revoke("phone"))
        world.tick(body, 2)
        # nothing recorded before the revocation changed, and nothing says the effect did not happen
        assert [r.hash for r in body.ledger.records][:len(before)] == before
        assert actions(body, "m:gated") == [done] and body.ledger.find(done["receipt"]).hash == receipt.hash
        assert note.read_text() == "approved"
        assert body.engine.book.missions["m:gated"].status == "ACHIEVED"
        # the separate appraiser, run after the revocation, still verifies the closure: the approval was in force
        verdict = body.appraise("m:gated")
        assert verdict["verdict"] == "VERIFIED" and verdict["checks"]["approval_boundaries_honored"], verdict
        assert body.ledger.verify_chain()[0]


def test_a_standing_approval_keeps_its_completed_run_and_the_next_run_asks_again(world):
    """An unpaid approve stands for the mission's lifetime: the run it already allowed stays, the remainder is void."""
    mid = "m:hold"
    note = workspace(world.home, mid) / "n.txt"
    with world.body() as body:
        phone = world.enroll(body, "phone")
        body.apply(world.sign("MISSION", mission(
            mid, checks=[note_check("n", note, "kept")], strategies=[write_strategy("w", "n.txt", "kept", ["n"])],
            capabilities=["fs.read"], ceiling="read_only",
            closure={"kind": "infinite", "ladder": [["n"]], "cadence_seconds": 60})))
        world.tick(body, 2)
        [ask] = open_asks(body, mid)
        body.apply(world.approve(ask["request_id"], key=phone))
        world.tick(body, 3)
        [first] = actions(body, mid)
        assert first["status"] == "DONE" and note.read_text() == "kept"
        body.apply(world.revoke("phone"))
        note.write_text("drifted")                           # the world drifts: the mission would write again
        world.clock.advance(61)
        world.tick(body, 4)
        assert note.read_text() == "drifted" and actions(body, mid) == [first]
        [again] = open_asks(body, mid)
        assert again["request_id"] != ask["request_id"]
        body.apply(world.approve(again["request_id"]))        # the founder's own approval stands again
        world.tick(body, 3)
        assert note.read_text() == "kept" and [a["status"] for a in actions(body, mid)] == ["DONE", "DONE"]


def test_a_paid_approval_whose_one_run_happened_is_used_and_not_voided(world):
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = asked(world, body, mid="m:paid", cost_usd=0.5)
        body.apply(world.approve(ask["request_id"], key=phone))
        world.tick(body, 3)
        [done] = actions(body, "m:paid")
        assert done["status"] == "DONE" and ask["request_id"] in body.engine.book.consumed
        body.apply(world.revoke("phone"))
        world.tick(body)
        assert body.engine.book.voided == {} and trail(body) == []
        assert actions(body, "m:paid") == [done]


def test_a_dispatch_claimed_before_the_revocation_is_settled_from_the_gates_record_and_not_rewritten(world, monkeypatch):
    """In flight: the body stops after the Gate's receipt and before the mission's own record; the founder revokes
    the phone; the restarted body records the dispatch from the Gate's receipt. Nothing new runs on the approval."""
    with world.body() as body:
        body.boot()
        phone = world.enroll(body, "phone")
        note, ask = asked(world, body)
        body.apply(world.approve(ask["request_id"], key=phone))
        monkeypatch.setattr(body.engine, "_record_outcome", lambda *a, **k: (_ for _ in ()).throw(SystemExit("killed")))
        with pytest.raises(SystemExit):
            world.tick(body)
        assert note.read_text() == "approved" and actions(body, "m:gated") == []     # dispatched, not yet recorded
    with world.body() as body:
        body.boot()
        body.apply(world.revoke("phone", suspected_compromise=True))
        # the review reads the Gate's own grant: the dispatch is listed although the mission had not recorded it
        [review] = [e.payload for e in body.journal.replay(revocation.REVIEW_RECORD)]
        [unrecorded] = review["effects"]
        assert unrecorded["effect"].startswith("a dispatch the Gate granted under its approval, not yet recorded")
        assert unrecorded["mission_id"] == "m:gated" and unrecorded["scope_digest"] == ask["scope_digest"]
        world.tick(body, 4)
        [done] = actions(body, "m:gated")
        assert done["status"] == "DONE" and done["receipt"]
        assert body.ledger.find(done["receipt"]).payload["grant_id"] == unrecorded["grant_id"]
        assert done["reasons"] == ["retained receipt of a dispatch the body did not record before it stopped"]
        assert len(body.ledger.select("grant_dispatch")) == 1 + len(
            [e for e in body.journal.replay("mission.observed") if e.payload["mission_id"] == "m:gated"])
        assert body.engine.book.missions["m:gated"].status == "ACHIEVED"
        verdict = body.journal.replay("mission.appraised")[-1].payload
        assert verdict["verdict"] == "VERIFIED", verdict        # dispatched before the revocation: in force then


# -- c. historical validity is not continuing authority ------------------------------------------------------------

def test_a_decision_signed_before_the_revocation_and_delivered_after_it_confers_nothing(world):
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = asked(world, body)
        early = world.approve(ask["request_id"], key=phone)          # signed while the phone was delegated
        body.apply(world.revoke("phone"))
        drop(world.home, early, "late.json")
        turn = world.tick(body)
        assert [c["status"] for c in turn["commands"]] == ["REJECTED"]
        assert "not enrolled or revoked" in turn["commands"][0]["reason"]
        world.tick(body, 2)
        assert not note.exists() and body.journal.replay("decision.answered") == []
        assert [r["request_id"] for r in open_asks(body, "m:gated")] == [ask["request_id"]]   # still the open ask


def test_replaying_the_device_envelope_after_the_revocation_confers_nothing(world):
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = asked(world, body)
        decision = world.approve(ask["request_id"], key=phone)
        body.apply(decision)
        body.apply(world.revoke("phone"))
        assert body.apply(decision)["status"] == "ALREADY_APPLIED"   # the same file again: nothing is applied twice
        drop(world.home, decision, "again.json")
        world.tick(body, 3)
        assert body.engine.book.missions["m:gated"].approved_scopes == set()
        assert not note.exists() and len(body.journal.replay("decision.answered")) == 1


def test_re_enrolling_the_key_revives_nothing_and_a_fresh_approval_works(world):
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = asked(world, body)
        decision = world.approve(ask["request_id"], key=phone)
        body.apply(decision)
        body.apply(world.revoke("phone"))
        world.clock.advance(60)
        world.enroll(body, "phone")                                  # the same key, delegated again
        assert world.kid("phone") in body.device_keys()
        world.tick(body, 3)
        assert not note.exists() and body.engine.book.missions["m:gated"].approved_scopes == set()
        assert ask["request_id"] in body.engine.book.voided
        drop(world.home, decision, "old.json")                       # the old approval, sent again
        world.tick(body, 2)
        assert not note.exists()
        [again] = open_asks(body, "m:gated")
        with pytest.raises(MissionError, match="request withdrawn"):  # a new signature on the voided request, too
            body.apply(world.approve(ask["request_id"], key=phone))
        body.apply(world.approve(again["request_id"], key=phone))    # signed under the new delegation
        world.tick(body, 3)
        assert note.read_text() == "approved" and [a["status"] for a in actions(body, "m:gated")] == ["DONE"]


def test_the_devices_old_signature_still_verifies_as_history(world):
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = asked(world, body)
        decision = world.approve(ask["request_id"], key=phone)
        body.apply(decision)
        body.apply(world.revoke("phone"))
        world.tick(body, 2)
        digest = sha256_json(decision)
        facts = goal_gravity.founder_facts(body.ledger)                  # replay of the whole ledger still holds
        assert facts.signed[digest]["principal"] == "device:phone"      # valid at its own position, as history
        assert digest in goal_gravity.verified_decisions(body.ledger)
        assert facts.book.answers[ask["request_id"]]["command_digest"] == digest
        assert facts.book.missions["m:gated"].approved_scopes == set()  # and no authority after the revocation
        assert body.ledger.verify_chain()[0]


def test_a_replay_only_book_voids_by_the_signer_its_records_state():
    """A stand-in journal without a ledger (tests, read-only replays) folds rows as they are: the signer is the
    one the command.accepted row states, and the same rule applies."""
    from types import SimpleNamespace
    from greg.missions import MissionBook

    def event(kind, payload):
        return SimpleNamespace(type="greg." + kind, payload=payload, event_id=None)

    spec = mission("m:replay", checks=[], strategies=[], capabilities=["fs.read"], ceiling="read_only")
    rows = [event("mission.registered", {"mission_id": "m:replay", "spec": spec, "command_digest": "sha256:m"})]
    for rid, scope, digest, key, signer in (("req-phone", "sha256:a", "sha256:1", "ed25519:phone", "device:phone"),
                                            ("req-founder", "sha256:b", "sha256:2", "ed25519:founder", "founder")):
        rows += [event("decision.requested", {"request_id": rid, "mission_id": "m:replay", "kind": "APPROVAL",
                                              "scope_digest": scope}),
                 event("decision.answered", {"request_id": rid, "mission_id": "m:replay", "answer": "approve",
                                             "command_digest": digest}),
                 event("command.accepted", {"kind": "DECISION", "digest": digest, "founder_key_id": key,
                                            "signer": signer})]
    journal = SimpleNamespace(replay=lambda prefix="": list(rows))
    assert MissionBook(journal).missions["m:replay"].approved_scopes == {"sha256:a", "sha256:b"}
    rows.append(event("device.revoked", {"device_key_id": "ed25519:phone", "at": "2026-11-11T00:00:00Z"}))
    book = MissionBook(journal)
    assert book.missions["m:replay"].approved_scopes == {"sha256:b"} and set(book.voided) == {"req-phone"}


# -- only the revoked device's unused authority ---------------------------------------------------------------------

def test_another_devices_and_the_founders_approvals_are_untouched(world):
    with world.body() as body:
        phone, laptop = world.enroll(body, "phone"), world.enroll(body, "laptop")
        notes = {mid: world.gated(body, mid) for mid in ("m:phone", "m:laptop", "m:founder")}
        world.tick(body, 2)
        for mid in notes:                              # all three approved before the body's next turn
            [ask] = open_asks(body, mid)
            body.apply(world.approve(ask["request_id"], key={"m:phone": phone, "m:laptop": laptop}.get(mid)))
        drop(world.home, world.revoke("phone"), "revoke.json")
        world.tick(body, 4)
        assert not notes["m:phone"].exists()
        assert notes["m:laptop"].read_text() == "approved" and notes["m:founder"].read_text() == "approved"
        assert [v["mission_id"] for v in body.engine.book.voided.values()] == ["m:phone"]
        assert [v["mission_id"] for v in trail(body)] == ["m:phone"]
        assert set(body.device_keys()) == {world.kid("laptop")}


def test_a_revocation_record_naming_the_founder_key_voids_no_founder_approval(world):
    """Only an answer a device key signed is voided: a device.revoked row written by any route names no founder
    answer away."""
    with world.body() as body:
        note, ask = asked(world, body)
        body.apply(world.approve(ask["request_id"]))
        [founder] = body.enrolled_keys()
        body.journal.record("device.revoked", {"device_key_id": founder, "at": "2026-11-11T00:00:00Z"},
                            key=[founder, "forged"])
        body.engine.book.rebuild()
        assert body.engine.book.voided == {}
        world.tick(body, 4)
        assert note.read_text() == "approved"
        verdict = body.journal.replay("mission.appraised")[-1].payload     # the separate appraiser agrees
        assert verdict["verdict"] == "VERIFIED" and verdict["checks"]["approval_boundaries_honored"], verdict


def test_an_approval_already_withdrawn_is_not_voided_a_second_time(world):
    """A standing approval that failure evidence already withdrew (greg/autonomy.py ``regress`` writes this row) is
    asked again by that withdrawal. Revoking the device that signed it finds nothing unused: no second record."""
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = asked(world, body)
        body.apply(world.approve(ask["request_id"], key=phone))
        body.journal.record("decision.withdrawn", {
            "request_id": ask["request_id"], "mission_id": "m:gated", "voids_approval": True,
            "why": "a run of w under this approval failed; the approval no longer stands",
            "at": stamp(world.clock())}, key=[ask["request_id"], "withdrawn", "regressed"])
        body.apply(world.revoke("phone"))
        world.tick(body, 2)
        assert body.engine.book.voided == {} and trail(body) == []
        assert len([e for e in body.journal.replay("decision.withdrawn")
                    if e.payload["request_id"] == ask["request_id"]]) == 1
        assert not note.exists() and len(open_asks(body, "m:gated")) == 1


def test_a_devices_rejection_stands_after_its_revocation(world):
    """A rejection authorizes nothing, so there is nothing to void: it stays the recorded decision."""
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = asked(world, body)
        body.apply(world.approve(ask["request_id"], key=phone, answer="reject"))
        body.apply(world.revoke("phone"))
        world.tick(body, 3)
        m = body.engine.book.missions["m:gated"]
        assert body.engine.book.voided == {} and ask["scope_digest"] in m.rejected_scopes
        assert not note.exists()


# -- an unrecorded reconciliation answer ---------------------------------------------------------------------------

def explode_once(body, capability="fs.write", *, after_effect=False):
    """The first dispatch dies with no receipt: before the effect, or (``after_effect``) once the file is written."""
    real, calls = body.registry.adapters[capability], []

    def adapter(params, ctx):
        calls.append(params)
        if len(calls) == 1:
            if after_effect:
                real(params, ctx)
            raise RuntimeError("power lost mid-effect")
        return real(params, ctx)
    body.registry.adapters[capability] = adapter
    return calls


def uncertain(world, body, mid="m:uncertain", *, after_effect=False):
    """A mission whose first write died mid-effect: one UNCERTAIN dispatch and its open RECONCILIATION ask."""
    note = workspace(world.home, mid) / "c.txt"
    body.apply(world.sign("MISSION", mission(mid, checks=[note_check("c", note, "ok")],
                                             strategies=[write_strategy("w", "c.txt", "ok", ["c"])],
                                             capabilities=["fs.read", "fs.write"])))
    calls = explode_once(body, after_effect=after_effect)
    world.tick(body, 3)
    assert [a["status"] for a in actions(body, mid)] == ["UNCERTAIN"]
    [ask] = open_asks(body, mid, kind="RECONCILIATION")
    return note, ask, calls


def test_an_unrecorded_reconciliation_answer_of_a_revoked_device_settles_nothing(world):
    """reconcile_not_executed would let the action be dispatched again; revoked before the engine recorded it,
    the answer settles nothing and the same dispatch is asked about again."""
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask, calls = uncertain(world, body)
        drop(world.home, world.approve(ask["request_id"], key=phone, answer="reconcile_not_executed"), "a.json")
        drop(world.home, world.revoke("phone"), "b.json")
        world.tick(body, 3)
        assert len(calls) == 1 and [a["status"] for a in actions(body, "m:uncertain")] == ["UNCERTAIN"]
        [again] = open_asks(body, "m:uncertain", kind="RECONCILIATION")
        assert again["request_id"] != ask["request_id"]
        assert again["authority_requested"] == ask["authority_requested"]     # the same one dispatch
        # a suspicion signed later is a second revocation record of the same key: it voids nothing a second time
        marked = body.apply(world.revoke("phone", suspected_compromise=True))["result"]
        assert "voided_requests" not in marked
        [void] = trail(body, ask["request_id"])
        assert "voids_approval" not in void and void["voids_answer"] is True and void["kind"] == "RECONCILIATION"
        assert void["voided_by"]["revocation_event"] == body.journal.replay("device.revoked")[0].event_id
        [review] = [e.payload for e in body.journal.replay(revocation.REVIEW_RECORD)]
        assert review["voided_by_this_revocation"] == [ask["request_id"]] and review["effects"] == []
        body.apply(world.approve(again["request_id"], answer="reconcile_not_executed"))   # the founder's own answer
        world.tick(body, 4)
        assert [a["status"] for a in actions(body, "m:uncertain")] == ["UNCERTAIN", "RECONCILED_NOT_EXECUTED", "DONE"]
        assert note.read_text() == "ok"


def test_a_voided_reconciliation_is_asked_again_before_the_mission_may_close(world):
    """The interrupted write did reach the file, so the check passes on re-observation. With the phone's answer
    voided, the mission must not close over a dispatch nobody has settled: it asks again first."""
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask, calls = uncertain(world, body, after_effect=True)
        assert note.read_text() == "ok"
        drop(world.home, world.approve(ask["request_id"], key=phone, answer="reconcile_executed"), "a.json")
        drop(world.home, world.revoke("phone"), "b.json")
        world.tick(body, 3)
        m = body.engine.book.missions["m:uncertain"]
        assert m.status == "ACTIVE" and [a["status"] for a in actions(body, "m:uncertain")] == ["UNCERTAIN"]
        [again] = open_asks(body, "m:uncertain", kind="RECONCILIATION")
        assert again["request_id"] != ask["request_id"] and m.blocker["request_id"] == again["request_id"]
        body.apply(world.approve(again["request_id"], answer="reconcile_executed"))
        world.tick(body, 3)
        assert body.engine.book.missions["m:uncertain"].status == "ACHIEVED" and len(calls) == 1


def test_a_voided_reconciliation_of_an_ended_mission_is_not_recorded(world):
    """The mission was abandoned while its question was open. The phone's answer, voided before it was recorded,
    settles nothing there either: the same dispatch is asked about again and nothing is recorded in its name."""
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask, calls = uncertain(world, body)
        body.apply(world.sign("LIFECYCLE", {"mission_id": "m:uncertain", "state": "ABANDONED", "reason": "stop"}))
        drop(world.home, world.approve(ask["request_id"], key=phone, answer="reconcile_executed"), "a.json")
        drop(world.home, world.revoke("phone"), "b.json")
        world.tick(body, 3)
        assert [a["status"] for a in actions(body, "m:uncertain")] == ["UNCERTAIN"]
        assert not [a for a in actions(body, "m:uncertain") if a.get("route") == "founder_reconciliation"]
        [again] = open_asks(body, "m:uncertain", kind="RECONCILIATION")
        assert again["request_id"] != ask["request_id"]
        body.apply(world.approve(again["request_id"], answer="reconcile_executed"))
        world.tick(body, 2)
        [settled] = [a for a in actions(body, "m:uncertain") if a.get("route") == "founder_reconciliation"]
        assert settled["status"] == "DONE" and settled["reconciles"]["request_id"] == again["request_id"]


def test_a_recorded_reconciliation_stays_after_the_devices_revocation(world):
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask, calls = uncertain(world, body)
        body.apply(world.approve(ask["request_id"], key=phone, answer="reconcile_executed"))
        world.tick(body, 2)
        recorded = actions(body, "m:uncertain")
        assert [a["status"] for a in recorded] == ["UNCERTAIN", "DONE"]
        body.apply(world.revoke("phone"))
        world.tick(body, 2)
        assert body.engine.book.voided == {} and trail(body) == []
        assert actions(body, "m:uncertain")[:2] == recorded and len(calls) == 1


def test_an_uncertain_dispatch_under_a_devices_approval_stays_and_its_retry_needs_a_new_approval(world):
    """In flight, the other way: the approved dispatch's completion is unknown when the phone is revoked. Its
    record and its reconciliation stay; a retry is a new effect and waits for a new approval."""
    mid = "m:gated"
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = asked(world, body, mid=mid)
        calls = explode_once(body)
        body.apply(world.approve(ask["request_id"], key=phone))
        world.tick(body, 2)
        [first] = actions(body, mid)
        assert first["status"] == "UNCERTAIN"
        [question] = open_asks(body, mid, kind="RECONCILIATION")
        body.apply(world.revoke("phone"))
        world.tick(body, 2)
        assert actions(body, mid) == [first]                               # not rewritten
        assert [r["request_id"] for r in open_asks(body, mid, kind="RECONCILIATION")] == [question["request_id"]]
        body.apply(world.approve(question["request_id"], answer="reconcile_not_executed"))
        world.tick(body, 3)
        assert len(calls) == 1 and not note.exists()                       # no retry on the voided approval
        [again] = open_asks(body, mid)
        assert again["request_id"] != ask["request_id"]


def test_a_dispatch_the_founder_reconciles_as_executed_after_the_revocation_keeps_its_approval(world):
    """The device approved, the dispatch's completion was unknown, the device was revoked, and the founder then
    answered that it did run. It was dispatched before the revocation, so its approval was in force: the separate
    appraiser finds the approval boundary honoured (it still cannot verify a run that has no Gate receipt)."""
    mid = "m:gated"
    with world.body() as body:
        body.boot()
        phone = world.enroll(body, "phone")
        note, ask = asked(world, body, mid=mid)
        calls = explode_once(body, after_effect=True)
        body.apply(world.approve(ask["request_id"], key=phone))
        world.tick(body, 2)
        [question] = open_asks(body, mid, kind="RECONCILIATION")
        body.apply(world.revoke("phone"))
        world.tick(body, 2)
        body.apply(world.approve(question["request_id"], answer="reconcile_executed"))
        world.tick(body, 4)
        assert [a["status"] for a in actions(body, mid)] == ["UNCERTAIN", "DONE"] and len(calls) == 1
        verdict = body.journal.replay("mission.appraised")[-1].payload
        assert verdict["checks"]["approval_boundaries_honored"] is True, verdict["findings"]
        assert not [f for f in verdict["findings"] if "approval that was void" in f]


# -- e. it holds across a restart -----------------------------------------------------------------------------------

@pytest.mark.parametrize("restart", ["between_approval_and_revocation", "between_revocation_and_act"])
def test_the_void_holds_across_a_restart(world, restart):
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = asked(world, body)
        body.apply(world.approve(ask["request_id"], key=phone))
        if restart == "between_revocation_and_act":
            body.apply(world.revoke("phone"))
    if restart == "between_approval_and_revocation":
        with world.body() as body:
            body.apply(world.revoke("phone"))
    with world.body() as body:                       # a new process: everything is rebuilt from the ledger
        assert body.engine.book.missions["m:gated"].approved_scopes == set()
        world.tick(body, 4)
        assert not note.exists() and actions(body, "m:gated") == []
        assert len(trail(body, ask["request_id"])) == 1
        assert [r["request_id"] for r in open_asks(body, "m:gated")] != [ask["request_id"]]


def test_a_body_that_stops_between_the_revocation_and_its_trail_finishes_it_once(world, monkeypatch):
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = asked(world, body)
        body.apply(world.approve(ask["request_id"], key=phone))
        revoke = world.revoke("phone", suspected_compromise=True)
        with monkeypatch.context() as patch:
            patch.setattr(revocation, "settle", lambda *a: (_ for _ in ()).throw(SystemExit("killed")))
            with pytest.raises(SystemExit):
                body.apply(revoke)
        assert len(body.journal.replay("device.revoked")) == 1 and trail(body) == []
        assert not [e for e in body.journal.replay("command.accepted") if e.payload["kind"] == "DEVICE_REVOKE"]

    def recorded(body):
        return (len(body.journal.replay("device.revoked")), len(trail(body, ask["request_id"])),
                len(body.journal.replay(revocation.REVIEW_RECORD)),
                len([r for r in body.engine.book.requests.values() if r["kind"] == revocation.REVIEW_ASK]))

    with world.body() as body:                           # the next turn finishes the trail from the ledger alone
        world.tick(body)
        assert recorded(body) == (1, 1, 1, 1) and not note.exists()
    drop(world.home, revoke, "revoke.json")              # the file was still in the inbox of the body that stopped
    with world.body() as body:
        turn = world.tick(body)
        assert [c["status"] for c in turn["commands"]] == ["APPLIED"]      # the same command finishes, not refused
        world.tick(body, 3)
        assert recorded(body) == (1, 1, 1, 1) and not note.exists()
        [accepted] = [e.payload for e in body.journal.replay("command.accepted") if e.payload["kind"] == "DEVICE_REVOKE"]
        assert accepted["result"]["voided_requests"] == [ask["request_id"]]


def test_a_trail_record_written_late_takes_nothing_from_an_approval_given_since(world, monkeypatch):
    """The void takes effect at the revocation. If its trail lands only after the founder approved the same scope
    again (a body that stopped in between), that record must not void the founder's new approval."""
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = asked(world, body)
        body.apply(world.approve(ask["request_id"], key=phone))
        with monkeypatch.context() as patch:
            patch.setattr(revocation, "settle", lambda journal, book: {"voided": [], "reviews": []})
            body.apply(world.revoke("phone"))
            world.tick(body, 2)
            [again] = open_asks(body, "m:gated")
            body.apply(world.approve(again["request_id"]))
            assert trail(body) == []
        assert revocation.settle(body.journal, body.engine.book)["voided"] == [ask["request_id"]]
        assert body.engine.book.missions["m:gated"].approved_scopes == {ask["scope_digest"]}
        assert MissionBook(body.journal).missions["m:gated"].approved_scopes == {ask["scope_digest"]}
        world.tick(body, 3)
        assert note.read_text() == "approved"


def test_a_restore_that_withdrew_the_approval_is_not_given_a_second_withdrawal(world):
    """A restore voids every device delegation and withdraws the live approvals itself (greg/recovery.py). The
    fold voids the phone's approval at the restore's revocation record; the restore's own withdrawal is the record,
    and the turn adds no second one for the same request."""
    from foundry.systems import seed
    from greg.recovery import restore_body
    with world.body() as body:
        body.boot()
        phone = world.enroll(body, "phone")
        note, ask = asked(world, body)
        body.apply(world.approve(ask["request_id"], key=phone))
    made = seed.make_seed(world.home, world.tmp / "seed-store")
    world.home.rename(world.home.parent / "lost-machine")
    world.clock.advance(60)
    report = restore_body(world.tmp / "seed-store", made["seed"], world.home, clock=world.clock)
    assert report["voided"]["approvals"] == [ask["request_id"]]
    with world.body() as body:
        body.boot()
        assert body.engine.book.missions["m:gated"].approved_scopes == set()
        assert ask["request_id"] in body.engine.book.voided
        assert world.tick(body)["paused"]                                  # held: the turn still settles the trail
        withdrawn = [e.payload for e in body.journal.replay("decision.withdrawn")
                     if e.payload["request_id"] == ask["request_id"]]
        assert len(withdrawn) == 1 and withdrawn[0]["restore_id"] == report["restore_id"]
        body.apply(world.sign("BODY_RESUME", {}))
        world.tick(body, 3)
        assert not note.exists() and len(open_asks(body, "m:gated")) == 1


def test_the_trail_is_written_once_however_often_it_is_settled(world):
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = asked(world, body)
        body.apply(world.approve(ask["request_id"], key=phone))
        body.apply(world.revoke("phone", suspected_compromise=True))
        records = len(body.ledger.records)
        for _ in range(3):
            assert revocation.settle(body.journal, body.engine.book) == {"voided": [], "reviews": []}
        assert len(body.ledger.records) == records


# -- d. a suspected compromise opens a separate retrospective review ---------------------------------------------

def test_a_plain_revocation_is_recorded_as_before_and_opens_no_review(world):
    with world.body() as body:
        world.enroll(body, "phone")
        command = world.revoke("phone")
        result = body.apply(command)["result"]
        assert result == {"device_key_id": world.kid("phone"), "revoked": True}
        [revoked] = [e.payload for e in body.journal.replay("device.revoked")]
        assert set(revoked) == {"device_key_id", "command_digest", "at"}
        world.tick(body, 2)
        assert body.journal.replay(revocation.REVIEW_RECORD) == []
        assert not [r for r in body.engine.book.requests.values() if r["kind"] == revocation.REVIEW_ASK]


def test_only_a_currently_delegated_key_is_revoked(world):
    with world.body() as body:
        world.enroll(body, "phone")
        body.apply(world.revoke("phone"))
        with pytest.raises(MissionError, match="currently delegated device_key_id$"):
            body.apply(world.revoke("phone"))                                 # already revoked, exactly as before
        for never in ({}, {"suspected_compromise": True}):                    # a key that was never delegated
            with pytest.raises(MissionError, match="currently delegated"):
                body.apply(world.sign("DEVICE_REVOKE", {"device_key_id": "ed25519:" + "0" * 32, **never}))
        with pytest.raises(MissionError, match="currently delegated"):
            body.apply(world.sign("DEVICE_REVOKE", {"device_key_id": [world.kid("phone")]}))   # a key id is text
        assert len(body.journal.replay("device.revoked")) == 1
        assert body.journal.replay(revocation.REVIEW_RECORD) == []


def test_a_suspicion_after_a_plain_revocation_opens_the_review_once(world):
    """The phone is revoked first; the suspicion comes later. The founder signs DEVICE_REVOKE for the revoked key
    again, with suspected_compromise: it revokes nothing more and opens the review of that revocation, once."""
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = asked(world, body)
        decision = world.approve(ask["request_id"], key=phone)
        body.apply(decision)
        plain = body.apply(world.revoke("phone"))["result"]
        assert plain == {"device_key_id": world.kid("phone"), "revoked": True, "voided_requests": [ask["request_id"]]}
        world.tick(body, 2)
        [first] = body.journal.replay("device.revoked")
        assert body.journal.replay(revocation.REVIEW_RECORD) == []
        marked = body.apply(world.revoke("phone", suspected_compromise=True))["result"]
        [_, mark] = body.journal.replay("device.revoked")
        assert mark.payload["marks_revocation"] == first.event_id and mark.payload["suspected_compromise"] is True
        [review] = [e.payload for e in body.journal.replay(revocation.REVIEW_RECORD)]
        assert marked == {"device_key_id": world.kid("phone"), "revoked": True, "integrity_review": review["review_id"]}
        assert review["revocation"]["marks_revocation"] == first.event_id
        assert [c["command_digest"] for c in review["commands"]] == [sha256_json(decision)]
        assert review["commands"][0]["standing"].startswith("VOIDED_BY_THIS_REVOCATION")
        assert review["voided_by_this_revocation"] == [ask["request_id"]]
        # it revoked and voided nothing more: one withdrawal, by the first revocation; no key is delegated
        [void] = trail(body, ask["request_id"])
        assert void["voided_by"]["revocation_event"] == first.event_id and body.device_keys() == {}
        with pytest.raises(MissionError, match="no integrity review yet"):   # once: the review is open
            body.apply(world.revoke("phone", suspected_compromise=True))
        world.tick(body, 3)
        assert len(body.journal.replay("device.revoked")) == 2 and len(body.journal.replay(revocation.REVIEW_RECORD)) == 1
        assert not note.exists() and body.ledger.verify_chain()[0]
    rows = status(world.home)["security"]["device_revocations"]
    assert [r.get("marks_revocation") for r in rows] == [None, first.event_id]
    assert rows[0]["voided_requests"] == [ask["request_id"]] and rows[1]["integrity_review"]["state"] == "OPEN"
    assert "integrity_review" not in rows[0]                 # the plain revocation itself opened none
    # delegated again and revoked as suspected: that is a new revocation with its own review
    with world.body() as body:
        world.clock.advance(60)
        world.enroll(body, "phone")
        again = body.apply(world.revoke("phone", suspected_compromise=True))["result"]
        assert again["integrity_review"] != marked["integrity_review"]
        assert len(body.journal.replay(revocation.REVIEW_RECORD)) == 2
        # and each later delegation starts clean: revoked plainly, its revocation can be marked in its turn
        world.clock.advance(60)
        world.enroll(body, "phone")
        body.apply(world.revoke("phone"))
        body.apply(world.revoke("phone", suspected_compromise=True))
        assert len(body.journal.replay(revocation.REVIEW_RECORD)) == 3


@pytest.mark.parametrize("extra", [{"suspected_compromise": False}, {"suspected_compromise": "yes"},
                                   {"suspected_compromise": 1}, {"reason": "lost"}, {"suspected": True}])
def test_the_revocation_body_takes_only_its_validated_fields(world, extra):
    with world.body() as body:
        world.enroll(body, "phone")
        with pytest.raises(MissionError):
            body.apply(world.revoke("phone", **extra))
        assert world.kid("phone") in body.device_keys() and body.journal.replay("device.revoked") == []


def compromised(world, body):
    """The phone approved one write that ran and one that has not run, paused a mission and wrote a critique;
    the laptop and the founder each approved a write that ran. Then the founder revokes the phone as suspected."""
    phone = world.enroll(body, "phone", ("DECISION", "LIFECYCLE", "CRITIQUE"))
    laptop = world.enroll(body, "laptop")
    done = {}
    for mid, key in (("m:ran", phone), ("m:laptop", laptop), ("m:founder", None)):
        _, ask = asked(world, body, mid=mid)
        done[mid] = world.approve(ask["request_id"], key=key)
        body.apply(done[mid])
        world.tick(body, 3)
        assert [a["status"] for a in actions(body, mid)] == ["DONE"]
    _, waiting = asked(world, body, mid="m:waiting")
    pending = world.approve(waiting["request_id"], key=phone)
    pause = world.sign("LIFECYCLE", {"mission_id": "m:waiting", "state": "PAUSED", "reason": "from the phone"},
                       key=phone)
    target = [e for e in body.journal.replay("mission.action") if e.payload["mission_id"] == "m:laptop"][0]
    critique = world.sign("CRITIQUE", {"target_event_id": target.event_id, "verdict": "note",
                                       "evidence_type": "founder_judgment", "text": "noted from the phone"}, key=phone)
    for command in (pause, pending, critique):
        body.apply(command)
    result = body.apply(world.revoke("phone", suspected_compromise=True))["result"]
    return {"result": result, "phone_commands": [done["m:ran"], pause, pending, critique], "waiting": waiting}


def test_a_suspected_compromise_review_lists_exactly_the_devices_commands_and_resting_effects(world):
    with world.body() as body:
        made = compromised(world, body)
        [review] = [e.payload for e in body.journal.replay(revocation.REVIEW_RECORD)]
        assert made["result"]["integrity_review"] == review["review_id"]
        # the unused approval, and the standing remainder of the one whose write already ran
        assert made["result"]["voided_requests"] == sorted(body.engine.book.voided)
        assert made["waiting"]["request_id"] in body.engine.book.voided and len(body.engine.book.voided) == 2
        assert review["device"]["device_key_id"] == world.kid("phone") and review["device"]["label"] == "phone"
        assert review["status"] == "OPEN_FOR_FOUNDER_REVIEW"
        # every accepted command the phone signed, and no one else's
        assert [c["command_digest"] for c in review["commands"]] == [sha256_json(c) for c in made["phone_commands"]]
        assert [c["kind"] for c in review["commands"]] == ["DECISION", "LIFECYCLE", "DECISION", "CRITIQUE"]
        assert all(c["signature_verifies"] and c["signer"] == "device:phone" for c in review["commands"])
        standing = {c["mission_id"]: c["standing"].split(":")[0] for c in review["commands"] if c["kind"] == "DECISION"}
        assert standing == {"m:ran": "VOIDED_BY_THIS_REVOCATION", "m:waiting": "VOIDED_BY_THIS_REVOCATION"}
        # every effect that rested on its authority: the write it approved, with its receipt, and the pause it set
        [ran] = actions(body, "m:ran")
        effects = [(x["effect"], x.get("mission_id"), x.get("receipt")) for x in review["effects"]]
        assert effects == [("an action dispatched under its approval", "m:ran", ran["receipt"]),
                           ("a mission lifecycle it set", "m:waiting", None)]
        assert review["receipts"] == [ran["receipt"]] and review["missions"] == ["m:ran", "m:waiting"]
        assert review["voided_by_this_revocation"] == sorted(body.engine.book.voided)
        assert "m:laptop" not in json.dumps(review["effects"]) and "m:founder" not in json.dumps(review)
        assert review["history_rewritten"] is False and review["revokes_further"] is False
        # it rewrites nothing and revokes nothing further
        assert set(body.device_keys()) == {world.kid("laptop")}
        assert [a["status"] for mid in ("m:ran", "m:laptop", "m:founder") for a in actions(body, mid)] == ["DONE"] * 3
        assert body.ledger.verify_chain()[0]
        # the same revocation gives the same review whenever it is built: it reads the ledger as the revocation
        # left it, so what the key signs under a later delegation is not in it
        [revoked] = body.journal.replay("device.revoked")
        world.clock.advance(60)
        phone = world.enroll(body, "phone", ("DECISION", "LIFECYCLE", "CRITIQUE"))
        body.apply(world.sign("LIFECYCLE", {"mission_id": "m:waiting", "state": "ACTIVE", "reason": "later"},
                              key=phone))
        world.tick(body, 2)
        assert revocation.build_review(body.journal, revoked) == review


def test_a_review_that_cannot_be_built_is_recorded_as_such_and_the_body_keeps_turning(world, monkeypatch):
    """A review is a reading over everything a suspected key signed. If that reading fails, the revocation and its
    void still hold, the failure is recorded once as the review, the founder is still asked, and the body's turn
    (also a paused body's) never stops on it."""
    def broken(journal, revoked):
        raise KeyError("a record the reading did not expect")
    monkeypatch.setattr(revocation, "build_review", broken)
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = asked(world, body)
        body.apply(world.approve(ask["request_id"], key=phone))
        result = body.apply(world.revoke("phone", suspected_compromise=True))["result"]
        assert result["voided_requests"] == [ask["request_id"]]
        [review] = [e.payload for e in body.journal.replay(revocation.REVIEW_RECORD)]
        assert review["status"] == "COULD_NOT_BE_BUILT" and "KeyError" in review["error"]
        assert review["commands"] == [] and review["review_id"] == result["integrity_review"]
        body.apply(world.sign("BODY_PAUSE", {}))
        assert world.tick(body)["paused"]
        body.apply(world.sign("BODY_RESUME", {}))
        world.tick(body, 3)
        assert not note.exists() and len(body.journal.replay(revocation.REVIEW_RECORD)) == 1
    [shown] = [r for r in status(world.home)["decisions_required"] if r["kind"] == revocation.REVIEW_ASK]
    assert "could not be built" in shown["why_now"] and "KeyError" in shown["why_now"]


def test_what_a_revoked_device_resumed_keeps_running_and_the_review_lists_the_resume(world):
    """The founder's sentence does not settle this (ADR open question 3); this pins the draft's default. A mission
    the founder paused and the phone resumed, and a body the phone resumed, keep running after the phone is revoked:
    a resume is not a Gate approval, and the mission runs under its own founder-signed mandate. The review lists
    each resume, pause and stop the key signed, so the founder can pause again."""
    with world.body() as body:
        phone = world.enroll(body, "phone", ("LIFECYCLE", "BODY_PAUSE", "BODY_RESUME"))
        note = workspace(world.home, "m:free") / "n.txt"
        body.apply(world.sign("MISSION", mission("m:free", checks=[note_check("n", note, "x")],
                                                 strategies=[write_strategy("w", "n.txt", "x", ["n"])],
                                                 capabilities=["fs.read", "fs.write"])))
        body.apply(world.sign("LIFECYCLE", {"mission_id": "m:free", "state": "PAUSED", "reason": "the founder's"}))
        body.apply(world.sign("BODY_PAUSE", {}))
        world.tick(body, 2)
        assert not note.exists()
        resumes = [world.sign("LIFECYCLE", {"mission_id": "m:free", "state": "ACTIVE", "reason": "phone"}, key=phone),
                   world.sign("BODY_RESUME", {}, key=phone)]
        for command in resumes:
            body.apply(command)
        result = body.apply(world.revoke("phone", suspected_compromise=True))["result"]
        assert "voided_requests" not in result
        [review] = [e.payload for e in body.journal.replay(revocation.REVIEW_RECORD)]
        assert [c["command_digest"] for c in review["commands"]] == [sha256_json(c) for c in resumes]
        assert [(x["effect"], x.get("mission_id"), x.get("state")) for x in review["effects"]] == [
            ("a mission lifecycle it set", "m:free", "ACTIVE"), ("the body resumed by it", None, None)]
        world.tick(body, 4)
        assert not body.paused() and note.read_text() == "x"            # the default: what it resumed keeps running
        # what it resumed and what still runs is in the founder's status, also for a plain revocation
        body.apply(world.sign("MISSION", mission("m:held", checks=[note_check("n", note, "never")], strategies=[],
                                                 capabilities=["fs.read"])))
        laptop = world.enroll(body, "laptop", ("LIFECYCLE",))
        body.apply(world.sign("LIFECYCLE", {"mission_id": "m:held", "state": "ACTIVE", "reason": "no-op"}, key=laptop))
        body.apply(world.revoke("laptop"))
    rows = {r["device_key_id"]: r for r in status(world.home)["security"]["device_revocations"]}
    # m:free achieved since (it is listed while it runs, never after); the body is still resumed by the phone
    assert rows[world.kid("phone")]["resumed_and_still_running"] == {"missions": [], "body": True}
    assert "resumed_and_still_running" not in rows[world.kid("laptop")]   # its ACTIVE lifted no pause
    with world.body() as body:
        tablet = world.enroll(body, "tablet", ("LIFECYCLE",))
        body.apply(world.sign("LIFECYCLE", {"mission_id": "m:held", "state": "PAUSED", "reason": "mine again"}))
        body.apply(world.sign("LIFECYCLE", {"mission_id": "m:held", "state": "ACTIVE", "reason": "tablet"}, key=tablet))
        body.apply(world.revoke("tablet"))
        body.apply(world.sign("BODY_PAUSE", {}))
    rows = {r["device_key_id"]: r for r in status(world.home)["security"]["device_revocations"]}
    assert rows[world.kid("tablet")]["resumed_and_still_running"] == {"missions": ["m:held"], "body": False}
    assert "resumed_and_still_running" not in rows[world.kid("phone")]    # the founder paused the body since


def test_the_review_is_put_to_the_founder_where_pending_decisions_already_show(world):
    with world.body() as body:
        made = compromised(world, body)
        rid = made["result"]["integrity_review"]
    shown = {r["request_id"]: r for r in status(world.home)["decisions_required"]}
    ask = shown[rid]
    assert ask["kind"] == "DEVICE_INTEGRITY_REVIEW" and "suspected compromise" in ask["why_now"]
    assert ask["answer_effect"] == asks.ANSWER_ONLY_RECORDS["DEVICE_INTEGRITY_REVIEW"]
    assert ask["evidence"]["counts"] == {"commands": 4, "effects": 2, "voided_by_this_revocation": 2, "missions": 2,
                                         "receipts": 1}
    assert "wording_withheld" not in ask
    [row] = status(world.home)["security"]["device_revocations"]
    assert row["integrity_review"] == {"request_id": rid, "recorded": True, "state": "OPEN"}
    assert len(row["voided_requests"]) == 2
    # a device is offered no answer to it, and the body refuses one a device signs
    [for_device] = [r for r in asks.for_signer(list(shown.values()), "device:laptop") if r["request_id"] == rid]
    assert for_device["answerable"] is False
    assert asks.for_signer(list(shown.values()), "founder") == list(shown.values())
    with world.body() as body:
        laptop = world.devices["laptop"][0]
        with pytest.raises(MissionError, match="only the founder key"):
            body.apply(world.approve(rid, key=laptop))
        assert rid not in body.engine.book.answers
        before = len(body.journal.replay("device.revoked")), len(trail(body)), sorted(body.device_keys())
        body.apply(world.approve(rid))                       # the founder's answer is recorded and changes nothing
        world.tick(body, 2)
        assert body.engine.book.answers[rid]["answer"] == "approve"
        assert (len(body.journal.replay("device.revoked")), len(trail(body)), sorted(body.device_keys())) == before
    after = status(world.home)
    assert rid not in [r["request_id"] for r in after["decisions_required"]]
    assert after["security"]["device_revocations"][0]["integrity_review"]["state"] == "ANSWERED: approve"


def test_an_answer_row_for_a_review_that_a_device_signed_is_not_counted_by_the_fold(world):
    """The fold mirrors the command path: were a device's answer to a review ever accepted, it would not count."""
    with world.body() as body:
        made = compromised(world, body)
        rid = made["result"]["integrity_review"]
        book = body.engine.book
        request = book.requests[rid]
        signed = {"digest": "sha256:x", "principal": "device:laptop",
                  "envelope": {"body": {"request_id": rid, "answer": "approve"}}}
        row = {"request_id": rid, "mission_id": None, "answer": "approve", "reason": "", "command_digest": "sha256:x"}
        book._signed = {"sha256:x": {**signed, "kind": "DECISION"}}
        assert "only the founder key" in book._refusal(row, request, signed)
        assert book._refusal(row, request, {**signed, "principal": "founder"}) is None


# -- the separate appraiser enforces the same rule ----------------------------------------------------------------

def test_the_appraiser_refutes_an_act_dispatched_on_a_voided_approval(world, monkeypatch):
    """A body without this rule (the fold's void and the trail removed) acts on the revoked phone's approval, as
    8d205324 did; the separate appraiser re-derives the rule from the ledger and refutes the closure."""
    monkeypatch.setattr(MissionBook, "_revoked", lambda self, data, event_id: None)
    monkeypatch.setattr(revocation, "settle", lambda journal, book: {"voided": [], "reviews": []})
    with world.body() as body:
        body.boot()
        phone = world.enroll(body, "phone")
        note, ask = asked(world, body)
        body.apply(world.approve(ask["request_id"], key=phone))
        body.apply(world.revoke("phone"))
        world.tick(body, 4)
        assert note.read_text() == "approved"                 # the defect: it ran
        verdict = body.journal.replay("mission.appraised")[-1].payload
    assert verdict["verdict"] == "REFUTED" and verdict["checks"]["approval_boundaries_honored"] is False, verdict
    assert [f for f in verdict["findings"] if f.startswith("w: dispatched under an approval that was void")], verdict


# -- the founder's tools ---------------------------------------------------------------------------------------------

def test_the_cli_signs_a_suspected_compromise_revocation_and_reads_the_reviews(world, capsys):
    from greg import cli
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = asked(world, body)
        body.apply(world.approve(ask["request_id"], key=phone))
    key_file = str(world.tmp / "founder.pem")
    assert cli.main(["--home", str(world.home), "device", "revoke", world.kid("phone"), "--suspected-compromise",
                     "--key", key_file, "--no-passphrase"]) == 0
    [dropped] = (world.home / "inbox").glob("*.json")
    assert json.loads(dropped.read_text())["body"] == {"device_key_id": world.kid("phone"),
                                                       "suspected_compromise": True}
    with Body(world.home) as body:                       # the command carries the wall clock: so does this body
        assert [c["status"] for c in body.tick()["commands"]] == ["APPLIED"]
    capsys.readouterr()
    assert cli.main(["--home", str(world.home), "device", "reviews"]) == 0
    shown = json.loads(capsys.readouterr().out)
    [row], [review] = shown["revocations"], shown["reviews"]
    assert row["voided_requests"] == [ask["request_id"]] and row["integrity_review"]["state"] == "OPEN"
    assert review["device"]["device_key_id"] == world.kid("phone") and len(review["commands"]) == 1
    # a plain revocation is signed exactly as before
    with Body(world.home) as body:
        body.apply(sign_command(world.key, "DEVICE_ENROLL", world.grant("tablet"), body_id=world.body_id))
    assert cli.main(["--home", str(world.home), "device", "revoke", world.kid("tablet"), "--key", key_file,
                     "--no-passphrase"]) == 0
    [plain] = (world.home / "inbox").glob("*.json")
    assert json.loads(plain.read_text())["body"] == {"device_key_id": world.kid("tablet")}


def test_the_phone_channel_offers_a_device_no_answer_to_a_review(world):
    from datetime import datetime, timezone
    from greg import remote
    from greg.founder import sign_read
    with world.body() as body:
        made = compromised(world, body)
        rid = made["result"]["integrity_review"]
    now = datetime.now(timezone.utc)           # the remote channel reads the wall clock; the laptop is delegated
    laptop = world.devices["laptop"][0]

    def decisions(key):
        headers = sign_read(key, body_id=world.body_id, method="GET", path="/api/decisions", now=now)
        code, _, raw = remote.handle(world.home, "GET", "/api/decisions", headers, b"", now=now)
        assert code == 200
        return {r["request_id"]: r for r in json.loads(raw)["data"]}

    assert decisions(laptop)[rid]["answerable"] is False
    assert "only the founder key" in decisions(laptop)[rid]["answer_effect"]
    assert "answerable" not in decisions(world.key)[rid]


# -- a persistent goal bound to the mission (Goal Gravity, Mission F) ----------------------------------------------

def test_a_goal_does_not_take_a_revoked_devices_approval_as_its_answer(tmp_path, monkeypatch):
    """The goal asked ahead about the out-of-cone write and the phone approved it. Revoked before the mission ran
    it, that approval is neither the mission's authority nor the goal's answer; the goal's evidence says so."""
    from greg import goal_gravity as gg
    from tests.unit import test_greg_goal_gravity as mission_f
    monkeypatch.setattr(Body, "_close_out", lambda self, now: None)       # as that suite's ``fast`` fixture
    w = mission_f.World(tmp_path)
    gid, _ = w.start()
    phone = mission_f._device(w, ["DECISION"])
    w.tick(3)
    rid, scope = mission_f.expected_w2_request(w)
    assert [r["request_id"] for r in w.w2_requests()] == [rid]
    with w.body() as b:
        b.apply(w.sign("DECISION", {"request_id": rid, "answer": "approve", "reason": "ship it"}, key=phone))
        assert b.engine.book.missions[mission_f.MID].approved_scopes == {scope}
        b.apply(w.sign("DEVICE_REVOKE", {"device_key_id": next(iter(b.device_keys()))}))
    w.tick(4)
    assert not (w.ws / "d.txt").exists()
    with w.body() as b:
        book = b.engine.book
        assert book.missions[mission_f.MID].approved_scopes == set() and rid in book.voided
        shown = {a["request_id"]: a for a in gg.evidence(b.journal, gid)["asks"]}
        assert shown[rid]["answer"] == "approve" and "revoked" in shown[rid]["answer_voided"]
        again = [e.payload for e in b.journal.replay("decision.requested")
                 if e.payload.get("action_id") == "w2" and e.payload["request_id"] != rid]
        assert len(again) == 1 and again[0]["request_id"] not in book.answers       # asked again, still open
        b.apply(w.sign("DECISION", {"request_id": again[0]["request_id"], "answer": "approve", "reason": "mine"}))
    w.tick(4)
    assert (w.ws / "d.txt").read_text() == "shipped"


# -- the founder's words are kept as he wrote them ------------------------------------------------------------

def test_the_policy_is_recorded_verbatim_with_every_ledger_field():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    source = (root / "docs/intent/sources/REVOKED-DEVICE-AUTHORITY-2026-11-11-source.md").read_text(encoding="utf-8")
    record = json.loads((root / "docs/intent/INTENT-20261111-REVOKED-DEVICE-AUTHORITY.json").read_text())
    for sentence in ("My preferred policy is that revoking a device should immediately invalidate its unused "
                     "authority to authorize future execution.",
                     "Actions already legitimately completed must remain in the evidence ledger.",
                     "Revocation must not erase history or pretend an external effect never happened.",
                     "A suspected key compromise should trigger a separate retrospective integrity review.",
                     "Distinguish historical validity of a signature from its continuing authority to approve a "
                     "new effect.",
                     "Do not silently alter protected authority rules."):
        assert sentence in source and sentence in record["statement"]
    required = ["intent_id", "statement", "source_refs", "owner", "state", "binding_scope",
                "constitutional_constraints", "success_evidence", "failure_evidence", "dependencies", "conflicts",
                "next_review_trigger", "supersedes", "superseded_by", "implementation_refs"]
    assert not [k for k in required if k not in record]
    assert all((root / ref).exists() for ref in record["source_refs"] + record["implementation_refs"])
    assert record["intent_id"] in (root / "docs/FOUNDER_INTENT_LEDGER.md").read_text(encoding="utf-8")
