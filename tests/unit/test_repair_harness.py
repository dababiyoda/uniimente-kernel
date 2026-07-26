"""The governed loop, asserted end to end.

The loop's value depends on properties that are easy to claim and easy to lose:
that the author did not pick the winner, that the decision cannot promote
anything, that evidence is append-only, and that a failed prediction is reported
rather than absorbed. Each of those is a test here.
"""
import json
import subprocess
import sys

import pytest

from evolution.capsule import HYPOTHESIS_ONLY, RetainRegressKill
from evolution.repair import spec
from evolution.repair.harness import (
    ReplacementExperiment, continuity_fingerprint, original_is_intact,
)
from provenance.ledger import EvidenceLedger


@pytest.fixture(scope="module")
def run():
    ledger = EvidenceLedger("sha256:package3-test")
    record = ReplacementExperiment(ledger=ledger).run()
    return record, ledger


# ==========================================================================
# The loop's shape
# ==========================================================================

def test_the_control_confirms_health_before_anything_is_removed(run):
    record, _ = run
    assert record["control_healthy"]["lost"] is False
    assert record["control_healthy"]["function_fraction"] == 1.0


def test_the_removal_happened_and_was_detected_blind(run):
    record, _ = run
    assert record["disable_event"]["type"] == "repair.component_disabled"
    assert record["disable_event"]["evicted_modules"]

    loss = record["detected_loss"]
    assert loss["lost"] is True
    assert loss["observed_edges"] == 0
    assert loss["required_edges"] == 4
    # Blindness survives serialisation into the evidence record.
    assert spec.SUBJECT_PACKAGE not in json.dumps(loss)


def test_governance_and_continuity_held_while_the_function_was_absent(run):
    record, _ = run
    assert record["governance_while_absent"] == {
        "authority_compiles": True, "shutdown_succeeds": True,
        "original_on_disk_intact": True}
    assert record["continuity"]["while_absent"] == spec.CONTINUITY_COMBINED_SHA256


def test_continuity_is_unchanged_before_during_and_after(run):
    record, _ = run
    continuity = record["continuity"]
    assert continuity["before"] == continuity["after"] == \
        continuity["while_absent"] == spec.CONTINUITY_COMBINED_SHA256
    assert continuity["unchanged"] is True
    assert continuity["artifact_count"] == 12
    # And still true now, after the whole run.
    assert continuity_fingerprint() == spec.CONTINUITY_COMBINED_SHA256
    assert original_is_intact() is True


def test_every_frozen_candidate_was_tried_and_none_was_added(run):
    record, _ = run
    assert set(record["trials"]) == set(spec.CANDIDATE_IDS)
    for cid, trial in record["trials"].items():
        # Five corpora attempted per candidate, all kept.
        assert len(trial["attempts"]) == 1 + len(spec.HELD_OUT_CORPUS)
        assert {a["corpus"] for a in trial["attempts"]} == \
            {"LIVE"} | {c["corpus_id"] for c in spec.HELD_OUT_CORPUS}


# ==========================================================================
# Selection was not performed by the author
# ==========================================================================

def test_ranking_uses_the_existing_comparison_and_the_frozen_thresholds(run):
    record, _ = run
    comparison = record["comparison"]
    assert comparison["baseline"] == spec.EXPERIMENT.baseline == 0.0
    assert comparison["threshold"] == spec.EXPERIMENT.threshold == 1.0
    assert len(comparison["primary_ranking"]) == len(spec.CANDIDATE_IDS)
    for row in comparison["primary_ranking"]:
        assert row["measured"] in (0.0, 1.0), \
            "the gated metric admits no partial credit"


def test_the_primary_champion_is_declared_tie_arbitrary_when_it_is(run):
    """Honesty about a weak signal. cost_usd and duration_days are zero for every
    candidate, so Comparison's score tuples are identical and the 'champion' is
    just whichever sorted first. Reporting that as a finding would be false."""
    record, _ = run
    measured = {row["measured"] for row in record["comparison"]["primary_ranking"]}
    if len(measured) == 1:
        assert record["comparison"]["champion_is_tie_arbitrary"] is True
        assert "not a finding" in record["comparison"]["note"]


def test_the_secondary_order_is_the_frozen_one_and_actually_discriminates(run):
    record, _ = run
    secondary = record["secondary_ranking"]
    assert secondary["terms"] == list(spec.SECONDARY_ORDER_TERMS)

    keys = [tuple(row[t] for t in spec.SECONDARY_ORDER_TERMS)
            for row in secondary["order"]]
    assert keys == sorted(keys), "the secondary order is not sorted by its own key"
    assert len(set(keys)) == len(keys), \
        "the secondary order failed to discriminate; it is not a tie-break"


def test_selection_reports_the_two_questions_separately(run):
    """The founder required these kept apart: did a different structure restore
    the function, and was it better than restoring the original."""
    record, _ = run
    selection = record["selection"]
    assert selection["best_structural_replacement"] in spec.CANDIDATE_IDS
    assert selection["best_structural_replacement"] != spec.BASELINE_CANDIDATE_ID
    assert selection["cheapest_overall"] in spec.CANDIDATE_IDS
    assert "the author did not choose" in selection["reason"]


def test_the_baseline_is_never_reported_as_a_structural_replacement(run):
    record, _ = run
    assert spec.BASELINE_CANDIDATE_ID not in \
        record["selection"]["all_qualifying_replacements"]
    assert record["trials"][spec.BASELINE_CANDIDATE_ID][
        "qualifies_as_replacement"] is False


# ==========================================================================
# Installation, rollback, and the limits of both
# ==========================================================================

def test_installation_is_verified_by_the_blind_detector(run):
    record, _ = run
    install = record["installation"]
    assert install["attempted"] is True
    assert install["restored"] is True
    assert install["function_fraction"] == 1.0
    assert "blind detector" in install["verified_by"]


def test_installation_scope_is_stated_and_the_live_path_is_untouched(run):
    """Overstating this would be the easiest way to inflate the result. The
    winner goes into the experiment's registry, not into the kernel's imports."""
    record, _ = run
    assert "live import path is unmodified" in record["installation"]["scope"]

    import os
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), "closure", "kernel_registry.py")) as fh:
        registry_source = fh.read()
    assert "from linker.linker import InstitutionalLinker" in registry_source, \
        "the kernel's live path was rewritten; that was never authorized"
    assert "evolution.repair" not in registry_source

    assert any("live import path" in lim for lim in record["limitations"])


def test_rollback_restores_the_original_and_the_original_survived(run):
    record, _ = run
    rollback = record["installation"]["rollback"]
    assert rollback["restored_after_rollback"] is True
    assert rollback["original_intact"] is True
    assert rollback["registry_history"] == ["repair.provider_registered",
                                           "repair.provider_withdrawn",
                                           "repair.provider_registered"]


def test_the_baseline_rollback_is_one_step_and_replacements_cost_more(run):
    record, _ = run
    baseline_steps = record["trials"][spec.BASELINE_CANDIDATE_ID]["cost"][
        "rollback_steps"]
    assert baseline_steps == 1, \
        "nothing was deleted, so restoring the original must be a single step"
    for cid in spec.CANDIDATE_IDS:
        if cid != spec.BASELINE_CANDIDATE_ID:
            assert record["trials"][cid]["cost"]["rollback_steps"] > baseline_steps


# ==========================================================================
# The decision may recommend and may not promote
# ==========================================================================

def test_the_decision_is_valid_and_cannot_self_promote(run):
    record, _ = run
    decision = record["decision"]
    assert decision["decision"] in (RetainRegressKill.RETAIN,
                                    RetainRegressKill.REGRESS,
                                    RetainRegressKill.KILL)
    assert decision["reason"]
    assert decision["verifier"]["level"] not in HYPOTHESIS_ONLY, \
        "a hypothesis-only verifier may never authorize a promotion decision"

    # The structural guarantee, re-asserted directly: retain is unrepresentable
    # with a hypothesis-only verifier.
    from evolution.capsule import RetainRegressKillDecision, VerifierRecord
    weak = RetainRegressKillDecision(
        decision=RetainRegressKill.RETAIN, reason="x", decided_by="test",
        verifier=VerifierRecord(level="same_model_critique", evidence="e",
                                decided_by="test"))
    assert any("may not authorize retain" in p for p in weak.validate())


def test_the_decision_declines_promotion_when_the_original_is_cheaper(run):
    """The founder's instruction: if restoring the original is cheaper and safer,
    say so, and let the alternative stand as a proven fallback."""
    record, _ = run
    cheapest = record["selection"]["cheapest_overall"]
    if cheapest == spec.BASELINE_CANDIDATE_ID:
        assert record["decision"]["decision"] == RetainRegressKill.REGRESS
        reason = record["decision"]["reason"]
        assert "PROVEN" in reason
        assert "DECLINED" in reason
        assert "fallback" in reason
        assert "promotes nothing" in reason


def test_the_capsule_records_the_whole_cycle(run):
    record, _ = run
    capsule = record["capsule"]
    assert capsule["bottleneck"]
    assert capsule["experiment"]["experiment_id"] == \
        spec.EXPERIMENT.experiment_id
    assert capsule["measured_value"] == 1.0
    assert capsule["outcome_class"] == "positive"
    assert capsule["tree"]["branches"], "strategy branching was not reused"
    assert len(capsule["tree"]["branches"]) == 11, \
        "the existing generator produces all eleven branch kinds"
    assert "WRONG" in capsule["notes"], \
        "the failed prediction must survive into the capsule"


# ==========================================================================
# Evidence
# ==========================================================================

def test_the_ledger_chain_verifies_and_is_append_only(run):
    record, ledger = run
    ok, detail = ledger.verify_chain()
    assert ok, detail

    events = [r.payload.get("type") for r in ledger.by_type("event")]
    for required in ("repair.component_disabled", "repair.component_restored",
                     "repair.capability_loss_detected", "repair.trial_complete",
                     "repair.provider_registered", "repair.provider_withdrawn",
                     "repair.capsule_recorded"):
        assert required in events, f"{required} was not ledgered"


def test_failed_candidates_and_negative_results_are_preserved(run):
    """Nothing is summarised away. Every attempt on every corpus survives, and
    the rejected list is present even when it is empty."""
    record, _ = run
    assert "rejected" in record["selection"]
    assert "failure_analysis" in record
    total_attempts = sum(len(t["attempts"]) for t in record["trials"].values())
    assert total_attempts == len(spec.CANDIDATE_IDS) * 5


def test_the_audit_is_honest_rather_than_green(run):
    """Package 3 has no buyer, no beneficiary and no external consequence.
    Marking those satisfied to obtain a green audit is the fabricated field the
    build order forbids, so INCOMPLETE is the correct verdict."""
    record, _ = run
    audit = record["spider_web_audit"]
    assert audit["verdict"] == "INCOMPLETE"
    missing = set(audit["missing_completeness"])
    assert {"external_consequence", "buyer_or_mandate_actor", "real_beneficiary"} \
        <= missing
    assert "settlement_capital_physics" in audit["sides_failed"]


def test_limitations_are_carried_into_the_result(run):
    record, _ = run
    joined = " ".join(record["limitations"]).lower()
    for expected in ("one author", "stateless", "unscripted morphogenesis",
                     "live import path"):
        assert expected in joined, f"limitation dropped: {expected}"
    assert len(record["limitations"]) >= len(spec.DECLARED_LIMITATIONS)


def test_the_record_names_the_frozen_spec_it_was_judged_by(run):
    record, _ = run
    assert record["spec_sha256"] == spec.SPEC_SHA256
    assert record["baseline_commit"] == spec.BASELINE_COMMIT
    assert record["experiment_id"] == spec.EXPERIMENT.experiment_id


# ==========================================================================
# The failed prediction is reported, not absorbed
# ==========================================================================

def test_prediction_review_scores_every_frozen_prediction(run):
    record, _ = run
    review = record["prediction_review"]
    for cid in spec.CANDIDATE_IDS:
        assert set(review[cid]) >= {
            "predicted_function_score", "actual_function_score",
            "predicted_repair_cost_rank", "actual_repair_cost_rank",
            "function_prediction_held", "cost_rank_prediction_held"}
    assert review["summary"]["predictions_total"] == 4


def test_the_r3_prediction_is_recorded_as_wrong(run):
    """spec.EXPECTED_RESULTS froze R3 at 0.0 and predicted it would fail HO-4.
    It scored 1.0. The spec required that outcome be reported as a failed
    prediction, so this test exists to make silence impossible."""
    record, _ = run
    r3 = record["prediction_review"]["R3-local-rule"]
    assert r3["predicted_function_score"] == 0.0
    assert r3["actual_function_score"] == 1.0
    assert r3["function_prediction_held"] is False
    assert record["prediction_review"]["summary"]["function_predictions_held"] < 4, \
        "if every prediction held, this test is stale and must be revisited"


# ==========================================================================
# The runnable entry point
# ==========================================================================

def test_module_entry_point_emits_a_valid_record_and_exits_zero():
    proc = subprocess.run([sys.executable, "-m", "evolution.repair"],
                          capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, proc.stderr[-2000:]
    record = json.loads(proc.stdout)
    assert record["ledger"]["chain_verifies"] is True
    assert record["continuity"]["unchanged"] is True
    assert record["detected_loss"]["lost"] is True
