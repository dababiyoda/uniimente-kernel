"""Bridge D — Reality-to-Learning, attacked rather than demonstrated.

The tests that matter: an actor cannot verify itself, the Single Bottleneck
Metric refuses to move on internal evidence, and the calibration gap this
bridge exposed stays visible until someone with the authority closes it.
"""
import ast
import os

import pytest

from bridges import reality_to_learning as bridge
from compiler.ucl_compiler import compile_constitution
from evolution.experiment import ExperimentSpec
from identity.machine_passport import PassportRegistry
from policy.consequence_gate import ConsequenceGate
from provenance.commit_witness import CommitWitness, WitnessSigner
from provenance.ledger import EvidenceLedger

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUTSIDE = "spiffe://external/customer/acme-corp"


@pytest.fixture
def committed():
    """A real committed action, produced by running Bridge C. Not a fixture dict.

    The point of Bridge D is to judge actions the institution actually took, so
    the thing under test has to be one.
    """
    from bridges import experiment_to_reality as bridge_c

    compiled = compile_constitution(ROOT)
    passports = PassportRegistry()
    ledger = EvidenceLedger(compiled.constitution_hash)
    gate = ConsequenceGate(compiled=compiled, passports=passports, ledger=ledger,
                           signer=WitnessSigner(env="development"))
    actor = passports.issue(
        kind="agent", creator="alfonso", owner_organ="uniimente-kernel",
        legal_principal="alfonso_lopez", declared_capabilities=["experiment.run"],
        budget_ceiling_usd=5.0, consequence_class="internal_write")
    spec = ExperimentSpec(
        decisive_unknown="does an outside party ever speak",
        hypothesis="it does not, yet", prediction="the sandbox run records a value",
        metric="verified_outcomes", baseline=0.0, threshold=1.0, direction="gte",
        workflow="experiment.run", required_capabilities=["experiment.run"],
        authority_requirements=["kernel.grant"], budget_usd=0.0, reversible=True,
        rollback_path="discard the sandbox record", kill_condition="measured exceeds 100",
        verification="cryptographic_receipt")
    run = bridge_c.run(spec, gate=gate, passports=passports,
                       actor=actor.passport_id, measure=lambda s: 2.0, ledger=ledger)
    assert run.completed
    return ledger, run.action_id, actor.passport_id


def observation(action_id, **kw):
    base = dict(action_id=action_id, observer=OUTSIDE,
                external_observation="the sandbox run records a value",
                result_class="positive",
                validation_status=bridge.EXTERNALLY_VERIFIED)
    base.update(kw)
    return base


# --- nothing verifies itself -------------------------------------------------

def test_an_actor_cannot_verify_its_own_action(committed):
    """The single most important refusal in this file.

    Without it, any component could write `externally_verified` about itself and
    the entire evidence ladder would become self-report under a stronger word.
    """
    ledger, action_id, actor = committed

    run = bridge.run(observation(action_id, observer=actor), ledger=ledger)

    assert run.completed is False
    assert run.halted_at is bridge.Halt.SELF_ATTESTATION
    assert run.validation is None


def test_the_actor_is_read_from_the_witness_not_from_the_observation(committed):
    """An observation claiming a different actor cannot dodge the self-check."""
    ledger, action_id, actor = committed

    # The observation names itself as the observer AND lies about who acted.
    forged = observation(action_id, observer=actor)
    forged["actor"] = "spiffe://external/somebody-else"

    run = bridge.run(forged, ledger=ledger)

    assert run.halted_at is bridge.Halt.SELF_ATTESTATION


def test_an_unattributed_observation_is_a_rumour(committed):
    ledger, action_id, _ = committed

    for missing in ("", "   ", None):
        run = bridge.run(observation(action_id, observer=missing), ledger=ledger)
        assert run.halted_at is bridge.Halt.OBSERVER_NOT_ATTRIBUTED


def test_an_observation_about_no_witnessed_action_is_not_evidence(committed):
    ledger, _, _ = committed

    run = bridge.run(observation("no-such-action-id"), ledger=ledger)

    assert run.halted_at is bridge.Halt.NO_SUCH_ACTION


def test_an_unknown_validation_status_is_refused(committed):
    ledger, action_id, _ = committed

    run = bridge.run(observation(action_id, validation_status="probably_fine"),
                     ledger=ledger)

    assert run.halted_at is bridge.Halt.UNKNOWN_VALIDATION_STATUS


# --- the Single Bottleneck Metric --------------------------------------------

def test_the_sbm_is_zero_before_any_external_observer_speaks(committed):
    """Read from the ledger, not asserted. Bridge C committed and receipted an
    action; the metric still reads 0 because nothing outside said so."""
    ledger, _, _ = committed

    assert bridge.clean_verified_outcomes(ledger) == 0
    assert len(ledger.by_type("outcome")) >= 1   # an outcome exists; it just isn't clean


def test_an_internally_observed_outcome_never_counts(committed):
    ledger, action_id, _ = committed

    run = bridge.run(observation(action_id,
                                 validation_status=bridge.INTERNALLY_OBSERVED),
                     ledger=ledger)

    assert run.completed is True
    assert run.clean_verified_outcomes == 0
    assert run.validation.weight == 0.6


def test_a_self_reported_outcome_never_counts(committed):
    ledger, action_id, _ = committed

    run = bridge.run(observation(action_id, validation_status=bridge.SELF_REPORTED),
                     ledger=ledger)

    assert run.clean_verified_outcomes == 0
    assert run.validation.weight == 0.3


def test_an_external_verification_that_contradicts_the_prediction_does_not_count(committed):
    """Externally verified and positive, but not what was predicted.

    Three conditions, all required. This is the one a build is most likely to
    let through, because two of the three look like success.
    """
    ledger, action_id, _ = committed

    run = bridge.run(observation(action_id,
                                 external_observation="something else entirely"),
                     ledger=ledger)

    assert run.completed is True
    assert run.validation.validation_status == bridge.EXTERNALLY_VERIFIED
    assert run.validation.result_class == "positive"
    assert run.clean_verified_outcomes == 0     # reconciliation failed


def test_an_external_negative_does_not_count(committed):
    ledger, action_id, _ = committed

    run = bridge.run(observation(action_id, result_class="negative"), ledger=ledger)

    assert run.clean_verified_outcomes == 0


def test_the_metric_moves_only_when_all_three_conditions_hold(committed):
    """The positive case, so the zeros above mean something.

    An outside party, a positive result, and an observation matching what was
    predicted before the action ran.
    """
    ledger, action_id, _ = committed

    run = bridge.run(observation(action_id), ledger=ledger)

    assert run.completed is True
    assert run.validation.weight == 1.0
    assert run.clean_verified_outcomes == 1


# --- the gap this bridge exposed ---------------------------------------------

def test_calibration_is_blocked_and_says_why(committed):
    """GAP-BRIDGE-D-001, pinned so it cannot be silently forgotten.

    `CausalMemory.calibrate` works perfectly on hand-built pairs, which is how
    the gap stayed invisible: the institution never produces the data it needs.
    """
    ledger, action_id, _ = committed

    run = bridge.run(observation(action_id), ledger=ledger)

    assert run.calibration is None
    assert run.calibration_blocked_by == bridge.CALIBRATION_GAP
    assert "evidence_confidence" in run.calibration_blocked_by


def test_the_witness_really_has_no_field_for_the_prediction_it_was_graded_on():
    """The gap asserted against the structure rather than against a symptom.

    If someone ratifies the contract change and widens `CommitWitness`, this
    test fails and the pinned gap above has to be revisited — which is the
    point. A gap nobody is forced to revisit is a gap that becomes permanent.
    """
    fields = set(CommitWitness.__dataclass_fields__)

    assert "expected_outcome" in fields       # the prediction's *content* is kept
    assert "evidence_confidence" not in fields  # its *confidence* is not
    assert bridge.predicted_versus_realized(EvidenceLedger("probe")) == []


def test_the_join_reads_confidence_from_the_witness_not_the_outcome():
    """Sourcing it from the outcome would compare a result to itself.

    Asserted structurally, because the failure it prevents is invisible at
    runtime: a calibration built that way reports perfect calibration forever.
    """
    path = os.path.join(ROOT, "bridges", "reality_to_learning.py")
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "predicted_versus_realized")
    # The outcome is read for the *result*; the confidence must come only from
    # the witness. One read, and it must be off `witness`.
    confidence_reads = [n for n in ast.walk(fn)
                        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                        and n.func.attr == "get"
                        and any(isinstance(a, ast.Constant) and a.value == "evidence_confidence"
                                for a in n.args)]
    assert len(confidence_reads) == 1
    assert isinstance(confidence_reads[0].func.value, ast.Name)
    assert confidence_reads[0].func.value.id == "witness"


# --- promotion stays governed ------------------------------------------------

def test_a_capability_genome_is_never_promoted_by_the_learning_loop(committed):
    ledger, action_id, _ = committed

    run = bridge.run(observation(action_id), ledger=ledger, capability="experiment.run")

    assert run.proposed_genome_evidence["applied"] is False
    assert "governed act" in run.proposed_genome_evidence["why_not_applied"]


def test_the_bridge_never_writes_to_the_genome_registry():
    """AST over calls: no register, no promotion, under any name."""
    path = os.path.join(ROOT, "bridges", "reality_to_learning.py")
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

    for forbidden in ("register", "may_instantiate", "issue", "issue_single_action"):
        assert forbidden not in called, f"bridge calls {forbidden}"


# --- the peer's claim stays the peer's ---------------------------------------

def test_an_outside_observation_is_ingested_and_never_emitted(committed):
    """`emit` would make the kernel the source of a claim it merely received —
    which would turn an external verification into an internal one."""
    ledger, action_id, _ = committed
    before = {r.payload.get("event_id") for r in ledger.by_type("event")}

    run = bridge.run(observation(action_id), ledger=ledger)
    assert run.completed is True

    external = [r.payload for r in ledger.by_type("event")
                if r.payload.get("type") == "bridge.external_observation_received"]
    assert len(external) == 1
    assert external[0]["source"] == OUTSIDE
    assert external[0]["source"] != bridge.KERNEL
    assert before != {r.payload.get("event_id") for r in ledger.by_type("event")}


def test_the_bridge_introduces_no_new_mechanism():
    path = os.path.join(ROOT, "bridges", "reality_to_learning.py")
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    defined = {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
    assert defined <= {"LearningRun", "Halt", "ValidationResult"}, (
        f"bridge defines its own mechanism: "
        f"{sorted(defined - {'LearningRun', 'Halt', 'ValidationResult'})}"
    )
