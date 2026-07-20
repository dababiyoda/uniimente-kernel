import unittest

from foundry import (
    AdvantageFoundry, CapabilityNeed, CommercialClosureCompiler, CommercialStage,
    FoundryError, OpportunitySpec, StrategyBranch, STRATEGY_ROUTES,
)
from provenance.ledger import EvidenceLedger


def opportunity():
    return OpportunitySpec(
        opportunity_id="opp-1", buyer="buyer", beneficiary="user", pain_owner="ops",
        budget_owner="cfo", recurring_transaction="verify workflow", broken_state="proof missing",
        trapped_value_usd=10000, accepted_artifact="verification receipt",
        external_consequence="buyer changes workflow", lawful_path="paid pilot",
        evidence_refs=("sha256:" + "a" * 64,),
    )


def branches():
    return [
        StrategyBranch(
            route=route, mechanism=f"mechanism-{route}", governing_assumption="buyer cares",
            strongest_counterargument="status quo may be sufficient",
            cheapest_falsification_test="ask for a paid pilot", kill_condition="no commitment",
            cost_usd=10 + index, time_to_proof_days=1 + index,
            expected_value_usd=1000 + index * 100, reversibility=1.0,
            evidence_quality=0.8, founder_hours=1.0,
            required_capabilities=("research.read",),
        )
        for index, route in enumerate(STRATEGY_ROUTES)
    ]


def architecture():
    foundry = AdvantageFoundry()
    winner, _ = foundry.complete_route_tournament(branches())
    return foundry.compile_architecture(
        opportunity(), winner,
        (CapabilityNeed("research.read", "research", ("request",), ("result",), "read_only", 10),),
        control_surface="proof", success_metrics=("payment",), kill_conditions=("no buyer",),
    )


def evidence(label):
    return (f"sha256:{label * 64}"[:71],)


def advance_to_reconciled(compiler, case_id, *, margin=200):
    steps = (
        (CommercialStage.BUYER_CONFIRMED, {"buyer_ref": "buyer:1"}),
        (CommercialStage.PROBLEM_EVIDENCE_CONFIRMED, {"problem_evidence_ref": "proof:1"}),
        (CommercialStage.OFFER_APPROVED, {"offer_ref": "offer:1", "human_approval_ref": "approval:1"}),
        (CommercialStage.OUTREACH_AUTHORIZED, {"human_approval_ref": "approval:2", "gate_receipt_hash": "sha256:" + "a" * 64}),
        (CommercialStage.BUYER_COMMITMENT, {"commitment_ref": "loi:1"}),
        (CommercialStage.PAYMENT_OR_BINDING_COMMITMENT, {"payment_or_contract_ref": "payment:1", "payment_usd": 500}),
        (CommercialStage.DELIVERY_AUTHORIZED, {"human_approval_ref": "approval:3", "gate_receipt_hash": "sha256:" + "b" * 64}),
        (CommercialStage.DELIVERY_COMPLETED, {"delivery_receipt_ref": "delivery:1"}),
        (CommercialStage.CUSTOMER_ACCEPTANCE, {"acceptance_ref": "acceptance:1"}),
        (CommercialStage.OUTCOME_OBSERVED, {"outcome_ref": "outcome:1", "externally_verified": True}),
        (CommercialStage.ECONOMICS_RECONCILED, {"reconciliation_ref": "reconcile:1", "contribution_margin_usd": margin, "founder_hours": 3, "metric_results": {"value": 1}}),
    )
    for index, (stage, payload) in enumerate(steps):
        compiler.advance(
            case_id,
            stage,
            actor="alfonso_lopez",
            evidence_refs=evidence(chr(99 + index)),
            payload=payload,
        )


class CommercialClosureTests(unittest.TestCase):
    def test_stages_cannot_be_skipped(self):
        compiler = CommercialClosureCompiler()
        case = compiler.open_case(opportunity(), architecture())
        with self.assertRaises(FoundryError):
            compiler.advance(
                case.case_id,
                CommercialStage.OFFER_APPROVED,
                actor="alfonso_lopez",
                evidence_refs=evidence("c"),
                payload={"offer_ref": "offer", "human_approval_ref": "approval"},
            )

    def test_consequential_authorization_requires_gate_receipt(self):
        compiler = CommercialClosureCompiler()
        case = compiler.open_case(opportunity(), architecture())
        compiler.advance(
            case.case_id, CommercialStage.BUYER_CONFIRMED,
            actor="alfonso_lopez", evidence_refs=evidence("c"),
            payload={"buyer_ref": "buyer"},
        )
        compiler.advance(
            case.case_id, CommercialStage.PROBLEM_EVIDENCE_CONFIRMED,
            actor="alfonso_lopez", evidence_refs=evidence("d"),
            payload={"problem_evidence_ref": "proof"},
        )
        compiler.advance(
            case.case_id, CommercialStage.OFFER_APPROVED,
            actor="alfonso_lopez", evidence_refs=evidence("e"),
            payload={"offer_ref": "offer", "human_approval_ref": "approval"},
        )
        with self.assertRaises(FoundryError):
            compiler.advance(
                case.case_id, CommercialStage.OUTREACH_AUTHORIZED,
                actor="alfonso_lopez", evidence_refs=evidence("f"),
                payload={"human_approval_ref": "approval"},
            )

    def test_verified_paid_path_builds_external_outcome(self):
        compiler = CommercialClosureCompiler()
        case = compiler.open_case(opportunity(), architecture())
        advance_to_reconciled(compiler, case.case_id)
        outcome = compiler.build_external_outcome(case.case_id)
        self.assertEqual(outcome.payment_usd, 500)
        self.assertTrue(outcome.accepted_delivery)
        self.assertTrue(outcome.externally_verified)
        self.assertEqual(outcome.contribution_margin_usd, 200)

    def test_only_retain_can_mark_genome_sealed(self):
        compiler = CommercialClosureCompiler()
        case = compiler.open_case(opportunity(), architecture())
        advance_to_reconciled(compiler, case.case_id)
        compiler.decide(
            case.case_id, "MODIFY", actor="alfonso_lopez",
            evidence_ref="decision:1", human_approval_ref="approval:4",
        )
        with self.assertRaises(FoundryError):
            compiler.mark_genome_sealed(
                case.case_id, genome_key="audit@1", actor="alfonso_lopez",
                seal_record_hash="sha256:" + "f" * 64,
            )

    def test_ledger_rebuild_preserves_commercial_case(self):
        ledger = EvidenceLedger("sha256:" + "0" * 64)
        compiler = CommercialClosureCompiler(ledger)
        case = compiler.open_case(opportunity(), architecture())
        advance_to_reconciled(compiler, case.case_id)
        compiler.decide(
            case.case_id, "RETAIN", actor="alfonso_lopez",
            evidence_ref="decision:1", human_approval_ref="approval:4",
        )
        compiler.mark_genome_sealed(
            case.case_id, genome_key="audit@1.0.0", actor="alfonso_lopez",
            seal_record_hash="sha256:" + "f" * 64,
        )
        restarted = CommercialClosureCompiler(ledger)
        rebuilt = restarted.get(case.case_id)
        self.assertEqual(rebuilt.stage, CommercialStage.CAPABILITY_GENOME_SEALED)
        self.assertEqual(rebuilt.sealed_genome_key, "audit@1.0.0")
        self.assertTrue(ledger.verify_chain()[0])


if __name__ == "__main__":
    unittest.main()
