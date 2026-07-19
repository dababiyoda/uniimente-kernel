"""Phase 4 — the three canonical agent-authored workflows.

Doctrine (AUTOMATION LOOM): at least three workflows authored BY the
machine, ratified BY the human, running on the durable spine. These are
the institution's first self-woven routines:

1. daily_reconciliation — outcomes vs expectations, every day, with a
   published (retractable) report.
2. evidence_floor_review — replays the admission corpus, measures weak
   admissions, drafts a floor-change proposal, and requires the human's
   approval before the recommendation is recorded.
3. venture_validation_gate — validates one opportunity packet against
   contracts, pre-screens it, and gates it behind human approval.

Authored by the loom-author agent; Alfonso ratifies; the spine executes.
"""
from __future__ import annotations

from loom.pattern import StepSpec, WorkflowPattern

AUTHOR = "spiffe://uniimente.internal/agent/loom-author"
PRINCIPAL = "alfonso_lopez"


def daily_reconciliation() -> WorkflowPattern:
    return WorkflowPattern(
        title="daily_reconciliation",
        objective="reconcile ledger outcomes against expectations; publish a retractable report",
        authored_by=AUTHOR, legal_principal=PRINCIPAL,
        required_capabilities=["ledger.read", "report.publish", "report.retract", "archive.write"],
        steps=[
            StepSpec(name="gather_outcomes", action="gather_outcomes",
                     capability="ledger.read", consequence_class="read_only",
                     params={"window": "1d"}),
            StepSpec(name="compare_expectations", action="compare_expectations",
                     capability="ledger.read", consequence_class="read_only"),
            StepSpec(name="publish_report", action="publish_report",
                     capability="report.publish", consequence_class="internal_write",
                     compensation="retract_report"),
            StepSpec(name="archive", action="archive",
                     capability="archive.write", consequence_class="read_only"),
        ])


def evidence_floor_review() -> WorkflowPattern:
    return WorkflowPattern(
        title="evidence_floor_review",
        objective="measure weak admissions; draft a floor proposal; human ratifies the recommendation",
        authored_by=AUTHOR, legal_principal=PRINCIPAL,
        required_capabilities=["corpus.replay", "proposal.draft", "recommendation.record",
                               "proposal.retract"],
        steps=[
            StepSpec(name="replay_corpus", action="replay_corpus",
                     capability="corpus.replay", consequence_class="read_only"),
            StepSpec(name="measure_weak_admissions", action="measure_weak",
                     capability="corpus.replay", consequence_class="read_only"),
            StepSpec(name="draft_proposal", action="draft_floor_proposal",
                     capability="proposal.draft", consequence_class="internal_write",
                     compensation="retract_proposal"),
            StepSpec(name="human_gate", action="present_to_founder",
                     capability="recommendation.record", consequence_class="external_contact",
                     approval_required=True, compensation="retract_proposal"),
            StepSpec(name="record_recommendation", action="record_recommendation",
                     capability="recommendation.record", consequence_class="internal_write",
                     compensation="retract_proposal"),
        ])


def venture_validation_gate() -> WorkflowPattern:
    return WorkflowPattern(
        title="venture_validation_gate",
        objective="validate one opportunity packet end-to-end behind a human gate",
        authored_by=AUTHOR, legal_principal=PRINCIPAL,
        required_capabilities=["packet.validate", "packet.prescreen", "gate.decide",
                               "decision.record", "decision.void"],
        steps=[
            StepSpec(name="validate_contract", action="validate_packet",
                     capability="packet.validate", consequence_class="read_only"),
            StepSpec(name="prescreen", action="prescreen_packet",
                     capability="packet.prescreen", consequence_class="read_only"),
            StepSpec(name="human_gate", action="present_to_founder",
                     capability="gate.decide", consequence_class="external_contact",
                     approval_required=True, compensation="void_decision"),
            StepSpec(name="record_decision", action="record_decision",
                     capability="decision.record", consequence_class="internal_write",
                     compensation="void_decision"),
        ])


CANONICAL = {"daily_reconciliation": daily_reconciliation,
             "evidence_floor_review": evidence_floor_review,
             "venture_validation_gate": venture_validation_gate}
