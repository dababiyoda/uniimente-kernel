"""Directive section 22 (S22.A4): after a real outcome each formed capability is proposed RETAIN, REPAIR, REGRESS or
REMOVE, never self-applied.

On a real body, a construction Genesis formed answers portfolio questions; signed REALIZATION reports then settle its
answers (the realized values are synthetic, not buyer outcomes). Each tick the body reviews every formed capability
with settled outcomes and records a proposal; a change to anything but RETAIN asks the founder and withdraws the
earlier ask. The registry is never changed by the review: only the founder's own signed command detaches or attaches.
"""
from __future__ import annotations

import inspect

import pytest

from greg import asks, disposition
from greg.cognition import settlement


def row(cid="c.new", function="f", settled=0, correct=0, faults=0, state="ATTACHED"):
    low, high = settlement._wilson(correct, settled)
    return {"capability_id": cid, "function": function, "origin": "composed", "state": state,
            "in_service_quarantines": faults, "settled": settled, "correct": correct,
            "wilson95": [round(low, 4), round(high, 4)], "outcomes": []}


def test_the_rules_follow_the_settlement_demotion_bound():
    assert disposition.judge(row(settled=3, correct=3), [])[0] == "RETAIN"
    assert disposition.judge(row(settled=3, correct=3, faults=1), [])[0] == "REPAIR"     # a fault in service
    assert disposition.judge(row(settled=2, correct=1), [])[0] == "REPAIR"
    assert disposition.judge(row(settled=3, correct=0), [])[0] == "REPAIR"   # upper bound 0.56: not yet demoted
    assert disposition.judge(row(settled=4, correct=0), [])[0] == "REMOVE"   # upper bound 0.49: demoted
    earlier = row("c.old", settled=5, correct=5)
    verdict, why, back = disposition.judge(row(settled=4, correct=0), [earlier])
    assert verdict == "REGRESS" and back is earlier and "c.old" in why
    for gone in (row("c.old", settled=5, correct=5, state="DETACHED"), row("c.old", settled=5, correct=5,
                 state="QUARANTINED"), row("c.old", settled=4, correct=0), row("c.old")):
        # detached, quarantined, itself demoted, or never settled: nothing to go back to
        assert disposition.judge(row(settled=4, correct=0), [gone])[0] == "REMOVE"


def test_the_review_writes_no_capability_state_and_inherits_no_command():
    source = inspect.getsource(disposition)
    assert "set_state" not in source and '"capability.state", {' not in source
    assert "CAPABILITY_DISPOSITION" in asks.ANSWER_ONLY_RECORDS
    assert "only recorded" in asks.ANSWER_ONLY_RECORDS["CAPABILITY_DISPOSITION"]


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
        run.ask("disp-kept", PORTFOLIO)
        cid = construction_id(run.body)
        run.body.tick()
        [p] = proposals(run.body, cid)
        assert p["disposition"] == "RETAIN" and p["evidence"]["settled"] == p["evidence"]["correct"] == 1
        assert p["applied"] is False and p["authority_created"] is False and p["request_id"] is None
        assert disposition_asks(run.body) == []
        run.body.tick()
        assert len(proposals(run.body, cid)) == 1                 # same evidence: reviewed once


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
        for k in range(1, 3):                                     # 2 and 3 wrong of 2 and 3: still REPAIR
            wrong(run, f"disp-{k}")
            assert [a["request_id"] for a in disposition_asks(run.body)] == [repair["request_id"]]
        wrong(run, "disp-3")                                      # 4 wrong of 4: the upper bound falls below 1/2
        latest = proposals(run.body, cid)[-1]
        assert latest["disposition"] == "REMOVE" and latest["evidence"]["settled"] == 4
        assert latest["applies_by"] == "the founder's signed command: CAPABILITY_DETACH"
        [ask] = disposition_asks(run.body)
        assert ask["request_id"] == latest["request_id"] != repair["request_id"]
        [withdrawn] = [e.payload for e in run.body.journal.replay("decision.withdrawn")
                       if e.payload["request_id"] == repair["request_id"]]
        assert withdrawn["why"].startswith(f"superseded: the disposition of {cid} is now REMOVE")
        assert run.body.registry.state[cid] == "ATTACHED" and states(run.body) == before    # proposed, not applied
        assert run.command("DECISION", {"request_id": ask["request_id"], "answer": "approve"})["status"] == "APPLIED"
        run.body.tick()
        assert run.body.registry.state[cid] == "ATTACHED" and states(run.body) == before    # an answer applies nothing
        # each answer is reviewed twice: as answered (its certificate counts it correct), then as realized short
        assert [p["evidence"]["correct"] for p in proposals(run.body, cid)] == [1, 0, 1, 0, 1, 0, 1, 0]
        reviewed = len(proposals(run.body, cid))
        assert run.command("CAPABILITY_DETACH", {"capability_id": cid})["status"] == "APPLIED"
        run.body.tick()
        assert run.body.registry.state[cid] == "DETACHED" and len(proposals(run.body, cid)) == reviewed
        assert [e.payload["why"] for e in run.body.journal.replay("decision.withdrawn")
                if e.payload["request_id"] == latest["request_id"]] == [f"the founder detached {cid}"]
