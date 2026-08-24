"""Bridge D — Reality-to-Learning, attacked rather than demonstrated.

The tests that matter: an actor cannot verify itself, the Single Bottleneck
Metric refuses to move on internal evidence, and the calibration gap this
bridge exposed stays visible until someone with the authority closes it.
"""
import ast
import os
import tempfile

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

    The `committed` spec supplies no forecast, so this stays blocked — and the
    assertion below now names the half that is actually missing. It used to
    assert `"evidence_confidence" in ...`, which stopped being true on
    2026-08-24 when the gap text was corrected: v2 emission had closed the
    contract half, and reporting a resolved blocker as the live one is the
    stale-gap failure #25, #26, #30 and #48 were each corrected for.
    """
    ledger, action_id, _ = committed

    run = bridge.run(observation(action_id), ledger=ledger)

    assert run.calibration is None
    assert run.calibration_blocked_by == bridge.CALIBRATION_GAP
    assert "NO FORECAST IS SUPPLIED" in run.calibration_blocked_by
    assert "NO OUTSIDER HAS SPOKEN" in run.calibration_blocked_by


# --- what calibration is allowed to score ------------------------------------

def _spec(**kw):
    from evolution.experiment import ExperimentSpec

    base = dict(
        decisive_unknown="does an outside party ever speak",
        hypothesis="it does not, yet", prediction="the sandbox run records a value",
        metric="verified_outcomes", baseline=0.0, threshold=1.0, direction="gte",
        workflow="experiment.run", required_capabilities=["experiment.run"],
        authority_requirements=["kernel.grant"], budget_usd=0.0, reversible=True,
        rollback_path="discard the sandbox record",
        kill_condition="measured exceeds 100",
        verification="cryptographic_receipt")
    base.update(kw)
    return ExperimentSpec(**base)


def _committed_with(forecast):
    """One real committed action whose spec carries the given forecast."""
    from runtime.session import Session

    session = Session.open(tempfile.mkdtemp())
    run = session.traverse_experiment_to_reality(
        _spec(predicted_success_probability=forecast), measure=lambda s: 2.0)
    assert run.completed, run.reason
    return session.runtime.ledger, run.run.action_id


def test_calibration_scores_the_forecast_and_not_the_evidence():
    """CONTRADICTION-0003 Option A, at the one place the data is consumed.

    The two quantities are opposite by construction for a novel experiment, so
    a test that used the same number for both would pass either way. This spec
    forecasts 0.25 while Bridge C's evidence_confidence is 0.9, and the pair
    must carry 0.25.

    The defect this pins was mine, introduced in the same session as the split:
    `calibratable` was moved onto the forecast and this join was not, so it
    gated on the forecast's presence and then graded the institution on its
    evidence.
    """
    ledger, action_id = _committed_with(0.25)
    bridge.run(observation(action_id), ledger=ledger)

    assert bridge.predicted_versus_realized(ledger) == [(0.25, True)]


def test_an_unforecast_experiment_produces_no_pair_rather_than_a_zero():
    """Absent is not a prediction of failure, and must not be scored as one."""
    ledger, action_id = _committed_with(None)
    bridge.run(observation(action_id), ledger=ledger)

    assert bridge.predicted_versus_realized(ledger) == []


def test_an_internally_observed_outcome_does_not_calibrate_anything():
    """The institution may not grade its forecast against its own account.

    Every consequential action writes its own `internally_observed` outcome at
    the gate. Counting those meant one action produced two pairs, one of them
    scored against the institution's own report of what happened — the same
    self-assessment this bridge's `SELF_ATTESTATION` halt refuses, arriving
    through the realized side instead of the observer side.
    """
    ledger, _ = _committed_with(0.25)

    internal = [r.payload for r in ledger.by_type("outcome")]
    assert internal, "the gate wrote its own outcome"
    assert all(o["validation_status"] != bridge.EXTERNALLY_VERIFIED for o in internal)
    assert bridge.predicted_versus_realized(ledger) == []


def test_one_action_yields_one_pair_not_one_per_outcome_record():
    ledger, action_id = _committed_with(0.25)
    bridge.run(observation(action_id), ledger=ledger)

    assert len(ledger.by_type("outcome")) == 2, "internal + external"
    assert len(bridge.predicted_versus_realized(ledger)) == 1


def test_a_forecast_outside_zero_to_one_is_refused_by_the_spec():
    """Absent is fine; present-and-nonsensical would be scored as if it meant
    something."""
    assert _spec(predicted_success_probability=1.7).validate() == [
        "predicted_success_probability must be within 0..1"]
    assert _spec(predicted_success_probability=-0.1).validate() == [
        "predicted_success_probability must be within 0..1"]
    assert _spec(predicted_success_probability=0.0).validate() == []
    assert _spec(predicted_success_probability=None).validate() == []


def test_the_forecast_governs_no_admission_decision():
    """It is the number reality grades, never the number that buys entry.

    Asserted over the AST rather than by behaviour, because a behavioural test
    would only cover the thresholds it happened to pick.
    """
    import ast

    source = open(os.path.join(ROOT, "policy", "engine.py"), encoding="utf-8").read()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FunctionDef) and node.name == "evaluate":
            names = {n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)}
            assert "predicted_success_probability" not in names, (
                "policy.engine.evaluate reads the forecast; admission must "
                "depend on evidence_confidence alone")
            break
    else:                                          # pragma: no cover
        raise AssertionError("policy.engine.evaluate not found")


def test_the_witness_now_carries_the_prediction_it_is_graded_on():
    """The gap, closed — and the test that forced the revisit, doing its job.

    This assertion used to read `"evidence_confidence" not in fields`, with the
    note: *"If someone ratifies the contract change and widens CommitWitness,
    this test fails and the pinned gap has to be revisited — which is the
    point. A gap nobody is forced to revisit is a gap that becomes
    permanent."*

    The founder ratified it (FOUNDER-RULING-2026-08-23), the witness widened,
    and this test failed exactly as designed. The inversion is kept in place
    rather than deleted so the closure is visible as a closure.

    Both quantities are now present and they are not the same field —
    CONTRADICTION-0003. Grading a decision-to-act confidence against an outcome
    would have measured the wrong thing while looking correct.
    """
    fields = set(CommitWitness.__dataclass_fields__)

    assert "expected_outcome" in fields               # the prediction's content
    assert "evidence_confidence" in fields            # why it was admitted
    assert "predicted_success_probability" in fields  # what calibration scores
    assert "witness_version" in fields

    # Still empty for an empty ledger: emitting the field is not the same as
    # having anything to calibrate. CVO remains 0 and nothing here changes it.
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

    # UPDATED for witness contract v2. The invariant is unchanged and is the
    # whole point of this test; only the mechanism it inspects moved. Confidence
    # used to be read as `witness.get("evidence_confidence")`; it is now read
    # through `witness_v2.read(witness)`, which additionally distinguishes an
    # UNRECORDED v1 field from a genuine value.
    reads = [n for n in ast.walk(fn)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "read"
             and isinstance(n.func.value, ast.Name)
             and n.func.value.id == "witness_v2"]
    assert len(reads) == 1, "confidence must be read once, through the contract"
    assert isinstance(reads[0].args[0], ast.Name)
    assert reads[0].args[0].id == "witness", (
        "the reading must be taken from the witness, which is written BEFORE "
        "execution, not from the outcome, which is written after"
    )

    # The invariant restated as a prohibition, so a future edit that reaches for
    # the outcome fails here rather than silently reporting perfect calibration.
    outcome_confidence = [
        n for n in ast.walk(fn)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and n.func.attr == "get"
        and isinstance(n.func.value, ast.Name) and n.func.value.id == "outcome"
        and any(isinstance(a, ast.Constant) and a.value == "evidence_confidence"
                for a in n.args)]
    assert not outcome_confidence, "confidence was read off the outcome"


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
