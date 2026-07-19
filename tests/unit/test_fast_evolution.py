"""Phase 3 acceptance tests: fast capability evolution.

The machine generates all eleven candidate branches, tests each in
isolation, analyzes failures, compares against baseline, and proposes
the champion to the ClosureLoop. It may never self-authorize, never
route around doctrine, and never manufacture a winner.
"""
import pytest

from evolution.auto_cycle import AutoEvolutionCycle, AutoCycleReport
from evolution.branch_generator import BranchGenerator
from evolution.capsule import RetainRegressKill
from evolution.comparison import Comparison, IsolatedResult
from evolution.failure_analysis import analyze, classify
from evolution.loop import CycleRefused
from evolution.spider_web import EIGHT_SIDES, SUPER_NODES, SpiderWebAudit
from evolution.strategy_tree import BRANCH_KINDS
from provenance.ledger import EvidenceLedger

GENESIS = "sha256:" + "0" * 64


def _complete_audit():
    audit = SpiderWebAudit(subject="fast cycle")
    for s in EIGHT_SIDES:
        audit.set_side(s, True, "ok")
    for node in SUPER_NODES:
        audit.map_mechanism(f"mechanism-{node}", node)
    for req in ("bounded_transaction", "real_beneficiary", "buyer_or_mandate_actor",
                "lawful_permission_path", "accepted_artifact", "external_consequence",
                "participant_benefit", "ninety_day_falsification_test",
                "fundable_reliability", "recovery_path", "kill_criteria"):
        audit.set_completeness(req, True)
    return audit


def _result(branch, measured, attempts=None, executed=True):
    return IsolatedResult(branch_id=branch.branch_id, kind=branch.kind,
                          measured=measured, attempts=attempts or [{"ok": True}],
                          cost_usd=10.0, duration_days=1, executed=executed)


# ---------------------------------------------------------------- generation
class TestBranchGenerator:
    def test_all_eleven_kinds_generated_valid(self):
        tree = BranchGenerator().propose_tree(
            bottleneck="weak admissions", objective="zero weak admissions",
            decisive_unknown="does a higher floor hold recall", metric="good_refusals",
            baseline=0.0, budget_ceiling_usd=100.0)
        assert len(tree.branches) == 11
        assert all(tree.coverage().values())
        for b in tree.branches:
            assert b.validate() == []                    # generator never emits invalid

    def test_do_nothing_is_free(self):
        branches = BranchGenerator().generate(
            bottleneck="b", objective="o", decisive_unknown="u",
            metric="m", baseline=1.0, budget_ceiling_usd=50.0)
        dn = [b for b in branches if b.kind == "do_nothing"][0]
        assert dn.cost_usd == 0.0 and dn.founder_attention_minutes == 0


# ---------------------------------------------------------------- comparison
class TestComparison:
    def test_champion_must_resolve_and_beat(self):
        comp = Comparison(baseline=0.70, threshold=0.90, direction="gte")
        good = _result(type("B", (), {"branch_id": "1", "kind": "radical_simplification"})(), 0.95)
        middling = _result(type("B", (), {"branch_id": "2", "kind": "fastest_path"})(), 0.80)
        champ = comp.champion([middling, good])
        assert champ.result.branch_id == "1" and champ.beats_baseline

    def test_no_champion_when_nothing_beats_baseline(self):
        comp = Comparison(baseline=0.70, threshold=0.90, direction="gte")
        r = _result(type("B", (), {"branch_id": "1", "kind": "fastest_path"})(), 0.65)
        assert comp.champion([r]) is None                # do_nothing wins by default

    def test_lte_direction(self):
        comp = Comparison(baseline=10.0, threshold=5.0, direction="lte")
        r = _result(type("B", (), {"branch_id": "1", "kind": "lowest_capital"})(), 3.0)
        champ = comp.champion([r])
        assert champ is not None and champ.resolves_unknown


# ---------------------------------------------------------------- failure analysis
class TestFailureAnalysis:
    def test_classification_and_dominant_fix(self):
        r1 = _result(type("B", (), {"branch_id": "1", "kind": "k1"})(), 0.5,
                     attempts=[{"ok": False, "error": "policy refused: deny_by_default"}])
        r2 = _result(type("B", (), {"branch_id": "2", "kind": "k2"})(), 0.5,
                     attempts=[{"ok": False, "error": "connection timeout"}])
        report = analyze([r1, r2])
        assert report.total_failures == 2
        assert report.by_class["doctrinal_refusal"] == 1
        assert report.by_class["transient"] == 1
        assert report.failures[0]["branch_id"] == "1"    # failures preserved verbatim

    def test_structural_when_class_spans_branches(self):
        mk = lambda i: _result(type("B", (), {"branch_id": str(i), "kind": f"k{i}"})(), 0.5,
                               attempts=[{"ok": False, "error": "refused by doctrine"}])
        report = analyze([mk(1), mk(2), mk(3)])
        assert report.structural and report.dominant_class == "doctrinal_refusal"
        assert "amend doctrine" in report.recommended_fix

    def test_explicit_class_wins(self):
        assert classify({"failure_class": "budget_exceeded", "error": "refused"}) == "budget_exceeded"


# ---------------------------------------------------------------- the fast cycle
def _run_cycle(tester, **overrides):
    ledger = EvidenceLedger(GENESIS)
    cycle = AutoEvolutionCycle(ledger)
    kw = dict(bottleneck="weak admissions at floor 0.70",
              objective="zero weak admissions, zero new good refusals",
              decisive_unknown="does floor 0.75 hold recall",
              metric="weak_admissions", baseline=2.0, threshold=0.5, direction="lte",
              budget_ceiling_usd=50.0, audit=_complete_audit(),
              isolated_tester=tester,
              executor=lambda spec: (0.0, "positive"),
              verifier_level="formal_proof",
              verifier_evidence="replay: sha256 of corpus + admission counts",
              workflow="evidence_floor_raise", rollback_path="restore floor 0.70",
              kill_condition="any good proposal newly refused")
    kw.update(overrides)
    return cycle, cycle.run(**kw), ledger


class TestAutoCycle:
    def test_full_cycle_retain(self):
        def tester(branch):
            if branch.kind == "radical_simplification":
                return _result(branch, 0.0)              # zero weak admissions
            if branch.kind == "fastest_path":
                return _result(branch, 3.0, attempts=[{"ok": False, "error": "timeout"}])
            return _result(branch, 2.0)                  # at baseline: no improvement
        cycle, report, ledger = _run_cycle(tester)
        assert report.outcome == RetainRegressKill.RETAIN
        assert report.champion.result.kind == "radical_simplification"
        assert report.capsule is not None
        # every stage ledgered: generated, 11 tested, analyzed, champion
        types = [r.payload["type"] for r in ledger.by_type("event")]
        assert "auto_cycle.generated" in types
        assert types.count("auto_cycle.branch_tested") == 11
        assert "auto_cycle.failures_analyzed" in types
        assert "auto_cycle.champion" in types
        assert "evolution.experiment_measured" in types
        # losers preserved with revival evidence (ten rejected branches)
        rejected = [b for b in report.tree.branches if b.rejected]
        assert len(rejected) == 10 and all(b.revival_evidence for b in rejected)

    def test_no_improvement_when_baseline_unbeaten(self):
        _, report, ledger = _run_cycle(lambda branch: _result(branch, 2.0))
        assert report.outcome == "no_improvement"
        assert report.capsule is None and report.champion is None
        types = [r.payload["type"] for r in ledger.by_type("event")]
        assert "auto_cycle.no_improvement" in types

    def test_hypothesis_only_verifier_refused_before_execution(self):
        executed = []
        def tester(branch):
            executed.append(branch.kind)
            return _result(branch, 0.0)
        with pytest.raises(CycleRefused, match="hypothesis-only"):
            _run_cycle(tester, verifier_level="intrinsic_confidence")
        assert executed == []                              # refused before ANY testing

    def test_structural_doctrinal_refusal_halts_cycle(self):
        def tester(branch):
            return _result(branch, 0.0,
                           attempts=[{"ok": False, "error": "policy refused: absolute prohibition"}])
        with pytest.raises(CycleRefused, match="route around"):
            _run_cycle(tester)
