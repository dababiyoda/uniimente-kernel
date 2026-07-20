import unittest

from capabilities.genome import AuthorityEnvelope, CapabilityGenome, GenomeRegistry
from foundry import (
    AdvantageFoundry,
    CapabilityNeed,
    CommercialClosureCompiler,
    CommercialStage,
    FoundryError,
    FoundryPipeline,
    OpportunitySpec,
    PipelineStatus,
    StrategyBranch,
    STRATEGY_ROUTES,
)
from omnimorph import OmnimorphEngine, RatificationRecord
from provenance.ledger import EvidenceLedger


def opportunity():
    return OpportunitySpec(
        opportunity_id="pipeline-opp-1",
        buyer="Named Buyer LLC",
        beneficiary="operations team",
        pain_owner="VP Operations",
        budget_owner="CFO",
        recurring_transaction="approve and settle verified service",
        broken_state="proof is unreliable",
        trapped_value_usd=50000,
        accepted_artifact="signed verification receipt",
        external_consequence="buyer changes settlement decision",
        lawful_path="paid diagnostic under reviewed agreement",
        evidence_refs=("sha256:" + "a" * 64,),
    )


def branches():
    return tuple(
        StrategyBranch(
            route=route,
            mechanism=f"mechanism-{route}",
            governing_assumption="buyer will pay for verified proof",
            strongest_counterargument="status quo may be sufficient",
            cheapest_falsification_test="ask for one paid diagnostic",
            kill_condition="no paid commitment",
            cost_usd=10 + index,
            time_to_proof_days=1 + index,
            expected_value_usd=1000 + index * 100,
            reversibility=1.0,
            evidence_quality=0.8,
            founder_hours=1.0,
            required_capabilities=("research.read", "offer.compile"),
        )
        for index, route in enumerate(STRATEGY_ROUTES)
    )


def registry(ledger=None):
    result = GenomeRegistry(ledger=ledger)
    for name, consequence_class, budget in (
        ("research.read", "read_only", 100),
        ("offer.compile", "internal_write", 200),
    ):
        result.register(CapabilityGenome(
            name=name,
            version="1.0.0",
            description=name,
            interface={"inputs": {"request": "dict"}, "outputs": {"result": "dict"}},
            contracts=["event", "outcome"],
            authority=AuthorityEnvelope(
                max_consequence_class=consequence_class,
                budget_ceiling_usd=budget,
            ),
            acceptance_tests=["deterministic"],
            failure_modes=["dependency unavailable"],
            recovery_path="retry or replace",
        ))
    return result


def build_system(ledger):
    foundry = AdvantageFoundry(ledger)
    omnimorph = OmnimorphEngine(registry(), ledger=ledger)
    commercial = CommercialClosureCompiler(ledger)
    pipeline = FoundryPipeline(
        foundry=foundry,
        omnimorph=omnimorph,
        commercial=commercial,
        ledger=ledger,
    )
    return foundry, omnimorph, commercial, pipeline


def design(foundry, pipeline):
    foundry.intake(opportunity())
    return pipeline.design(
        opportunity_id=opportunity().opportunity_id,
        branches=branches(),
        capability_needs=(
            CapabilityNeed(
                "research.read", "research", ("request",), ("result",),
                "read_only", 10,
            ),
            CapabilityNeed(
                "offer.compile", "compile offer", ("request",), ("result",),
                "internal_write", 20,
            ),
        ),
        control_surface="proof",
        success_metrics=("paid commitment", "verified outcome"),
        kill_conditions=("no buyer commitment",),
        capability_versions={
            "research.read": "1.0.0",
            "offer.compile": "1.0.0",
        },
        objective="deliver one governed proof diagnostic",
        consequence_ceiling="internal_write",
        expires_at="2099-08-01T00:00:00Z",
    )


def advance_commercial(commercial, case_id):
    steps = (
        (CommercialStage.BUYER_CONFIRMED, {"buyer_ref": "buyer:1"}),
        (
            CommercialStage.PROBLEM_EVIDENCE_CONFIRMED,
            {"problem_evidence_ref": "proof:1"},
        ),
        (
            CommercialStage.OFFER_APPROVED,
            {"offer_ref": "offer:1", "human_approval_ref": "approval:offer"},
        ),
        (
            CommercialStage.OUTREACH_AUTHORIZED,
            {
                "human_approval_ref": "approval:outreach",
                "gate_receipt_hash": "sha256:" + "b" * 64,
            },
        ),
        (CommercialStage.BUYER_COMMITMENT, {"commitment_ref": "commitment:1"}),
        (
            CommercialStage.PAYMENT_OR_BINDING_COMMITMENT,
            {"payment_or_contract_ref": "payment:1", "payment_usd": 500},
        ),
        (
            CommercialStage.DELIVERY_AUTHORIZED,
            {
                "human_approval_ref": "approval:delivery",
                "gate_receipt_hash": "sha256:" + "c" * 64,
            },
        ),
        (
            CommercialStage.DELIVERY_COMPLETED,
            {"delivery_receipt_ref": "delivery:1"},
        ),
        (
            CommercialStage.CUSTOMER_ACCEPTANCE,
            {"acceptance_ref": "acceptance:1"},
        ),
        (
            CommercialStage.OUTCOME_OBSERVED,
            {"outcome_ref": "outcome:1", "externally_verified": True},
        ),
        (
            CommercialStage.ECONOMICS_RECONCILED,
            {
                "reconciliation_ref": "reconcile:1",
                "contribution_margin_usd": 200,
                "founder_hours": 3,
                "metric_results": {"verified_workflow_improvement": 1},
            },
        ),
    )
    for index, (stage, payload) in enumerate(steps):
        commercial.advance(
            case_id,
            stage,
            actor="alfonso_lopez",
            evidence_refs=("sha256:" + f"{index + 1:x}" * 64,)[:1],
            payload=payload,
        )


class FoundryPipelineTests(unittest.TestCase):
    def test_design_stops_before_authority(self):
        ledger = EvidenceLedger("sha256:" + "0" * 64)
        foundry, omnimorph, _, pipeline = build_system(ledger)
        run = design(foundry, pipeline)
        self.assertEqual(run.status, PipelineStatus.AWAITING_RATIFICATION)
        self.assertTrue(run.simulation_passed)
        self.assertNotIn(run.organ_id, omnimorph.active)
        with self.assertRaises(FoundryError):
            pipeline.open_commercial_validation(run.run_id)

    def test_self_ratification_is_refused(self):
        ledger = EvidenceLedger("sha256:" + "0" * 64)
        foundry, _, _, pipeline = build_system(ledger)
        run = design(foundry, pipeline)
        with self.assertRaises(FoundryError):
            pipeline.propose_activation(
                run.run_id,
                RatificationRecord(
                    run.manifest_hash,
                    "OMNIMORPH",
                    "sha256:" + "d" * 64,
                    "2099-08-01T00:00:00Z",
                ),
            )

    def test_complete_paid_pipeline_rebuilds_after_restart(self):
        ledger = EvidenceLedger("sha256:" + "0" * 64)
        foundry, omnimorph, commercial, pipeline = build_system(ledger)
        run = design(foundry, pipeline)
        pipeline.propose_activation(
            run.run_id,
            RatificationRecord(
                run.manifest_hash,
                "alfonso_lopez",
                "sha256:" + "d" * 64,
                "2099-08-01T00:00:00Z",
            ),
        )
        pipeline.record_gate_activation(
            run.run_id,
            "sha256:" + "e" * 64,
        )
        pipeline.open_commercial_validation(run.run_id)
        advance_commercial(commercial, run.commercial_case_id)
        commercial.decide(
            run.commercial_case_id,
            "RETAIN",
            actor="alfonso_lopez",
            evidence_ref="sha256:" + "f" * 64,
            human_approval_ref="sha256:" + "1" * 64,
        )
        genome = pipeline.finalize_retained_genome(
            run.run_id,
            genome_name="governed-proof-diagnostic",
            genome_version="1.0.0",
            capability_versions=(
                "research.read@1.0.0",
                "offer.compile@1.0.0",
            ),
            time_to_validated_genome_days=7,
            rollback="revoke organ grants and restore prior workflow",
            accountable_actor="alfonso_lopez",
            seal_record_hash="sha256:" + "2" * 64,
        )
        self.assertEqual(genome.contribution_margin_usd, 200)
        self.assertEqual(
            pipeline.get(run.run_id).status,
            PipelineStatus.RETAINED_GENOME,
        )
        self.assertTrue(ledger.verify_chain()[0])

        restarted_foundry, restarted_omnimorph, restarted_commercial, restarted_pipeline = build_system(ledger)
        rebuilt = restarted_pipeline.get(run.run_id)
        self.assertEqual(rebuilt.status, PipelineStatus.RETAINED_GENOME)
        self.assertEqual(rebuilt.genome_key, genome.key)
        self.assertEqual(
            restarted_foundry.get_opportunity(opportunity().opportunity_id),
            opportunity(),
        )
        self.assertIsNotNone(
            restarted_foundry.get_architecture(run.architecture_id),
        )
        self.assertIsNotNone(
            restarted_omnimorph.get_manifest(run.organ_id),
        )
        self.assertEqual(
            restarted_commercial.get(run.commercial_case_id).stage,
            CommercialStage.CAPABILITY_GENOME_SEALED,
        )
        self.assertTrue(ledger.verify_chain()[0])

    def test_unverified_or_unretained_case_cannot_seal(self):
        ledger = EvidenceLedger("sha256:" + "0" * 64)
        foundry, _, commercial, pipeline = build_system(ledger)
        run = design(foundry, pipeline)
        pipeline.propose_activation(
            run.run_id,
            RatificationRecord(
                run.manifest_hash,
                "alfonso_lopez",
                "sha256:" + "d" * 64,
                "2099-08-01T00:00:00Z",
            ),
        )
        pipeline.record_gate_activation(run.run_id, "sha256:" + "e" * 64)
        pipeline.open_commercial_validation(run.run_id)
        with self.assertRaises(FoundryError):
            pipeline.finalize_retained_genome(
                run.run_id,
                genome_name="invalid",
                genome_version="1.0.0",
                capability_versions=(),
                time_to_validated_genome_days=0,
                rollback="revoke",
                accountable_actor="alfonso_lopez",
                seal_record_hash="sha256:" + "2" * 64,
            )
        self.assertEqual(
            commercial.get(run.commercial_case_id).stage,
            CommercialStage.QUALIFIED_SIGNAL,
        )


if __name__ == "__main__":
    unittest.main()
