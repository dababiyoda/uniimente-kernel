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

import importlib.util
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
from . import outcomes
from .organs import adversarial, cpsat
from .organs.cpsat import CpSatOrgan
from .organs.deterrence import DeterrenceOrgan
from .organs.estimation import EstimationOrgan
from .organs.evidence_causal import EvidenceCausalOrgan
from .organs.formal import FormalOrgan
from .organs.schedule_extraction import ScheduleExtractionOrgan
from .organs import schedule_extraction
from .organs.semantic import SemanticOrgan

POLICY_VERSION = "cortex-route-policy/0.2"
BUDGET_POLICY = "cortex-thinking-budget/0.1"
RECEIPT_SCHEMA = "cortex-receipt/0.2"
FORMAL = "cortex.formal.z3@0.2.0"
FERMI = "cortex.estimation.fermi@0.1.0"
EVIDENCE = "cortex.evidence_causal@0.1.0"
SEMANTIC = "cortex.semantic@0.1.0"
DETERRENCE = "cortex.deterrence.accountability@0.1.0"
CPSAT = cpsat.ORGAN_ID
EXTRACT = schedule_extraction.ORGAN_ID
# Fault-diverse engines behind the one formal_model contract (directive 7C, 14).
FORMAL_ENGINES = (FORMAL, CPSAT)

# The deterministic route policy lives in _route_parts: formal_model -> Formal,
# estimation_model -> Fermi, claim -> Evidence/Causal, sources -> Semantic.
# Policy 0.2: the Formal slot has two engines (Z3, OR-Tools CP-SAT) chosen by
# _formal_plan after hard eligibility; see that function for the fixed order.
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


def _formal_class(model: Mapping[str, Any]) -> str:
    kind = (model.get("query") or {}).get("kind", "feasibility")
    return {"entailment": "deductive_logical", "optimize": "optimization"}.get(kind, "constraint_feasibility")


def _route_parts(payload: Mapping[str, Any]) -> list[tuple[str, str]]:
    """(route key, epistemic class of the payload part it serves), in policy order."""
    parts = []
    fm = payload.get("formal_model")
    if isinstance(fm, Mapping):
        parts.append((FORMAL, _formal_class(fm)))
    elif isinstance(payload.get("schedule_request"), Mapping):
        # Seed composition: words -> declarative model -> formal slot (planned after extraction).
        parts.append((EXTRACT, "constraint_feasibility"))
    if isinstance(payload.get("estimation_model"), Mapping):
        parts.append((FERMI, "estimate"))
    if isinstance(payload.get("deterrence_model"), Mapping):
        parts.append((DETERRENCE, "strategic"))
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
        out.append(_formal_class(fm))
    elif isinstance(payload.get("schedule_request"), Mapping):
        out.append("constraint_feasibility")
    if isinstance(payload.get("estimation_model"), Mapping):
        out.append("estimate")
    if isinstance(payload.get("deterrence_model"), Mapping):
        out.append("strategic")
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
                 "optimization": "exact_required", "arithmetic": "exact_required",
                 "estimate": "approximate_ok"}.get(epistemic, "unknown")
    uncertainty = {"constraint_feasibility": "low", "deductive_logical": "low", "optimization": "low",
                   "estimate": "high",
                   "causal": "high", "prediction": "high"}.get(epistemic, "unknown")
    objective = {"constraint_feasibility": "decide_feasibility", "deductive_logical": "decide_entailment",
                 "optimization": "optimize_objective",
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


# ------------------------------------------------------------------ accountability
# Review pass 2 (B34, B35): a receipt should narrow disputes. It names the strongest
# counterargument, what observation would falsify each route's claim, and what is missing.
_SEVERITY = {"critical": 0, "major": 1, "minor": 2}


def _falsifier(result: OrganResult) -> str:
    proof, answer = result.proof or {}, result.answer
    pc = proof.get("proof_class")
    if answer is None:
        return "no claim asserted; nothing to falsify"
    if pc in ("formal", "optimization"):
        kind = (proof.get("structured_model") or {}).get("query", {}).get("kind", "feasibility")
        premises = [p.get("id") for p in proof.get("premises") or []]
        tail = f", or premise {premises} found false" if premises else ""
        if kind == "optimize" and answer.get("optimal"):
            relation = "<" if answer.get("sense") == "minimize" else ">"
            return f"a feasible assignment with objective {relation} {answer.get('objective')}, or a mis-encoded constraint{tail}"
        if answer.get("feasible") is False:
            return f"an assignment satisfying every constraint in core {answer.get('unsat_core')}, or a mis-encoded constraint{tail}"
        if answer.get("entailed") is True:
            return f"an assignment satisfying the constraints that violates the property{tail}"
        if answer.get("entailed") is False:
            return "the reported counterexample violating a constraint"
        return f"the reported model violating a constraint, or a requirement the encoding omits{tail}"
    if pc == "estimation":
        return (f"an observed value outside [{answer.get('low')}, {answer.get('high')}] {answer.get('unit')}, "
                f"or a reference class the estimate contradicts")
    if pc == "causal_estimate":
        return (f"a better-identified estimate (e.g. randomized) outside {answer.get('ci95')}, a failed refutation, "
                f"or an identification assumption shown false")
    if pc == "evidence_assessment":
        return "verified evidence contradicting the claim, or the missing observations resolving against it"
    if pc == "semantic_sourced":
        return "a quoted span absent from its cited source, or the cited source shown wrong"
    if pc == "deterrence_assessment":
        best = answer.get("best_intervention") or {}
        return (f"misconduct persisting after {best.get('id', 'the intervention')} at a rate above "
                f"{best.get('pays_probability_after', answer.get('misconduct_pays_probability'))}, "
                f"or a declared parameter range shown wrong")
    return "not stated by the route"


def _accountability(geometry, results, verifier, gate_reports, protection) -> dict:
    findings = sorted(verifier.get("findings", []), key=lambda f: _SEVERITY.get(f["severity"], 3))
    strongest = ({"severity": findings[0]["severity"], "kind": findings[0]["kind"], "detail": findings[0]["detail"]}
                 if findings else None)
    missing = [f"geometry field {f} unresolved" for f in geometry.unresolved_fields]
    for r in results:
        proof = r.proof or {}
        assessment = proof.get("evidence_assessment", proof)
        missing += [f"observation: {m.get('description')}" for m in assessment.get("missing_observations", []) or []]
        if assessment.get("unresolved_question"):
            missing.append(f"unresolved: {assessment['unresolved_question']}")
    for option, report in (gate_reports or {}).items():
        missing += [f"{option}: {name} gate unresolved ({g.reason})" for name, g in report.gates.items()
                    if g.status == "UNRESOLVED"]
    if protection is not None and protection.relevant:
        missing += [f"protection: {g}" for g in protection.gaps]
    return {"strongest_counterargument": strongest,
            "falsification_conditions": [{"route": r.organ_id, "condition": _falsifier(r)} for r in results],
            "missing_information": list(dict.fromkeys(missing)),
            "note": "competence evidence and proof narrow disputes; they never create authority"}


class Cortex:
    """The seed cortex. Holds a registry and organ executors; owns no authority."""

    def __init__(self, registry: IntelligenceRegistry | None = None, *, organs: Mapping[str, Any] | None = None,
                 clock: Callable[[], str] | None = None, memory=None):
        self.registry = registry or seed_registry()
        self.organs = dict(organs or {FORMAL: FormalOrgan(), CPSAT: CpSatOrgan(), EXTRACT: ScheduleExtractionOrgan(),
                                      FERMI: EstimationOrgan(),
                                      EVIDENCE: EvidenceCausalOrgan(), SEMANTIC: SemanticOrgan(),
                                      DETERRENCE: DeterrenceOrgan()})
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
        formal_plan = None
        for i, (key, part_class) in enumerate(parts):
            if key == FORMAL:
                formal_plan = self._formal_plan(problem, replace(geometry, epistemic_class=part_class))
                lead = formal_plan["order"][0] if formal_plan["order"] else FORMAL
                parts[i] = (lead, part_class)
                rows = {e.key: e for e in self.registry.eligibility(replace(geometry, epistemic_class=part_class))}
                part_eligibility.update({k: rows[k] for k in FORMAL_ENGINES if k in rows})
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
        elif set(FORMAL_ENGINES) & set(selected) and limits.max_solver_calls < 1:
            budget_problem = "route needs the solver; solver-call budget is zero"

        results: list[OrganResult] = []
        attempts: list[dict] = []
        decisions: list[dict] = []
        source_problem = problem
        if budget_problem is None:
            for key in list(selected):
                if key == EXTRACT:
                    problem, executed, plan = self._compose_schedule(problem, geometry, limits, started, results,
                                                                     attempts, decisions)
                    selected = selected + [k for k in executed if k not in selected]
                    formal_plan = plan
                    continue
                if key in FORMAL_ENGINES and formal_plan is not None:
                    result, tried, decided = self._run_formal(problem, geometry, limits, formal_plan, started)
                    results.append(result)
                    attempts += tried
                    decisions += decided
                else:
                    results.append(self.organs[key].run(problem, geometry, limits))
        l1 = _l1_checks(problem, geometry, formal_plan)
        spent = Expenditure()
        for r in results:
            spent = spent.plus(r.expenditure)
        for a in attempts:
            spent = spent.plus(Expenditure(seconds=a["expenditure"]["seconds"],
                                           solver_calls=a["expenditure"]["solver_calls"]))

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
        extra_reasons = []
        if disposition == "handoff" and consequence_rank(geometry.consequence_class) >= consequence_rank("financial"):
            extra_reasons.append("AUTHORITY_REQUIRED")
        if protection.relevant and (set(protection.required_actions) & set(HUMAN_LED_PROTECTION) or protection.gaps):
            human_led = [a for a in protection.ordered_actions if a in HUMAN_LED_PROTECTION]
            extra_reasons.append("HUMAN_JUDGMENT_REQUIRED")
            if disposition != "handoff":
                disposition = "handoff"
                why = f"human-led action {human_led}" if human_led else f"unresolved protection gaps {list(protection.gaps)}"
                reason = f"victim protection requires {why}; {reason}"
            next_step = (f"human-led protective response ({', '.join(protection.ordered_actions) or 'actions to be decided'}); "
                         f"evidence access {protection.evidence_access}"
                         + (f"; resolve first: {'; '.join(protection.gaps)}" if protection.gaps else ""))
        deterrent = next((r for r in results if (r.proof or {}).get("proof_class") == "deterrence_assessment"
                          and r.answer and r.answer.get("external_action_required")), None)
        if deterrent is not None:
            # Deterrence that reaches another party is decided by legitimate authority, never by cognition.
            kind = deterrent.answer["best_intervention"]["kind"]
            extra_reasons.append("AUTHORITY_REQUIRED")
            if disposition != "handoff":
                disposition = "handoff"
                reason = f"strongest lawful deterrent ({kind}) reaches another party; {reason}"
            next_step = (f"give the deterrence assessment and its evidence to the competent authority for a "
                         f"decision on {kind}; the cortex takes no action against anyone")
        verifier = adversarial.verify(problem, geometry, results, proposed_disposition=disposition,
                                      gate_reports=gate_reports, ranking=ranking, protection=protection)
        if verifier["blocking"] and disposition == "recommend":
            kinds = {f["kind"] for f in verifier["findings"] if f["severity"] == "critical"}
            disposition = "handoff" if kinds & {"authority_boundary", "consequence_boundary"} else "abstain"
            reason = f"critical verifier finding(s): {sorted(kinds)}"
            next_step = "resolve the findings before relying on this result"
        spent = spent.plus(Expenditure(seconds=time.perf_counter() - started - spent.seconds))
        return self._receipt(source_problem, geometry, eligibility, selected, alternatives, results, verifier,
                             gate_reports, ranking, state, disposition, reason, next_step, spent, protection,
                             formal_plan=formal_plan, attempts=attempts, decisions=decisions, l1=l1,
                             extra_reasons=extra_reasons)



    # ------------------------------------------------------------------ seed composition
    def _compose_schedule(self, problem, geometry, limits, started, results, attempts, decisions):
        """Extraction -> compiled formal model -> formal slot. Returns (problem, executed keys, plan).

        The formal stage sees the compiled model; the verifier re-checks against it. Whether the
        compiled model is a faithful reading of the words is the extraction audit's and the
        founder's question, recorded in the extraction proof, never assumed here."""
        ext = self.organs[EXTRACT].run(problem, geometry, limits)
        results.append(ext)
        if ext.state != "OK":
            decisions.append({"step": "formal stage", "taken": False,
                              "reason": f"extraction state {ext.state}: no model to solve"})
            return problem, [], None
        model = ext.proof["compiled_model"]
        composed = Problem(problem.problem_id, problem.question, {**problem.payload, "formal_model": model})
        kind = (model.get("query") or {}).get("kind", "feasibility")
        part_geometry = replace(geometry, epistemic_class="optimization" if kind == "optimize"
                                else "constraint_feasibility")
        plan = self._formal_plan(composed, part_geometry)
        if not plan["order"]:
            decisions.append({"step": "formal stage", "taken": False,
                              "reason": f"no eligible formal engine: {plan['excluded']}"})
            return composed, [], plan
        result, tried, decided = self._run_formal(composed, part_geometry, limits, plan, started)
        results.append(result)
        attempts += tried
        decisions += decided
        return composed, [result.organ_id], plan

    # ------------------------------------------------------------------ formal slot (policy 0.2)
    def _engine_available(self, key: str, payload: Mapping[str, Any]) -> tuple[bool, str]:
        faults = payload.get("faults", {}) or {}
        if key == FORMAL:
            if faults.get("solver_available") is False:
                return False, "z3 outage injected by fault"
            return (importlib.util.find_spec("z3") is not None, "z3-solver is not installed")
        if key == CPSAT:
            if faults.get("cpsat_available") is False:
                return False, "CP-SAT outage injected by fault"
            return (cpsat.available(), "ortools is not installed")
        return True, ""

    def _formal_plan(self, problem: Problem, part_geometry: ProblemGeometry) -> dict:
        """Hard eligibility for each formal engine, then the fixed policy order.

        Eligibility (all must hold): registry row eligible (lifecycle, enabled, geometry,
        founder detach projected from GREG), dependency importable, model inside the
        engine's declared fragment. Order among eligible engines: optimization queries
        go to CP-SAT first (a dedicated OR engine; Z3 then supplies a fault-diverse
        optimality certificate); feasibility and entailment go to Z3 first (its
        per-constraint counterexample search and unsat core are the richer proof),
        CP-SAT second. Competence memory may reorder eligible engines only."""
        model = problem.payload.get("formal_model") or {}
        kind = (model.get("query") or {}).get("kind", "feasibility") if isinstance(model, Mapping) else "feasibility"
        rows = {e.key: e for e in self.registry.eligibility(part_geometry)}
        policy = [CPSAT, FORMAL] if kind == "optimize" else [FORMAL, CPSAT]
        order, excluded, unavailable = [], {}, []
        for key in policy:
            reasons = []
            row = rows.get(key)
            if row is None:
                reasons.append("not registered")
            elif not row.eligible:
                reasons += list(row.reasons)
            ok, why = self._engine_available(key, problem.payload)
            if not ok:
                reasons.append(f"dependency unavailable: {why}")
            if key == CPSAT and isinstance(model, Mapping):
                reasons += [f"outside fragment: {r}" for r in cpsat.unsupported(model)]
            if reasons:
                excluded[key] = reasons
                if row is not None and row.eligible and all(r.startswith("dependency unavailable") for r in reasons):
                    unavailable.append(key)
            else:
                order.append(key)
        if self.memory is not None and len(order) > 1:
            order = self.memory.reorder(order, part_geometry)
        if not order and unavailable:
            # Every engine the registry allows is down: run the first so the receipt states
            # DEPENDENCY_UNAVAILABLE truthfully instead of claiming no method exists.
            order = unavailable[:1]
        return {"policy": POLICY_VERSION, "query_kind": kind, "order": order, "excluded": excluded,
                "policy_order": policy}

    def _run_formal(self, problem, geometry, limits, plan, started) -> tuple[OrganResult, list, list]:
        """Run the lead engine, fall back on engine failure, then take only the optional
        cross-checks whose result could change the decision (budget controller)."""
        attempts, decisions = [], []
        order = list(plan["order"])
        result = self.organs[order[0]].run(problem, geometry, limits)
        calls = result.expenditure.solver_calls
        remaining = [k for k in order[1:]]
        failing = ("DEPENDENCY_UNAVAILABLE", "TIMEOUT", "INCONCLUSIVE")
        def rest():
            """The latency budget that remains for a later engine; never a fresh budget."""
            return replace(limits, max_latency_s=max(0.0, limits.max_latency_s - (time.perf_counter() - started)))

        while result.state in failing and result.answer is None and remaining:
            alt = remaining.pop(0)
            if calls >= limits.max_solver_calls:
                decisions.append({"step": f"fallback to {alt}", "taken": False,
                                  "reason": "solver-call budget exhausted", "solver_calls_used": calls})
                break
            if rest().max_latency_s <= 0:
                decisions.append({"step": f"fallback to {alt}", "taken": False,
                                  "reason": f"latency budget of {limits.max_latency_s}s exhausted",
                                  "solver_calls_used": calls})
                break
            decisions.append({"step": f"fallback to {alt}", "taken": True,
                              "reason": f"{result.organ_id} returned {result.state}; a fault-diverse engine can "
                                        f"still decide the same encoded question", "solver_calls_used": calls})
            attempts.append(_attempt(result, "superseded by fallback"))
            result = self.organs[alt].run(problem, geometry, rest())
            calls += result.expenditure.solver_calls
        others = [k for k in order if k != f"{result.organ_id}"]
        answer = result.answer or {}
        model = problem.payload.get("formal_model") or {}

        def affordable() -> tuple[bool, str]:
            elapsed = time.perf_counter() - started
            if calls >= limits.max_solver_calls:
                return False, "solver-call budget exhausted"
            if elapsed > limits.max_latency_s / 2:
                return False, f"latency budget: {elapsed:.3f}s of {limits.max_latency_s}s already spent"
            return True, ""

        if result.organ_id == CPSAT and answer.get("optimal") and FORMAL in others:
            ok, why = affordable()
            if not ok:
                decisions.append({"step": "independent optimality certificate (z3)", "taken": False, "reason": why})
            else:
                cert = cpsat.z3_optimality_certificate(model, answer["objective"], max(1, min(
                    int(model.get("timeout_ms", 5000)), int(rest().max_latency_s * 1000))))
                calls += 1
                decisions.append({"step": "independent optimality certificate (z3)", "taken": True,
                                  "reason": "an optimality claim changes which assignment is recommended; a "
                                            "different engine's UNSAT for a strictly better objective is cheap",
                                  "result": cert["status"]})
                proof = dict(result.proof)
                proof["certificate"] = cert
                state = result.state
                notes = result.notes
                if cert["status"] == "REFUTED":
                    state = "CONTESTED"
                    notes = notes + (f"z3 found a strictly better assignment {cert.get('better_assignment')}",)
                result = replace(result, proof=proof, state=state, notes=notes,
                                 expenditure=result.expenditure.plus(Expenditure(solver_calls=1)))
        elif result.organ_id == CPSAT and answer.get("feasible") and answer.get("optimal") is False \
                and FORMAL in others:
            ok, why = affordable()
            decisions.append({"step": "second engine to close the optimality gap (z3)", "taken": ok,
                              "reason": why or f"gap {answer.get('gap')} > 0: a proof of optimality could change "
                                               "the recommended assignment"})
            if ok:
                second = self.organs[FORMAL].run(problem, geometry, rest())
                calls += second.expenditure.solver_calls
                if second.state in ("OK", "WORLD_UNVERIFIED") and (second.answer or {}).get("optimal"):
                    attempts.append(_attempt(result, "superseded: z3 proved optimality"))
                    result = second
                else:
                    attempts.append(_attempt(second, "second engine did not close the gap"))
        elif (answer.get("feasible") is False or answer.get("entailed") is True) and others:
            alt = others[0]
            ok, why = affordable()
            decisions.append({"step": f"confirm the verdict with {alt}", "taken": ok,
                              "reason": why or "an impossibility or entailment verdict ends or settles the plan; a "
                                               "second engine's confirmation is cheap relative to acting on it"})
            if ok:
                second = self.organs[alt].run(problem, geometry, rest())
                calls += second.expenditure.solver_calls
                key = "feasible" if "feasible" in answer else "entailed"
                agrees = second.answer is not None and second.answer.get(key) == answer.get(key)
                attempts.append(_attempt(second, "confirmation" if agrees else "disagreement"))
                if second.answer is not None and not agrees:
                    proof = dict(result.proof)
                    proof["engine_disagreement"] = {"engine": second.organ_id, "answer": second.answer}
                    result = replace(result, state="CONTESTED", proof=proof,
                                     notes=result.notes + (f"{second.organ_id} disagrees: {second.answer}",))
                elif agrees:
                    proof = dict(result.proof)
                    proof["confirmed_by"] = {"engine": second.organ_id, "state": second.state}
                    result = replace(result, proof=proof)
        elif answer.get("feasible") is True or answer.get("entailed") is False:
            decisions.append({"step": "second engine", "taken": False,
                              "reason": "the returned assignment is re-checked against every source constraint by "
                                        "the solver-independent evaluator; a second engine cannot change a verified "
                                        "witness"})
        else:
            decisions.append({"step": "second engine", "taken": False,
                              "reason": f"no answer to cross-check (state {result.state})"})
        return result, attempts, decisions

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
        formal = next((r for r in results if r.proof.get("proof_class") in ("formal", "optimization")), None)
        if formal is None:
            formal_validity = "not_applicable"
        elif formal.state in ("OK", "WORLD_UNVERIFIED"):
            formal_validity = "valid_given_encoding"
        else:
            formal_validity = "not_established"
        empirical = "unknown"
        for r in results:
            pc = r.proof.get("proof_class")
            if pc in ("formal", "optimization") and r.state == "OK":
                empirical = "premises_verified"
            elif pc in ("formal", "optimization") and r.state == "WORLD_UNVERIFIED":
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
                 ranking, state, disposition, reason, next_step, spent, protection=None, *, formal_plan=None,
                 attempts=(), decisions=(), l1=(), extra_reasons=()) -> dict:
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
        outcome = outcomes.classify_cortex(
            state, disposition, answer_present=answer is not None, verifier_blocking=bool(verifier["blocking"]),
            refused_interventions=any((r.proof or {}).get("refused") for r in results))
        outcome["reasons"] = list(dict.fromkeys(outcome["reasons"] + list(extra_reasons)))
        solver = next((r.proof.get("solver") for r in results if r.proof.get("solver")), None)
        if solver:
            versions["solver"] = {"name": solver.get("name"), "version": solver.get("version")}
        model = next((r.proof.get("model") for r in results if r.proof.get("proof_class") == "semantic_sourced"), None)
        if model:
            versions["model"] = model
        body = {
            "schema": RECEIPT_SCHEMA,
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
                                   "eligibility and budget filter first",
                      "formal_plan": formal_plan, "attempts": list(attempts)},
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
                "human_led_actions": [a for a in protection.ordered_actions if a in HUMAN_LED_PROTECTION]},
            "accountability": _accountability(geometry, results, verifier, gate_reports, protection),
            "outcome_link": {"status": "absent_feedback", "settlement_ref": None,
                             "memory_keys": [f"{k}|{geometry.epistemic_class}" for k in selected]},
            "l1_checks": list(l1),
            "budget_controller": {"policy": BUDGET_POLICY, "decisions": list(decisions),
                                  "mandatory": ["eligibility gates", "adversarial verifier",
                                                "independent assignment re-evaluation", "consequence ceiling"],
                                  "note": "mandatory checks are never traded for cost; only optional deeper "
                                          "cognition is gated on its chance of changing the decision"},
            "outcome": outcome,
            "authority_created": False,
            "execution_authority": "none",
        }
        body["receipt_id"] = digest(body)
        return body

    def _malformed(self, raw, why, started, geometry=None) -> dict:
        body = {
            "schema": RECEIPT_SCHEMA, "created_at": self.clock(),
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
            "accountability": {"strongest_counterargument": {"severity": "critical", "kind": "malformed_input",
                                                             "detail": why},
                               "falsification_conditions": [], "missing_information": [f"well-formed input: {why}"],
                               "note": "competence evidence and proof narrow disputes; they never create authority"},
            "outcome_link": {"status": "absent_feedback", "settlement_ref": None, "memory_keys": []},
            "l1_checks": [{"check": "schema_valid", "value": "fail", "detail": why[:300]}],
            "budget_controller": {"policy": BUDGET_POLICY, "decisions": [], "mandatory": [],
                                  "note": "input rejected before any cognition was spent"},
            "outcome": outcomes.classify_cortex("MALFORMED_INPUT", "abstain", answer_present=False),
            "authority_created": False, "execution_authority": "none",
        }
        body["receipt_id"] = digest(body)
        return body


def _attempt(result: OrganResult, why: str) -> dict:
    return {"organ_id": result.organ_id, "state": result.state, "answer": None if result.answer is None
            else dict(result.answer), "why": why, "expenditure": result.expenditure.to_dict(),
            "notes": list(result.notes)[:5]}


L1_VALUES = ("pass", "fail", "unknown", "not_applicable")


def _l1_checks(problem: Problem, geometry: ProblemGeometry, formal_plan) -> list[dict]:
    """Layer-1 primitive checks: cheap, deterministic, four-valued (pass, fail, unknown,
    not_applicable are distinct). They record local state; they never replace an organ's
    own checks and never grant anything."""
    p = problem.payload
    out = [{"check": "schema_valid", "value": "pass", "detail": "problem and payload parsed"}]
    as_of = p.get("as_of")
    out.append({"check": "as_of_present", "value": "pass" if as_of else "unknown",
                "detail": as_of or "no reference date; freshness cannot be judged"})
    evidence = p.get("evidence") or []
    if not evidence:
        fresh, detail = "not_applicable", "no evidence items"
    elif not as_of:
        fresh, detail = "unknown", "no reference date"
    else:
        stale, unknown = [], []
        ref = datetime.fromisoformat(str(as_of)[:10])
        for e in evidence:
            try:
                age = (ref - datetime.fromisoformat(str(e.get("observed_at"))[:10])).days
            except (TypeError, ValueError):
                unknown.append(e.get("id"))
                continue
            if age < 0 or (e.get("max_age_days") is not None and age > e["max_age_days"]):
                stale.append(e.get("id"))
        fresh = "fail" if stale else ("unknown" if unknown else "pass")
        detail = f"stale or future-dated {stale}; undated {unknown}" if stale or unknown else "all within max age"
    out.append({"check": "evidence_fresh", "value": fresh, "detail": detail})
    sources = p.get("sources") or []
    injected = [s.get("id") for s in sources if adversarial._INJECTION.search(str(s.get("text", "")))]
    out.append({"check": "no_instruction_text_in_sources",
                "value": "not_applicable" if not sources else ("fail" if injected else "pass"),
                "detail": f"instruction-like text in {injected}" if injected else "scanned sources"})
    limits = geometry.resource_limits
    out.append({"check": "budget_declared", "value": "pass" if "resources" in p else "unknown",
                "detail": limits.to_dict()})
    if formal_plan is None:
        out.append({"check": "formal_engine_available", "value": "not_applicable", "detail": "no formal model"})
    else:
        out.append({"check": "formal_engine_available", "value": "pass" if formal_plan["order"] else "fail",
                    "detail": {"order": formal_plan["order"], "excluded": formal_plan["excluded"]}})
    return out


def _lower(current: str, floor: str) -> str:
    """Move a disposition toward caution; never toward recommend."""
    return current if _ORDER.index(current) >= _ORDER.index(floor) else floor
