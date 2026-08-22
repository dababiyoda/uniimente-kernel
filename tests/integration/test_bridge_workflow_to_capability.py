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


def test_the_envelope_matches_the_authority_the_actor_actually_held(ran):
    ledger, action_id, passports, actor = ran
    held = passports.to_dict(actor)

    result = bridge_g.extract(ledger, action_id, passports=passports,
                              failure_modes=MODES)

    assert result.genome.authority.max_consequence_class == held["consequence_class"]
    assert result.genome.authority.budget_ceiling_usd == held["budget_ceiling_usd"]
    assert result.exercised_consequence_class == held["consequence_class"]


def test_an_unresolvable_identity_refuses_rather_than_defaulting(ran):
    """An invented ceiling is worse than no capability.

    The passport registry is the only authority source available, so when it
    cannot answer, extraction stops. It must not fall back to `read_only`, to
    zero, or to anything else that would look like a safe default while being a
    fabricated authority claim.
    """
    ledger, action_id, _, _ = ran

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

def test_the_ledger_really_cannot_supply_the_authority_envelope(ran):
    """GAP-BRIDGE-G-001, asserted against the records rather than the prose.

    If someone widens the witness or starts recording the budget, this fails and
    the bridge should be revisited to read from the ledger instead of the
    passport — which is the point of pinning it.
    """
    ledger, action_id, _, _ = ran

    witness = ledger.by_type("witness")[0].payload
    assert "consequence_class" not in witness
    assert "budget_ceiling_usd" not in witness

    receipt = ledger.by_type("receipt")[0].payload
    assert "budget_usd" not in receipt

    # And the gate's transitions are `event` records, not a queryable state type.
    assert ledger.by_type("action_state") == []
    proposed = [r.payload for r in ledger.by_type("event")
                if r.payload.get("type") == "action.proposed"]
    assert proposed and "consequence_class" not in proposed[0]


def test_the_gap_is_named_in_the_module_not_only_in_a_commit_message():
    assert "consequence class" in bridge_g.GAP_BRIDGE_G_001
    assert "budget ceiling" in bridge_g.GAP_BRIDGE_G_001


def test_the_bridge_introduces_no_new_mechanism():
    path = os.path.join(ROOT, "bridges", "workflow_to_capability.py")
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    defined = {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
    assert defined <= {"ExtractionRun", "Halt"}, (
        f"bridge defines its own mechanism: {sorted(defined - {'ExtractionRun', 'Halt'})}"
    )
