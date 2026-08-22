"""Bridge E — the evolution loop, governed, without a second evolution loop.

The tests that matter: the adapter really does drive the *existing*
`ClosureLoop` unchanged, and a refused gate never becomes a RETAIN.
"""
import ast
import os

import pytest

from bridges import governed_evolution
from compiler.ucl_compiler import compile_constitution
from evolution.capsule import RetainRegressKill
from evolution.experiment import ExperimentSpec
from evolution.loop import ClosureLoop, CycleRefused
from evolution.spider_web import (COMPLETENESS_REQUIREMENTS, EIGHT_SIDES,
                                  SpiderWebAudit)
from evolution.strategy_tree import BRANCH_KINDS, StrategyBranch
from identity.machine_passport import PassportRegistry
from policy.consequence_gate import ConsequenceGate
from provenance.commit_witness import WitnessSigner
from provenance.ledger import EvidenceLedger

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def stack():
    compiled = compile_constitution(ROOT)
    passports = PassportRegistry()
    ledger = EvidenceLedger(compiled.constitution_hash)
    gate = ConsequenceGate(compiled=compiled, passports=passports, ledger=ledger,
                           signer=WitnessSigner(env="development"))
    actor = passports.issue(
        kind="agent", creator="alfonso", owner_organ="uniimente-kernel",
        legal_principal="alfonso_lopez", declared_capabilities=["experiment.run"],
        budget_ceiling_usd=5.0, consequence_class="internal_write")
    return gate, passports, ledger, actor.passport_id


def branches():
    return [StrategyBranch(
        kind=kind, title=f"{kind} branch",
        governing_assumption="the loop can be governed without being replaced",
        mechanism="experiment.run", required_capabilities=["experiment.run"],
        cost_usd=0.0, founder_attention_minutes=5, time_to_proof_days=1,
        authority_requirements=["kernel.grant"], irreversible_downside="none",
        expected_result="the metric clears its threshold",
        strongest_counterargument="the wrapper could hide a refusal",
        cheapest_falsification_test="refuse at the gate and check the verdict",
        kill_condition="measured exceeds 100") for kind in BRANCH_KINDS]


def audit():
    a = SpiderWebAudit(subject="governed evolution")
    for side in EIGHT_SIDES:
        a.set_side(side, True, notes="probe")
    for req in COMPLETENESS_REQUIREMENTS:
        a.set_completeness(req, True)
    return a


def spec():
    return ExperimentSpec(
        decisive_unknown="can an existing cycle be governed by one argument",
        hypothesis="yes, via an executor that crosses the gate",
        prediction="the sandbox run records a value",
        metric="verified_outcomes", baseline=0.0, threshold=1.0, direction="gte",
        workflow="experiment.run", required_capabilities=["experiment.run"],
        authority_requirements=["kernel.grant"], budget_usd=0.0, reversible=True,
        rollback_path="discard the sandbox record", kill_condition="measured exceeds 100",
        verification="cryptographic_receipt")


def run_cycle(stack, *, measure, **kw):
    gate, passports, ledger, actor = stack
    bs = branches()
    loop = ClosureLoop(ledger)
    executor = governed_evolution.gate_mediated(
        gate=gate, passports=passports, actor=actor, measure=measure,
        ledger=ledger, **kw)
    return loop.run_cycle(
        bottleneck="the evolution loop does not cross its own gate",
        objective="govern it without replacing it",
        branches=bs, selected_branch_id=bs[0].branch_id,
        decisive_unknown="can an existing cycle be governed by one argument",
        audit=audit(), experiment=spec(), executor=executor,
        verifier_level="cryptographic_receipt",
        verifier_evidence="the gate's own receipt binds the measurement")


# --- the adapter drives the existing loop, unchanged -------------------------

def test_the_existing_closure_loop_runs_governed_and_retains(stack):
    """`ClosureLoop` is not modified, subclassed or reimplemented — it is handed
    one different argument and produces its own capsule."""
    capsule = run_cycle(stack, measure=lambda s: 2.0)

    assert capsule.decision["decision"] == RetainRegressKill.RETAIN
    assert capsule.verifier["level"] == "cryptographic_receipt"


def test_the_measurement_that_reached_the_loop_is_the_one_the_gate_receipted(stack):
    """Not a number the wrapper invented alongside the action."""
    gate, passports, ledger, actor = stack
    capsule = run_cycle(stack, measure=lambda s: 2.0)

    measured_events = [r.payload for r in ledger.by_type("event")
                       if r.payload.get("type") == "evolution.experiment_measured"]
    assert measured_events[-1]["measured"] == 2.0
    assert len(ledger.by_type("receipt")) == 1
    assert capsule.decision["decision"] == RetainRegressKill.RETAIN


def test_a_measurement_below_threshold_regresses_rather_than_retains(stack):
    capsule = run_cycle(stack, measure=lambda s: 0.5)

    assert capsule.decision["decision"] == RetainRegressKill.REGRESS


# --- the property this adapter exists for ------------------------------------

def test_a_refused_gate_never_becomes_a_retain(stack):
    """The sharpest failure this prevents.

    `run_cycle` compares whatever number it receives against the baseline and
    can emit RETAIN — a promotion decision. An executor returning a number on
    refusal would let a refused action produce a verdict computed from a
    measurement nobody took.
    """
    gate, passports, ledger, actor = stack
    passports.revoke(actor, reason="testing identity lapse", revoker="alfonso")

    with pytest.raises(CycleRefused) as excinfo:
        run_cycle(stack, measure=lambda s: 999.0)

    assert "gate refused" in str(excinfo.value)
    assert "no retain, regress or kill" in str(excinfo.value).lower()
    # and no capsule was written claiming a decision
    assert ledger.by_type("capsule") == []


def test_the_instrument_never_runs_when_the_gate_refuses(stack):
    gate, passports, ledger, actor = stack
    passports.revoke(actor, reason="testing identity lapse", revoker="alfonso")

    def exploding(_spec):
        raise AssertionError("the instrument ran despite a refused gate")

    with pytest.raises(CycleRefused):
        run_cycle(stack, measure=exploding)


def test_a_budgeted_cycle_refuses_rather_than_spending_unauthorised(stack):
    """The evolution loop inherits Bridge C's funding refusal for free."""
    gate, passports, ledger, actor = stack
    bs = branches()
    loop = ClosureLoop(ledger)
    costly = spec()
    costly.budget_usd = 2.0
    executor = governed_evolution.gate_mediated(
        gate=gate, passports=passports, actor=actor,
        measure=lambda s: 5.0, ledger=ledger)

    with pytest.raises(CycleRefused):
        loop.run_cycle(
            bottleneck="b", objective="o", branches=bs,
            selected_branch_id=bs[0].branch_id, decisive_unknown="u",
            audit=audit(), experiment=costly, executor=executor,
            verifier_level="cryptographic_receipt", verifier_evidence="e")


# --- what was found, kept true ------------------------------------------------

def test_the_evolution_loop_still_does_not_reference_the_gate_itself():
    """The finding, pinned. `evolution/` is untouched: governance arrives by
    composition at the call site, not by editing the loop.

    If someone later wires the gate into `evolution/loop.py` directly, this
    fails — and it should, because that is a second, unadapted consequence path
    and the choice deserves to be made deliberately rather than discovered.
    """
    for name in ("loop.py", "auto_cycle.py"):
        with open(os.path.join(ROOT, "evolution", name), encoding="utf-8") as fh:
            source = fh.read()
        assert "ConsequenceGate" not in source
        assert "consequence_gate" not in source


def test_the_unmediated_path_is_preserved(stack):
    """Section 2: the old behaviour is not deleted, and still works.

    A bare executor remains valid. That is the point of an adapter — the
    ungoverned path stays available and is now a visible choice rather than the
    only option.
    """
    gate, passports, ledger, actor = stack
    bs = branches()
    loop = ClosureLoop(ledger)

    capsule = loop.run_cycle(
        bottleneck="b", objective="o", branches=bs,
        selected_branch_id=bs[0].branch_id, decisive_unknown="u",
        audit=audit(), experiment=spec(),
        executor=lambda s: (2.0, "benefit"),
        verifier_level="cryptographic_receipt", verifier_evidence="e")

    assert capsule.decision["decision"] == RetainRegressKill.RETAIN
    assert ledger.by_type("receipt") == []   # ungoverned: no receipt at all


# --- structural guards --------------------------------------------------------

def test_the_adapter_defines_no_mechanism_of_its_own():
    """An adapter that grew a class would be a second loop in disguise."""
    path = os.path.join(ROOT, "bridges", "governed_evolution.py")
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    assert [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)] == []
    top_level = [n.name for n in tree.body
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    assert top_level == ["gate_mediated"]


def test_the_adapter_cannot_report_harm_on_a_refusal():
    """KILL is a finding; a refusal is an absence of evidence.

    Asserted structurally: `HARM` must never be the value returned on the
    refusal path, which is enforced by that path raising instead of returning.
    """
    path = os.path.join(ROOT, "bridges", "governed_evolution.py")
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "executor")
    returns = [n for n in ast.walk(fn) if isinstance(n, ast.Return)]
    assert len(returns) == 1     # exactly one way out that is not an exception
    raises = [n for n in ast.walk(fn) if isinstance(n, ast.Raise)]
    assert len(raises) == 1
