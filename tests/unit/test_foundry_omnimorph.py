import unittest

from capabilities.genome import AuthorityEnvelope, CapabilityGenome, GenomeRegistry
from foundry import (
    AdvantageFoundry, CapabilityNeed, ClosureState, ExternalOutcome, FoundryError,
    OpportunitySpec, StrategyBranch, STRATEGY_ROUTES,
)
from omnimorph import OmnimorphEngine, RatificationRecord


def opportunity():
    return OpportunitySpec(
        opportunity_id="opp-1", buyer="buyer", beneficiary="user", pain_owner="ops",
        budget_owner="cfo", recurring_transaction="verify workflow", broken_state="proof missing",
        trapped_value_usd=10000, accepted_artifact="verification receipt",
        external_consequence="buyer changes workflow", lawful_path="paid pilot",
        evidence_refs=("sha256:" + "a" * 64,),
    )


def branches():
    result = []
    for i, route in enumerate(STRATEGY_ROUTES):
        result.append(StrategyBranch(
            route=route, mechanism=f"mechanism-{route}", governing_assumption="buyer cares",
            strongest_counterargument="status quo may be sufficient",
            cheapest_falsification_test="ask for a paid pilot", kill_condition="no commitment",
            cost_usd=10 + i, time_to_proof_days=1 + i, expected_value_usd=1000 + i * 100,
            reversibility=1.0, evidence_quality=0.8, founder_hours=1.0,
            required_capabilities=("research.read", "offer.compile"),
        ))
    return result


def registry():
    result = GenomeRegistry()
    for name, consequence_class, budget in (
        ("research.read", "read_only", 100),
        ("offer.compile", "internal_write", 200),
    ):
        result.register(CapabilityGenome(
            name=name, version="1.0.0", description=name,
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


class FoundryTests(unittest.TestCase):
    def test_complete_tournament_required(self):
        foundry = AdvantageFoundry()
        with self.assertRaises(FoundryError):
            foundry.complete_route_tournament(branches()[:-1])
        winner, losers = foundry.complete_route_tournament(branches())
        self.assertEqual(len(losers), 10)
        self.assertIn(winner.route, STRATEGY_ROUTES)

    def test_changed_content_replay_refused(self):
        foundry = AdvantageFoundry()
        foundry.intake(opportunity())
        changed = OpportunitySpec(**{**opportunity().__dict__, "buyer": "other"})
        with self.assertRaises(FoundryError):
            foundry.intake(changed)

    def test_false_closure_cannot_seal(self):
        foundry = AdvantageFoundry()
        winner, _ = foundry.complete_route_tournament(branches())
        architecture = foundry.compile_architecture(
            opportunity(), winner,
            (CapabilityNeed("research.read", "research", ("request",), ("result",), "read_only", 10),),
            control_surface="proof",
            success_metrics=("payment",),
            kill_conditions=("no buyer",),
        )
        false_outcome = ExternalOutcome(
            100, True, False, 50, 2, True, {}, ("sha256:" + "b" * 64,),
        )
        self.assertEqual(foundry.closure_state(false_outcome), ClosureState.FALSELY_CLOSED)
        with self.assertRaises(FoundryError):
            foundry.seal_advantage_genome(
                "x", "1", architecture, ("research.read@1.0.0",), false_outcome,
                time_to_validated_genome_days=1, rollback="revoke",
            )

    def test_paid_verified_outcome_seals_immutable_genome(self):
        foundry = AdvantageFoundry()
        winner, _ = foundry.complete_route_tournament(branches())
        architecture = foundry.compile_architecture(
            opportunity(), winner,
            (CapabilityNeed("research.read", "research", ("request",), ("result",), "read_only", 10),),
            control_surface="proof",
            success_metrics=("payment",),
            kill_conditions=("no buyer",),
        )
        outcome = ExternalOutcome(
            500, True, True, 200, 3, True,
            {"payment": 1}, ("sha256:" + "b" * 64,),
        )
        genome = foundry.seal_advantage_genome(
            "audit", "1.0.0", architecture, ("research.read@1.0.0",), outcome,
            time_to_validated_genome_days=7, rollback="revoke",
        )
        self.assertEqual(genome.contribution_margin_usd, 200)
        with self.assertRaises(FoundryError):
            foundry.seal_advantage_genome(
                "audit", "1.0.0", architecture, (), outcome,
                time_to_validated_genome_days=7, rollback="revoke",
            )


class OmnimorphTests(unittest.TestCase):
    def architecture(self):
        foundry = AdvantageFoundry()
        winner, _ = foundry.complete_route_tournament(branches())
        return foundry.compile_architecture(
            opportunity(), winner,
            (
                CapabilityNeed("research.read", "research", ("request",), ("result",), "read_only", 10),
                CapabilityNeed("offer.compile", "compile offer", ("request",), ("result",), "internal_write", 20),
            ),
            control_surface="proof",
            success_metrics=("payment",),
            kill_conditions=("no buyer",),
        )

    def test_compose_simulate_ratify_and_gate_activate(self):
        engine = OmnimorphEngine(registry())
        manifest = engine.compose(
            self.architecture(),
            {"research.read": "1.0.0", "offer.compile": "1.0.0"},
            objective="build audit organ",
            consequence_ceiling="internal_write",
            expires_at="2026-08-01T00:00:00Z",
        )
        report = engine.simulate(manifest)
        self.assertTrue(report.passed)
        ratification = RatificationRecord(
            manifest.digest, "alfonso_lopez", "sig:founder", "2026-08-01T00:00:00Z",
        )
        proposal = engine.propose_activation(manifest, report, ratification)
        self.assertEqual(proposal.status, "PROPOSED_NOT_EXECUTED")
        activated = engine.record_gate_activation(manifest, "sha256:" + "c" * 64)
        self.assertEqual(activated.status, "GATE_ACTIVATED")

    def test_self_ratification_refused(self):
        engine = OmnimorphEngine(registry())
        manifest = engine.compose(
            self.architecture(),
            {"research.read": "1.0.0", "offer.compile": "1.0.0"},
            objective="x", consequence_ceiling="internal_write",
            expires_at="2026-08-01T00:00:00Z",
        )
        with self.assertRaises(FoundryError):
            engine.propose_activation(
                manifest,
                engine.simulate(manifest),
                RatificationRecord(
                    manifest.digest, "OMNIMORPH", "sig:x", "2026-08-01T00:00:00Z",
                ),
            )

    def test_out_of_envelope_capability_refused(self):
        engine = OmnimorphEngine(registry())
        architecture = self.architecture()
        oversized = tuple(
            CapabilityNeed(
                need.capability, need.purpose, need.inputs, need.outputs,
                need.consequence_class, 1000,
            )
            for need in architecture.capability_needs
        )
        bad_architecture = type(architecture)(
            **{**architecture.__dict__, "capability_needs": oversized},
        )
        with self.assertRaises(FoundryError):
            engine.compose(
                bad_architecture,
                {"research.read": "1.0.0", "offer.compile": "1.0.0"},
                objective="x", consequence_ceiling="internal_write",
                expires_at="2026-08-01T00:00:00Z",
            )

    def test_payment_without_verified_outcome_refused(self):
        with self.assertRaises(FoundryError):
            OmnimorphEngine.validate_paid_outcome(
                ExternalOutcome(
                    100, True, False, 50, 2, True, {},
                    ("sha256:" + "d" * 64,),
                ),
            )


if __name__ == "__main__":
    unittest.main()
