"""Construction claims follow the appraisal of their own closure (review TXT-R6-1 of #196's 4ec00605, and S2/S3).

4ec00605 settled each observation under its own closure's appraisal in measured_outcomes, but the offered and
disputed rows of awaiting_realization, and the weighing of disputes, still read the mission-level rule, which drops a
VERIFIED_UNMET once the mission is achieved. They now take each claim's appraisal as measured_outcomes does.
Fixture journal; values are synthetic.
"""
from __future__ import annotations

from greg.cognition import settlement
from greg.sop import REQUIRED_CHECKS
from tests.unit.test_greg_pending_construction_realization import observe, pending

MID = "m:pending-fixture"


def appraise(journal, verdict, closure_event=None, *, failing=()):
    journal.record("mission.appraised", {
        "mission_id": MID, "verdict": verdict,
        "checks": {k: verdict.startswith("VERIFIED") and k not in failing for k in REQUIRED_CHECKS},
        **({"closure_event": closure_event} if closure_event else {})})
    return journal.events[-1].event_id


def close(journal, kind):
    journal.record(f"mission.{kind}", {"mission_id": MID})
    return journal.events[-1].event_id


def unmet_then_appraised(journal):
    unmet = close(journal, "unmet")
    return appraise(journal, "VERIFIED_UNMET", unmet)


def test_the_row_of_a_claim_observed_before_a_failure_closure_still_settles_once_the_mission_is_achieved():
    journal, receipt = pending()
    failure = unmet_then_appraised(journal)
    [row] = settlement.awaiting_realization(journal)
    assert row["settles"].startswith("once for the claim")
    close(journal, "achieved")                                   # no appraisal of the achievement yet
    [row] = settlement.awaiting_realization(journal)
    assert row["settles"].startswith("once for the claim")
    settlement.record_realization(journal, receipt=receipt, realized=1, source="external_record")
    [outcome] = settlement.measured_outcomes(journal)
    assert outcome["appraisal_event"] == failure and outcome["world"]["realized"] == 1


def test_a_dispute_on_a_claim_observed_before_a_failure_closure_is_weighed_after_a_refuted_achievement():
    journal, receipt = pending()
    unmet_then_appraised(journal)
    close(journal, "achieved")
    appraise(journal, "REFUTED")
    settlement.record_realization(journal, receipt=receipt, realized=2, source="founder_reported")
    settlement.record_realization(journal, receipt=receipt, realized=1, source="founder_reported")
    [row] = [r for r in settlement.awaiting_realization(journal) if r.get("kind") == "objective_conflict"]
    assert row["claim_settles"] is True and row["decision_impact"] is not None
    assert "no appraisal settles" not in row["priority_why"]


def test_an_observation_after_a_failure_closure_settles_under_the_achievements_own_verified():   # mutant S2
    journal, receipt = pending(observed=False)
    unmet_then_appraised(journal)
    observe(journal, receipt)
    observed = journal.events[-1].event_id
    close(journal, "achieved")
    success = appraise(journal, "VERIFIED")
    [outcome] = settlement.measured_outcomes(journal)
    assert outcome["observation_event"] == observed and outcome["appraisal_event"] == success


def test_a_failure_closure_whose_appraisal_misses_a_required_check_settles_nothing():               # mutant S3
    journal, _ = pending()
    unmet = close(journal, "unmet")
    appraise(journal, "VERIFIED_UNMET", unmet, failing=(REQUIRED_CHECKS[0],))
    close(journal, "achieved")
    assert settlement.measured_outcomes(journal) == []
