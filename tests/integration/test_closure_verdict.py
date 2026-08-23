"""The whole-body verdict on the bridge chain — asserted against its author.

The load-bearing test in this file is the one that says the chain is FALSELY
CLOSED. A build that could only demonstrate its own success would have no way
to notice this, which is exactly the failure the controller exists to name.
"""
import ast
import os

import pytest

from bridges import closure_verdict
from bridges import experiment_to_reality as bridge_c
from bridges import reality_to_learning as bridge_d
from compiler.ucl_compiler import compile_constitution
from evolution.experiment import ExperimentSpec
from identity.machine_passport import PassportRegistry
from policy.consequence_gate import ConsequenceGate
from provenance.commit_witness import WitnessSigner
from provenance.ledger import EvidenceLedger

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUTSIDE = "spiffe://external/customer/acme-corp"


def spec():
    return ExperimentSpec(
        decisive_unknown="is the chain externally closed",
        hypothesis="it is not",
        prediction="the sandbox run records a value",
        metric="verified_outcomes", baseline=0.0, threshold=1.0, direction="gte",
        workflow="experiment.run", required_capabilities=["experiment.run"],
        authority_requirements=["kernel.grant"], budget_usd=0.0, reversible=True,
        rollback_path="discard the sandbox record",
        kill_condition="measured exceeds 100",
        verification="cryptographic_receipt")


@pytest.fixture
def ran():
    """A ledger holding a real, committed, receipted chain traversal."""
    compiled = compile_constitution(ROOT)
    passports = PassportRegistry()
    ledger = EvidenceLedger(compiled.constitution_hash)
    gate = ConsequenceGate(compiled=compiled, passports=passports, ledger=ledger,
                           signer=WitnessSigner(env="development"))
    actor = passports.issue(
        kind="agent", creator="alfonso", owner_organ="uniimente-kernel",
        legal_principal="alfonso_lopez", declared_capabilities=["experiment.run"],
        budget_ceiling_usd=5.0, consequence_class="internal_write")
    run = bridge_c.run(spec(), gate=gate, passports=passports,
                       actor=actor.passport_id, measure=lambda s: 2.0, ledger=ledger)
    assert run.completed
    return ledger, run.action_id


# --- the verdict against this session's own work -----------------------------

def test_the_bridge_chain_is_falsely_closed_not_closed(ran):
    """The chain ran end to end and the institution still calls it a failure.

    Internal metrics moved — witnesses, receipts, outcomes, events. The external
    consequence is flat, because there is no egress and no counterparty. That is
    the controller's definition of FALSELY_CLOSED, and it is the honest verdict
    on everything built this session.
    """
    ledger, _ = ran

    verdict = closure_verdict.assess(ledger)

    assert verdict["overall"] == "FALSELY_CLOSED"
    assert verdict["falsely_closed"], "the chain must not report itself closed"


def test_the_controller_demands_regression_of_this_work(ran):
    """Not a warning — the required actions name what should happen."""
    ledger, _ = ran

    verdict = closure_verdict.assess(ledger)

    assert "investigate_false_closure" in verdict["required_actions"]
    assert "regress_change" in verdict["required_actions"]


def test_the_reality_loop_is_among_the_falsely_closed(ran):
    ledger, _ = ran

    verdict = closure_verdict.assess(ledger)

    assert "reality" in verdict["falsely_closed"]
    assert verdict["verdicts"]["reality"] == "FALSELY_CLOSED"


# --- it corrects itself, without anyone editing it ---------------------------

def test_a_real_external_observation_closes_the_loops_with_no_code_change(ran):
    """The same function, the same file, a different ledger — a different verdict.

    This is what makes the pessimism above honest rather than performative: the
    verdict is derived, so it moves the moment an outside party speaks and not
    because someone decided the work was good enough.
    """
    ledger, action_id = ran
    before = closure_verdict.assess(ledger)

    d = bridge_d.run({"action_id": action_id, "observer": OUTSIDE,
                      "external_observation": spec().prediction,
                      "result_class": "positive",
                      "validation_status": bridge_d.EXTERNALLY_VERIFIED},
                     ledger=ledger)
    assert d.clean_verified_outcomes == 1

    after = closure_verdict.assess(ledger)

    assert before["overall"] == "FALSELY_CLOSED"
    assert after["overall"] == "CLOSED"
    assert after["falsely_closed"] == []


def test_a_self_attested_observation_does_not_close_anything(ran):
    """The obvious cheat, refused upstream.

    An actor verifying itself is rejected by Bridge D, so the SBM never moves
    and the verdict never improves. The two guards compose.
    """
    ledger, action_id = ran
    witness = ledger.by_type("witness")[0].payload

    d = bridge_d.run({"action_id": action_id, "observer": witness["actor"],
                      "external_observation": spec().prediction,
                      "result_class": "positive",
                      "validation_status": bridge_d.EXTERNALLY_VERIFIED},
                     ledger=ledger)

    assert d.halted_at is bridge_d.Halt.SELF_ATTESTATION
    assert closure_verdict.assess(ledger)["overall"] == "FALSELY_CLOSED"


def test_an_empty_ledger_is_open_rather_than_falsely_closed():
    """Nothing ran, so nothing is falsely closed. OPEN and FALSELY_CLOSED are
    different failures and the module must not conflate them."""
    verdict = closure_verdict.assess(EvidenceLedger("sha256:" + "0" * 64))

    assert verdict["overall"] != "FALSELY_CLOSED"
    assert verdict["falsely_closed"] == []
    assert "reality" in verdict["open_loops"]


# --- no caller may assert an external consequence ----------------------------

def test_assess_has_no_parameter_that_could_claim_external_success():
    """Structural, because this is the whole design.

    `LoopEvidence` takes two booleans. If `assess` accepted either from a
    caller, the builder would be grading their own work — and the failure this
    module exists to catch is precisely a builder's optimism.
    """
    path = os.path.join(ROOT, "bridges", "closure_verdict.py")
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name == "assess")
    params = ([a.arg for a in fn.args.args]
              + [a.arg for a in fn.args.kwonlyargs])

    assert params == ["ledger", "change_id"]
    for banned in ("external_ok", "internal_ok", "external", "verified", "closed"):
        assert banned not in params


def test_external_success_has_exactly_one_source():
    """`external_ok` must be fed from the SBM and nothing else.

    A second source would be a second truth about reality, which is the
    duplication of authority the constitution forbids in its most consequential
    place.
    """
    path = os.path.join(ROOT, "bridges", "closure_verdict.py")
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name == "assess")

    # Every external_ok= keyword must be the same single Name.
    sources = {n.value.id for n in ast.walk(fn)
               if isinstance(n, ast.keyword) and n.arg == "external_ok"
               and isinstance(n.value, ast.Name)}
    assert sources == {"external"}, f"external_ok fed from {sources}"

    # And that name is assigned exactly once, from clean_verified_outcomes.
    assigns = [n for n in ast.walk(fn)
               if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == "external" for t in n.targets)]
    assert len(assigns) == 1
    calls = [n.func.id for n in ast.walk(assigns[0])
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
    assert calls == ["clean_verified_outcomes"]


def test_the_module_claims_only_loops_the_chain_touches():
    """Claiming loops the bridges never touch would be its own inflation —
    a component reporting on commercial or capital closure it never reached."""
    from closure.whole_body import Loop

    assert closure_verdict.BRIDGE_LOOPS < set(Loop)
    for never_touched in (Loop.COMMERCIAL, Loop.CAPITAL, Loop.DISTRIBUTION,
                          Loop.AUTONOMY, Loop.CONTINUITY, Loop.REGENERATIVE):
        assert never_touched not in closure_verdict.BRIDGE_LOOPS
