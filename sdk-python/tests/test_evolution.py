"""Tests for the First Evolution Cycle machinery. Stdlib unittest only."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from uniimente_kernel.evolution import (  # noqa: E402
    BRANCH_ARCHETYPES,
    SPIDER_REQUIREMENTS,
    SPIDER_SIDES,
    EvolutionCapsule,
    EvolutionError,
    ExperimentSpec,
    RetainRegressKillDecision,
    SpiderWebAudit,
    StrategyBranch,
    StrategyTree,
    VerifierRecord,
    ClosureController,
)
from uniimente_kernel.ledger import DecisionLedger  # noqa: E402

BOTTLENECK = "publishing family lacks verified outcome observation"


def make_branch(archetype, **over):
    base = dict(
        archetype=archetype,
        governing_assumption=f"{archetype} assumption",
        mechanism=f"{archetype} mechanism",
        required_capabilities=["gate"],
        cost_usd=0.0,
        founder_attention_minutes=30,
        time_to_proof_days=7,
        authority_requirements=["grant"],
        irreversible_downside="none",
        expected_result="verified outcome loop",
        strongest_counterargument="cost exceeds value",
        cheapest_falsification_test="run one cycle",
        kill_condition="external harm observed",
    )
    base.update(over)
    return StrategyBranch(**base)


def full_tree(ledger):
    tree = StrategyTree(ledger, bottleneck=BOTTLENECK)
    for archetype in BRANCH_ARCHETYPES:
        tree.add(make_branch(archetype))
    return tree


def passing_audit(branch_id):
    return SpiderWebAudit(
        branch_id=branch_id,
        sides={s: f"finding for {s}" for s in SPIDER_SIDES},
        mechanism_map={"gate.execute": "default_routing",
                       "ledger": "proof_and_truth"},
        requirements={r: True for r in SPIDER_REQUIREMENTS},
    )


def experiment():
    return ExperimentSpec(
        decisive_unknown="does outcome observation close the loop?",
        hypothesis="gate-mediated publish beats manual baseline",
        method="adopt gate, measure",
        metrics={"mediated_coverage_pct": "higher", "suite_size": "higher"},
        baseline={"mediated_coverage_pct": 0.0, "suite_size": 25.0},
        reversibility="reversible",
        budget_usd=0.0,
        kill_condition="any unmediated live effect",
    )


def verifier(level=1):
    return VerifierRecord(level=level, verifier_name="pytest-suite",
                          evidence_ref="sha256:" + "b" * 64)


class EvolutionFixture(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.ledger = DecisionLedger(path=os.path.join(self.dir.name, "l.jsonl"))

    def tearDown(self):
        self.dir.cleanup()

    def events(self, name):
        return self.ledger.replay(event=name)


class TestBranchAndTree(EvolutionFixture):
    def test_branch_requires_all_fields(self):
        with self.assertRaises(EvolutionError):
            make_branch("do_nothing", mechanism="").validate()

    def test_branch_rejects_unknown_archetype(self):
        with self.assertRaises(EvolutionError):
            make_branch("sneaky_path").validate()

    def test_branch_rejects_negative_cost(self):
        with self.assertRaises(EvolutionError):
            make_branch("do_nothing", cost_usd=-1).validate()

    def test_selection_refused_until_all_archetypes_generated(self):
        tree = StrategyTree(self.ledger, bottleneck=BOTTLENECK)
        branch = tree.add(make_branch("fastest_path"))
        with self.assertRaises(EvolutionError) as ctx:
            tree.select(branch.branch_id, decider="alfonso-lopez",
                        rationale="x", loss_reasons={})
        self.assertIn("archetypes not yet generated", str(ctx.exception))

    def test_selection_requires_loss_reason_for_every_loser(self):
        tree = full_tree(self.ledger)
        winner = next(iter(tree.branches.values()))
        with self.assertRaises(EvolutionError):
            tree.select(winner.branch_id, decider="alfonso-lopez",
                        rationale="x", loss_reasons={})

    def test_rejected_branches_preserved_with_revival_evidence(self):
        tree = full_tree(self.ledger)
        winner = next(iter(tree.branches.values()))
        losers = [b.branch_id for b in tree.branches.values()
                  if b.branch_id != winner.branch_id]
        reasons = {lid: f"{tree.branches[lid].archetype} lost on founder attention"
                   for lid in losers}
        revival = {losers[0]: "if capital falls below threshold"}
        tree.select(winner.branch_id, decider="alfonso-lopez",
                    rationale="highest verified ownership per unit attention",
                    loss_reasons=reasons, revival_evidence=revival)
        rejected = tree.rejected()
        self.assertEqual(len(rejected), 10)
        self.assertTrue(all(r.loss_reason for r in rejected))
        self.assertEqual(tree.branches[losers[0]].revival_evidence,
                         "if capital falls below threshold")
        self.assertEqual(len(self.events("strategy_branch_rejected")), 10)
        self.assertEqual(len(self.events("strategy_branch_selected")), 1)


class TestSpiderWeb(EvolutionFixture):
    def test_pass(self):
        ok, failures = passing_audit("b1").evaluate()
        self.assertTrue(ok)
        self.assertEqual(failures, [])

    def test_missing_side_fails(self):
        audit = passing_audit("b1")
        audit.sides.pop(SPIDER_SIDES[0])
        ok, failures = audit.evaluate()
        self.assertFalse(ok)
        self.assertTrue(any("sides" in f for f in failures))

    def test_decorative_mechanism_fails(self):
        audit = passing_audit("b1")
        audit.mechanism_map["vanity_dashboard"] = None
        ok, failures = audit.evaluate()
        self.assertFalse(ok)
        self.assertEqual(audit.decorative_mechanisms(), ["vanity_dashboard"])

    def test_unmet_requirement_fails(self):
        audit = passing_audit("b1")
        audit.requirements["external_consequence"] = False
        ok, failures = audit.evaluate()
        self.assertFalse(ok)
        self.assertTrue(any("external_consequence" in f for f in failures))


class TestExperiment(EvolutionFixture):
    def test_must_be_reversible(self):
        spec = experiment()
        spec.reversibility = "costly_to_reverse"
        with self.assertRaises(EvolutionError):
            spec.validate()

    def test_metric_needs_baseline(self):
        spec = experiment()
        spec.metrics["orphan"] = "higher"
        with self.assertRaises(EvolutionError):
            spec.validate()

    def test_beats_baseline_directions(self):
        spec = experiment()
        self.assertTrue(spec.beats_baseline(
            {"mediated_coverage_pct": 100.0, "suite_size": 39.0}))
        self.assertFalse(spec.beats_baseline(
            {"mediated_coverage_pct": 100.0, "suite_size": 25.0}))  # tie is not beating
        self.assertFalse(spec.beats_baseline(
            {"mediated_coverage_pct": -1.0, "suite_size": 39.0}))  # below baseline
        self.assertFalse(spec.beats_baseline(
            {"mediated_coverage_pct": 100.0}))  # missing metric


class TestVerifierAndDecision(EvolutionFixture):
    def test_level_bounds(self):
        with self.assertRaises(EvolutionError):
            VerifierRecord(level=8, verifier_name="x",
                           evidence_ref="sha256:" + "a" * 64).validate()

    def test_levels_six_and_seven_cannot_authorize_retain(self):
        for level in (6, 7):
            with self.assertRaises(EvolutionError):
                RetainRegressKillDecision(
                    decision="retain", rationale="x",
                    evidence_refs=["sha256:" + "a" * 64],
                    verifier=verifier(level),
                ).validate()

    def test_retain_allowed_at_authorizing_levels(self):
        for level in (1, 2, 3, 4, 5):
            RetainRegressKillDecision(
                decision="retain", rationale="x",
                evidence_refs=["sha256:" + "a" * 64],
                verifier=verifier(level),
            ).validate()


class TestClosure(EvolutionFixture):
    def test_four_states(self):
        controller = ClosureController(self.ledger)
        self.assertEqual(controller.evaluate(
            "c1", internal_metric_met=True, external_consequence_met=True), "closed")
        self.assertEqual(controller.evaluate(
            "c2", internal_metric_met=False, external_consequence_met=True), "partially_closed")
        self.assertEqual(controller.evaluate(
            "c3", internal_metric_met=False, external_consequence_met=False), "open")

    def test_false_closure_triggers_investigation(self):
        controller = ClosureController(self.ledger)
        state = controller.evaluate(
            "c4", internal_metric_met=True, external_consequence_met=False)
        self.assertEqual(state, "falsely_closed")
        self.assertEqual(len(self.events("closure_investigation_opened")), 1)


class TestCapsule(EvolutionFixture):
    def _cycle(self, **over):
        tree = full_tree(self.ledger)
        winner = next(iter(tree.branches.values()))
        losers = [b.branch_id for b in tree.branches.values()
                  if b.branch_id != winner.branch_id]
        tree.select(winner.branch_id, decider="alfonso-lopez",
                    rationale="strongest proof per unit attention",
                    loss_reasons={lid: "weaker proof" for lid in losers})
        args = dict(
            bottleneck=BOTTLENECK,
            tree=tree,
            selected_branch_id=winner.branch_id,
            audit=passing_audit(winner.branch_id),
            experiment=experiment(),
            outcome={"mediated_coverage_pct": 100.0, "suite_size": 39.0},
            outcome_evidence_refs=["sha256:" + "c" * 64],
            verifier=verifier(1),
        )
        args.update(over)
        return EvolutionCapsule(self.ledger).complete_cycle(**args)

    def test_retain_cycle_ledgers_everything(self):
        capsule = self._cycle()
        self.assertEqual(capsule["decision"]["decision"], "retain")
        self.assertTrue(capsule["beats_baseline"])
        self.assertEqual(capsule["closure_state"], "closed")
        for event in ("spider_web_audit", "closure_evaluated",
                      "evolution_cycle_completed", "strategy_branch_selected"):
            self.assertTrue(self.events(event), event)
        ok, bad = self.ledger.verify_chain()
        self.assertTrue(ok, bad)

    def test_regress_when_not_beating_baseline(self):
        capsule = self._cycle(outcome={"mediated_coverage_pct": 0.0,
                                       "suite_size": 39.0})
        self.assertEqual(capsule["decision"]["decision"], "regress")
        self.assertIn("baseline", capsule["decision"]["rationale"])

    def test_kill_condition_preempts_everything(self):
        capsule = self._cycle(kill_condition_fired=True)
        self.assertEqual(capsule["decision"]["decision"], "kill")

    def test_hypothesis_level_verifier_regresses_even_when_winning(self):
        capsule = self._cycle(verifier=verifier(7))
        self.assertEqual(capsule["decision"]["decision"], "regress")
        self.assertIn("may not authorize", capsule["decision"]["rationale"])

    def test_false_closure_regresses_with_investigation(self):
        capsule = self._cycle(external_consequence_met=False)
        self.assertEqual(capsule["decision"]["decision"], "regress")
        self.assertEqual(capsule["closure_state"], "falsely_closed")
        self.assertEqual(len(self.events("closure_investigation_opened")), 1)

    def test_audit_failure_regresses(self):
        audit = passing_audit("b1")
        audit.requirements["kill_criteria"] = False
        capsule = self._cycle(audit=audit)
        self.assertEqual(capsule["decision"]["decision"], "regress")


if __name__ == "__main__":
    unittest.main()
