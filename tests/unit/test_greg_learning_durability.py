"""Learning lives in institutional state, not process memory; regressions close only on demonstration.

Each "life" of the body runs in a forked process that is killed with SIGKILL (no close, no flush,
no cleanup). The next life builds a new Body from the GREG home alone. Reviews are signed with a
per-test key (not Alfonso's); GitHub is the per-day fixture world of test_greg_learning.
"""
from datetime import datetime
import json
import multiprocessing
import os
from pathlib import Path
import signal

from greg import briefs, learning, tribunal
from greg.body import Body, Layout
from greg.templates import engineering_brief
from tests.greg_fixtures import drop, signed
from tests.unit.test_greg_learning import _age_all, apply, events, morning, review, setup  # noqa: F401

A_LABELS = {"needs_decision": ["acme/kernel#7", "acme/organ#2"]}
B_LABELS = {"needs_decision": ["acme/kernel#11", "acme/kernel#7", "acme/organ#22"]}


def life(s, steps, out: Path):
    """Run steps in a fresh process that opens its own Body and then dies by SIGKILL mid-life."""
    s["body"].close()

    def run():
        s["body"] = Body(s["home"], clock=s["clock"]).open()
        s["body"].boot()
        result = steps(s)
        out.write_text(json.dumps({"clock": s["clock"].now.isoformat(), "result": result}, default=str))
        os.kill(os.getpid(), signal.SIGKILL)           # process death: nothing is closed or flushed

    child = multiprocessing.get_context("fork").Process(target=run)
    child.start()
    child.join(120)
    assert child.exitcode == -signal.SIGKILL, child.exitcode
    state = json.loads(out.read_text())
    s["clock"].now = datetime.fromisoformat(state["clock"])
    s["body"] = Body(s["home"], clock=s["clock"]).open()   # a new body from durable history only
    s["body"].boot()
    return state["result"]


def one_off_brief(s, day: str) -> dict:
    """A NEW founder-signed bounded brief mission in world `day`; returns its delivery and its appraisal."""
    daily = next(e for e in events(s, "mission.registered") if e["spec"]["mission_id"] == "m:engineering-brief-daily")
    local = {r["name"]: r["path"] for r in daily["spec"]["strategies"][0]["params"]["local"]}
    spec = engineering_brief(local=local, github=["acme/kernel", "acme/organ"], preauthorize_delivery=True,
                             horizon_days=60, today=s["clock"].now.date().isoformat())
    s["clock"].advance(13 * 3600)          # older than a one-off brief allows (12h), younger than daily (20h)
    s["gh"].day, s["gh"].now = day, s["clock"].now
    drop(s["home"], signed(s["key"], s["body_id"], "MISSION", spec, now=s["clock"].now))
    for _ in range(4):
        s["clock"].advance(30)
        s["body"].tick()
        _age_all(s)
    mid = spec["mission_id"]
    action = [e for e in events(s, "mission.action") if e["mission_id"] == mid and e["status"] == "DONE"]
    appraisal = [e for e in events(s, "mission.appraised") if e["mission_id"] == mid]
    assert len(action) == 1 and appraisal, (action, appraisal)
    return {"output": s["body"]._receipt_output(action[0]["receipt"]), "appraisal": appraisal[-1], "mission_id": mid}


def critique(action, labels, *, regression=None, text="test-key review"):
    body = {"target_event_id": action["event_id"], "verdict": "note", "evidence_type": "founder_judgment",
            "text": text, "review": {"classification": "PREFERENCE", "labels": labels}}
    if regression:
        body["regression"] = regression
    return body


def open_regressions(s):
    return {r["regression_id"] for r in [c["regression"] for c in events(s, "critique.recorded") if c.get("regression")]
            } - {c["regression_id"] for c in events(s, "critique.regression_closed")}


def test_retained_learning_survives_process_death_and_a_revert_does_too(setup, tmp_path):
    s = setup

    def learn(s):
        a = morning(s, "A")
        apply(s, critique(a, A_LABELS))
        b = morning(s, "B")
        apply(s, critique(b, B_LABELS))
        return learning.policy(s["body"].journal, "brief.engineering")

    in_life = life(s, learn, tmp_path / "life1.json")
    assert in_life["version"] == 1
    rebuilt = learning.policy(s["body"].journal, "brief.engineering")
    assert rebuilt == in_life                                                    # reconstructed from the ledger
    c = one_off_brief(s, "C")                                                    # a new eligible mission
    assert c["output"]["inputs"]["policy"] == {"version": 1, "draft_attention": "after_ready",
                                               "check_fetch_order": "api_order"}
    deliveries = Layout(s["home"]).home / "deliveries"
    verdict = c["appraisal"]                                                     # the separate-process appraiser
    assert verdict["verdict"] == "VERIFIED" and verdict["checks"]["deliveries_bound_to_evidence"] is True, verdict
    held_out = events(s, "learning.evaluated")[0]
    assert held_out["decision"] == "RETAIN"
    b_inputs = s["body"]._receipt_output(held_out["case"]["receipt"])["inputs"]
    assert "ready-for-review" in briefs.render({**b_inputs, "policy": c["output"]["inputs"]["policy"]})

    retained = next(e for e in s["body"].journal.replay("learning.retained"))

    def revert(s):
        return apply(s, {"target_event_id": retained.event_id, "verdict": "reject",
                         "evidence_type": "founder_judgment", "text": "revert: drafts inline again"})

    life(s, revert, tmp_path / "life2.json")
    assert learning.policy(s["body"].journal, "brief.engineering")["version"] == 0
    d = one_off_brief(s, "D")
    assert d["output"]["inputs"]["policy"] == {"version": 0, "draft_attention": "inline",
                                               "check_fetch_order": "api_order"}   # baseline behavior restored
    assert d["appraisal"]["verdict"] == "VERIFIED" and d["appraisal"]["checks"]["deliveries_bound_to_evidence"]
    assert "ready-for-review" not in briefs.render({**b_inputs, "policy": d["output"]["inputs"]["policy"]})
    assert briefs.verify_delivery(d["output"], deliveries)[0]
    assert events(s, "learning.retained") and events(s, "learning.reverted")    # history kept
    if os.environ.get("GREG_RECORD_EVIDENCE"):
        out = Path(__file__).resolve().parents[1] / "evidence" / "greg-product"
        (out / "learning-durability.json").write_text(json.dumps({
            "reality": "TESTED: each body life ran in a forked process killed by SIGKILL; the next life was a new "
                       "Body built from the GREG home; per-test key; fixture GitHub",
            "retained_in_dying_life": in_life, "rebuilt_after_death": rebuilt,
            "day_C_policy": c["output"]["inputs"]["policy"], "day_C_appraisal": verdict,
            "reverted": events(s, "learning.reverted"),
            "day_D_policy_after_revert_and_death": d["output"]["inputs"]["policy"],
            "day_D_appraisal": d["appraisal"]}, indent=1, default=str))
    s["body"].close()


def test_a_regression_closes_only_when_its_own_correction_demonstrates_the_close_condition(setup):
    s = setup
    a = morning(s, "A")
    mine = apply(s, critique(a, A_LABELS, regression="drafts bury the pull requests that need me"))
    other = apply(s, {"target_event_id": a["event_id"], "verdict": "note", "evidence_type": "founder_judgment",
                      "text": "an unrelated regression on the same brief",
                      "regression": "the brief does not show review requests"})
    reg_mine, reg_other = mine["regression"]["regression_id"], other["regression"]["regression_id"]
    assert open_regressions(s) == {reg_mine, reg_other}
    b = morning(s, "B")
    apply(s, critique(b, B_LABELS))
    closure = events(s, "critique.regression_closed")
    assert [c["regression_id"] for c in closure] == [reg_mine]                   # never the other correction's
    c = closure[0]
    assert c["critique_id"] == mine["critique_id"] and c["decision"] == "RETAIN"
    assert c["check"]["failing_on_baseline"] == {"noise_before_last_needed": 4}
    assert c["check"]["on_candidate"] == {"noise_before_last_needed": 0}
    assert c["held_out_case"]["receipt"] == b["receipt"] and c["evidence"]["receipt"] == b["receipt"]
    assert open_regressions(s) == {reg_other}
    report = tribunal.morning_report(s["body"].journal, s["body"].engine)
    assert [r["regression_id"] for r in report["q11_change"]] == [reg_other]
    assert any(e["critique"]["regression"]["state"] == "OPEN" for e in [{"critique": x} for x in
               events(s, "critique.recorded") if x.get("regression", {}).get("regression_id") == reg_mine])
    s["body"].close()


def test_a_regression_stays_open_when_the_candidate_is_rejected_or_not_demonstrated(setup):
    s = setup
    a = morning(s, "A")
    apply(s, {**critique(a, A_LABELS, regression="drafts bury what needs me"),
              "review": {"classification": "CORRECT",
                         "correction": {"knob": "draft_attention", "value": "after_ready"}}})
    b = morning(s, "B")
    apply(s, critique(b, {"needs_decision": ["acme/kernel#12", "acme/organ#21", "acme/organ#20"]}))
    assert events(s, "learning.decided")[0]["decision"] in ("REGRESS", "CONFLICTED")
    assert not events(s, "critique.regression_closed") and len(open_regressions(s)) == 1


def test_the_close_condition_itself_must_be_demonstrated():
    retained_without_a_defect = ({"missed_obligations": 0, "noise_before_last_needed": 0, "top_item_needed": 0},
                                 {"missed_obligations": 0, "noise_before_last_needed": 0, "top_item_needed": 1})
    assert learning.decide(*retained_without_a_defect)[0] == "RETAIN"
    assert learning.regression_check(*retained_without_a_defect)[0] is False       # RETAIN alone does not close
    partial = ({"missed_failing_ready": 2, "unknown_ready_checks": 3}, {"missed_failing_ready": 0,
                                                                        "unknown_ready_checks": 1})
    assert learning.regression_check(*partial)[0] is False                         # every failing check must clear
    traded = ({"noise_before_last_needed": 4, "missed_obligations": 0}, {"noise_before_last_needed": 0,
                                                                         "missed_obligations": 1})
    assert learning.regression_check(*traded)[0] is False                          # no defect traded for another
    assert learning.regression_check({"missed_failing_ready": 2}, {"missed_failing_ready": 0})[0] is True
