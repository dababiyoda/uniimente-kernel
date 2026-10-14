"""Independent adversarial verifier (build prompt item 7).

Rule-based and model-free, so it shares no model with the semantic route and
cannot be talked into agreement. It inspects evidence and artifacts and attacks
assumptions, omitted constraints, contradictions and boundary violations. It also
records correlated dependencies: agreement between routes that share a model,
solver or source is not independent verification.

Findings can only lower a disposition. A critical finding blocks ``recommend``.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

from ..contracts import HUMAN_AUTHORITY_CLASSES, consequence_rank

VERIFIER_ID = "cortex.verifier.adversarial@0.1.0"
VERIFIER_DEPENDENCIES = ("python-stdlib", "rules:cortex.organs.adversarial")
SEVERITIES = ("critical", "major", "minor")
_PROHIBITED_DETERRENCE = ("threat", "retaliation", "intimidation", "extortion", "deception", "doxxing",
                          "unconsented_surveillance", "vigilantism", "harassment", "coercion")
_NUMBER = re.compile(r"(?<![A-Za-z_])\d+(?:\.\d+)?")
_INJECTION = re.compile(r"(ignore (all|previous|prior) instructions|system:|mark (this|it) (as )?correct|"
                        r"you must answer|output approved)", re.I)


def _recheck_formal_answers(payload, results, add) -> None:
    """Directive 7C/7E: check every returned assignment against the SOURCE constraints.

    Reads the model from the problem payload, never from the route's proof, so a
    forged or corrupted proof artifact cannot vouch for itself. Shares only the
    parser with the engines (disclosed in ``formal_eval``)."""
    model = payload.get("formal_model")
    candidates = [r for r in results if (r.proof or {}).get("proof_class") in ("formal", "optimization")
                  and r.answer is not None]
    if not candidates or not isinstance(model, Mapping):
        return
    from .formal import FormalModelError, Spec
    from . import formal_eval
    try:
        spec = Spec(model)
    except (FormalModelError, KeyError, TypeError, ValueError) as exc:
        add("critical", "source_model_unparseable", f"answer returned for a model the verifier cannot parse: {exc}")
        return
    for r in candidates:
        answer, proof = r.answer, r.proof
        assignment = answer.get("model") if answer.get("feasible") else answer.get("counterexample")
        if assignment is not None:
            check = formal_eval.check_assignment(spec, assignment)
            if not check["holds"]:
                add("critical", "assignment_violates_source_constraints",
                    f"{r.organ_id}: {check['violated_constraints'] or check['bound_violations'] or check['error']}",
                    r.organ_id)
            elif answer.get("counterexample") is not None and spec.query.get("kind") == "entailment":
                prop = formal_eval.evaluate(spec.query["property"], assignment, spec.variables)
                if prop is not False:
                    add("critical", "counterexample_does_not_violate_property",
                        f"{r.organ_id}: reported counterexample satisfies the property", r.organ_id)
        if answer.get("optimal") is not None and assignment is not None and spec.query.get("kind") == "optimize":
            value = formal_eval.objective_value(spec, assignment)
            if value != answer.get("objective"):
                add("critical", "objective_mismatch",
                    f"{r.organ_id}: reported objective {answer.get('objective')} but the assignment yields {value}",
                    r.organ_id)
        if answer.get("optimal") is True:
            solver = proof.get("solver") or {}
            proven = (solver.get("certificate_check") == "UNSAT" or proof.get("native_status") == "OPTIMAL"
                      or solver.get("status") == "OPTIMAL")
            if not proven:
                add("critical", "optimality_claim_without_proof",
                    f"{r.organ_id} claims an optimum but neither a certificate nor an OPTIMAL status is recorded",
                    r.organ_id)
            cert = proof.get("certificate") or {}
            if cert.get("status") == "REFUTED":
                add("critical", "optimality_refuted_by_second_engine",
                    f"{cert.get('engine')} found a strictly better assignment", r.organ_id)
        if (proof.get("engine_disagreement") or {}).get("answer") is not None:
            add("critical", "engines_disagree", f"{r.organ_id} vs {proof['engine_disagreement']['engine']}: "
                f"{proof['engine_disagreement']['answer']}", r.organ_id)


def verify(problem, geometry, results: list, *, proposed_disposition: str,
           gate_reports: Mapping[str, Any] | None = None, ranking: Mapping[str, Any] | None = None,
           protection: Any = None) -> dict:
    findings: list[dict] = []

    def add(severity, kind, detail, target=None):
        findings.append({"severity": severity, "kind": kind, "detail": detail, "target": target})

    payload = problem.payload
    _recheck_formal_answers(payload, results, add)
    # injected instructions inside supplied data
    for s in payload.get("sources", []):
        if _INJECTION.search(s.get("text", "")):
            add("major", "prompt_injection_in_source", f"source {s.get('id')} contains instruction-like text",
                s.get("id"))
    for r in results:
        proof = r.proof
        pc = proof.get("proof_class")
        # assumptions without evidence
        if pc in ("formal", "optimization"):
            for pid in proof.get("unverified_premises", []):
                add("major", "unverified_premise", f"formal premise {pid} is unverified; result is WORLD_UNVERIFIED",
                    pid)
            for w in (proof.get("discrepancy_check") or {}).get("warnings", []):
                add("minor", "possible_omitted_constraint", w)
            for d in (proof.get("discrepancy_check") or {}).get("discrepancies", []):
                add("critical", "omitted_or_unfaithful_constraint", d)
            for c in proof.get("counterexample_search", []):
                if str(c.get("result", "")).startswith("implied"):
                    add("minor", "redundant_constraint", f"{c['constraint']} is implied by the others")
            requirement = proof.get("original_requirement") or ""
            encoded = str(proof.get("structured_model", {}).get("constraints", "")) + \
                str(proof.get("structured_model", {}).get("query", ""))
            bounds = str(proof.get("structured_model", {}).get("bounds", ""))
            missing = sorted(set(_NUMBER.findall(requirement)) - set(_NUMBER.findall(encoded + bounds)))
            if missing and r.state in ("OK", "WORLD_UNVERIFIED"):
                add("major", "requirement_number_not_encoded",
                    f"numbers {missing} in the original requirement appear nowhere in the model")
        elif pc == "estimation":
            ref = proof.get("reference_class") or {}
            if ref.get("comparable") and ref.get("outside"):
                add("major", "outside_view_contradiction", "estimate does not overlap its reference class")
            if not ref.get("available"):
                add("minor", "no_outside_view", "no reference-class anchor available")
            for a in r.assumptions:
                if a.startswith("assumed independent") and proof.get("dependencies") == []:
                    add("minor", "independence_assumed", a)
        elif pc in ("evidence_assessment", "causal_estimate"):
            a = proof.get("evidence_assessment", proof) if pc == "causal_estimate" else proof
            for c in a.get("contradictions", []):
                add("major", "contradictory_sources", f"supports {c['supports']} vs contradicts {c['contradicts']}")
            for s in a.get("stale", []):
                add("minor", "stale_evidence", f"{s['id']} is {s['age_days']} days old (limit {s['max_age_days']})",
                    s["id"])
            for e in a.get("excluded", []):
                add("minor", "non_settling_evidence", f"{e['id']}: {e['why']}", e["id"])
            if pc == "causal_estimate":
                failed = [x["name"] for x in proof.get("refutations", []) if not x.get("passed")]
                if failed:
                    add("critical", "refutation_failed", f"refutation checks failed: {failed}")
                add("minor", "identification_assumed",
                    "estimate rests on stated identification assumptions; refutations do not prove them")
        elif pc == "deterrence_assessment":
            for refused in proof.get("refused", []):
                add("major", "coercive_or_harmful_intervention_refused", f"{refused['id']} ({refused['kind']}): "
                    f"{refused['why']}", refused["id"])
            ranked = proof.get("interventions", [])
            prohibited = [i["id"] for i in ranked if i.get("kind") in _PROHIBITED_DETERRENCE]
            if prohibited:
                add("critical", "coercive_intervention_ranked", f"coercive interventions ranked: {prohibited}")
            if ranked and ranked[0].get("severity_only"):
                add("major", "severity_only_deterrence",
                    "best intervention moves only severity; evidence supports certainty of apprehension far more "
                    "consistently (Nagin 2013)", ranked[0]["id"])
            add("minor", "risk_neutral_assumption", "deterrence model assumes a risk-neutral actor")
        elif pc == "semantic_sourced":
            if proof.get("rejected_claims"):
                add("major", "unsupported_claims_dropped",
                    f"{len(proof['rejected_claims'])} model claim(s) failed the source check")
            for c in proof.get("contradictions", []):
                add("major", "contradiction_reported", str(c))

    # boundary violations
    if proposed_disposition == "recommend":
        if consequence_rank(geometry.consequence_class) >= consequence_rank("financial"):
            add("critical", "consequence_boundary",
                f"{geometry.consequence_class} decisions are handed off, never recommended by cognition")
        if geometry.epistemic_class in HUMAN_AUTHORITY_CLASSES:
            add("critical", "authority_boundary",
                f"{geometry.epistemic_class} questions belong to legitimate human or institutional authority")
    if protection is not None and getattr(protection, "relevant", False) and proposed_disposition == "recommend" \
            and (set(protection.required_actions) & {"immediate_protection", "safe_contact", "escalation"}
                 or getattr(protection, "gaps", ())):
        add("critical", "victim_protection_boundary",
            "protective actions are human-led; cognition may not recommend in their place")
    if proposed_disposition == "recommend" and any(
            (r.answer or {}).get("external_action_required") for r in results
            if (r.proof or {}).get("proof_class") == "deterrence_assessment"):
        add("critical", "deterrence_authority_boundary",
            "deterrence that reaches another party belongs to legitimate authority, not cognition")
    if ranking and ranking.get("chosen") and gate_reports:
        rep = gate_reports.get(ranking["chosen"])
        if rep is not None and not rep.all_pass:
            add("critical", "gate_violation", f"chosen option {ranking['chosen']} did not pass all gates")

    # correlated dependencies
    deps: dict[str, list[str]] = {}
    for r in results:
        for d in r.dependencies:
            deps.setdefault(d, []).append(r.organ_id)
    shared = {d: ids for d, ids in deps.items() if len(set(ids)) > 1 and d != "python-stdlib"}
    verifier_shared = sorted(set(VERIFIER_DEPENDENCIES) & set(deps) - {"python-stdlib"})
    independence = {
        "verifier": VERIFIER_ID,
        "verifier_dependencies": list(VERIFIER_DEPENDENCIES),
        "shared_with_routes": verifier_shared,
        "independent_of_routes": not verifier_shared,
        "shared_between_routes": shared,
        "note": "agreement between routes that share a model, solver or source is not independent verification",
    }
    worst = min((SEVERITIES.index(f["severity"]) for f in findings), default=len(SEVERITIES))
    return {"proof_class": "verifier_findings", "verifier": VERIFIER_ID, "findings": findings,
            "blocking": worst == 0, "independence": independence}
