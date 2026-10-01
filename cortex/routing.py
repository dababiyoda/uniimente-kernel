"""Consequence-aware routing and verification (build prompt item 7).

    problem -> geometry -> cognitive eligibility -> budget -> route or bounded
    composition -> typed artifact -> adversarial verification ->
    abstain / recommend / bounded_test / handoff -> receipt

The policy is a fixed table, readable in this file. It does not learn in v0.1;
``cortex.memory`` may later *reorder* eligible routes from settled outcomes but
cannot add a route, enable a family or change a ceiling.

High consequence never selects Formal by itself: Formal is chosen only when a
structured model exists, and a formal answer still carries separate empirical
and authority dimensions in the receipt.
"""
from __future__ import annotations

import time
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from .contracts import (CLAIM_TYPE_TO_EPISTEMIC, CORTEX_VERSION, EPISTEMIC_CLASSES,
                        HUMAN_AUTHORITY_CLASSES, ConsequenceVector, CortexError, Expenditure,
                        OrganResult, Problem, ProblemGeometry, ResourceLimits, VictimProtection,
                        consequence_rank, digest)
from .gates import AuthorityRecord, Option, evaluate_gates, rank_after_gates
from .genome import IntelligenceRegistry, seed_registry
from .organs import adversarial
from .organs.estimation import EstimationOrgan
from .organs.evidence_causal import EvidenceCausalOrgan
from .organs.formal import FormalOrgan
from .organs.semantic import SemanticOrgan

POLICY_VERSION = "cortex-route-policy/0.1"
FORMAL = "cortex.formal.z3@0.1.1"
FERMI = "cortex.estimation.fermi@0.1.0"
EVIDENCE = "cortex.evidence_causal@0.1.0"
SEMANTIC = "cortex.semantic@0.1.0"

# The deterministic route policy lives in _route_parts: formal_model -> Formal,
# estimation_model -> Fermi, claim -> Evidence/Causal, sources -> Semantic.
MAX_COMPOSITION = 2

# State -> disposition, before verifier findings and gates can only lower it.
STATE_DISPOSITION = {
    "OK": "recommend",
    "WORLD_UNVERIFIED": "bounded_test",
    "CONTESTED": "handoff",
    "NOT_IDENTIFIED": "bounded_test",
    "INSUFFICIENT_EVIDENCE": "abstain",
    "FORMALIZATION_INCOMPLETE": "abstain",
    "DEPENDENCY_UNAVAILABLE": "abstain",
    "TIMEOUT": "abstain",
    "INCONCLUSIVE": "abstain",
    "BUDGET_EXHAUSTED": "abstain",
    "MALFORMED_INPUT": "abstain",
    "DIMENSION_MISMATCH": "abstain",
    "UNSUPPORTED_GEOMETRY": "abstain",
    "NO_ELIGIBLE_METHOD": "abstain",
    "GATE_FAILED": "abstain",
    "GATE_UNRESOLVED": "handoff",
    "REQUIRES_HUMAN_AUTHORITY": "handoff",
}
_ORDER = ("recommend", "bounded_test", "handoff", "abstain")
# Protective actions that are human-led by nature (build prompt item 8).
HUMAN_LED_PROTECTION = ("immediate_protection", "safe_contact", "escalation")


def _route_parts(payload: Mapping[str, Any]) -> list[tuple[str, str]]:
    """(route key, epistemic class of the payload part it serves), in policy order."""
    parts = []
    fm = payload.get("formal_model")
    if isinstance(fm, Mapping):
        kind = (fm.get("query") or {}).get("kind", "feasibility")
        parts.append((FORMAL, "deductive_logical" if kind == "entailment" else "constraint_feasibility"))
    if isinstance(payload.get("estimation_model"), Mapping):
        parts.append((FERMI, "estimate"))
    claim = payload.get("claim")
    if isinstance(claim, Mapping) and claim.get("type") in CLAIM_TYPE_TO_EPISTEMIC:
        parts.append((EVIDENCE, CLAIM_TYPE_TO_EPISTEMIC[claim["type"]]))
    if payload.get("sources"):
        parts.append((SEMANTIC, "semantic"))
    return parts


def _structural_classes(payload: Mapping[str, Any]) -> list[str]:
    out = []
    fm = payload.get("formal_model")
    if isinstance(fm, Mapping):
        kind = (fm.get("query") or {}).get("kind", "feasibility")
        out.append("deductive_logical" if kind == "entailment" else "constraint_feasibility")
    if isinstance(payload.get("estimation_model"), Mapping):
        out.append("estimate")
    claim = payload.get("claim")
    if isinstance(claim, Mapping) and claim.get("type") in CLAIM_TYPE_TO_EPISTEMIC:
        out.append(CLAIM_TYPE_TO_EPISTEMIC[claim["type"]])
    if payload.get("options") and not out:
        out.append("strategic")
    if payload.get("sources") and not out:
        out.append("semantic")
    return out


def derive_geometry(problem: Problem, *, proposer: Callable[[Problem], Mapping] | None = None) -> ProblemGeometry:
    """Deterministic geometry from the structured payload; proposals are validated, not trusted."""
    p = problem.payload
    declared = dict(p.get("declared") or {})
    prov: dict[str, dict] = {}
    unresolved: list[str] = []
    rejected: list[dict] = []

    structural = _structural_classes(p)
    epistemic = structural[0] if structural else None
    if epistemic:
        prov["epistemic_class"] = {"source": "payload_structure", "confidence": 1.0}
    declared_class = declared.get("epistemic_class")
    if declared_class is not None:
        if declared_class not in EPISTEMIC_CLASSES:
            raise CortexError(f"declared epistemic class {declared_class!r} unknown")
        if declared_class in HUMAN_AUTHORITY_CLASSES or epistemic is None:
            epistemic = declared_class
            prov["epistemic_class"] = {"source": "requester_declared", "confidence": None}
        elif declared_class != epistemic:
            rejected.append({"field": "epistemic_class", "value": declared_class, "source": "requester_declared",
                             "why": f"structure indicates {epistemic}"})
    if proposer is not None:
        for fname, prop in (proposer(problem) or {}).items():
            value, conf = prop.get("value"), prop.get("confidence")
            if fname == "epistemic_class" and epistemic is None and value in structural:
                epistemic = value
                prov[fname] = {"source": "semantic_proposal_validated", "confidence": conf}
            else:
                rejected.append({"field": fname, "value": value, "source": "semantic_proposal",
                                 "confidence": conf, "why": "not supported by the structured payload"})
    if epistemic is None:
        unresolved.append("epistemic_class")
        prov["epistemic_class"] = {"source": "default_unknown", "confidence": None}

    def pick(name, default, allowed_default_source="default_unknown"):
        if name in declared:
            prov[name] = {"source": "requester_declared", "confidence": None}
            return declared[name]
        prov[name] = {"source": allowed_default_source, "confidence": None}
        if allowed_default_source == "default_unknown":
            unresolved.append(name)
        return default

    consequence = pick("consequence_class", "internal_write")
    reversibility = pick("reversibility", "unknown")
    harm = ConsequenceVector.from_partial(declared.get("harm"))
    if "harm" not in declared:
        unresolved.append("consequence_vector")
    claim = p.get("claim") if isinstance(p.get("claim"), Mapping) else None
    spec = p.get("causal_spec") if isinstance(p.get("causal_spec"), Mapping) else None
    if spec:
        origin = (spec.get("identification_basis") or {}).get("origin")
        causal = {"randomized_experiment": "declared_experiment", "model_generated": "model_generated"}.get(
            origin, "declared_adjustment" if origin else "unknown")
    elif claim and claim.get("type") == "intervention":
        causal = "unidentified"
    else:
        causal = "none"
    evidence = p.get("evidence") or []
    statuses = {e.get("validation_status") for e in evidence}
    quality = ("high" if "externally_verified" in statuses else "medium" if "internally_observed" in statuses
               else "low" if evidence or p.get("sources") else "none")
    exactness = {"constraint_feasibility": "exact_required", "deductive_logical": "exact_required",
                 "arithmetic": "exact_required", "estimate": "approximate_ok"}.get(epistemic, "unknown")
    uncertainty = {"constraint_feasibility": "low", "deductive_logical": "low", "estimate": "high",
                   "causal": "high", "prediction": "high"}.get(epistemic, "unknown")
    objective = {"constraint_feasibility": "decide_feasibility", "deductive_logical": "decide_entailment",
                 "estimate": "estimate_quantity", "causal": "estimate_effect", "prediction": "assess_claim",
                 "semantic": "assess_claim" if claim else "synthesize", "strategic": "choose_option",
                 "normative_value": "adjudicate", "legal": "adjudicate",
                 "institutional_acceptance": "adjudicate"}.get(epistemic, "unknown")
    constraints = [c.get("id") for c in (p.get("formal_model") or {}).get("constraints", []) if c.get("id")]
    constraints += [f"option:{o.get('option_id')}" for o in p.get("options") or []]
    return ProblemGeometry(
        problem_id=problem.problem_id, epistemic_class=epistemic,
        claim_type=claim.get("type") if claim and claim.get("type") in CLAIM_TYPE_TO_EPISTEMIC else None,
        objective=objective,
        ambiguity=declared.get("ambiguity", "low" if len(structural) == 1 else "high"),
        exactness=exactness, uncertainty=uncertainty, causal_structure=causal,
        constraints=tuple(constraints), temporal_character=declared.get("temporal_character", "static"),
        evidence_quality=quality, resource_limits=ResourceLimits.from_dict(p.get("resources")),
        consequence_vector=harm, consequence_class=consequence, reversibility=reversibility,
        unresolved_fields=tuple(dict.fromkeys(unresolved)), provenance=prov, rejected_proposals=tuple(rejected))


class Cortex:
    """The seed cortex. Holds a registry and organ executors; owns no authority."""

    def __init__(self, registry: IntelligenceRegistry | None = None, *, organs: Mapping[str, Any] | None = None,
                 clock: Callable[[], str] | None = None, memory=None):
        self.registry = registry or seed_registry()
        self.organs = dict(organs or {FORMAL: FormalOrgan(), FERMI: EstimationOrgan(),
                                      EVIDENCE: EvidenceCausalOrgan(), SEMANTIC: SemanticOrgan()})
        self.clock = clock or (lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        self.memory = memory

    # ------------------------------------------------------------------ pipeline
    def run(self, problem: Problem | Mapping[str, Any], *, records: list | None = None,
            proposer: Callable[[Problem], Mapping] | None = None) -> dict:
        started = time.perf_counter()
        if not isinstance(problem, Problem):
            try:
                problem = Problem.from_dict(problem)
            except (CortexError, KeyError, TypeError) as exc:
                return self._malformed(problem, str(exc), started)
        try:
            geometry = derive_geometry(problem, proposer=proposer)
            protection = VictimProtection.from_dict(problem.payload.get("victim_protection"))
        except CortexError as exc:
            return self._malformed(problem.to_dict(), str(exc), started)

        eligibility = self.registry.eligibility(geometry)
        parts = _route_parts(problem.payload)
        if geometry.epistemic_class in HUMAN_AUTHORITY_CLASSES:
            parts = [(k, c) for k, c in parts if k == SEMANTIC]  # may assist with sources, never decide
        # Each route is checked against the geometry of the payload part it serves.
        part_eligibility = {}
        for key, part_class in parts:
            rows = {e.key: e for e in self.registry.eligibility(replace(geometry, epistemic_class=part_class))}
            if key in rows:
                part_eligibility[key] = rows[key]
        selected = [k for k, _ in parts if k in part_eligibility and part_eligibility[k].eligible][:MAX_COMPOSITION]
        by_key = {e.key: e for e in eligibility}
        by_key.update(part_eligibility)
        eligibility = [by_key[k] for k in sorted(by_key)]
        if self.memory is not None and len(selected) > 1:
            selected = self.memory.reorder(selected, geometry)
        alternatives = [{"route": e.key, "why_not": list(e.reasons) or ["not required by this payload"]}
                        for e in eligibility if e.key not in selected]

        # budget: refuse before spending, never after
        limits = geometry.resource_limits
        profiles = self.registry.profiles()
        planned_cost = sum(profiles[k].cost_usd_per_call for k in selected)
        planned_model_calls = sum(1 for k in selected if k == SEMANTIC)
        budget_problem = None
        if planned_cost > limits.max_cost_usd:
            budget_problem = f"planned cost {planned_cost} exceeds {limits.max_cost_usd}"
        elif planned_model_calls > limits.max_model_calls:
            budget_problem = f"route needs {planned_model_calls} model call(s); budget allows {limits.max_model_calls}"
        elif FORMAL in selected and limits.max_solver_calls < 1:
            budget_problem = "route needs the solver; solver-call budget is zero"

        results: list[OrganResult] = []
        if budget_problem is None:
            for key in selected:
                results.append(self.organs[key].run(problem, geometry, limits))
        spent = Expenditure()
        for r in results:
            spent = spent.plus(r.expenditure)

        # gates before ranking, on consequential options
        gate_reports, ranking = {}, None
        options = []
        if problem.payload.get("options"):
            try:
                recs = [r if isinstance(r, AuthorityRecord) else AuthorityRecord.from_dict(r) for r in (records or [])]
                options = [Option.from_dict(o) for o in problem.payload["options"]]
            except (CortexError, KeyError) as exc:
                return self._malformed(problem.to_dict(), f"option rejected: {exc}", started, geometry)
            remaining = limits.max_cost_usd - spent.usd
            try:
                gate_reports = {o.option_id: evaluate_gates(o, recs, remaining_budget_usd=remaining,
                                                            as_of=problem.payload.get("as_of"))
                                for o in options}
            except (CortexError, ValueError, TypeError) as exc:
                return self._malformed(problem.to_dict(), f"authority record rejected: {exc}", started, geometry)
            weights = next((r.body.get("weights") for r in recs if r.kind == "founder_mandate"
                            and r.permission_bearing and r.body.get("weights")), None)
            ranking = rank_after_gates(options, gate_reports, founder_weights=weights)

        state, disposition, reason, next_step = self._dispose(
            geometry, selected, eligibility, results, budget_problem, ranking, gate_reports, options)
        if protection.relevant and set(protection.required_actions) & set(HUMAN_LED_PROTECTION):
            human_led = [a for a in protection.required_actions if a in HUMAN_LED_PROTECTION]
            if disposition != "handoff":
                disposition = "handoff"
                reason = f"victim protection requires human-led action {human_led}; {reason}"
            next_step = (f"human-led protective response ({', '.join(protection.required_actions)}); "
                         f"evidence access {protection.evidence_access}")
        verifier = adversarial.verify(problem, geometry, results, proposed_disposition=disposition,
                                      gate_reports=gate_reports, ranking=ranking, protection=protection)
        if verifier["blocking"] and disposition == "recommend":
            kinds = {f["kind"] for f in verifier["findings"] if f["severity"] == "critical"}
            disposition = "handoff" if kinds & {"authority_boundary", "consequence_boundary"} else "abstain"
            reason = f"critical verifier finding(s): {sorted(kinds)}"
            next_step = "resolve the findings before relying on this result"
        spent = spent.plus(Expenditure(seconds=time.perf_counter() - started - spent.seconds))
        return self._receipt(problem, geometry, eligibility, selected, alternatives, results, verifier,
                             gate_reports, ranking, state, disposition, reason, next_step, spent, protection)

    # ------------------------------------------------------------------ disposition
    def _dispose(self, geometry, selected, eligibility, results, budget_problem, ranking, gate_reports, options):
        if geometry.epistemic_class in HUMAN_AUTHORITY_CLASSES:
            return ("REQUIRES_HUMAN_AUTHORITY", "handoff",
                    f"{geometry.epistemic_class} questions belong to legitimate human or institutional authority",
                    "route to the authorized human decision-maker with the assembled evidence")
        if budget_problem:
            return "BUDGET_EXHAUSTED", "abstain", budget_problem, "raise the budget or narrow the question"
        if geometry.epistemic_class is None:
            return ("UNSUPPORTED_GEOMETRY", "abstain", "no structured facts establish what kind of claim this is",
                    "supply structured facts or declare the question type")
        if not selected and not options:
            enabled = [e for e in eligibility if not any("disabled" in r for r in e.reasons)]
            state = "NO_ELIGIBLE_METHOD" if enabled else "UNSUPPORTED_GEOMETRY"
            return state, "abstain", f"no enabled route supports {geometry.epistemic_class}", \
                "register and validate a capability for this geometry"
        states = [r.state for r in results]
        if results:
            worst = max(states, key=lambda s: _ORDER.index(STATE_DISPOSITION[s]))
            disposition = STATE_DISPOSITION[worst]
            state = worst
            reason = f"route states {states}"
            primary = results[0].proof
            next_step = primary.get("proposal") or {"bounded_test": "verify premises or run the bounded experiment",
                                                     "abstain": "acquire the missing input",
                                                     "handoff": "adjudicate the conflict"}.get(disposition)
        else:
            state, disposition, reason, next_step = "OK", "recommend", "options only", None
        if ranking is not None:
            status = ranking["status"]
            if status == "chosen" and disposition == "recommend":
                reason = f"option {ranking['chosen']} passed every gate and dominates on the recorded criteria"
            elif status in ("incomparable", "within_margin"):
                state, disposition = state if state != "OK" else "OK", _lower(disposition, "handoff")
                reason = f"eligible options are {status}; tradeoffs preserved for the founder"
                next_step = "founder chooses among the preserved tradeoffs"
            elif status == "none_eligible":
                resolutions = set(ranking["excluded"].values())
                if "authorized_adjudication" in resolutions:
                    state, disposition = "GATE_UNRESOLVED", _lower(disposition, "handoff")
                    next_step = "obtain the missing authorization through the Kernel authority path"
                elif "bounded_evidence_acquisition" in resolutions:
                    state, disposition = "GATE_UNRESOLVED", _lower(disposition, "bounded_test")
                    next_step = "acquire the evidence the gates name"
                else:
                    state, disposition = "GATE_FAILED", "abstain"
                    next_step = "no option may be recommended"
                reason = f"no option passed every gate: {ranking['excluded']}"
        if disposition == "recommend":
            ceiling_ok = all(next((e.may_recommend for e in eligibility if e.key == k), False) for k in selected)
            if not ceiling_ok or consequence_rank(geometry.consequence_class) >= consequence_rank("financial"):
                disposition = "handoff"
                reason = f"{geometry.consequence_class} exceeds what cognition may recommend; handing off"
                next_step = "decision through the Kernel authority path and Consequence Gate"
        return state, disposition, reason, next_step

    # ------------------------------------------------------------------ receipt
    def _truth(self, results: list[OrganResult]) -> dict:
        formal = next((r for r in results if r.proof.get("proof_class") == "formal"), None)
        if formal is None:
            formal_validity = "not_applicable"
        elif formal.state in ("OK", "WORLD_UNVERIFIED"):
            formal_validity = "valid_given_encoding"
        else:
            formal_validity = "not_established"
        empirical = "unknown"
        for r in results:
            pc = r.proof.get("proof_class")
            if pc == "formal" and r.state == "OK":
                empirical = "premises_verified"
            elif pc == "formal" and r.state == "WORLD_UNVERIFIED":
                empirical = "unverified_premises"
            elif pc == "evidence_assessment" and r.state == "OK":
                empirical = f"evidence_{r.answer['verdict']}"
            elif pc == "evidence_assessment" and r.state == "CONTESTED":
                empirical = "contested"
            elif pc == "causal_estimate":
                empirical = "conditional_on_identification_assumptions"
            elif pc == "estimation" and r.state == "OK":
                empirical = "unverified_estimate"
            elif pc == "semantic_sourced" and r.state == "OK":
                empirical = "textually_supported_only"
        return {"formal_validity": formal_validity, "empirical_validity": empirical,
                "legitimate_authority": "not_granted_by_cortex",
                "authority_path": "Kernel policy engine -> capability grant -> Consequence Gate"}

    def _receipt(self, problem, geometry, eligibility, selected, alternatives, results, verifier, gate_reports,
                 ranking, state, disposition, reason, next_step, spent, protection=None) -> dict:
        payload = problem.payload
        refs = sorted({s.get("id") for s in payload.get("sources", []) if s.get("id")} |
                      {e.get("id") for e in payload.get("evidence", []) if e.get("id")})
        answer = None
        if disposition in ("recommend", "bounded_test", "handoff"):
            answers = [r.answer for r in results if r.answer is not None]
            answer = answers[0] if len(answers) == 1 else (answers or None)
        if ranking is not None and ranking.get("chosen") and disposition == "recommend":
            answer = {"chosen_option": ranking["chosen"], "route_answers": answer}
        versions = {"cortex": CORTEX_VERSION, "policy": POLICY_VERSION,
                    "routes": {r.organ_id: r.organ_version for r in results}}
        solver = next((r.proof.get("solver") for r in results if r.proof.get("solver")), None)
        if solver:
            versions["solver"] = {"name": solver.get("name"), "version": solver.get("version")}
        model = next((r.proof.get("model") for r in results if r.proof.get("proof_class") == "semantic_sourced"), None)
        if model:
            versions["model"] = model
        body = {
            "schema": "cortex-receipt/0.1",
            "created_at": self.clock(),
            "problem": {"problem_id": problem.problem_id, "question_digest": digest(problem.question),
                        "payload_digest": digest(dict(payload))},
            "inputs": {"evidence_refs": refs, "payload_keys": sorted(payload)},
            "versions": versions,
            "geometry": geometry.to_dict(),
            "eligibility": [e.to_dict() for e in eligibility],
            "route": {"policy": POLICY_VERSION, "selected": list(selected),
                      "composition": len(selected) > 1,
                      "rationale": "structured payload fields select routes by the fixed policy table; "
                                   "eligibility and budget filter first"},
            "alternatives": alternatives,
            "assumptions": [a for r in results for a in r.assumptions],
            "output": {"state": state, "answer": answer, "per_route": [r.to_dict() for r in results]},
            "uncertainty": "; ".join(r.uncertainty for r in results) or "no route executed",
            "proof_artifacts": [dict(r.proof) for r in results],
            "verifier": verifier,
            "gates": {k: v.to_dict() for k, v in gate_reports.items()} or None,
            "ranking": ranking,
            "shared_dependencies": verifier["independence"]["shared_between_routes"],
            "expenditure": spent.to_dict(),
            "disposition": {"kind": disposition, "reason": reason, "next_step": next_step},
            "truth": self._truth(results),
            "protection": None if protection is None or not protection.relevant else {
                **protection.to_dict(),
                "evidence_handling": "receipt carries evidence identifiers and digests only, never content",
                "human_led_actions": [a for a in protection.required_actions if a in HUMAN_LED_PROTECTION]},
            "outcome_link": {"status": "absent_feedback", "settlement_ref": None,
                             "memory_keys": [f"{k}|{geometry.epistemic_class}" for k in selected]},
            "authority_created": False,
            "execution_authority": "none",
        }
        body["receipt_id"] = digest(body)
        return body

    def _malformed(self, raw, why, started, geometry=None) -> dict:
        body = {
            "schema": "cortex-receipt/0.1", "created_at": self.clock(),
            "problem": {"problem_id": str((raw or {}).get("problem_id") if isinstance(raw, Mapping) else "unknown"),
                        "question_digest": digest(str((raw or {}).get("question") if isinstance(raw, Mapping) else "")),
                        "payload_digest": digest(str(raw))},
            "inputs": {"evidence_refs": [], "payload_keys": []},
            "versions": {"cortex": CORTEX_VERSION, "policy": POLICY_VERSION, "routes": {}},
            "geometry": geometry.to_dict() if geometry else None,
            "eligibility": [], "route": {"policy": POLICY_VERSION, "selected": [], "composition": False,
                                         "rationale": "input rejected before routing"},
            "alternatives": [], "assumptions": [],
            "output": {"state": "MALFORMED_INPUT", "answer": None, "per_route": []},
            "uncertainty": "no route executed", "proof_artifacts": [],
            "verifier": {"proof_class": "verifier_findings", "verifier": adversarial.VERIFIER_ID,
                         "findings": [{"severity": "major", "kind": "malformed_input", "detail": why,
                                       "target": None}], "blocking": False,
                         "independence": {"verifier": adversarial.VERIFIER_ID,
                                          "verifier_dependencies": list(adversarial.VERIFIER_DEPENDENCIES),
                                          "shared_with_routes": [], "independent_of_routes": True,
                                          "shared_between_routes": {}, "note": "no routes ran"}},
            "gates": None, "ranking": None, "shared_dependencies": {},
            "expenditure": Expenditure(seconds=time.perf_counter() - started).to_dict(),
            "disposition": {"kind": "abstain", "reason": f"malformed input: {why}",
                            "next_step": "correct the input"},
            "truth": {"formal_validity": "not_applicable", "empirical_validity": "unknown",
                      "legitimate_authority": "not_granted_by_cortex",
                      "authority_path": "Kernel policy engine -> capability grant -> Consequence Gate"},
            "protection": None,
            "outcome_link": {"status": "absent_feedback", "settlement_ref": None, "memory_keys": []},
            "authority_created": False, "execution_authority": "none",
        }
        body["receipt_id"] = digest(body)
        return body


def _lower(current: str, floor: str) -> str:
    """Move a disposition toward caution; never toward recommend."""
    return current if _ORDER.index(current) >= _ORDER.index(floor) else floor
