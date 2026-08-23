"""Phase 2 tests: First Evolution Cycle.

Includes one complete, manual, machine-recorded improvement cycle against
the real Consequence Gate: raise the external_contact evidence floor from
0.70 to 0.75, measured by replaying a corpus of proposals and counting
weak-evidence admissions. Verifier: formal proof (deterministic replay
invariant). Decision: RETAIN. Everything lands on the ledger.
"""
import os
import pytest

from compiler.ucl_compiler import compile_constitution
from evolution.capsule import (VerifierRecord, RetainRegressKill,
                               RetainRegressKillDecision, VERIFIER_LEVELS)
from evolution.experiment import ExperimentSpec, ExperimentCompiler
from evolution.loop import ClosureLoop, CycleRefused
from evolution.spider_web import SpiderWebAudit, EIGHT_SIDES, SUPER_NODES
from evolution.strategy_tree import StrategyTree, StrategyBranch, BRANCH_KINDS
from identity.machine_passport import PassportRegistry
from policy.consequence_gate import ConsequenceGate
from policy.engine import Proposal
from provenance.ledger import EvidenceLedger
from provenance.commit_witness import WitnessSigner

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def branch(kind, title, **kw):
    defaults = dict(
        governing_assumption="the corpus is representative of live traffic",
        mechanism="described in title",
        required_capabilities=["policy.evaluate"],
        cost_usd=0.0,
        founder_attention_minutes=10,
        time_to_proof_days=1,
        authority_requirements=["alfonso ratification to apply to production"],
        irreversible_downside="none; simulation only",
        expected_result="fewer weak admissions",
        strongest_counterargument="corpus too small to generalize",
        cheapest_falsification_test="replay corpus and count weak admissions",
        kill_condition="any good proposal newly refused",
    )
    defaults.update(kw)
    return StrategyBranch(kind=kind, title=title, **defaults)


def test_branch_requires_all_twelve_fields():
    b = branch("fastest_path", "x")
    b.kill_condition = ""
    problems = b.validate()
    assert any("kill_condition" in p for p in problems)


def test_tree_preserves_rejected_branches_with_revival_evidence():
    tree = StrategyTree(bottleneck="b", objective="o")
    b1 = tree.add(branch("fastest_path", "raise floor to 0.75"))
    b2 = tree.add(branch("do_nothing", "keep 0.70"))
    tree.select(b1.branch_id, decisive_unknown="u", reason="best value/attention")
    assert b2.rejected
    assert b2.revival_evidence == b2.cheapest_falsification_test
    assert "lost to" in b2.rejection_reason


def test_all_eleven_branch_kinds():
    assert len(BRANCH_KINDS) == 11
    tree = StrategyTree(bottleneck="b", objective="o")
    for k in BRANCH_KINDS:
        tree.add(branch(k, f"branch {k}"))
    assert all(tree.coverage().values())


def test_spider_web_eight_sides_and_super_nodes():
    audit = SpiderWebAudit(subject="floor raise")
    for s in EIGHT_SIDES:
        audit.set_side(s, True, "ok")
    audit.map_mechanism("policy engine", "eligibility")
    audit.map_mechanism("consequence gate", "default_routing")
    audit.map_mechanism("commit witness", "proof_and_truth")
    audit.map_mechanism("budget office", "cashflow_and_settlement")
    audit.map_mechanism("decorative dashboard", None)
    removed = audit.remove_decorative()
    assert removed == ["decorative dashboard"]
    for req in ("bounded_transaction", "real_beneficiary", "buyer_or_mandate_actor",
                "lawful_permission_path", "accepted_artifact", "external_consequence",
                "participant_benefit", "ninety_day_falsification_test",
                "fundable_reliability", "recovery_path", "kill_criteria"):
        audit.set_completeness(req, True)
    assert audit.verdict == "COMPLETE"


def test_spider_web_incomplete_when_side_missing():
    audit = SpiderWebAudit(subject="x")
    audit.set_side(EIGHT_SIDES[0], True, "ok")
    assert audit.verdict == "INCOMPLETE"
    assert len(audit.sides_failed) == 7


def test_experiment_must_be_reversible_and_falsifiable():
    spec = ExperimentSpec(
        decisive_unknown="u", hypothesis="h", prediction="p", metric="m",
        baseline=2.0, threshold=0.0, direction="lte", workflow="w",
        required_capabilities=["c"], authority_requirements=["a"], budget_usd=0.0,
        reversible=False, rollback_path="r", kill_condition="k",
        verification="formal_proof")
    with pytest.raises(ValueError):
        ExperimentCompiler().compile(spec)


def test_hypothesis_only_verifiers_cannot_retain():
    v = VerifierRecord(level="intrinsic_confidence", evidence="feels right", decided_by="model")
    d = RetainRegressKillDecision(decision=RetainRegressKill.RETAIN, reason="x",
                                  decided_by="model", verifier=v)
    problems = d.validate()
    assert any("may not authorize retain" in p for p in problems)


def test_verifier_levels_seven_ordered():
    assert VERIFIER_LEVELS[0] == "formal_proof"
    assert VERIFIER_LEVELS[-1] == "intrinsic_confidence"
    assert len(VERIFIER_LEVELS) == 7


# ---------------- the complete manual improvement cycle ----------------

GOOD_CONF = [0.95, 0.9, 0.85, 0.8]     # four legitimate proposals
WEAK_CONF = [0.72, 0.71]               # two weak-evidence proposals (floor 0.70 admits them)


def _replay(thresholds):
    """Replay the corpus through the real gate under candidate floors.
    Returns (weak_admissions, good_admissions)."""
    compiled = compile_constitution(ROOT)
    passports = PassportRegistry()
    ledger = EvidenceLedger(compiled.constitution_hash)
    gate = ConsequenceGate(compiled=compiled, passports=passports, ledger=ledger,
                           signer=WitnessSigner(env="development"),
                           evidence_thresholds=thresholds)
    actor = passports.issue(kind="agent", creator="alfonso", owner_organ="uniimente-kernel",
                            legal_principal="alfonso_lopez", declared_capabilities=["draft.publish"],
                            budget_ceiling_usd=5.0, consequence_class="external_contact")
    good = weak = 0
    for conf in GOOD_CONF + WEAK_CONF:
        p = Proposal(actor=actor.passport_id, legal_principal="alfonso_lopez",
                     action_class="draft.publish", objective="t", payload={"c": conf},
                     target="sandbox:outbox", consequence_class="external_contact",
                     evidence_confidence=conf, evidence_refs=["sha256:" + "a" * 64],
                     estimated_cost_usd=0.0, requested_capability="draft.publish",
                     expected_outcome="queued",
                     # Containment declared (CONTRADICTION-0003 Option B). True
                     # of this corpus: sandbox target, in-process inert
                     # executor. Declared here so the replay keeps measuring the
                     # floor rather than the new containment requirement.
                     context={"contained": True, "reversible": True,
                              "observable": True, "killable": True,
                              "proportionate": True})
        # An external_contact action needs a grant issued outside the run
        # (CONTRADICTION-0003's authorization fix). Issued here so the replay
        # keeps measuring the evidence FLOOR, which is its subject.
        g = gate.grants.issue_single_action(proposal=p,
                                            policy_version=gate.policy_version)
        rec = gate.run(p, executor=lambda pr: {"observed_outcome": "queued",
                                               "result_class": "positive"},
                       standing_grant=g)
        if rec.state == "recorded":
            if conf in WEAK_CONF:
                weak += 1
            else:
                good += 1
    return weak, good


def test_baseline_floor_admits_weak_evidence():
    weak, good = _replay(None)  # production floors: 0.70
    assert weak == 2 and good == 4


def test_complete_machine_recorded_improvement_cycle():
    ledger = EvidenceLedger(compile_constitution(ROOT).constitution_hash)
    loop = ClosureLoop(ledger)

    branches = [branch(k, f"{k} approach") for k in BRANCH_KINDS]
    selected = branches[0]  # fastest_path: raise the floor to 0.75

    audit = SpiderWebAudit(subject="raise external_contact floor to 0.75")
    for s in EIGHT_SIDES:
        audit.set_side(s, True, "assessed")
    audit.map_mechanism("policy engine floors", "eligibility")
    audit.map_mechanism("consequence gate", "default_routing")
    audit.map_mechanism("replay harness", "proof_and_truth")
    audit.map_mechanism("budget office", "cashflow_and_settlement")
    for req in ("bounded_transaction", "real_beneficiary", "buyer_or_mandate_actor",
                "lawful_permission_path", "accepted_artifact", "external_consequence",
                "participant_benefit", "ninety_day_falsification_test",
                "fundable_reliability", "recovery_path", "kill_criteria"):
        audit.set_completeness(req, True)

    spec = ExperimentSpec(
        decisive_unknown="does floor 0.75 eliminate weak admissions without refusing good proposals",
        hypothesis="floor 0.75 removes weak admissions and preserves all good admissions",
        prediction="weak admissions 2 -> 0; good admissions stay 4",
        metric="weak_admissions_in_replay",
        baseline=2.0, threshold=0.0, direction="lte",
        workflow="replay_corpus_under_candidate_floor",
        required_capabilities=["policy.evaluate", "gate.replay"],
        authority_requirements=["alfonso ratification to apply to production"],
        budget_usd=0.0, reversible=True,
        rollback_path="restore default EVIDENCE_THRESHOLDS",
        kill_condition="any good proposal newly refused",
        verification="formal_proof")

    def executor(spec):
        weak, good = _replay({"read_only": 0.0, "internal_write": 0.5, "external_contact": 0.75,
                              "financial": 0.8, "irreversible": 0.9})
        assert good == 4, "kill condition: a good proposal was newly refused"
        return float(weak), "positive" if weak == 0 else "negative"

    capsule = loop.run_cycle(
        bottleneck="external_contact evidence floor 0.70 admits weak-evidence effects",
        objective="zero weak-evidence external effects with zero new good refusals",
        branches=branches,
        selected_branch_id=selected.branch_id,
        decisive_unknown=spec.decisive_unknown,
        audit=audit,
        experiment=spec,
        executor=executor,
        verifier_level="formal_proof",
        verifier_evidence="deterministic replay: weak admissions 0/2, good admissions 4/4",
        notes="first manual machine-recorded improvement cycle (Phase 2)")

    assert capsule.decision["decision"] == "retain"
    assert capsule.beats_baseline is True
    assert capsule.measured_value == 0.0
    # everything is on the ledger: tree, audit, measurement, capsule, whole-body
    types = [r.payload.get("type") for r in ledger.by_type("event")]
    for t in ("evolution.tree_selected", "evolution.audit_complete",
              "evolution.experiment_measured", "evolution.whole_body"):
        assert t in types
    assert len(ledger.by_type("capsule")) == 1
    # rejected branches preserved with revival evidence
    rejected = [b for b in capsule.tree["branches"] if b["rejected"]]
    assert len(rejected) == 10
    assert all(b["revival_evidence"] for b in rejected)
    ok, _ = ledger.verify_chain()
    assert ok


def test_cycle_refuses_incomplete_audit():
    ledger = EvidenceLedger("sha256:" + "0" * 64)
    loop = ClosureLoop(ledger)
    audit = SpiderWebAudit(subject="x")
    audit.set_side(EIGHT_SIDES[0], True, "ok")  # seven sides missing
    spec = ExperimentSpec(
        decisive_unknown="u", hypothesis="h", prediction="p", metric="m",
        baseline=1.0, threshold=0.0, direction="lte", workflow="w",
        required_capabilities=["c"], authority_requirements=["a"], budget_usd=0.0,
        reversible=True, rollback_path="r", kill_condition="k",
        verification="formal_proof")
    b = branch("fastest_path", "x")
    with pytest.raises(CycleRefused):
        loop.run_cycle(bottleneck="b", objective="o",
                       branches=[b],
                       selected_branch_id=b.branch_id, decisive_unknown="u",
                       audit=audit, experiment=spec, executor=lambda s: (0.0, "positive"),
                       verifier_level="formal_proof", verifier_evidence="e")
