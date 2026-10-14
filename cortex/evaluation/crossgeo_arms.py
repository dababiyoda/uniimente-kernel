"""The five compared systems (directive section 15), each given the same facts.

1. ``existing_greg``  GREG's #140 cognition path without the cortex. It accepts its own operation
   contract, so each item passes through a declared adapter (below) that projects the cortex
   payload onto the strongest #140 operation able to carry it. The adapter never adds a fact and
   never claims a design the input lacks; what it cannot carry is recorded as information lost.
2. ``always_llm``     the configured loopback model with a careful prompt. Runs only if a
   founder-selected local model answers a probe; otherwise NOT_RUN with the exact reason.
3. ``tool_llm``       a tool-enabled model workflow with the same tools. Same precondition.
4. ``static_router``  a fixed payload-key table to one specialist per part, using the same organ
   implementations as the cortex, plus the two obvious hard rules (human-authority questions and
   financial-or-worse consequences are handed off) and gate-checked option ranking. No
   eligibility, engine plan, fallback, certificate, budget controller, composition planning or
   independent verifier.
5. ``routed_greg``    the proposed system as deployed: ``cognition.solve`` -> GREG bridge ->
   bounded worker -> cortex -> GREG receipt. Latency includes the worker process.

Disposition vocabulary for scoring: recommend, abstain, handoff, bounded_test, error.
"""
from __future__ import annotations

import math
import time
import urllib.error
from dataclasses import replace
from typing import Any, Mapping

from ..contracts import HUMAN_AUTHORITY_CLASSES, CortexError, Problem, consequence_rank

# ------------------------------------------------------------------ 5. routed through GREG
_REGISTRY = None


def _greg_registry():
    global _REGISTRY
    if _REGISTRY is None:
        from greg.cognition.cortex import registry_view
        _REGISTRY = registry_view()
    return _REGISTRY


def routed_greg(item: Mapping[str, Any]) -> dict:
    from greg.cognition.cortex import reason
    from greg.cognition.settlement import _valid_receipt
    from ..schemas import validate
    params = {"problem_id": item["item_id"], "problem": {"question": item["problem"]["question"],
                                                         "payload": item["problem"]["payload"]}}
    if item.get("records"):
        params["records"] = item["records"]
    started = time.perf_counter()
    r = reason(params, registry=_greg_registry())
    latency = time.perf_counter() - started
    out = {"latency_s": latency, "cost_usd": float(r.get("money_cost") or 0.0),
           "authority_created": bool(r.get("authority_created")), "method": r.get("method"),
           "outcome": (r.get("outcome") or {}).get("outcome")}
    if r.get("proof_type") != "cortex_receipt":
        out.update(disposition="error", answer=None, receipt_valid=_valid_receipt(r),
                   error="; ".join(r.get("missing_information") or [])[:300])
        return out
    pa = r["proof_artifact"]
    try:
        validate(pa, "cortex-receipt")
        valid = _valid_receipt(r)
    except Exception:   # noqa: BLE001 - any schema failure is an invalid receipt
        valid = False
    out.update(disposition=pa["disposition"]["kind"], answer=pa["output"]["answer"], receipt_valid=valid,
               authority_created=out["authority_created"] or bool(pa.get("authority_created")),
               receipt_id=r.get("receipt_id"))
    return out


# ------------------------------------------------------------------ 1. existing GREG (#140) + adapter
ADAPTER_INFORMATION_LOST = (
    "premises and their verification state", "witnesses", "obligations and coverage", "requirement text",
    "estimation dependencies and reference classes (an interval enclosure is valid regardless)",
    "evidence records, claims, options and authority records (no #140 operation carries them)",
    "resource budgets other than latency", "free-text schedule requests")
_STRICT_INT = {"<": ("<=", -1), ">": (">=", 1)}


def _linear(node, sorts):
    """s-expression -> ({var: coeff}, const) or None when not linear."""
    if isinstance(node, bool):
        return None
    if isinstance(node, (int, float)):
        return {}, node
    if isinstance(node, str):
        return ({node: 1}, 0) if node in sorts else None
    if not isinstance(node, list) or not node:
        return None
    op, args = node[0], [_linear(a, sorts) for a in node[1:]]
    if any(a is None for a in args):
        return None
    if op == "+":
        coeffs, const = {}, 0
        for c, k in args:
            const += k
            for v, x in c.items():
                coeffs[v] = coeffs.get(v, 0) + x
        return coeffs, const
    if op == "-":
        if len(args) == 1:
            return {v: -x for v, x in args[0][0].items()}, -args[0][1]
        (c0, k0), rest = args[0], args[1:]
        coeffs, const = dict(c0), k0
        for c, k in rest:
            const -= k
            for v, x in c.items():
                coeffs[v] = coeffs.get(v, 0) - x
        return coeffs, const
    if op == "*":
        scalar, var = 1, None
        for c, k in args:
            if c:
                if var is not None:
                    return None
                var = (c, k)
            else:
                scalar *= k
        if var is None:
            return {}, scalar
        return {v: x * scalar for v, x in var[0].items()}, var[1] * scalar
    return None


def _constraint(expr, sorts, all_int):
    if not isinstance(expr, list) or len(expr) != 3 or expr[0] not in ("<=", ">=", "=", "!=", "<", ">"):
        return None
    lhs, rhs = _linear(expr[1], sorts), _linear(expr[2], sorts)
    if lhs is None or rhs is None:
        return None
    coeffs = dict(lhs[0])
    for v, x in rhs[0].items():
        coeffs[v] = coeffs.get(v, 0) - x
    bound = rhs[1] - lhs[1]
    op = {"=": "=="}.get(expr[0], expr[0])
    if op in _STRICT_INT:
        if not all_int or any(not float(x).is_integer() for x in [*coeffs.values(), bound]):
            return None
        op, shift = _STRICT_INT[op]
        bound += shift
    coeffs = {v: x for v, x in coeffs.items() if x}
    if not coeffs:
        return None
    if all_int:
        if any(not float(x).is_integer() for x in [*coeffs.values(), bound]):
            return None
        coeffs, bound = {v: int(x) for v, x in coeffs.items()}, int(bound)
    return {"coefficients": coeffs, "op": op, "rhs": bound}


_NEGATE = {"<=": (">=", 1), ">=": ("<=", -1), "!=": ("==", 0)}


def _formal_requests(fm) -> list[dict] | None:
    variables = fm.get("variables") or []
    if any(v.get("sort") not in ("int", "real") or v.get("lo") is None or v.get("hi") is None for v in variables):
        return None
    sorts = {v["name"]: v["sort"] for v in variables}
    all_int = all(s == "int" for s in sorts.values())
    bounds = {v["name"]: [v["lo"], v["hi"]] for v in variables}
    cons = [_constraint(c.get("expr"), sorts, all_int) for c in fm.get("constraints", [])]
    if any(c is None for c in cons):
        return None
    query = fm.get("query") or {"kind": "feasibility"}
    if query["kind"] == "feasibility":
        if all_int:
            return [{"operation": "optimize", "data": {"variables": bounds, "constraints": cons,
                                                       "objective": {"coefficients": {}, "sense": "min"}},
                     "_read": "feasible_int"}]
        return [{"operation": "constraints", "data": {"variables": bounds, "constraints": cons},
                 "_read": "feasible_real"}]
    if query["kind"] == "optimize":
        obj = _linear(query.get("objective"), sorts)
        if not all_int or obj is None or any(not float(x).is_integer() for x in obj[0].values()):
            return None
        sense = {"minimize": "min", "maximize": "max"}.get(query.get("sense"))
        return [{"operation": "optimize", "data": {"variables": bounds, "constraints": cons,
                                                   "objective": {"coefficients": {v: int(x) for v, x in obj[0].items()},
                                                                 "sense": sense}},
                 "_read": "optimize", "_offset": obj[1]}]
    if query["kind"] == "entailment" and all_int:
        prop = _constraint(query.get("property"), sorts, True)
        if prop is None or prop["op"] not in _NEGATE:
            return None
        op, shift = _NEGATE[prop["op"]]
        negated = {"coefficients": prop["coefficients"], "op": op, "rhs": prop["rhs"] + shift}
        return [{"operation": "optimize", "data": {"variables": bounds, "constraints": cons + [negated],
                                                   "objective": {"coefficients": {}, "sense": "min"}},
                 "_read": "entailed"}]
    return None


def _estimation_request(em) -> dict | None:
    from ..organs.estimation import EstimationError, Unit
    expr = em.get("expression")
    if not isinstance(expr, list) or not expr or expr[0] != "*":
        return None
    by_name = {v.get("name"): v for v in em.get("variables", [])}
    factors, scale = [], 1.0
    try:
        for arg in expr[1:]:
            if isinstance(arg, str) and arg in by_name:
                v = by_name[arg]
                if v.get("low") is None or v.get("high") is None:
                    return None
                lo, hi = float(v["low"]), float(v["high"])
                factors.append({"name": arg, "low": lo, "central": math.sqrt(lo * hi), "high": hi})
                scale *= Unit.parse(v.get("unit", "1")).scale
            elif isinstance(arg, dict) and "const" in arg:
                c = float(arg["const"])
                factors.append({"name": f"const_{len(factors)}", "low": c, "central": c, "high": c})
                scale *= Unit.parse(arg.get("unit", "1")).scale
            else:
                return None
        scale /= Unit.parse((em.get("target") or {}).get("unit", "1")).scale
    except (EstimationError, ValueError, TypeError):
        return None
    if abs(scale - 1.0) > 1e-12:
        factors.append({"name": "unit_conversion", "low": scale, "central": scale, "high": scale})
    return {"operation": "estimate", "data": {"factors": factors}, "_read": "interval"}


def _causal_request(spec) -> dict | None:
    rows = spec.get("data")
    if not isinstance(rows, list) or not rows:
        return None
    t, y = spec.get("treatment", "t"), spec.get("outcome", "y")
    design = "randomized" if (spec.get("identification_basis") or {}).get("origin") == "randomized_experiment" \
        else "observational"
    return {"operation": "treatment_effect", "data": {
        "design": design, "treated": [r[y] for r in rows if r.get(t) == 1],
        "control": [r[y] for r in rows if r.get(t) == 0]}, "_read": "effect"}


def adapt(problem: Mapping[str, Any]) -> tuple[list[dict] | None, dict]:
    """Cortex payload -> #140 requests (None when no #140 operation can carry it)."""
    payload = problem.get("payload") or {}
    declared = payload.get("declared") or {}
    geometry = {"consequence_class": declared.get("consequence_class", "read_only"),
                "reversibility": declared.get("reversibility", "reversible")}
    if geometry["consequence_class"] not in ("read_only", "internal_write", "external_contact", "financial",
                                             "irreversible"):
        geometry["consequence_class"] = "read_only"
    if geometry["reversibility"] not in ("reversible", "partially_reversible", "irreversible", "unknown"):
        geometry["reversibility"] = "unknown"
    latency = (payload.get("resources") or {}).get("max_latency_s")
    if isinstance(latency, (int, float)):
        geometry["latency_limit"] = min(30.0, max(0.01, float(latency)))
    klass = declared.get("epistemic_class")
    if klass in ("legal", "normative_value", "normative"):
        flag = {"legal": "legal_content"}.get(klass, "human_value_content")
        return [{"operation": "human_review", "data": {}, "geometry": {**geometry, flag: True,
                                                                       "epistemic_class": "legal" if klass == "legal"
                                                                       else "normative"}, "_read": "none"}], geometry
    requests: list[dict] = []
    if isinstance(payload.get("formal_model"), Mapping):
        r = _formal_requests(payload["formal_model"])
        if r is None:
            return None, geometry
        requests += r
    if isinstance(payload.get("estimation_model"), Mapping):
        r = _estimation_request(payload["estimation_model"])
        if r is None:
            return None, geometry
        requests.append(r)
    if isinstance(payload.get("causal_spec"), Mapping):
        r = _causal_request(payload["causal_spec"])
        if r is None:
            return None, geometry
        requests.append(r)
    if payload.get("sources"):
        requests.append({"operation": "interpret", "data": {"sources": payload["sources"]}, "_read": "text"})
    other = {"claim", "evidence", "options", "schedule_request", "deterrence_model"} & set(payload)
    if other and not (other == {"claim"} and "causal_spec" in payload):
        return None, geometry
    if not requests:
        return None, geometry
    return requests, geometry


def _read(kind, output, offset=0):
    if kind == "feasible_int":
        return {"feasible": output["solver_status"] in ("OPTIMAL", "FEASIBLE"), "model": output.get("solution")}
    if kind == "feasible_real":
        if output["solver_status"] not in ("SAT", "UNSAT"):
            return None
        return {"feasible": output["solver_status"] == "SAT", "model": output.get("solution")}
    if kind == "optimize":
        if output["solver_status"] == "INFEASIBLE":
            return {"feasible": False}
        if output.get("objective_value") is None:
            return None
        v = output["objective_value"] + offset
        return {"feasible": True, "objective": int(v) if float(v).is_integer() else v,
                "optimal": output["solver_status"] == "OPTIMAL"}
    if kind == "entailed":
        return {"entailed": output["solver_status"] == "INFEASIBLE"}
    if kind == "interval":
        return {"low": output["low"], "median": output["central"], "high": output["high"]}
    if kind == "effect":
        return {"effect": output.get("effect")}
    if kind == "text":
        return {"answer": " ".join(str(c) for c in output.get("claims", []))}
    return None


def existing_greg(item: Mapping[str, Any]) -> dict:
    from greg.cognition.cortex import reason
    from greg.cognition.settlement import _valid_receipt
    started = time.perf_counter()
    requests, geometry = adapt(item["problem"])
    if requests is None:
        return {"disposition": "abstain", "answer": None, "latency_s": time.perf_counter() - started,
                "cost_usd": 0.0, "note": "no #140 operation carries this payload", "receipt_valid": None}
    dispositions, answers, cost, authority, valid = [], [], 0.0, False, True
    for i, req in enumerate(requests):
        params = {"problem_id": f"{item['item_id']}:{i}", "operation": req["operation"], "data": req["data"],
                  "geometry": req.get("geometry", geometry)}
        r = reason(params, registry=_greg_registry())
        cost += float(r.get("money_cost") or 0.0)
        authority = authority or bool(r.get("authority_created"))
        valid = valid and _valid_receipt(r)
        state, output = r.get("abstention_state"), r.get("output")
        answer = _read(req["_read"], output, req.get("_offset", 0)) if output is not None else None
        if state == "HUMAN_REVIEW_REQUIRED":
            dispositions.append("handoff")
        elif state == "NONE" and answer is not None:
            dispositions.append("recommend")
        elif state == "WORLD_UNVERIFIED" and answer is not None:
            dispositions.append("bounded_test")
        else:
            dispositions.append("abstain")
        answers.append(answer)
    if all(d == "recommend" for d in dispositions):
        disposition = "recommend"
    elif "handoff" in dispositions:
        disposition = "handoff"
    elif "bounded_test" in dispositions and "abstain" not in dispositions:
        disposition = "bounded_test"
    else:
        disposition = "abstain"
    return {"disposition": disposition, "answer": answers[0] if len(answers) == 1 else answers,
            "latency_s": time.perf_counter() - started, "cost_usd": cost, "authority_created": authority,
            "receipt_valid": valid, "operations": [r["operation"] for r in requests]}


# ------------------------------------------------------------------ 4. static rules router
class _NoModel:
    def complete(self, system, user):
        raise OSError("no founder-selected local model")


def static_router(item: Mapping[str, Any]) -> dict:
    from ..gates import AuthorityRecord, Option, evaluate_gates, rank_after_gates
    from ..organs.formal import FormalOrgan
    from ..organs.schedule_extraction import ScheduleExtractionOrgan
    from ..organs.semantic import SemanticOrgan
    from ..routing import (EXTRACT, FORMAL, CPSAT, SEMANTIC, Cortex, _route_parts, derive_geometry)
    started = time.perf_counter()

    def done(disposition, answer=None, **kw):
        return {"disposition": disposition, "answer": answer, "latency_s": time.perf_counter() - started,
                "cost_usd": 0.0, **kw}
    try:
        problem = Problem.from_dict(item["problem"])
        geometry = derive_geometry(problem)
    except (CortexError, KeyError, TypeError, ValueError) as exc:
        return done("abstain", note=f"malformed: {exc}")
    if geometry.epistemic_class in HUMAN_AUTHORITY_CLASSES or \
            consequence_rank(geometry.consequence_class) >= consequence_rank("financial"):
        return done("handoff")
    organs = Cortex().organs
    organs[SEMANTIC] = SemanticOrgan(_NoModel())
    organs[EXTRACT] = ScheduleExtractionOrgan(None)
    limits = geometry.resource_limits
    states, answers = [], []
    for key, part_class in _route_parts(problem.payload):
        g = replace(geometry, epistemic_class=part_class)
        if key == EXTRACT:
            ext = organs[EXTRACT].run(problem, g, limits)
            states.append(ext.state)
            answers.append(ext.answer)
            if ext.state != "OK":
                continue
            model = ext.proof["compiled_model"]
            composed = Problem(problem.problem_id, problem.question, {**problem.payload, "formal_model": model})
            res = FormalOrgan().run(composed, g, limits)
        elif key in (FORMAL, CPSAT):
            res = organs[FORMAL].run(problem, g, limits)
        else:
            res = organs[key].run(problem, g, limits)
        states.append(res.state)
        answers.append(res.answer)
    if problem.payload.get("options"):
        try:
            recs = [AuthorityRecord.from_dict(r) for r in item.get("records") or []]
            options = [Option.from_dict(o) for o in problem.payload["options"]]
            reports = {o.option_id: evaluate_gates(o, recs, remaining_budget_usd=limits.max_cost_usd,
                                                   as_of=problem.payload.get("as_of")) for o in options}
            ranking = rank_after_gates(options, reports)
        except (CortexError, KeyError, ValueError, TypeError) as exc:
            return done("abstain", note=f"options rejected: {exc}")
        states.append("OK" if ranking.get("chosen") else "NO_CHOICE")
        answers.append({"chosen_option": ranking["chosen"]} if ranking.get("chosen") else None)
    if not states:
        return done("abstain", note="no specialist for this payload")
    answer = answers[0] if len(answers) == 1 else answers
    if all(s == "OK" for s in states):
        return done("recommend", answer)
    if all(s in ("OK", "WORLD_UNVERIFIED") for s in states):
        return done("bounded_test", answer)
    return done("abstain", answer, states=states)


# ------------------------------------------------------------------ 2-3. model baselines
def model_probe() -> tuple[Any | None, str | None]:
    """One probe of the founder-selectable loopback model. Never a remote or paid endpoint."""
    try:
        from egregore.local_model import LocalModelClient, LocalModelConfig
        client = LocalModelClient(LocalModelConfig(timeout_seconds=5.0))
        client.complete("Return {\"ok\": true} as JSON.", "{}")
        return client, None
    except (OSError, urllib.error.URLError, TimeoutError, ValueError) as exc:
        return None, f"{type(exc).__name__}: {exc}"


def always_llm(item, client) -> dict:
    from .arms import always_llm as one_call
    return one_call(item, client)


def always_abstain(item) -> dict:
    return {"disposition": "abstain", "answer": None, "latency_s": 0.0, "cost_usd": 0.0}
