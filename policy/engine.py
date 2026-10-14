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

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from functools import lru_cache
from typing import Mapping

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

# Maximum age of an evidence packet (contracts/evidence.schema.json captured_at)
# per consequence class, applied when the Gate holds an evidence register. A
# packet's own fresh_until can only shorten it. Bounded, declared defaults:
# production ages change only by ratified policy, like EVIDENCE_THRESHOLDS.
EVIDENCE_MAX_AGE = {
    "read_only": timedelta(days=365),
    "internal_write": timedelta(days=30),
    "external_contact": timedelta(days=7),
    "financial": timedelta(days=1),
    "irreversible": timedelta(days=1),
}
# A packet stamped later than this past the evaluator's clock is ambiguous, so refused.
EVIDENCE_CLOCK_SKEW = timedelta(minutes=2)


@lru_cache(maxsize=1)
def _evidence_contract():
    from importlib.resources import files
    from jsonschema import Draft202012Validator, FormatChecker
    schema = json.loads(files("contracts").joinpath("evidence.schema.json").read_bytes())
    Draft202012Validator.check_schema(schema)
    checker = FormatChecker()
    if {"date-time", "uuid"} - checker.checkers.keys():
        # Without them jsonschema passes every timestamp; a smaller install must not weaken this.
        raise ValueError("evidence contract format implementation unavailable")
    return Draft202012Validator(schema, format_checker=checker)


def _instant(value) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp is not a string")
    instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if instant.tzinfo is None:
        raise ValueError("timestamp has no timezone")
    return instant


def evidence_freshness_reasons(refs: list[str], register: Mapping[str, dict], consequence_class: str,
                               now: datetime) -> list[str]:
    """Resolve every evidence ref in the register; unknown or stale evidence refuses.

    Mechanism of PR #21 kernel/gate/revalidate.py check_evidence_freshness, re-expressed
    against the canonical evidence contract. Ambiguity fails closed: an id the register
    does not hold, a packet that does not validate against contracts/evidence.schema.json
    or whose packet_id differs from the ref, a timestamp without a timezone, a packet
    captured in the future, or a class with no declared maximum age. A packet is stale at
    min(captured_at + EVIDENCE_MAX_AGE[class], fresh_until).
    """
    reasons: list[str] = []
    max_age = EVIDENCE_MAX_AGE.get(consequence_class)
    for ref in refs:
        try:
            packet = register.get(ref)
        except Exception as exc:  # a register that cannot answer is not evidence
            reasons.append(f"evidence {ref!r} could not be resolved: {type(exc).__name__}")
            continue
        if packet is None:
            reasons.append(f"unknown evidence id {ref!r}; ambiguity fails closed")
            continue
        try:
            errors = sorted(_evidence_contract().iter_errors(packet), key=lambda e: str(list(e.path)))
            if errors:
                raise ValueError(f"evidence contract: {errors[0].message}")
            if packet["packet_id"] != ref:
                raise ValueError("packet_id does not match the reference")
            captured = _instant(packet["captured_at"])
            deadline = captured + max_age if max_age is not None else captured
            if packet.get("fresh_until") is not None:
                deadline = min(deadline, _instant(packet["fresh_until"]))
        except (ValueError, TypeError, KeyError) as exc:
            reasons.append(f"evidence {ref!r} is not a valid evidence packet: {exc}")
            continue
        if captured > now + EVIDENCE_CLOCK_SKEW:
            reasons.append(f"evidence {ref!r} is captured in the future ({packet['captured_at']}); "
                           "ambiguity fails closed")
        elif max_age is None:
            reasons.append(f"no evidence age declared for consequence class {consequence_class!r}")
        elif now >= deadline:
            reasons.append(f"evidence {ref!r} is stale: relied on until "
                           f"{deadline.isoformat().replace('+00:00', 'Z')}, now "
                           f"{now.isoformat().replace('+00:00', 'Z')}")
    return reasons


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
    evidence_confidence: float
    evidence_refs: list[str]
    estimated_cost_usd: float
    requested_capability: str
    expected_outcome: str
    context: dict = field(default_factory=dict)
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
             thresholds: dict | None = None,
             evidence: Mapping[str, dict] | None = None) -> PolicyDecision:
    """Evaluate a proposal. Pure function of (compiled doctrine, proposal,
    identity verdict, current grant, evidence register). Deny by default.

    thresholds: optional evidence-floor override per consequence class
    (defaults to EVIDENCE_THRESHOLDS). Evolution cycles may test candidate
    floors in simulation; production floors change only by ratified policy.

    evidence: optional register of evidence packets by packet_id. When given,
    every evidence ref must resolve to a fresh, contract-valid packet (#21);
    without it refs are opaque digests and only their presence is checked.
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
    if evidence is not None:
        stale = evidence_freshness_reasons(proposal.evidence_refs, evidence, proposal.consequence_class, now)
        if stale:
            reasons.extend(stale)
            missing.append("fresh_evidence")
    law.append("evidence.schema.json")

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
