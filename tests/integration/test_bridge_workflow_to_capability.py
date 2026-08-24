"""Bridge G — extraction, attacked rather than demonstrated.

The tests that matter: a caller cannot widen the packaged authority, a refused
run yields no capability, and the economic half of Bridge G stays unclaimed.
"""
import ast
import inspect
import os

import pytest

from bridges import experiment_to_reality as bridge_c
from bridges import workflow_to_capability as bridge_g
from capabilities.genome import GenomeRegistry
from compiler.ucl_compiler import compile_constitution
from evolution.experiment import ExperimentSpec
from identity.machine_passport import PassportRegistry
from policy.consequence_gate import ConsequenceGate
from provenance.commit_witness import WitnessSigner
from provenance.ledger import EvidenceLedger

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MODES = ("the sandbox target is unreachable", "the measure instrument raises")


def spec():
    return ExperimentSpec(
        decisive_unknown="can a run be packaged",
        hypothesis="only with the authority it actually held",
        prediction="the sandbox run records a value",
        metric="verified_outcomes", baseline=0.0, threshold=1.0, direction="gte",
        workflow="experiment.run", required_capabilities=["experiment.run"],
        authority_requirements=["kernel.grant"], budget_usd=0.0, reversible=True,
        rollback_path="discard the sandbox record",
        kill_condition="measured exceeds 100",
        verification="cryptographic_receipt")


@pytest.fixture
def ran():
    """A real receipted action, produced by Bridge C rather than fabricated."""
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
    return ledger, run.action_id, passports, actor.passport_id


# --- the pathway --------------------------------------------------------------

def test_a_receipted_action_becomes_a_registered_capability(ran):
    """The first genome in this institution derived from something that ran.

    Every other `CapabilityGenome` is a literal written inside a closure probe.
    """
    ledger, action_id, passports, _ = ran
    registry = GenomeRegistry(ledger=ledger)

    result = bridge_g.extract(ledger, action_id, passports=passports,
                              failure_modes=MODES, registry=registry)

    assert result.completed is True
    assert result.registered is True
    assert result.genome.validate() == []
    assert registry.get(result.genome.name, result.genome.version) is not None


def test_the_genome_cites_the_real_witness_and_receipt(ran):
    """Acceptance tests that name records the ledger actually holds."""
    ledger, action_id, passports, _ = ran

    result = bridge_g.extract(ledger, action_id, passports=passports,
                              failure_modes=MODES)

    witness_id = ledger.by_type("witness")[0].payload["witness_id"]
    assert f"witness:{witness_id}" in result.genome.acceptance_tests
    assert f"receipt:{action_id}" in result.genome.acceptance_tests


def test_the_evidence_provenance_travels_with_the_genome(ran):
    """Internally observed, and the description says so rather than implying
    a capability that reality has confirmed."""
    ledger, action_id, passports, _ = ran

    result = bridge_g.extract(ledger, action_id, passports=passports,
                              failure_modes=MODES)

    assert "internally_observed" in result.genome.description
    assert "not been externally verified" in result.genome.description


# --- the anti-inflation property ---------------------------------------------

def test_no_caller_can_set_the_consequence_class_or_budget():
    """Packaging is the quietest place to widen authority.

    `GenomeRegistry.may_instantiate` checks requests against this envelope, so a
    parameter here would be an authority grant wearing a registry entry.
    Asserted on the signature, because the failure is invisible at runtime.
    """
    params = set(inspect.signature(bridge_g.extract).parameters)

    for banned in ("consequence_class", "budget", "budget_ceiling_usd",
                   "authority", "envelope", "max_consequence_class"):
        assert banned not in params, f"extract() accepts {banned}"


def test_the_envelope_matches_the_authority_the_action_actually_ran_under(ran):
    """GAP-BRIDGE-G-001, closed: the envelope is now the exercised authority.

    This test used to compare the genome against the actor's PASSPORT, because
    the passport was the only authority source the ledger could offer. That was
    always an over-estimate — a passport states what an identity may *ever* do,
    not what this action was authorised to do — and the bridge labelled it as
    one.

    Since the Gate emits Witness v2 the action carries its own answer, so the
    ceiling here is the one the grant actually permitted (0.0 for a zero-cost
    action) rather than the actor's standing 5.0. A capability packaged with a
    5.0 ceiling it never exercised would over-state its own authority every
    time it was transplanted.
    """
    ledger, action_id, passports, actor = ran
    held = passports.to_dict(actor)

    result = bridge_g.extract(ledger, action_id, passports=passports,
                              failure_modes=MODES)

    assert result.authority_source == "witness"

    witness = ledger.by_type("witness")[0].payload
    assert result.genome.authority.max_consequence_class == \
        witness["consequence_class"]
    assert result.genome.authority.budget_ceiling_usd == \
        witness["exposure_ceiling_usd"]
    assert result.exercised_consequence_class == witness["consequence_class"]

    # The exercised ceiling is BELOW the standing one, which is the whole point.
    assert result.genome.authority.budget_ceiling_usd < held["budget_ceiling_usd"]


def test_a_v2_action_no_longer_depends_on_the_passport_being_resolvable(ran):
    """The dependency GAP-BRIDGE-G-001 created, removed.

    This test used to assert that an unresolvable passport halts extraction,
    because the passport was the only authority source. It still must never
    invent a ceiling — but for a v2 action it no longer has to ask, since the
    action's own witness states what it ran under. An extraction that survives
    the identity registry being unavailable is strictly better evidence.
    """
    ledger, action_id, _, _ = ran

    class Empty:
        def to_dict(self, _passport_id):
            raise KeyError("unknown identity")

    result = bridge_g.extract(ledger, action_id, passports=Empty(),
                              failure_modes=MODES)

    assert result.completed is True
    assert result.authority_source == "witness"


def test_a_v1_action_with_an_unresolvable_identity_still_refuses(ran):
    """The original protection, preserved for the records it was written for.

    v1 witnesses carry no authority envelope, so for those the passport remains
    the only source and an unreadable one must still halt extraction. An
    invented ceiling is worse than no capability, and that has not changed for
    any record written before the migration.
    """
    ledger, action_id, _, _ = ran

    # Strip the v2 facts from the stored witness, reproducing a v1 record.
    witness_record = ledger.by_type("witness")[0]
    for field in ("witness_version", "evidence_confidence", "consequence_class",
                  "exposure_ceiling_usd", "predicted_success_probability"):
        witness_record.payload.pop(field, None)

    class Empty:
        def to_dict(self, _passport_id):
            raise KeyError("unknown identity")

    result = bridge_g.extract(ledger, action_id, passports=Empty(),
                              failure_modes=MODES)

    assert result.completed is False
    assert result.halted_at is bridge_g.Halt.AUTHORITY_UNREADABLE
    assert result.genome is None


# --- a capability that never worked is never packaged ------------------------

def test_an_action_with_no_receipt_yields_no_capability(ran):
    ledger, _, passports, _ = ran

    result = bridge_g.extract(ledger, "no-such-action", passports=passports,
                              failure_modes=MODES)

    assert result.halted_at is bridge_g.Halt.NO_RECEIPT
    assert result.genome is None


def test_a_refused_run_leaves_nothing_to_package():
    """End to end: the gate refuses, so no receipt exists, so no genome does."""
    compiled = compile_constitution(ROOT)
    passports = PassportRegistry()
    ledger = EvidenceLedger(compiled.constitution_hash)
    gate = ConsequenceGate(compiled=compiled, passports=passports, ledger=ledger,
                           signer=WitnessSigner(env="development"))
    actor = passports.issue(
        kind="agent", creator="alfonso", owner_organ="uniimente-kernel",
        legal_principal="alfonso_lopez", declared_capabilities=["experiment.run"],
        budget_ceiling_usd=5.0, consequence_class="internal_write")
    passports.revoke(actor.passport_id, reason="testing", revoker="alfonso")

    run = bridge_c.run(spec(), gate=gate, passports=passports,
                       actor=actor.passport_id, measure=lambda s: 2.0, ledger=ledger)
    assert run.completed is False

    result = bridge_g.extract(ledger, run.action_id or "none", passports=passports,
                              failure_modes=MODES)

    assert result.completed is False
    assert result.genome is None


def test_a_genome_declaring_no_failure_modes_is_refused(ran):
    """`CapabilityGenome.validate` requires them, and the bridge does not
    invent any to get past it."""
    ledger, action_id, passports, _ = ran

    result = bridge_g.extract(ledger, action_id, passports=passports,
                              failure_modes=())

    assert result.halted_at is bridge_g.Halt.GENOME_INVALID
    assert "failure modes" in result.reason


# --- the economic half stays unclaimed ---------------------------------------

def test_the_faster_or_cheaper_claim_is_explicitly_not_made(ran):
    """Bridge G's payoff needs a verified outcome. There is none."""
    from bridges.reality_to_learning import clean_verified_outcomes

    ledger, action_id, passports, _ = ran

    result = bridge_g.extract(ledger, action_id, passports=passports,
                              failure_modes=MODES)

    assert clean_verified_outcomes(ledger) == 0
    assert result.economic_claim.startswith("none:")
    assert "verified outcome" in result.economic_claim


# --- the gap this bridge found ------------------------------------------------

def test_the_ledger_now_supplies_the_authority_envelope(ran):
    """GAP-BRIDGE-G-001, closed — by the test that pinned it open.

    The previous assertion was `"consequence_class" not in witness`, with the
    note: *"If someone widens the witness or starts recording the budget, this
    fails and the bridge should be revisited to read from the ledger instead of
    the passport — which is the point of pinning it."*

    Someone did. The inversion is kept so the closure is legible as a closure
    rather than as a test that quietly disappeared.
    """
    ledger, action_id, _, _ = ran

    witness = ledger.by_type("witness")[0].payload
    assert witness["witness_version"] == 2
    assert "consequence_class" in witness
    assert "exposure_ceiling_usd" in witness

    # The receipt still carries no budget, and does not need to: the ceiling is
    # a property of the authority, not of the result.
    receipt = ledger.by_type("receipt")[0].payload
    assert "budget_usd" not in receipt

    # And the gate's transitions are `event` records, not a queryable state type.
    assert ledger.by_type("action_state") == []
    proposed = [r.payload for r in ledger.by_type("event")
                if r.payload.get("type") == "action.proposed"]
    assert proposed and "consequence_class" not in proposed[0]


def test_the_gap_is_named_in_the_module_not_only_in_a_commit_message():
    """Still asserted after the v2 migration, with the vocabulary it now uses.

    The purpose is unchanged: a reader of this module must find the gap in the
    module. What changed is that the gap is no longer "the fields do not exist"
    but "the fields exist and nothing writes them", so the text names the
    concrete fields and the reason adoption is blocked.
    """
    gap = bridge_g.GAP_BRIDGE_G_001
    assert "consequence_class" in gap
    assert "exposure_ceiling_usd" in gap
    # The gap must say why it is still open, not merely that it is.
    assert "CONTRADICTION-0002" in gap
    assert "actor_passport" in gap, (
        "the fallback is an over-estimate and the gap text must say which "
        "source a reader is actually looking at"
    )


def test_the_bridge_introduces_no_new_mechanism():
    path = os.path.join(ROOT, "bridges", "workflow_to_capability.py")
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    defined = {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
    assert defined <= {"ExtractionRun", "Halt"}, (
        f"bridge defines its own mechanism: {sorted(defined - {'ExtractionRun', 'Halt'})}"
    )
