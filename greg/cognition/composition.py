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
When no single recipe fits, ``derive`` builds the chain by dataflow from typed stage signatures
(``PRODUCERS``): every ``$param`` root in the formal template must be produced by a stage whose input
the payload carries (for example estimate + identify -> optimize, which no recipe lists). A root
without a producer makes the composition abstain; nothing is guessed.

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

0.3 (P6 v3) adds ``forecast_then_staff``: forecast_distribution per arrival block at the critical
fractile q* = 1 - c/P of a staffing cost (c per agent, P per agent short of the Erlang requirement at the
realised rate) -> erlang_c_staffing on that rate. Because the Erlang requirement rises monotonically with
the arrival rate, staffing to the q* forecast quantile is the expected-cost minimiser under the
predictive distribution; neither intelligence can produce it alone (the forecaster has no queueing model,
the queueing model has no predictive distribution).

0.4 (P6 v5) adds ``track_then_staff``, the first recipe whose first stage is a Layer 1 (basal) genome:
kalman_track follows today's demand multiplier z_j = N_j / plan_j against a standing plan (the observed blocks
whose plan is at least half the day's mean plan; fewer than 3 such blocks abstains), and the q* = 1 - c/P
quantile of the predicted multiplier, m = position + z(q*) sqrt(position variance + r), scales the plan of the
decision block into an arrival rate -> erlang_c_staffing at that rate. The tracker has no queueing model; the
queueing model has no view of how today departs from the plan. An observed count may be null: a block with no
observation (for example the local hour that does not exist when daylight saving time starts) gives no measurement,
never a zero. The staffing plan's own numbers (block length, agent cost, shortage penalty) are checked before any
stage runs, and a critical fractile that rounds to 0 or 1 is refused: both staffing recipes share that check.
"""
from __future__ import annotations

import copy
import math
from statistics import NormalDist, fmean
import time

from .contracts import CognitionError, canonical, digest, strict_data

SCHEMA = "greg-composition/0.4"
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
                            "stages": ("compile", "optimize", "cross_check"),
                            "operations": ("compile_capacity_expansion", "optimize", "max_flow")},
    # Bayesian posterior -> preposterior analysis -> value of information -> next action.
    "bayes_then_voi": {"requires": ("beta_evidence", "pilot_option"),
                       "stages": ("posterior", "preposterior", "value_of_information", "act"),
                       "operations": ("beta_update", "preposterior_scenarios", "value_of_information")},
    # Calibrated predictive distribution -> SAA newsvendor allocation under shared capacity.
    "forecast_then_allocate": {"requires": ("demand_histories", "newsvendor"),
                               "stages": ("forecast", "compile", "optimize"),
                               "operations": ("forecast_distribution", "compile_newsvendor", "optimize")},
    # Predictive arrival distribution -> critical-fractile rate -> Erlang C staffing per block.
    "forecast_then_staff": {"requires": ("arrival_histories", "staffing"),
                            "stages": ("forecast", "staff"),
                            "operations": ("forecast_distribution", "erlang_c_staffing")},
    # Basal tracker of today's multiplier against a standing plan -> critical-fractile rate -> Erlang C staffing.
    "track_then_staff": {"requires": ("observed_today", "standing_plan", "staffing"),
                         "stages": ("track", "staff"),
                         "operations": ("kalman_track", "erlang_c_staffing")},
}
OPERATION_STAGE_LATENCY_S = 20.0


# Typed stage signatures: what each stage needs from the payload and which template root it produces.
# A chain absent from RECIPES is derived from these by dataflow (the template's ``$param`` roots).
PRODUCERS = {"estimate": ("estimate", "estimation_model"), "effect": ("identify", "causal_studies")}
STAGE_ORDER = ("estimate", "identify")


def matching(payload: dict) -> list[str]:
    """Every recipe whose required inputs the payload carries."""
    keys = set(payload)
    return [name for name, r in RECIPES.items() if set(r["requires"]) <= keys]


def route(payload: dict) -> str | None:
    """The recipe whose geometry the payload has, or None when no single recipe fits."""
    matches = matching(payload)
    return matches[0] if len(matches) == 1 else None


def _reads(recipe: str) -> set:
    """Payload keys a recipe reads (its required inputs plus every ``payload[...]``/``payload.get(...)`` key in its
    operation function), so a receipt can name what the chain never consumed."""
    import ast
    import inspect
    keys = set(RECIPES.get(recipe, {}).get("requires", ()))
    fn = OPERATION_RECIPES.get(recipe)
    if fn is not None:
        for node in ast.walk(ast.parse(inspect.getsource(fn))):
            if isinstance(node, ast.Subscript) and getattr(node.value, "id", None) == "payload" \
                    and isinstance(node.slice, ast.Constant):
                keys.add(node.slice.value)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get" \
                    and getattr(node.func.value, "id", None) == "payload" and node.args \
                    and isinstance(node.args[0], ast.Constant):
                keys.add(node.args[0].value)
    return keys


def _roots(template, out: set) -> set:
    if isinstance(template, dict) and "$param" in template:
        out.add(str(template["$param"]).split(".", 1)[0])
    elif isinstance(template, dict):
        for v in template.values():
            _roots(v, out)
    elif isinstance(template, list):
        for v in template:
            _roots(v, out)
    return out


def derive(payload: dict) -> tuple[str, ...] | None:
    """Derive a chain by dataflow when no single recipe fits: every ``$param`` root the formal template
    references must be produced by a stage whose input the payload carries. None when any root has no
    producer (the composition abstains rather than guessing)."""
    if not isinstance(payload.get("formal_template"), dict):
        return None
    roots = _roots(payload["formal_template"], set())
    if not roots or any(r not in PRODUCERS or PRODUCERS[r][1] not in payload for r in roots):
        return None
    needed = {PRODUCERS[r][0] for r in roots}
    return tuple(stage for stage in STAGE_ORDER if stage in needed) + ("optimize",)


def derived_inputs(payload: dict) -> set:
    """The payload keys a derived chain consumes: each producer stage's input and the formal template."""
    if not isinstance(payload.get("formal_template"), dict):
        return set()
    roots = _roots(payload["formal_template"], set())
    return {PRODUCERS[r][1] for r in roots if r in PRODUCERS} | {"formal_template"}


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
            "state": output.get("state"), "latency_s": round(receipt["latency"], 4),
            "counterargument": receipt.get("strongest_counterargument")}


def _operation(reason, pid: str, operation: str, data: dict, *, registry, journal, model_config) -> dict:
    """One operation-path stage on the same canonical cognition (isolated worker + independent verifier)."""
    return reason({"problem_id": pid[:128], "operation": operation, "data": data,
                   "geometry": {"latency_limit": OPERATION_STAGE_LATENCY_S}},
                  registry=registry, journal=journal, model_config=model_config)


def _op_summary(name: str, receipt: dict) -> dict:
    return {"stage": name, "receipt_id": receipt["receipt_id"], "method": receipt["method"],
            "abstention_state": receipt["abstention_state"],
            "verifier": (receipt.get("evaluator_result") or {}).get("verdict"),
            "latency_s": round(receipt["latency"], 4), "counterargument": receipt.get("strongest_counterargument")}


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
    # the optimiser's own status travels with the answer: FEASIBLE is feasible with optimality unproven
    return finish("ANSWERED", None, {"increments": increments, "flow_value": claimed,
                                     "control_points": check["output"]["cut_edges"],
                                     "solver_status": out["solver_status"],
                                     "optimality": ("proven by the solver's bound" if out["solver_status"] == "OPTIMAL"
                                                    else "feasible; optimality unproven")})


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


def _real(x, name) -> float:
    """A finite real number given as a JSON number: never a bool, a string or a non-finite float."""
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        raise CognitionError(f"{name} must be a finite number")
    return float(x)


def staffing_quantile(plan: dict) -> float:
    """Critical fractile of the staffing cost: agent cost c, shortage penalty P per missing agent (P > c).

    The fractile is rounded to 6 decimals, and a rounded fractile of 0 or 1 is refused: no normal quantile exists
    there, so a penalty barely above the agent cost or vastly above it is not a staffing plan GREG can price."""
    c, penalty = _real(plan["agent_cost"], "agent_cost"), _real(plan["shortage_penalty"], "shortage_penalty")
    if not (c > 0 and penalty > c):
        raise CognitionError("staffing needs agent_cost > 0 and shortage_penalty > agent_cost")
    level = round(1.0 - c / penalty, 6)
    if not 0.0 < level < 1.0:
        raise CognitionError(f"the critical fractile 1 - agent_cost / shortage_penalty rounds to {level:g}; it must "
                             "lie strictly between 0 and 1")
    return level


STAFF_KEYS = {"block_seconds", "mean_service_time", "target_wait", "max_wait_probability", "agent_cost",
              "shortage_penalty"}


def staffing_plan(plan, recipe: str) -> tuple[float, float]:
    """(block seconds, critical fractile) of a staffing plan, checked before any stage runs (shared by
    ``forecast_then_staff`` and ``track_then_staff``): exactly ``STAFF_KEYS``, a block length that is a finite
    number above 0, and a fractile strictly between 0 and 1. The service time, waiting target and waiting
    probability are the Erlang genome's own inputs and are checked by its contract."""
    if not isinstance(plan, dict) or set(plan) != STAFF_KEYS:
        raise CognitionError(f"{recipe} takes a staffing plan with exactly {sorted(STAFF_KEYS)}")
    seconds = _real(plan["block_seconds"], "block_seconds")
    if not seconds > 0:
        raise CognitionError("block_seconds must be above 0")
    return seconds, staffing_quantile(plan)


def _forecast_then_staff(payload, pid, kw, receipt, finish):
    from .cortex import reason
    blocks, plan = payload["arrival_histories"], payload["staffing"]
    if (not isinstance(blocks, list) or not 1 <= len(blocks) <= 48 or not isinstance(plan, dict)
            or set(plan) != STAFF_KEYS or not all(isinstance(b, dict) and set(b) == {"block", "history"}
                                                 for b in blocks)):
        raise CognitionError("forecast_then_staff takes 1-48 {block, history} arrival histories and a staffing "
                             f"plan with exactly {sorted(STAFF_KEYS)}")
    block_seconds, level = staffing_plan(plan, "forecast_then_staff")
    receipt["bindings"].append({"slot": "staffing costs -> critical fractile", "bound": level})
    agents = []
    for b in blocks:
        f = _operation(reason, f"{pid}/forecast-{b['block']}", "forecast_distribution",
                       {"history": b["history"], "horizon": 1, "levels": [level]}, **kw)
        receipt["stages"].append(_op_summary(f"forecast:{b['block']}", f))
        if not _answered(f):
            return finish("STAGE_ABSTAINED", f"forecast {b['block']}: {f['abstention_state']}")
        arrivals = f["output"]["quantiles"][f"{level:g}"][0]
        rate = arrivals / block_seconds
        if not (math.isfinite(rate) and rate > 0):
            receipt["translation_failures"].append(f"{b['block']}: forecast quantile {arrivals} is not a rate")
            return finish("TRANSLATION_FAILED", "forecast quantile cannot become an arrival rate")
        receipt["bindings"].append({"slot": f"forecast q{level:g} {b['block']} -> arrival_rate", "bound": rate})
        staffed = _operation(reason, f"{pid}/staff-{b['block']}", "erlang_c_staffing",
                             {"arrival_rate": rate, "mean_service_time": plan["mean_service_time"],
                              "target_wait": plan["target_wait"], "max_wait_probability": plan["max_wait_probability"]},
                             **kw)
        receipt["stages"].append(_op_summary(f"staff:{b['block']}", staffed))
        if not _answered(staffed):
            return finish("STAGE_ABSTAINED", f"staff {b['block']}: {staffed['abstention_state']}")
        agents.append(staffed["output"]["agents"])
    return finish("ANSWERED", None, {"agents": agents, "blocks": [b["block"] for b in blocks],
                                     "quantile_level": level})


TRACK_NULL_FRACTION = 0.5          # a block whose plan is below half the day's mean plan gives no measurement
TRACK_MIN_MEASUREMENTS = 3          # fewer usable blocks than this: the tracker abstains
TRACK_FLOOR_MULTIPLIER = 0.05       # the staffed rate never falls below 5% of the plan
TRACKER_KEYS = {"q", "r", "prior"}


def _count(x, name) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or x < 0:
        raise CognitionError(f"{name} must be a finite non-negative number")
    return float(x)


def _observed(x) -> float | None:
    """An observed block count, or null for a block with no observation (it gives no measurement, never a zero)."""
    return None if x is None else _count(x, "an observed count")


def track_measurements(payload: dict) -> tuple[dict, int, float]:
    """The kalman_track request a track_then_staff payload implies: (data, usable measurements, decision-block plan).

    z_j = N_j / plan_j for each observed block j, null where plan_j is below half the day's mean plan (or zero) and
    where the observed count is null (a block with no observation, such as the local hour that does not exist when
    daylight saving time starts: its structural zero is not demand). The standing plan covers the whole day; its
    decision block must come after every observed block (a payload holding the count it is asked to staff for is
    refused). q, r and the prior come from ``tracker``; a missing
    noise declaration is passed through so the Kalman genome's own contract abstains on it."""
    observed, plan, tracker = payload["observed_today"], payload["standing_plan"], payload.get("tracker", {})
    if not isinstance(observed, list) or not 1 <= len(observed) <= 999:
        raise CognitionError("observed_today lists 1-999 completed block counts (null: not observed), from the start "
                             "of the day")
    if (not isinstance(plan, dict) or set(plan) != {"blocks", "decision_block"} or not isinstance(plan["blocks"], list)
            or not 2 <= len(plan["blocks"]) <= 1000):
        raise CognitionError("standing_plan is {blocks: the day's planned count per block, decision_block: index}")
    block = plan["decision_block"]
    if isinstance(block, bool) or not isinstance(block, int) or not len(observed) <= block < len(plan["blocks"]):
        raise CognitionError("the decision block is a block of the plan after every observed block")
    if not isinstance(tracker, dict) or set(tracker) - TRACKER_KEYS:
        raise CognitionError(f"tracker takes only {sorted(TRACKER_KEYS)}")
    counts = [_observed(n) for n in observed]
    blocks = [_count(p, "a planned count") for p in plan["blocks"]]
    zs = plan_ratios(counts, blocks)
    data = {"dt": 1.0, "measurements": zs, **{k: tracker[k] for k in sorted(TRACKER_KEYS) if k in tracker}}
    return data, sum(z is not None for z in zs), blocks[block]


def plan_ratios(counts: list, blocks: list) -> list:
    """N_j / plan_j for the counted blocks; null where N_j is null (not observed) and where plan_j is zero or below
    half the day's mean plan."""
    floor = TRACK_NULL_FRACTION * fmean(blocks)
    return [n / p if n is not None and p > 0 and p >= floor else None for n, p in zip(counts, blocks)]


def tracked_multiplier(output: dict, r: float, level: float) -> float:
    """The q* quantile of the decision block's multiplier: position + z(q*) sqrt(position variance + r)."""
    return _quantile_multiplier(output, r, NormalDist().inv_cdf(level))


def _quantile_multiplier(output: dict, r: float, z: float) -> float:
    return output["positions"][-1] + z * math.sqrt(output["final_position_variance"] + r)


def _track_then_staff(payload, pid, kw, receipt, finish):
    from .cortex import reason
    plan = payload["staffing"]
    block_seconds, level = staffing_plan(plan, "track_then_staff")
    data, usable, planned = track_measurements(payload)
    receipt["bindings"].append({"slot": "staffing costs -> critical fractile", "bound": level})
    if usable < TRACK_MIN_MEASUREMENTS:
        return finish("STAGE_ABSTAINED", f"track: {usable} usable measurements, at least {TRACK_MIN_MEASUREMENTS} "
                                         f"required (a block planned below {TRACK_NULL_FRACTION} x the day's mean "
                                         "gives none)")
    tracked = _operation(reason, f"{pid}/track", "kalman_track", data, **kw)
    receipt["stages"].append(_op_summary("track", tracked))
    if not _answered(tracked):
        return finish("STAGE_ABSTAINED", f"track: {tracked['abstention_state']}")
    out = tracked["output"]
    z = multiplier = rate = math.nan
    try:
        z = NormalDist().inv_cdf(level)
        multiplier = _quantile_multiplier(out, float(data["r"]), z)
        rate = planned * max(multiplier, TRACK_FLOOR_MULTIPLIER) / block_seconds
    except (KeyError, TypeError, ValueError, IndexError, OverflowError) as exc:
        multiplier = rate = math.nan
        receipt["translation_failures"].append(f"tracker output cannot become a multiplier: {type(exc).__name__}")
    receipt["bindings"].append({"slot": f"kalman position, variance -> q{level:g} multiplier", "bound": multiplier,
                                "z": z, "r": data.get("r")})
    if not (math.isfinite(rate) and rate > 0):
        receipt["translation_failures"].append(f"multiplier {multiplier} x plan {planned} is not an arrival rate")
        return finish("TRANSLATION_FAILED", "the tracked multiplier cannot become an arrival rate")
    receipt["bindings"].append({"slot": f"multiplier x plan[{payload['standing_plan']['decision_block']}] -> "
                                        "arrival_rate", "bound": rate, "floor": TRACK_FLOOR_MULTIPLIER})
    staffed = _operation(reason, f"{pid}/staff", "erlang_c_staffing",
                         {"arrival_rate": rate, "mean_service_time": plan["mean_service_time"],
                          "target_wait": plan["target_wait"], "max_wait_probability": plan["max_wait_probability"]},
                         **kw)
    receipt["stages"].append(_op_summary("staff", staffed))
    if not _answered(staffed):
        return finish("STAGE_ABSTAINED", f"staff: {staffed['abstention_state']}")
    return finish("ANSWERED", None, {"agents": staffed["output"]["agents"],
                                     "block": payload["standing_plan"]["decision_block"], "quantile_level": level,
                                     "multiplier": multiplier, "arrival_rate": rate})


OPERATION_RECIPES = {"graph_then_allocate": _graph_then_allocate, "bayes_then_voi": _bayes_then_voi,
                     "forecast_then_allocate": _forecast_then_allocate, "forecast_then_staff": _forecast_then_staff,
                     "track_then_staff": _track_then_staff}


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
    stages = RECIPES[recipe]["stages"] if recipe else None
    ambiguous = [] if chain.get("recipe") else matching(payload)
    # derive only when the derived chain consumes every input of every recipe that matched: otherwise the
    # geometry is ambiguous and the composition refuses rather than silently dropping a recipe's inputs
    # (review of #179, M8). A three-stage estimate+identify chain matches both template recipes and consumes both.
    if recipe is None and not chain.get("recipe") and (derived := derive(payload)) is not None \
            and all(set(RECIPES[m]["requires"]) <= derived_inputs(payload) for m in ambiguous):
        stages, recipe, routed_by = derived, "derived:" + "+".join(derived), "dataflow"
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
        if len(ambiguous) > 1:
            return finish("NO_RECIPE", f"ambiguous geometry: recipes {ambiguous} all match; supply one recipe")
        return finish("NO_RECIPE", "no single composition recipe matches this geometry")
    requires = RECIPES[recipe]["requires"] if recipe in RECIPES else \
        tuple(PRODUCERS[r][1] for r in PRODUCERS if PRODUCERS[r][0] in stages) + ("formal_template",)
    missing = [k for k in requires if k not in payload]
    if missing:
        return finish("NO_RECIPE", f"recipe {recipe} needs {missing}")
    receipt["chain"] = list(stages)
    consumed = _reads(recipe) if recipe in RECIPES else set(requires) | {"declared"}
    receipt["unconsumed_inputs"] = sorted(k for k in payload if k not in consumed | {"declared"})
    declared = payload.get("declared", DECL)
    values = {}
    kw = dict(registry=registry, journal=journal, model_config=model_config)
    if recipe in OPERATION_RECIPES:
        return OPERATION_RECIPES[recipe](payload, pid, kw, receipt, finish)
    if "estimate" in stages:
        first = _stage(reason, f"{pid}/estimate", question,
                       {"estimation_model": payload["estimation_model"], "declared": declared}, **kw)
        receipt["stages"].append(_summary("estimate", first))
        if first["abstention_state"] != "NONE" or not isinstance((first.get("output") or {}).get("answer"), dict):
            return finish("STAGE_ABSTAINED", f"estimate: {first['abstention_state']}")
        values["estimate"] = first["output"]["answer"]
    if "identify" in stages:
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
