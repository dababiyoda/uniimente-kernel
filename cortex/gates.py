"""Hard gates before ranking (build prompt item 3).

Order is the invariant: every consequential option passes law, rights,
founder-authorized scope, consent, evidence sufficiency, harm, budget and
consequence boundary *before* any advantage score is read. A failed gate
excludes the option whatever its score. An unresolved gate yields an explicit
state and one of: bounded evidence acquisition, authorized adjudication, or
abstention.

Permission comes only from existing policy and authorization records: the
Kernel policy engine (``policy.engine.PolicyDecision``), founder mandates,
capability grants, consent records and qualified human opinions. Model
interpretations, proof artifacts, confidence, reputation and benchmark results
are *recorded* as rejected bases and never create permission.

This module reads records. It does not call the Consequence Gate, issue
grants, or evaluate policy on anyone's behalf.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from fnmatch import fnmatchcase
from typing import Any, Mapping

from memory.causal import VALIDATION_WEIGHT

from .contracts import (CONSEQUENCE_CLASSES, REVERSIBILITY, ConsequenceVector, CortexError,
                        consequence_rank, digest)

GATES = ("law", "rights", "founder_scope", "consent", "evidence_sufficiency", "harm",
         "budget", "consequence_boundary")
GATE_STATUS = ("PASS", "FAIL", "UNRESOLVED", "NOT_APPLICABLE")
RESOLUTIONS = ("proceed", "exclude", "bounded_evidence_acquisition", "authorized_adjudication", "abstain")

# kind -> origins that make the record permission-bearing
PERMISSION_BEARING = {
    "policy_decision": ("kernel_policy_engine",),
    "founder_mandate": ("founder_signed",),
    "capability_grant": ("kernel_grant_issuer",),
    "consent_record": ("consent_capture",),
    "legal_opinion": ("qualified_human",),
}
NEVER_PERMISSION = ("model_interpretation", "proof_artifact", "confidence", "reputation",
                    "benchmark_result")
RECORD_KINDS = tuple(PERMISSION_BEARING) + NEVER_PERMISSION

# Evidence floor per consequence class, in memory.causal VALIDATION_WEIGHT units
# (externally_verified 1.0, internally_observed 0.6, self_reported 0.3).
EVIDENCE_FLOOR = {"read_only": 0.0, "internal_write": 0.3, "external_contact": 0.6,
                  "financial": 1.0, "irreversible": 1.0}
# Uncertainty margin grows with consequence and irreversibility (item 3).
_BASE_MARGIN = {"read_only": 0.02, "internal_write": 0.05, "external_contact": 0.10,
                "financial": 0.20, "irreversible": 0.30}
_REVERSIBILITY_FACTOR = {"reversible": 1.0, "costly_to_reverse": 1.5, "irreversible": 2.0, "unknown": 2.0}


def uncertainty_margin(consequence_class: str, reversibility: str) -> float:
    return _BASE_MARGIN[consequence_class] * _REVERSIBILITY_FACTOR[reversibility]


@dataclass(frozen=True)
class AuthorityRecord:
    record_id: str
    kind: str
    origin: str
    body: Mapping[str, Any]

    def __post_init__(self):
        if self.kind not in RECORD_KINDS:
            raise CortexError(f"unknown authority record kind {self.kind!r}")

    @property
    def permission_bearing(self) -> bool:
        return self.origin in PERMISSION_BEARING.get(self.kind, ())

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AuthorityRecord":
        body = dict(value.get("body", {}))
        return cls(record_id=value.get("record_id") or digest(body), kind=value["kind"],
                   origin=value["origin"], body=body)

    def to_dict(self) -> dict:
        return {"record_id": self.record_id, "kind": self.kind, "origin": self.origin, "body": dict(self.body)}


def record_from_policy_decision(decision: Any, *, subject: str, action_class: str) -> AuthorityRecord:
    """Adapter: an existing ``policy.engine.PolicyDecision`` becomes a gate record.

    Duck-typed so the cortex imports nothing that can act. The record is only as
    good as the decision the Kernel policy engine actually produced.
    """
    verdict = getattr(decision.verdict, "value", decision.verdict)
    body = {"subject": subject, "action_class": action_class, "verdict": verdict,
            "reasons": list(decision.reasons), "law_applied": list(decision.law_applied),
            "missing": list(decision.missing), "rule_ids": list(decision.rule_ids)}
    return AuthorityRecord(digest(body), "policy_decision", "kernel_policy_engine", body)


@dataclass(frozen=True)
class Option:
    option_id: str
    action_class: str
    target: str
    consequence_class: str
    reversibility: str
    cost_usd: float | None
    requires_consent: bool
    consent_subject: str | None
    harm: ConsequenceVector
    evidence_statuses: tuple[str, ...]
    advantage: Mapping[str, float]

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Option":
        cc = value.get("consequence_class", "internal_write")
        if cc not in CONSEQUENCE_CLASSES:
            raise CortexError(f"option consequence_class {cc!r} unknown")
        rev = value.get("reversibility", "unknown")
        if rev not in REVERSIBILITY:
            raise CortexError(f"option reversibility {rev!r} unknown")
        cost = value.get("cost_usd")
        if cost is not None and (isinstance(cost, bool) or not isinstance(cost, (int, float)) or cost < 0):
            raise CortexError("option cost_usd must be a non-negative number or null")
        adv = value.get("advantage", {})
        if not isinstance(adv, Mapping) or any(
                isinstance(v, bool) or not isinstance(v, (int, float)) for v in adv.values()):
            raise CortexError("option advantage must map criteria to numbers")
        return cls(option_id=value["option_id"], action_class=value["action_class"],
                   target=value.get("target", "internal://unspecified"), consequence_class=cc,
                   reversibility=rev, cost_usd=cost, requires_consent=bool(value.get("requires_consent")),
                   consent_subject=value.get("consent_subject"),
                   harm=ConsequenceVector.from_partial(value.get("harm")),
                   evidence_statuses=tuple(value.get("evidence_statuses", ())),
                   advantage=dict(adv))


@dataclass(frozen=True)
class GateResult:
    status: str
    reason: str
    basis: tuple[str, ...] = ()
    resolution: str = "proceed"

    def to_dict(self) -> dict:
        return {"status": self.status, "reason": self.reason, "basis": list(self.basis),
                "resolution": self.resolution}


@dataclass(frozen=True)
class GateReport:
    option_id: str
    gates: Mapping[str, GateResult]
    rejected_bases: tuple[dict, ...] = ()

    @property
    def all_pass(self) -> bool:
        return all(g.status in ("PASS", "NOT_APPLICABLE") for g in self.gates.values())

    @property
    def resolution(self) -> str:
        statuses = [g.status for g in self.gates.values()]
        if "FAIL" in statuses:
            return "exclude"
        unresolved = [g.resolution for g in self.gates.values() if g.status == "UNRESOLVED"]
        for preferred in ("authorized_adjudication", "bounded_evidence_acquisition", "abstain"):
            if preferred in unresolved:
                return preferred
        return "proceed"

    def to_dict(self) -> dict:
        return {"option_id": self.option_id, "all_pass": self.all_pass, "resolution": self.resolution,
                "gates": {k: v.to_dict() for k, v in self.gates.items()},
                "rejected_bases": list(self.rejected_bases)}


def _instant(value: str) -> datetime:
    """Date-only means 00:00 UTC. Any other timestamp must carry a timezone."""
    text = str(value)
    if len(text) == 10:
        text += "T00:00:00+00:00"
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise CortexError(f"timestamp {value!r} has no timezone")
    return parsed


def _in_scope(scope: Mapping[str, Any], option: Option, as_of: str | None) -> tuple[bool, str]:
    caps = scope.get("action_classes", [])
    targets = scope.get("targets", [])
    ceiling = scope.get("max_consequence_class", "read_only")
    if not any(fnmatchcase(option.action_class, p) for p in caps):
        return False, f"{option.action_class} outside mandate action classes"
    if not any(fnmatchcase(option.target, p) for p in targets):
        return False, f"{option.target} outside mandate targets"
    if ceiling not in CONSEQUENCE_CLASSES or consequence_rank(option.consequence_class) > consequence_rank(ceiling):
        return False, f"{option.consequence_class} exceeds mandate ceiling {ceiling}"
    expires = scope.get("expires_at")
    if expires and as_of:
        if _instant(as_of) >= _instant(expires):
            return False, "mandate expired"
    return True, "within mandate"


def evaluate_gates(option: Option, records: list[AuthorityRecord], *,
                   remaining_budget_usd: float, as_of: str | None = None) -> GateReport:
    usable = [r for r in records if r.permission_bearing]
    rejected = tuple({"record_id": r.record_id, "kind": r.kind, "origin": r.origin,
                      "why": "not a permission-bearing record kind/origin"}
                     for r in records if not r.permission_bearing)
    gates: dict[str, GateResult] = {}
    cc_rank = consequence_rank(option.consequence_class)

    # law — existing Kernel policy decision about this option
    decisions = [r for r in usable if r.kind == "policy_decision" and r.body.get("subject") == option.option_id]
    if not decisions:
        gates["law"] = GateResult("UNRESOLVED", "no Kernel policy decision for this option",
                                  resolution="authorized_adjudication")
    else:
        verdicts = {r.body.get("verdict") for r in decisions}
        ids = tuple(r.record_id for r in decisions)
        if "deny" in verdicts:
            gates["law"] = GateResult("FAIL", "policy engine denied", ids)
        elif "require_human" in verdicts:
            gates["law"] = GateResult("UNRESOLVED", "policy engine requires a human", ids,
                                      "authorized_adjudication")
        elif verdicts == {"allow"}:
            gates["law"] = GateResult("PASS", "policy engine allowed", ids)
        else:
            gates["law"] = GateResult("UNRESOLVED", f"unrecognized verdicts {sorted(map(str, verdicts))}",
                                      ids, "authorized_adjudication")

    # rights — hard dimension, never traded
    rights = option.harm.levels["rights"]
    if rights in ("high", "critical"):
        gates["rights"] = GateResult("FAIL", f"rights harm {rights}")
    elif rights == "unknown" and cc_rank >= consequence_rank("external_contact"):
        gates["rights"] = GateResult("UNRESOLVED", "rights impact unmeasured for a consequential option",
                                     resolution="bounded_evidence_acquisition")
    else:
        gates["rights"] = GateResult("PASS", f"rights harm {rights}")

    # founder-authorized scope
    mandates = [r for r in usable if r.kind in ("founder_mandate", "capability_grant")]
    if not mandates:
        gates["founder_scope"] = GateResult("UNRESOLVED", "no founder mandate or grant covers this option",
                                            resolution="authorized_adjudication")
    else:
        covering, why = [], []
        for r in mandates:
            ok, reason = _in_scope(r.body.get("scope", {}), option, as_of)
            (covering if ok else why).append(r.record_id if ok else reason)
        gates["founder_scope"] = (GateResult("PASS", "within founder-authorized scope", tuple(covering))
                                  if covering else GateResult("FAIL", "; ".join(why)))

    # consent
    if not option.requires_consent:
        gates["consent"] = GateResult("NOT_APPLICABLE", "consent not required")
    else:
        consents = [r for r in usable if r.kind == "consent_record"
                    and r.body.get("subject") == option.consent_subject
                    and any(fnmatchcase(option.action_class, p) for p in r.body.get("purposes", []))]
        if any(r.body.get("revoked") for r in consents):
            gates["consent"] = GateResult("FAIL", "consent revoked", tuple(r.record_id for r in consents))
        elif consents:
            gates["consent"] = GateResult("PASS", "consent recorded", tuple(r.record_id for r in consents))
        else:
            gates["consent"] = GateResult("UNRESOLVED", "consent required and not recorded",
                                          resolution="authorized_adjudication")

    # evidence sufficiency, proportional to consequence and irreversibility
    floor = EVIDENCE_FLOOR[option.consequence_class]
    weights = sorted((VALIDATION_WEIGHT.get(s, 0.0) for s in option.evidence_statuses), reverse=True)
    needed_items = 2 if option.reversibility in ("irreversible", "unknown") and cc_rank >= 2 else 1
    strong = [w for w in weights if w >= floor]
    if floor == 0.0:
        gates["evidence_sufficiency"] = GateResult("PASS", "read-only option")
    elif len(strong) >= needed_items:
        gates["evidence_sufficiency"] = GateResult("PASS", f"{len(strong)} item(s) at or above {floor}")
    else:
        gates["evidence_sufficiency"] = GateResult(
            "UNRESOLVED", f"needs {needed_items} item(s) at weight >= {floor}; have {len(strong)}",
            resolution="bounded_evidence_acquisition")

    # harm vector
    hard = option.harm.hard_violations()
    unknown_hard = [d for d in option.harm.unknown() if d in ("physical", "rights", "discrimination",
                                                               "third_party", "irreversible_disclosure")]
    if hard:
        gates["harm"] = GateResult("FAIL", f"unacceptable harm: {list(hard)}")
    elif unknown_hard and cc_rank >= consequence_rank("external_contact"):
        gates["harm"] = GateResult("UNRESOLVED", f"unmeasured hard harm dimensions {unknown_hard}",
                                   resolution="bounded_evidence_acquisition")
    else:
        gates["harm"] = GateResult("PASS", "no hard harm violation")

    # budget
    if option.cost_usd is None:
        gates["budget"] = GateResult("UNRESOLVED", "cost unknown", resolution="bounded_evidence_acquisition")
    elif option.cost_usd > remaining_budget_usd + 1e-9:
        gates["budget"] = GateResult("FAIL", f"cost {option.cost_usd} exceeds remaining {remaining_budget_usd}")
    else:
        gates["budget"] = GateResult("PASS", "within budget")

    # consequence boundary: financial/irreversible are never delegated to cognition
    if option.consequence_class in ("financial", "irreversible"):
        gates["consequence_boundary"] = GateResult(
            "UNRESOLVED", f"{option.consequence_class} requires its own founder decision via the Consequence Gate",
            resolution="authorized_adjudication")
    else:
        gates["consequence_boundary"] = GateResult("PASS", "within cortex recommendation boundary")

    return GateReport(option.option_id, gates, rejected)


def rank_after_gates(options: list[Option], reports: Mapping[str, GateReport], *,
                     founder_weights: Mapping[str, float] | None = None) -> dict:
    """Rank only gate-passing options. Advantage is never read for excluded ones.

    Without founder-policy weights, incomparable options stay an explicit
    tradeoff set (Pareto front); nothing is collapsed into a scalar. With
    weights, a winner must beat the runner-up by the uncertainty margin.
    """
    eligible = [o for o in options if reports[o.option_id].all_pass]
    excluded = {o.option_id: reports[o.option_id].resolution for o in options
                if not reports[o.option_id].all_pass}
    if not eligible:
        return {"status": "none_eligible", "chosen": None, "eligible": [], "excluded": excluded,
                "front": [], "tradeoffs": [], "margin": None}
    worst = max(eligible, key=lambda o: (consequence_rank(o.consequence_class),
                                         list(_REVERSIBILITY_FACTOR).index(o.reversibility)))
    margin = uncertainty_margin(worst.consequence_class, worst.reversibility)
    criteria = sorted(set().union(*[set(o.advantage) for o in eligible]))

    def dominates(a: Option, b: Option) -> bool:
        if any(c not in a.advantage or c not in b.advantage for c in criteria):
            return False
        return all(a.advantage[c] >= b.advantage[c] for c in criteria) and any(
            a.advantage[c] > b.advantage[c] for c in criteria)

    front = [o for o in eligible if not any(dominates(p, o) for p in eligible if p is not o)]
    tradeoffs = [{"option_id": o.option_id, "advantage": dict(o.advantage)} for o in front]
    result = {"eligible": [o.option_id for o in eligible], "excluded": excluded,
              "front": [o.option_id for o in front], "tradeoffs": tradeoffs, "margin": margin}
    if len(front) == 1:
        return {**result, "status": "chosen", "chosen": front[0].option_id}
    if not founder_weights:
        return {**result, "status": "incomparable", "chosen": None}
    scored = sorted(((sum(founder_weights.get(c, 0.0) * o.advantage.get(c, 0.0) for c in criteria), o.option_id)
                     for o in front), reverse=True)
    if scored[0][0] - scored[1][0] <= margin:
        return {**result, "status": "within_margin", "chosen": None,
                "weighted": [{"option_id": i, "score": s} for s, i in scored]}
    return {**result, "status": "chosen", "chosen": scored[0][1],
            "weighted": [{"option_id": i, "score": s} for s, i in scored]}
