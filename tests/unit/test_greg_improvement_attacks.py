"""One improvement substrate under attack: evidence-acquisition learning, typed claims, protected state,
regression closure, expiry, and learning that survives the death of the process.

Pass 1 attacks (false learning): learn from its own training case; take a founder factual claim as
truth; retain on a tie; retain after fewer than three held-out cases; buy an improvement with extra
calls; write protected state; close the wrong regression; lose learning on restart; re-activate
reverted learning on restart. Every attack below must fail.

The founder key is a real Ed25519 test key, not Alfonso's. GitHub is an in-process fixture.
"""
from datetime import datetime, timedelta, timezone
import os
import urllib.parse

import pytest

from greg import briefs, improvement, tribunal
from greg.body import Body, Layout
from greg.templates import engineering_brief
from tests.greg_fixtures import Clock, drop, make_body, signed
from tests.unit.test_greg_briefs import _brief_mission, _open_request, _run, github, repo  # noqa: F401 (fixtures)
from tests.unit.test_greg_learning_gate import DRAFT, Morning

NOW = datetime.now(timezone.utc)


def _stamp(days):
    return (NOW - timedelta(days=days)).isoformat().replace("+00:00", "Z")


def big_repo(*, ready_failing=True, draft_heads=10):
    """Ten drafts first (they use the whole check budget in API order), then one ready pull request #99."""
    pulls = [{"number": n, "title": f"draft {n}", "draft": True, "user": {"login": "agent"},
              "created_at": _stamp(3), "updated_at": _stamp(1), "head": {"sha": f"{n:040d}"} if n <= draft_heads else {},
              "base": {"ref": "main"}} for n in range(1, 11)]
    pulls.append({"number": 99, "title": "ready fix", "draft": False, "user": {"login": "alfonso"},
                  "created_at": _stamp(2), "updated_at": _stamp(1), "head": {"sha": "9" * 40}, "base": {"ref": "main"}})
    checks = {f"{n:040d}": [("tests", "completed", "success")] for n in range(1, 11)}
    checks["9" * 40] = [("tests", "completed", "failure" if ready_failing else "success")]
    calls = []

    def fetch(url, token):
        calls.append(url)
        parts = urllib.parse.urlsplit(url).path.strip("/").split("/")
        if parts[3] == "pulls":
            return 200, pulls
        runs = [{"name": n, "status": s, "conclusion": c} for n, s, c in checks[parts[4]]]
        return 200, {"total_count": len(runs), "check_runs": runs}
    return fetch, calls


class Evidence(Morning):
    """Morning, over the acme/big repository: a daily brief whose check budget drafts can exhaust."""

    def __init__(self, tmp_path, repo_path):
        self.home, self.key, self.body_id, _ = make_body(tmp_path)
        spec = engineering_brief(local={"kernel": str(repo_path)}, github=["acme/big"], daily=True)
        drop(self.home, signed(self.key, self.body_id, "MISSION", spec))
        self.clock = Clock()
        self.body = Body(self.home, clock=self.clock).open()
        self.body.boot()
        _run(self.body, self.clock)
        request = _open_request(self.body)
        drop(self.home, signed(self.key, self.body_id, "DECISION",
                               {"request_id": request["request_id"], "answer": "approve"}))
        self.day = 0

    def claim(self, action, refs, *, regression=None):
        body = {"target_event_id": action.event_id, "verdict": "reject", "evidence_type": "objective_failure",
                "text": "the brief missed a failing pull request", "failure_claim": {"missed_failing": refs}}
        if regression:
            body["regression"] = regression
        drop(self.home, signed(self.key, self.body_id, "CRITIQUE", body, now=self.clock.now))
        self.body.tick()


def restart(m):
    """Destroy the Body completely and build a fresh one from the same durable home."""
    m.body.close()
    m.body = None
    m.body = Body(m.home, clock=m.clock).open()
    m.body.boot()


def sign(m, target_event_id, **fields):
    body = {"target_event_id": target_event_id, "verdict": "note", "evidence_type": "founder_judgment",
            "text": "morning review", **fields}
    drop(m.home, signed(m.key, m.body_id, "CRITIQUE", body, now=m.clock.now))
    m.body.tick()


# -- evidence acquisition: independent verification, no bought results ---------------------------------

def test_a_verified_failure_claim_teaches_ready_first_checks_and_it_survives_process_death(tmp_path, repo,
                                                                                          monkeypatch):
    fetch, calls = big_repo()
    monkeypatch.setattr(briefs, "FETCH", fetch)
    m = Evidence(tmp_path, repo)
    action, output = m.brief()
    assert output["inputs"]["github"]["repos"]["acme/big"]["pulls"][-1]["checks"] is None   # #99 never read
    m.claim(action, ["acme/big#99"], regression="the brief hid a failing ready pull request")
    proposed = [p for p in m.events("improvement.proposed") if p["lever"] == "brief.acquisition"]
    assert len(proposed) == 1 and proposed[0]["policy"] == {"check_fetch_order": "ready_first"}
    assert proposed[0]["evidence_basis"].startswith("founder_reported_failure")
    critique = m.events("critique.recorded")[-1]
    assert critique["epistemic"] == {"failure_claim": "founder_reported_failure", "is_truth": False}
    for _ in range(3):
        action, output = m.brief()
        assert "check_order" not in output["inputs"]["github"]                 # production is unchanged in SHADOW
        assert output["shadow"]["truth_complete"] and output["shadow"]["truth"]["acme/big#99"]["failing"]
    retained = [d for d in m.events("improvement.retained") if d["lever"] == "brief.acquisition"]
    # per held-out brief the current policy misses #99's failure and leaves one ready PR unknown (2); ready-first 0
    assert len(retained) == 1 and retained[0]["errors"] == {"current": 6, "candidate": 0}
    assert retained[0]["claim"]["verified"] and retained[0]["extra_call_cases"] == []
    closed = m.events("critique.regression_closed")
    assert len(closed) == 1 and closed[0]["proof"]["claim_independently_verified"] is True
    assert closed[0]["candidate_id"] == retained[0]["candidate_id"] and closed[0]["decision"] == "RETAIN"

    restart(m)                                                                 # the process dies
    action, output = m.brief()
    github_in = output["inputs"]["github"]
    assert github_in["check_order"] == "ready_first"
    assert github_in["repos"]["acme/big"]["pulls"][-1]["checks"]["failing"] == 1
    assert "acme/big#99" in briefs.flagged_keys(output["inputs"])           # the failing PR now reaches Alfonso
    assert github_in["api_calls"] == 11                                        # same ceiling: 1 list + 10 checks
    ok, detail = briefs.verify_delivery(output, Layout(m.home).home / "deliveries")
    assert ok, detail
    report = tribunal.morning_report(m.body.journal)
    assert not report["q11_change"]                                            # the regression reads closed
    m.body.close()


def test_a_founder_failure_claim_that_reality_does_not_reproduce_teaches_nothing(tmp_path, repo, monkeypatch):
    fetch, _ = big_repo(ready_failing=False)          # #99 is actually passing
    monkeypatch.setattr(briefs, "FETCH", fetch)
    m = Evidence(tmp_path, repo)
    action, _ = m.brief()
    m.claim(action, ["acme/big#99"])
    assert [p for p in m.events("improvement.proposed") if p["lever"] == "brief.acquisition"]
    for _ in range(3):
        m.brief()
    rejected = [d for d in m.events("improvement.rejected") if d["lever"] == "brief.acquisition"]
    assert len(rejected) == 1 and "not independently reproduced" in " ".join(rejected[0]["why"])
    assert {c["status"] for c in m.events("improvement.claim_checked")} == {"not_reproduced"}
    assert improvement.active_policy(m.body.journal, "brief.acquisition") == briefs.ACQUISITION_BASELINE
    m.body.close()


def test_completeness_bought_with_extra_calls_is_rejected(tmp_path, repo, monkeypatch):
    # drafts 1-5 have heads, 6-10 do not: API order spends 5 check calls on drafts and never reads #99;
    # ready-first reads #99 AND drafts 1-5 (9 slots left), i.e. one more call than the current policy.
    fetch, _ = big_repo(draft_heads=5)
    monkeypatch.setattr(briefs, "FETCH", fetch)
    m = Evidence(tmp_path, repo)
    action, output = m.brief()
    assert output["inputs"]["github"]["api_calls"] == 6
    m.claim(action, ["acme/big#99"])
    assert [p for p in m.events("improvement.proposed") if p["lever"] == "brief.acquisition"]
    for _ in range(3):
        m.brief()
    rejected = [d for d in m.events("improvement.rejected") if d["lever"] == "brief.acquisition"]
    assert len(rejected) == 1
    assert rejected[0]["errors"]["candidate"] < rejected[0]["errors"]["current"]    # it WAS more complete ...
    assert len(rejected[0]["extra_call_cases"]) == 3 and rejected[0]["claim"]["verified"]
    assert rejected[0]["why"] == ["used more calls than the current policy on 3 case(s): an improvement bought "
                                  "with calls does not count"]                    # ... and lost only on the guard
    assert improvement.active_policy(m.body.journal, "brief.acquisition") == briefs.ACQUISITION_BASELINE
    m.body.close()


# -- preference lever: no leakage, no ties, no premature retention --------------------------------------

def test_relabelling_the_training_brief_is_never_held_out_evidence(tmp_path, repo, github):
    m = Morning(tmp_path, repo)
    origin, _ = m.brief()
    m.label(origin, noise=[DRAFT])
    for _ in range(5):                                # the same brief, labelled again and again
        m.label(origin, noise=[DRAFT])
    assert not m.events("improvement.evaluated") and not m.events("improvement.retained")
    m.body.close()


def test_two_held_out_briefs_are_not_enough(tmp_path, repo, github):
    m = Morning(tmp_path, repo)
    action, _ = m.brief()
    m.label(action, noise=[DRAFT])
    for _ in range(2):
        action, _ = m.brief()
        m.label(action, noise=[DRAFT])
    assert not m.events("improvement.retained") and not m.events("improvement.rejected")   # 2 < 3
    action, _ = m.brief()
    m.label(action, noise=[DRAFT])
    assert len(m.events("improvement.retained")) == 1                                    # the third decides
    m.body.close()


def test_a_candidate_that_loses_on_held_out_briefs_is_rejected(tmp_path, repo, github):
    m = Morning(tmp_path, repo)
    action, _ = m.brief()
    m.label(action, noise=[DRAFT])                      # candidate: stop flagging idle drafts
    for labels in ({"noise": [DRAFT]},                  # current 1, candidate 0
                   {},                                  # current 0, candidate 1 (the founder wanted the draft)
                   {"missed": ["acme/organ#2"]}):       # current 1, candidate 2
        action, _ = m.brief()
        m.label(action, **labels)
    rejected = m.events("improvement.rejected")
    assert len(rejected) == 1 and not m.events("improvement.retained")
    assert rejected[0]["errors"]["candidate"] >= rejected[0]["errors"]["current"]
    m.body.close()


def test_equal_errors_is_a_rejection_not_a_retention():
    # With a one-key lever and three held-out briefs each brief moves the totals by one, so the fixture
    # cannot produce an exact tie; the one decision rule is tested directly instead.
    assert improvement.verdict(2, 2) == "rejected"
    assert improvement.verdict(2, 3) == "rejected"
    assert improvement.verdict(2, 1) == "retained"


def test_a_candidate_without_enough_evidence_expires_as_no_improvement(tmp_path, repo, github):
    m = Morning(tmp_path, repo)
    action, _ = m.brief()
    m.label(action, noise=[DRAFT])
    assert m.events("improvement.proposed")
    m.clock.advance(improvement.MAX_PENDING_DAYS * 86400 + 60)
    m.body.tick()
    expired = m.events("improvement.expired")
    assert len(expired) == 1 and expired[0]["decision"] == "NO_IMPROVEMENT"
    assert improvement.active_policy(m.body.journal) == briefs.ATTENTION_BASELINE
    assert len(m.events("improvement.proposed")) == 1          # not immediately re-proposed without new evidence
    m.body.tick()
    assert len(m.events("improvement.expired")) == 1
    m.body.close()


# -- protected state -----------------------------------------------------------------------------------

PROTECTED_FIELDS = ["authority", "founder_identity", "shutdown", "credentials", "budget_usd", "scope", "targets",
                    "consequence_class", "permissions", "grants", "kernel_policy", "light_cone", "approval_scope"]


@pytest.mark.parametrize("lever", sorted(improvement.LEVERS))
@pytest.mark.parametrize("field", PROTECTED_FIELDS)
def test_no_protected_field_can_become_a_learned_policy(lever, field):
    baseline = dict(improvement.LEVERS[lever]["baseline"])
    with pytest.raises(improvement.ImprovementError):
        improvement.validate_policy({**baseline, field: "anything"}, lever)
    assert improvement.protected(field)


def test_a_forged_ledger_record_with_protected_state_is_never_executed(tmp_path, repo, github):
    m = Morning(tmp_path, repo)
    m.brief()
    forged = {**briefs.ATTENTION_BASELINE, "idle_includes_drafts": False, "budget_usd": 1_000_000,
              "consequence_class": "irreversible"}
    m.body.journal.record("improvement.retained", {"candidate_id": "impr-forged", "lever": "brief.attention",
                                                  "policy": forged, "replaces": briefs.ATTENTION_BASELINE,
                                                  "decided_after_seq": 0}, key="forged")
    assert improvement.active_policy(m.body.journal) == briefs.ATTENTION_BASELINE
    assert "brief.attention" not in improvement.learned(m.body.journal)
    _, output = m.brief()
    assert "attention_policy" not in output["inputs"]
    m.body.close()


# -- regression obligations close only through their own proven condition ----------------------------------

def test_a_regression_closes_only_through_its_own_proven_condition_and_reopens_on_reversion(tmp_path, repo, github):
    m = Morning(tmp_path, repo)
    action, _ = m.brief()
    sign(m, action.event_id, attention={"missed": [], "noise": [DRAFT]},
         regression="the brief keeps flagging stale drafts")
    unrelated_brief = action
    for _ in range(3):
        action, _ = m.brief()
        m.label(action, noise=[DRAFT])
    retained = m.events("improvement.retained")
    closed = m.events("critique.regression_closed")
    assert retained and len(closed) == 1
    c = closed[0]
    assert c["candidate_id"] == retained[0]["candidate_id"] and c["decision"] == "RETAIN"
    assert c["proof"]["origin_errors_under_retained_policy"] == 0 and c["held_out"] == retained[0]["held_out"]
    assert c["close_condition"] == improvement.attention_close_condition()
    assert not tribunal.morning_report(m.body.journal)["q11_change"]

    # the founder signs a rejection of the retained change: reverted, and the regression reopens
    retained_event = [e for e in m.body.journal.replay("improvement.retained")][0]
    drop(m.home, signed(m.key, m.body_id, "CRITIQUE", {
        "target_event_id": retained_event.event_id, "verdict": "reject", "evidence_type": "founder_judgment",
        "text": "I want to see drafts again"}, now=m.clock.now))
    m.body.tick()
    assert m.events("improvement.reverted")[0]["by"] == "founder"
    assert m.events("critique.regression_reopened")
    assert tribunal.morning_report(m.body.journal)["q11_change"]              # open again
    m.body.close()


def test_a_regression_the_retained_change_does_not_fix_stays_open(tmp_path, repo, github):
    m = Morning(tmp_path, repo)
    action, _ = m.brief()
    # criticized behavior: a pull request the attention lever cannot flag at all
    sign(m, action.event_id, attention={"missed": ["acme/organ#2"], "noise": [DRAFT]},
         regression="the healthy change should have been surfaced")
    for _ in range(3):
        action, _ = m.brief()
        m.label(action, noise=[DRAFT])
    assert m.events("improvement.retained")                                   # a real gain was kept ...
    assert not m.events("critique.regression_closed")                         # ... but it does not fix THIS
    assert tribunal.morning_report(m.body.journal)["q11_change"]
    m.body.close()


def test_a_rejected_candidate_closes_no_regression(tmp_path, repo, github):
    m = Morning(tmp_path, repo)
    action, _ = m.brief()
    sign(m, action.event_id, attention={"missed": [], "noise": [DRAFT]}, regression="drafts are noise")
    for _ in range(3):
        action, _ = m.brief()
        m.label(action)
    assert m.events("improvement.rejected") and not m.events("critique.regression_closed")
    m.body.close()


# -- learning lives in durable state, not in process memory ----------------------------------------------

def test_retained_learning_survives_death_and_reverted_learning_stays_reverted(tmp_path, repo, github):
    m = Morning(tmp_path, repo)
    for _ in range(4):
        action, _ = m.brief()
        m.label(action, noise=[DRAFT])
    assert m.events("improvement.retained")

    restart(m)                                                                 # death 1
    action, output = m.brief()
    assert output["inputs"]["attention_policy"]["idle_includes_drafts"] is False
    assert DRAFT not in briefs.flagged_keys(output["inputs"])

    retained_event = [e for e in m.body.journal.replay("improvement.retained")][0]
    drop(m.home, signed(m.key, m.body_id, "CRITIQUE", {
        "target_event_id": retained_event.event_id, "verdict": "reject", "evidence_type": "founder_judgment",
        "text": "revert this"}, now=m.clock.now))
    m.body.tick()
    assert m.events("improvement.reverted")

    restart(m)                                                                 # death 2
    _, output = m.brief()
    assert "attention_policy" not in output["inputs"] and DRAFT in briefs.flagged_keys(output["inputs"])
    restart(m)                                                                 # death 3: still reverted
    assert improvement.active_policy(m.body.journal) == briefs.ATTENTION_BASELINE
    assert len(m.events("improvement.proposed")) == 1                         # and not silently re-proposed
    m.body.close()


# -- one engine ----------------------------------------------------------------------------------------

def test_there_is_one_learning_engine():
    import importlib.util
    assert importlib.util.find_spec("greg.learning") is None                  # #119's parallel engine is absent
    assert set(improvement.LEVERS) == {"brief.attention", "brief.acquisition"}
    assert {spec["kind"] for spec in improvement.LEVERS.values()} == {"preference", "evidence"}
