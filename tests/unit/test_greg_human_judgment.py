"""Human judgment returns as typed evidence; only the founder's signed answer decides (directive sections 4, 9)."""
from types import SimpleNamespace

import pytest

from greg.cognition import human
from greg.cognition.contracts import CognitionError
from greg.cognition.cortex import reason, registry_view


class Journal:
    def __init__(self, answers):
        self.events = [SimpleNamespace(type="greg.decision.answered", payload=p) for p in answers]

    def replay(self, prefix=""):
        return [e for e in self.events if e.type.startswith("greg." + prefix)]


def judgment(ref, role, verdict, evidence_ref=None, **kw):
    return {"participant_ref": ref, "role": role, "competence_domain": kw.get("domain", "claims policy"),
            "conflicts": kw.get("conflicts", []), "verdict": verdict, "rationale": kw.get("why", f"{ref} reasons"),
            **({"evidence_ref": evidence_ref} if evidence_ref else {})}


def compile_(judgments, journal=None):
    body = {"geometry": {"geometry": "normative", "human_judgment_required": True},
            "data": {"question": "may the claims policy exclude late filers?"},
            "human": {"roles": ["founder", "domain_expert", "affected_participant"], "judgments": judgments}}
    return reason({"problem_id": "h", "compile": body}, registry=registry_view(), journal=journal)


SIGNED = [{"request_id": "req-1", "answer": "reject", "command_digest": "sha256:" + "f" * 64}]


def test_a_majority_never_decides_the_founders_signed_answer_does_and_every_view_is_kept():
    js = [judgment("expert:a", "domain_expert", "approve"), judgment("expert:b", "domain_expert", "approve"),
          judgment("participant:c", "affected_participant", "approve"),
          judgment("founder:alfonso", "founder", "reject", evidence_ref="req-1")]
    r = compile_(js, Journal(SIGNED))
    assert r["state"] == "HUMAN_JUDGMENT_RECORDED"
    assert r["result"]["decision"]["verdict"] == "reject"                    # 3 approvals do not outvote it
    assert r["result"]["decision"]["decided_by"] == "signed decision.answered req-1"
    assert sum("approve" in d for d in r["dissent"]) == 3                     # the minority views are preserved
    assert r["human_judgments"]["aggregation"].startswith("none")
    assert r["human_judgments"]["authority_created"] is False


def test_without_a_signed_record_judgments_stay_evidence_and_nothing_is_decided():
    js = [judgment("founder:alfonso", "founder", "approve", evidence_ref="req-1"),
          judgment("expert:a", "domain_expert", "approve")]
    r = compile_(js)                                                          # no journal: provenance unprovable
    assert r["state"] == "HUMAN_JUDGMENT_REQUIRED"
    assert {j["provenance"] for j in r["human_judgments"]["judgments"]} == {"UNVERIFIED_PROVENANCE"}
    assert r["result"]["awaiting"] == "the founder's signed answer"


def test_a_founder_judgment_that_contradicts_the_signed_answer_decides_nothing():
    r = compile_([judgment("founder:alfonso", "founder", "approve", evidence_ref="req-1")], Journal(SIGNED))
    assert r["state"] == "HUMAN_JUDGMENT_REQUIRED"
    assert any("the signed answer says reject" in d for d in r["dissent"])


def test_a_signed_answer_cited_by_another_role_lends_it_no_authority():
    r = compile_([judgment("expert:a", "domain_expert", "reject", evidence_ref="req-1")], Journal(SIGNED))
    assert r["state"] == "HUMAN_JUDGMENT_REQUIRED" and r["human_judgments"]["decision"] is None


def test_refusal_is_recorded_and_never_overridden():
    js = [judgment("participant:c", "affected_participant", "REFUSED", why="I do not consent to be assessed"),
          judgment("founder:alfonso", "founder", "reject", evidence_ref="req-1")]
    r = compile_(js, Journal(SIGNED))
    assert r["human_judgments"]["refusals"] == [{"participant_ref": "participant:c", "role": "affected_participant",
                                                 "rationale": "I do not consent to be assessed"}]
    assert any("REFUSED" in d for d in r["dissent"])


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
