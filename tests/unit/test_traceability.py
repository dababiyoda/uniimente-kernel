"""Single Bottleneck Metric: chain walking, honest refusals, contamination.

The metric under test is:

    percentage of completed goals traceable from founder intent to decision,
    action, evidence and outcome without unauthorized external effects.

These tests are written adversarially. Most of them try to make the walker
report a number it has not earned — by omitting links, by presenting a
plausible-looking near-match, by claiming completion with nothing behind it, and
by slipping an external effect past the authority chain. Every one of those must
be refused or counted, never smoothed over.
"""
import json
import pathlib

import pytest

from provenance.ledger import EvidenceLedger
from traceability import (
    LINKS,
    TraceabilityWalker,
    single_bottleneck_metric,
)

GENESIS = "sha256:" + "0" * 64
CONTRACTS = pathlib.Path(__file__).resolve().parents[2] / "contracts"


def _ledger():
    return EvidenceLedger(GENESIS)


def _intent(ledger, intent_id="INTENT-9001", state="implemented",
            implementation_refs=("policy/consequence_gate.py",)):
    payload = {
        "intent_id": intent_id,
        "statement": "No agent or person receives unrestricted treasury access.",
        "source_refs": ["chat:founder-2026-07-27"],
        "owner": "alfonso_lopez",
        "state": state,
        "binding_scope": ["pumpstation"],
        "constitutional_constraints": ["authority.bounded"],
        "success_evidence": ["zero unrestricted grants in the registry"],
        "failure_evidence": ["any grant with no spending ceiling"],
        "dependencies": [],
        "conflicts": [],
        "next_review_trigger": "before any real-value token is enabled",
        "supersedes": None,
        "superseded_by": None,
        "implementation_refs": list(implementation_refs),
    }
    ledger.append("intent", payload)
    return payload


def _evidence(ledger, n=1):
    """Append a real record and return its hash, so evidence_refs resolve."""
    rec = ledger.append("event", {"event_id": f"ev-{n}", "type": "test.evidence"})
    return rec.hash


def _decision(ledger, decision_id="dec-1", intent_ref="INTENT-9001",
              evidence_refs=None):
    payload = {
        "decision_id": decision_id,
        "intent_ref": intent_ref,
        "objective": "bound the treasury",
        "evidence_refs": list(evidence_refs or []),
    }
    ledger.append("decision", payload)
    return payload


def _witness(ledger, witness_id="wit-1"):
    ledger.append("witness", {"witness_id": witness_id})
    return witness_id


def _receipt(ledger, action_id="act-1", decision_ref="dec-1",
             grant_id="grant-1", witness_id="wit-1"):
    payload = {"action_id": action_id, "decision_ref": decision_ref,
               "grant_id": grant_id, "witness_id": witness_id, "result": {}}
    ledger.append("receipt", payload)
    return payload


def _outcome(ledger, action_ref="act-1"):
    ledger.append("outcome", {"action_ref": action_ref, "result_class": "positive",
                              "validation_status": "externally_verified",
                              "recorded_at": "2026-07-27T00:00:00Z"})


def _complete_chain(ledger, intent_id="INTENT-9001"):
    """One goal with all five links intact and an authorized effect."""
    _intent(ledger, intent_id)
    ref = _evidence(ledger)
    _decision(ledger, "dec-1", intent_id, [ref])
    _witness(ledger, "wit-1")
    _receipt(ledger, "act-1", "dec-1", "grant-1", "wit-1")
    _outcome(ledger, "act-1")


class TestCompleteChain:
    def test_full_chain_is_traceable_and_scores_100(self):
        ledger = _ledger()
        _complete_chain(ledger)
        report = single_bottleneck_metric(ledger)
        assert report.completed_goals == 1
        assert report.traceable_goals == 1
        assert report.rate == 100.0
        assert report.contaminated is False
        assert report.false_completions == []

    def test_trace_resolves_every_link(self):
        ledger = _ledger()
        _complete_chain(ledger)
        trace = TraceabilityWalker(ledger).trace("INTENT-9001")
        assert trace.traceable
        assert trace.broken_links == []
        assert len(trace.decisions) == 1
        assert len(trace.actions) == 1
        assert len(trace.evidence) == 1
        assert len(trace.outcomes) == 1


class TestRefusals:
    def test_empty_ledger_refuses_a_rate_instead_of_reporting_100(self):
        report = single_bottleneck_metric(_ledger())
        assert report.rate is None
        assert report.reportable is False
        assert report.completed_goals == 0
        assert "empty denominator" in report.refusal

    def test_goals_that_do_not_claim_completion_are_not_counted(self):
        ledger = _ledger()
        _intent(ledger, "INTENT-9003", state="exploratory")
        report = single_bottleneck_metric(ledger)
        assert report.completed_goals == 0
        assert report.rate is None

    def test_implemented_with_no_implementation_refs_is_a_false_completion(self):
        ledger = _ledger()
        _intent(ledger, "INTENT-9002", state="implemented", implementation_refs=())
        ref = _evidence(ledger)
        _decision(ledger, "dec-1", "INTENT-9002", [ref])
        _witness(ledger)
        _receipt(ledger, "act-1", "dec-1")
        _outcome(ledger)
        report = single_bottleneck_metric(ledger)
        assert report.rate == 0.0
        assert report.false_completions == ["INTENT-9002"]
        assert report.broken_link_counts.get("intent") == 1


class TestBrokenLinks:
    def test_decision_that_names_no_intent_breaks_the_first_link(self):
        ledger = _ledger()
        _intent(ledger)
        ref = _evidence(ledger)
        _decision(ledger, "dec-1", intent_ref=None, evidence_refs=[ref])
        report = single_bottleneck_metric(ledger)
        assert report.rate == 0.0
        assert report.broken_link_counts.get("decision") == 1

    def test_decision_with_no_action_breaks_the_action_link(self):
        ledger = _ledger()
        _intent(ledger)
        ref = _evidence(ledger)
        _decision(ledger, "dec-1", evidence_refs=[ref])
        trace = TraceabilityWalker(ledger).trace("INTENT-9001")
        assert "action" in trace.broken_links
        assert any("produced no recorded external action" in u.reason
                   for u in trace.unresolved)

    def test_decision_citing_no_evidence_breaks_the_evidence_link(self):
        ledger = _ledger()
        _intent(ledger)
        _decision(ledger, "dec-1", evidence_refs=[])
        _witness(ledger)
        _receipt(ledger)
        _outcome(ledger)
        trace = TraceabilityWalker(ledger).trace("INTENT-9001")
        assert "evidence" in trace.broken_links

    def test_evidence_ref_that_resolves_to_nothing_is_not_evidence(self):
        ledger = _ledger()
        _intent(ledger)
        _decision(ledger, "dec-1", evidence_refs=["sha256:" + "f" * 64])
        _witness(ledger)
        _receipt(ledger)
        _outcome(ledger)
        trace = TraceabilityWalker(ledger).trace("INTENT-9001")
        assert "evidence" in trace.broken_links
        assert trace.evidence == []
        assert any("does not resolve" in u.reason for u in trace.unresolved)

    def test_action_with_no_outcome_breaks_the_outcome_link(self):
        ledger = _ledger()
        _intent(ledger)
        ref = _evidence(ledger)
        _decision(ledger, "dec-1", evidence_refs=[ref])
        _witness(ledger)
        _receipt(ledger)          # no outcome appended
        trace = TraceabilityWalker(ledger).trace("INTENT-9001")
        assert "outcome" in trace.broken_links
        assert any("never reconciled" in u.reason for u in trace.unresolved)

    def test_missing_intent_record_reports_and_stops(self):
        trace = TraceabilityWalker(_ledger()).trace("INTENT-9004")
        assert trace.broken_links == ["intent"]
        assert trace.intent is None


class TestNoInference:
    """The walker must never repair a chain by guessing."""

    def test_matching_objective_does_not_substitute_for_a_declared_link(self):
        ledger = _ledger()
        _intent(ledger)
        ref = _evidence(ledger)
        # Same objective text, no intent_ref. A fuzzy join would resolve this.
        ledger.append("decision", {"decision_id": "dec-1", "intent_ref": None,
                                   "objective": "bound the treasury",
                                   "evidence_refs": [ref]})
        trace = TraceabilityWalker(ledger).trace("INTENT-9001")
        assert trace.decisions == []
        assert "decision" in trace.broken_links

    def test_sole_candidate_does_not_substitute_for_a_declared_link(self):
        ledger = _ledger()
        _intent(ledger)
        ref = _evidence(ledger)
        _decision(ledger, "dec-1", evidence_refs=[ref])
        _witness(ledger)
        # The only receipt in the ledger, but it names no decision.
        ledger.append("receipt", {"action_id": "act-1", "decision_ref": None,
                                  "grant_id": "g", "witness_id": "wit-1"})
        trace = TraceabilityWalker(ledger).trace("INTENT-9001")
        assert trace.actions == []
        assert "action" in trace.broken_links


class TestTraceLinkRecords:
    """The decision->action link, asserted separately from the receipt.

    The Consequence Gate writes receipts but is a frozen continuity artifact, so
    it cannot grow a decision_ref field without mutating an authority invariant.
    A `trace_link` record carries the link instead.
    """

    def _linked_chain(self, ledger):
        _intent(ledger)
        ref = _evidence(ledger)
        _decision(ledger, "dec-1", evidence_refs=[ref])
        _witness(ledger, "wit-1")
        # Receipt exactly as the real gate writes it: no decision_ref field.
        ledger.append("receipt", {"action_id": "act-1", "witness_id": "wit-1",
                                  "grant_id": "grant-1", "result": {}})
        _outcome(ledger, "act-1")

    def test_trace_link_closes_the_action_link(self):
        ledger = _ledger()
        self._linked_chain(ledger)
        ledger.append("trace_link", {"decision_ref": "dec-1", "action_ref": "act-1",
                                     "asserted_by": "alfonso_lopez",
                                     "asserted_at": "2026-07-27T00:00:00Z"})
        report = single_bottleneck_metric(ledger)
        assert report.rate == 100.0
        assert report.goals[0]["actions"] == 1

    def test_without_the_link_record_the_action_stays_unresolved(self):
        ledger = _ledger()
        self._linked_chain(ledger)          # no trace_link appended
        trace = TraceabilityWalker(ledger).trace("INTENT-9001")
        assert "action" in trace.broken_links

    def test_link_to_a_nonexistent_action_is_reported_not_counted(self):
        ledger = _ledger()
        self._linked_chain(ledger)
        ledger.append("trace_link", {"decision_ref": "dec-1", "action_ref": "act-1",
                                     "asserted_by": "alfonso_lopez"})
        ledger.append("trace_link", {"decision_ref": "dec-1", "action_ref": "ghost-9",
                                     "asserted_by": "alfonso_lopez"})
        report = single_bottleneck_metric(ledger)
        assert report.goals[0]["actions"] == 1
        assert len(report.dangling_link_assertions) == 1
        assert report.dangling_link_assertions[0]["action_ref"] == "ghost-9"
        assert "no receipt" in report.summary()

    def test_link_is_not_double_counted_when_both_paths_agree(self):
        ledger = _ledger()
        _intent(ledger)
        ref = _evidence(ledger)
        _decision(ledger, "dec-1", evidence_refs=[ref])
        _witness(ledger, "wit-1")
        _receipt(ledger, "act-1", "dec-1", "grant-1", "wit-1")   # carries decision_ref
        ledger.append("trace_link", {"decision_ref": "dec-1", "action_ref": "act-1",
                                     "asserted_by": "alfonso_lopez"})
        _outcome(ledger, "act-1")
        trace = TraceabilityWalker(ledger).trace("INTENT-9001")
        assert len(trace.actions) == 1

    def test_link_record_cannot_launder_an_unauthorized_effect(self):
        """Asserting a link does not confer authority on the action it names."""
        ledger = _ledger()
        _intent(ledger)
        ref = _evidence(ledger)
        _decision(ledger, "dec-1", evidence_refs=[ref])
        ledger.append("receipt", {"action_id": "act-1", "grant_id": None,
                                  "witness_id": None})
        ledger.append("trace_link", {"decision_ref": "dec-1", "action_ref": "act-1",
                                     "asserted_by": "someone"})
        _outcome(ledger, "act-1")
        report = single_bottleneck_metric(ledger)
        assert report.contaminated is True
        assert report.rate == 0.0


class TestFrozenAuthorityArtifacts:
    def test_consequence_gate_still_matches_its_frozen_continuity_hash(self):
        """traceability/ must never have been bought by editing an authority
        invariant. This test fails if a future change takes that shortcut."""
        import hashlib

        from evolution.repair import spec

        root = pathlib.Path(__file__).resolve().parents[2]
        rel = "policy/consequence_gate.py"
        expected = spec.CONTINUITY_ARTIFACT_SHA256[rel]
        actual = hashlib.sha256((root / rel).read_bytes()).hexdigest()
        assert actual == expected


class TestUnauthorizedEffects:
    def test_receipt_without_grant_is_unauthorized_and_contaminates(self):
        ledger = _ledger()
        _intent(ledger)
        ref = _evidence(ledger)
        _decision(ledger, "dec-1", evidence_refs=[ref])
        _witness(ledger)
        _receipt(ledger, "act-1", "dec-1", grant_id=None)
        _outcome(ledger)
        report = single_bottleneck_metric(ledger)
        assert report.unauthorized_external_effects == 1
        assert report.contaminated is True
        assert report.rate == 0.0

    def test_receipt_naming_an_absent_witness_is_unauthorized(self):
        ledger = _ledger()
        _intent(ledger)
        ref = _evidence(ledger)
        _decision(ledger, "dec-1", evidence_refs=[ref])
        # witness "wit-1" never appended
        _receipt(ledger, "act-1", "dec-1", witness_id="wit-1")
        _outcome(ledger)
        report = single_bottleneck_metric(ledger)
        assert report.contaminated is True
        assert any("absent from the ledger" in e["reason"]
                   for e in report.goals[0]["unauthorized_effects"])

    def test_effect_belonging_to_no_goal_still_contaminates(self):
        """The worst class: no goal's score is harmed, so only an institution-level
        counter can see it."""
        ledger = _ledger()
        _complete_chain(ledger)
        ledger.append("receipt", {"action_id": "rogue-1", "decision_ref": None,
                                  "grant_id": None, "witness_id": None})
        report = single_bottleneck_metric(ledger)
        # Every goal still traces perfectly...
        assert report.traceable_goals == report.completed_goals == 1
        assert report.rate == 100.0
        # ...and the report is still contaminated.
        assert report.contaminated is True
        assert report.unauthorized_external_effects == 1
        assert report.unattributed_effects[0]["action_id"] == "rogue-1"

    def test_authorized_unattributed_effect_does_not_contaminate(self):
        ledger = _ledger()
        _complete_chain(ledger)
        _witness(ledger, "wit-2")
        ledger.append("receipt", {"action_id": "act-2", "decision_ref": None,
                                  "grant_id": "grant-2", "witness_id": "wit-2"})
        report = single_bottleneck_metric(ledger)
        assert report.contaminated is False
        assert report.unauthorized_external_effects == 0


class TestAggregation:
    def test_rate_is_the_share_of_traceable_completed_goals(self):
        ledger = _ledger()
        _complete_chain(ledger, "INTENT-9005")
        _intent(ledger, "INTENT-9006", state="implemented")   # nothing downstream
        report = single_bottleneck_metric(ledger)
        assert report.completed_goals == 2
        assert report.traceable_goals == 1
        assert report.rate == 50.0
        assert report.false_completions == ["INTENT-9006"]

    def test_broken_link_counts_name_the_bottleneck(self):
        ledger = _ledger()
        for n in (1, 2, 3):
            gid = f"INTENT-90{n:02d}"
            _intent(ledger, gid)
            ref = _evidence(ledger, n)
            _decision(ledger, f"dec-{n}", gid, [ref])
            # no receipts anywhere: 'action' is the bottleneck for all three
        report = single_bottleneck_metric(ledger)
        assert report.broken_link_counts == {"action": 3}

    def test_summary_reports_refusal_and_contamination(self):
        assert "NOT REPORTABLE" in single_bottleneck_metric(_ledger()).summary()
        ledger = _ledger()
        _complete_chain(ledger)
        ledger.append("receipt", {"action_id": "rogue", "grant_id": None})
        assert "CONTAMINATED" in single_bottleneck_metric(ledger).summary()


class TestReadOnly:
    def test_walking_appends_nothing_to_the_ledger(self):
        ledger = _ledger()
        _complete_chain(ledger)
        before = len(ledger.records), ledger.head
        single_bottleneck_metric(ledger)
        TraceabilityWalker(ledger).trace_all()
        assert (len(ledger.records), ledger.head) == before

    def test_report_is_json_serializable(self):
        ledger = _ledger()
        _complete_chain(ledger)
        json.dumps(single_bottleneck_metric(ledger).to_dict())


class TestIntentContract:
    """The IntentRecord contract is the typed form of docs/FOUNDER_INTENT_LEDGER.md."""

    @staticmethod
    def _schema():
        return json.loads((CONTRACTS / "intent.schema.json").read_text())

    def test_contract_requires_all_fifteen_documented_fields(self):
        documented = {
            "intent_id", "statement", "source_refs", "owner", "state",
            "binding_scope", "constitutional_constraints", "success_evidence",
            "failure_evidence", "dependencies", "conflicts",
            "next_review_trigger", "supersedes", "superseded_by",
            "implementation_refs",
        }
        assert set(self._schema()["required"]) == documented

    def test_contract_states_match_the_founder_intent_ledger(self):
        assert set(self._schema()["properties"]["state"]["enum"]) == {
            "active", "implemented", "deferred", "superseded", "prohibited",
            "exploratory"}

    def test_a_valid_intent_record_validates(self):
        jsonschema = pytest.importorskip("jsonschema")
        ledger = _ledger()
        record = _intent(ledger)
        jsonschema.validate(record, self._schema())

    def test_decision_contract_carries_the_intent_link(self):
        decision = json.loads((CONTRACTS / "decision.schema.json").read_text())
        assert "intent_ref" in decision["properties"]
        # Optional: pre-existing decisions stay valid, and stay untraceable.
        assert "intent_ref" not in decision["required"]


def test_links_are_the_five_named_in_the_metric():
    assert LINKS == ("intent", "decision", "action", "evidence", "outcome")
