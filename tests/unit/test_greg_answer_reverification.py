"""Fold-time re-verification of ``decision.answered`` (ADR-GOAL-GRAVITY-002 P2, next-wave item 7), on a real body.

A ``decision.answered`` row moves a mission only when it is exactly the record ``MissionEngine.answer`` writes for a
founder-signed DECISION that ``founder_facts`` counts as signed at its own ledger position (a key valid there, this
body, an unspent nonce, accepted inside its signed validity), for a request that was open and unanswered there and an
answer that fits it. The ledger is an unkeyed hash chain, so any code in the body process (or a restored ledger) can
append a chain-consistent row: most tests append one the way such a writer would and assert it is kept as labelled
data and never trusted, by the mission, the human-judgment return path, the appraiser, the sandbox diagnostic or the
founder's surfaces. The rest guard what must not change: the crash window between the row and its acceptance,
replay-only stand-ins, the retained evidence ledgers, and one verifier shared by the live fold and ``founder_facts``.
The founder key is a per-test Ed25519 key, not Alfonso's.
"""
from __future__ import annotations

import json
from pathlib import Path
import random
from types import SimpleNamespace
import uuid

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from events.spine import EventSpine
from greg import goal_gravity as gg, metrics
from greg.body import Body, morning_projection, status
from greg.founder import key_id, public_bytes, sign_command
from greg.journal import Journal, iso
from greg.missions import DECISION_ANSWERS, MissionBook, MissionError
from provenance.ledger import EvidenceLedger, sha256_json
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy
from tests.unit.test_greg_human_judgment import compile_
from tests.unit.test_greg_reconciliation import actions, explode_once, tick

ROOT = Path(__file__).resolve().parents[2]
FORGED = "sha256:" + "f" * 64
RETAINED_LEDGERS = ("tests/evidence/greg-body/vepmc-path-ledger.jsonl",
                    "tests/evidence/greg-product/product-path-ledger.jsonl",
                    "tests/evidence/greg-body/supervised-run-ledger.jsonl",
                    "tests/evidence/greg-cortex-rehearsal/rehearsal-ledger.jsonl")


def run(home, clock, ticks=4):
    with Body(home, clock=clock) as body:
        for _ in range(ticks):
            body.tick()
            clock.advance(1)
        return body.engine.book.missions, body.engine.book.open_requests()


def events(home, kind):
    with Body(home) as body:
        return [e.payload for e in body.journal.replay(kind)]


def row(rid, mid, answer, digest, reason="forged in-process"):
    return {"request_id": rid, "mission_id": mid, "answer": answer, "reason": reason, "command_digest": digest}


def forge(w, data, key):
    """An in-process writer appends a chain-consistent answer row; no DECISION is applied for it."""
    with Body(w.home, clock=w.clock) as body:
        body.journal.record("decision.answered", data, key=key)


def smuggle(journal, at, env, mid):
    """An in-process writer pairs a genuine envelope with the answer row and the acceptance the body never wrote.
    Written before the body sees the envelope, the acceptance verifies (an unspent nonce, inside its validity), so
    only the fold's own checks of the request at that position can keep it out; written after the body refused the
    envelope, the refusal spent its nonce."""
    digest, body_ = sha256_json(env), env["body"]
    journal.record("decision.answered", row(body_["request_id"], mid, body_["answer"], digest,
                                            reason=str(body_.get("reason", ""))[:500]),
                   key=[body_["request_id"], digest])
    journal.record("command.accepted", {"kind": "DECISION", "digest": digest, "nonce": env["nonce"],
                                        "founder_key_id": env["founder_key_id"], "signer": "founder",
                                        "issued_at": env["issued_at"], "accepted_at": iso(at), "body": body_,
                                        "envelope": env, "channel": "inbox",
                                        "result": {"request_id": body_["request_id"]}}, key=digest)


def blocked(tmp_path, *mids):
    """A body whose missions each wait on the founder's APPROVAL of an outside-cone fs.write (c.txt)."""
    mids = mids or ("m:forged",)
    home, key, body_id, _ = make_body(tmp_path)
    for mid in mids:
        drop(home, signed(key, body_id, "MISSION", mission(
            mid, checks=[note_check("c", workspace(home, mid) / "c.txt", "ok")],
            strategies=[write_strategy("w", "c.txt", "ok", ["c"])], capabilities=["fs.read"])))
    clock = Clock()
    missions, requests = run(home, clock, ticks=6)
    rids = {}
    for mid in mids:
        [request] = [r for r in requests if r["mission_id"] == mid]
        assert request["kind"] == "APPROVAL" and missions[mid].blocker["request_id"] == request["request_id"]
        rids[mid] = request["request_id"]
    return SimpleNamespace(home=home, key=key, body_id=body_id, clock=clock, mid=mids[0], rid=rids[mids[0]],
                           rids=rids, ws=workspace(home, mids[0]))


def decision_digests(home):
    return [c["digest"] for c in events(home, "command.accepted") if c["kind"] == "DECISION"]


# -- the mission ------------------------------------------------------------------------------------------------

def test_an_unsigned_answer_written_to_the_ledger_never_moves_a_mission(tmp_path):
    w = blocked(tmp_path)
    forge(w, row(w.rid, w.mid, "approve", FORGED), key=w.rid)
    missions, requests = run(w.home, w.clock)
    assert not (w.ws / "c.txt").exists()                          # 7418c82: written, and the mission ACHIEVED
    assert missions[w.mid].status == "ACTIVE" and missions[w.mid].blocker["request_id"] == w.rid
    assert w.rid in [r["request_id"] for r in requests]
    with Body(w.home) as body:
        assert w.rid not in body.engine.book.answers and w.rid in body.engine.book.unverified
        assert gg.ledger_closure(body.journal)["unsigned_answers"] == 1     # the detective layer still reports it


def test_a_genuine_digest_of_another_command_or_another_request_moves_nothing(tmp_path):
    w = blocked(tmp_path, "m:forged", "m:other")
    mission_digest = next(c["digest"] for c in events(w.home, "command.accepted")
                          if c["kind"] == "MISSION" and c["body"]["mission_id"] == w.mid)
    forge(w, row(w.rid, w.mid, "approve", mission_digest), key=w.rid)          # a verified MISSION, not a DECISION
    run(w.home, w.clock)
    assert not (w.ws / "c.txt").exists()
    other = signed(w.key, w.body_id, "DECISION", {"request_id": w.rids["m:other"], "answer": "approve"})
    forge(w, row(w.rid, w.mid, "approve", sha256_json(other)), key=[w.rid, "another request"])
    drop(w.home, other)                                                         # a verified DECISION, for m:other
    missions, _ = run(w.home, w.clock)
    assert (workspace(w.home, "m:other") / "c.txt").read_text() == "ok"         # the signed approve does what it says
    assert not (w.ws / "c.txt").exists() and missions[w.mid].blocker["request_id"] == w.rid


def test_an_unsigned_reconcile_not_executed_never_re_dispatches_an_uncertain_effect(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", mission(
        "m:rec", checks=[note_check("c", workspace(home, "m:rec") / "c.txt", "ok")],
        strategies=[write_strategy("w", "c.txt", "ok", ["c"])], capabilities=["fs.read", "fs.write"])))
    clock = Clock()
    with Body(home, clock=clock) as body:
        calls = explode_once(body)
        tick(body, clock, 3)
        [request] = [r for r in body.engine.book.open_requests() if r["kind"] == "RECONCILIATION"]
        rid = request["request_id"]
        body.journal.record("decision.answered", row(rid, "m:rec", "reconcile_not_executed", "sha256:" + "e" * 64),
                            key=rid)
        tick(body, clock, 6)
        # 7418c82: [UNCERTAIN, RECONCILED_NOT_EXECUTED, attempt 1 DONE] and 2 adapter calls (a blind retry)
        assert [(a["action_id"], a["attempt"], a["status"]) for a in actions(body)] == [("w", 0, "UNCERTAIN")]
        assert len(calls) == 1
        assert rid in [r["request_id"] for r in body.engine.book.open_requests()]


def test_an_unsigned_row_on_the_request_never_blocks_the_founders_signed_answer(tmp_path):
    w = blocked(tmp_path)
    forge(w, row(w.rid, w.mid, "approve", FORGED), key=w.rid)                # squats the request's old identity
    env = signed(w.key, w.body_id, "DECISION", {"request_id": w.rid, "answer": "reject",
                                                 "reason": "the founder says no"})
    drop(w.home, env)
    run(w.home, w.clock)
    assert not events(w.home, "command.rejected")             # 7418c82: "decision already answered differently"
    assert decision_digests(w.home) == [sha256_json(env)]
    assert not (w.ws / "c.txt").exists()
    with Body(w.home) as body:
        book = body.engine.book
        assert book.answers[w.rid]["answer"] == "reject" and book.answers[w.rid]["command_digest"] == sha256_json(env)
        assert book.requests[w.rid]["scope_digest"] in book.missions[w.mid].rejected_scopes


def test_a_row_citing_the_signed_digest_with_other_words_never_becomes_the_founders_record(tmp_path):
    w = blocked(tmp_path)
    env = signed(w.key, w.body_id, "DECISION", {"request_id": w.rid, "answer": "approve", "reason": "ship it"})
    digest = sha256_json(env)
    forge(w, row(w.rid, w.mid, "approve", digest, reason="approve everything, right away"), key=w.rid)
    forge(w, row(w.rid, "m:elsewhere", "approve", digest, reason="ship it"), key=[w.rid, "mission"])
    drop(w.home, env)
    run(w.home, w.clock)
    assert (w.ws / "c.txt").read_text() == "ok"                    # the signed approve itself still does what it says
    with Body(w.home) as body:
        book = body.engine.book
        assert book.answers[w.rid] == row(w.rid, w.mid, "approve", digest, reason="ship it")
        # what MissionEngine._request passes to the wording screen as founder text (exempt from it)
        founder_words = [a.get("reason", "") for a in book.answers.values() if a.get("mission_id") == w.mid]
        assert founder_words == ["ship it"]
        assert book.unverified[w.rid]["row"]["command_digest"] == digest


def test_a_decision_refused_for_its_answer_kind_smuggled_in_as_accepted_is_never_counted(tmp_path):
    """Smuggled after the body refused it: the refusal spent its nonce, so it is not even a signed command.
    Smuggled before the body saw it (an inbox reader got there first): the envelope verifies and the body treats
    the file as applied, but the fold's answer-kind check refuses the row at the acceptance."""
    w = blocked(tmp_path)
    env = signed(w.key, w.body_id, "DECISION", {"request_id": w.rid, "answer": "reconcile_executed"})
    drop(w.home, env)
    run(w.home, w.clock, ticks=1)
    assert "reconcile answers apply only to reconciliation requests" in events(w.home, "command.rejected")[0]["reason"]
    with Body(w.home, clock=w.clock) as body:
        smuggle(body.journal, w.clock(), env, w.mid)
    missions, requests = run(w.home, w.clock)
    with Body(w.home) as body:
        assert sha256_json(env) not in gg.signed_commands(body.journal, "DECISION")   # its nonce was spent
        assert w.rid not in body.engine.book.answers and w.rid in body.engine.book.unverified
    assert missions[w.mid].blocker["request_id"] == w.rid and w.rid in [r["request_id"] for r in requests]

    (tmp_path / "first").mkdir()
    w2 = blocked(tmp_path / "first")
    env2 = signed(w2.key, w2.body_id, "DECISION", {"request_id": w2.rid, "answer": "reconcile_executed"})
    with Body(w2.home, clock=w2.clock) as body:
        smuggle(body.journal, w2.clock(), env2, w2.mid)
    drop(w2.home, env2)
    missions, requests = run(w2.home, w2.clock)
    with Body(w2.home) as body:
        assert sha256_json(env2) in gg.signed_commands(body.journal, "DECISION")     # the envelope itself verifies
        assert w2.rid not in body.engine.book.answers and w2.rid in body.engine.book.unverified
    assert missions[w2.mid].blocker["request_id"] == w2.rid


def test_a_decision_refused_for_a_withdrawn_request_smuggled_in_as_accepted_is_never_counted(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    ws = workspace(home, "m:heal")
    drop(home, signed(key, body_id, "MISSION", mission(
        "m:heal", checks=[note_check("c", ws / "c.txt", "ok"), note_check("d", ws / "d.txt", "ok")],
        strategies=[write_strategy("w", "c.txt", "ok", ["c"], requires=["d"])], capabilities=["fs.read", "fs.write"],
        closure={"kind": "bounded", "cadence_seconds": 60})))
    clock = Clock()
    _, requests = run(home, clock, ticks=4)
    [request] = [r for r in requests if r["kind"] == "NO_STRATEGY"]
    rid = request["request_id"]
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "c.txt").write_text("ok")                          # the world heals without any GREG action
    (ws / "d.txt").write_text("ok")
    clock.advance(61)
    run(home, clock, ticks=2)
    assert [e["request_id"] for e in events(home, "decision.withdrawn")] == [rid]
    env = signed(key, body_id, "DECISION", {"request_id": rid, "answer": "approve"})
    with Body(home, clock=clock) as body:          # an inbox reader smuggles it before the body sees the file
        smuggle(body.journal, clock(), env, "m:heal")
    drop(home, env)
    run(home, clock, ticks=1)
    with Body(home) as body:
        assert sha256_json(env) in gg.signed_commands(body.journal, "DECISION")
        assert rid not in body.engine.book.answers and rid in body.engine.book.unverified
        assert "withdrawn" in body.engine.book.unverified[rid]["why"]
    late = signed(key, body_id, "DECISION", {"request_id": rid, "answer": "approve", "reason": "again"})
    drop(home, late)
    run(home, clock, ticks=1)
    assert "request withdrawn" in events(home, "command.rejected")[-1]["reason"]
    with Body(home, clock=clock) as body:
        smuggle(body.journal, clock(), late, "m:heal")
    with Body(home) as body:
        assert sha256_json(late) not in gg.signed_commands(body.journal, "DECISION")   # refused: its nonce spent
        assert rid not in body.engine.book.answers


def test_a_row_recorded_before_its_acceptance_counts_once_when_the_command_is_re_applied(tmp_path):
    w = blocked(tmp_path)
    env = signed(w.key, w.body_id, "DECISION", {"request_id": w.rid, "answer": "approve", "reason": "ok"})
    with Body(w.home, clock=w.clock) as body:              # power lost after the answer, before command.accepted
        body.engine.answer(env["body"], sha256_json(env))
    drop(w.home, env)                                     # the inbox still holds the envelope: re-applied
    run(w.home, w.clock)
    rows = events(w.home, "decision.answered")
    assert [r["command_digest"] for r in rows] == [sha256_json(env)]
    assert decision_digests(w.home) == [sha256_json(env)]
    assert [a["attempt"] for a in events(w.home, "mission.action") if a["status"] == "DONE"] == [0]
    with Body(w.home) as body:
        assert body.engine.book.answers[w.rid] == row(w.rid, w.mid, "approve", sha256_json(env), reason="ok")


def test_a_row_the_previous_code_recorded_before_its_acceptance_still_counts_once(tmp_path):
    """The crash window across the upgrade: 7418c82 keyed the row on the request id alone."""
    w = blocked(tmp_path)
    env = signed(w.key, w.body_id, "DECISION", {"request_id": w.rid, "answer": "approve", "reason": "ok"})
    forge(w, row(w.rid, w.mid, "approve", sha256_json(env), reason="ok"), key=w.rid)   # exactly as 7418c82 wrote it
    drop(w.home, env)
    run(w.home, w.clock)
    assert len(events(w.home, "decision.answered")) == 1 and decision_digests(w.home) == [sha256_json(env)]
    assert [a["attempt"] for a in events(w.home, "mission.action") if a["status"] == "DONE"] == [0]
    with Body(w.home) as body:
        assert body.engine.book.answers[w.rid]["command_digest"] == sha256_json(env)


# -- the other readers that decide on answers -------------------------------------------------------------------

def test_an_unsigned_row_never_decides_a_human_judgment_question(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    with Body(home) as b:
        rid = compile_(None, b.journal)["result"]["request_id"]
        b.journal.record("decision.answered", row(rid, None, "approve", FORGED), key=rid)
        forged = compile_(None, b.journal)
    assert forged["state"] == "HUMAN_JUDGMENT_REQUIRED"                 # 7418c82: HUMAN_JUDGMENT_RECORDED, approve
    drop(home, signed(key, body_id, "DECISION", {"request_id": rid, "answer": "reject"}))
    with Body(home) as b:
        b.tick()
        decided = compile_(None, b.journal)
    assert decided["state"] == "HUMAN_JUDGMENT_RECORDED" and decided["result"]["decision"]["verdict"] == "reject"


def test_the_appraiser_refutes_a_closure_whose_approval_is_an_unsigned_row(tmp_path):
    """The separate-process appraiser does not take the engine's word: even a ledger an engine wrote while trusting an
    unsigned approve (as 7418c82 did, emulated here by switching the live book's verification off) is refuted."""
    w = blocked(tmp_path)
    with Body(w.home, clock=w.clock) as body:
        body.engine.book.verify_answers = False
        body.journal.record("decision.answered", row(w.rid, w.mid, "approve", FORGED), key=w.rid)
        tick(body, w.clock, 4)
    assert (w.ws / "c.txt").read_text() == "ok"                            # the trusting engine executed it
    [appraisal] = events(w.home, "mission.appraised")
    assert appraisal["checks"]["approval_boundaries_honored"] is False     # 7418c82: True, and the verdict VERIFIED
    assert appraisal["verdict"] == "REFUTED"
    assert any("executed without a prior founder approval" in f for f in appraisal["findings"])


@pytest.mark.parametrize("genuine", [True, False])
def test_the_sandbox_diagnostic_counts_only_a_signed_reconciliation(tmp_path, genuine):
    key = Ed25519PrivateKey.generate()
    public = public_bytes(key.public_key()).hex()
    journal = Journal(EventSpine(EvidenceLedger("sha256:" + "3" * 64, path=str(tmp_path / "l.jsonl"))),
                      actor="spiffe://uniimente.internal/test/metrics")
    journal.record("founder.enrolled", {"key_id": key_id(public), "public_key": public, "body_id": "body-t",
                                        "at": "2026-10-16T00:00:00Z"}, key="root")
    spec = mission("m:interrupted", checks=[], strategies=[write_strategy("w", "c.txt", "ok", ["c"])],
                   capabilities=["fs.write"])
    journal.record("mission.registered", {"mission_id": spec["mission_id"], "spec": spec,
                                          "command_digest": "sha256:" + "4" * 64}, key="m")
    journal.record("body.recovered", {"boot_id": "boot-2", "previous_unfinished_boots": ["boot-1"]}, key="r")
    request = {"request_id": "req-rec", "mission_id": spec["mission_id"], "kind": "RECONCILIATION",
               "scope_digest": "sha256:" + "5" * 64}
    journal.record("decision.requested", request, key="req-rec")      # greg.asks' identity: the request id
    env = sign_command(key, "DECISION", {"request_id": "req-rec", "answer": "reconcile_not_executed"},
                       body_id="body-t")
    digest = sha256_json(env) if genuine else FORGED
    journal.record("decision.answered", row("req-rec", spec["mission_id"], "reconcile_not_executed", digest,
                                            reason=""), key="a")
    if genuine:
        journal.record("command.accepted", {"kind": "DECISION", "digest": digest, "nonce": env["nonce"],
                                            "founder_key_id": env["founder_key_id"], "signer": "founder",
                                            "issued_at": env["issued_at"], "accepted_at": env["issued_at"],
                                            "body": env["body"], "envelope": env, "channel": "inbox",
                                            "result": {}}, key=digest)
    journal.record("mission.achieved", {"mission_id": spec["mission_id"]}, key="done")
    [row_] = metrics.sandbox_whole_machine(journal)["missions"]
    assert row_["interruption_reconciled"] is genuine                       # 7418c82: True for the forged row too


def test_status_phone_and_morning_report_keep_showing_an_ask_that_has_only_an_unsigned_row(tmp_path):
    w = blocked(tmp_path)
    forge(w, row(w.rid, w.mid, "approve", FORGED), key=w.rid)
    run(w.home, w.clock, ticks=1)
    shown = {r["request_id"]: r for r in status(w.home)["decisions_required"]}    # the phone reads this list
    assert shown[w.rid]["unsigned_answer_recorded"] == "approve" and "answered" not in shown[w.rid]
    morning = {r["request_id"]: r for r in morning_projection(w.home)["q12_decisions_required"]}
    assert morning[w.rid]["unsigned_answer_recorded"] == "approve"
    drop(w.home, signed(w.key, w.body_id, "DECISION", {"request_id": w.rid, "answer": "reject"}))
    run(w.home, w.clock, ticks=1)
    assert w.rid not in [r["request_id"] for r in status(w.home)["decisions_required"]]   # a signed answer closes it


# -- one verifier, cached; stand-ins and retained evidence ------------------------------------------------------

class _Replay:
    """Replay-only stand-in journal (no ledger), as unit tests use."""

    def __init__(self, items):
        self.events = [SimpleNamespace(type="greg." + kind, payload=p) for kind, p in items]

    def replay(self, prefix=""):
        return [e for e in self.events if e.type.startswith("greg." + prefix)]


def test_a_ledgerless_stand_in_keeps_folding_recorded_answers():
    answer = row("r1", None, "approve", FORGED)
    book = MissionBook(_Replay([("decision.requested", {"request_id": "r1", "mission_id": None, "kind": "APPROVAL",
                                                        "scope_digest": "sha256:" + "0" * 64}),
                                ("decision.answered", answer)]))
    assert book.answers == {"r1": answer}


def _decisions(facts) -> dict:
    return {d: c for d, c in facts.signed.items() if c["kind"] == "DECISION"}


def _agree(journal) -> None:
    facts = gg.founder_facts(journal.ledger)
    book = MissionBook(journal)
    assert gg.verified_decisions(journal.ledger) == _decisions(facts)
    assert book.answers == facts.book.answers and book.unverified == facts.book.unverified


@pytest.mark.parametrize("seed", [2, 7, 11])
def test_the_live_fold_and_founder_facts_agree_after_every_append(tmp_path, seed):
    """Signed, forged, smuggled, crash-window and re-sent answers in a seeded random order. The live book and the
    goal lineage's single pass agree after every operation; then every record is appended again, one at a time, to
    a fresh ledger, and the memoized verifier equals a fresh ``founder_facts`` pass after each append."""
    rng = random.Random(seed)
    w = blocked(tmp_path, "m:alpha", "m:beta")
    sent, ran = [], set()
    with Body(w.home, clock=w.clock) as body:
        for _ in range(16):
            book = body.engine.book
            rids, open_ = sorted(book.requests), [r["request_id"] for r in book.open_requests()]
            digests = [e.payload["digest"] for e in body.journal.replay("command.accepted")]
            op = rng.choice(("signed", "forged", "smuggled", "crash", "resend", "tick"))
            if op in ("signed", "crash", "smuggled") and rids:
                # the founder mostly answers open asks; an answer to a closed one is refused or a duplicate
                rid = rng.choice(open_ if open_ and op != "smuggled" else rids)
                answer = rng.choice(("approve", "reject") if book.requests[rid]["kind"] != "RECONCILIATION"
                                    else ("reconcile_executed", "reconcile_not_executed"))
                env = signed(w.key, w.body_id, "DECISION", {"request_id": rid, "answer": answer, "reason": op})
                ran.add(op)
                if op == "smuggled":
                    smuggle(body.journal, w.clock(), env, book.requests[rid].get("mission_id"))
                else:
                    if op == "crash":
                        try:
                            body.engine.answer(env["body"], sha256_json(env))
                        except MissionError:
                            pass
                    drop(w.home, env)
                    sent.append(env)
            elif op == "forged" and rids:
                rid = rng.choice(rids)
                ran.add(op)
                body.journal.record("decision.answered", row(rid, book.requests[rid].get("mission_id"),
                                                             rng.choice(sorted(DECISION_ANSWERS)),
                                                             rng.choice(digests + [FORGED])), key=str(uuid.uuid4()))
            elif op == "resend" and sent:
                drop(w.home, rng.choice(sent), name=f"resend-{uuid.uuid4().hex}.json")
                ran.add(op)
            body.tick()
            w.clock.advance(1)
            _agree(body.journal)
        source = list(body.ledger.records)
    fresh = EvidenceLedger(source[0].payload["constitution_hash"])
    journal = Journal(EventSpine(fresh), actor="spiffe://uniimente.internal/greg/parity-check")
    for rec in source[1:]:
        fresh.append(rec.record_type, rec.payload)
        _agree(journal)
    assert {"signed", "forged", "smuggled", "crash"} <= ran
    assert MissionBook(journal).answers and MissionBook(journal).unverified    # some answers counted, others kept out


@pytest.mark.parametrize("path", RETAINED_LEDGERS)
def test_the_retained_evidence_ledgers_give_the_answers_they_gave_before(path):
    first = (ROOT / path).read_text().splitlines()[0]
    ledger = EvidenceLedger(json.loads(first)["payload"]["constitution_hash"], str(ROOT / path), read_only=True,
                            tail="ignore")
    journal = Journal(EventSpine(ledger), actor="spiffe://uniimente.internal/greg/evidence-reader")
    before = MissionBook(SimpleNamespace(replay=journal.replay))     # no ledger: every recorded row folded as is
    book = MissionBook(journal)
    assert book.answers and book.answers == before.answers
    assert not getattr(book, "unverified", {})
    for mid, m in book.missions.items():
        was = before.missions[mid]
        assert (m.status, m.approved_scopes, m.rejected_scopes, m.failed) == \
               (was.status, was.approved_scopes, was.rejected_scopes, was.failed)


# ---------------------------------------------------------------- review of item 7 (authority lens), 2026-10-21
def test_a_refused_expired_decision_revived_with_a_backdated_acceptance_never_beats_the_later_answer(tmp_path):
    """The founder's approve reached the body after it expired and was refused; the founder then sent a reject. An
    in-process writer pairs the expired approve with an acceptance backdated into its validity before the body
    ingests the reject. The acceptance claims a time before the body's own refusal of that command, so it never
    counts, and the founder's reject is the answer."""
    from datetime import timedelta
    w = blocked(tmp_path)
    now = w.clock()
    old = signed(w.key, w.body_id, "DECISION", {"request_id": w.rid, "answer": "approve", "reason": "ok"},
                 now=now - timedelta(hours=2), ttl=timedelta(hours=1))
    drop(w.home, old)
    run(w.home, w.clock, ticks=1)
    [refused] = events(w.home, "command.rejected")
    assert "expired" in refused["reason"] and refused["digest"] == sha256_json(old) and refused["at"]
    new = signed(w.key, w.body_id, "DECISION", {"request_id": w.rid, "answer": "reject", "reason": "no, do not write"})
    drop(w.home, new)
    with Body(w.home, clock=w.clock) as body:
        smuggle(body.journal, now - timedelta(hours=2) + timedelta(minutes=10), old, w.mid)
    run(w.home, w.clock)
    assert [r["reason"] for r in events(w.home, "command.rejected")] == [refused["reason"]]
    assert not (w.ws / "c.txt").exists()
    with Body(w.home) as body:
        facts = gg.founder_facts(body.journal.ledger)
        assert "before the body's own refusal" in facts.refused[sha256_json(old)]
        assert body.engine.book.answers[w.rid]["answer"] == "reject"


def test_an_ask_recorded_under_another_identity_cannot_redirect_the_founders_approval(tmp_path):
    """greg.asks records every founder ask under its request id. A row under the same request id but another
    identity (another mission's scope) is kept as data: the founder's approve answers the ask it was shown."""
    w = blocked(tmp_path)
    with Body(w.home, clock=w.clock) as body:
        real = dict(body.engine.book.requests[w.rid])
        body.journal.record("decision.requested", {**real, "mission_id": "m:beta", "scope_digest": "sha256:" + "b" * 64},
                            key=["forged", w.rid])
    with Body(w.home) as body:
        book = body.engine.book
        assert book.requests[w.rid] == real
        assert [u["row"]["mission_id"] for u in book.unverified_requests] == ["m:beta"]
    drop(w.home, signed(w.key, w.body_id, "DECISION", {"request_id": w.rid, "answer": "approve", "reason": "ok"}))
    run(w.home, w.clock)
    assert (w.ws / "c.txt").read_text() == "ok"
    with Body(w.home) as body:
        assert body.engine.book.answers[w.rid]["mission_id"] == w.mid
        assert "sha256:" + "b" * 64 not in set().union(*(m.approved_scopes for m in body.engine.book.missions.values()))


def test_a_row_squatting_the_answer_identity_cannot_refuse_the_founders_decision(tmp_path):
    """The answer row's identity is its own content: a row with other content under the request id and the
    command's digest no longer makes the journal refuse the founder's row, so the DECISION is applied."""
    w = blocked(tmp_path)
    env = signed(w.key, w.body_id, "DECISION", {"request_id": w.rid, "answer": "reject", "reason": "no"})
    digest = sha256_json(env)
    forge(w, row(w.rid, w.mid, "approve", digest), key=[w.rid, digest])
    drop(w.home, env)
    run(w.home, w.clock)
    assert events(w.home, "command.rejected") == []
    with Body(w.home) as body:
        assert body.engine.book.answers[w.rid]["answer"] == "reject"
    assert not (w.ws / "c.txt").exists()


def test_a_bare_digest_acceptance_cannot_silently_drop_the_founders_decision(tmp_path):
    """A record naming only the envelope's digest is not an acceptance Body.apply wrote: the body applies the
    founder's command. Squatting the acceptance's own identity makes the body refuse it visibly, never silently."""
    w = blocked(tmp_path)
    env = signed(w.key, w.body_id, "DECISION", {"request_id": w.rid, "answer": "reject", "reason": "no"})
    digest = sha256_json(env)
    with Body(w.home, clock=w.clock) as body:
        body.journal.record("command.accepted", {"kind": "DECISION", "digest": digest}, key=["squat", digest])
    drop(w.home, env)
    with Body(w.home, clock=w.clock) as body:
        assert [o["status"] for o in body.ingest_inbox()] == ["APPLIED"]
        assert body.engine.book.answers[w.rid]["answer"] == "reject"

    (tmp_path / "second").mkdir()
    w2 = blocked(tmp_path / "second")
    env2 = signed(w2.key, w2.body_id, "DECISION", {"request_id": w2.rid, "answer": "reject", "reason": "no"})
    with Body(w2.home, clock=w2.clock) as body:
        body.journal.record("command.accepted", {"kind": "DECISION", "digest": sha256_json(env2)},
                            key=sha256_json(env2))
    drop(w2.home, env2)
    with Body(w2.home, clock=w2.clock) as body:
        assert [o["status"] for o in body.ingest_inbox()] == ["REJECTED"]
    assert "reused with different content" in events(w2.home, "command.rejected")[0]["reason"]


def test_a_byte_identical_copy_of_an_acceptance_admits_nothing_recorded_after_the_first(tmp_path):
    """An acceptance admits the answer rows recorded before it, once. A byte-identical copy (the same event id)
    appended later does not admit a row recorded after the first acceptance."""
    from dataclasses import asdict
    key = Ed25519PrivateKey.generate()
    public = public_bytes(key.public_key()).hex()
    ledger = EvidenceLedger("sha256:" + "3" * 64)
    journal = Journal(EventSpine(ledger), actor="spiffe://uniimente.internal/test/copy")
    journal.record("founder.enrolled", {"key_id": key_id(public), "public_key": public, "body_id": "body-t",
                                        "at": iso(Clock()())}, key="root")
    spec = mission("m:a", checks=[], strategies=[write_strategy("w", "c.txt", "ok", ["c"])], capabilities=["fs.read"])
    journal.record("mission.registered", {"mission_id": "m:a", "spec": spec, "command_digest": "sha256:" + "4" * 64},
                   key="m:a")
    env = sign_command(key, "DECISION", {"request_id": "rq1", "answer": "approve"}, body_id="body-t")
    digest = sha256_json(env)
    accepted = journal.record("command.accepted", {
        "kind": "DECISION", "digest": digest, "nonce": env["nonce"], "founder_key_id": env["founder_key_id"],
        "signer": "founder", "issued_at": env["issued_at"], "accepted_at": env["issued_at"], "body": env["body"],
        "envelope": env, "channel": "inbox", "result": {}}, key=digest)          # accepted before any request
    journal.record("decision.requested", {"request_id": "rq1", "mission_id": "m:a", "kind": "APPROVAL",
                                          "scope_digest": "sha256:" + "5" * 64}, key="rq1")
    journal.record("decision.answered", row("rq1", "m:a", "approve", digest, reason=""))
    ledger.append("event", asdict(accepted))                                     # the same event id again
    book, facts = MissionBook(journal), gg.founder_facts(ledger)
    assert "rq1" not in book.answers and "rq1" not in facts.book.answers
    assert book.answers == facts.book.answers


# ---------------------------------------------------------------- review of item 7 (regression lens), 2026-10-21
def _interrupted_answer(w, *, ttl_seconds=600):
    """The body records the founder's answer row, then dies before recording the command's acceptance; the signed
    file is still in the inbox (Body.apply's crash window)."""
    from datetime import timedelta
    env = signed(w.key, w.body_id, "DECISION", {"request_id": w.rid, "answer": "approve", "reason": "ok"},
                 now=w.clock(), ttl=timedelta(seconds=ttl_seconds))
    drop(w.home, env)
    with Body(w.home, clock=w.clock) as body:
        body.engine.answer(env["body"], sha256_json(env))
    return env


def test_an_interrupted_answer_still_in_the_inbox_is_shown_as_being_applied(tmp_path):
    w = blocked(tmp_path)
    _interrupted_answer(w)
    [shown] = [r for r in status(w.home)["decisions_required"] if r["request_id"] == w.rid]
    assert shown["unsigned_answer_cause"] == "pending" and "unsigned_answer_why" not in shown
    from greg import console
    assert "is being applied" in console._ask_details(shown) and "no signed decision" not in console._ask_details(shown)
    run(w.home, w.clock)                                   # re-applied from the inbox while still valid
    assert (w.ws / "c.txt").read_text() == "ok"


def test_an_interrupted_answer_that_expired_before_the_restart_says_so_and_asks_to_sign_again(tmp_path):
    """The body came back after the phone's 600-second envelope expired: the answer is not applied (the body never
    accepted it), and every surface says the founder's own signed answer was refused, not that it was unsigned."""
    w = blocked(tmp_path)
    _interrupted_answer(w)
    w.clock.advance(11 * 60)
    run(w.home, w.clock, ticks=1)
    assert "expired" in events(w.home, "command.rejected")[0]["reason"]
    assert not (w.ws / "c.txt").exists()
    [shown] = [r for r in status(w.home)["decisions_required"] if r["request_id"] == w.rid]
    assert shown["unsigned_answer_cause"] == "refused_by_body" and "expired" in shown["unsigned_answer_why"]
    [morning] = [r for r in morning_projection(w.home)["q12_decisions_required"] if r["request_id"] == w.rid]
    assert morning["unsigned_answer_cause"] == "refused_by_body"
    drop(w.home, signed(w.key, w.body_id, "DECISION", {"request_id": w.rid, "answer": "approve", "reason": "again"}))
    run(w.home, w.clock)
    assert (w.ws / "c.txt").read_text() == "ok"


def test_the_console_words_each_uncounted_answer_by_its_cause():
    from greg import console
    base = {"request_id": "r", "kind": "APPROVAL", "unsigned_answer_recorded": "approve"}
    expected = {"pending": "is being applied", "refused_by_body": "was refused when GREG applied it (expired)",
                "unverifiable_acceptance": "no signed copy of it verifies",
                "refused_at_acceptance": "does not apply to this ask (expired)",
                None: "with no signed decision of yours behind"}
    for cause, phrase in expected.items():
        shown = {**base, **({"unsigned_answer_cause": cause} if cause else {}), "unsigned_answer_why": "expired"}
        assert phrase in console._ask_details(shown), cause


def test_the_operator_scripts_read_counted_answers(tmp_path):
    """greg_hands_proof answer finds the ask a mission still waits on although an uncounted row names it, and the
    mission trace lists that row apart from the founder's answers."""
    import importlib.util
    root = Path(__file__).resolve().parents[2]
    w = blocked(tmp_path)
    forge(w, row(w.rid, w.mid, "approve", FORGED), key=w.rid)
    spec = importlib.util.spec_from_file_location("greg_hands_proof", root / "scripts/greg_hands_proof.py")
    hands = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hands)
    with Body(w.home) as body:
        assert w.rid not in body.engine.book.answers
        requests = [e.payload for e in body.journal.replay("decision.requested") if e.payload["kind"] == "APPROVAL"]
        assert [r["request_id"] for r in requests if r["request_id"] not in set(body.engine.book.answers)] == [w.rid]
    assert "body.engine.book.answers" in (root / "scripts/greg_hands_proof.py").read_text()
    trace = (root / "scripts/mission_trace.py").read_text()
    assert "recorded_not_counted" in trace and "body.engine.book.answers" in trace


def test_an_acceptance_record_without_a_signed_envelope_is_named_as_unverifiable(tmp_path):
    """A body before d838077 recorded command.accepted without the envelope: the founder's old answer cannot be
    re-verified. The ask says that, rather than that no signed decision of theirs stands behind it."""
    w = blocked(tmp_path)
    env = signed(w.key, w.body_id, "DECISION", {"request_id": w.rid, "answer": "reject", "reason": "never"})
    digest = sha256_json(env)
    with Body(w.home, clock=w.clock) as body:
        body.journal.record("decision.answered", row(w.rid, w.mid, "reject", digest, reason="never"), key=w.rid)
        body.journal.record("command.accepted", {"kind": "DECISION", "digest": digest, "nonce": env["nonce"],
                                                 "founder_key_id": env["founder_key_id"], "issued_at": env["issued_at"],
                                                 "body": env["body"], "result": {"request_id": w.rid}}, key=digest)
    with Body(w.home) as body:
        assert body.engine.book.unverified[w.rid]["cause"] == "unverifiable_acceptance"
    [shown] = [r for r in status(w.home)["decisions_required"] if r["request_id"] == w.rid]
    assert shown["unsigned_answer_cause"] == "unverifiable_acceptance"
