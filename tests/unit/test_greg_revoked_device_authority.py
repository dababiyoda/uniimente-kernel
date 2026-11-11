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


# -- compensations: the Gate's record decides, before any approval is looked at (independent review, finding 1) ---

RESTORE = {"capability": "fs.write", "params": {"relative_path": "note.txt", "content": "original"},
           "target": "workspace:note.txt"}


def compensable(world, body, mid="m:comp"):
    """A mission whose executed write has a signed compensation: write the original text back."""
    note = workspace(world.home, mid) / "note.txt"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("original")
    body.apply(world.sign("MISSION", mission(
        mid, checks=[note_check("c", note, "draft")],
        strategies=[write_strategy("w", "note.txt", "draft", ["c"], compensate=RESTORE)],
        capabilities=["fs.read", "fs.write"],
        closure={"kind": "infinite", "ladder": [["c"]], "cadence_seconds": 3600})))
    world.tick(body, 3)
    assert note.read_text() == "draft"
    return note


def superseded_and_asked(world, body, mid="m:comp"):
    """The founder superseded the mission: undoing its write is asked first (a successor may rely on it)."""
    note = compensable(world, body, mid)
    body.apply(world.sign("LIFECYCLE", {"mission_id": mid, "state": "SUPERSEDED", "reason": "replaced"}))
    world.tick(body, 2)
    [ask] = open_asks(body, mid)
    assert ask["compensation"] is True
    return note, ask


def compensated(body, mid="m:comp"):
    return [e.payload for e in body.journal.replay("mission.compensated") if e.payload["mission_id"] == mid]


def gate_record(body, ask, mid="m:comp"):
    """(dispatch claims, receipts) the Gate holds for the one proposal of this mission's compensation."""
    [ran] = [a for a in actions(body, mid) if a["status"] == "DONE"]
    proposal = body.engine.office.proposal_id(ask["scope_digest"], f"compensate:w:{ran['receipt']}")
    claims = body.ledger.select("grant_dispatch", proposal_id=proposal)
    receipts = [r for c in claims for r in body.ledger.select("receipt", grant_id=c.payload["grant_id"])]
    return claims, receipts


def killed_before_the_mission_records(body):
    """The body stops after the Gate's receipt of the compensation and before the mission's own record of it."""
    real = body.journal.record

    def record(kind, data, **kw):
        if kind == "mission.compensated":
            raise SystemExit("killed after the Gate's receipt, before the mission's record")
        return real(kind, data, **kw)
    body.journal.record = record
    with pytest.raises(SystemExit):
        body.tick()
    assert compensated(body) == []


@pytest.mark.parametrize("revoked", [False, True])
def test_a_compensation_the_gate_completed_is_recorded_from_its_receipt_whatever_became_of_its_approval(world, revoked):
    """The phone approves the compensation; the Gate dispatches it and writes its receipt; the body dies before
    ``mission.compensated``; the founder revokes the phone while the body is down. The restarted body records the
    compensation from the Gate's receipt. Before this fix it asked the founder to approve it again, said "nothing is
    run for it" about a write that had run, and recorded DECLINED with no receipt when he rejected."""
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = superseded_and_asked(world, body)
        decision = world.approve(ask["request_id"], key=phone)
        body.apply(decision)
        killed_before_the_mission_records(body)
        assert note.read_text() == "original"                       # the compensation DID run
        [claim], [receipt] = gate_record(body, ask)
        assert receipt.payload["result"]["result_class"] == "positive"
    if revoked:
        drop(world.home, world.revoke("phone"), "a-revoke.json")    # while the body is down
    with world.body() as body:
        world.tick(body, 3)
        [row] = compensated(body)
        assert row["status"] == "DONE" and row["receipt"] == receipt.hash and row["scope_digest"] == ask["scope_digest"]
        assert row["reasons"] == ["retained receipt of a compensation the body did not record before it stopped"]
        assert gate_record(body, ask) == ([claim], [receipt])       # the Gate never dispatched it a second time
        assert open_asks(body, "m:comp") == [] and open_asks(body, "m:comp", kind="COMPENSATION") == []
        assert note.read_text() == "original" and body.ledger.verify_chain()[0]
        if not revoked:
            return
        # what the approval had not been used for is void all the same, and nothing asks for it again
        [void] = trail(body, ask["request_id"])
        assert void["voids_approval"] is True
        # a suspicion signed later finds the compensation by the Gate grant issued while the approval stood,
        # although the mission recorded it only after the revocation
        body.apply(world.revoke("phone", suspected_compromise=True))
        [review] = [e.payload for e in body.journal.replay(revocation.REVIEW_RECORD)]
        [effect] = review["effects"]
        assert effect["effect"] == "a compensation dispatched under its approval"
        assert effect["receipt"] == receipt.hash and effect["rested_on"]["command_digest"] == sha256_json(decision)


def test_a_compensation_interrupted_inside_its_dispatch_is_recorded_as_unknown_not_asked_as_if_unrun(world):
    """The body dies inside the compensation's dispatch (the Gate's claim, no receipt), and the phone that approved
    it is revoked before the restart. The outcome is unknown: it is recorded UNCERTAIN and put to the founder as a
    COMPENSATION decision, exactly as without a revocation. It is never offered for approval as if nothing ran."""
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = superseded_and_asked(world, body)
        body.apply(world.approve(ask["request_id"], key=phone))
        real = body.registry.adapters["fs.write"]

        def dies(params, ctx):
            real(params, ctx)
            raise SystemExit("power lost after the write, before the Gate's receipt")
        body.registry.adapters["fs.write"] = dies
        with pytest.raises(SystemExit):
            body.tick()
        assert note.read_text() == "original" and compensated(body) == []
        [claim], receipts = gate_record(body, ask)
        assert receipts == []
    drop(world.home, world.revoke("phone"), "a-revoke.json")
    with world.body() as body:
        world.tick(body, 3)
        [row] = compensated(body)
        assert row["status"] == "UNCERTAIN" and row["receipt"] is None
        assert "outcome is unknown" in row["reasons"][0]
        assert open_asks(body, "m:comp") == []                      # no APPROVAL ask for an effect that may have run
        [question] = open_asks(body, "m:comp", kind="COMPENSATION")
        assert "outcome is unknown" in json.dumps(question["evidence"]["compensation_failed"])
        assert gate_record(body, ask) == ([claim], [])              # never dispatched again, never blind-retried
        body.apply(world.approve(question["request_id"], answer="reject"))
        world.tick(body, 3)
        assert [r["status"] for r in compensated(body)] == ["UNCERTAIN"]   # the answer is a record; DECLINED is never written


def test_a_refused_compensation_found_again_after_a_restart_is_recorded_as_the_refusal_it_was(world):
    """The Gate's receipt is read by its result, not by its existence: a compensation the capability refused is
    recorded REFUSED after the restart and the founder is asked about the effect, which still stands."""
    from greg.capabilities import CapabilityError
    with world.body() as body:
        note, ask = superseded_and_asked(world, body)
        body.apply(world.approve(ask["request_id"]))

        def refuses(params, ctx):
            raise CapabilityError("the disk is read-only")
        body.registry.adapters["fs.write"] = refuses
        killed_before_the_mission_records(body)
        [claim], [receipt] = gate_record(body, ask)
        assert receipt.payload["result"]["result_class"] == "negative" and note.read_text() == "draft"
    with world.body() as body:
        world.tick(body, 3)
        [row] = compensated(body)
        assert row["status"] == "REFUSED" and row["receipt"] == receipt.hash
        assert "the disk is read-only" in row["reasons"][0]
        [question] = open_asks(body, "m:comp", kind="COMPENSATION")
        assert "the disk is read-only" in json.dumps(question["evidence"]["compensation_failed"])
        assert gate_record(body, ask) == ([claim], [receipt]) and note.read_text() == "draft"


def test_a_compensation_approved_by_a_device_revoked_before_its_dispatch_does_not_run(world):
    """The same rule as for an action: the phone's approval of a compensation the Gate has not dispatched is void
    from the revocation on. The effect stands until the founder (or a device still delegated) answers the new ask."""
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = superseded_and_asked(world, body)
        drop(world.home, world.approve(ask["request_id"], key=phone), "a-decision.json")
        drop(world.home, world.revoke("phone"), "b-revoke.json")
        world.tick(body, 4)
        assert note.read_text() == "draft" and compensated(body) == [] and gate_record(body, ask) == ([], [])
        [again] = open_asks(body, "m:comp")
        assert again["request_id"] != ask["request_id"] and again["compensation"] is True
        [void] = trail(body, ask["request_id"])
        assert void["voids_approval"] is True
        body.apply(world.approve(again["request_id"]))              # the founder approves: it runs, once
        world.tick(body, 3)
        assert note.read_text() == "original" and [c["status"] for c in compensated(body)] == ["DONE"]
        assert [len(x) for x in gate_record(body, ask)] == [1, 1]


def test_the_review_lists_a_compensation_the_device_approved(world):
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = superseded_and_asked(world, body)
        decision = world.approve(ask["request_id"], key=phone)
        body.apply(decision)
        world.tick(body, 3)
        [row] = compensated(body)
        assert row["status"] == "DONE" and note.read_text() == "original"
        body.apply(world.revoke("phone", suspected_compromise=True))
        [review] = [e.payload for e in body.journal.replay(revocation.REVIEW_RECORD)]
        [effect] = review["effects"]
        assert effect["effect"] == "a compensation dispatched under its approval"
        assert effect["receipt"] == row["receipt"] and effect["original_receipt"] == row["original_receipt"]
        assert effect["rested_on"] == {"command_digest": sha256_json(decision), "kind": "DECISION",
                                       "request_id": ask["request_id"]}
        assert compensated(body) == [row]                           # the review changed nothing


def test_a_compensation_the_gate_completed_is_recorded_when_its_capability_was_detached_since(world):
    """The same reading, for a cause that is not a revocation (and predates this policy: 8d205324 did the same): the
    founder detaches the compensating capability while the body is down. The completed compensation is recorded
    from its receipt; before, the founder was told the capability "is not usable" about an effect already undone."""
    with world.body() as body:
        note, ask = superseded_and_asked(world, body)
        body.apply(world.approve(ask["request_id"]))
        killed_before_the_mission_records(body)
        [claim], [receipt] = gate_record(body, ask)
        assert note.read_text() == "original"
    drop(world.home, world.sign("CAPABILITY_DETACH", {"capability_id": "fs.write"}), "a-detach.json")
    with world.body() as body:
        world.tick(body, 3)
        [row] = compensated(body)
        assert row["status"] == "DONE" and row["receipt"] == receipt.hash and row["capability"] == "fs.write"
        assert open_asks(body, "m:comp", kind="COMPENSATION") == []


def test_a_receipt_that_does_not_say_what_happened_is_an_unknown_outcome_of_the_compensation(world):
    """The Gate's executor writes two result classes. A retained receipt of any other class does not say whether
    the capability acted: the compensation is unknown (asked about, never retried), neither done nor refused."""
    class Stub:
        def __init__(self, payload):
            self.payload, self.hash = payload, "sha256:" + "5" * 64
    with world.body() as body:
        engine = body.engine
        real = engine.office.prior
        try:
            for result, status_ in (({"result_class": "positive"}, "DONE"), ({"result_class": "negative"}, "REFUSED"),
                                    ({"result_class": "partial"}, "UNCERTAIN"), ("not a result", "UNCERTAIN")):
                engine.office.prior = lambda proposal_id: (Stub({"grant_id": "g"}), Stub({"result": result}))
                outcome = engine._dispatched_compensation("sha256:scope", "w", "sha256:original")
                assert (outcome.status, outcome.receipt_hash, outcome.grant_id) == (status_, "sha256:" + "5" * 64, "g")
            engine.office.prior = lambda proposal_id: (None, None)
            assert engine._dispatched_compensation("sha256:scope", "w", "sha256:original") is None
        finally:
            engine.office.prior = real


def test_an_interrupted_compensation_the_device_approved_is_listed_once(world):
    """Its record names no grant (its dispatch was interrupted): the review finds the grant by the compensation's
    proposal, so the dispatch is listed once, as the compensation, and not again as an unrecorded grant."""
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = superseded_and_asked(world, body)
        explode_once(body)                                          # the compensating write dies with no receipt
        body.apply(world.approve(ask["request_id"], key=phone))
        world.tick(body, 2)
        [row] = compensated(body)
        assert row["status"] == "UNCERTAIN" and row["receipt"] is None and "grant_id" not in row
        body.apply(world.revoke("phone", suspected_compromise=True))
        [review] = [e.payload for e in body.journal.replay(revocation.REVIEW_RECORD)]
        assert [(x["effect"], x["status"]) for x in review["effects"]] == [
            ("a compensation dispatched under its approval", "UNCERTAIN")]


# -- the review attributes to the key only what rested on it (independent review, finding 2) ----------------------

def scope_grants(body, scope):
    return [r for r in body.ledger.by_type("event") if r.payload.get("type") == "greg.authority.grant_issued"
            and r.payload.get("founder_approved_scope") and r.payload.get("scope_digest") == scope]


def standing(world, body, mid, *, wants="approved", writes="approved"):
    """A standing mission whose write lies outside its read-only cone; returns (note path, its open APPROVAL)."""
    note = workspace(world.home, mid) / "n.txt"
    body.apply(world.sign("MISSION", mission(
        mid, checks=[note_check("n", note, wants)], strategies=[write_strategy("w", "n.txt", writes, ["n"])],
        capabilities=["fs.read"], ceiling="read_only",
        closure={"kind": "infinite", "ladder": [["n"]], "cadence_seconds": 60})))
    world.tick(body, 2)
    [ask] = open_asks(body, mid)
    return note, ask


def cadence(world, body, times=3):
    for _ in range(times):
        world.clock.advance(61)
        world.tick(body, 2)


def test_a_late_suspicion_does_not_list_what_the_founder_approved_after_the_revocation(world):
    """The phone approves a standing write; it runs; the phone is revoked plainly; the FOUNDER approves the new ask
    and the write runs again; later the founder marks the revocation as a suspected compromise. The review lists the
    phone's run and nothing of the founder's: before this fix it listed the founder's dispatch as "granted under
    its approval, not yet recorded by the mission"."""
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = standing(world, body, "m:stand")
        decision = world.approve(ask["request_id"], key=phone)
        body.apply(decision)
        world.tick(body, 3)
        [first] = scope_grants(body, ask["scope_digest"])
        [ran] = [a for a in actions(body, "m:stand") if a["status"] == "DONE"]
        body.apply(world.revoke("phone"))                           # voids the standing remainder
        note.unlink()                                               # drift: the standing mission must write again
        cadence(world, body)
        [again] = open_asks(body, "m:stand")
        assert again["request_id"] != ask["request_id"] and again["scope_digest"] == ask["scope_digest"]
        body.apply(world.approve(again["request_id"]))              # the FOUNDER approves
        cadence(world, body)
        assert note.read_text() == "approved"
        [_, second] = scope_grants(body, ask["scope_digest"])
        assert len([a for a in actions(body, "m:stand") if a["status"] == "DONE"]) == 2
        body.apply(world.revoke("phone", suspected_compromise=True))
        [review] = [e.payload for e in body.journal.replay(revocation.REVIEW_RECORD)]
        [effect] = review["effects"]
        assert effect["effect"] == "an action dispatched under its approval" and effect["receipt"] == ran["receipt"]
        assert effect["rested_on"]["command_digest"] == sha256_json(decision)
        assert second.payload["grant_id"] not in json.dumps(review) and review["receipts"] == [ran["receipt"]]
        assert body.ledger.find(ran["receipt"]).payload["grant_id"] == first.payload["grant_id"]


def test_a_review_does_not_list_what_ran_after_the_devices_approval_was_withdrawn(world):
    """The phone's standing approval is withdrawn by the standing-approval regression (a run under it proved
    ineffective); the FOUNDER approves the ask that follows and the write runs again; then the phone, delegated all
    along, is revoked as a suspected compromise. The founder's dispatch is not the phone's."""
    mid = "m:regress"
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = standing(world, body, mid, wants="final", writes="draft")   # the run executes and proves ineffective
        body.apply(world.approve(ask["request_id"], key=phone))
        cadence(world, body, 4)
        assert [e.payload["request_id"] for e in body.journal.replay("autonomy.regressed")] == [ask["request_id"]]
        phones = scope_grants(body, ask["scope_digest"])
        note.write_text("final")                                    # the world passes once (by hand), then drifts
        cadence(world, body, 1)
        note.unlink()
        cadence(world, body)
        [again] = [r for r in open_asks(body, mid) if r["request_id"] != ask["request_id"]]
        body.apply(world.approve(again["request_id"]))              # the FOUNDER approves
        cadence(world, body, 2)
        founders = [g for g in scope_grants(body, ask["scope_digest"]) if g not in phones]
        assert phones and founders
        body.apply(world.revoke("phone", suspected_compromise=True))
        [review] = [e.payload for e in body.journal.replay(revocation.REVIEW_RECORD)]
        assert {x["effect"] for x in review["effects"]} == {"an action dispatched under its approval"}
        listed = {body.ledger.find(x["receipt"]).payload["grant_id"] for x in review["effects"]}
        assert listed == {g.payload["grant_id"] for g in phones}
        assert not [g for g in founders if g.payload["grant_id"] in json.dumps(review)]
        [command] = review["commands"]
        assert command["standing"].startswith("WITHDRAWN_EARLIER")


def test_a_late_suspicion_lists_a_dispatch_granted_under_the_approval_and_recorded_after_the_revocation(world, monkeypatch):
    """The Gate granted and ran the phone-approved write, the body died before recording it, the phone was revoked
    plainly, and the restarted body recorded the action from the Gate's receipt. A suspicion signed later lists that
    action: it rested on the phone's approval although its record follows the revocation."""
    with world.body() as body:
        body.boot()
        phone = world.enroll(body, "phone")
        note, ask = asked(world, body)
        decision = world.approve(ask["request_id"], key=phone)
        body.apply(decision)
        monkeypatch.setattr(body.engine, "_record_outcome", lambda *a, **k: (_ for _ in ()).throw(SystemExit("killed")))
        with pytest.raises(SystemExit):
            world.tick(body)
        assert note.read_text() == "approved" and actions(body, "m:gated") == []
    with world.body() as body:
        body.boot()
        body.apply(world.revoke("phone"))
        world.tick(body, 4)
        [done] = actions(body, "m:gated")
        assert done["status"] == "DONE"
        body.apply(world.revoke("phone", suspected_compromise=True))
        [review] = [e.payload for e in body.journal.replay(revocation.REVIEW_RECORD)]
        [effect] = review["effects"]
        assert effect["effect"] == "an action dispatched under its approval" and effect["receipt"] == done["receipt"]
        assert effect["rested_on"]["command_digest"] == sha256_json(decision)


def test_a_dispatch_reconciled_before_the_revocation_is_listed_once(world):
    """The phone-approved write's first dispatch is interrupted and the founder reconciles it as executed. The
    review lists the dispatch once, as the action under the phone's approval, not a second time for the record of
    the founder's reconciliation."""
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = asked(world, body)
        explode_once(body, after_effect=True)
        body.apply(world.approve(ask["request_id"], key=phone))
        world.tick(body, 2)
        [question] = open_asks(body, "m:gated", kind="RECONCILIATION")
        body.apply(world.approve(question["request_id"], answer="reconcile_executed"))
        world.tick(body, 3)
        records = actions(body, "m:gated")
        assert [a["status"] for a in records][0] == "UNCERTAIN" and len(records) == 2
        assert records[1]["route"] == "founder_reconciliation"
        body.apply(world.revoke("phone", suspected_compromise=True))
        [review] = [e.payload for e in body.journal.replay(revocation.REVIEW_RECORD)]
        rows = [(x["effect"], x["status"]) for x in review["effects"]]
        assert rows == [("an action dispatched under its approval", "UNCERTAIN")]


def test_a_record_that_names_no_grant_is_attributed_by_where_it_stands(world):
    """A dispatch found again under the earlier scope form is recorded UNCERTAIN with no grant id (greg/authority.py,
    "retained legacy dispatch"). Such a record rests on the phone's approval when it was written while the approval
    stood, and not when it was written after the revocation voided it. (The two rows are written here as that path
    writes them; the body is not turned afterwards.)"""
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = standing(world, body, "m:stand")
        body.apply(world.approve(ask["request_id"], key=phone))
        world.tick(body, 3)
        [ran] = [a for a in actions(body, "m:stand") if a["status"] == "DONE"]
        legacy = {**ran, "status": "UNCERTAIN", "receipt": None, "cost_usd": 0.0,
                  "reasons": ["retained legacy dispatch; no receipt or blind retry"]}
        body.journal.record("mission.action", {**legacy, "attempt": 91}, key=["m:stand", "w", 91, "legacy"])
        body.apply(world.revoke("phone"))
        body.journal.record("mission.action", {**legacy, "attempt": 92}, key=["m:stand", "w", 92, "legacy"])
        body.apply(world.revoke("phone", suspected_compromise=True))
        [review] = [e.payload for e in body.journal.replay(revocation.REVIEW_RECORD)]
        assert [(x["effect"], x["status"], x["attempt"]) for x in review["effects"]] == [
            ("an action dispatched under its approval", "DONE", ran["attempt"]),
            ("an action dispatched under its approval", "UNCERTAIN", 91)]


# -- a mission a revoked device ended (independent review, finding 3) ---------------------------------------------

def test_a_mission_a_revoked_device_abandoned_is_still_compensated_and_every_surface_says_so(world):
    """OPEN FOUNDER QUESTION (ADR open question 1); this pins the draft's default and what the founder is shown.

    The phone abandons a mission whose executed write has a signed compensation, and is revoked before the body's
    next turn. The compensation is dispatched after the revocation: ending a mission is not a Gate approval, and
    the compensation was signed by the founder with the mission. Nothing is held for the revocation. The review
    (read as the revocation left the ledger) says the compensation was still to run, and the founder's status lists
    it while it is owed and after it ran."""
    with world.body() as body:
        phone = world.enroll(body, "phone", ("LIFECYCLE",))
        note = compensable(world, body)
        [ran] = actions(body, "m:comp")
        body.apply(world.sign("BODY_PAUSE", {}))                    # so the turn that reads both steps no mission
        abandon = world.sign("LIFECYCLE", {"mission_id": "m:comp", "state": "ABANDONED", "reason": "phone"}, key=phone)
        drop(world.home, abandon, "a-abandon.json")
        drop(world.home, world.revoke("phone", suspected_compromise=True), "b-revoke.json")
        turn = world.tick(body)
        assert [c["status"] for c in turn["commands"]] == ["APPLIED", "APPLIED"] and turn["paused"]
        assert note.read_text() == "draft" and compensated(body) == []
        [revoked] = body.journal.replay("device.revoked")
        [review] = [e.payload for e in body.journal.replay(revocation.REVIEW_RECORD)]
        assert [c["command_digest"] for c in review["commands"]] == [sha256_json(abandon)]
        assert [(x["effect"], x.get("mission_id"), x.get("action_id")) for x in review["effects"]] == [
            ("a mission lifecycle it set", "m:comp", None), (revocation.STILL_TO_RUN, "m:comp", "w")]
        assert review["effects"][1]["original_receipt"] == ran["receipt"]
        assert review["effects"][1]["capability"] == "fs.write"
    row = status(world.home)["security"]["device_revocations"][0]
    assert row["ended_and_compensated"] == [{"mission_id": "m:comp", "state": "ABANDONED",
                                             "compensated_since_the_revocation": [], "still_to_run": ["w"]}]
    with world.body() as body:
        before = len([r for r in body.ledger.by_type("event") if r.payload.get("type") == "greg.authority.grant_issued"])
        body.apply(world.sign("BODY_RESUME", {}))
        world.tick(body, 3)
        assert note.read_text() == "original"                       # the default: it is compensated all the same
        [done] = compensated(body)
        assert done["status"] == "DONE" and done["original_receipt"] == ran["receipt"]
        seq = {r.payload.get("event_id"): r.seq for r in body.ledger.by_type("event")}
        new = [r for r in body.ledger.by_type("event") if r.payload.get("type") == "greg.authority.grant_issued"][before:]
        assert len(new) == 1 and new[0].seq > seq[revoked.event_id]
        assert new[0].payload["founder_approved_scope"] is False    # under the mission's mandate, no one's approval
        assert revocation.build_review(body.journal, revoked) == review     # the review is a reading of that moment
    row = status(world.home)["security"]["device_revocations"][0]
    assert row["ended_and_compensated"] == [{
        "mission_id": "m:comp", "state": "ABANDONED", "still_to_run": [],
        "compensated_since_the_revocation": [{"action_id": "w", "status": "DONE", "receipt": done["receipt"]}]}]


def test_only_what_the_revoked_key_itself_ended_is_listed_under_its_revocation(world):
    """Not listed under the phone's revocation: a mission the founder ended, one the laptop ended, one the phone
    ended that was compensated before the revocation, and one it ended whose write has no signed compensation
    (nothing runs for it). A mission the key ends under a later delegation is listed under that delegation's
    revocation only, and never under another key's revocation that came in between."""
    with world.body() as body:
        phone, laptop = world.enroll(body, "phone", ("LIFECYCLE",)), world.enroll(body, "laptop", ("LIFECYCLE",))
        for mid, key in (("m:founder", None), ("m:laptop", laptop), ("m:early", phone)):
            compensable(world, body, mid)
            body.apply(world.sign("LIFECYCLE", {"mission_id": mid, "state": "ABANDONED", "reason": "x"}, key=key))
            world.tick(body, 3)
            assert [c["status"] for c in compensated(body, mid)] == ["DONE"]
        plain = workspace(world.home, "m:plain") / "n.txt"
        body.apply(world.sign("MISSION", mission("m:plain", checks=[note_check("n", plain, "x")],
                                                 strategies=[write_strategy("w", "n.txt", "x", ["n"])],
                                                 capabilities=["fs.read", "fs.write"],
                                                 closure={"kind": "infinite", "ladder": [["n"]], "cadence_seconds": 3600})))
        world.tick(body, 3)
        assert plain.read_text() == "x"
        body.apply(world.sign("LIFECYCLE", {"mission_id": "m:plain", "state": "ABANDONED", "reason": "x"}, key=phone))
        world.tick(body, 2)
        assert compensated(body, "m:plain") == []                   # an open obligation: no compensation was signed
        body.apply(world.revoke("phone"))
        world.clock.advance(60)
        world.enroll(body, "phone", ("LIFECYCLE",))
        compensable(world, body, "m:late")
        body.apply(world.sign("BODY_PAUSE", {}))
        body.apply(world.sign("LIFECYCLE", {"mission_id": "m:late", "state": "ABANDONED", "reason": "x"}, key=phone))
        body.apply(world.revoke("laptop"))
        body.apply(world.revoke("phone"))
    rows = status(world.home)["security"]["device_revocations"]
    assert [r["device_key_id"] for r in rows] == [world.kid("phone"), world.kid("laptop"), world.kid("phone")]
    assert "ended_and_compensated" not in rows[0] and "ended_and_compensated" not in rows[1]
    assert rows[2]["ended_and_compensated"] == [{"mission_id": "m:late", "state": "ABANDONED",
                                                 "compensated_since_the_revocation": [], "still_to_run": ["w"]}]


# -- safeguards the independent review found without a failing test (finding 4, and its other survivors) ----------

def test_voiding_a_devices_reconciliation_answer_leaves_the_founders_approval_of_the_action(world):
    """The FOUNDER approved the write; its first dispatch's completion is unknown; the phone answers the
    reconciliation and is revoked before the engine records that answer. Only the phone's answer is void. A
    RECONCILIATION ask carries the action's scope digest, so a careless void would take the founder's approval."""
    mid = "m:gated"
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = asked(world, body, mid=mid)
        explode_once(body)
        body.apply(world.approve(ask["request_id"]))                # the founder's own approval
        world.tick(body, 2)
        [question] = open_asks(body, mid, kind="RECONCILIATION")
        assert question["scope_digest"] == ask["scope_digest"]
        drop(world.home, world.approve(question["request_id"], key=phone, answer="reconcile_not_executed"), "a.json")
        drop(world.home, world.revoke("phone"), "b.json")
        world.tick(body, 2)
        assert question["request_id"] in body.engine.book.voided
        assert body.engine.book.missions[mid].approved_scopes == {ask["scope_digest"]}
        [again] = open_asks(body, mid, kind="RECONCILIATION")
        body.apply(world.approve(again["request_id"], answer="reconcile_not_executed"))
        world.tick(body, 4)
        assert note.exists() and open_asks(body, mid) == []         # the retry ran on the founder's approval


def appraised(body):
    return body.journal.replay("mission.appraised")[-1].payload


def test_the_appraiser_refutes_nothing_for_another_devices_revocation(world):
    """The laptop approves; the PHONE is revoked before the dispatch. The laptop's approval was in force."""
    with world.body() as body:
        body.boot()
        world.enroll(body, "phone")
        laptop = world.enroll(body, "laptop")
        note, ask = asked(world, body)
        body.apply(world.approve(ask["request_id"], key=laptop))
        body.apply(world.revoke("phone"))
        world.tick(body, 4)
        assert note.read_text() == "approved"
        verdict = appraised(body)
        assert verdict["verdict"] == "VERIFIED" and verdict["checks"]["approval_boundaries_honored"] is True, verdict


def test_the_appraiser_accepts_a_fresh_approval_of_a_key_delegated_again(world):
    """The phone was revoked before it approved anything and delegated again; its approval under the new delegation
    is in force. Only a revocation between an answer and the dispatch voids that answer."""
    with world.body() as body:
        body.boot()
        phone = world.enroll(body, "phone")
        note, ask = asked(world, body)
        body.apply(world.revoke("phone"))
        world.clock.advance(60)
        world.enroll(body, "phone")
        world.clock.advance(5)
        body.apply(world.approve(ask["request_id"], key=phone))
        world.tick(body, 4)
        assert note.read_text() == "approved"
        verdict = appraised(body)
        assert verdict["verdict"] == "VERIFIED" and verdict["checks"]["approval_boundaries_honored"] is True, verdict


def test_the_review_lists_an_exclusion_an_abandons_compensation_and_a_settled_reconciliation(world):
    with world.body() as body:
        phone = world.enroll(body, "phone", ("DECISION", "CRITIQUE", "LIFECYCLE"))
        note = compensable(world, body)                             # abandoned by the phone; the compensation runs
        abandon = world.sign("LIFECYCLE", {"mission_id": "m:comp", "state": "ABANDONED", "reason": "phone"}, key=phone)
        body.apply(abandon)
        world.tick(body, 3)
        [undone] = compensated(body)
        assert note.read_text() == "original" and undone["status"] == "DONE"
        _, question, _ = uncertain(world, body)                     # an interrupted dispatch the phone reconciles
        reconcile = world.approve(question["request_id"], key=phone, answer="reconcile_executed")
        body.apply(reconcile)
        world.tick(body, 2)
        target = [e for e in body.journal.replay("mission.action") if e.payload["mission_id"] == "m:uncertain"][0]
        critique = world.sign("CRITIQUE", {"target_event_id": target.event_id, "verdict": "reject",
                                           "evidence_type": "founder_judgment", "text": "not this way",
                                           "exclude_strategy": True}, key=phone)
        body.apply(critique)
        body.apply(world.revoke("phone", suspected_compromise=True))
        [review] = [e.payload for e in body.journal.replay(revocation.REVIEW_RECORD)]
        assert [c["command_digest"] for c in review["commands"]] == [sha256_json(c) for c in (abandon, reconcile, critique)]
        rows = [(x["effect"], x.get("mission_id"), x.get("action_id"), x["rested_on"]["command_digest"])
                for x in review["effects"]]
        assert rows == [
            ("a mission lifecycle it set", "m:comp", None, sha256_json(abandon)),
            ("a compensation run after it ended the mission", "m:comp", "w", sha256_json(abandon)),
            ("an interrupted dispatch settled by its answer", "m:uncertain", "w", sha256_json(reconcile)),
            ("a strategy excluded by its critique", "m:uncertain", "w", sha256_json(critique))]
        assert review["effects"][1]["receipt"] == undone["receipt"]


def test_the_review_lists_a_compensation_obligation_the_devices_answer_closed(world):
    """The compensating capability is detached, so the effect is put to the founder; the phone answers "the effect
    stands"; the obligation is closed by that answer. The review lists the closure under the phone's DECISION."""
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note = compensable(world, body)
        body.apply(world.sign("CAPABILITY_DETACH", {"capability_id": "fs.write"}))
        world.tick(body)
        body.apply(world.sign("LIFECYCLE", {"mission_id": "m:comp", "state": "ABANDONED", "reason": "over"}))
        world.tick(body, 2)
        [question] = open_asks(body, "m:comp", kind="COMPENSATION")
        answer = world.approve(question["request_id"], key=phone, answer="reject")
        body.apply(answer)
        world.tick(body, 2)
        [closed] = compensated(body)
        assert closed["status"] == "FOUNDER_DECIDED" and closed["request_id"] == question["request_id"]
        body.apply(world.revoke("phone", suspected_compromise=True))
        [review] = [e.payload for e in body.journal.replay(revocation.REVIEW_RECORD)]
        [effect] = review["effects"]
        assert effect["effect"] == "a compensation obligation closed by its answer" and effect["action_id"] == "w"
        assert effect["rested_on"]["command_digest"] == sha256_json(answer)
        assert note.read_text() == "draft"


def test_each_revocation_lists_only_what_it_voided_itself(world):
    """Two delegations of one key, each revoked while one of its approvals was unused: the status lists under each
    revocation what that revocation voided, and the review of the second says the first approval was voided
    earlier."""
    with world.body() as body:
        phone = world.enroll(body, "phone")
        _, one = asked(world, body, mid="m:one")
        body.apply(world.approve(one["request_id"], key=phone))
        body.apply(world.revoke("phone"))
        world.clock.advance(60)
        world.enroll(body, "phone")
        world.clock.advance(5)
        _, two = asked(world, body, mid="m:two")
        body.apply(world.approve(two["request_id"], key=phone))
        result = body.apply(world.revoke("phone", suspected_compromise=True))["result"]
        assert result["voided_requests"] == [two["request_id"]]
        [review] = [e.payload for e in body.journal.replay(revocation.REVIEW_RECORD)]
        standing_of = {c["request_id"]: c["standing"].split(":")[0].split(" ")[0] for c in review["commands"]}
        assert standing_of == {one["request_id"]: "VOIDED_BY_AN_EARLIER_REVOCATION",
                               two["request_id"]: "VOIDED_BY_THIS_REVOCATION"}
        assert review["voided_by_this_revocation"] == [two["request_id"]]
    rows = status(world.home)["security"]["device_revocations"]
    assert [r["voided_requests"] for r in rows] == [[one["request_id"]], [two["request_id"]]]


def test_a_listed_command_verifies_only_as_the_envelope_its_digest_names(world):
    """``signature_verifies`` says the listed digest is the digest of an envelope the delegated key signed. A row
    whose digest names something other than its envelope does not verify, whatever the envelope's own signature."""
    with world.body() as body:
        phone = world.enroll(body, "phone")
        _, ask = asked(world, body)
        decision = world.approve(ask["request_id"], key=phone)
        body.apply(decision)
        [accepted] = [e.payload for e in body.journal.replay("command.accepted") if e.payload["kind"] == "DECISION"]
        other = world.sign("DECISION", {"request_id": "req-other", "answer": "reject", "reason": "x"}, key=phone)
        body.journal.record("command.accepted", {**accepted, "digest": "sha256:" + "0" * 64, "envelope": other},
                            key=["forged-row"])
        body.apply(world.revoke("phone", suspected_compromise=True))
        [review] = [e.payload for e in body.journal.replay(revocation.REVIEW_RECORD)]
        assert [(c["command_digest"], c["signature_verifies"]) for c in review["commands"]] == [
            (sha256_json(decision), True), ("sha256:" + "0" * 64, False)]


def test_the_ask_carries_the_first_rows_of_a_long_review_and_says_where_the_rest_is(world):
    with world.body() as body:
        phone = world.enroll(body, "phone", ("BODY_PAUSE", "BODY_RESUME"))
        for i in range(revocation.ASK_SHOWN // 2 + 1):
            body.apply(world.sign("BODY_PAUSE", {}, key=phone))
            body.apply(world.sign("BODY_RESUME", {}, key=phone))
        result = body.apply(world.revoke("phone", suspected_compromise=True))["result"]
        [review] = [e.payload for e in body.journal.replay(revocation.REVIEW_RECORD)]
        assert len(review["commands"]) == len(review["effects"]) == revocation.ASK_SHOWN + 2
        ask = body.engine.book.requests[result["integrity_review"]]
        evidence = ask["evidence"]
        assert len(evidence["commands"]) == len(evidence["effects"]) == revocation.ASK_SHOWN
        assert evidence["truncated"] is True and evidence["counts"]["commands"] == revocation.ASK_SHOWN + 2
        assert [c["command_digest"] for c in evidence["commands"]] == [
            c["command_digest"] for c in review["commands"][:revocation.ASK_SHOWN]]


def test_a_void_made_by_a_restore_names_the_restore(world):
    """A restore voids every device delegation by a revocation record of its own; the fold's void of the phone's
    unused approval names that restore."""
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
    with world.body() as body:
        body.boot()
        void = body.engine.book.voided[ask["request_id"]]
        assert void["voided_by"]["restore_id"] == report["restore_id"]
        assert void["voided_by"]["device_key_id"] == world.kid("phone")
