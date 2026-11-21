"""Round 4 of the review of #221 (session_01Kucyfoabgsg6W8H8xj4qea, #221 comment 6510355399).

TXT-R4-1 runs on the fixture journal and a real body; the decision-value cases run on injected settled counts
through the compiler's own rules; the reconcile cases on a real body with a per-test founder key. Values are
synthetic test inputs.
"""
from __future__ import annotations


import pytest

pytest.importorskip("networkx")
pytest.importorskip("scipy")

from greg.cognition import compiler, settlement  # noqa: E402
from greg.cognition.contracts import digest  # noqa: E402
from tests.unit.test_greg_construction_realization import PROMISED, Run  # noqa: E402
from tests.unit.test_greg_pending_construction_realization import appraise, pending  # noqa: E402
from tests.unit.test_greg_recombine import PORTFOLIO  # noqa: E402

MISSION = "m:pending-fixture"


def weigh(monkeypatch, counts, disputes):
    monkeypatch.setattr(compiler, "_settled_counts", lambda journal: counts)
    rows = [{"method": m, "mission_id": "m", "check_passed": True} for m, d in disputes.items() for _ in range(d)]
    settlement._weigh_investigations(object(), rows, settling={"m": object()})
    return {r["method"]: r for r in rows}


# --- TXT-R4-1: the row text follows the integrator's fix (#196 afcd75f3) -------------------------------------
# The fix itself (Body._close_out and _settling_appraisals) is #196's, tested by test_greg_achievement_after_unmet.py.


def test_txt_r4_1_an_achievement_after_an_appraised_failure_reads_pending_until_its_own_appraisal():
    journal, _ = pending()
    journal.record("mission.unmet", {"mission_id": MISSION})
    unmet = journal.events[-1].event_id
    journal.record("mission.appraised", {"mission_id": MISSION, "verdict": "VERIFIED_UNMET", "checks": {},
                                         "closure_event": unmet})
    assert MISSION not in settlement._awaiting_appraisal(journal)
    journal.record("mission.achieved", {"mission_id": MISSION})
    assert MISSION in settlement._awaiting_appraisal(journal)       # "pending", not "final"
    journal.record("mission.appraised", {"mission_id": MISSION, "verdict": "VERIFIED", "checks": {}})
    assert MISSION not in settlement._awaiting_appraisal(journal)


# --- the decision value -------------------------------------------------------------------------------------------


def test_w4_4_a_disputed_method_with_no_settled_outcome_is_in_the_walk(monkeypatch):
    """X (32, 32) with 1 dispute; Y has no settled outcome and 12 open disputes: with Y at 8 of 10, Y first, the
    pick goes Y, Y, X across X's states."""
    row = weigh(monkeypatch, {"construction.X": (32, 32)}, {"construction.X": 1, "construction.Y": 12})
    assert row["construction.X"]["priority"] == "investigate"
    assert any("construction.Y" in r for r in row["construction.X"]["decision_impact"]["could_change"])


@pytest.mark.parametrize("counts, disputes", [
    ({"construction.X": (20, 5), "fit.B": (30, 20)}, {"construction.X": 1}),
    ({"construction.X": (12, 1)}, {"construction.X": 2}),
])
def test_w4_3_a_method_demoted_at_every_reachable_count_is_not_an_inhibition_change(monkeypatch, counts, disputes):
    row = weigh(monkeypatch, counts, disputes)["construction.X"]
    assert not any("inhibition rule" in r for r in row["decision_impact"]["could_change"])
    assert row["priority"] == "hold"


def test_w4_5_laplace_is_not_compared_across_demotion_classes(monkeypatch):
    """X (5, 1) with 1 dispute is undemoted; Y (14, 3) is demoted, Laplace 0.250 at X's lower end."""
    row = weigh(monkeypatch, {"construction.X": (5, 1), "fit.Y": (14, 3)}, {"construction.X": 1})["construction.X"]
    assert not any("fit.Y" in r for r in row["decision_impact"]["could_change"])


def test_w4_6_a_partial_resolution_of_another_method_is_walked(monkeypatch):
    """X (34, 20) with 1 dispute, Z (14, 12) with 4: the change needs Z at 13 of 15, one of its four resolved."""
    row = weigh(monkeypatch, {"construction.X": (34, 20), "construction.Z": (14, 12)},
                {"construction.X": 1, "construction.Z": 4})["construction.X"]
    assert row["priority"] == "investigate"
    assert any("with construction.Z at" in r for r in row["decision_impact"]["could_change"])


def test_n38_the_joint_state_limit_applies_per_family_and_is_named(monkeypatch):
    counts = {f"construction.M{i}": (20, 10) for i in range(4)}
    row = weigh(monkeypatch, counts, {m: 3 for m in counts})["construction.M0"]
    assert row["priority"] == "investigate"
    assert any("joint state limit" in w for w in row["decision_impact"]["walk_limits"])


def test_n43_the_reason_names_the_fit_actually_ranked_first(monkeypatch):
    counts = {"construction.X": (36, 24), "construction.Y": (31, 28), "fit.A": (18, 4)}     # fit.A is demoted
    row = weigh(monkeypatch, counts, {"construction.X": 4, "construction.Y": 2})["construction.X"]
    reasons = row["decision_impact"]["could_change"]
    assert reasons and not any("fit.A ranked first" in r or "fit.A or" in r for r in reasons)


# --- reconcile -------------------------------------------------------------------------------------------------


def _old_rule_body(run, monkeypatch, pid):
    journal = run.body.journal
    current_rule = settlement._answer_version
    with monkeypatch.context() as old:
        old.setattr(settlement, "_answer_version", lambda built: digest(["engine-1", built.get("result")]))
        record = run.ask(pid, PORTFOLIO)
        run.realize(record, PROMISED, source="external_record")
        settlement.reconcile(journal)
    head = [e for e in journal.replay("cognition.settled") if e.payload.get("compile_receipt")][-1]
    return record, head, current_rule


def _supersessions(journal, event_id):
    return [e for e in journal.replay("cognition.settled") if e.payload.get("supersedes") == event_id]


def test_n32_a_merged_shadow_is_closed_once_even_after_a_withdrawal(tmp_path, monkeypatch):
    with Run(tmp_path) as run:
        journal = run.body.journal
        record, head, _ = _old_rule_body(run, monkeypatch, "pf-n32")
        shadow = journal.record("cognition.settled", {**head.payload, "answer_version": digest(["engine-2"]),
                                                      "supersedes": None}, key=["old-rule", "engine-2"])
        settlement.reconcile(journal)
        mission = next(e.payload["mission_id"] for e in journal.replay("mission.observed")
                       if e.payload["receipt"] == record.hash)
        appraise(journal, "UNAVAILABLE", mission_id=mission)
        settlement.reconcile(journal)
        settlement.reconcile(journal)
        assert len(_supersessions(journal, shadow.event_id)) == 1


def test_n46_an_unmeasured_duplicate_is_invalidated_not_merged(tmp_path, monkeypatch):
    with Run(tmp_path) as run:
        journal = run.body.journal
        record, head, current_rule = _old_rule_body(run, monkeypatch, "pf-n46")
        new = journal.record("cognition.settled", {**head.payload, "supersedes": None, "answer_version":
                             current_rule(record.payload["result"]["output"])}, key=["base", "new-row"])
        journal.record("cognition.settled", {**head.payload, "invalidated": True, "supersedes": head.event_id,
                       "reason": "current appraisal no longer supports competence; history retained"},
                       key=["base", "invalidate"])
        mission = next(e.payload["mission_id"] for e in journal.replay("mission.observed")
                       if e.payload["receipt"] == record.hash)
        appraise(journal, "UNAVAILABLE", mission_id=mission)            # the claim is unmeasured now
        settlement.reconcile(journal)
        [closed] = _supersessions(journal, new.event_id)
        assert closed.payload["invalidated"] is True and "merged_into" not in closed.payload


# --- N49: an appraised held closure is not awaiting ---------------------------------------------------------------


def test_n49_an_appraised_held_closure_does_not_read_pending():
    journal, _ = pending()
    journal.record("mission.held", {"mission_id": MISSION})
    held = journal.events[-1].event_id
    assert MISSION in settlement._awaiting_appraisal(journal)
    journal.record("mission.appraised", {"mission_id": MISSION, "verdict": "REFUTED", "checks": {},
                                         "closure_event": held})
    assert MISSION not in settlement._awaiting_appraisal(journal)
