"""WP-06 fast-cycle end-to-end + hostile suite (SPEC-WP06 4.8 + 4.9).

End-to-end: rc=0, capsule ok/verdict baseline_beaten with improvement 0.999,
decisions {retain:1, regress:2, kill:1}, ComparisonReport ranks stream #1,
the ImprovementProposal is sealed PENDING and then ratified by a founder
RATIFICATION event, FailureAnalysis records carry their pinned regression
test refs, the chain verifies, and the verdict line is byte-identical across
runs.

Hostile: a verifier re-run that disagrees with the adapter-attested receipt
facts fails closed with CycleError (both the engine's candidate check and the
WP-06 per-variant cross-check); ratification without a valid founder approval
over the proposal fingerprint seals NO RATIFICATION event and the proposal
stays pending.
"""
from __future__ import annotations

import json

import pytest

from kernel.contracts.evolution import ExperimentSpec
from kernel.crypto.hashing import canonical_json, content_hash
from kernel.evolution import CycleError, RuleBasedAuditor, SHIPPED_RULES
from kernel.gate import errors
from kernel.spine import Spine

from scripts import run_fast_cycle
from scripts import wp06_bench as bench
from scripts.run_fast_cycle import (
    CHUNK256_REGRESSION_TEST_REF,
    founder_ratify,
    pinned_matrix_protocol,
)
from tests.evolution.test_wp06_bench_matrix import build_world_wp06


def run_end_to_end(tmp_path):
    capsule_path = tmp_path / "wp06_fast_cycle_capsule.json"
    spine_dir = tmp_path / "spine-root"
    rc = run_fast_cycle.main(
        [
            "--capsule",
            str(capsule_path),
            "--spine-dir",
            str(spine_dir),
            "--skip-test-rerun",
        ]
    )
    return rc, capsule_path, Spine(spine_dir / "spine")


def test_fast_cycle_end_to_end(tmp_path):
    rc, capsule_path, spine = run_end_to_end(tmp_path)
    assert rc == 0
    capsule = json.loads(capsule_path.read_text(encoding="utf-8"))
    assert capsule["ok"] is True
    assert capsule["verdict"] == "baseline_beaten"
    assert capsule["baseline_value"] == 1000.0
    assert capsule["measured_value"] == 1.0
    assert capsule["improvement_ratio"] == 0.999
    assert capsule["threshold_met"] is True
    assert capsule["metric"]["metric_id"] == "pg_spine_verify_peak_rows"
    assert capsule["metric"]["workload_id"] == "verify1000-pinned-chain"
    assert capsule["experiment"]["receipt_facts"]["variant_values"] == {
        "stream": 1.0,
        "chunk64": 64.0,
        "chunk256": 256.0,
    }
    assert spine.verify_chain() is True


def test_decisions_exercise_all_three_types(tmp_path):
    rc, _capsule_path, spine = run_end_to_end(tmp_path)
    assert rc == 0
    decisions = [r for r in spine.iter() if r["kind"] == "RetainRegressKillDecision"]
    counts = {"retain": 0, "regress": 0, "kill": 0}
    for rec in decisions:
        counts[rec["payload"]["decision"]] += 1
    assert counts == {"retain": 1, "regress": 2, "kill": 1}
    rationales = [r["payload"]["rationale"] for r in decisions]
    assert any("beaten by stream" in r for r in rationales)
    assert any("below threshold" in r for r in rationales)
    assert any("audit killed" in r for r in rationales)


def test_comparison_report_ranks_stream_first(tmp_path):
    rc, _capsule_path, spine = run_end_to_end(tmp_path)
    assert rc == 0
    (report,) = [r["payload"] for r in spine.iter() if r["kind"] == "ComparisonReport"]
    assert report["metric_id"] == "pg_spine_verify_peak_rows"
    assert report["baseline_value"] == 1000.0
    by_rank = sorted(report["entries"], key=lambda e: e["rank"])
    assert [e["variant_id"] for e in by_rank] == [
        "stream",
        "chunk64",
        "chunk256",
        "no_commit_stream",
    ]
    assert [e["disposition"] for e in by_rank] == [
        "best",
        "beaten",
        "below_threshold",
        "not_measured",
    ]
    assert by_rank[0]["measured_value"] == 1.0
    assert by_rank[0]["improvement_ratio"] == 0.999
    assert report["winner_branch_id"] == by_rank[0]["branch_id"]


def test_proposal_pending_then_founder_ratification_event(tmp_path):
    rc, _capsule_path, spine = run_end_to_end(tmp_path)
    assert rc == 0
    (proposal,) = [r["payload"] for r in spine.iter() if r["kind"] == "ImprovementProposal"]
    assert proposal["ratification"] == "pending"  # sealed pending, never mutated
    assert proposal["authority_class"] == "C2"
    (ratification,) = [r for r in spine.iter() if r["kind"] == "RATIFICATION"]
    assert ratification["refs"]["proposal_id"] == proposal["id"]
    assert ratification["refs"]["approval_id"]  # founder approval reference
    assert ratification["refs"]["proposal_fingerprint"]
    (report,) = [r["payload"] for r in spine.iter() if r["kind"] == "ComparisonReport"]
    assert proposal["recommended_branch_id"] == report["winner_branch_id"]
    assert proposal["report_id"] == report["id"]


def test_failure_analyses_sealed_with_pinned_regression_refs(tmp_path):
    rc, _capsule_path, spine = run_end_to_end(tmp_path)
    assert rc == 0
    analyses = [r["payload"] for r in spine.iter() if r["kind"] == "FailureAnalysis"]
    assert len(analyses) == 2
    by_class = {a["failure_class"]: a for a in analyses}
    threshold = by_class["threshold_unmet"]
    assert threshold["regression_test_ref"] == CHUNK256_REGRESSION_TEST_REF
    assert threshold["experiment_spec_id"]  # measured, then failed
    # The regression ref points at a REAL pinned test in the suite.
    test_path = (
        CHUNK256_REGRESSION_TEST_REF.split("::")[0]
    )
    test_name = CHUNK256_REGRESSION_TEST_REF.split("::")[1]
    source = (run_fast_cycle.REPO_ROOT / test_path).read_text(encoding="utf-8")
    assert f"def {test_name}(" in source
    killed = by_class["audit_killed"]
    assert killed["experiment_spec_id"] == ""  # killed pre-experiment
    assert killed["regression_test_ref"] == ""  # allowed for audit_killed
    assert killed["evidence_refs"]  # the audit id is pinned as evidence


def test_verdict_line_byte_identical_across_runs(tmp_path, capsys):
    capsule = tmp_path / "capsule.json"  # same path both runs: the line is stable
    rc1 = run_fast_cycle.main(
        ["--capsule", str(capsule), "--spine-dir", str(tmp_path / "s1"),
         "--skip-test-rerun"]
    )
    line1 = capsys.readouterr().out
    rc2 = run_fast_cycle.main(
        ["--capsule", str(capsule), "--spine-dir", str(tmp_path / "s2"),
         "--skip-test-rerun"]
    )
    line2 = capsys.readouterr().out
    assert rc1 == rc2 == 0
    assert line1 == line2  # stable scalars only; byte-identical
    assert "verdict=baseline_beaten" in line1
    assert "improvement_ratio=0.999" in line1
    assert "decisions=retain:'stream',regress:'chunk64',regress:'chunk256',kill:'no_commit_stream'" in line1


# ------------------------------------------------------------------ hostile


def run_through_experiment(tmp_path):
    """Stages 1-5 of the WP-06 cycle against a fresh world (test driver)."""
    w = build_world_wp06(tmp_path)
    from kernel.evolution import EvolutionCycle

    cycle = EvolutionCycle(
        w["gate"], w["spine"], w["authority"],
        actor_id="uniimente-kernel", organ_id="evolution-organ", cycle_index=2,
    )
    drafts = run_fast_cycle.make_generator().generate(run_fast_cycle.make_space())
    tree = cycle.propose_tree("objective", "wp06", "rule", drafts)
    auditor = RuleBasedAuditor(SHIPPED_RULES)
    audits = {}
    for draft, findings in auditor.audit(drafts):
        audits[draft.id] = cycle.audit(draft.id, "test-auditor", findings)
    selected = cycle.select(tree, list(audits.values()))
    spec = ExperimentSpec(
        branch_id=selected.id,
        metric_id=bench.METRIC_ID,
        metric_unit=bench.METRIC_UNIT,
        baseline_value=bench.BASELINE_VALUE,
        threshold_improvement=bench.THRESHOLD_IMPROVEMENT,
        direction="decrease",
        harness_ref="scripts/wp06_bench.py",
        workload_id=bench.WORKLOAD_ID,
        pre_registered=True,
    )
    cycle.register_experiment(spec)
    from kernel.contracts.action import ActionIntent

    intent = ActionIntent(
        actor_id="uniimente-kernel",
        organ_id="evolution-organ",
        legal_principal="Uniimente Ltd",
        objective="WP-06 hostile-test matrix experiment",
        action_type="evolution_experiment",
        resource="kernel",
        target="bench://wp06/pg-spine-verify-peak-rows",
        payload={"experiment_spec_id": spec.id},
        consequence_class="C2",
        evidence_ids=[],
        expected_outcome=canonical_json(pinned_matrix_protocol()),
        rollback=None,
        expiry_minutes=30,
    )
    approval = w["authority"].issue_approval(w["gate"].fingerprint(intent))
    episode = cycle.run_experiment(intent, w["adapter"], approval)
    facts = run_fast_cycle.receipt_facts(w["spine"], episode)
    return w, cycle, drafts, selected, spec, facts


def test_verifier_rerun_disagreement_fails_closed(tmp_path):
    w, cycle, drafts, selected, spec, facts = run_through_experiment(tmp_path)
    before = w["spine"].next_seq
    # (a) The engine's candidate/baseline check: a lying re-run.
    with pytest.raises(CycleError, match="contradicts the adapter-attested"):
        cycle.verify(
            spec,
            lambda: (1000.0, 2.0),  # lying: stream was attested at 1.0
            verifier_id="verifier:hostile",
            tests_green=False,
        )
    assert w["spine"].next_seq == before  # nothing sealed
    # (b) The WP-06 per-variant cross-check: one tampered attested value.
    tampered = {**facts, "variant_values": {**facts["variant_values"], "chunk64": 65.0}}
    with pytest.raises(CycleError, match="contradicts the adapter-attested"):
        run_fast_cycle.remeasure_and_cross_check(tampered)
    # (c) A dropped variant in the attested matrix.
    dropped = {**facts, "variant_values": {"stream": 1.0, "chunk64": 64.0}}
    with pytest.raises(CycleError, match="variant set mismatch"):
        run_fast_cycle.remeasure_and_cross_check(dropped)
    # Honest re-run agrees and returns (baseline, candidate).
    assert run_fast_cycle.remeasure_and_cross_check(facts) == (1000.0, 1.0)


def test_ratification_without_founder_approval_seals_nothing(tmp_path):
    w, cycle, drafts, selected, spec, facts = run_through_experiment(tmp_path)
    from kernel.contracts.evolution import StrategyTree
    from kernel.evolution import build_proposal, build_report

    tree = StrategyTree(
        root_objective="hostile-test objective",
        horizon="wp06-test",
        selection_rule="test rule",
        branch_ids=[d.id for d in drafts],
        created_by="test",
    )
    branch_of = {d.id: d for d in drafts}
    report = build_report(
        cycle.loop_id, tree, branch_of,
        {v: float(x) for v, x in facts["variant_values"].items()},
        1000.0, 0.90, "decrease", metric_unit="rows",
    )
    proposal = build_proposal(report, cycle.loop_id, "adopt the winner")
    spine = w["spine"]
    before = spine.next_seq
    # (a) No approval at all -> CycleError, nothing appended, pending forever.
    with pytest.raises(CycleError, match="founder approval"):
        founder_ratify(
            spine, w["authority"], proposal, approval=None,
            actor_id="uniimente-kernel", organ_id="evolution-organ",
        )
    assert spine.next_seq == before
    # (b) An approval over the WRONG fingerprint -> ApprovalRefusal.
    wrong = w["authority"].issue_approval("0" * 64)
    with pytest.raises(errors.ApprovalRefusal):
        founder_ratify(
            spine, w["authority"], proposal, approval=wrong,
            actor_id="uniimente-kernel", organ_id="evolution-organ",
        )
    assert spine.next_seq == before
    assert [r for r in spine.iter() if r["kind"] == "RATIFICATION"] == []
    assert proposal.ratification == "pending"  # frozen: never self-ratifies
    # (c) A valid founder approval over the proposal fingerprint seals it.
    approval = w["authority"].issue_approval(content_hash(proposal))
    founder_ratify(
        spine, w["authority"], proposal, approval=approval,
        actor_id="uniimente-kernel", organ_id="evolution-organ",
    )
    (event,) = [r for r in spine.iter() if r["kind"] == "RATIFICATION"]
    assert event["refs"]["approval_id"] == approval.id
    # (d) Replay of the same approval is refused (one-use nonce).
    with pytest.raises(errors.ApprovalRefusal, match="replay"):
        founder_ratify(
            spine, w["authority"], proposal, approval=approval,
            actor_id="uniimente-kernel", organ_id="evolution-organ",
        )
    assert spine.verify_chain() is True
