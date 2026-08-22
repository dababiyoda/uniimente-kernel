"""Bridge C — Experiment-to-Reality, attacked rather than demonstrated.

The interesting tests here are the ones that would fail if the bridge were
ceremony: an experiment that grants itself authority, an executor that declares
its own success, and a refusal recorded as a negative result.
"""
import ast
import os

import pytest

from bridges import experiment_to_reality as bridge
from compiler.ucl_compiler import compile_constitution
from evolution.experiment import ExperimentSpec
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
    # `issue` returns the passport object; the bridge takes the id.
    return gate, passports, ledger, actor.passport_id


def make_spec(**kw):
    defaults = dict(
        decisive_unknown="does the narrowing actually narrow",
        hypothesis="min(requested, ceiling) is applied, not the request",
        prediction="granted budget equals the ceiling when the request exceeds it",
        metric="granted_budget_usd",
        baseline=0.0, threshold=1.0, direction="gte",
        workflow="experiment.run",
        required_capabilities=["experiment.run"],
        authority_requirements=["kernel.grant"],
        budget_usd=0.0, reversible=True,
        rollback_path="discard the sandbox run record",
        kill_condition="measured value exceeds 100",
        verification="cryptographic_receipt")
    defaults.update(kw)
    return ExperimentSpec(**defaults)


# --- the property the bridge exists to keep ---------------------------------

def test_an_experiment_cannot_grant_itself_a_capability_its_actor_lacks(stack):
    """The spec asks. The passport decides. Refused before a proposal is built."""
    gate, passports, ledger, actor = stack
    spec = make_spec(required_capabilities=["treasury.transfer"],
                     workflow="treasury.transfer")

    run = bridge.run(spec, gate=gate, passports=passports, actor=actor,
                     measure=lambda s: 1.0, ledger=ledger)

    assert run.completed is False
    assert run.halted_at is bridge.Halt.CAPABILITY_EXCEEDS_PASSPORT
    assert "treasury.transfer" in run.reason
    # And the gate was never asked to bless it.
    assert run.action_id is None


def test_an_experiment_cannot_budget_past_its_passport_ceiling(stack):
    gate, passports, ledger, actor = stack
    spec = make_spec(budget_usd=500.0)

    run = bridge.run(spec, gate=gate, passports=passports, actor=actor,
                     measure=lambda s: 1.0, ledger=ledger)

    assert run.halted_at is bridge.Halt.BUDGET_EXCEEDS_PASSPORT
    assert run.requested_budget_usd == 500.0
    assert run.granted_budget_usd is None  # nothing was granted at all


def test_the_granted_budget_is_the_smaller_of_the_two_never_the_request(stack):
    """min, not max. Asserted with numbers that would differ under either rule.

    The run is refused downstream for want of a budget authorization — which is
    the next test's subject. What is asserted here is the narrowing itself, read
    off the record the refusal still carries.
    """
    gate, passports, ledger, actor = stack
    spec = make_spec(budget_usd=2.0)  # ceiling is 5.0

    run = bridge.run(spec, gate=gate, passports=passports, actor=actor,
                     measure=lambda s: 3.0, ledger=ledger)

    assert run.granted_budget_usd == 2.0  # the request, because it is smaller
    assert run.requested_budget_usd == 2.0


def test_a_budgeted_experiment_cannot_fund_itself(stack):
    """No standing grant, no spend. The bridge does not mint one to get past this.

    This is the constraint that makes Bridge C honest: an experiment naming a
    budget is denied at the policy engine until someone with the authority to
    fund it has issued a budget authorization. Discovered by running the bridge,
    not by reading the doctrine — the first draft assumed a budgeted experiment
    would simply run.
    """
    gate, passports, ledger, actor = stack
    spec = make_spec(budget_usd=2.0)

    run = bridge.run(spec, gate=gate, passports=passports, actor=actor,
                     measure=lambda s: 3.0, ledger=ledger)

    assert run.halted_at is bridge.Halt.GATE_REFUSED
    assert run.resolved is None
    assert run.measured is None


# --- the ceremony-catching test ---------------------------------------------

def test_an_executor_reporting_success_below_threshold_does_not_resolve(stack):
    """The executor returns exactly what the gate expects — and still fails.

    This is the test that separates a measurement from a claim. The gate
    reconciles expected against observed and is satisfied; the experiment is
    not, because the metric sits below the threshold fixed before the run.
    """
    gate, passports, ledger, actor = stack
    spec = make_spec(baseline=0.0, threshold=10.0, direction="gte")

    run = bridge.run(spec, gate=gate, passports=passports, actor=actor,
                     measure=lambda s: 2.0, ledger=ledger)

    assert run.completed is True          # the action committed
    assert run.gate_state == "recorded"   # the gate is satisfied
    assert run.receipt_hash is not None   # there is a receipt
    assert run.measured == 2.0
    assert run.resolved is False          # and the experiment still failed


def test_a_measurement_over_the_threshold_resolves(stack):
    gate, passports, ledger, actor = stack
    spec = make_spec(baseline=0.0, threshold=10.0, direction="gte")

    run = bridge.run(spec, gate=gate, passports=passports, actor=actor,
                     measure=lambda s: 11.0, ledger=ledger)

    assert run.resolved is True
    assert run.measured == 11.0
    assert run.witness_id is not None


def test_direction_lte_is_honoured_and_not_silently_treated_as_gte(stack):
    """A latency-style experiment: lower is better. Same number, opposite verdict."""
    gate, passports, ledger, actor = stack
    spec = make_spec(baseline=100.0, threshold=50.0, direction="lte")

    beats = bridge.run(spec, gate=gate, passports=passports, actor=actor,
                       measure=lambda s: 20.0, ledger=ledger)
    misses = bridge.run(spec, gate=gate, passports=passports, actor=actor,
                        measure=lambda s: 80.0, ledger=ledger)

    assert beats.resolved is True
    assert misses.resolved is False


# --- refusal is not a negative result ---------------------------------------

def test_a_refused_gate_yields_no_measurement_rather_than_a_failure(stack):
    """`resolved is None`, not False. Absence of evidence, not evidence of absence."""
    gate, passports, ledger, actor = stack
    passports.revoke(actor, reason="testing identity lapse", revoker="alfonso")
    spec = make_spec()

    run = bridge.run(spec, gate=gate, passports=passports, actor=actor,
                     measure=lambda s: 999.0, ledger=ledger)

    assert run.completed is False
    assert run.halted_at is bridge.Halt.GATE_REFUSED
    assert run.resolved is None            # not False
    assert run.measured is None            # the instrument never ran
    assert run.produced_a_measurement is False


def test_the_instrument_never_runs_when_the_gate_refuses(stack):
    """Proved by a measure() that would raise if called."""
    gate, passports, ledger, actor = stack
    passports.revoke(actor, reason="testing identity lapse", revoker="alfonso")

    def exploding_instrument(_spec):
        raise AssertionError("the instrument ran despite a refused gate")

    run = bridge.run(make_spec(), gate=gate, passports=passports, actor=actor,
                     measure=exploding_instrument, ledger=ledger)

    assert run.halted_at is bridge.Halt.GATE_REFUSED


def test_an_uncompilable_experiment_never_reaches_the_gate(stack):
    """`ExperimentCompiler` refuses hopes; the bridge does not route around it."""
    gate, passports, ledger, actor = stack
    spec = make_spec(reversible=False)

    run = bridge.run(spec, gate=gate, passports=passports, actor=actor,
                     measure=lambda s: 1.0, ledger=ledger)

    assert run.halted_at is bridge.Halt.SPEC_DOES_NOT_COMPILE
    assert "reversible" in run.reason
    assert run.action_id is None


# --- claims about the outside world -----------------------------------------

def test_a_target_outside_the_sandbox_is_refused(stack):
    """The institution holds zero egress sites; any other target is a lie."""
    gate, passports, ledger, actor = stack

    run = bridge.run(make_spec(), gate=gate, passports=passports, actor=actor,
                     measure=lambda s: 1.0, ledger=ledger,
                     target="https://api.example.com/v1/publish")

    assert run.halted_at is bridge.Halt.TARGET_NOT_SANDBOXED
    assert run.action_id is None


def test_a_run_claims_nothing_about_the_outside_world(stack):
    gate, passports, ledger, actor = stack
    run = bridge.run(make_spec(), gate=gate, passports=passports, actor=actor,
                     measure=lambda s: 11.0, ledger=ledger)

    assert run.reality == bridge.SIMULATED
    # Nothing in the recorded events upgrades the reality axis.
    for record in ledger.by_type("event"):
        assert record.payload.get("reality", bridge.SIMULATED) == bridge.SIMULATED


def test_a_fired_kill_condition_is_recorded_beside_a_successful_commit(stack):
    """Success and a tripped kill condition are both facts. Neither hides the other."""
    gate, passports, ledger, actor = stack
    spec = make_spec(baseline=0.0, threshold=10.0, direction="gte")

    run = bridge.run(spec, gate=gate, passports=passports, actor=actor,
                     measure=lambda s: 150.0, ledger=ledger,
                     kill_check=lambda measured: measured > 100)

    assert run.resolved is True
    assert run.kill_condition_fired is True


# --- structural guards -------------------------------------------------------

def test_the_bridge_introduces_no_new_mechanism():
    """Every import is a module that existed and was tested before this file.

    The gate owns witness, receipt and reconciliation. If this file starts
    defining its own, the institution has quietly grown a second consequence
    path — the exact duplication one-authority-many-capabilities forbids.
    """
    path = os.path.join(ROOT, "bridges", "experiment_to_reality.py")
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    defined = {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
    assert defined <= {"ExperimentRun", "Halt"}, (
        f"bridge defines its own mechanism: {sorted(defined - {'ExperimentRun', 'Halt'})}"
    )


def test_the_bridge_never_mints_a_grant_or_widens_a_ceiling():
    """AST, not substring: the guard must not fire on an identifier that merely
    reads like the thing it forbids."""
    path = os.path.join(ROOT, "bridges", "experiment_to_reality.py")
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

    for forbidden in ("issue_single_action", "issue", "mark_used", "reserve"):
        assert forbidden not in called, f"bridge calls {forbidden} directly"

    # The narrowing must be a min. A max here would invert the whole property.
    assert "min" in called
    assert "max" not in called


def test_this_is_the_first_function_to_compose_an_experiment_with_the_gate():
    """The disconnection Bridge C ends, stated precisely enough to be falsifiable.

    Not "evolution/ was imported by nobody": `closure/kernel_registry.py` both
    imports `ExperimentSpec` and constructs `Proposal` objects. It does each in
    a *different* closure function and never turns one into the other. So the
    unit of the claim is the function, not the file — a per-file check passes
    vacuously here, which is how the first draft of this test was wrong.

    Nested functions are excluded from their parent's subtree, or an enclosing
    registration function would inherit both names from unrelated children and
    the test would find composers that do not exist.
    """
    def names_owned_by(fn):
        owned = set()
        for child in ast.iter_child_nodes(fn):
            for node in ast.walk(child):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    break
                if isinstance(node, ast.Name):
                    owned.add(node.id)
                elif isinstance(node, ast.Attribute):
                    owned.add(node.attr)
        for arg in fn.args.args + fn.args.kwonlyargs:
            if isinstance(arg.annotation, ast.Name):
                owned.add(arg.annotation.id)
        return owned

    composers: list[str] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames
                       if d not in {".git", "__pycache__", "tests", ".venv"}]
        for name in sorted(filenames):
            if not name.endswith(".py"):
                continue
            path = os.path.join(dirpath, name)
            with open(path, encoding="utf-8", errors="ignore") as fh:
                try:
                    tree = ast.parse(fh.read())
                except SyntaxError:
                    continue
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if {"ExperimentSpec", "Proposal"} <= names_owned_by(node):
                    composers.append(f"{os.path.relpath(path, ROOT)}::{node.name}")

    assert composers == ["bridges/experiment_to_reality.py::run"], (
        f"expected exactly one composer of experiment and proposal, found {composers}"
    )
