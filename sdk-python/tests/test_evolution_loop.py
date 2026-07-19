"""Tests for the Fast Capability Evolution loop. Stdlib unittest only."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from uniimente_kernel.evolution import (  # noqa: E402
    BRANCH_ARCHETYPES,
    SPIDER_REQUIREMENTS,
    SPIDER_SIDES,
    EvolutionError,
    ExperimentSpec,
    VerifierRecord,
)
from uniimente_kernel.evolution_loop import (  # noqa: E402
    BranchCandidate,
    BranchGenerator,
    EvolutionLoop,
    FailureAnalyzer,
    ImprovementProposal,
    IsolatedResult,
    IsolatedRunner,
    OutcomeComparator,
)
from uniimente_kernel.ledger import DecisionLedger  # noqa: E402

BOTTLENECK = "toy capability underperforms its baseline"


def read_records(path):
    with open(path, "r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]

TOY_MODULE = '''"""Toy experiment module for loop tests."""
import os
import sys
import time


def measure(value=1.0, **kwargs):
    return {"score": float(value)}


def boom(**kwargs):
    raise RuntimeError("boom")


def sleepy(seconds=5.0, **kwargs):
    time.sleep(seconds)
    return {"score": 1.0}


def exit3(**kwargs):
    sys.exit(3)


def bad_shape(**kwargs):
    return {"score": "high"}


def empty(**kwargs):
    return {}


def chatty(**kwargs):
    print("junk line one")
    print("junk line two")
    return {"score": 3.0}


def env_probe(**kwargs):
    return {
        "score": 1.0,
        "has_secret": 1.0 if "SENTINEL_SECRET" in os.environ else 0.0,
        "in_tmp_cwd": 1.0 if "uniimente_iso_" in os.getcwd() else 0.0,
    }
'''


def branch_fields(archetype, **over):
    base = dict(
        governing_assumption=f"{archetype} assumption",
        mechanism=f"{archetype} mechanism",
        required_capabilities=["loop"],
        cost_usd=0.0,
        founder_attention_minutes=15,
        time_to_proof_days=1,
        authority_requirements=["grant"],
        irreversible_downside="none",
        expected_result="score beats baseline",
        strongest_counterargument="measurement noise",
        cheapest_falsification_test="rerun the isolated entry",
        kill_condition="any side effect observed",
    )
    base.update(over)
    return base


def entry(function, **kwargs):
    return {"module": "toy_exp", "function": function, "kwargs": kwargs}


def candidate(archetype, function="measure", **kwargs):
    return {
        "archetype": archetype,
        "branch_fields": branch_fields(archetype),
        "entry": entry(function, **kwargs),
    }


def eleven(value_by_archetype=None, function_by_archetype=None):
    values = value_by_archetype or {}
    functions = function_by_archetype or {}
    return [
        candidate(
            archetype,
            function=functions.get(archetype, "measure"),
            value=values.get(archetype, 1.0),
        )
        for archetype in BRANCH_ARCHETYPES
    ]


def experiment(metric_direction="higher", baseline=1.0):
    return ExperimentSpec(
        decisive_unknown="can the toy capability beat its baseline?",
        hypothesis="a higher configured value raises the measured score",
        method="isolated subprocess measurement per branch",
        metrics={"score": metric_direction},
        baseline={"score": baseline},
        reversibility="reversible",
        budget_usd=0.0,
        kill_condition="any side effect observed",
    )


class LoopFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        with open(os.path.join(self.tmp, "toy_exp.py"), "w", encoding="utf-8") as handle:
            handle.write(TOY_MODULE)
        self.ledger = DecisionLedger(os.path.join(self.tmp, "ledger.jsonl"))

    def context(self, candidates):
        return {"candidates": candidates, "pythonpath": self.tmp}

    def loop_args(self, **over):
        args = dict(
            bottleneck=BOTTLENECK,
            context=self.context(eleven()),
            experiment=experiment(),
            audit_sides={s: f"finding {s}" for s in SPIDER_SIDES},
            mechanism_map={"loop.run_cycle": "default_routing"},
            requirements={r: True for r in SPIDER_REQUIREMENTS},
            verifier=VerifierRecord(
                level=1,
                verifier_name="isolated runner, deterministic",
                evidence_ref="sha256:" + "0" * 64,
            ),
            decider="alfonso-lopez",
            rationale="highest-margin branch that beats baseline wins",
            outcome_evidence_refs=["sha256:" + "1" * 64],
        )
        args.update(over)
        return args

    def make_loop(self, **kwargs):
        context = kwargs.pop("context", self.context(eleven()))
        for candidate_dict in context["candidates"]:
            candidate_dict["entry"]["pythonpath"] = self.tmp
        return EvolutionLoop(self.ledger, **kwargs), context


class TestCandidateValidation(unittest.TestCase):
    def test_valid_candidate_assembles_branch(self):
        c = BranchCandidate(
            archetype="fastest_path",
            branch_fields=branch_fields("fastest_path"),
            entry=entry("measure", value=2.0),
        ).validate()
        branch = c.to_branch(bottleneck="x")
        self.assertEqual(branch.archetype, "fastest_path")
        self.assertEqual(branch.bottleneck, "x")

    def test_unknown_archetype_rejected(self):
        with self.assertRaises(EvolutionError):
            BranchCandidate("preferred_idea", branch_fields("x"), entry("measure")).validate()

    def test_missing_entry_module_rejected(self):
        with self.assertRaises(EvolutionError):
            BranchCandidate("do_nothing", branch_fields("x"), {"function": "f"}).validate()

    def test_non_dict_kwargs_rejected(self):
        with self.assertRaises(EvolutionError):
            BranchCandidate(
                "do_nothing", branch_fields("x"),
                {"module": "m", "function": "f", "kwargs": [1]},
            ).validate()

    def test_non_string_pythonpath_rejected(self):
        with self.assertRaises(EvolutionError):
            BranchCandidate(
                "do_nothing", branch_fields("x"),
                {"module": "m", "function": "f", "pythonpath": 7},
            ).validate()

    def test_non_json_safe_fields_rejected(self):
        fields = branch_fields("x")
        fields["mechanism"] = object()
        with self.assertRaises(EvolutionError):
            BranchCandidate("do_nothing", fields, entry("measure")).validate()

    def test_missing_branch_field_rejected_at_generation(self):
        fields = branch_fields("x")
        del fields["kill_condition"]
        with self.assertRaises(EvolutionError):
            BranchCandidate("do_nothing", fields, entry("measure")).validate()


class TestGenerator(unittest.TestCase):
    def test_missing_archetype_named(self):
        candidates = eleven()
        candidates = [c for c in candidates if c["archetype"] != "do_nothing"]
        with self.assertRaises(EvolutionError) as ctx:
            BranchGenerator().propose(bottleneck="b", context={"candidates": candidates})
        self.assertIn("do_nothing", str(ctx.exception))

    def test_duplicate_archetype_rejected(self):
        candidates = eleven()
        candidates[1] = candidate("fastest_path", value=9.0)
        with self.assertRaises(EvolutionError):
            BranchGenerator().propose(bottleneck="b", context={"candidates": candidates})

    def test_injected_proposer_validated_identically(self):
        def proposer(*, bottleneck, context):
            return [{"archetype": "fastest_path", "branch_fields": {}, "entry": {}}]

        with self.assertRaises(EvolutionError):
            BranchGenerator(proposer=proposer).propose(bottleneck="b", context={})

    def test_context_candidates_used_without_proposer(self):
        out = BranchGenerator().propose(bottleneck="b", context={"candidates": eleven()})
        self.assertEqual(len(out), 11)


class TestRunner(LoopFixture):
    def run_entry(self, function, timeout=10.0, **kwargs):
        runner = IsolatedRunner(timeout_seconds=timeout)
        e = entry(function, **kwargs)
        e["pythonpath"] = self.tmp
        return runner.run(e)

    def test_ok_path_returns_float_metrics(self):
        result = self.run_entry("measure", value=2.5)
        self.assertTrue(result.ok)
        self.assertEqual(result.outcome, {"score": 2.5})

    def test_environment_is_scrubbed(self):
        os.environ["SENTINEL_SECRET"] = "should-not-leak"
        try:
            result = self.run_entry("env_probe")
        finally:
            del os.environ["SENTINEL_SECRET"]
        self.assertTrue(result.ok)
        self.assertEqual(result.outcome["has_secret"], 0.0)
        self.assertEqual(result.outcome["in_tmp_cwd"], 1.0)

    def test_timeout_classified(self):
        result = self.run_entry("sleepy", timeout=0.5, seconds=5.0)
        self.assertFalse(result.ok)
        self.assertEqual(result.failure_class, "timeout")

    def test_exception_classified(self):
        result = self.run_entry("boom")
        self.assertFalse(result.ok)
        self.assertEqual(result.failure_class, "exception")
        self.assertIn("RuntimeError", result.detail)

    def test_nonzero_exit_classified(self):
        result = self.run_entry("exit3")
        self.assertFalse(result.ok)
        self.assertEqual(result.failure_class, "nonzero_exit")

    def test_non_numeric_metric_rejected(self):
        result = self.run_entry("bad_shape")
        self.assertFalse(result.ok)
        self.assertEqual(result.failure_class, "invalid_outcome")

    def test_empty_outcome_rejected(self):
        result = self.run_entry("empty")
        self.assertFalse(result.ok)
        self.assertEqual(result.failure_class, "invalid_outcome")

    def test_chatty_stdout_still_parses_final_line(self):
        result = self.run_entry("chatty")
        self.assertTrue(result.ok)
        self.assertEqual(result.outcome["score"], 3.0)


class TestAnalyzerAndComparator(unittest.TestCase):
    def test_classify_ok_is_none(self):
        analyzer = FailureAnalyzer()
        ok = IsolatedResult(True, {"score": 1.0}, None, "", 0.1)
        self.assertIsNone(analyzer.classify(branch_id="b", archetype="a", result=ok))

    def test_summarize_counts_by_class(self):
        analyzer = FailureAnalyzer()
        records = [
            analyzer.classify(
                branch_id=b, archetype=a,
                result=IsolatedResult(False, None, cls, "d", 0.1),
            )
            for b, a, cls in [("1", "x", "timeout"), ("2", "y", "timeout"), ("3", "z", "exception")]
        ]
        summary = analyzer.summarize([r for r in records if r])
        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["by_class"], {"timeout": 2, "exception": 1})

    def test_tie_does_not_beat_and_sorts_last(self):
        comparator = OutcomeComparator()
        ranking = comparator.rank(
            experiment=experiment(),
            outcomes={"tie": {"score": 1.0}, "beat": {"score": 2.0}, "lose": {"score": 0.5}},
        )
        self.assertEqual(ranking[0]["branch_id"], "beat")
        self.assertFalse(next(r for r in ranking if r["branch_id"] == "tie")["beats_baseline"])

    def test_lower_direction_respected(self):
        comparator = OutcomeComparator()
        ranking = comparator.rank(
            experiment=experiment(metric_direction="lower", baseline=5.0),
            outcomes={"down": {"score": 2.0}, "up": {"score": 8.0}},
        )
        self.assertEqual(ranking[0]["branch_id"], "down")

    def test_margin_picks_stronger_beater(self):
        comparator = OutcomeComparator()
        ranking = comparator.rank(
            experiment=experiment(),
            outcomes={"small": {"score": 1.5}, "big": {"score": 4.0}},
        )
        self.assertEqual(ranking[0]["branch_id"], "big")
        self.assertGreater(ranking[0]["margin"], ranking[1]["margin"])


class TestLoop(LoopFixture):
    def test_happy_path_retain_and_proposal_shape(self):
        candidates = eleven(value_by_archetype={"maximum_ownership": 2.0})
        loop, context = self.make_loop(context={"candidates": candidates, "pythonpath": self.tmp})
        args = self.loop_args(context=context)
        proposal = loop.run_cycle(**args)

        self.assertIsInstance(proposal, ImprovementProposal)
        self.assertEqual(proposal.decision, "retain")
        self.assertEqual(proposal.selected_archetype, "maximum_ownership")
        self.assertEqual(proposal.verifier_level, 1)
        self.assertFalse(proposal.applied)
        self.assertFalse(hasattr(proposal, "apply"))

    def test_winner_is_highest_margin_beater(self):
        candidates = eleven(value_by_archetype={"fastest_path": 2.0, "maximum_ownership": 3.0})
        loop, context = self.make_loop(context={"candidates": candidates, "pythonpath": self.tmp})
        args = self.loop_args(context=context)
        proposal = loop.run_cycle(**args)
        self.assertEqual(proposal.decision, "retain")
        self.assertEqual(proposal.selected_archetype, "maximum_ownership")
        self.assertEqual(proposal.outcome, {"score": 3.0})

        events = [record["event"] for record in read_records(self.ledger.path)]
        for expected in [
            "evolution_loop_started",
            "branch_candidate_generated",
            "isolated_run_completed",
            "failure_analysis_completed",
            "comparison_completed",
            "strategy_branch_selected",
            "spider_web_audit",
            "closure_evaluated",
            "evolution_cycle_completed",
            "improvement_proposal_emitted",
        ]:
            self.assertIn(expected, events)
        self.assertEqual(events.count("branch_candidate_generated"), 11)
        self.assertEqual(events.count("isolated_run_completed"), 11)
        ok, msg = self.ledger.verify_chain()
        self.assertTrue(ok, msg)

    def test_no_beater_selects_do_nothing_and_regresses(self):
        loop, context = self.make_loop()  # all values tie at baseline 1.0
        args = self.loop_args(context=context)
        proposal = loop.run_cycle(**args)
        self.assertEqual(proposal.selected_archetype, "do_nothing")
        self.assertEqual(proposal.decision, "regress")
        self.assertIn("did not beat baseline", proposal.summary)

    def test_failures_classified_and_losers_carry_reasons(self):
        functions = {
            "fastest_path": "boom",
            "lowest_capital": "exit3",
            "maximum_reversibility": "sleepy",
        }
        candidates = eleven(
            value_by_archetype={"maximum_ownership": 2.0},
            function_by_archetype=functions,
        )
        runner = IsolatedRunner(timeout_seconds=0.5)
        loop = EvolutionLoop(self.ledger, runner=runner)
        context = {"candidates": candidates, "pythonpath": self.tmp}
        for c in context["candidates"]:
            c["entry"]["pythonpath"] = self.tmp
        args = self.loop_args(context=context)
        proposal = loop.run_cycle(**args)
        self.assertEqual(proposal.decision, "retain")
        self.assertEqual(proposal.selected_archetype, "maximum_ownership")

        analysis = [
            record for record in read_records(self.ledger.path)
            if record["event"] == "failure_analysis_completed"
        ][0]
        self.assertEqual(analysis["payload"]["total"], 3)
        self.assertEqual(
            analysis["payload"]["by_class"],
            {"exception": 1, "nonzero_exit": 1, "timeout": 1},
        )
        rejected = [
            record["payload"] for record in read_records(self.ledger.path)
            if record["event"] == "strategy_branch_rejected"
        ]
        reasons = {r["archetype"]: r["loss_reason"] for r in rejected}
        self.assertEqual(reasons["fastest_path"], "isolated run failed (exception)")
        self.assertEqual(reasons["lowest_capital"], "isolated run failed (nonzero_exit)")
        self.assertEqual(reasons["maximum_reversibility"], "isolated run failed (timeout)")
        self.assertEqual(reasons["do_nothing"], "did not beat baseline")

    def test_verifier_level_six_cannot_authorize_retain(self):
        candidates = eleven(value_by_archetype={"fastest_path": 5.0})
        loop, context = self.make_loop(context={"candidates": candidates, "pythonpath": self.tmp})
        args = self.loop_args(
            context=context,
            verifier=VerifierRecord(
                level=6,
                verifier_name="same-model critique",
                evidence_ref="sha256:" + "2" * 64,
            ),
        )
        proposal = loop.run_cycle(**args)
        self.assertEqual(proposal.decision, "regress")
        self.assertIn("may not authorize", proposal.summary)

    def test_zero_timeout_rejected(self):
        with self.assertRaises(EvolutionError):
            IsolatedRunner(timeout_seconds=0)


if __name__ == "__main__":
    unittest.main()
