"""AdvantageCase: the strongest lawful option, after hard gates (directive §13).

Order is the invariant. Every option first passes hard prohibitions (consequence vector)
and the evidence-backed legitimacy gates (law, consent, rights, authority). Only then are
the survivors compared, and the comparison is a Pareto frontier over criteria with
different units — never one multiplied "leverage score". A founder-owned, versioned
weight policy may rank the frontier; the ranking reports whether it survives a ±25%
perturbation of each weight. Without that policy the frontier is returned unranked and
the choice escalates.

The six outcomes the founder named are reported separately — evidence, institutional
leverage, accountability, deterrence, victim protection, minimal collateral harm — each
with what the case supplies and what is missing. Nothing here grants authority.
"""
from __future__ import annotations

from dataclasses import asdict

from .contracts import CognitionError, ConsequenceVector, number

MAXIMIZE = ("benefit_low", "benefit_high", "evidence_strength", "durability", "optionality")
MINIMIZE = ("residual_exposure", "resource_burden", "irreversibility")
_IRREVERSIBILITY = {"reversible": 0.0, "partially_reversible": 0.5, "irreversible": 1.0, "unknown": 1.0}
REQUIRED_KINDS = ("do_nothing", "smallest_intervention")
SECTIONS = {
    "evidence": ("evidence", "strongest_counterexample"),
    "institutional_leverage": ("accepting_actor", "process", "accepted_artifact", "decision_it_can_change"),
    "accountability": ("decision_owner", "appeal_path", "correction_path", "restitution"),
    "deterrence": ("lawful_mechanism",),
    "victim_protection": ("protection_review",),
    "minimal_collateral_harm": ("consequences",),
}


def _criteria(option):
    raw = option.get("criteria", {})
    low, high = raw.get("expected_benefit", [0, 0])
    low, high = number(low), number(high)
    if low > high:
        raise CognitionError(f"{option['id']}: expected benefit range is reversed")
    reversibility = raw.get("reversibility", "unknown")
    if reversibility not in _IRREVERSIBILITY:
        raise CognitionError(f"{option['id']}: invalid reversibility")
    return {"benefit_low": low, "benefit_high": high,
            "evidence_strength": number(raw.get("evidence_strength", 0), low=0, high=1),
            "durability": number(raw.get("durability", 0), low=0, high=1),
            "optionality": number(raw.get("optionality", 0), low=0, high=1),
            "residual_exposure": number(raw.get("residual_exposure", 1), low=0, high=1),
            "resource_burden": number(raw.get("resource_burden", 0), low=0),
            "irreversibility": _IRREVERSIBILITY[reversibility]}


def _dominates(a, b):
    ge = all(a[k] >= b[k] for k in MAXIMIZE) and all(a[k] <= b[k] for k in MINIMIZE)
    gt = any(a[k] > b[k] for k in MAXIMIZE) or any(a[k] < b[k] for k in MINIMIZE)
    return ge and gt


def _scores(frontier, weights):
    if not frontier:
        return {}
    spans = {k: (min(f["criteria"][k] for f in frontier), max(f["criteria"][k] for f in frontier))
             for k in MAXIMIZE + MINIMIZE}
    def norm(k, v):
        lo, hi = spans[k]
        x = 0.5 if hi == lo else (v - lo) / (hi - lo)
        return x if k in MAXIMIZE else 1 - x
    return {f["id"]: sum(weights.get(k, 0) * norm(k, f["criteria"][k]) for k in MAXIMIZE + MINIMIZE)
            for f in frontier}


def assess(data, geometry):
    from .gates import evaluate
    from .solvers import result
    options = data.get("options")
    if not isinstance(options, list) or not 2 <= len(options) <= 32:
        raise CognitionError("two to 32 options required")
    kinds = [o.get("kind", "proposal") for o in options]
    missing_kinds = [k for k in REQUIRED_KINDS if k not in kinds]
    if missing_kinds:
        raise CognitionError(f"an advantage case must include {missing_kinds} options")
    ids = [o.get("id") for o in options]
    if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        raise CognitionError("unique option ids required")
    gated, excluded = [], []
    for option in options:
        vector = ConsequenceVector(**option.get("consequences", {}))
        records = option.get("legitimacy", [])
        # Doing nothing takes no action, so the action gates do not apply unless a record says otherwise
        # (a duty to notify or protect can make inaction prohibited).
        gates = evaluate(records, consequential=option.get("kind") != "do_nothing")
        reasons = (["hard constraint in the consequence vector"] if vector.prohibited else []) + \
            [f"{g}: prohibited" for g in gates["prohibited"]] + [f"{g}: unresolved" for g in gates["unresolved"]]
        entry = {"id": option["id"], "kind": option.get("kind", "proposal"), "criteria": _criteria(option),
                 "consequences": asdict(vector), "legitimacy_verdict": gates["verdict"]}
        if reasons:
            excluded.append({**entry, "excluded_because": reasons})
        else:
            gated.append(entry)
    frontier = [g for g in gated if not any(_dominates(o["criteria"], g["criteria"]) for o in gated if o is not g)]
    dominated = [{"id": g["id"], "dominated_by": [o["id"] for o in gated if _dominates(o["criteria"], g["criteria"])]}
                 for g in gated if g not in frontier]
    policy = data.get("weights")
    ranking, status = None, "HUMAN_REVIEW_REQUIRED"
    if policy is not None:
        if not isinstance(policy, dict) or not policy.get("owner") or not policy.get("policy_ref") or not policy.get("version"):
            raise CognitionError("weights need a founder-owned, versioned policy reference")
        weights = {k: number(v, low=0, high=1) for k, v in policy.get("weights", {}).items()}
        if set(weights) - set(MAXIMIZE + MINIMIZE) or not weights:
            raise CognitionError("weights name known criteria")
        base = _scores(frontier, weights)
        top = max(sorted(base), key=base.get) if base else None
        unstable = []
        for k in weights:
            for factor in (0.75, 1.25):
                alt = _scores(frontier, {**weights, k: weights[k] * factor})
                if alt and max(sorted(alt), key=alt.get) != top:
                    unstable.append(f"{k} x{factor}")
        ranking = {"policy": {k: policy[k] for k in ("owner", "policy_ref", "version")}, "scores": base, "top": top,
                   "sensitivity": "stable under ±25% on every weight" if not unstable else
                   f"top option changes under {sorted(set(unstable))}"}
        status = "ANSWER" if top is not None and not unstable else "HUMAN_REVIEW_REQUIRED"
    case = data.get("case", {})
    sections = {}
    for name, fields in SECTIONS.items():
        supplied = {f: case.get(name, {}).get(f) for f in fields if case.get(name, {}).get(f)}
        sections[name] = {"supplied": supplied, "missing": [f for f in fields if f not in supplied]}
    sections["minimal_collateral_harm"]["frontier_exposure"] = {f["id"]: f["consequences"] for f in frontier}
    if not frontier:
        status = "HUMAN_REVIEW_REQUIRED"
    out = {"frontier": [f["id"] for f in frontier], "excluded": [{"id": e["id"], "why": e["excluded_because"]}
                                                                  for e in excluded],
           "dominated": dominated, "ranking": ranking, "sections": sections,
           "recommendation": ranking["top"] if status == "ANSWER" else None,
           "score_note": "no multiplicative leverage score: criteria keep their units; hard limits sit outside any ranking",
           "authority_created": False}
    proof = {"options": [{"id": o["id"], "kind": o.get("kind", "proposal")} for o in options],
             "gates": {e["id"]: e["legitimacy_verdict"] for e in gated + excluded},
             "frontier": out["frontier"], "weights": ranking["policy"] if ranking else None,
             "sensitivity": ranking["sensitivity"] if ranking else "no ranking without a founder-owned weight policy",
             "desired_outcome": data.get("desired_outcome"), "bounded_failure": data.get("bounded_failure")}
    return result(out, proof, status=status,
                  missing=() if status == "ANSWER" else
                  ("founder choice among the frontier, or a founder-owned weight policy that is stable under perturbation",))
