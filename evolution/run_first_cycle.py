"""The first machine-recorded improvement cycle, run manually.

Subject: Phase 1, Consequence Integrity. Baseline: the organ published
through an unmediated live path (kill switch + rate governor only), 25
harness tests, no idempotency evidence. Improvement: the ConsequenceGate
adoption (kernel v0.8.0 + organ gate service). Verifier: deterministic
invariant, the organ harness suite passing on two consecutive runs.

The capsule this prints is the artifact; the ledger beside it is the
causal record. Rejected branches are preserved with why they lost.
"""

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sdk-python"))

from uniimente_kernel.evolution import (  # noqa: E402
    BRANCH_ARCHETYPES,
    SPIDER_REQUIREMENTS,
    SPIDER_SIDES,
    EvolutionCapsule,
    ExperimentSpec,
    SpiderWebAudit,
    StrategyBranch,
    StrategyTree,
    VerifierRecord,
)
from uniimente_kernel.ledger import DecisionLedger  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = DecisionLedger(path=os.path.join(HERE, "ledger.jsonl"))
BOTTLENECK = "organ publishing produced unmediated, unverified side effects"


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def build_tree() -> StrategyTree:
    tree = StrategyTree(LEDGER, bottleneck=BOTTLENECK)
    specs = {
        "fastest_path": (
            "Gate only the x adapter; leave linkedin/mastodon ungated.",
            "Speed beats coverage for the threshold.",
            "Partial coverage leaves the family open; the threshold is 100%.",
        ),
        "lowest_capital": (
            "Document the policy; rely on developer discipline.",
            "Process costs nothing.",
            "Discipline is not a mechanism; bypass remains one import away.",
        ),
        "maximum_ownership": (
            "One gate in the inherited template method; every adapter "
            "mediated, witnessed, receipted, with organ-owned grants.",
            "Ownership of the boundary compounds: future adapters inherit.",
            "Requires kernel stack to land first; slower than fastest path.",
        ),
        "maximum_reversibility": (
            "Config flag: gate on or off.",
            "Rollback is one toggle.",
            "An off switch is a bypass; the threshold forbids it.",
        ),
        "maximum_regeneration": (
            "Gate plus automatic outcome observation pull.",
            "Every publish feeds the memory loop.",
            "Outcome pull needs provider read APIs not yet wired.",
        ),
        "strongest_partnership": (
            "Adopt a third-party policy engine.",
            "Battle-tested policy logic.",
            "External dependency owns the trust rail; violates sovereignty.",
        ),
        "acquisition": (
            "Acquire a social-approval SaaS.",
            "Existing product, existing users.",
            "Capital-heavy, unauditable internals, wrong stage.",
        ),
        "incumbent_compatible": (
            "Keep the organ's kill switch as the only gate.",
            "Zero new code.",
            "No one-time execution, no receipts, no reconciliation: the "
            "status quo is the bottleneck.",
        ),
        "radical_simplification": (
            "Delete live publishing entirely.",
            "No live path, no risk.",
            "Removes the capability the institution exists to exercise.",
        ),
        "complete_removal": (
            "Retire the publishing organ.",
            "Eliminates the risk surface.",
            "Removes the family's value, not just its risk.",
        ),
        "do_nothing": (
            "Accept unmediated publishing.",
            "Zero effort.",
            "The bottleneck stands; Phase 1 never closes.",
        ),
    }
    for archetype in BRANCH_ARCHETYPES:
        mechanism, assumption, counter = specs[archetype]
        tree.add(StrategyBranch(
            archetype=archetype,
            bottleneck=BOTTLENECK,
            governing_assumption=assumption,
            mechanism=mechanism,
            required_capabilities=["consequence_gate", "commit_witness"],
            cost_usd=0.0,
            founder_attention_minutes=60,
            time_to_proof_days=3,
            authority_requirements=["operator-approved publish grant"],
            irreversible_downside="none: dry-run posture is the default",
            expected_result="100% verified mediated side-effect coverage",
            strongest_counterargument=counter,
            cheapest_falsification_test="run the harness suite twice",
            kill_condition="any unmediated live effect observed",
        ))
    return tree


def build_audit(branch_id: str) -> SpiderWebAudit:
    return SpiderWebAudit(
        branch_id=branch_id,
        sides={
            "reality_failure_geometry": "provider failure receipted; fake "
                "success disarms; dedupe survives restarts",
            "power_participant_geometry": "founder mints grants; organ "
                "executes; no self-issued authority",
            "eligibility_permission": "capability grant per platform+kind, "
                "bounded uses, approval-verified",
            "default_routing_access": "BaseSocialClient.publish is the single "
                "seam; bypass analysis found no other production caller",
            "proof_truth_reputation": "hash-chained ledger, causal event "
                "spine, JSON-safe receipts",
            "settlement_capital_physics": "cost ceiling enforced at commit "
                "time; zero-spend family",
            "distribution_entanglement_counterposition": "publishing is the "
                "distribution organ; gating it protects every downstream loop",
            "reliability_governance_regeneration_continuity": "deny-all "
                "default, restart-dedupe, kill conditions, reconciliation",
        },
        mechanism_map={
            "gate.execute": "default_routing",
            "capability grants": "eligibility",
            "hash-chained ledger + receipts": "proof_and_truth",
            "commit-time cost ceiling": "cashflow_and_settlement",
        },
        requirements={r: True for r in SPIDER_REQUIREMENTS},
    )


def main() -> None:
    tree = build_tree()
    winner = next(b for b in tree.branches.values()
                  if b.archetype == "maximum_ownership")
    losers = [b.branch_id for b in tree.branches.values()
              if b.branch_id != winner.branch_id]
    tree.select(
        winner.branch_id,
        decider="alfonso-lopez",
        rationale="the threshold is 100% coverage with verification; only "
                  "owning the inherited boundary satisfies it without a "
                  "bypass, and every future adapter inherits the posture",
        loss_reasons={lid: "leaves a bypass, removes the capability, or "
                      "cedes the trust rail" for lid in losers},
    )

    audit = build_audit(winner.branch_id)
    audit_ok, failures = audit.evaluate()
    assert audit_ok, failures

    experiment = ExperimentSpec(
        decisive_unknown="can one bounded action family reach 100% verified "
                         "mediated side-effect coverage with today's code?",
        hypothesis="gating the inherited publish seam closes the family and "
                   "the suite proves it deterministically",
        method="adopt the gate in kernel + organ; run the harness twice",
        metrics={
            "organ_suite_green": "higher",
            "mediated_coverage_pct": "higher",
            "consecutive_green_runs": "higher",
        },
        baseline={
            "organ_suite_green": 25.0,
            "mediated_coverage_pct": 0.0,
            "consecutive_green_runs": 0.0,
        },
        reversibility="reversible",
        budget_usd=0.0,
        kill_condition="any unmediated live effect observed",
    )
    experiment.validate()

    # Evidence: the harness run records produced by the adoption work.
    runs_dir = "/tmp/daleobanks-swap/verifier/runs"
    evidence = sorted(
        sha256_file(os.path.join(runs_dir, name))
        for name in os.listdir(runs_dir) if name.endswith(".json")
    )
    capsule = EvolutionCapsule(LEDGER).complete_cycle(
        bottleneck=BOTTLENECK,
        tree=tree,
        selected_branch_id=winner.branch_id,
        audit=audit,
        experiment=experiment,
        outcome={
            "organ_suite_green": 39.0,
            "mediated_coverage_pct": 100.0,
            "consecutive_green_runs": 2.0,
        },
        outcome_evidence_refs=evidence,
        verifier=VerifierRecord(
            level=1,
            verifier_name="organ harness suite, two consecutive runs",
            evidence_ref=evidence[-1],
        ),
        rationale="100% of the family's live path crosses the gate; the "
                  "suite grew 25 -> 39 and passed twice consecutively, and "
                  "the one failure in the trajectory (test isolation) was "
                  "diagnosed, fixed, and preserved",
    )

    out = os.path.join(HERE, "capsules")
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "0001-phase1-consequence-integrity.json")
    with open(path, "w") as handle:
        json.dump(capsule, handle, indent=2)
    print(f"decision: {capsule['decision']['decision']}")
    print(f"capsule: {path}")


if __name__ == "__main__":
    main()
