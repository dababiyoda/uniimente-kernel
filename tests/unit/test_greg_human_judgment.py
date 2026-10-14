"""Human judgment returns as typed evidence; only the founder's signed answer to THIS question decides
(directive sections 4, 9)."""
from types import SimpleNamespace

import pytest

from greg.body import Body
from greg.cognition import human
from greg.cognition.contracts import CognitionError
from greg.cognition.cortex import reason, registry_view
from tests.greg_fixtures import drop, make_body, signed

DIGEST = "sha256:" + "f" * 64


class Journal:
    """Replay-only stand-in for the canonical journal (events carry the ``greg.`` prefix)."""

    def __init__(self, events):
        self.events = [SimpleNamespace(type="greg." + kind, payload=p) for kind, p in events]

    def replay(self, prefix=""):
        return [e for e in self.events if e.type.startswith("greg." + prefix)]


def judgment(ref, role, verdict, evidence_ref=None, **kw):
    return {"participant_ref": ref, "role": role, "competence_domain": kw.get("domain", "claims policy"),
            "conflicts": kw.get("conflicts", []), "verdict": verdict, "rationale": kw.get("why", f"{ref} reasons"),
            **({"evidence_ref": evidence_ref} if evidence_ref else {})}


QUESTION = {"question": "may the claims policy exclude late filers?"}


def compile_(judgments, journal=None, data=QUESTION, pid="h"):
    body = {"geometry": {"geometry": "normative", "human_judgment_required": True}, "data": data,
            "human": {"roles": ["founder", "domain_expert", "affected_participant"],
                      **({"judgments": judgments} if judgments is not None else {})}}
    return reason({"problem_id": pid, "compile": body}, registry=registry_view(), journal=journal)


def question_ids(data=QUESTION, pid="h"):
    r = compile_(None, data=data, pid=pid)
    return r["result"]["request_id"], r["result"]["scope_digest"]


def answered(answer, data=QUESTION, pid="h", scope=None):
    rid, digest = question_ids(data, pid)
    return Journal([("decision.requested", {"request_id": rid, "kind": "HUMAN_JUDGMENT", "scope_digest": scope or digest}),
                    ("decision.answered", {"request_id": rid, "answer": answer, "command_digest": DIGEST})]), rid


def test_a_majority_never_decides_the_founders_signed_answer_to_this_question_does():
    journal, rid = answered("reject")
    js = [judgment("expert:a", "domain_expert", "approve"), judgment("expert:b", "domain_expert", "approve"),
          judgment("participant:c", "affected_participant", "approve"),
          judgment("founder:alfonso", "founder", "reject", evidence_ref=rid)]
    r = compile_(js, journal)
    assert r["state"] == "HUMAN_JUDGMENT_RECORDED"
    assert r["result"]["decision"]["verdict"] == "reject"                    # 3 approvals do not outvote it
    assert r["result"]["decision"]["decided_by"] == f"signed decision.answered {rid}"
    assert r["result"]["decision"]["command_digest"] == DIGEST
    assert sum("approve" in d for d in r["dissent"]) == 3                     # the minority views are preserved
    assert r["human_judgments"]["aggregation"].startswith("none")
    assert r["human_judgments"]["authority_created"] is False


def test_a_signed_answer_to_another_request_decides_nothing_here():
    """Review finding 1: the founder's approval of an unrelated newsletter send decided a rights question."""
    other = Journal([("decision.requested", {"request_id": "approve-newsletter-send", "kind": "RESOURCE",
                                             "scope_digest": "sha256:" + "a" * 64}),
                     ("decision.answered", {"request_id": "approve-newsletter-send", "mission_id": "m:newsletter",
                                            "answer": "approve", "command_digest": "sha256:" + "a" * 64})])
    r = compile_([judgment("founder:alfonso", "founder", "approve", evidence_ref="approve-newsletter-send")], other)
    assert r["state"] == "HUMAN_JUDGMENT_REQUIRED" and r["human_judgments"]["decision"] is None
    assert r["human_judgments"]["judgments"][0]["provenance"] == "UNVERIFIED_PROVENANCE"


def test_a_request_recorded_under_this_id_for_another_question_decides_nothing():
    journal, rid = answered("approve", scope="sha256:" + "b" * 64)
    r = compile_([judgment("founder:alfonso", "founder", "approve", evidence_ref=rid)], journal)
    assert r["state"] == "HUMAN_JUDGMENT_REQUIRED" and r["human_judgments"]["decision"] is None


def test_the_answer_binds_the_question_not_the_problem_id():
    journal, rid = answered("approve")
    changed = {"question": "may the claims policy exclude every filer?"}
    r = compile_([judgment("founder:alfonso", "founder", "approve", evidence_ref=rid)], journal, data=changed)
    assert r["state"] == "HUMAN_JUDGMENT_REQUIRED"
    assert r["result"]["request_id"] != rid


def test_an_unsigned_judgment_never_cancels_or_rewords_the_signed_answer():
    """Review finding 1: a second judgment claiming to be the founder cancelled the real signed answer."""
    journal, rid = answered("reject")
    js = [judgment("founder:alfonso", "founder", "reject", evidence_ref=rid),
          judgment("someone-else", "founder", "approve", evidence_ref=rid)]
    r = compile_(js, journal)
    assert r["state"] == "HUMAN_JUDGMENT_RECORDED" and r["result"]["decision"]["verdict"] == "reject"
    assert [j["provenance"] for j in r["human_judgments"]["judgments"]] == [
        f"SIGNED_FOUNDER_ANSWER decision.answered {rid}", "UNVERIFIED_PROVENANCE"]
    assert any("the signed answer stands" in d for d in r["dissent"])


def test_a_signed_answer_cited_by_another_role_lends_it_no_provenance_and_every_judgment_is_labelled():
    journal, rid = answered("reject")
    js = [judgment("expert:a", "domain_expert", "reject", evidence_ref=rid),
          judgment("expert:z", "domain_expert", "approve")]
    r = compile_(js, journal)
    assert [j["provenance"] for j in r["human_judgments"]["judgments"]] == ["UNVERIFIED_PROVENANCE"] * 2
    assert r["result"]["decision"]["verdict"] == "reject"                    # decided by the record, not by them


def test_without_a_signed_record_judgments_stay_evidence_and_the_question_is_asked():
    rid, scope = question_ids()
    js = [judgment("founder:alfonso", "founder", "approve", evidence_ref=rid),
          judgment("expert:a", "domain_expert", "approve")]
    r = compile_(js)                                                          # no journal: provenance unprovable
    assert r["state"] == "HUMAN_JUDGMENT_REQUIRED"
    assert {j["provenance"] for j in r["human_judgments"]["judgments"]} == {"UNVERIFIED_PROVENANCE"}
    assert r["result"]["awaiting"] == f"the founder's signed answer to {rid}"
    ask = r["result"]["founder_ask"]
    assert ask["state"] == "PREPARED_NOT_RECORDED" and ask["kind"] == "HUMAN_JUDGMENT"
    assert ask["scope_digest"] == scope and ask["request_id"] == rid


def test_refusal_is_recorded_and_never_overridden():
    journal, rid = answered("reject")
    js = [judgment("participant:c", "affected_participant", "REFUSED", why="I do not consent to be assessed"),
          judgment("founder:alfonso", "founder", "reject", evidence_ref=rid)]
    r = compile_(js, journal)
    assert r["human_judgments"]["refusals"] == [{"participant_ref": "participant:c", "role": "affected_participant",
                                                 "rationale": "I do not consent to be assessed"}]
    assert any("REFUSED" in d for d in r["dissent"])


def test_on_the_body_the_question_is_asked_once_and_the_founders_signed_answer_decides_it(tmp_path):
    """End to end: compile records the ask through greg.asks, Alfonso answers with a signed DECISION, and the
    same question then returns his verdict; a different question stays open."""
    home, key, body_id, _ = make_body(tmp_path)
    with Body(home) as b:
        first = compile_(None, b.journal)
        again = compile_(None, b.journal)
        requested = [e.payload for e in b.journal.replay("decision.requested")]
    rid = first["result"]["request_id"]
    assert first["state"] == "HUMAN_JUDGMENT_REQUIRED" and first["result"]["founder_ask"]["state"] == "RECORDED"
    assert again["result"]["founder_ask"]["state"] == "RECORDED"
    assert [r["request_id"] for r in requested] == [rid]                      # asked once, not once per compile
    assert requested[0]["kind"] == "HUMAN_JUDGMENT" and requested[0]["scope_digest"] == first["result"]["scope_digest"]
    drop(home, signed(key, body_id, "DECISION", {"request_id": rid, "answer": "approve"}))
    with Body(home) as b:
        b.tick()
        decided = compile_(None, b.journal)
        other = compile_(None, b.journal, data={"question": "may the claims policy exclude every filer?"})
    assert decided["state"] == "HUMAN_JUDGMENT_RECORDED"
    assert decided["result"]["decision"]["verdict"] == "approve"
    assert decided["result"]["decision"]["decided_by"] == f"signed decision.answered {rid}"
    assert other["state"] == "HUMAN_JUDGMENT_REQUIRED"


@pytest.mark.parametrize("bad", [
    [judgment("x", "majority", "approve")],                                     # not a recognised role
    [judgment("x", "domain_expert", "probably")],                               # not a verdict
    [{**judgment("x", "domain_expert", "approve"), "weight": 3}],               # no weighting fields
    [{k: v for k, v in judgment("x", "domain_expert", "approve").items() if k != "rationale"}],
    [],
])
def test_malformed_judgments_are_refused(bad):
    with pytest.raises(CognitionError):
        human.validate(bad)
