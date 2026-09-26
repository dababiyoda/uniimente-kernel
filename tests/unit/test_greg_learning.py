"""Founder correction -> verified improvement -> retention or rejection, through the real body.

Five mornings of the real ``brief.engineering`` capability (GitHub replaced by a per-day fixture
world modelled on the live brief of 2026-09-26; local Git is a real repository). Reviews are
signed with a per-test key through the real CRITIQUE path; they are not Alfonso's.

Closure 1 (a PREFERENCE, judged by the founder's labels of a LATER brief):
    day A: drafts crowd the attention list -> founder labels what needed him -> candidate
           draft_attention=after_ready, fitted on A only, frozen
    day B: a different world; labels given after the freeze -> baseline vs candidate re-rendered
           from B's receipted inputs -> RETAIN -> policy v1
Closure 2 (a FAILURE_CLAIM, judged by independent observation; baseline = policy v1):
    day C: a failing ready PR was never checked (drafts used the budget) -> founder claims the miss
           -> diagnosis on C -> candidate check_fetch_order=ready_first, frozen
    day D: production gathers with v1; the candidate gathers in shadow inside the same approved
           action; every ready PR is observed exhaustively as truth -> RETAIN -> policy v2
    day E: GREG itself now fetches ready PRs first and flags the failure it used to miss.
"""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import urllib.parse

import pytest

from greg import briefs, learning
from greg.body import Body, Layout
from greg.templates import engineering_brief
from tests.greg_fixtures import Clock, drop, make_body, signed
from tests.unit.test_greg_briefs import git


def pull(number, *, draft, idle_days, sha, now):
    stamp = (now - timedelta(days=idle_days)).isoformat().replace("+00:00", "Z")
    return {"number": number, "title": f"change {number}", "draft": draft, "user": {"login": "agent"},
            "created_at": stamp, "updated_at": stamp, "head": {"sha": sha}, "base": {"ref": "main"}}


def world(day: str, now: datetime):
    """(pulls per repo in API order, newest first; check runs per head sha) for one morning."""
    fail, ok = [("build", "completed", "failure")], [("build", "completed", "success")]
    if day == "A":
        pulls = {"acme/kernel": [pull(7, draft=False, idle_days=16, sha="k7", now=now),
                                 pull(6, draft=True, idle_days=25, sha="k6", now=now),
                                 pull(5, draft=True, idle_days=30, sha="k5", now=now)],
                 "acme/organ": [pull(9, draft=True, idle_days=40, sha="o9", now=now),
                                pull(8, draft=True, idle_days=41, sha="o8", now=now),
                                pull(2, draft=False, idle_days=20, sha="o2", now=now)]}
        checks = {s: ok for s in ("k7", "k6", "k5", "o9", "o8", "o2")}
    elif day == "B":
        pulls = {"acme/kernel": [pull(11, draft=False, idle_days=1, sha="k11", now=now),
                                 pull(12, draft=True, idle_days=18, sha="k12", now=now),
                                 pull(7, draft=False, idle_days=17, sha="k7", now=now),
                                 pull(6, draft=True, idle_days=26, sha="k6", now=now)],
                 "acme/organ": [pull(21, draft=True, idle_days=15, sha="o21", now=now),
                                pull(20, draft=True, idle_days=16, sha="o20", now=now),
                                pull(22, draft=False, idle_days=21, sha="o22", now=now)]}
        checks = {**{s: ok for s in ("k12", "k7", "k6", "o21", "o20", "o22")}, "k11": fail}
    elif day in ("C", "D", "E"):
        drafts = [pull(100 + n, draft=True, idle_days=2, sha=f"d{n}", now=now) for n in range(11)]
        ready = {"C": [pull(30, draft=False, idle_days=3, sha="r30", now=now),
                       pull(31, draft=False, idle_days=2, sha="r31", now=now)],
                 "D": [pull(40, draft=False, idle_days=1, sha="r40", now=now),
                       pull(41, draft=False, idle_days=1, sha="r41", now=now),
                       pull(30, draft=False, idle_days=4, sha="r30", now=now)],
                 "E": [pull(50, draft=False, idle_days=1, sha="r50", now=now),
                       pull(40, draft=False, idle_days=2, sha="r40", now=now)]}[day]
        pulls = {"acme/kernel": [pull(7, draft=False, idle_days=1, sha="k7", now=now)],
                 "acme/organ": drafts + ready}
        checks = {**{f"d{n}": ok for n in range(11)}, "k7": ok, "r30": fail, "r31": ok, "r40": fail,
                  "r41": ok, "r50": fail}
    return pulls, checks


class GitHub:
    def __init__(self):
        self.day, self.now, self.calls = "A", None, []

    def __call__(self, url, token):
        self.calls.append(url)
        pulls, checks = world(self.day, self.now)
        parts = urllib.parse.urlsplit(url).path.strip("/").split("/")
        if parts[3] == "pulls":
            return 200, pulls.get("/".join(parts[1:3]), [])
        runs = [{"name": n, "status": s, "conclusion": c} for n, s, c in checks[parts[4]]]
        return 200, {"total_count": len(runs), "check_runs": runs}


@pytest.fixture
def setup(tmp_path, monkeypatch):
    home, key, body_id, data = make_body(tmp_path)
    repo = data / "kernel"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main"); (repo / "a").write_text("a"); git(repo, "add", "a")
    git(repo, "commit", "-q", "-m", "first")
    clock = Clock()
    gh = GitHub()
    monkeypatch.setattr(briefs, "FETCH", gh)
    monkeypatch.setattr(briefs, "NOW", lambda: clock.now)
    spec = engineering_brief(local={"kernel": str(repo)}, github=["acme/kernel", "acme/organ"], daily=True,
                             preauthorize_delivery=True)
    drop(home, signed(key, body_id, "MISSION", spec))
    body = Body(home, clock=clock).open()
    body.boot()
    return {"home": home, "key": key, "body_id": body_id, "body": body, "clock": clock, "gh": gh}


def morning(s, day: str) -> dict:
    """Advance to the next morning; the daily mission delivers exactly one brief. Returns its action."""
    body, clock, gh = s["body"], s["clock"], s["gh"]
    if day != "A":
        clock.advance(21 * 3600)
    gh.day, gh.now = day, clock.now
    before = {e.event_id for e in body.journal.replay("mission.action")}
    for _ in range(3):
        clock.advance(30)
        body.tick()
        _age_all(s)   # brief.freshness reads file mtime: stamp deliveries with the body clock
    new = [e for e in body.journal.replay("mission.action") if e.event_id not in before
           and e.payload["status"] == "DONE" and e.payload["capability"] == "brief.engineering"]
    assert len(new) == 1, [e.payload["status"] for e in body.journal.replay("mission.action")]
    _age_all(s)
    return {"event_id": new[0].event_id, **new[0].payload, "output": body._receipt_output(new[0].payload["receipt"])}


def _age_all(s):
    """Stamp every delivered brief with the body clock so the next morning sees it as 21 hours old."""
    folder = Layout(s["home"]).home / "deliveries" / "briefs"
    stamp = s["clock"].now.timestamp()
    for path in folder.glob("*.md"):
        os.utime(path, (stamp, stamp))


def review(s, action: dict, classification: str, **review_fields) -> dict:
    body = {"target_event_id": action["event_id"], "verdict": "note", "evidence_type": "founder_judgment",
            "text": f"test-key review ({classification})", "review": {"classification": classification,
                                                                      **review_fields}}
    return apply(s, body)


def apply(s, body):
    """Sign at the body's clock (the fixture world runs days ahead of wall time) and apply one CRITIQUE."""
    drop(s["home"], signed(s["key"], s["body_id"], "CRITIQUE", body, now=s["clock"].now))
    s["clock"].advance(5)
    s["body"].ingest_inbox()
    assert not events(s, "command.rejected"), events(s, "command.rejected")
    accepted = [e.payload for e in s["body"].journal.replay("command.accepted")][-1]
    assert accepted["body"] == body
    return accepted["result"]


def events(s, kind):
    return [e.payload for e in s["body"].journal.replay(kind)]


def test_two_orthogonal_closures_accumulate_competence_and_change_future_briefs(setup):
    s = setup
    # -- closure 1: preference ------------------------------------------------------------------
    a = morning(s, "A")
    assert "policy" in a["output"]["inputs"] and a["output"]["inputs"]["policy"]["version"] == 0
    result = review(s, a, "PREFERENCE", labels={"needs_decision": ["acme/kernel#7", "acme/organ#2"]})
    cand1 = result["learning"]["candidate"]
    assert cand1["change"] == {"draft_attention": "after_ready"} and cand1["baseline"]["version"] == 0
    assert cand1["fit_on_origin"]["baseline"]["noise_before_last_needed"] > \
        cand1["fit_on_origin"]["candidate"]["noise_before_last_needed"]
    review(s, a, "PREFERENCE", labels={"needs_decision": ["acme/kernel#7"]})     # origin again: not a test
    assert not events(s, "learning.evaluated")

    b = morning(s, "B")
    assert b["output"]["inputs"]["policy"] == {"version": 0, "draft_attention": "inline",
                                               "check_fetch_order": "api_order"}   # unchanged until earned
    review(s, b, "PREFERENCE", labels={"needs_decision": ["acme/kernel#11", "acme/kernel#7", "acme/organ#22"]})
    evaluated = events(s, "learning.evaluated")[0]
    assert evaluated["decision"] == "RETAIN" and evaluated["case"]["receipt"] == b["receipt"]
    assert evaluated["candidate"]["noise_before_last_needed"] < evaluated["baseline"]["noise_before_last_needed"]
    assert evaluated["candidate"]["missed_obligations"] == evaluated["baseline"]["missed_obligations"] == 0
    retained1 = events(s, "learning.retained")[0]
    assert retained1["version"] == 1 and retained1["rollback_to"] == 0 and retained1["authority_change"] is False

    # -- closure 2: failure claim, compared against the system that already contains retain 1 ----
    c = morning(s, "C")
    assert c["output"]["inputs"]["policy"]["draft_attention"] == "after_ready"   # future behavior changed
    assert "learned policy v1" in Path(c["output"]["path"]).read_text()
    b_now = {**b["output"]["inputs"], "policy": c["output"]["inputs"]["policy"]}   # day B's world under v1
    assert "ready-for-review pull request" in briefs.render(b_now)
    assert briefs.render(b_now) != Path(b["output"]["path"]).read_text()
    assert briefs.verify_delivery(c["output"], Layout(s["home"]).home / "deliveries")[0]   # appraiser still binds
    organ = c["output"]["inputs"]["github"]["repos"]["acme/organ"]["pulls"]
    assert next(p for p in organ if p["number"] == 30)["checks"] is None           # the real miss
    result = review(s, c, "FAILURE_CLAIM", claimed_missed=["acme/organ#30"])
    cand2 = result["learning"]["candidate"]
    assert cand2["change"] == {"check_fetch_order": "ready_first"} and cand2["baseline"]["version"] == 1
    assert cand2["fit_on_origin"]["diagnosis"]["explains"] is True

    d = morning(s, "D")
    assert d["output"]["inputs"]["github"].get("check_order") is None             # production: unchanged v1
    assert cand2["candidate_id"] in d["output"]["shadow"]["candidates"]
    decided = [x for x in events(s, "learning.decided") if x["candidate_id"] == cand2["candidate_id"]][0]
    assert decided["decision"] == "RETAIN", decided
    evaluation = [x for x in events(s, "learning.evaluated") if x["candidate_id"] == cand2["candidate_id"]][0]
    assert evaluation["baseline"]["missed_failing_ready"] == 2 and evaluation["candidate"]["missed_failing_ready"] == 0
    assert evaluation["candidate"]["api_calls"] <= evaluation["baseline"]["api_calls"]   # no bought results
    claim = events(s, "learning.claim_checked")[0]
    assert claim["ref"] == "acme/organ#30" and claim["status"] == "independently_verified_failure"

    e = morning(s, "E")
    policy = e["output"]["inputs"]["policy"]
    assert policy == {"version": 2, "draft_attention": "after_ready", "check_fetch_order": "ready_first"}
    flagged = [i["ref"] for i in briefs.attention(e["output"]["inputs"]) if "checks failing" in i["why"]]
    assert {"acme/organ#50", "acme/organ#40"} <= set(flagged)                      # what v0 would have missed
    v0 = briefs.gather_github(["acme/organ"], token=None)                         # the old behavior, same world
    assert not any(p["checks"] and p["checks"]["failing"] for p in v0["repos"]["acme/organ"]["pulls"])
    assert briefs.verify_delivery(e["output"], Layout(s["home"]).home / "deliveries")[0]

    report = learning.summary(s["body"].journal)
    assert report["policies"]["brief.engineering"]["version"] == 2 and not report["pending"]
    if os.environ.get("GREG_RECORD_EVIDENCE"):
        out = Path(__file__).resolve().parents[1] / "evidence" / "greg-product"
        out.mkdir(parents=True, exist_ok=True)
        (out / "learning-closures.json").write_text(json.dumps({
            "reality": "TESTED: real Body, real CRITIQUE path, real brief.engineering capability and appraiser "
                       "byte-compare; GitHub replaced by per-day fixture worlds modelled on the live 2026-09-26 "
                       "brief; reviews signed with a per-test key (not Alfonso)",
            "reviews": events(s, "learning.review"), "candidates": events(s, "learning.candidate"),
            "evaluations": events(s, "learning.evaluated"), "decisions": events(s, "learning.decided"),
            "retained": events(s, "learning.retained"), "claims": events(s, "learning.claim_checked"),
            "policy_after": report["policies"]}, indent=1, default=str))
    s["body"].close()


def test_a_worse_candidate_is_rejected_and_nothing_changes(setup):
    s = setup
    a = morning(s, "A")
    review(s, a, "CORRECT", correction={"knob": "draft_attention", "value": "after_ready"})
    b = morning(s, "B")
    # On day B the founder's own labels say the DRAFTS needed him: the candidate buries them.
    review(s, b, "PREFERENCE", labels={"needs_decision": ["acme/kernel#12", "acme/organ#21", "acme/organ#20"]})
    decided = events(s, "learning.decided")[0]
    assert decided["decision"] in ("REGRESS", "CONFLICTED") and decided["applied"] is False
    assert not events(s, "learning.retained")
    c = morning(s, "C")
    assert c["output"]["inputs"]["policy"]["draft_attention"] == "inline"          # behavior did not change
    assert events(s, "learning.evaluated")[0]["baseline"] != events(s, "learning.evaluated")[0]["candidate"]
    s["body"].close()


def test_learning_cannot_touch_constitutional_state(setup):
    s = setup
    a = morning(s, "A")
    for knob in ("budget_usd", "max_consequence_class", "founder_key", "light_cone.targets", "shutdown"):
        result = review(s, a, "CORRECT", correction={"knob": knob, "value": "anything"})
        assert result["learning"]["decision"] == "NEEDS_FOUNDER_DECISION"
    assert not events(s, "learning.candidate") and not events(s, "learning.retained")
    assert all(d["applied"] is False for d in events(s, "learning.decided"))
    s["body"].close()


def test_a_retained_improvement_is_reverted_by_a_signed_rejection(setup):
    s = setup
    a = morning(s, "A")
    review(s, a, "PREFERENCE", labels={"needs_decision": ["acme/kernel#7", "acme/organ#2"]})
    b = morning(s, "B")
    review(s, b, "PREFERENCE", labels={"needs_decision": ["acme/kernel#11", "acme/kernel#7", "acme/organ#22"]})
    retained = next(e for e in s["body"].journal.replay("learning.retained"))
    apply(s, {"target_event_id": retained.event_id, "verdict": "reject", "evidence_type": "founder_judgment",
              "text": "I want drafts inline again"})
    assert learning.policy(s["body"].journal, "brief.engineering")["version"] == 0
    c = morning(s, "C")
    assert c["output"]["inputs"]["policy"]["draft_attention"] == "inline"
    assert events(s, "learning.retained") and events(s, "learning.reverted")        # history kept
    s["body"].close()


def test_a_claim_the_retained_evidence_contradicts_yields_no_candidate(setup):
    s = setup
    a = morning(s, "A")
    result = review(s, a, "FAILURE_CLAIM", claimed_missed=["acme/kernel#7"])     # its checks were fetched: passing
    assert result["learning"]["candidate"]["candidate"] is None
    no = events(s, "learning.no_candidate")[0]
    assert "does not show" in no["why"] and "nothing was applied" in no["residual"]
    s["body"].close()


def test_one_change_under_test_at_a_time_and_untested_candidates_expire(setup):
    s = setup
    a = morning(s, "A")
    review(s, a, "PREFERENCE", labels={"needs_decision": ["acme/kernel#7", "acme/organ#2"]})
    second = review(s, a, "FAILURE_CLAIM", claimed_missed=["acme/organ#2"])   # arrives while cand 1 is tested
    assert second["learning"]["candidate"]["candidate"] is None
    assert "still under held-out test" in events(s, "learning.no_candidate")[-1]["why"]
    s["clock"].advance(learning.MAX_PENDING_DAYS * 86400)
    s["body"].tick()
    decided = events(s, "learning.decided")[-1]
    assert decided["decision"] == "NO_IMPROVEMENT" and "no eligible held-out case" in decided["detail"]["why"]
    assert learning.policy(s["body"].journal, "brief.engineering")["version"] == 0
    s["body"].close()


def test_decisions_resist_gaming_and_bought_results():
    base = {"missed_obligations": 0, "noise_before_last_needed": 6, "top_item_needed": 1, "needed_in_top3": 1.0}
    hides_everything = {**base, "noise_before_last_needed": 0, "missed_obligations": 2}
    assert learning.decide(base, hides_everything)[0] == "CONFLICTED"          # less noise by hiding: not retained
    bought = ({"missed_failing_ready": 2, "unknown_ready_checks": 3, "false_failing": 0, "api_calls": 13},
              {"missed_failing_ready": 0, "unknown_ready_checks": 0, "false_failing": 0, "api_calls": 40})
    assert learning.decide(*bought)[0] == "CONFLICTED"                        # better only by spending more calls
    assert learning.decide(base, dict(base))[0] == "NO_IMPROVEMENT"            # no difference: add no complexity
    costlier = ({"api_calls": 13, "missed_failing_ready": 0}, {"api_calls": 14, "missed_failing_ready": 0})
    assert learning.decide(*costlier)[0] == "REGRESS"
    for surface in ("light_cone", "grant", "credential_scope", "Kernel policy", "stop_file"):
        assert learning.protected_surface(surface)
    assert not any(learning.protected_surface(k) for k in learning.LEARNABLE["brief.engineering"])
