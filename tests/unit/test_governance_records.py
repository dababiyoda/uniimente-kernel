"""The governance records must stay valid, and must stay honest about themselves.

`docs/FOUNDER_INTENT_LEDGER.md` says the ledger "should ultimately become
machine-readable. Until that implementation lands, issues and ADRs must use these
fields verbatim." It has landed: `governance/intents.json` and
`docs/deliberations/*.json` are validated by the
install-recursive-founder-intent-collaboration-protocol validators.

Those validators live in the skill, not the repository, so CI cannot invoke them.
These tests re-assert the properties that matter most, against the committed
records, so a record cannot rot between skill invocations.
"""
from __future__ import annotations

import json
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LEDGER = os.path.join(ROOT, "governance", "intents.json")
DELIBERATIONS = os.path.join(ROOT, "docs", "deliberations")

INTENT_REQUIRED = (
    "intent_id", "title", "statement", "source", "source_location", "status",
    "authority_level", "consequence_class", "intended_outcome", "affected_systems",
    "rationale", "conflicts", "evidence_refs", "implementation_refs", "owner",
    "next_review_trigger", "unresolved_questions", "created_at", "updated_at",
)
LIFECYCLE = {"active", "implemented", "deferred", "superseded", "prohibited",
             "exploratory", "conflicted", "needs_evidence"}
WEAK_AUTHORITY = {"aspiration", "exploratory", "advisory", "unknown"}
DECISIONS = {"RETAIN", "REGRESS", "KILL", "DEFER", "EXPERIMENT",
             "NEEDS_FOUNDER_DECISION"}


@pytest.fixture(scope="module")
def intents() -> list[dict]:
    with open(LEDGER, encoding="utf-8") as fh:
        return json.load(fh)["intents"]


@pytest.fixture(scope="module")
def deliberations() -> list[dict]:
    out = []
    for name in sorted(os.listdir(DELIBERATIONS)):
        if name.endswith(".json"):
            with open(os.path.join(DELIBERATIONS, name), encoding="utf-8") as fh:
                out.append(json.load(fh))
    return out


# ------------------------------------------------------------------ ledger
def test_every_intent_carries_every_required_field(intents):
    assert intents
    for record in intents:
        missing = [f for f in INTENT_REQUIRED if f not in record]
        assert not missing, f"{record.get('intent_id')} missing {missing}"
        assert record["status"] in LIFECYCLE


def test_a_weak_authority_may_not_carry_an_active_status(intents):
    """The rule that stops an aspiration becoming an executable requirement."""
    for r in intents:
        if r["status"] in {"active", "implemented"}:
            assert r["authority_level"] not in WEAK_AUTHORITY, (
                f"{r['intent_id']}: {r['authority_level']!r} cannot authorize "
                f"status {r['status']!r}"
            )


def test_an_implemented_intent_names_where_it_is_implemented(intents):
    for r in intents:
        if r["status"] == "implemented":
            assert r["implementation_refs"], (
                f"{r['intent_id']} claims implemented with no implementation_refs"
            )


def test_a_conflicted_intent_names_its_conflict(intents):
    conflicted = [r for r in intents if r["status"] == "conflicted"]
    assert conflicted, "the router conflict should be recorded as a conflicted intent"
    for r in conflicted:
        assert r["conflicts"], f"{r['intent_id']} is conflicted but names no conflict"


def test_a_deferred_intent_names_what_would_revive_it(intents):
    for r in intents:
        if r["status"] == "deferred":
            assert r["next_review_trigger"].strip()


def test_the_constitutional_invariants_are_recorded_and_owned(intents):
    invariants = {r["intent_id"] for r in intents
                  if r["authority_level"] == "constitutional_invariant"}
    # No self-authorized authority; preserve contradictions; vocabulary is not sovereignty.
    assert {"INT-OM-004", "INT-OM-012", "INT-OM-013"} <= invariants
    for r in intents:
        if r["authority_level"] == "constitutional_invariant":
            assert r["consequence_class"] == "constitutional"


def test_intent_ids_are_unique(intents):
    ids = [r["intent_id"] for r in intents]
    assert len(ids) == len(set(ids))


# ----------------------------------------------------------- deliberations
def test_each_deliberation_has_five_roles_and_exactly_two_passes(deliberations):
    assert len(deliberations) >= 2
    for d in deliberations:
        assert len(d["roles"]) >= 5, f"{d['decision_id']} has fewer than five roles"
        assert "pass_1" in d and "pass_2" in d
        assert "pass_3" not in d, "there is no invisible third pass"


def test_each_deliberation_compares_do_nothing_and_a_competitor(deliberations):
    for d in deliberations:
        assert d["do_nothing_option"]["disadvantages"]
        comparisons = d["pass_1"]["comparisons"]
        for key in ("baseline", "do_nothing", "simplest_viable_alternative",
                    "strongest_competing_architecture", "reversible_experiment"):
            assert comparisons[key].strip(), f"{d['decision_id']} omits {key}"


def test_every_pass_1_disadvantage_is_dispositioned_in_pass_2(deliberations):
    """A Pass-1 downside may not disappear from the record."""
    for d in deliberations:
        raised = {x["id"] for x in d["pass_1"]["disadvantages"]}
        handled = {x["disadvantage_id"]
                   for x in d["pass_2"]["pass_1_disadvantage_dispositions"]}
        assert raised == handled, (
            f"{d['decision_id']}: disadvantages {raised - handled} vanished between passes"
        )


def test_dissent_is_preserved_with_an_owner_and_a_threshold(deliberations):
    for d in deliberations:
        if d["dissent"]["present"]:
            assert d["dissent"]["entries"]
            for e in d["dissent"]["entries"]:
                assert e["evidence_threshold"].strip()
                assert e["owner"].strip()
                assert e["review_trigger"].strip()


def test_every_decision_is_one_of_the_six_and_constitutional_ones_await_a_human(
        deliberations):
    for d in deliberations:
        assert d["decision"] in DECISIONS
        if d["authority_impact"]["level"] == "constitutional":
            assert d["authority_impact"]["requires_authorized_human"] is True
            assert d["authority_impact"]["approval_status"] == "pending"
            assert d["decision"] == "NEEDS_FOUNDER_DECISION", (
                f"{d['decision_id']} is constitutional but decided without a human"
            )


def test_no_deliberation_claims_to_change_authority(deliberations):
    for d in deliberations:
        assert d["authority_impact"]["changes_authority"] is False


def test_rollback_and_kill_criteria_are_concrete(deliberations):
    for d in deliberations:
        rb = d["rollback_plan"]
        assert rb["possible"] is True and rb["steps"]
        assert d["kill_criteria"], f"{d['decision_id']} names no kill criterion"


def test_the_two_open_blockers_each_have_a_deliberation(deliberations):
    ids = {d["decision_id"] for d in deliberations}
    assert {"DEC-OM-001", "DEC-OM-002"} <= ids
    by_id = {d["decision_id"]: d for d in deliberations}
    assert "canonical selector" in by_id["DEC-OM-001"]["title"].lower()
    assert "contradiction-0001" in by_id["DEC-OM-002"]["title"].lower()


def test_deliberations_reference_real_intent_records(deliberations, intents):
    known = {r["intent_id"] for r in intents}
    for d in deliberations:
        assert d["founder_intent_refs"]
        for ref in d["founder_intent_refs"]:
            assert ref in known, f"{d['decision_id']} cites unknown intent {ref}"
