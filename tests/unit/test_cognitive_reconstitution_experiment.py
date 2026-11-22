"""Counterfactual checks for the isolated developmental experiment."""
import json
from pathlib import Path
import unittest

from tests.experiments.reconstitution.experiment import (
    Central, Local, case_one, run, trace,
)


class ReconstitutionExperiment(unittest.TestCase):
    def test_source_retraction_after_a_successful_run(self):
        sources, rules = case_one()
        operators = {rule.name for rule in rules}
        local = Local(rules, sources)
        central = Central(rules)
        trace(local, sources, operators)
        central.solve(sources, operators)
        remaining = {name: claim for name, claim in sources.items() if name not in {"report", "record"}}
        for claims in trace(local, remaining, operators, frozen=False):
            self.assertTrue({"release", "provisional"}.isdisjoint(claims))
            self.assertIn("unrelated", claims)
        self.assertNotIn("release", central.solve(remaining, operators))
        self.assertIn("unrelated", central.memory)

    def test_operator_loss_does_not_revoke_independent_source(self):
        sources, rules = case_one()
        operators = {rule.name for rule in rules}
        local = Local(rules, sources)
        trace(local, sources, operators)
        claims = trace(local, sources, operators - {"a_fast"})
        self.assertTrue({"release", "provisional", "unrelated"} <= claims[-1])
        self.assertNotIn("a_fast", local.memory["d_release"].operators)
        self.assertEqual(local.memory["e_provisional"].sources, {"report"})

    def test_paired_comparisons_and_retained_receipt(self):
        outcome = run()
        recovery = outcome["recovery"]
        self.assertIsNotNone(recovery["adaptive_local"]["first_answer_round"])
        self.assertIsNone(recovery["frozen_local"]["first_answer_round"])
        self.assertEqual(outcome["capsule"], [["decide", 0, "corroborated"]])
        recorded = Path(__file__).resolve().parents[1] / "experiments/reconstitution/results.json"
        self.assertEqual(outcome, json.loads(recorded.read_text()))
