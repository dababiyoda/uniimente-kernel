"""Bridge B — Venture-to-Experiment, executed end to end.

VentureAssessment -> Strategy Tree -> Spider-Web Audit -> decisive unknown ->
ExperimentSpec -> approval requirement.

Composition only. `StrategyTree`, `SpiderWebAudit` and `ExperimentCompiler`
existed and were tested before this file; what was missing was the pathway that
makes any of them gate anything. An audit nothing consults is decoration, and
until now nothing consulted this one.

This bridge is the join between the other two. Bridge A ends at a canonical
`VentureAssessment` and deliberately stops, because an assessment is a claim
rather than a decision. Bridge C begins at a compiled `ExperimentSpec`. Bridge B
is the only thing that turns one into the other, and it is where every rule
about *not deciding too fast* has to be enforced or lost.

Five properties this pathway keeps:

**Eleven branches, or no selection.** `strategy_tree.BRANCH_KINDS` names eleven
mandated kinds, `do_nothing` among them. A tree missing any of them may not
select: "we considered the alternatives" is otherwise a sentence rather than a
fact. The missing kinds are named, never summarised as a count.

**An incomplete audit blocks the experiment.** `SpiderWebAudit.verdict` must
read COMPLETE. A failed side, a missing completeness requirement, or a
decorative mechanism still mapped all stop the bridge. This is the first place
in the institution where that verdict changes an outcome.

**Losing branches survive with their revival evidence.** Selection rejects the
others; it does not remove them. Every rejected branch keeps the reason it lost
and the cheapest test that would bring it back. Final Build Order section 12,
enforced rather than quoted.

**A capping adversarial case stops the venture.** The assessment adapter records
severe, unresolved against-cases as `capping_cases`. An experiment designed on
top of an unresolved fraud or incumbent-response case would be measuring the
wrong unknown, so the bridge refuses instead of proceeding.

**The bridge mints no capability grant.** The Final Build Order draws this
pathway as ending in one. It does not, and the deviation is deliberate: an
experiment that issued its own grant would be a component authorizing its own
promotion. What this produces is an *approval requirement* — a statement of the
grant a human would have to issue, carrying the assessment's own
`requires_human_approval: True` and `execution_authority: False` forward
unchanged. Bridge C then refuses to spend without that grant, which is where
the loop actually closes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from evolution.experiment import ExperimentCompiler, ExperimentSpec
from evolution.spider_web import SpiderWebAudit
from evolution.strategy_tree import BRANCH_KINDS, StrategyTree
from events.spine import Event, EventSpine
from provenance.ledger import EvidenceLedger

KERNEL = "spiffe://uniimente.internal/organ/constitutional-controller"

#: The reality axis of `blueprint.ladder`.
SIMULATED = "SIMULATED"

#: The audit verdict that permits an experiment. Any other value stops the run.
COMPLETE = "COMPLETE"

#: Assessment verdicts that may proceed to an experiment at all.
PROCEEDING_VERDICTS = ("go", "conditional_go")


class Halt(Enum):
    """Why a run stopped short. Every value is a refusal the institution wanted."""

    ASSESSMENT_REFUSES_TO_PROCEED = "assessment_refuses_to_proceed"
    CAPPING_CASE_UNRESOLVED = "capping_case_unresolved"
    TREE_INCOMPLETE = "tree_incomplete"
    NO_BRANCH_SELECTED = "no_branch_selected"
    AUDIT_INCOMPLETE = "audit_incomplete"
    EXPERIMENT_DOES_NOT_COMPILE = "experiment_does_not_compile"


@dataclass(frozen=True)
class ApprovalRequirement:
    """The grant a human would have to issue. Not a grant, and never becomes one."""

    capability: str
    #: Carried forward from the assessment verbatim. The bridge asserts these
    #: rather than deriving them, so no downstream reading can soften them.
    requires_human_approval: bool
    execution_authority: bool
    budget_usd: float
    consequence_class: str
    authority_requirements: tuple[str, ...]
    #: Why a human is being asked, in the words of the branch that won.
    justification: str
    granted: bool = False   # always False. A grant is issued elsewhere or not at all.


@dataclass(frozen=True)
class VentureRun:
    """What one traversal actually did. Derived; nothing here is supplied."""

    completed: bool
    halted_at: Halt | None = None
    reason: str = ""
    reality: str = SIMULATED
    #: The compiled experiment, ready for Bridge C. Present only on completion.
    experiment: ExperimentSpec | None = None
    approval: ApprovalRequirement | None = None
    #: The branch kinds the tree never considered. Named, not counted.
    missing_branch_kinds: tuple[str, ...] = ()
    #: What the audit could not clear.
    audit_verdict: str | None = None
    sides_failed: tuple[str, ...] = ()
    missing_completeness: tuple[str, ...] = ()
    #: Preserved losers, so a caller can read the trail without the tree.
    rejected_branches: tuple[dict, ...] = ()
    selected_branch_id: str | None = None
    event_ids: tuple[str, ...] = ()

    @property
    def reached_an_experiment(self) -> bool:
        return self.experiment is not None


def _emit_kernel_fact(spine: EventSpine, *, event_type: str, payload: dict,
                      causal_parent: str | None) -> str:
    """The kernel's own reading. Emitted, because the kernel is its source."""
    event = Event(
        type=event_type,
        source=KERNEL,
        actor=KERNEL,
        payload=payload,
        legal_principal="Alfonso Lopez",
        causal_parent=causal_parent,
    )
    spine.emit(event)
    return event.event_id


def run(assessment: dict, tree: StrategyTree, audit: SpiderWebAudit, *,
        decisive_unknown: str,
        selected_branch_id: str,
        selection_reason: str,
        metric: str, baseline: float, threshold: float, direction: str,
        verification: str = "cryptographic_receipt",
        consequence_class: str = "internal_write",
        ledger: EvidenceLedger | None = None) -> VentureRun:
    """Traverse Bridge B once.

    `assessment` is Bridge A's canonical output. The tree and audit are the
    caller's analysis; this bridge does not generate strategy, it refuses to
    proceed on analysis that is not complete.

    The measurement parameters are the caller's because the institution has no
    way to derive a threshold from an assessment — and inventing one would be
    exactly the fabricated field the adapters forbid.
    """
    ledger = ledger if ledger is not None else EvidenceLedger("bridge-b")
    spine = EventSpine(ledger)
    events: list[str] = []

    # --- leg 1: does the assessment permit an experiment at all? -------------
    verdict = assessment.get("verdict")
    if verdict not in PROCEEDING_VERDICTS:
        return VentureRun(completed=False, halted_at=Halt.ASSESSMENT_REFUSES_TO_PROCEED,
                          reason=f"assessment verdict {verdict!r} does not proceed")

    capping = tuple(assessment.get("adversarial_cases", {}).get("capping_cases", ()))
    if capping:
        return VentureRun(
            completed=False, halted_at=Halt.CAPPING_CASE_UNRESOLVED,
            reason=(f"severe unresolved adversarial cases cap this venture: {list(capping)}; "
                    f"an experiment built on top of them would measure the wrong unknown"))

    events.append(_emit_kernel_fact(
        spine, event_type="bridge.assessment_admitted",
        payload={"assessment_id": assessment.get("assessment_id"), "verdict": verdict},
        causal_parent=None))

    # --- leg 2: eleven branches, or no selection ----------------------------
    coverage = tree.coverage()
    missing = tuple(k for k in BRANCH_KINDS if not coverage.get(k))
    if missing:
        return VentureRun(
            completed=False, halted_at=Halt.TREE_INCOMPLETE,
            reason=(f"strategy tree never considered {len(missing)} of the eleven mandated "
                    f"branch kinds: {list(missing)}"),
            missing_branch_kinds=missing, event_ids=tuple(events))

    try:
        chosen = tree.select(selected_branch_id, decisive_unknown=decisive_unknown,
                             reason=selection_reason)
    except ValueError as exc:
        return VentureRun(completed=False, halted_at=Halt.NO_BRANCH_SELECTED,
                          reason=str(exc), event_ids=tuple(events))

    # Losing branches are preserved with the evidence that would revive them.
    rejected = tuple(b.to_dict() for b in tree.branches if b.rejected)

    events.append(_emit_kernel_fact(
        spine, event_type="bridge.strategy_branch_selected",
        payload={"tree_id": tree.tree_id, "selected": chosen.branch_id,
                 "rejected_preserved": len(rejected),
                 "decisive_unknown": decisive_unknown},
        causal_parent=events[-1]))

    # --- leg 3: the audit has to actually gate something --------------------
    if audit.verdict != COMPLETE:
        return VentureRun(
            completed=False, halted_at=Halt.AUDIT_INCOMPLETE,
            reason=f"spider-web audit verdict is {audit.verdict}, not {COMPLETE}",
            audit_verdict=audit.verdict,
            sides_failed=tuple(audit.sides_failed),
            missing_completeness=tuple(audit.missing_completeness),
            rejected_branches=rejected, selected_branch_id=chosen.branch_id,
            event_ids=tuple(events))

    events.append(_emit_kernel_fact(
        spine, event_type="bridge.audit_cleared",
        payload={"subject": audit.subject, "verdict": audit.verdict},
        causal_parent=events[-1]))

    # --- leg 4: the experiment, built from the branch that won --------------
    spec = ExperimentSpec(
        decisive_unknown=decisive_unknown,
        hypothesis=chosen.governing_assumption,
        prediction=chosen.expected_result,
        metric=metric, baseline=baseline, threshold=threshold, direction=direction,
        workflow=chosen.mechanism,
        required_capabilities=list(chosen.required_capabilities),
        authority_requirements=list(chosen.authority_requirements),
        budget_usd=float(chosen.cost_usd),
        # The branch declares its own irreversible downside; an experiment is
        # only reversible when that downside is absent. Reading it off the
        # branch rather than asserting True keeps the compiler's refusal live.
        reversible=chosen.irreversible_downside.strip().lower() in ("", "none"),
        rollback_path=chosen.cheapest_falsification_test,
        kill_condition=chosen.kill_condition,
        verification=verification)

    try:
        compiled = ExperimentCompiler().compile(spec)
    except ValueError as exc:
        return VentureRun(
            completed=False, halted_at=Halt.EXPERIMENT_DOES_NOT_COMPILE,
            reason=str(exc), audit_verdict=audit.verdict,
            rejected_branches=rejected, selected_branch_id=chosen.branch_id,
            event_ids=tuple(events))

    # --- leg 5: what a human would have to authorize ------------------------
    # Not a grant. The assessment's own two constants are carried forward
    # rather than recomputed, so nothing downstream can soften them.
    approval = ApprovalRequirement(
        capability=compiled.required_capabilities[0],
        requires_human_approval=bool(assessment["requires_human_approval"]),
        execution_authority=bool(assessment["execution_authority"]),
        budget_usd=compiled.budget_usd,
        consequence_class=consequence_class,
        authority_requirements=tuple(compiled.authority_requirements),
        justification=(f"branch {chosen.title!r} won on: {selection_reason}; "
                       f"its strongest counterargument stands: {chosen.strongest_counterargument}"))

    events.append(_emit_kernel_fact(
        spine, event_type="bridge.experiment_specified",
        payload={"experiment_id": compiled.experiment_id,
                 "requires_human_approval": approval.requires_human_approval,
                 "execution_authority": approval.execution_authority,
                 "granted": approval.granted,
                 "reality": SIMULATED},
        causal_parent=events[-1]))

    return VentureRun(
        completed=True, experiment=compiled, approval=approval,
        audit_verdict=audit.verdict, rejected_branches=rejected,
        selected_branch_id=chosen.branch_id, event_ids=tuple(events))
