"""Founder Intent Ledger and deliberation records, enforced inside the kernel.

Why these live here rather than calling the protocol skill's validators
----------------------------------------------------------------------
The recursive founder-intent collaboration protocol ships two validator scripts.
Running those in CI would make the build depend on a file under ~/.claude/skills
— outside version control, invisible to review, and absent from a fresh clone.
That is the same hidden-workspace-state failure the Golden Kernel
clean-reproducibility condition exists to prevent, and it would be a poor way to
install a governance protocol.

So the kernel enforces its own governance rules over its own records, in its own
suite, with no external dependency. The skill's validators remain useful as an
optional external cross-check: two implementations agreeing is cheap
corroboration. They are not the authority. This file is.

See docs/deliberations/D-001-intent-record-canonicalization.json, weakness W3.
"""
import json
import os
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
LEDGER = ROOT / "docs" / "intent" / "ledger.json"
DELIBERATIONS = ROOT / "docs" / "deliberations"

LIFECYCLE_STATES = {
    "active", "implemented", "deferred", "superseded", "prohibited",
    "exploratory", "conflicted", "needs_evidence",
}

#: An intent at one of these authority levels is not permitted to claim a state
#: that asserts it binds anything. This is the executable form of the founder's
#: rule that no aspiration becomes executable merely because it appears in prose.
NON_BINDING_AUTHORITY = {"aspiration", "exploratory", "advisory", "unknown"}

BINDING_STATES = {"active", "implemented"}

AUTHORITY_LEVELS = {
    "aspiration", "exploratory", "advisory", "active_requirement",
    "delegated_authority", "constitutional_invariant", "external_constraint",
    "unknown",
}

CONSEQUENCE_CLASSES = {"low", "bounded", "material", "constitutional"}

DECISIONS = {
    "RETAIN", "REGRESS", "KILL", "DEFER", "EXPERIMENT", "NEEDS_FOUNDER_DECISION",
}

#: The five canonical roles of docs/RECURSIVE_COLLABORATION_PROTOCOL.md section 1,
#: installed in Package 2 and already used by .github/pull_request_template.md.
#: The external protocol skill names its roles differently; that vocabulary was
#: deliberately NOT adopted, because replacing a working one to match an imported
#: template would destroy institutional memory for no control advantage. See
#: docs/RECURSIVE_COLLABORATION_PROTOCOL.md section 7.2.
REQUIRED_ROLES = {
    "builder",
    "adversary",
    "operator",
    "beneficiary representative",
    "constitutional reviewer",
}

#: Organs whose files this repository cannot see. An implementation_ref pointing
#: into one of these is allowed, but only if the record declares that organ.
SIBLING_ORGANS = {"DALEOBANKS", "WealthMachineIntelligence", "PumpStation",
                  "uniimente-golden-kernel"}


def _ledger():
    return json.loads(LEDGER.read_text(encoding="utf-8"))


def _deliberations():
    return [(p, json.loads(p.read_text(encoding="utf-8")))
            for p in sorted(DELIBERATIONS.glob("*.json"))]


class TestLedgerShape:
    def test_ledger_exists_and_is_a_non_empty_list(self):
        records = _ledger()
        assert isinstance(records, list) and records

    def test_intent_ids_are_unique(self):
        ids = [r["intent_id"] for r in _ledger()]
        assert len(ids) == len(set(ids)), "duplicate intent_id in the ledger"

    def test_every_record_carries_the_required_fields(self):
        required = {
            "intent_id", "statement", "source_refs", "owner", "state",
            "binding_scope", "constitutional_constraints", "success_evidence",
            "failure_evidence", "dependencies", "conflicts",
            "next_review_trigger", "supersedes", "superseded_by",
            "implementation_refs",
            # Proposed by ADR-001, present in the ledger, not yet in the contract
            "authority_level", "consequence_class", "title", "intended_outcome",
            "rationale", "unresolved_questions",
        }
        for record in _ledger():
            missing = required - set(record)
            assert not missing, f"{record.get('intent_id')} missing {sorted(missing)}"

    def test_enumerated_fields_use_declared_values(self):
        for record in _ledger():
            rid = record["intent_id"]
            assert record["state"] in LIFECYCLE_STATES, f"{rid}: bad state"
            assert record["authority_level"] in AUTHORITY_LEVELS, f"{rid}: bad authority_level"
            assert record["consequence_class"] in CONSEQUENCE_CLASSES, f"{rid}: bad consequence_class"

    def test_owner_is_a_human_not_an_organ(self):
        """Accountability never resolves to a system. Intelligence never
        creates authority, and an organ cannot be responsible for an intent."""
        for record in _ledger():
            owner = record["owner"]
            assert owner not in SIBLING_ORGANS and "organ/" not in owner, \
                f"{record['intent_id']}: owner {owner!r} is not a human legal principal"


class TestPendingContractGap:
    """The ledger is a superset of the canonical contract, by exactly six fields.

    ADR-001 proposes adding those six to contracts/intent.schema.json. It is not
    applied, because it amends a constitutional contract and the founder has not
    approved it. Until then the ledger satisfies every requirement the contract
    states and carries six fields the contract does not yet know about.

    This test pins that gap to its exact shape. If it widens, someone has added a
    field without going through ADR-001. If it closes, the contract was extended
    and this test should be deleted along with the pending status.
    """

    PROPOSED_FIELDS = {
        "authority_level", "consequence_class", "title", "intended_outcome",
        "rationale", "unresolved_questions",
    }

    @staticmethod
    def _contract():
        return json.loads(
            (ROOT / "contracts" / "intent.schema.json").read_text(encoding="utf-8"))

    def test_every_record_satisfies_every_current_contract_requirement(self):
        required = set(self._contract()["required"])
        for record in _ledger():
            missing = required - set(record)
            assert not missing, (
                f"{record['intent_id']} fails the CURRENT contract on "
                f"{sorted(missing)} — that is a defect, not the pending gap"
            )

    def test_the_gap_is_exactly_the_six_fields_adr_001_proposes(self):
        allowed = set(self._contract()["properties"])
        extra = set()
        for record in _ledger():
            extra |= set(record) - allowed
        assert extra == self.PROPOSED_FIELDS, (
            f"the ledger/contract gap is {sorted(extra)}, not the six fields "
            f"ADR-001 proposes ({sorted(self.PROPOSED_FIELDS)}). A field was "
            "added or removed outside the deliberation."
        )

    def test_intent_ids_match_the_contract_pattern(self):
        import re

        pattern = self._contract()["properties"]["intent_id"]["pattern"]
        for record in _ledger():
            assert re.fullmatch(pattern, record["intent_id"]), (
                f"{record['intent_id']!r} does not match the contract pattern "
                f"{pattern!r}"
            )

    def test_the_markdown_record_that_predates_the_contract_is_in_the_ledger(self):
        """INTENT-0001 existed as markdown before either schema. It set the ID
        convention the contract now follows, and it must not be orphaned."""
        ids = {r["intent_id"] for r in _ledger()}
        assert "INTENT-0001" in ids
        assert (ROOT / "docs" / "intent"
                / "INTENT-0001-uniimente-as-legal-principal.md").exists()


class TestAspirationCannotBecomeAuthority:
    """The rule the whole ledger exists to enforce."""

    def test_non_binding_authority_cannot_claim_a_binding_state(self):
        for record in _ledger():
            if record["state"] in BINDING_STATES:
                assert record["authority_level"] not in NON_BINDING_AUTHORITY, (
                    f"{record['intent_id']}: authority_level "
                    f"{record['authority_level']!r} cannot support status "
                    f"{record['state']!r} — an aspiration does not become "
                    "executable by being written down"
                )

    def test_the_ledger_actually_contains_a_non_binding_record(self):
        """Guards the rule above from passing vacuously. If every record were a
        requirement, the rule would be untested and the ledger would be evidence
        that nothing was ever classified as a brainstorm."""
        levels = {r["authority_level"] for r in _ledger()}
        assert levels & NON_BINDING_AUTHORITY, (
            "no record is classified as non-binding; either the ledger is "
            "missing the founder's exploratory material or classification is "
            "being inflated"
        )


class TestCompletionClaims:
    def test_implemented_requires_implementation_refs(self):
        """Same false-completion check the Single Bottleneck Metric applies."""
        for record in _ledger():
            if record["state"] == "implemented":
                assert record["implementation_refs"], (
                    f"{record['intent_id']}: claims implemented with nothing "
                    "enforcing it"
                )

    def test_conflicted_requires_a_named_conflict(self):
        for record in _ledger():
            if record["state"] == "conflicted":
                assert record["conflicts"], \
                    f"{record['intent_id']}: conflicted with no conflict named"

    def test_needs_evidence_requires_a_decisive_question(self):
        for record in _ledger():
            if record["state"] == "needs_evidence":
                assert record["unresolved_questions"], (
                    f"{record['intent_id']}: needs_evidence with no question "
                    "that would resolve it"
                )

    def test_conflict_references_resolve_to_real_intents(self):
        known = {r["intent_id"] for r in _ledger()}
        for record in _ledger():
            for ref in record["conflicts"]:
                assert ref in known, \
                    f"{record['intent_id']}: conflicts with unknown {ref!r}"

    def test_every_record_is_dated(self):
        for record in _ledger():
            assert record.get("recorded_at"), \
                f"{record['intent_id']}: no recorded_at"


class TestCitationsAreNotFabricated:
    """A control cited against a file that does not exist is not a control.

    The same discipline PumpStation's feature matrix applies to its own
    evidence references.
    """

    def test_kernel_implementation_refs_resolve_or_declare_their_organ(self):
        for record in _ledger():
            organs = set(record["binding_scope"])
            for ref in record["implementation_refs"]:
                if (ROOT / ref).exists():
                    continue
                # Not a kernel path. Permitted only if this record declares a
                # sibling organ, which is where the file must live.
                assert organs & SIBLING_ORGANS, (
                    f"{record['intent_id']}: implementation_ref {ref!r} does not "
                    "exist in this repository and the record declares no sibling "
                    "organ that could contain it"
                )

    def test_at_least_one_ref_in_the_ledger_is_checked_here(self):
        """Keeps the check above from passing because nothing was checkable."""
        checked = sum(
            1
            for record in _ledger()
            for ref in record["implementation_refs"]
            if (ROOT / ref).exists()
        )
        assert checked > 0, "no implementation_ref resolved inside this repository"


class TestDeliberationRecords:
    def test_at_least_one_deliberation_exists(self):
        assert _deliberations(), "no deliberation records found"

    def test_five_required_roles_are_present(self):
        for path, record in _deliberations():
            roles = {r["role"].strip().casefold() for r in record["roles"]}
            missing = REQUIRED_ROLES - roles
            assert not missing, f"{path.name}: missing role(s) {sorted(missing)}"

    def test_exactly_two_passes(self):
        for path, record in _deliberations():
            passes = {k for k in record if k.startswith("pass_")}
            assert passes == {"pass_1", "pass_2"}, \
                f"{path.name}: expected exactly pass_1 and pass_2, found {sorted(passes)}"

    def test_every_pass_1_disadvantage_is_disposed_of(self):
        """No disadvantage disappears quietly between the passes."""
        for path, record in _deliberations():
            raised = {d["id"] for d in record["pass_1"]["disadvantages"]}
            disposed = {d["disadvantage_id"]
                        for d in record["pass_2"]["pass_1_disadvantage_dispositions"]}
            assert raised == disposed, (
                f"{path.name}: silently omitted {sorted(raised - disposed)}, "
                f"unknown {sorted(disposed - raised)}"
            )

    def test_decision_matches_the_second_pass_recommendation(self):
        for path, record in _deliberations():
            assert record["decision"] in DECISIONS, f"{path.name}: bad decision"
            assert record["decision"] == record["pass_2"]["recommendation"], (
                f"{path.name}: decision {record['decision']!r} contradicts "
                f"pass_2 recommendation {record['pass_2']['recommendation']!r}"
            )

    def test_dissent_presence_matches_its_entries(self):
        for path, record in _deliberations():
            dissent = record["dissent"]
            assert bool(dissent["present"]) == bool(dissent["entries"]), (
                f"{path.name}: dissent.present contradicts its entries — "
                "manufactured consensus or lost objection"
            )

    def test_residual_risks_are_never_empty(self):
        """A design with no residual risk has not been attacked."""
        for path, record in _deliberations():
            assert record["pass_2"]["residual_risks"], \
                f"{path.name}: pass_2 records no residual risk"


class TestConstitutionalDecisionsCannotSelfApprove:
    """The rule that stopped this protocol's own installation.

    A constitutional or authority-changing decision may not resolve to anything
    other than NEEDS_FOUNDER_DECISION until a named human has actually approved
    it. Recording an approval that did not happen is fabricated authorization.
    """

    def test_constitutional_decisions_require_human_approval(self):
        for path, record in _deliberations():
            authority = record["authority_impact"]
            if authority["level"] == "constitutional" or authority["changes_authority"]:
                assert authority["requires_authorized_human"] is True, (
                    f"{path.name}: constitutional or authority-changing decision "
                    "does not require human approval"
                )

    def test_unapproved_decisions_stay_at_needs_founder_decision(self):
        for path, record in _deliberations():
            authority = record["authority_impact"]
            if authority["requires_authorized_human"] is not True:
                continue
            if authority["approval_status"] == "approved":
                assert authority.get("approver"), \
                    f"{path.name}: approved with no approver named"
                assert record["decision"] != "NEEDS_FOUNDER_DECISION", (
                    f"{path.name}: approved authority contradicts "
                    "NEEDS_FOUNDER_DECISION"
                )
            else:
                assert record["decision"] == "NEEDS_FOUNDER_DECISION", (
                    f"{path.name}: decision {record['decision']!r} claims authority "
                    f"that is only {authority['approval_status']!r}. An unapproved "
                    "constitutional decision stays at NEEDS_FOUNDER_DECISION."
                )

    def test_rollback_is_stated_or_its_absence_is_justified(self):
        for path, record in _deliberations():
            rollback = record["rollback_plan"]
            if rollback["possible"]:
                assert rollback["steps"], f"{path.name}: rollback possible but no steps"
            else:
                assert rollback["reason_impossible"], \
                    f"{path.name}: rollback impossible with no reason given"


def test_ledger_and_deliberations_cross_reference():
    """Every founder intent a deliberation claims to serve must exist."""
    known = {r["intent_id"] for r in _ledger()}
    for path, record in _deliberations():
        for ref in record["founder_intent_refs"]:
            assert ref in known, f"{path.name}: references unknown intent {ref!r}"
