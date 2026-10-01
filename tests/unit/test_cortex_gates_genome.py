"""Cortex seed v0.1 — hard gates before ranking, and the genome projection.

Build prompt items 1, 2, 3: IntelligenceGenome reuses the one GenomeRegistry;
gates read existing policy/authorization records; a favorable advantage score
never overrides a failed gate; model output, proofs, confidence, reputation and
benchmarks never create permission.
"""
import os

import pytest

from capabilities.genome import GenomeError, GenomeRegistry
from compiler.ucl_compiler import compile_constitution
from cortex.contracts import ConsequenceVector, CortexError, HARM_DIMENSIONS
from cortex.gates import (NEVER_PERMISSION, AuthorityRecord, Option, _instant, evaluate_gates,
                          rank_after_gates, record_from_policy_decision)
from cortex.genome import (RESERVED_FAMILIES, SEED_ORGANS, IntelligenceGenome, IntelligenceRegistry,
                           _capability, _profile, seed_registry)
from cortex.routing import derive_geometry
from cortex.contracts import Problem
from policy.engine import Proposal, evaluate
from provenance.ledger import EvidenceLedger

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NONE_HARM = {d: "none" for d in HARM_DIMENSIONS}
MANDATE = AuthorityRecord("m1", "founder_mandate", "founder_signed",
                          {"scope": {"action_classes": ["draft.*"], "targets": ["internal://*"],
                                     "max_consequence_class": "internal_write",
                                     "expires_at": "2026-12-31T00:00:00Z"}})


def allow(subject):
    return AuthorityRecord(f"p-{subject}", "policy_decision", "kernel_policy_engine",
                           {"subject": subject, "verdict": "allow"})


def opt(oid, advantage, **kw):
    base = dict(option_id=oid, action_class="draft.prepare", target="internal://drafts",
                consequence_class="internal_write", reversibility="reversible", cost_usd=0.0,
                harm=NONE_HARM, evidence_statuses=["internally_observed"], advantage=advantage)
    base.update(kw)
    return Option.from_dict(base)


# ------------------------------------------------------------------ gates
class TestHardGatesBeforeRanking:
    def test_favorable_score_cannot_override_failed_gate(self):
        o1 = opt("O1", {"value": 1e9}, harm={**NONE_HARM, "rights": "high"})
        o2 = opt("O2", {"value": 0.1})
        reports = {o.option_id: evaluate_gates(o, [allow("O1"), allow("O2"), MANDATE], remaining_budget_usd=1.0)
                   for o in (o1, o2)}
        assert reports["O1"].gates["rights"].status == "FAIL"
        ranking = rank_after_gates([o1, o2], reports)
        assert ranking["chosen"] == "O2"
        assert ranking["excluded"] == {"O1": "exclude"}

    @pytest.mark.parametrize("kind", NEVER_PERMISSION)
    def test_non_permission_records_never_create_permission(self, kind):
        fake = AuthorityRecord("x", kind, "assistant", {"subject": "O1", "verdict": "allow",
                                                        "scope": MANDATE.body["scope"]})
        report = evaluate_gates(opt("O1", {"v": 1}), [fake], remaining_budget_usd=1.0)
        assert report.gates["law"].status == "UNRESOLVED"
        assert report.gates["founder_scope"].status == "UNRESOLVED"
        assert not report.all_pass
        assert report.rejected_bases and report.rejected_bases[0]["kind"] == kind

    def test_forged_origin_on_a_permission_kind_is_rejected(self):
        forged = AuthorityRecord("f", "policy_decision", "assistant", {"subject": "O1", "verdict": "allow"})
        report = evaluate_gates(opt("O1", {"v": 1}), [forged, MANDATE], remaining_budget_usd=1.0)
        assert report.gates["law"].status == "UNRESOLVED"

    def test_real_policy_engine_decisions_map_to_gates(self):
        compiled = compile_constitution(ROOT)
        base = dict(actor="agent-1", legal_principal="alfonso_lopez", objective="o", payload={},
                    target="internal://drafts", consequence_class="internal_write", evidence_confidence=0.9,
                    evidence_refs=[], estimated_cost_usd=0.0, requested_capability="draft.prepare",
                    expected_outcome="draft")
        denied = evaluate(compiled, Proposal(action_class="draft.prepare", context={"deception": True}, **base),
                          identity_ok=True, grant=None)
        human = evaluate(compiled, Proposal(action_class="material_debt", **base), identity_ok=True, grant=None)
        assert denied.verdict.value == "deny" and human.verdict.value == "require_human"
        r_deny = record_from_policy_decision(denied, subject="O1", action_class="draft.prepare")
        r_human = record_from_policy_decision(human, subject="O2", action_class="material_debt")
        assert r_deny.permission_bearing and r_human.permission_bearing
        g1 = evaluate_gates(opt("O1", {"v": 1}), [r_deny, MANDATE], remaining_budget_usd=1.0)
        g2 = evaluate_gates(opt("O2", {"v": 1}), [r_human, MANDATE], remaining_budget_usd=1.0)
        assert g1.gates["law"].status == "FAIL" and g1.resolution == "exclude"
        assert g2.gates["law"].status == "UNRESOLVED" and g2.resolution == "authorized_adjudication"

    def test_consent_revoked_fails_and_missing_is_unresolved(self):
        o = opt("O1", {"v": 1}, requires_consent=True, consent_subject="c-1")
        revoked = AuthorityRecord("c", "consent_record", "consent_capture",
                                  {"subject": "c-1", "purposes": ["draft.*"], "revoked": True})
        assert evaluate_gates(o, [allow("O1"), MANDATE, revoked], remaining_budget_usd=1).gates["consent"].status == "FAIL"
        assert evaluate_gates(o, [allow("O1"), MANDATE], remaining_budget_usd=1).gates["consent"].status == "UNRESOLVED"

    def test_evidence_floor_grows_with_consequence_and_irreversibility(self):
        mandate = AuthorityRecord("m", "founder_mandate", "founder_signed",
                                  {"scope": {"action_classes": ["*.*"], "targets": ["*:*"],
                                             "max_consequence_class": "external_contact"}})
        o = opt("O1", {"v": 1}, consequence_class="external_contact", reversibility="irreversible",
                target="mail:x", evidence_statuses=["externally_verified"])
        rep = evaluate_gates(o, [allow("O1"), mandate], remaining_budget_usd=1)
        assert rep.gates["evidence_sufficiency"].status == "UNRESOLVED"          # needs two strong items
        o2 = opt("O1", {"v": 1}, consequence_class="external_contact", reversibility="irreversible",
                 target="mail:x", evidence_statuses=["externally_verified", "externally_verified"])
        assert evaluate_gates(o2, [allow("O1"), mandate], remaining_budget_usd=1).gates["evidence_sufficiency"].status == "PASS"

    def test_financial_is_never_delegated_to_cognition(self):
        o = opt("O1", {"v": 1}, consequence_class="financial")
        # A mandate capped at internal_write puts a financial option outside scope: excluded.
        capped = evaluate_gates(o, [allow("O1"), MANDATE], remaining_budget_usd=1)
        assert capped.gates["founder_scope"].status == "FAIL" and capped.resolution == "exclude"
        # Even inside a financial mandate, cognition does not decide: it hands off.
        wide = AuthorityRecord("m2", "founder_mandate", "founder_signed",
                               {"scope": {"action_classes": ["draft.*"], "targets": ["internal://*"],
                                          "max_consequence_class": "financial"}})
        rep = evaluate_gates(o, [allow("O1"), wide], remaining_budget_usd=1)
        assert rep.gates["consequence_boundary"].status == "UNRESOLVED"
        assert rep.resolution == "authorized_adjudication"

    def test_incomparable_options_preserve_tradeoffs_and_margin_blocks_near_ties(self):
        a, b = opt("A", {"speed": 0.9, "durability": 0.4}), opt("B", {"speed": 0.5, "durability": 0.8})
        recs = [allow("A"), allow("B"), MANDATE]
        reports = {o.option_id: evaluate_gates(o, recs, remaining_budget_usd=1) for o in (a, b)}
        r = rank_after_gates([a, b], reports)
        assert r["status"] == "incomparable" and r["chosen"] is None and len(r["tradeoffs"]) == 2
        near = rank_after_gates([a, b], reports, founder_weights={"speed": 0.5, "durability": 0.5})
        assert near["status"] == "within_margin"                                  # 0.65 vs 0.65
        clear = rank_after_gates([a, b], reports, founder_weights={"speed": 0.1, "durability": 0.9})
        assert clear["status"] == "chosen" and clear["chosen"] == "B"

    def test_naive_timestamps_are_refused_and_dates_mean_utc_midnight(self):
        assert _instant("2026-09-30").tzinfo is not None
        with pytest.raises(CortexError):
            _instant("2026-09-30T10:00:00")

    def test_harm_is_a_vector_with_unknown_default(self):
        v = ConsequenceVector.from_partial({"privacy": "high"})
        assert v.levels["physical"] == "unknown" and "privacy" not in v.hard_violations()
        assert "rights" in ConsequenceVector.from_partial({"rights": "high"}).hard_violations()
        with pytest.raises(CortexError):
            ConsequenceVector.from_partial({"harm_score": "low"})


# ------------------------------------------------------------------ genome projection
class TestIntelligenceGenomeProjection:
    def test_registers_through_the_one_kernel_registry_and_ledgers(self):
        ledger = EvidenceLedger("sha256:" + "0" * 64)
        genomes = GenomeRegistry(ledger=ledger)
        reg = seed_registry(genomes)
        assert len(reg.keys()) == len(SEED_ORGANS) + len(RESERVED_FAMILIES)
        assert genomes.get("cortex.formal.z3", "0.1.1") is not None          # same identifiers/versioning
        events = [r.payload["type"] for r in ledger.by_type("event")]
        assert events.count("capabilities.genome_registered") == len(reg.keys())
        assert events.count("cortex.profile_registered") == len(reg.keys())

    def test_reserved_families_are_registered_disabled_and_ineligible(self):
        reg = seed_registry()
        geometry = derive_geometry(Problem.from_dict({"problem_id": "p", "question": "q",
                                                      "payload": {"declared": {"epistemic_class": "strategic"}}}))
        rows = {e.key: e for e in reg.eligibility(geometry, role="reserved")}
        assert rows and all(not e.eligible and any("disabled" in r for r in e.reasons) for e in rows.values())
        for key in reg.keys():
            if key.split("@")[0] in RESERVED_FAMILIES:
                assert reg.get(key).profile.enabled is False

    def test_biological_concepts_must_compile_to_mechanisms(self):
        for name, (_, _, _, _, bio) in RESERVED_FAMILIES.items():
            if bio is not None:
                assert all(bio[f] for f in ("mechanism", "state_variables", "interface", "feedback_loop",
                                            "measurable_behavior", "test", "failure_condition")), name
        cap = _capability("x.bio", "d", {"i": "1"}, {"o": "1"}, ["t"], ["f"])
        profile = _profile("x.bio@0.1.0", role="reserved", layer="distributed_collective", geometries=("strategic",),
                           proofs=("simulation",), observations=("o",), state="s", update="u", recruitment="r",
                           inhibition="i", evidence=("e",), ceiling="read_only", diversity="k", deps=(),
                           lifecycle="SPECIFIED", enabled=False, bio={"mechanism": "ant trails"})
        with pytest.raises(GenomeError, match="biological concept"):
            IntelligenceRegistry().register(IntelligenceGenome(cap, profile))

    @pytest.mark.parametrize("mutation, message", [
        (dict(enabled=True), "routable"),
        (dict(cognitive_light_cone={"observes": [], "modifies": ["world"], "max_informed_consequence": "read_only",
                                    "horizon": "x"}), "never modify"),
        (dict(benchmark_history=("score:0.99",)), "self-asserted"),
    ])
    def test_profile_invariants(self, mutation, message):
        from dataclasses import replace
        reg = seed_registry(include_reserved=True)
        genome = reg.get("cortex.collective.hive_quorum@0.1.0")
        bad = IntelligenceGenome(genome.capability, replace(genome.profile, **mutation))
        with pytest.raises(GenomeError, match=message):
            IntelligenceRegistry().register(bad)

    def test_eligibility_reuses_may_instantiate(self, monkeypatch):
        reg = seed_registry(include_reserved=False)
        monkeypatch.setattr(reg.genomes, "may_instantiate", lambda *a, **k: (False, "envelope says no"))
        geometry = derive_geometry(Problem.from_dict({"problem_id": "p", "question": "q", "payload": {
            "estimation_model": {"target": {"unit": "1"}, "variables": [], "expression": "x"}}}))
        rows = reg.eligibility(geometry)
        assert all(not e.eligible and "envelope says no" in e.reasons for e in rows)
