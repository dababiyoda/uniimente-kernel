"""Directive section 22 (S22.A4): after a real outcome each formed capability is proposed RETAIN, REPAIR, REGRESS or
REMOVE, never self-applied.

The rules use the body's own demotion (``compiler._settled_inhibition``: ten counted outcomes, Wilson upper bound
below one half). Once the world has judged an answer of a capability, certificate-only answers wait as pending, so a
demoted capability does not flap back to REPAIR on answers nobody has checked. Each change to anything but RETAIN asks
the founder once, under a request id never used before; every other open disposition ask on that capability is
withdrawn, an answered one is not asked again for the same disposition, and an ask the founder's detach made moot is
asked again after a re-attach. The registry is never changed by the review: only the founder's own signed command
detaches or attaches.

The journal scenarios run on a real Journal with the settled outcomes injected; the body scenarios run a construction
Genesis formed, settled by signed REALIZATION reports (the realized values are synthetic, not buyer outcomes).
"""
from __future__ import annotations

from datetime import datetime, timezone
import inspect

import pytest

from events.spine import EventSpine
from greg import asks, disposition
from greg.cognition import settlement
from greg.journal import Journal
from provenance.ledger import EvidenceLedger


def row(cid="c.new", function="f", settled=0, correct=0, faults=0, state="ATTACHED"):
    low, high = settlement._wilson(correct, settled)
    return {"capability_id": cid, "function": function, "origin": "composed", "state": state,
            "in_service_quarantines": faults, "quarantine_why": None, "settled": settled, "correct": correct,
            "tier": "world", "pending": 0, "wilson95": [low, high], "outcomes": []}


def test_the_rules_follow_the_bodys_own_demotion():
    assert disposition.judge(row(settled=3, correct=3), [])[0] == "RETAIN"
    assert disposition.judge(row(settled=3, correct=3, faults=1), [])[0] == "REPAIR"     # a fault in service
    assert disposition.judge(row(settled=2, correct=1), [])[0] == "REPAIR"
    assert disposition.judge(row(settled=9, correct=0), [])[0] == "REPAIR"   # the compiler does not demote below 10
    assert disposition.judge(row(settled=10, correct=0), [])[0] == "REMOVE"
    assert disposition.judge(row(settled=204, correct=88), [])[0] == "REMOVE"     # upper bound 0.499986, unrounded
    earlier = row("c.old", settled=5, correct=5, state="VERIFIED")
    verdict, why, back = disposition.judge(row(settled=10, correct=0), [earlier])
    assert verdict == "REGRESS" and back is earlier and "c.old" in why
    for gone in (row("c.old", settled=5, correct=5, state="DETACHED"), row("c.old", settled=5, correct=5,
                 state="QUARANTINED"), row("c.old", settled=10, correct=0), row("c.old", settled=3, correct=0),
                 row("c.old", settled=3, correct=1), row("c.old")):
        # out of service, demoted, wrong more often than right, or never settled: nothing to go back to
        assert disposition.judge(row(settled=10, correct=0), [gone])[0] == "REMOVE"


def test_the_review_writes_no_capability_state_and_inherits_no_command():
    source = inspect.getsource(disposition)
    assert "set_state" not in source and '"capability.state", {' not in source
    assert "CAPABILITY_DISPOSITION" in asks.ANSWER_ONLY_RECORDS
    assert "only recorded" in asks.ANSWER_ONLY_RECORDS["CAPABILITY_DISPOSITION"]


# -- on a real Journal, with the settled outcomes injected -------------------------------------------

class Ledger:
    def __init__(self, monkeypatch):
        self.journal = Journal(EventSpine(EvidenceLedger("disposition-fixture")),
                               actor="spiffe://uniimente.internal/test/disposition")
        self.outcomes, self.n, self.clock = [], 0, 0
        monkeypatch.setattr(disposition, "measured_outcomes", lambda journal: list(self.outcomes))

    def register(self, cid, provider="composed:r", kind="composed", function="f", state="ATTACHED"):
        self.n += 1
        origin = {"function": function, **({"kind": kind} if kind else {})}
        self.journal.record("capability.registered", {"manifest": {"capability_id": cid, "provider": provider,
                                                                   "function": function},
                                                      "origin": origin, "state": state}, key=[cid, self.n])

    def state(self, cid, state, why=""):
        self.n += 1
        self.journal.record("capability.state", {"capability_id": cid, "state": state, "why": why},
                            key=[cid, state, self.n])

    def outcome(self, cid, correct, world=True):
        self.n += 1
        self.outcomes.append({"method": cid, "correct": correct, "appraisal_event": f"appraisal-{self.n}",
                              **({"world": {"state": "reported"}} if world else {})})

    def review(self):
        self.clock += 1
        return disposition.propose(self.journal, datetime(2026, 11, 4, 18, self.clock, tzinfo=timezone.utc))

    def proposals(self, cid="c"):
        return [e.payload for e in self.journal.replay("capability.disposition_proposed")
                if e.payload["capability_id"] == cid]

    def open_asks(self):
        return [r["request_id"] for r in asks.open_requests(self.journal.replay())
                if r["kind"] == "CAPABILITY_DISPOSITION"]

    def withdrawals(self, rid):
        return [e.payload["why"] for e in self.journal.replay("decision.withdrawn") if e.payload["request_id"] == rid]


@pytest.fixture
def L(monkeypatch):
    return Ledger(monkeypatch)


def test_returning_to_earlier_evidence_asks_again_under_a_new_request_id(L):
    L.register("c")
    for _ in range(10):
        L.outcome("c", False)
    L.review()
    [r1] = L.open_asks()
    tenth = L.outcomes.pop()                   # a disputed report drops the tenth outcome: 0 of 9, not demoted
    L.review()
    [r2] = L.open_asks()
    L.outcomes.append(tenth)                   # a resolution restores it: the evidence of the first REMOVE again
    L.review()
    [r3] = L.open_asks()
    assert len({r1, r2, r3}) == 3 and [p["disposition"] for p in L.proposals()] == ["REMOVE", "REPAIR", "REMOVE"]
    assert L.proposals()[0]["evidence_digest"] == L.proposals()[2]["evidence_digest"]
    assert L.proposals()[-1]["request_id"] == r3
    assert len(L.withdrawals(r1)) == len(L.withdrawals(r2)) == 1 and L.withdrawals(r3) == []


def test_a_crash_between_ask_and_proposal_leaves_no_orphaned_ask(L, monkeypatch):
    L.register("c")
    L.outcome("c", False)
    L.review()
    [r0] = L.open_asks()
    for _ in range(9):
        L.outcome("c", False)
    record = L.journal.record

    def dies_once(kind, data, **kw):
        if kind == "capability.disposition_proposed":
            monkeypatch.setattr(L.journal, "record", record)
            raise RuntimeError("killed before the proposal fact")
        return record(kind, data, **kw)
    monkeypatch.setattr(L.journal, "record", dies_once)
    with pytest.raises(RuntimeError):
        L.review()
    [orphan] = L.open_asks()                   # the REMOVE ask was recorded, its proposal was not
    L.outcome("c", False)                      # new evidence arrives before the next review
    L.review()
    [kept] = L.open_asks()
    assert kept != orphan and L.withdrawals(orphan) and len(L.withdrawals(r0)) == 1
    assert L.proposals()[-1]["disposition"] == "REMOVE" and L.proposals()[-1]["request_id"] == kept


def test_a_detach_makes_the_ask_moot_and_a_re_attach_with_new_evidence_asks_again(L):
    L.register("c")
    L.outcome("c", False)
    L.review()
    [r] = L.open_asks()
    L.state("c", "DETACHED")
    L.review()
    assert L.open_asks() == [] and L.withdrawals(r) == ["the founder detached c"]
    L.state("c", "ATTACHED")
    L.outcome("c", False)
    L.review()
    [again] = L.open_asks()
    assert again != r and L.proposals()[-1]["request_id"] == again and L.withdrawals(r) == ["the founder detached c"]


def test_an_answered_ask_is_not_asked_again_for_the_same_disposition(L):
    L.register("c")
    L.outcome("c", False)
    L.review()
    [r] = L.open_asks()
    L.journal.record("decision.answered", {"request_id": r, "answer": "reject", "mission_id": None},
                     key=[r, "answered"])
    L.outcome("c", False)
    L.review()
    assert L.open_asks() == [] and L.proposals()[-1]["disposition"] == "REPAIR"
    assert L.proposals()[-1]["request_id"] is None and L.proposals()[-1]["evidence"]["settled"] == 2
    for _ in range(8):
        L.outcome("c", False)
    L.review()
    [removal] = L.open_asks()
    assert L.proposals()[-1]["disposition"] == "REMOVE" and L.proposals()[-1]["request_id"] == removal


def test_certificate_only_answers_wait_as_pending_once_the_world_judges_the_capability(L):
    L.register("c")
    L.outcome("c", True, world=False)
    L.review()
    [first] = L.proposals()
    assert first["disposition"] == "RETAIN" and first["evidence"]["tier"] == "certificate"
    for _ in range(10):
        L.outcome("c", False)
    L.review()
    [r] = L.open_asks()
    assert L.proposals()[-1]["disposition"] == "REMOVE" and L.proposals()[-1]["evidence"]["tier"] == "world"
    reviewed = len(L.proposals())
    L.outcome("c", True, world=False)          # a new answer, judged only by its certificate so far
    L.review()
    assert len(L.proposals()) == reviewed and L.open_asks() == [r]        # no flap to REPAIR on an unchecked answer
    L.outcomes[-1] = {**L.outcomes[-1], "correct": False, "world": {"state": "reported"}}   # realized short
    L.review()
    assert L.proposals()[-1]["disposition"] == "REMOVE" and L.proposals()[-1]["evidence"]["settled"] == 11
    assert L.open_asks() == [r] and L.proposals()[-1]["request_id"] == r


def test_every_formed_provider_is_reviewed_and_faults_count_without_outcomes(L):
    L.register("b", provider="built:coding-agent", kind="built")
    L.register("w", provider="installed:wc", kind=None)              # the catalog-binary route records no kind
    L.register("p", provider="package:x", kind="package")            # not a provider Genesis forms
    for cid in ("b", "w", "p"):
        L.state(cid, "QUARANTINED", "failed in service: capability refused: built capability exited 1")
    L.review()
    assert L.journal.replay("capability.disposition_proposed") == []    # out of service: Genesis's repair decides
    for cid in ("b", "w", "p"):
        L.state(cid, "VERIFIED", "recovered: eligibility only")          # back in service, with a fault on record
    L.review()
    made = {e.payload["capability_id"]: e.payload for e in L.journal.replay("capability.disposition_proposed")}
    assert set(made) == {"b", "w"} and {p["disposition"] for p in made.values()} == {"REPAIR"}
    assert made["w"]["origin"] == "installed" and made["b"]["evidence"]["settled"] == 0


def test_a_capability_whose_identity_changed_is_not_reviewed(L):
    L.register("c")
    for _ in range(3):
        L.outcome("c", True)
    L.state("c", "QUARANTINED", "reduction code changed since qualification")
    L.review()
    assert L.proposals() == []


def test_a_later_registration_resets_the_state_as_genesis_does(L):
    L.register("c.old")
    for _ in range(5):
        L.outcome("c.old", True)
    L.state("c.old", "QUARANTINED", "failed in service: capability refused: composed engine faulted")
    L.register("c.old", state="VERIFIED")      # re-qualified on another deficit, under the same id
    L.register("c.new")
    for _ in range(10):
        L.outcome("c.new", False)
    L.review()
    latest = L.proposals("c.new")[-1]
    assert latest["disposition"] == "REGRESS" and latest["regress_to"] == "c.old"


# -- on a real body -------------------------------------------------------------------------------

pytest.importorskip("networkx")
pytest.importorskip("scipy")

from tests.unit.test_greg_construction_realization import PORTFOLIO, PROMISED, Run, construction_id  # noqa: E402


def proposals(body, cid):
    return [e.payload for e in body.journal.replay("capability.disposition_proposed")
            if e.payload["capability_id"] == cid]


def disposition_asks(body):
    return [r for r in asks.open_requests(body.journal.replay()) if r["kind"] == "CAPABILITY_DISPOSITION"]


def states(body):
    return [e.payload for e in body.journal.replay("capability.state")]


def wrong(run, pid):
    record = run.ask(pid, PORTFOLIO)
    assert run.realize(record, PROMISED - 1)["result"]["met"] is False
    run.body.tick()
    return record


def test_a_correct_settled_outcome_is_retained_quietly(tmp_path):
    with Run(tmp_path) as run:
        record = run.ask("disp-kept", PORTFOLIO)
        cid = construction_id(run.body)
        run.body.tick()
        [p] = proposals(run.body, cid)
        assert p["disposition"] == "RETAIN" and p["evidence"]["tier"] == "certificate"
        assert p["applied"] is False and p["authority_created"] is False and p["request_id"] is None
        assert run.realize(record, PROMISED)["result"]["met"] is True
        run.body.tick()
        run.body.tick()
        latest = proposals(run.body, cid)
        assert [q["evidence"]["tier"] for q in latest] == ["certificate", "world"]      # same evidence: reviewed once
        assert latest[-1]["disposition"] == "RETAIN" and disposition_asks(run.body) == []


def test_wrong_outcomes_move_from_repair_to_remove_asking_once_each_and_never_touching_the_registry(tmp_path):
    with Run(tmp_path) as run:
        wrong(run, "disp-0")
        cid = construction_id(run.body)
        assert run.body.registry.state[cid] == "ATTACHED"
        before = states(run.body)
        [repair] = [p for p in proposals(run.body, cid) if p["disposition"] == "REPAIR"]
        assert repair["evidence"]["settled"] == 1 and repair["evidence"]["correct"] == 0
        [ask] = disposition_asks(run.body)
        assert ask["request_id"] == repair["request_id"] and ask["capability_id"] == cid
        assert ask["authority_requested"]["spend"] == "none"
        assert "only recorded" in asks.surface(ask)["answer_effect"]
        for k in range(1, 9):                                     # 2 .. 9 wrong: the compiler does not demote yet
            wrong(run, f"disp-{k}")
            assert [a["request_id"] for a in disposition_asks(run.body)] == [repair["request_id"]]
        wrong(run, "disp-9")                                      # 10 wrong of 10: demoted by the body's own rule
        latest = proposals(run.body, cid)[-1]
        assert latest["disposition"] == "REMOVE" and latest["evidence"]["settled"] == 10
        assert latest["applies_by"] == "the founder's signed command: CAPABILITY_DETACH"
        [ask] = disposition_asks(run.body)
        assert ask["request_id"] == latest["request_id"] != repair["request_id"]
        [withdrawn] = [e.payload for e in run.body.journal.replay("decision.withdrawn")
                       if e.payload["request_id"] == repair["request_id"]]
        assert withdrawn["why"].startswith(f"superseded: the disposition of {cid} is now REMOVE")
        assert run.body.registry.state[cid] == "ATTACHED" and states(run.body) == before    # proposed, not applied
        # each answer waits as pending until it is realized, so the record never flaps back to a better disposition
        assert [p["disposition"] for p in proposals(run.body, cid)] == ["RETAIN"] + ["REPAIR"] * 9 + ["REMOVE"]
        assert [p["evidence"]["settled"] for p in proposals(run.body, cid)] == [1] + list(range(1, 11))
        assert run.command("DECISION", {"request_id": ask["request_id"], "answer": "approve"})["status"] == "APPLIED"
        run.body.tick()
        assert run.body.registry.state[cid] == "ATTACHED" and states(run.body) == before    # an answer applies nothing
        reviewed = len(proposals(run.body, cid))
        assert run.command("CAPABILITY_DETACH", {"capability_id": cid})["status"] == "APPLIED"
        run.body.tick()
        assert run.body.registry.state[cid] == "DETACHED" and len(proposals(run.body, cid)) == reviewed
        assert disposition_asks(run.body) == []
