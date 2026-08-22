"""Standing cognition, connected: signal -> tick -> candidate -> gate -> receipt.

`egregore/` is 1268 lines of bounded standing cognition, complete down to its own
`gate_adapter.submit_through_gate`. Until this file, **zero non-test modules
imported any of it** and nothing had ever run the pathway end to end.

No new mechanism is built here. `submit_through_gate` already existed and is
used as it stands; what was missing was the demonstration that the organ reaches
the canonical gate at all, and the registration that lets the Whole-Body Closure
Controller see it.
"""
import ast
import os

import pytest

from compiler.ucl_compiler import compile_constitution
from egregore.contracts import Assessment, CandidateProposal, SignalEnvelope
from egregore.gate_adapter import bind_for_gate, submit_through_gate
from egregore.resources import ResourceGovernor
from egregore.runtime import StandingCognitionRuntime
from identity.machine_passport import PassportRegistry
from policy.consequence_gate import ConsequenceGate
from provenance.commit_witness import WitnessSigner
from provenance.ledger import EvidenceLedger

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def signal(event_id="event-1"):
    return SignalEnvelope.build(
        source="discord://community/main",
        source_event_id=event_id,
        observed_at="2026-08-22T00:00:00Z",
        payload={"text": "the community asks for a status update"},
        evidence_refs=(f"source:{event_id}",))


def candidate_from(sig, **kw):
    base = dict(
        proposed_by="strategist",
        objective="draft a factual status update",
        action_class="community_update",
        requested_capability="social.publish.draft",
        target="sandbox:community-outbox",
        consequence_class="internal_write",
        payload={"text": "draft: a factual status update"},
        evidence_refs=sig.evidence_refs,
        confidence=0.9, estimated_cost_usd=0.0,
        expected_outcome="a reviewed community update is drafted",
        source_signal_ids=(sig.signal_id,))
    base.update(kw)
    return CandidateProposal.build(**base)


def approving(role):
    def evaluate(cand, signals, context):
        return Assessment.build(role=role, candidate_id=cand.candidate_id,
                                score=0.9, confidence=0.9, objections=(),
                                veto=False, evidence_refs=("review:probe",))
    return evaluate


@pytest.fixture
def wired():
    compiled = compile_constitution(ROOT)
    passports = PassportRegistry()
    ledger = EvidenceLedger(compiled.constitution_hash)
    gate = ConsequenceGate(compiled=compiled, passports=passports, ledger=ledger,
                           signer=WitnessSigner(env="development"))
    actor = passports.issue(
        kind="agent", creator="alfonso", owner_organ="uniimente-kernel",
        legal_principal="alfonso_lopez",
        declared_capabilities=["social.publish.draft"],
        budget_ceiling_usd=5.0, consequence_class="internal_write")
    sig = signal()
    runtime = StandingCognitionRuntime(
        ledger=ledger,
        proposers={"strategist": lambda signals, context: [candidate_from(sig)]},
        evaluators={"guardian": approving("guardian"),
                    "treasury": approving("treasury")})
    return gate, passports, ledger, actor.passport_id, runtime, sig


# --- the pathway ------------------------------------------------------------

def test_standing_cognition_reaches_the_canonical_gate_and_is_receipted(wired):
    """The whole point: a signal observed outside becomes a governed action.

    Nothing in the institution had ever run this, so `egregore/` was a complete
    organ with no pathway through it.
    """
    gate, passports, ledger, actor, runtime, sig = wired

    runtime.ingest(sig)
    cycle = runtime.tick(trigger_id="tick-1", signal_ids=(sig.signal_id,),
                         resources=ResourceGovernor(max_model_calls=20,
                                                    max_estimated_cost_usd=1.0))
    chosen = runtime.selected_candidate(cycle)
    assert chosen is not None

    record = submit_through_gate(
        gate, chosen, actor=actor, legal_principal="alfonso_lopez",
        executor=lambda p: {"observed_outcome": chosen.expected_outcome,
                            "result_class": "positive"})

    assert record.state == "recorded"
    assert record.receipt_hash is not None
    assert record.witness_id is not None


def test_the_candidate_carries_no_execution_authority_into_the_gate(wired):
    """`execution_authority` is 'none' on the candidate and stays 'none' in the
    proposal's context. Cognition proposes; it never authorizes."""
    gate, passports, ledger, actor, runtime, sig = wired
    chosen = candidate_from(sig)

    proposal = bind_for_gate(chosen, actor=actor, legal_principal="alfonso_lopez")

    assert chosen.execution_authority == "none"
    assert proposal.context["egregore_execution_authority"] == "none"


def test_the_gate_still_refuses_a_revoked_actor_even_with_a_clean_cycle(wired):
    """A completed cognition cycle confers nothing. Identity is checked at the
    gate, not inherited from the quality of the reasoning that produced it."""
    gate, passports, ledger, actor, runtime, sig = wired
    runtime.ingest(sig)
    cycle = runtime.tick(trigger_id="tick-1", signal_ids=(sig.signal_id,),
                         resources=ResourceGovernor(max_model_calls=20,
                                                    max_estimated_cost_usd=1.0))
    chosen = runtime.selected_candidate(cycle)
    passports.revoke(actor, reason="testing identity lapse", revoker="alfonso")

    record = submit_through_gate(
        gate, chosen, actor=actor, legal_principal="alfonso_lopez",
        executor=lambda p: {"observed_outcome": "should never run",
                            "result_class": "positive"})

    assert record.state == "refused"
    assert record.receipt_hash is None


def test_uniimente_may_never_be_the_legal_principal_on_this_path(wired):
    gate, passports, ledger, actor, runtime, sig = wired

    with pytest.raises(Exception):
        bind_for_gate(candidate_from(sig), actor=actor, legal_principal="UNIIMENTE")


# --- the registration finding, kept from recurring ---------------------------

def test_egregore_closures_are_registered_with_the_controller():
    """`egregore/closure.py` shipped five closures that were never registered.

    So the Whole-Body Closure Controller — the section 5.7 component whose whole
    job is detecting a loop left open — had never checked the one organ that
    wrote its own checks. They passed the entire time; nobody was reading them.
    """
    from closure.integration_registry import build_registry

    assert "egregore-standing-cognition" in build_registry().modules()


def test_no_module_ships_closures_that_go_unregistered():
    """The generalisation, so this class of blind spot cannot recur silently.

    A module defining `ModuleClosures` and not appearing in the registry is
    exactly the shape of the egregore gap: self-checks that run for nobody. The
    discovery was a one-off; this test is the standing check.
    """
    from closure.integration_registry import build_registry

    registered = set(build_registry().modules())

    shipping: list[str] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames
                       if d not in {".git", "__pycache__", "tests", ".venv", "closure"}]
        for name in filenames:
            if not name.endswith(".py"):
                continue
            path = os.path.join(dirpath, name)
            with open(path, encoding="utf-8", errors="ignore") as fh:
                try:
                    tree = ast.parse(fh.read())
                except SyntaxError:
                    continue
            builds = any(
                isinstance(n, ast.Call)
                and ((isinstance(n.func, ast.Name) and n.func.id == "ModuleClosures")
                     or (isinstance(n.func, ast.Attribute) and n.func.attr == "ModuleClosures"))
                for n in ast.walk(tree))
            if builds:
                shipping.append(os.path.relpath(path, ROOT))

    unregistered = []
    for path in shipping:
        with open(os.path.join(ROOT, path), encoding="utf-8") as fh:
            source = fh.read()
        # The module name a file declares is the string it hands ModuleClosures.
        declared = {n.value for n in ast.walk(ast.parse(source))
                    if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        if not (declared & registered):
            unregistered.append(path)

    assert unregistered == [], (
        f"these modules define closures nobody runs: {unregistered}")
