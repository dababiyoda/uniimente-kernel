"""Phase 5 acceptance tests: Institutional Twins + Counterfactual Tribunal.

A twin lives the change in parallel; the tribunal renders a verdict from
external-quality labels over one frozen corpus. Twins never touch main
state; the tribunal recommends and never applies.
"""
import os
from types import SimpleNamespace

import pytest

from compiler.ucl_compiler import compile_constitution
from policy.engine import EVIDENCE_THRESHOLDS, Proposal, evaluate
from provenance.ledger import EvidenceLedger
from twins.tribunal import CounterfactualTribunal
from twins.twin import Amendment, InstitutionalTwin

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GENESIS = "sha256:" + "0" * 64
GOOD_CONF = [0.95, 0.9, 0.85, 0.8]
WEAK_CONF = [0.72, 0.71]               # floor 0.70 admits them; 0.75 refuses


def _corpus():
    return ([(Proposal(actor="a", legal_principal="alfonso_lopez",
                       action_class="draft.publish", objective="t", payload={"c": c},
                       target="sandbox:outbox", consequence_class="external_contact",
                       evidence_confidence=c, evidence_refs=["sha256:" + "a" * 64],
                       estimated_cost_usd=0.0, requested_capability="draft.publish",
                       expected_outcome="queued"), "good") for c in GOOD_CONF]
            + [(Proposal(actor="a", legal_principal="alfonso_lopez",
                         action_class="draft.publish", objective="t", payload={"c": c},
                         target="sandbox:outbox", consequence_class="external_contact",
                         evidence_confidence=c, evidence_refs=["sha256:" + "a" * 64],
                         estimated_cost_usd=0.0, requested_capability="draft.publish",
                         expected_outcome="queued"), "weak") for c in WEAK_CONF])


class TestTwin:
    def test_fork_is_hermetic(self):
        compiled = compile_constitution(ROOT)
        before = dict(EVIDENCE_THRESHOLDS)
        twin = InstitutionalTwin(compiled, Amendment(
            description="raise external_contact floor to 0.75",
            evidence_thresholds={"external_contact": 0.75}))
        for p, _ in _corpus():
            twin.evaluate(p, identity_ok=True, grant=None)
        assert EVIDENCE_THRESHOLDS == before            # main floors untouched
        assert twin._compiled is not compiled
        assert twin.diverges_from_main()

    def test_floor_raise_is_twin_superior_over_real_engine(self):
        compiled = compile_constitution(ROOT)
        twin = InstitutionalTwin(compiled, Amendment(
            description="raise floor", evidence_thresholds={"external_contact": 0.75}))
        corpus = _corpus()
        main_decisions = [evaluate(compiled, p, identity_ok=True, grant=None) for p, _ in corpus]
        twin_decisions = [twin.evaluate(p, identity_ok=True, grant=None) for p, _ in corpus]
        v = CounterfactualTribunal().hear(corpus, main_decisions, twin_decisions,
                                          case="floor 0.70 -> 0.75")
        assert v.verdict == "twin_superior"
        assert v.main_profile.weak_admissions == 2 and v.twin_profile.weak_admissions == 0
        assert v.twin_profile.good_refusals == 0        # no recall lost


def _dec(verdict):
    return SimpleNamespace(verdict=verdict)


class TestTribunalGeometry:
    def _corpus_qualities(self):
        return [(f"p{i}", q) for i, q in
                enumerate(["good", "good", "weak", "weak", "bad"])]

    def test_tradeoff_is_inconclusive(self):
        corpus = self._corpus_qualities()
        main = [_dec("allow"), _dec("allow"), _dec("allow"), _dec("allow"), _dec("deny")]
        twin = [_dec("allow"), _dec("deny"), _dec("deny"), _dec("deny"), _dec("deny")]
        v = CounterfactualTribunal().hear(corpus, main, twin)
        assert v.verdict == "inconclusive"              # weak fixed but a good refused

    def test_regression_is_main_superior(self):
        corpus = self._corpus_qualities()
        main = [_dec("allow"), _dec("allow"), _dec("deny"), _dec("deny"), _dec("deny")]
        twin = [_dec("deny"), _dec("deny"), _dec("allow"), _dec("allow"), _dec("deny")]
        v = CounterfactualTribunal().hear(corpus, main, twin)
        assert v.verdict == "main_superior"

    def test_harm_increase_bars_promotion(self):
        corpus = self._corpus_qualities()
        main = [_dec("allow"), _dec("allow"), _dec("allow"), _dec("allow"), _dec("deny")]
        # twin fixes BOTH weak admissions but admits the bad one -> never superior
        twin = [_dec("allow"), _dec("allow"), _dec("deny"), _dec("deny"), _dec("allow")]
        v = CounterfactualTribunal().hear(corpus, main, twin)
        assert v.verdict != "twin_superior"

    def test_empty_corpus_refused(self):
        with pytest.raises(ValueError):
            CounterfactualTribunal().hear([], [], [])

    def test_verdict_recorded_on_ledger(self):
        ledger = EvidenceLedger(GENESIS)
        corpus = self._corpus_qualities()
        decisions = [_dec("allow")] * 4 + [_dec("deny")]
        CounterfactualTribunal(ledger).hear(corpus, decisions, decisions, case="parity")
        recs = [r for r in ledger.by_type("event") if r.payload["type"] == "twins.verdict"]
        assert len(recs) == 1 and recs[0].payload["case"] == "parity"
        assert recs[0].payload["corpus_size"] == 5
