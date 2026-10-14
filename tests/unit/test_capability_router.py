"""Capability Router (Competency Compiler) acceptance and hostile tests.

The router must pick only mechanisms whose kind of knowing can answer the
question, prefer the smallest competent one inside its envelope, compose
when one is not enough, route human-only questions to a person, name a
CapabilityDeficit instead of guessing, and learn only from independently
verified outcomes. It never confers authority.
"""
import pytest

from capabilities.genome import AuthorityEnvelope, CapabilityGenome, GenomeRegistry
from capabilities.router import (CapabilityRouter, Competency, ProblemSpec, RouterError,
                                 RESOLUTION_ORDER)
from provenance.ledger import EvidenceLedger


def _genome(name, cls="read_only", budget=0.0, human=False):
    return CapabilityGenome(
        name=name, version="1.0.0", description=f"{name} mechanism",
        interface={"inputs": {"q": "str"}, "outputs": {"answer": "str"}},
        contracts=["evidence"],
        authority=AuthorityEnvelope(max_consequence_class=cls, budget_ceiling_usd=budget,
                                    requires_human=human),
        acceptance_tests=["answers within contract"], failure_modes=["wrong answer"],
        recovery_path="discard output; re-route")


def _router(*specs, ledger=None):
    """specs: (name, methods, classes, consequence, cost, envelope_cls, envelope_budget)"""
    genomes = GenomeRegistry()
    router = CapabilityRouter(genomes, ledger=ledger)
    for name, methods, classes, cls, cost, env_cls, env_budget in specs:
        genomes.register(_genome(name, env_cls, env_budget))
        router.register(Competency(name, "1.0.0", tuple(methods), tuple(classes), cls, cost))
    return router


def _problem(cls, **kw):
    base = dict(problem_id=f"p-{cls}", question=f"answer a {cls} question", problem_class=cls)
    base.update(kw)
    return ProblemSpec(**base)


CALC = ("calc", ["deterministic_computation"], ["arithmetic", "code_correctness"],
        "read_only", 0.0, "read_only", 0.0)
SIM = ("sim", ["simulation"], ["forecast", "market_demand"], "read_only", 0.0, "read_only", 0.0)
PILOT = ("pilot", ["empirical_experiment"], ["market_demand"],
         "external_contact", 20.0, "external_contact", 50.0)
REVIEW = ("review", ["adversarial_review"], ["code_correctness", "design_critique"],
          "read_only", 0.0, "read_only", 0.0)


class TestEpistemicFit:
    def test_a_simulation_never_answers_a_demand_question(self):
        router = _router(SIM)
        decision = router.route(_problem("market_demand", max_consequence_class="external_contact",
                                         budget_usd=50.0))
        assert not decision.routed
        assert decision.deficit.missing_methods == ["one of: empirical_experiment"]
        assert "cannot answer market_demand" in decision.rejected["sim@1.0.0"]
        assert decision.deficit.resolution_order == RESOLUTION_ORDER
        assert "no acquisition" in decision.deficit.authority

    def test_a_real_experiment_answers_it_and_needs_the_gate(self):
        router = _router(SIM, PILOT)
        decision = router.route(_problem("market_demand", max_consequence_class="external_contact",
                                         budget_usd=50.0))
        assert decision.routed and [c.key for c in decision.selected] == ["pilot@1.0.0"]
        assert decision.expected_evidence == {"pilot@1.0.0": "external_fact"}
        assert decision.requires_gate is True
        assert "no execution authority" in decision.authority

    def test_problem_limits_exclude_bigger_mechanisms(self):
        router = _router(PILOT)
        cheap = router.route(_problem("market_demand", max_consequence_class="read_only"))
        assert not cheap.routed and "exceeds problem limit" in cheap.rejected["pilot@1.0.0"]
        poor = router.route(_problem("market_demand", max_consequence_class="external_contact",
                                     budget_usd=5.0))
        assert not poor.routed and "exceeds budget" in poor.rejected["pilot@1.0.0"]


class TestSmallestCompetent:
    def test_prefers_the_smaller_mechanism(self):
        big = ("cluster", ["deterministic_computation"], ["arithmetic"],
               "internal_write", 3.0, "internal_write", 10.0)
        router = _router(big, CALC)
        decision = router.route(_problem("arithmetic", max_consequence_class="internal_write",
                                         budget_usd=10.0))
        assert [c.key for c in decision.selected] == ["calc@1.0.0"]
        assert decision.requires_gate is False

    def test_composes_when_one_mechanism_is_not_enough(self):
        router = _router(CALC, REVIEW)
        decision = router.route(_problem("code_correctness"))
        assert sorted(c.key for c in decision.selected) == ["calc@1.0.0", "review@1.0.0"]

    def test_missing_part_of_a_composition_is_named(self):
        router = _router(CALC)
        decision = router.route(_problem("code_correctness"))
        assert not decision.routed and decision.selected == []
        assert decision.deficit.missing_methods == ["adversarial_review"]


class TestHumanAuthority:
    def test_authorization_goes_to_a_person_not_a_machine(self):
        router = _router(CALC, REVIEW)
        decision = router.route(_problem("authorization"))
        assert decision.selected == [] and decision.deficit is None
        assert decision.human_escalation == ["human_decision"]

    def test_no_mechanism_may_claim_a_human_only_method(self):
        genomes = GenomeRegistry()
        genomes.register(_genome("judge"))
        router = CapabilityRouter(genomes)
        with pytest.raises(RouterError, match="human-only"):
            router.register(Competency("judge", "1.0.0", ("human_decision",), ("authorization",)))
        with pytest.raises(RouterError, match="human-only"):
            router.register(Competency("judge", "1.0.0", ("legal_determination",),
                                       ("legal_question",)))


class TestRegistrationFailsClosed:
    def test_unregistered_genome_refused(self):
        router = CapabilityRouter(GenomeRegistry())
        with pytest.raises(RouterError, match="no registered genome"):
            router.register(Competency("ghost", "1.0.0", ("retrieval",), ("fact_lookup",)))

    def test_competency_cannot_exceed_its_genome_envelope(self):
        genomes = GenomeRegistry()
        genomes.register(_genome("calc"))
        router = CapabilityRouter(genomes)
        with pytest.raises(RouterError, match="envelope"):
            router.register(Competency("calc", "1.0.0", ("deterministic_computation",),
                                       ("arithmetic",), "external_contact", 0.0))
        with pytest.raises(RouterError, match="envelope"):
            router.register(Competency("calc", "1.0.0", ("deterministic_computation",),
                                       ("arithmetic",), "read_only", 1.0))

    def test_unknown_methods_and_classes_refused(self):
        genomes = GenomeRegistry()
        genomes.register(_genome("calc"))
        router = CapabilityRouter(genomes)
        with pytest.raises(RouterError):
            router.register(Competency("calc", "1.0.0", ("telepathy",), ("arithmetic",)))
        with pytest.raises(RouterError):
            router.register(Competency("calc", "1.0.0", ("retrieval",), ("everything",)))
        with pytest.raises(RouterError, match="invalid problem"):
            router.route(_problem("everything"))


class TestOutcomeCalibration:
    def test_verified_failures_demote_a_mechanism_and_the_alternative_takes_over(self):
        fast = ("fast", ["deterministic_computation"], ["arithmetic"], "read_only", 0.0,
                "read_only", 0.0)
        slow = ("slow", ["deterministic_computation"], ["arithmetic"], "read_only", 1.0,
                "read_only", 1.0)
        router = _router(fast, slow)
        problem = _problem("arithmetic", budget_usd=1.0)
        first = router.route(problem)
        assert [c.key for c in first.selected] == ["fast@1.0.0"]
        assert first.exploratory is True  # no verified track record yet

        for i in range(3):
            router.record_outcome(first.decision_id, "fast@1.0.0", correct=False,
                                  evidence_ref=f"audit-{i}", verified_by="independent-auditor")
        second = router.route(problem)
        assert [c.key for c in second.selected] == ["slow@1.0.0"]
        assert "below" in second.rejected["fast@1.0.0"]

    def test_proven_mechanism_beats_an_unproven_cheaper_one(self):
        b = ("b", ["retrieval"], ["fact_lookup"], "read_only", 0.5, "read_only", 1.0)
        router = _router(b)
        problem = _problem("fact_lookup", budget_usd=1.0)
        only_b = router.route(problem)
        for i in range(4):
            router.record_outcome(only_b.decision_id, "b@1.0.0", correct=True,
                                  evidence_ref=f"src-{i}", verified_by="fact-checker")
        # A cheaper newcomer arrives with no verified record.
        router.genomes.register(_genome("a"))
        router.register(Competency("a", "1.0.0", ("retrieval",), ("fact_lookup",)))
        decision = router.route(problem)
        assert [c.key for c in decision.selected] == ["b@1.0.0"]
        assert decision.selected[0].proven and decision.exploratory is False

    def test_a_mechanism_cannot_grade_itself(self):
        router = _router(CALC)
        decision = router.route(_problem("arithmetic"))
        for verifier in ("calc@1.0.0", "calc", "calc@2.0.0", ""):
            with pytest.raises(RouterError, match="someone other"):
                router.record_outcome(decision.decision_id, "calc@1.0.0", correct=True,
                                      evidence_ref="x", verified_by=verifier)
        assert router.calibration("calc@1.0.0", "arithmetic").trials == 0

    def test_outcomes_need_evidence_and_a_matching_decision(self):
        router = _router(CALC, REVIEW)
        decision = router.route(_problem("arithmetic"))
        with pytest.raises(RouterError, match="evidence"):
            router.record_outcome(decision.decision_id, "calc@1.0.0", correct=True,
                                  evidence_ref="", verified_by="auditor")
        with pytest.raises(RouterError, match="did not select"):
            router.record_outcome(decision.decision_id, "review@1.0.0", correct=True,
                                  evidence_ref="x", verified_by="auditor")
        with pytest.raises(RouterError, match="unknown"):
            router.record_outcome("sha256:nope", "calc@1.0.0", correct=True,
                                  evidence_ref="x", verified_by="auditor")


class TestRecordAndDeterminism:
    def test_same_inputs_same_decision_and_everything_is_ledgered(self):
        ledger = EvidenceLedger("sha256:" + "d" * 64)
        router = _router(CALC, SIM, ledger=ledger)
        one = router.route(_problem("arithmetic"))
        two = router.route(_problem("arithmetic"))
        assert one.decision_id == two.decision_id
        gap = router.route(_problem("market_demand"))
        router.record_outcome(one.decision_id, "calc@1.0.0", correct=True,
                              evidence_ref="unit-test", verified_by="test-oracle")

        types = [r.payload.get("type") for r in ledger.records if r.record_type == "event"]
        assert types.count("capabilities.competency_registered") == 2
        assert types.count("capabilities.routing_decision") == 3
        assert types.count("capabilities.routing_outcome") == 1
        assert ledger.verify_chain()[0] is True
        assert gap.to_dict()["deficit"]["deficit_id"].startswith("sha256:")


class TestRestart:
    def test_track_record_survives_restart_from_the_ledger(self, tmp_path):
        path = str(tmp_path / "ledger.jsonl")
        genesis = "sha256:" + "e" * 64
        ledger = EvidenceLedger(genesis, path=path)
        fast = ("fast", ["deterministic_computation"], ["arithmetic"], "read_only", 0.0,
                "read_only", 0.0)
        slow = ("slow", ["deterministic_computation"], ["arithmetic"], "read_only", 1.0,
                "read_only", 1.0)
        router = _router(fast, slow, ledger=ledger)
        problem = _problem("arithmetic", budget_usd=1.0)
        first = router.route(problem)
        for i in range(3):
            router.record_outcome(first.decision_id, "fast@1.0.0", correct=False,
                                  evidence_ref=f"audit-{i}", verified_by="independent-auditor")
        ledger.close()

        # A fresh process: new registry, same ledger file.
        reopened = EvidenceLedger(genesis, path=path)
        rebuilt = _router(fast, slow, ledger=reopened)
        assert rebuilt.restore() == 3
        assert rebuilt.calibration("fast@1.0.0", "arithmetic").incorrect == 3
        assert [c.key for c in rebuilt.route(problem).selected] == ["slow@1.0.0"]
        # Outcomes for decisions made before the restart still validate.
        rebuilt.record_outcome(first.decision_id, "fast@1.0.0", correct=True,
                               evidence_ref="audit-late", verified_by="independent-auditor")
        assert rebuilt.calibration("fast@1.0.0", "arithmetic").trials == 4

    def test_restore_refuses_without_a_ledger(self):
        with pytest.raises(RouterError, match="no ledger"):
            _router(CALC).restore()


class TestReviewFindings:
    def test_composition_respects_the_aggregate_budget(self):
        calc = ("calc8", ["deterministic_computation"], ["code_correctness"],
                "read_only", 8.0, "read_only", 8.0)
        review = ("review8", ["adversarial_review"], ["code_correctness"],
                  "read_only", 8.0, "read_only", 8.0)
        router = _router(calc, review)
        tight = router.route(_problem("code_correctness", budget_usd=10.0))
        assert not tight.routed and tight.selected == []
        assert tight.deficit.missing_methods == ["no composition within budget $10.0"]
        roomy = router.route(_problem("code_correctness", budget_usd=16.0))
        assert sorted(c.key for c in roomy.selected) == ["calc8@1.0.0", "review8@1.0.0"]

    def test_one_full_mechanism_beats_a_cheaper_partial_plus_another(self):
        partial = ("partial", ["deterministic_computation"], ["code_correctness"],
                   "read_only", 0.0, "read_only", 0.0)
        full = ("full", ["deterministic_computation", "adversarial_review"],
                ["code_correctness"], "read_only", 1.0, "read_only", 1.0)
        router = _router(partial, full)
        decision = router.route(_problem("code_correctness", budget_usd=1.0))
        assert [c.key for c in decision.selected] == ["full@1.0.0"]

    def test_calibration_is_a_snapshot_not_a_handle(self):
        router = _router(CALC)
        decision = router.route(_problem("arithmetic"))
        router.record_outcome(decision.decision_id, "calc@1.0.0", correct=False,
                              evidence_ref="audit", verified_by="auditor")
        snapshot = router.calibration("calc@1.0.0", "arithmetic")
        with pytest.raises(Exception):
            snapshot.correct = 1000  # frozen: no silent promotion
        assert router.calibration("calc@1.0.0", "arithmetic").correct == 0
        assert router.calibration("calc@1.0.0", "arithmetic").incorrect == 1

    def test_a_failed_ledger_write_changes_nothing(self):
        class RefusingLedger:
            refuse = False

            def append(self, record_type, payload):
                if self.refuse:
                    raise RuntimeError("ledger requires reconciliation")

        ledger = RefusingLedger()
        router = _router(CALC, ledger=ledger)
        decision = router.route(_problem("arithmetic"))
        ledger.refuse = True

        with pytest.raises(RuntimeError):
            router.record_outcome(decision.decision_id, "calc@1.0.0", correct=True,
                                  evidence_ref="audit", verified_by="auditor")
        assert router.calibration("calc@1.0.0", "arithmetic").trials == 0

        unrecorded = _problem("arithmetic", problem_id="p-unrecorded")
        with pytest.raises(RuntimeError):
            router.route(unrecorded)
        # Decisions are deterministic, so a twin router reproduces the id the
        # failed route would have used. That decision was never ledgered and
        # must not accept outcomes.
        lost_id = _router(CALC).route(unrecorded).decision_id
        ledger.refuse = False
        with pytest.raises(RouterError, match="unknown"):
            router.record_outcome(lost_id, "calc@1.0.0", correct=True,
                                  evidence_ref="audit", verified_by="auditor")

        router.genomes.register(_genome("late"))
        ledger.refuse = True
        with pytest.raises(RuntimeError):
            router.register(Competency("late", "1.0.0", ("retrieval",), ("fact_lookup",)))
        ledger.refuse = False
        assert "late@1.0.0" not in router.route(_problem("fact_lookup")).rejected
