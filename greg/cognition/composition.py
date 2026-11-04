"""P6 cognitive composition: typed chains of cortex intelligences, routed by problem geometry.

A composite problem names what it knows (an estimation model, causal studies, a formal model with
typed parameter slots). The router recognises which recipe the geometry calls for; each stage is an
ordinary cortex request through ``cognition.reason`` (the same bounded, network-isolated worker,
verifier and receipt), and a typed translation step carries one stage's verified answer into the next
stage's model. Nothing here is a new solver or a new authority:

    composite problem
      -> route(payload)                       geometry -> recipe (or none: no composition)
      -> stage 1..k (cortex receipts)          estimate / identify
      -> translate                             {"$param": "<stage>.<field>"} -> number (typed,
                                               rounded as declared; any failure is recorded)
      -> final stage (cortex receipt)          optimize, certified by the cortex as usual
      -> composition receipt                   stage receipt ids, bindings, failures, latency

A stage that abstains, a translation that fails, or a chain that exceeds its latency budget makes
the composition abstain; the receipt says which. ``recipe`` in the request pins one chain (a static
composition); without it the geometry router chooses.

Recipes live in ``RECIPES``; each declares the payload keys that identify its geometry. A recipe is
eligible only when exactly its geometry is present, so two recipes never claim the same problem.

0.2 (P6 v2, INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION) adds three recipes whose stages run on
the operation path of the same ``cognition.reason`` (isolated worker, independent verifier,
CognitiveReceipt per stage; families from the executable IntelligenceGenome library):

* ``graph_then_allocate``    compile_capacity_expansion -> optimize (CP-SAT) -> max_flow on the
                             reinforced network, an independent graph intelligence that must reproduce
                             the optimiser's claimed flow (a cross-intelligence translation check);
* ``bayes_then_voi``         beta_update -> preposterior_scenarios -> value_of_information -> act
                             (pilot, launch or abandon: next-best test selection);
* ``forecast_then_allocate`` forecast_distribution per product -> compile_newsvendor per week ->
                             optimize (sample-average approximation under a shared capacity).

v1's two recipes execute exactly as before.
"""
from __future__ import annotations

import copy
import math
import time

from .contracts import CognitionError, canonical, digest, strict_data

SCHEMA = "greg-composition/0.2"
MAX_REQUEST_BYTES = 192 * 1024
DECL = {"consequence_class": "read_only", "reversibility": "reversible"}

RECIPES = {
    # Fermi estimate -> robust optimisation: the optimiser's demand slot takes an estimate quantile.
    "estimate_then_optimize": {"requires": ("estimation_model", "formal_template"),
                               "stages": ("estimate", "optimize")},
    # Causal identification of each intervention -> allocation over the identified effects.
    "identify_then_optimize": {"requires": ("causal_studies", "formal_template"),
                               "stages": ("identify", "optimize")},
    # Graph bottleneck structure -> integer allocation; graph intelligence re-checks the answer.
    "graph_then_allocate": {"requires": ("capacity_network",),
                            "stages": ("compile", "optimize", "cross_check")},
    # Bayesian posterior -> preposterior analysis -> value of information -> next action.
    "bayes_then_voi": {"requires": ("beta_evidence", "pilot_option"),
                       "stages": ("posterior", "preposterior", "value_of_information", "act")},
    # Calibrated predictive distribution -> SAA newsvendor allocation under shared capacity.
    "forecast_then_allocate": {"requires": ("demand_histories", "newsvendor"),
                               "stages": ("forecast", "compile", "optimize")},
}
OPERATION_STAGE_LATENCY_S = 20.0


def route(payload: dict) -> str | None:
    """The recipe whose geometry the payload has, or None when no single recipe fits."""
    keys = set(payload)
    matches = [name for name, r in RECIPES.items() if set(r["requires"]) <= keys]
    return matches[0] if len(matches) == 1 else None


class TranslationError(CognitionError):
    """A stage's answer could not be carried into the next stage's model."""


def _lookup(values: dict, path: str):
    node = values
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            raise TranslationError(f"no value at {path}")
        node = node[part]
    if isinstance(node, bool) or not isinstance(node, (int, float)) or not math.isfinite(node):
        raise TranslationError(f"{path} is not a finite number")
    return float(node)


def substitute(template, values: dict, bindings: list):
    """Replace every {"$param": path, "scale": s, "round": r} node with a number."""
    if isinstance(template, dict) and "$param" in template:
        if set(template) - {"$param", "scale", "round"}:
            raise TranslationError("a parameter slot takes $param, scale and round only")
        value = _lookup(values, template["$param"]) * float(template.get("scale", 1))
        rounding = template.get("round", "ceil")
        if rounding == "ceil":
            out = int(math.ceil(value - 1e-9))
        elif rounding == "floor":
            out = int(math.floor(value + 1e-9))
        elif rounding == "nearest":
            out = int(round(value))
        else:
            raise TranslationError(f"unknown rounding {rounding!r}")
        bindings.append({"slot": template["$param"], "value": value, "scale": template.get("scale", 1),
                         "round": rounding, "bound": out})
        return out
    if isinstance(template, dict):
        return {k: substitute(v, values, bindings) for k, v in template.items()}
    if isinstance(template, list):
        return [substitute(v, values, bindings) for v in template]
    return template


def _stage(reason, pid: str, question: str, payload: dict, *, registry, journal, model_config) -> dict:
    receipt = reason({"problem_id": pid[:128], "problem": {"question": question, "payload": payload}},
                     registry=registry, journal=journal, model_config=model_config)
    return receipt


def _summary(name: str, receipt: dict) -> dict:
    output = receipt.get("output") or {}
    return {"stage": name, "receipt_id": receipt["receipt_id"], "method": receipt["method"],
            "abstention_state": receipt["abstention_state"], "answer": output.get("answer"),
            "state": output.get("state"), "latency_s": round(receipt["latency"], 4)}


def _operation(reason, pid: str, operation: str, data: dict, *, registry, journal, model_config) -> dict:
    """One operation-path stage on the same canonical cognition (isolated worker + independent verifier)."""
    return reason({"problem_id": pid[:128], "operation": operation, "data": data,
                   "geometry": {"latency_limit": OPERATION_STAGE_LATENCY_S}},
                  registry=registry, journal=journal, model_config=model_config)


def _op_summary(name: str, receipt: dict) -> dict:
    return {"stage": name, "receipt_id": receipt["receipt_id"], "method": receipt["method"],
            "abstention_state": receipt["abstention_state"],
            "verifier": (receipt.get("evaluator_result") or {}).get("verdict"),
            "latency_s": round(receipt["latency"], 4)}


def _answered(receipt: dict) -> bool:
    return receipt["abstention_state"] == "NONE" and isinstance(receipt.get("output"), dict)


def _graph_then_allocate(payload, pid, kw, receipt, finish):
    from .cortex import reason
    network = payload["capacity_network"]
    compiled = _operation(reason, f"{pid}/compile", "compile_capacity_expansion", network, **kw)
    receipt["stages"].append(_op_summary("compile", compiled))
    if not _answered(compiled):
        return finish("STAGE_ABSTAINED", f"compile: {compiled['abstention_state']}")
    model, decode = compiled["output"]["model"], compiled["output"]["decode"]
    solved = _operation(reason, f"{pid}/optimize", "optimize", model, **kw)
    receipt["stages"].append(_op_summary("optimize", solved))
    out = solved.get("output") or {}
    if not _answered(solved) or out.get("solver_status") not in ("OPTIMAL", "FEASIBLE"):
        return finish("STAGE_ABSTAINED", f"optimize: {solved['abstention_state']} {out.get('solver_status')}")
    increments = {decode[x]: v for x, v in out["solution"].items() if x in decode}
    receipt["bindings"].append({"slot": "optimize.solution -> increments", "bound": len(increments)})
    reinforced = {"edges": [[u, v, c + increments.get(f"{u}->{v}", 0)] for u, v, c in network["edges"]],
                  "source": network["source"], "sink": network["sink"]}
    check = _operation(reason, f"{pid}/cross-check", "max_flow", reinforced, **kw)
    receipt["stages"].append(_op_summary("cross_check", check))
    if not _answered(check):
        return finish("STAGE_ABSTAINED", f"cross_check: {check['abstention_state']}")
    claimed = int(round(out["objective_value"]))
    if check["output"]["value"] != claimed:
        receipt["translation_failures"].append(f"optimiser claimed flow {claimed}; max-flow organ found "
                                               f"{check['output']['value']}")
        return finish("TRANSLATION_FAILED", "cross-intelligence flow check disagreed")
    return finish("ANSWERED", None, {"increments": increments, "flow_value": claimed,
                                     "control_points": check["output"]["cut_edges"]})


def _bayes_then_voi(payload, pid, kw, receipt, finish):
    from .cortex import reason
    evidence, pilot = payload["beta_evidence"], payload["pilot_option"]
    model = payload.get("decision_model")
    if not isinstance(model, dict):
        raise CognitionError("bayes_then_voi needs a decision_model (customers, value_per_success, fixed_cost)")
    posterior = _operation(reason, f"{pid}/posterior", "beta_update", evidence, **kw)
    receipt["stages"].append(_op_summary("posterior", posterior))
    if not _answered(posterior):
        return finish("STAGE_ABSTAINED", f"posterior: {posterior['abstention_state']}")
    a, b = posterior["output"]["alpha"], posterior["output"]["beta"]
    receipt["bindings"].append({"slot": "posterior.alpha,beta -> preposterior", "bound": [a, b]})
    pre = _operation(reason, f"{pid}/preposterior", "preposterior_scenarios",
                     {"alpha": a, "beta": b, **pilot, **model}, **kw)
    receipt["stages"].append(_op_summary("preposterior", pre))
    if not _answered(pre):
        return finish("STAGE_ABSTAINED", f"preposterior: {pre['abstention_state']}")
    scenarios = pre["output"]
    voi = _operation(reason, f"{pid}/voi", "value_of_information",
                     {k: scenarios[k] for k in ("posterior_scenarios", "prior_best_value", "cost")}, **kw)
    receipt["stages"].append(_op_summary("value_of_information", voi))
    if not _answered(voi):
        return finish("STAGE_ABSTAINED", f"value_of_information: {voi['abstention_state']}")
    action = "pilot" if voi["output"]["acquire"] else scenarios["act_now"]
    return finish("ANSWERED", None, {"action": action, "net_value_of_information": voi["output"]["net_value"],
                                     "posterior_mean": posterior["output"]["mean"]})


def _forecast_then_allocate(payload, pid, kw, receipt, finish):
    from .cortex import reason
    products, plan = payload["demand_histories"], payload["newsvendor"]
    if not isinstance(products, list) or not 1 <= len(products) <= 3 or not isinstance(plan, dict):
        raise CognitionError("forecast_then_allocate takes 1-3 demand histories and a newsvendor plan")
    weeks, count = int(plan.get("weeks", 1)), int(plan.get("scenarios", 10))
    if not 1 <= weeks <= 8 or not 2 <= count <= 10:
        raise CognitionError("1-8 weeks and 2-10 scenarios")
    levels = [round((j + 0.5) / count, 6) for j in range(count)]
    paths = []
    for p in products:
        f = _operation(reason, f"{pid}/forecast-{p['name']}", "forecast_distribution",
                       {"history": p["history"], "horizon": weeks, "levels": levels}, **kw)
        receipt["stages"].append(_op_summary(f"forecast:{p['name']}", f))
        if not _answered(f):
            return finish("STAGE_ABSTAINED", f"forecast {p['name']}: {f['abstention_state']}")
        paths.append(f["output"]["quantiles"])
    allocation = []
    for t in range(weeks):
        data = {"capacity": plan["capacity"],
                "products": [{"name": p["name"], "over_cost": p["over_cost"], "under_cost": p["under_cost"],
                              "scenarios": [paths[i][f"{q:g}"][t] for q in levels]}
                             for i, p in enumerate(products)]}
        receipt["bindings"].append({"slot": f"forecast quantiles week {t + 1} -> scenarios", "bound": count})
        compiled = _operation(reason, f"{pid}/compile-{t}", "compile_newsvendor", data, **kw)
        receipt["stages"].append(_op_summary(f"compile:{t + 1}", compiled))
        if not _answered(compiled):
            return finish("STAGE_ABSTAINED", f"compile week {t + 1}: {compiled['abstention_state']}")
        solved = _operation(reason, f"{pid}/optimize-{t}", "optimize", compiled["output"]["model"], **kw)
        receipt["stages"].append(_op_summary(f"optimize:{t + 1}", solved))
        out = solved.get("output") or {}
        if not _answered(solved) or out.get("solver_status") not in ("OPTIMAL", "FEASIBLE"):
            return finish("STAGE_ABSTAINED", f"optimize week {t + 1}: {out.get('solver_status')}")
        allocation.append([out["solution"][f"q{i}"] for i in range(len(products))])
    return finish("ANSWERED", None, {"plan": allocation, "products": [p["name"] for p in products]})


OPERATION_RECIPES = {"graph_then_allocate": _graph_then_allocate, "bayes_then_voi": _bayes_then_voi,
                     "forecast_then_allocate": _forecast_then_allocate}


def validate(params) -> tuple[str, dict]:
    if not isinstance(params, dict) or set(params) - {"problem_id", "chain"}:
        raise CognitionError("a composite request takes problem_id and chain")
    strict_data(params)
    if len(canonical(params).encode()) > MAX_REQUEST_BYTES:
        raise CognitionError("composite request exceeds 192 KiB")
    chain = params.get("chain")
    if not isinstance(chain, dict) or set(chain) - {"question", "payload", "recipe", "max_latency_s"} or \
            not isinstance(chain.get("payload"), dict):
        raise CognitionError("chain takes question, payload, optional recipe and max_latency_s")
    recipe = chain.get("recipe")
    if recipe is not None and recipe not in RECIPES:
        raise CognitionError(f"unknown recipe {recipe!r}")
    pid = params.get("problem_id")
    if not isinstance(pid, str) or not 1 <= len(pid) <= 96:
        raise CognitionError("bounded problem identity required")
    return pid, chain


def run(params, *, registry, journal=None, model_config=None) -> dict:
    from .cortex import reason
    started = time.monotonic()
    pid, chain = validate(params)
    payload = chain["payload"]
    question = str(chain.get("question", "")) or pid
    budget = float(chain.get("max_latency_s", 60.0))
    recipe = chain.get("recipe") or route(payload)
    routed_by = "fixed" if chain.get("recipe") else "geometry"
    receipt = {"schema": SCHEMA, "problem_id": pid, "input_digest": digest(params), "recipe": recipe,
               "routed_by": routed_by, "stages": [], "bindings": [], "translation_failures": [],
               "answer": None, "state": "ABSTAIN", "reason": None, "authority_created": False,
               "execution_authority": "none"}

    def finish(state, why=None, answer=None):
        receipt.update(state=state, reason=why, answer=answer,
                       latency_s=round(time.monotonic() - started, 4))
        if state == "ANSWERED" and receipt["latency_s"] > budget:
            receipt.update(state="TIMEOUT", reason=f"chain took {receipt['latency_s']}s of {budget}s", answer=None)
        receipt["receipt_id"] = digest({k: v for k, v in receipt.items() if k != "receipt_id"})
        return receipt

    if recipe is None:
        return finish("NO_RECIPE", "no single composition recipe matches this geometry")
    missing = [k for k in RECIPES[recipe]["requires"] if k not in payload]
    if missing:
        return finish("NO_RECIPE", f"recipe {recipe} needs {missing}")
    declared = payload.get("declared", DECL)
    values = {}
    kw = dict(registry=registry, journal=journal, model_config=model_config)
    if recipe in OPERATION_RECIPES:
        return OPERATION_RECIPES[recipe](payload, pid, kw, receipt, finish)
    if recipe == "estimate_then_optimize":
        first = _stage(reason, f"{pid}/estimate", question,
                       {"estimation_model": payload["estimation_model"], "declared": declared}, **kw)
        receipt["stages"].append(_summary("estimate", first))
        if first["abstention_state"] != "NONE" or not isinstance((first.get("output") or {}).get("answer"), dict):
            return finish("STAGE_ABSTAINED", f"estimate: {first['abstention_state']}")
        values["estimate"] = first["output"]["answer"]
    else:
        studies = payload["causal_studies"]
        if not isinstance(studies, dict) or not 1 <= len(studies) <= 8:
            raise CognitionError("causal_studies maps 1-8 named studies")
        values["effect"] = {}
        for name, study in sorted(studies.items()):
            if not isinstance(study, dict):
                raise CognitionError("each causal study is an object")
            result = _stage(reason, f"{pid}/identify-{name}", question, {**study, "declared": declared}, **kw)
            receipt["stages"].append(_summary(f"identify:{name}", result))
            answer = (result.get("output") or {}).get("answer")
            if result["abstention_state"] not in ("NONE", "WORLD_UNVERIFIED") or not isinstance(answer, dict) \
                    or "effect" not in answer:
                return finish("STAGE_ABSTAINED", f"identify {name}: {result['abstention_state']}")
            values["effect"][name] = answer["effect"]
    try:
        model = substitute(copy.deepcopy(payload["formal_template"]), values, receipt["bindings"])
    except TranslationError as exc:
        receipt["translation_failures"].append(str(exc))
        return finish("TRANSLATION_FAILED", str(exc))
    final = _stage(reason, f"{pid}/optimize", question, {"formal_model": model, "declared": declared}, **kw)
    receipt["stages"].append(_summary("optimize", final))
    answer = (final.get("output") or {}).get("answer")
    if final["abstention_state"] != "NONE" or not isinstance(answer, dict):
        return finish("STAGE_ABSTAINED", f"optimize: {final['abstention_state']}")
    return finish("ANSWERED", None, answer)
