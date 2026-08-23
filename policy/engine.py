"""Policy engine: evaluates compiled UCL at proposal time and commit time.

Deny by default. Structured refusal reasons. The institution can read a
proposed action and state: which law applies, who is authorized, what
remains missing, what may happen, what must not happen, and why.

Evaluation order follows the sovereignty hierarchy: rank 1 (rights/law)
first, then absolute prohibitions, reserved matters, legal principal,
identity, evidence, budget, capability, expiry. A failure at any level is
terminal for the proposal; it never "continues with warnings".
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from compiler.ucl_compiler import CompiledConstitution, KERNEL_INVARIANT_REQUIREMENTS


class Verdict(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_HUMAN = "require_human"


# Evidence confidence floors per consequence class (bounded, declared).
EVIDENCE_THRESHOLDS = {
    "read_only": 0.0,
    "internal_write": 0.5,
    "external_contact": 0.7,
    "financial": 0.8,
    "irreversible": 0.9,
}

# Consequence classes that always wait for a human, per doctrine.
ALWAYS_HUMAN_CLASSES = ("irreversible",)

#: What an external action must demonstrate, beyond the evidence floor.
#:
#: CONTRADICTION-0003 Option B, ratified 2026-08-23. The floor alone was being
#: asked to mean two things, and for a first canary they point opposite ways:
#: the evidence that running it is justified is strong *because* the outcome is
#: uncertain. The founder's ruling names what the external-action policy should
#: actually judge — "sufficiently evidenced, contained, authorized, reversible,
#: observable, killable, and proportionate" — "rather than requiring us to
#: pretend beforehand that the experiment will probably succeed".
#:
#: These are additional REQUIREMENTS, not a discount on the floor. Nothing here
#: lowers 0.70; a proposal must now clear the floor *and* declare containment.
#: Each must be stated affirmatively in `proposal.context` — absence is refusal,
#: never assent, so an action that simply forgot to declare its kill switch is
#: refused exactly like one that has none.
CONTAINMENT_REQUIREMENTS = {
    "contained": "the blast radius is bounded and stated",
    "reversible": "the effect can be undone, or its persistence is stated and accepted",
    "observable": "the outcome can be verified from outside the acting process",
    "killable": "a kill switch exists and is reachable during the action",
    "proportionate": "the exposure is proportionate to what is being learned",
}

#: Consequence classes that must satisfy `CONTAINMENT_REQUIREMENTS`.
#: `read_only` and `internal_write` are excluded: they touch nothing outside the
#: institution, and demanding a containment declaration for a log write would
#: turn a real check into a form everybody fills in without reading.
CONTAINED_CLASSES = ("external_contact", "financial", "irreversible")


@dataclass
class Proposal:
    """A proposed action. Agents propose; the Kernel decides."""
    actor: str                     # machine passport id
    legal_principal: str
    action_class: str
    objective: str
    payload: dict
    target: str
    consequence_class: str
    #: "How strong is the evidence that taking this bounded action is
    #: justified?" This is what the floors above gate on, and the only
    #: confidence that governs admission.
    evidence_confidence: float
    evidence_refs: list[str]
    estimated_cost_usd: float
    requested_capability: str
    expected_outcome: str
    context: dict = field(default_factory=dict)
    #: "How likely do we predict this achieves its preregistered outcome?"
    #:
    #: Added 2026-08-23 under CONTRADICTION-0003 Option A. **Never read by
    #: `evaluate`** — asserted structurally by
    #: `test_the_engine_never_reads_the_prediction_when_deciding`. It exists so
    #: the durable record can carry a forecast for Bridge D to score, without
    #: that forecast having to clear a policy floor.
    #:
    #: `None` for the majority of actions, which predict nothing because they
    #: are not experiments. None means absent, never 0.5.
    predicted_success_probability: float | None = None
    proposal_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class PolicyDecision:
    verdict: Verdict
    reasons: list[str]             # structured refusal / pend reasons
    law_applied: list[str]         # which law/rules fired
    missing: list[str]             # what remains missing to allow
    rule_ids: list[str]


def evaluate(compiled: CompiledConstitution, proposal: Proposal,
             *, identity_ok: bool, grant: dict | None,
             now: datetime | None = None,
             thresholds: dict | None = None) -> PolicyDecision:
    """Evaluate a proposal. Pure function of (compiled doctrine, proposal,
    identity verdict, current grant). Deny by default.

    thresholds: optional evidence-floor override per consequence class
    (defaults to EVIDENCE_THRESHOLDS). Evolution cycles may test candidate
    floors in simulation; production floors change only by ratified policy.
    """
    now = now or datetime.now(timezone.utc)
    floors = thresholds or EVIDENCE_THRESHOLDS
    reasons: list[str] = []
    missing: list[str] = []
    law: list[str] = []
    rules: list[str] = []

    # Rank 1: participant rights. Absolute effect classes are handled by the
    # reserved-matters prohibitions below; rights additionally refuse any
    # proposal whose context flags a rights violation.
    if proposal.context.get("foreseeable_physical_harm") or proposal.context.get("deception"):
        return PolicyDecision(Verdict.DENY, ["proposal context violates a rank-1 participant right"],
                              ["participant-rights.ucl"], [], ["right:safety"])
    law.append("participant-rights.ucl")

    # Absolute prohibitions (reserved matters with requires: []).
    if proposal.action_class in compiled.reserved_matters and not compiled.reserved_matters[proposal.action_class]:
        return PolicyDecision(Verdict.DENY, [f"{proposal.action_class} is absolutely prohibited; no one may authorize it"],
                              ["reserved-matters.yaml", "constitution.ucl"], [], [f"prohibit:{proposal.action_class}"])
    law.append("reserved-matters.yaml")

    # Legal principal must be valid and never UNIIMENTE.
    if proposal.legal_principal in compiled.prohibited_principals:
        return PolicyDecision(Verdict.DENY, [f"{proposal.legal_principal} is prohibited as a legal principal"],
                              ["legal-principals.yaml"], [], ["never_uniimente_principal"])
    if proposal.legal_principal not in compiled.legal_principals:
        return PolicyDecision(Verdict.DENY, [f"unknown legal principal {proposal.legal_principal!r} (hard refusal)"],
                              ["legal-principals.yaml"], [], ["valid_legal_principal"])
    law.append("legal-principals.yaml")

    # Identity: recognized machine passport required.
    if not identity_ok:
        return PolicyDecision(Verdict.DENY, ["actor identity not recognized (unknown, expired, or revoked passport)"],
                              ["service-identities.yaml"], ["recognized_identity"], ["recognized_identity"])
    law.append("identity")

    # Reserved matters requiring a human.
    req = compiled.reserved_matters.get(proposal.action_class)
    if req:
        rules.append(f"reserved:{proposal.action_class}")
        return PolicyDecision(Verdict.REQUIRE_HUMAN,
                              [f"{proposal.action_class} is reserved; requires {', '.join(req)}"],
                              law, ["human_approval"], rules)

    # Consequence class always requiring human approval.
    if proposal.consequence_class in ALWAYS_HUMAN_CLASSES:
        return PolicyDecision(Verdict.REQUIRE_HUMAN,
                              [f"consequence class {proposal.consequence_class} always requires human approval"],
                              law + ["approval-lifecycle.yaml"], ["human_approval"], rules)

    # Grant: at proposal time the gate may issue capability next, so a missing
    # grant is not itself a refusal; but a non-zero cost with no budget
    # authorization is. At commit time a grant is always present and is fully
    # revalidated.
    if grant is None:
        if proposal.estimated_cost_usd > 0:
            reasons.append(f"non-zero cost {proposal.estimated_cost_usd} with no budget authorization")
            missing.append("budget_authorization")
    else:
        if grant.get("revoked"):
            reasons.append("grant is revoked")
        elif now >= datetime.fromisoformat(grant["expires_at"].replace("Z", "+00:00")):
            reasons.append("grant is expired")
        if proposal.requested_capability not in grant.get("permitted_actions", []):
            reasons.append(f"capability {proposal.requested_capability!r} not in grant")
        if proposal.legal_principal != grant.get("legal_actor"):
            reasons.append("grant legal_actor mismatch (cross-principal credentials prohibited)")
        if proposal.estimated_cost_usd > float(grant.get("spending_limit_usd", 0)):
            reasons.append(f"estimated cost {proposal.estimated_cost_usd} exceeds grant spending limit "
                           f"{grant.get('spending_limit_usd')}")
        if proposal.action_class in grant.get("prohibited", []):
            reasons.append(f"{proposal.action_class} is prohibited by the grant itself")
        stage = grant.get("stage", grant.get("initial_stage", "simulate"))
        if stage in ("simulate", "shadow") and proposal.consequence_class not in ("read_only", "internal_write"):
            reasons.append(f"grant stage {stage} may not execute {proposal.consequence_class} effects")
    law.append("capability-grant.schema.json")

    # Evidence sufficiency.
    floor = floors.get(proposal.consequence_class, 1.0)
    if proposal.evidence_confidence < floor:
        reasons.append(f"evidence confidence {proposal.evidence_confidence:.2f} below floor {floor:.2f} "
                       f"for {proposal.consequence_class}")
        missing.append("sufficient_evidence")
    if not proposal.evidence_refs and floor > 0:
        reasons.append("no evidence references supplied")
        missing.append("sufficient_evidence")
    law.append("evidence.schema.json")

    # Containment sufficiency (CONTRADICTION-0003 Option B). Additional to the
    # floor above, never a substitute for it. Fails closed: an undeclared
    # property is treated exactly like an absent one.
    if proposal.consequence_class in CONTAINED_CLASSES:
        for prop, description in CONTAINMENT_REQUIREMENTS.items():
            if proposal.context.get(prop) is not True:
                reasons.append(
                    f"{proposal.consequence_class} action does not declare "
                    f"'{prop}': {description}")
                missing.append(f"containment:{prop}")
        rules.append("containment_declared")
        law.append("sovereignty.ucl")

    if reasons:
        return PolicyDecision(Verdict.DENY, reasons, law, missing, rules + ["deny_by_default"])

    return PolicyDecision(Verdict.ALLOW, ["all kernel invariant preconditions satisfied"],
                          law + ["constitution.ucl"], [], rules + ["kernel_invariant"])


def explain(compiled: CompiledConstitution, proposal: Proposal, decision: PolicyDecision) -> dict:
    """The science-fiction behavior, concretely: the institution states which
    law applies, who is authorized, what remains missing, what may happen,
    what must not happen, and why."""
    return {
        "which_law_applies": decision.law_applied,
        "who_is_authorized": [who for who, spec in compiled.authorities.items()
                              if proposal.action_class in (spec.get("may") or [])],
        "what_remains_missing": decision.missing,
        "what_may_happen": proposal.expected_outcome if decision.verdict == Verdict.ALLOW else "nothing; refused",
        "what_must_not_happen": [m for m, req in compiled.reserved_matters.items() if req == []],
        "why": decision.reasons,
        "verdict": decision.verdict.value,
    }
