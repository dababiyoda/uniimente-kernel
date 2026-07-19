"""Fast Capability Evolution, cycle 2: the organ's quality scorer.

Bottleneck: the critic rewards keyword density, not doctrine quality.
Hype, vagueness, and unrealistic claims pass unpenalized, so a
revolutionary-game-changing draft outranks a concrete engineering
update. The loop competes eleven weight configurations against the
doctrine-labeled corpus in isolated subprocesses and emits a proposal.

The baseline is not a paraphrase: BASELINE_WEIGHTS reproduces the organ
critic (DALEOBANKS services/critic.py, blob b11e8b31...) on every
corpus text, proven against critic_baseline_reference.json, which the
real critic generated. No parity, no cycle.

Run:  python3 evolution/run_fast_loop.py
"""

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "sdk-python"))
sys.path.insert(0, str(REPO_ROOT / "evolution" / "experiments"))

from uniimente_kernel.evolution import ExperimentSpec, VerifierRecord  # noqa: E402
from uniimente_kernel.evolution_loop import BranchGenerator, EvolutionLoop  # noqa: E402
from uniimente_kernel.ledger import DecisionLedger  # noqa: E402

import critic_weights as cw  # noqa: E402

BOTTLENECK = (
    "the organ's quality scorer rewards keyword density, not doctrine "
    "quality: hype and vagueness pass unpenalized"
)

LEDGER_PATH = REPO_ROOT / "evolution" / "ledger.jsonl"
CAPSULE_PATH = REPO_ROOT / "evolution" / "capsules" / "0002-fast-capability-evolution.json"
CORPUS_PATH = REPO_ROOT / "evolution" / "experiments" / "critic_corpus.json"
REFERENCE_PATH = REPO_ROOT / "evolution" / "experiments" / "critic_baseline_reference.json"
HARNESS_RUN = "2026-07-19T19-16-48.174886+00-00-harness.json"


def sha256_ref(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def branch_fields(mechanism: str, counterargument: str, **over):
    fields = dict(
        governing_assumption="The corpus is a faithful proxy for doctrine quality.",
        mechanism=mechanism,
        required_capabilities=["evolution_loop", "isolated_runner"],
        cost_usd=0.0,
        founder_attention_minutes=20,
        time_to_proof_days=1,
        authority_requirements=["founder-ratified weight change"],
        irreversible_downside="none: weights are data, rollback is a revert",
        expected_result="bad texts separated from good texts on the corpus",
        strongest_counterargument=counterargument,
        cheapest_falsification_test="rerun measure_config on the corpus",
        kill_condition="any doctrine-good text penalized below the accept bar",
    )
    fields.update(over)
    return fields


def make_entry(weights):
    return {
        "module": "critic_weights",
        "function": "measure_config",
        "kwargs": {"weights": weights},
        "pythonpath": str(REPO_ROOT / "evolution" / "experiments"),
    }


def propose(*, bottleneck, context):
    b = cw.BASELINE_WEIGHTS
    specs = [
        ("fastest_path", {"hype_penalty": -25.0},
         "Add one hype penalty (-25); a single-line change to the weight table.",
         "Vague and unrealistic texts still pass unpenalized."),
        ("lowest_capital", {k: (v * 0.5) for k, v in b.items()},
         "Scale every weight by 0.5; no new features, no review surface.",
         "Compresses good and bad together and halves the floor under good texts."),
        ("maximum_ownership",
         {"hype_penalty": -25.0, "vague_penalty": -25.0, "unrealistic_penalty": -25.0,
          "measurable_outcomes": 25.0, "concrete_actions": 20.0},
         "Own the full weight table: penalize hype/vague/unrealistic markers "
         "(-25 each) and boost substance signals (measurable 25, concrete 20).",
         "Largest diff; stays honest only while the corpus and parity artifact hold."),
        ("maximum_reversibility",
         {"hype_penalty": -20.0, "vague_penalty": -20.0, "unrealistic_penalty": -20.0},
         "All three penalties at -20 behind one multiplier flag; rollback is one toggle.",
         "An off switch is a bypass, and weaker penalties leave bad texts nearer the bar."),
        ("maximum_regeneration",
         {"hype_penalty": -15.0, "vague_penalty": -15.0, "unrealistic_penalty": -15.0},
         "Penalties at -15 plus a loop feeding misclassifications back into the corpus.",
         "Weaker separation today for a feedback loop that is not yet wired."),
        ("strongest_partnership", {},
         "Adopt a third-party scoring API and route drafts through it.",
         "An external dependency owns the trust rail and cannot be audited offline."),
        ("acquisition", {},
         "Acquire a content-scoring SaaS and inherit its scorer.",
         "Capital-heavy, unauditable internals, wrong stage."),
        ("incumbent_compatible", {},
         "Keep the critic exactly as is; rely on the blocking-issues lists outside the score.",
         "The blocking lists do not move the score; hype still outranks substance."),
        ("radical_simplification",
         {k: 0.0 for k in b if k not in ("length_high", "length_mid", "length_low")},
         "Score on length alone and delete every signal feature.",
         "Destroys all quality signal; good and bad texts converge to the length tier."),
        ("complete_removal", {k: 0.0 for k in b},
         "Delete the scorer and publish unjudged.",
         "Removes the capability the quality gate exists to exercise."),
        ("do_nothing", {},
         "Accept the current weights as the standing configuration.",
         "The bottleneck stands: hype outranks substance on the organ's own corpus."),
    ]
    return [
        {
            "archetype": archetype,
            "branch_fields": branch_fields(mechanism, counterargument),
            "entry": make_entry(weights),
        }
        for archetype, weights, mechanism, counterargument in specs
    ]


def main() -> int:
    # Gate 0: the baseline must be the organ scorer, proven by the
    # reference artifact the real critic generated, against this corpus.
    reference = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))
    if reference["corpus_sha256"] != sha256_ref(CORPUS_PATH):
        print("ABORT: reference artifact names a different corpus")
        return 1
    errors = cw.baseline_parity_errors()
    if errors:
        print("ABORT: baseline is not the organ scorer:")
        for error in errors:
            print(" ", error)
        return 1

    baseline = cw.measure_config({})
    experiment = ExperimentSpec(
        decisive_unknown=(
            "can a weight configuration separate doctrine-good from "
            "doctrine-bad texts the organ's baseline conflates?"
        ),
        hypothesis=(
            "penalizing doctrine violations while boosting substance "
            "signals separates the corpus the baseline scores backwards"
        ),
        method=(
            "eleven weight configurations measured on the fixed corpus in "
            "isolated subprocesses; strict directional comparison"
        ),
        metrics={
            "separation_margin": "higher",
            "false_accepts": "lower",
            "good_floor": "higher",
        },
        baseline=baseline,
        reversibility="reversible",
        budget_usd=0.0,
        kill_condition="any doctrine-good text penalized below the accept bar",
    )

    ledger = DecisionLedger(str(LEDGER_PATH))
    loop = EvolutionLoop(ledger, generator=BranchGenerator(proposer=propose))
    evidence_refs = [
        sha256_ref(CORPUS_PATH),
        sha256_ref(REFERENCE_PATH),
        f"harness-run:{HARNESS_RUN}",
    ]
    proposal = loop.run_cycle(
        bottleneck=BOTTLENECK,
        context={},
        experiment=experiment,
        audit_sides={
            "reality_failure_geometry": (
                "the failure is hype outranking substance; it is measured "
                "on a fixed corpus, not asserted"
            ),
            "power_participant_geometry": (
                "the scorer steers what the organ may publish; the founder "
                "holds the weight table"
            ),
            "eligibility_permission": (
                "weight changes ship only as a gated proposal; the loop "
                "has no apply path"
            ),
            "default_routing_access": (
                "every draft routes through the scorer; the default path "
                "is the governed path"
            ),
            "proof_truth_reputation": (
                "scores reproduce from corpus plus weights; the reference "
                "artifact pins the organ baseline by blob sha"
            ),
            "settlement_capital_physics": (
                "no capital moves; the cost is founder review minutes"
            ),
            "distribution_entanglement_counterposition": (
                "better separation emits less hype into the network; no "
                "dependency is added"
            ),
            "reliability_governance_regeneration_continuity": (
                "corpus and reference are versioned artifacts; the cycle "
                "re-runs deterministically"
            ),
        },
        mechanism_map={
            "weight_table": "default_routing",
            "parity_reference": "proof_and_truth",
            "gated_proposal": "eligibility",
        },
        requirements={
            "bounded_transaction": True,
            "real_beneficiary": True,
            "buyer_or_mandate_actor": True,
            "lawful_permission_path": True,
            "accepted_artifact": True,
            "external_consequence": True,
            "participant_benefit": True,
            "ninety_day_falsification_test": True,
            "fundable_reliability": True,
            "recovery": True,
            "kill_criteria": True,
        },
        verifier=VerifierRecord(
            level=1,
            verifier_name=(
                "deterministic invariant: isolated corpus measurement, "
                "baseline pinned to the real organ critic by parity artifact"
            ),
            evidence_ref=evidence_refs[1],
        ),
        decider="alfonso-lopez",
        rationale=(
            "the only configuration beating baseline on all three metrics: "
            "penalize doctrine violations, boost substance, keep the good "
            "floor rising"
        ),
        outcome_evidence_refs=evidence_refs,
    )

    capsule_record = {
        "proposal": proposal.to_dict(),
        "baseline": baseline,
        "winner_outcome": proposal.outcome,
        "experiment_id": experiment.experiment_id,
    }
    CAPSULE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CAPSULE_PATH.write_text(json.dumps(capsule_record, indent=2) + "\n", encoding="utf-8")

    print(f"decision: {proposal.decision}")
    print(f"selected: {proposal.selected_archetype}")
    print(f"outcome: {proposal.outcome}")
    print(f"baseline: {baseline}")
    print(f"summary: {proposal.summary}")
    print(f"capsule -> {CAPSULE_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
