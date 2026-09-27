"""Held-out learning evidence is independent BRIEFS, not a count of labels.

One brief is one case. A newer signed label on the same brief supersedes the earlier one
for scoring (the earlier one stays in history), so re-labelling can neither add weight nor
turn a training brief into held-out evidence. Candidate fitting, retention, post-retention
monitoring and the retry cool-down each count distinct briefs, and the briefs used by one
decision phase are not reused as the evidence of the next.

Harness: the real daily brief mission of test_greg_learning_gate (test key, fixture GitHub).
"""
import os
import subprocess
import sys

from greg import improvement
from greg.body import Body
from tests.greg_fixtures import drop, signed
from tests.unit.test_greg_briefs import github, repo  # noqa: F401 (fixtures)
from tests.unit.test_greg_learning_gate import DRAFT, Morning


def relabel(m, action, **labels):
    """A later signed label on a brief that is already labelled: a correction or a repeat."""
    m.clock.advance(60)
    m.label(action, **labels)


def brief_of(m) -> dict:
    return {c["case_id"]: c["brief_event_id"]
            for c in improvement.labelled_cases(m.body.journal, m.body.ledger, every_label=True)}


def distinct_briefs(m, case_ids) -> set:
    mapping = brief_of(m)
    return {mapping[case_id] for case_id in case_ids}


def undecided(m) -> bool:
    return not (m.events("improvement.retained") or m.events("improvement.rejected"))


def test_1_the_training_brief_relabelled_three_times_leaves_the_candidate_in_shadow(tmp_path, repo, github):
    m = Morning(tmp_path, repo)
    action, _ = m.brief()
    m.label(action, noise=[DRAFT])
    assert m.events("improvement.proposed")[0]["state"] == "SHADOW"
    for _ in range(3):
        relabel(m, action, noise=[DRAFT])
    assert undecided(m) and not m.events("improvement.evaluated")      # the derivation brief is never held out
    assert len(m.events("improvement.proposed")) == 1
    m.body.close()


def test_2_3_one_later_brief_labelled_three_times_is_one_case_three_distinct_briefs_decide(tmp_path, repo, github):
    m = Morning(tmp_path, repo)
    action, _ = m.brief()
    m.label(action, noise=[DRAFT])
    later, _ = m.brief()
    for _ in range(3):
        relabel(m, later, noise=[DRAFT])
    assert undecided(m)
    assert distinct_briefs(m, [e["case_id"] for e in m.events("improvement.evaluated")]) == {later.event_id}
    for _ in range(2):
        action, _ = m.brief()
        m.label(action, noise=[DRAFT])
    retained = m.events("improvement.retained")
    assert len(retained) == 1 and retained[0]["errors"] == {"current": 3, "candidate": 0}
    assert len(distinct_briefs(m, retained[0]["held_out"])) == 3 == len(retained[0]["held_out"])
    m.body.close()


def test_3_three_distinct_later_briefs_without_a_strict_gain_reject(tmp_path, repo, github):
    m = Morning(tmp_path, repo)
    action, _ = m.brief()
    m.label(action, noise=[DRAFT])
    for labels in ({"noise": [DRAFT]}, {}, {}):                          # one agrees, two disagree
        action, _ = m.brief()
        m.label(action, **labels)
    rejected = m.events("improvement.rejected")
    assert len(rejected) == 1 and rejected[0]["errors"] == {"current": 1, "candidate": 2}
    assert not m.events("improvement.retained") and len(distinct_briefs(m, rejected[0]["held_out"])) == 3
    m.body.close()


def test_4_10_a_corrected_label_controls_scoring_counts_once_and_the_original_stays_inspectable(
        tmp_path, repo, github):
    m = Morning(tmp_path, repo)
    action, _ = m.brief()
    m.label(action, noise=[DRAFT])
    corrected, _ = m.brief()
    m.label(corrected, noise=[DRAFT])                                    # original judgement
    original = m.events("critique.recorded")[-1]["critique_id"]
    relabel(m, corrected)                                                # correction: the draft was worth seeing
    correction = m.events("critique.recorded")[-1]["critique_id"]
    for _ in range(2):
        action, _ = m.brief()
        m.label(action, noise=[DRAFT])
    retained = m.events("improvement.retained")[0]
    assert len(retained["held_out"]) == 3                                # the corrected brief counts once
    assert correction in retained["held_out"] and original not in retained["held_out"]
    assert retained["errors"] == {"current": 2, "candidate": 1}          # scored on the NEWEST label
    report = improvement.report(m.body.journal, m.body.ledger)
    assert report["labelled_briefs"] == 4
    assert report["superseded_labels"] == [{"case_id": original, "brief_event_id": corrected.event_id,
                                            "labels": {"missed": [], "noise": [DRAFT]},
                                            "superseded_by": correction}]
    assert {original, correction} <= {e["critique_id"] for e in m.events("critique.recorded")}   # history kept
    m.body.close()


def test_5_three_labels_on_one_brief_cannot_close_a_regression(tmp_path, repo, github):
    m = Morning(tmp_path, repo)
    origin_brief, _ = m.brief()
    m.label(origin_brief, noise=[DRAFT], regression="idle drafts bury decisions")
    later, _ = m.brief()
    for _ in range(3):
        relabel(m, later, noise=[DRAFT])
    for _ in range(2):
        relabel(m, origin_brief, noise=[DRAFT])                          # nor can the originating brief
    assert not m.events("critique.regression_closed") and undecided(m)
    for _ in range(2):
        action, _ = m.brief()
        m.label(action, noise=[DRAFT])
    closed = m.events("critique.regression_closed")
    assert len(closed) == 1
    evidence_briefs = {row["brief_event_id"] for row in closed[0]["held_out_evidence"]}
    assert len(evidence_briefs) == 3 == len(closed[0]["held_out_evidence"])
    assert origin_brief.event_id not in evidence_briefs
    m.body.close()


def test_6_7_retention_briefs_are_not_reused_to_revert_distinct_later_briefs_can(tmp_path, repo, github):
    m = Morning(tmp_path, repo)
    labelled = []
    for _ in range(4):
        action, _ = m.brief()
        m.label(action, noise=[DRAFT])
        labelled.append(action)
    retained = m.events("improvement.retained")[0]
    for action in labelled[1:]:                                          # the retention evidence, re-judged
        relabel(m, action, missed=[DRAFT])
    monitored, _ = m.brief()
    for _ in range(3):
        relabel(m, monitored, missed=[DRAFT])                            # one later brief, three labels
    assert not m.events("improvement.reverted")
    for _ in range(2):
        action, _ = m.brief()
        m.label(action, missed=[DRAFT])
    reverted = m.events("improvement.reverted")
    assert len(reverted) == 1 and reverted[0]["errors"] == {"retained": 3, "restored": 0}
    monitoring = distinct_briefs(m, reverted[0]["cases"])
    assert len(monitoring) == 3 == len(reverted[0]["cases"])
    fitting = distinct_briefs(m, m.events("improvement.proposed")[0]["derived_from"])
    retention = distinct_briefs(m, retained["held_out"])
    assert not (fitting & retention) and not (retention & monitoring) and not (fitting & monitoring)
    m.body.close()


def test_retry_after_a_loss_needs_three_new_distinct_briefs(tmp_path, repo, github):
    m = Morning(tmp_path, repo)
    action, _ = m.brief()
    m.label(action, noise=[DRAFT])
    lost_on = []
    for _ in range(3):
        action, _ = m.brief()
        m.label(action)
        lost_on.append(action)
    assert m.events("improvement.rejected")
    for action in lost_on:                                               # re-judging the rejection's own evidence
        relabel(m, action, noise=[DRAFT])
    fresh, _ = m.brief()
    for _ in range(3):
        relabel(m, fresh, noise=[DRAFT])                                 # one new brief, three labels
    assert len(m.events("improvement.proposed")) == 1
    assert m.events("improvement.no_candidate")[-1].get("suppressed")
    for _ in range(2):
        action, _ = m.brief()
        m.label(action, noise=[DRAFT])
    assert len(m.events("improvement.proposed")) == 2                    # three new distinct briefs: may retry
    m.body.close()


def test_8_case_identity_and_watermarks_reconstruct_after_process_death(tmp_path, repo, github):
    m = Morning(tmp_path, repo)

    def die_and_rebuild():
        m.body.close()
        child = subprocess.run([sys.executable, "-c", "import os, signal; from greg.body import Body; "
                                "b=Body(os.environ['GREG_TEST_HOME']).open(); b.boot(); "
                                "os.kill(os.getpid(), signal.SIGKILL)"],
                               env={**os.environ, "GREG_TEST_HOME": str(m.home)})
        assert child.returncode == -9
        m.body = Body(m.home, clock=m.clock).open()
        m.body.boot()

    first, _ = m.brief()
    m.label(first, noise=[DRAFT])
    later, _ = m.brief()
    m.label(later, noise=[DRAFT])
    relabel(m, later, noise=[DRAFT])
    relabel(m, first, noise=[DRAFT])
    die_and_rebuild()
    relabel(m, later, noise=[DRAFT])
    assert undecided(m)
    assert [c["brief_event_id"] for c in improvement.labelled_cases(m.body.journal, m.body.ledger)] == [
        first.event_id, later.event_id]
    action, _ = m.brief()
    m.label(action, noise=[DRAFT])
    die_and_rebuild()
    assert undecided(m)
    action, _ = m.brief()
    m.label(action, noise=[DRAFT])
    retained = m.events("improvement.retained")
    assert len(retained) == 1 and len(distinct_briefs(m, retained[0]["held_out"])) == 3
    assert first.event_id not in distinct_briefs(m, retained[0]["held_out"])
    m.body.close()


def test_9_a_replayed_signed_critique_does_not_add_a_case(tmp_path, repo, github):
    m = Morning(tmp_path, repo)
    action, _ = m.brief()
    m.label(action, noise=[DRAFT])
    later, _ = m.brief()
    envelope = signed(m.key, m.body_id, "CRITIQUE", {
        "target_event_id": later.event_id, "verdict": "note", "evidence_type": "founder_judgment",
        "text": "morning review of the brief", "attention": {"missed": [], "noise": [DRAFT]}}, now=m.clock.now)
    drop(m.home, envelope)
    m.body.tick()
    for copy in range(3):
        m.clock.advance(60)
        drop(m.home, envelope, name=f"replay-{copy}.json")               # the same signed bytes again
        m.body.tick()
    cases = improvement.labelled_cases(m.body.journal, m.body.ledger)
    assert [c["brief_event_id"] for c in cases] == [action.event_id, later.event_id]
    assert distinct_briefs(m, [e["case_id"] for e in m.events("improvement.evaluated")]) == {later.event_id}
    assert undecided(m)
    m.body.close()
