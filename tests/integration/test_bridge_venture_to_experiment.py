"""Bridge B — Venture-to-Experiment, attacked rather than demonstrated.

The load-bearing tests are the refusals: a tree that skipped branch kinds, an
audit that never cleared, a capping adversarial case, and an approval
requirement that is not allowed to become a grant.

The last test in this file is the one that matters most: B's output feeds C's
input, so A -> B -> C is one pathway rather than three adjacent ones.
"""
import ast
import os

import pytest

from bridges import venture_to_experiment as bridge
from evolution.spider_web import (COMPLETENESS_REQUIREMENTS, EIGHT_SIDES,
                                  SpiderWebAudit)
from evolution.strategy_tree import BRANCH_KINDS, StrategyBranch, StrategyTree
from provenance.ledger import EvidenceLedger

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def make_assessment(**kw):
    base = dict(
        assessment_id="11111111-1111-1111-1111-111111111111",
        verdict="go",
        adversarial_cases={"bull": "b", "bear": "r", "do_nothing": "d"},
        requires_human_approval=True,
        execution_authority=False)
    base.update(kw)
    return base


def make_branch(kind, **kw):
    base = dict(
        kind=kind, title=f"{kind} branch",
        governing_assumption="the narrowing holds under selection",
        mechanism="experiment.run",
        required_capabilities=["experiment.run"],
        cost_usd=0.0, founder_attention_minutes=10, time_to_proof_days=1,
        authority_requirements=["kernel.grant"],
        irreversible_downside="none",
        expected_result="the metric clears its threshold",
        strongest_counterargument="the metric may be measuring the wrong thing",
        cheapest_falsification_test="re-run against the frozen corpus",
        kill_condition="measured exceeds 100")
    base.update(kw)
    return StrategyBranch(**base)


def make_tree(kinds=BRANCH_KINDS, **branch_kw):
    tree = StrategyTree(bottleneck="no verified outcome exists",
                        objective="resolve one decisive unknown")
    for kind in kinds:
        tree.add(make_branch(kind, **branch_kw))
    return tree


def make_audit(complete=True):
    audit = SpiderWebAudit(subject="the selected branch")
    for side in EIGHT_SIDES:
        audit.set_side(side, complete, notes="probe")
    for req in COMPLETENESS_REQUIREMENTS:
        audit.set_completeness(req, complete)
    return audit


def run_ok(tree=None, audit=None, assessment=None, **kw):
    tree = tree if tree is not None else make_tree()
    audit = audit if audit is not None else make_audit()
    params = dict(decisive_unknown="does the pathway hold end to end",
                  selected_branch_id=tree.branches[0].branch_id,
                  selection_reason="cheapest falsification per hour of founder attention",
                  metric="verified_outcomes", baseline=0.0, threshold=1.0,
                  direction="gte", ledger=EvidenceLedger("bridge-b-test"))
    params.update(kw)
    return bridge.run(assessment if assessment is not None else make_assessment(),
                      tree, audit, **params)


# --- the happy path, stated so the refusals mean something ------------------

def test_a_complete_analysis_produces_a_compiled_experiment():
    run = run_ok()

    assert run.completed is True
    assert run.reached_an_experiment is True
    assert run.experiment.validate() == []
    assert run.audit_verdict == "COMPLETE"


# --- eleven branches, or no selection ---------------------------------------

def test_a_tree_missing_branch_kinds_may_not_select():
    """'We considered the alternatives' has to be a fact, not a sentence."""
    partial = make_tree(kinds=("fastest_path", "lowest_capital"))
    run = run_ok(tree=partial)

    assert run.halted_at is bridge.Halt.TREE_INCOMPLETE
    assert run.experiment is None


def test_the_missing_branch_kinds_are_named_not_counted():
    partial = make_tree(kinds=("fastest_path", "lowest_capital"))
    run = run_ok(tree=partial)

    assert "do_nothing" in run.missing_branch_kinds
    assert "do_nothing" in run.reason
    assert len(run.missing_branch_kinds) == len(BRANCH_KINDS) - 2


def test_do_nothing_is_a_mandated_branch_and_its_absence_alone_halts():
    """The one branch a build is most tempted to skip, isolated."""
    without = make_tree(kinds=tuple(k for k in BRANCH_KINDS if k != "do_nothing"))
    run = run_ok(tree=without)

    assert run.halted_at is bridge.Halt.TREE_INCOMPLETE
    assert run.missing_branch_kinds == ("do_nothing",)


# --- the audit has to gate something -----------------------------------------

def test_an_incomplete_audit_blocks_the_experiment():
    run = run_ok(audit=make_audit(complete=False))

    assert run.halted_at is bridge.Halt.AUDIT_INCOMPLETE
    assert run.audit_verdict == "INCOMPLETE"
    assert run.experiment is None
    # and it names what failed rather than reporting a bare verdict
    assert len(run.sides_failed) == len(EIGHT_SIDES)
    assert len(run.missing_completeness) == len(COMPLETENESS_REQUIREMENTS)


def test_a_single_failed_side_is_enough_to_block():
    audit = make_audit()
    audit.set_side("proof_truth_reputation", False, notes="no external verifier exists")
    run = run_ok(audit=audit)

    assert run.halted_at is bridge.Halt.AUDIT_INCOMPLETE
    assert run.sides_failed == ("proof_truth_reputation",)


def test_a_decorative_mechanism_blocks_even_with_every_side_passing():
    """A mechanism mapped to no governing super-node is decoration."""
    audit = make_audit()
    audit.map_mechanism("a dashboard nobody acts on", None)
    run = run_ok(audit=audit)

    assert run.halted_at is bridge.Halt.AUDIT_INCOMPLETE
    assert run.audit_verdict == "DECORATIVE_MECHANISMS_PRESENT"


# --- preservation ------------------------------------------------------------

def test_losing_branches_are_preserved_with_the_evidence_that_would_revive_them():
    """Final Build Order section 12, enforced rather than quoted."""
    run = run_ok()

    assert len(run.rejected_branches) == len(BRANCH_KINDS) - 1
    for branch in run.rejected_branches:
        assert branch["rejected"] is True
        assert branch["rejection_reason"]
        assert branch["revival_evidence"] == "re-run against the frozen corpus"
    # nothing was removed
    assert run.selected_branch_id not in [b["branch_id"] for b in run.rejected_branches]


# --- the assessment's own limits survive -------------------------------------

def test_a_no_go_assessment_never_reaches_a_strategy_tree():
    run = run_ok(assessment=make_assessment(verdict="no_go"))

    assert run.halted_at is bridge.Halt.ASSESSMENT_REFUSES_TO_PROCEED
    assert run.event_ids == ()


def test_a_capping_adversarial_case_stops_the_venture():
    """Severe, unresolved, against. Building on top of it measures the wrong thing."""
    capped = make_assessment(adversarial_cases={
        "bull": "b", "bear": "r", "do_nothing": "d",
        "capping_cases": ["fraud_manipulation"]})
    run = run_ok(assessment=capped)

    assert run.halted_at is bridge.Halt.CAPPING_CASE_UNRESOLVED
    assert "fraud_manipulation" in run.reason


def test_the_approval_requirement_is_not_a_grant_and_never_becomes_one():
    run = run_ok()

    assert run.approval.granted is False
    assert run.approval.requires_human_approval is True
    assert run.approval.execution_authority is False


def test_the_bridge_cannot_soften_the_assessments_two_constants():
    """Carried forward verbatim, not recomputed.

    An assessment claiming it needs no human approval is a malformed assessment,
    and the requirement must reflect what it said rather than what would be
    convenient.
    """
    softened = make_assessment(requires_human_approval=False, execution_authority=True)
    run = run_ok(assessment=softened)

    assert run.approval.requires_human_approval is False
    assert run.approval.execution_authority is True
    # The bridge reports what it was given; it does not quietly re-assert True.


# --- reversibility is read, not assumed --------------------------------------

def test_a_branch_with_an_irreversible_downside_produces_no_experiment():
    """The compiler refuses irreversible experiments; the bridge must feed it
    the branch's real answer rather than hardcoding reversible=True."""
    tree = make_tree(irreversible_downside="the customer relationship is burned")
    run = run_ok(tree=tree)

    assert run.halted_at is bridge.Halt.EXPERIMENT_DOES_NOT_COMPILE
    assert "reversible" in run.reason


# --- the chain claim ---------------------------------------------------------

def test_bridge_b_output_is_accepted_by_bridge_c_unmodified():
    """A -> B -> C is one pathway, not three adjacent ones.

    This is the test that makes the chain a fact. If B's ExperimentSpec needed
    any adjustment before C would take it, the two bridges would be adjacent
    rather than joined, and this would fail.
    """
    from bridges import experiment_to_reality as bridge_c
    from compiler.ucl_compiler import compile_constitution
    from identity.machine_passport import PassportRegistry
    from policy.consequence_gate import ConsequenceGate
    from provenance.commit_witness import WitnessSigner

    b_run = run_ok()
    assert b_run.completed is True

    compiled = compile_constitution(ROOT)
    passports = PassportRegistry()
    ledger = EvidenceLedger(compiled.constitution_hash)
    gate = ConsequenceGate(compiled=compiled, passports=passports, ledger=ledger,
                           signer=WitnessSigner(env="development"))
    actor = passports.issue(
        kind="agent", creator="alfonso", owner_organ="uniimente-kernel",
        legal_principal="alfonso_lopez",
        declared_capabilities=list(b_run.experiment.required_capabilities),
        budget_ceiling_usd=5.0, consequence_class="internal_write")

    c_run = bridge_c.run(b_run.experiment, gate=gate, passports=passports,
                         actor=actor.passport_id, measure=lambda s: 2.0, ledger=ledger)

    assert c_run.completed is True
    assert c_run.resolved is True          # threshold 1.0, measured 2.0
    assert c_run.receipt_hash is not None
    assert c_run.reality == bridge_c.SIMULATED


def test_the_chain_still_refuses_to_spend_without_a_grant():
    """B says a human must approve. C is where that refusal becomes operative."""
    from bridges import experiment_to_reality as bridge_c
    from compiler.ucl_compiler import compile_constitution
    from identity.machine_passport import PassportRegistry
    from policy.consequence_gate import ConsequenceGate
    from provenance.commit_witness import WitnessSigner

    b_run = run_ok(tree=make_tree(cost_usd=2.0))
    assert b_run.approval.budget_usd == 2.0
    assert b_run.approval.granted is False

    compiled = compile_constitution(ROOT)
    passports = PassportRegistry()
    ledger = EvidenceLedger(compiled.constitution_hash)
    gate = ConsequenceGate(compiled=compiled, passports=passports, ledger=ledger,
                           signer=WitnessSigner(env="development"))
    actor = passports.issue(
        kind="agent", creator="alfonso", owner_organ="uniimente-kernel",
        legal_principal="alfonso_lopez", declared_capabilities=["experiment.run"],
        budget_ceiling_usd=5.0, consequence_class="internal_write")

    c_run = bridge_c.run(b_run.experiment, gate=gate, passports=passports,
                         actor=actor.passport_id, measure=lambda s: 2.0, ledger=ledger)

    assert c_run.halted_at is bridge_c.Halt.GATE_REFUSED
    assert c_run.resolved is None


# --- structural guards -------------------------------------------------------

def test_the_bridge_introduces_no_new_mechanism():
    """Strategy, audit and compiler are imported, never reimplemented."""
    path = os.path.join(ROOT, "bridges", "venture_to_experiment.py")
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    defined = {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
    assert defined <= {"VentureRun", "Halt", "ApprovalRequirement"}, (
        f"bridge defines its own mechanism: "
        f"{sorted(defined - {'VentureRun', 'Halt', 'ApprovalRequirement'})}"
    )


def test_the_bridge_never_issues_a_grant():
    """AST over calls, not substrings: a guard that fires on an identifier
    merely reading like the forbidden thing is not a guard."""
    path = os.path.join(ROOT, "bridges", "venture_to_experiment.py")
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Attribute):
                called.add(fn.attr)
            elif isinstance(fn, ast.Name):
                called.add(fn.id)

    for forbidden in ("issue_single_action", "issue", "reserve", "mark_used", "run"):
        assert forbidden not in called, f"bridge calls {forbidden}"


def test_the_approval_requirement_has_no_way_to_grant_itself():
    """`granted` is a frozen field defaulting to False; there is no setter and
    no code path that writes True. Asserted structurally so a later edit that
    adds one fails here rather than in production."""
    path = os.path.join(ROOT, "bridges", "venture_to_experiment.py")
    with open(path, encoding="utf-8") as fh:
        source = fh.read()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == "granted":
            raise AssertionError("something passes granted= explicitly")
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Attribute) and target.attr == "granted":
                    raise AssertionError("something assigns to .granted")

    with pytest.raises(Exception):
        run_ok().approval.granted = True   # frozen dataclass
