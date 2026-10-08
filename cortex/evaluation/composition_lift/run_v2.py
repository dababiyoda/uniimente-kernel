"""P6 v2: finish or falsify the cognitive-composition lift gate (founder directive 2026-10-07, step A).

v1 (``run.py``, ``freeze-v1.json``) measured VPL = 1 of 2 constructed families (F1 lift, F2 not lift at
n = 16). v2 adds four held-out families and keeps v1's verdict rule; nothing in v1 is re-scored.

* ``F2R`` replication of F2 (causal identification -> allocation) with 64 fresh held-out seeds (25-88),
  because 16 items could not reach the threshold (4 wins, 0 losses, p = 0.0625). Declared up front as a
  replication for power, not a re-run until success: the v1 F2 verdict stays "not lift".
* ``F3`` graph bottleneck -> allocation: buy capacity on a relay network under a budget to maximise s-t
  flow. Constituents: graph intelligence alone (``reinforce_min_cut``: cheapest edge on the current
  minimum cut, repeated) and the optimiser alone on a flow-blind model (maximise capacity bought on
  source and sink edges). Truth: min-cost-flow parametric optimum (NetworkX network simplex), a
  different algorithm from CP-SAT.
* ``F4`` Bayesian uncertainty -> value of information -> next-best test: launch, abandon or run a pilot
  first. Constituents: Bayes alone (act on the posterior mean, never pilot) and VOI alone on an
  uninformed prior (ignores the observed data). Truth: the exact Bayes-optimal action in rational
  arithmetic; realised value under the generator's true rate is reported as a secondary.
* ``F5`` NATURAL / independently derived: real M4 Weekly series (Makridakis et al.; categories Micro
  and Industry, 117 series in 39 fixed groups of three) as product demand histories. Decide four weeks
  of stocking quantities under a shared weekly capacity with asymmetric overage/underage costs; score
  the REALISED cost on the real M4 test weeks. The data and outcomes are independent of every organ and
  of this design; the decision layer (costs, capacity) is a standard newsvendor formulation we apply.
  Constituents: forecasting alone (critical-ratio quantile, scaled to capacity), optimiser alone (on
  the last observed value), and the historical-mean plan. Ablation (not a constituent): point forecast
  -> optimiser, which isolates the value of the predictive distribution.

Arms all run through ``greg.cognition.cortex.reason`` (isolated workers, independent verifiers, typed
receipts); genome families are attached in an evaluation-only registry view (the founder-pin mechanism
P4 used; no body changes). ``static_composition`` is the one recipe with the most correct (F5: feasible)
development decisions across all v2 families; ``routed_composition`` lets the geometry router choose.

Verdict (frozen, v1 rule) for F2R, F3, F4: a family counts toward VPL when routed composition decides
more held-out items correctly than the best constituent, adds no wrong answer, the one-sided exact sign
test over discordant items gives p < 0.05, and its median latency is within the 60 s chain budget.
F5 (continuous outcome): routed total realised cost below the best constituent's (lowest total among
constituents), per-group sign test p < 0.05 on lower cost, no more infeasible plans, median latency
within budget. The best constituent is chosen on held-out results (conservative toward constituents).
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from fractions import Fraction
import json
import math
from pathlib import Path
import platform
import random
import statistics
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from cortex.evaluation.composition_lift import run as V1  # noqa: E402

SUITE = HERE / "suite-v2.json"
MANIFEST = HERE / "freeze-v2.json"
CHAIN_BUDGET_S = 60.0
F5_WEEKS, F5_CAPACITY, F5_SCENARIOS = 4, 300, 10
F5_RATIOS = ((0.6, 3), (0.75, 6), (0.9, 18))         # critical ratio -> under cost (over cost 2)
SEEDS = {"F2R": (range(1, 9), range(25, 89)), "F3": (range(1, 9), range(9, 39)),
         "F4": (range(1, 9), range(9, 39)), "F5": (range(0, 9), range(9, 39))}
CONSTITUENTS = {"F2R": ("identify_alone", "optimize_on_association"),
                "F3": ("graph_alone_greedy", "optimize_flow_blind"),
                "F4": ("bayes_alone", "voi_uninformed"),
                "F5": ("forecast_alone", "optimize_alone", "historical_mean")}
ABLATIONS = {"F5": ("point_forecast_then_optimize",)}
EVAL_ATTACH = ("cognition.flow_maxflow", "cognition.flow_capacity_plan", "cognition.flow_reinforce_greedy",
               "cognition.forecast_quantile", "cognition.newsvendor_compile", "cognition.decision_preposterior",
               "cognition.probabilistic", "cognition.information", "cognition.optimization")
FROZEN_CODE = ["cortex/evaluation/composition_lift/run_v2.py", "cortex/evaluation/composition_lift/run.py",
               "greg/cognition/composition.py", "greg/cognition/cortex.py", "greg/cognition/bridge.py",
               "greg/cognition/catalog.py", "greg/cognition/contracts.py", "greg/cognition/solvers.py",
               "greg/cognition/verification.py", "greg/cognition/worker.py",
               "greg/cognition/genomes/contract.py", "greg/cognition/genomes/library.py",
               "greg/cognition/genomes/flow.py", "greg/cognition/genomes/forecasting.py",
               "greg/cognition/genomes/decision.py", "cortex/routing.py", "cortex/organs/evidence_causal.py",
               "cortex/organs/cpsat.py", "cortex/organs/formal.py", "cortex/evaluation/generators.py",
               "cortex/evaluation/data/m4_weekly.json.gz", "requirements-cortex.txt",
               "requirements-cognition.txt"]
VERDICT_RULE = ("binary families (F2R, F3, F4): routed correct > best constituent correct, routed wrong <= best "
                "constituent wrong, one-sided exact sign test p < 0.05 over discordant items, routed median "
                "latency <= 60 s. F5: routed total realised cost < best constituent total, per-group one-sided "
                "sign test p < 0.05, routed infeasible <= best constituent infeasible, median latency <= 60 s. "
                "Best constituent chosen on held-out results. VPL = families meeting their rule.")


# ------------------------------------------------------------------ registry
_REGISTRY = None


def registry():
    global _REGISTRY
    if _REGISTRY is None:
        from greg.cognition.cortex import registry_view
        _REGISTRY = registry_view()
        for cid in EVAL_ATTACH:
            _REGISTRY.set_state(cid, "ATTACHED")       # evaluation-only founder pin, in memory
    return _REGISTRY


def reason(params):
    from greg.cognition.cortex import reason as canonical
    return canonical(params, registry=registry())


def op(pid, operation, data):
    r = reason({"problem_id": pid[:128], "operation": operation, "data": data, "geometry": {"latency_limit": 20}})
    return r["output"] if r["abstention_state"] == "NONE" and isinstance(r.get("output"), dict) else None


def chain(item, recipe=None):
    c = {"question": "generated", "payload": item["payload"], "max_latency_s": CHAIN_BUDGET_S}
    if recipe:
        c["recipe"] = recipe
    started = time.perf_counter()
    r = reason({"problem_id": item["item_id"], "chain": c})
    return (r["answer"] if r["state"] == "ANSWERED" else None), time.perf_counter() - started, r


# ------------------------------------------------------------------ F2R
def f2r(seed):
    item = V1.f2(seed)
    return {**item, "item_id": f"F2R-{seed}", "family": "F2R"}


# ------------------------------------------------------------------ F3
def f3(seed):
    from greg.cognition.genomes.flow import _network, expansion_truth
    data = _network(10_000 + seed, costs=True)                # disjoint from the genome's admission seeds
    return {"item_id": f"F3-{seed}", "family": "F3", "seed": seed, "payload": {"capacity_network": data},
            "truth": {"optimum": expansion_truth(data)}}


def f3_score(item, answer):
    from greg.cognition.genomes.flow import expansion_value
    if not isinstance(answer, dict) or not isinstance(answer.get("increments"), dict):
        return "no_decision"
    value, _ = expansion_value(item["payload"]["capacity_network"], answer["increments"])
    if value is None:
        return "wrong"                                          # over budget or out of bounds
    if "flow_value" in answer and answer["flow_value"] is not None and answer["flow_value"] != value:
        return "wrong"                                          # claims a flow it does not achieve
    return "correct" if value == item["truth"]["optimum"] else "suboptimal"


def f3_flow_blind_model(net):
    """The optimiser alone, without flow structure: maximise capacity bought on source and sink edges."""
    variables, cost = {}, {}
    for i, (u, v, _) in enumerate(net["edges"]):
        if u == net["source"] or v == net["sink"]:
            variables[f"x{i}"] = [0, net["max_increment"]]
            cost[f"x{i}"] = net["unit_cost"][f"{u}->{v}"]
    return {"variables": variables,
            "constraints": [{"coefficients": cost, "op": "<=", "rhs": net["budget"], "requirement_id": "budget"}],
            "objective": {"coefficients": {k: 1 for k in variables}, "sense": "max"}}


# ------------------------------------------------------------------ F4
def _beta_binomial_exact(a, b, n, k):
    def beta(x, y):
        return Fraction(math.factorial(x - 1) * math.factorial(y - 1), math.factorial(x + y - 1))
    return math.comb(n, k) * beta(a + k, b + n - k) / beta(a, b)


def f4(seed):
    # Generator v2 (set before any arm ran; calibrated on seeds 100-199, which are neither dev nor held out):
    # the first draft made "pilot first" optimal on 2 of 30 held-out items, leaving the family no power.
    # The break-even rate is now drawn around the posterior mean, where a pilot can change the decision.
    r = random.Random(4000 + seed)
    theta = round(r.uniform(0.02, 0.30), 4)
    n_hist = r.randint(2, 25)
    s = sum(r.random() < theta for _ in range(n_hist))
    a, b = 1 + s, 1 + n_hist - s
    breakeven = a / (a + b) * r.uniform(0.6, 1.4)
    model = {"customers": 1000, "value_per_success": 20, "fixed_cost": int(round(20_000 * breakeven))}
    pilot = {"pilot_size": r.randint(20, 120), "pilot_cost": r.randint(50, 600)}
    gain = Fraction(model["customers"] * model["value_per_success"])
    now = gain * Fraction(a, a + b) - model["fixed_cost"]
    best_now = max(Fraction(0), now)
    n = pilot["pilot_size"]
    ev_pilot = sum(_beta_binomial_exact(a, b, n, k) * max(Fraction(0), gain * Fraction(a + k, a + b + n)
                                                          - model["fixed_cost"]) for k in range(n + 1)) - pilot["pilot_cost"]
    act_now = "launch" if now > 0 else "abandon"
    gap = float(ev_pilot - best_now)
    optimal = ["pilot"] if gap > 1e-6 else [act_now] if gap < -1e-6 else ["pilot", act_now]
    return {"item_id": f"F4-{seed}", "family": "F4", "seed": seed,
            "payload": {"beta_evidence": {"alpha": 1, "beta": 1, "successes": s, "failures": n_hist - s},
                        "pilot_option": pilot, "decision_model": model},
            "truth": {"optimal_actions": optimal, "theta": theta, "ev_pilot": float(ev_pilot),
                      "ev_now": float(best_now)}}


def f4_realised(item, action):
    """Expected realised value of the action under the generator's TRUE rate (secondary metric)."""
    t, p, m = item["truth"]["theta"], item["payload"]["pilot_option"], item["payload"]["decision_model"]
    gain = m["customers"] * m["value_per_success"]
    if action == "launch":
        return gain * t - m["fixed_cost"]
    if action == "abandon":
        return 0.0
    a = 1 + item["payload"]["beta_evidence"]["successes"]
    b = 1 + item["payload"]["beta_evidence"]["failures"]
    n, value = p["pilot_size"], -p["pilot_cost"]
    for k in range(n + 1):
        prob = math.comb(n, k) * t ** k * (1 - t) ** (n - k)
        if gain * (a + k) / (a + b + n) - m["fixed_cost"] > 0:
            value += prob * (gain * t - m["fixed_cost"])
    return value


def f4_score(item, answer):
    if not isinstance(answer, dict) or answer.get("action") not in ("launch", "abandon", "pilot"):
        return "no_decision"
    return "correct" if answer["action"] in item["truth"]["optimal_actions"] else "wrong"


# ------------------------------------------------------------------ F5 (natural: real M4 weekly data)
def f5_groups():
    from greg.cognition.genomes.forecasting import m4_weekly
    pool = sorted((s for s in m4_weekly()["series"] if s["category"] in ("Micro", "Industry")),
                  key=lambda s: int(s["id"][1:]))
    random.Random(20261008).shuffle(pool)
    return [pool[i:i + 3] for i in range(0, len(pool) - len(pool) % 3, 3)]


def f5(index):
    group = f5_groups()[index]
    products, actual = [], []
    for k, s in enumerate(group):
        unit = statistics.fmean(s["train"][-52:]) / 100.0
        ratio, under = F5_RATIOS[(index + k) % 3]
        products.append({"name": s["id"], "history": [round(v / unit, 4) for v in s["train"]],
                         "over_cost": 2, "under_cost": under})
        actual.append([v / unit for v in s["test"][:F5_WEEKS]])
    hindsight = 0.0
    for t in range(F5_WEEKS):                                    # capacity to the highest under-costs first
        left = F5_CAPACITY
        for k in sorted(range(len(products)), key=lambda k: -products[k]["under_cost"]):
            take = min(left, math.floor(actual[k][t]))
            left -= take
            hindsight += products[k]["under_cost"] * (actual[k][t] - take)
    return {"item_id": f"F5-g{index}", "family": "F5", "seed": index,
            "payload": {"demand_histories": products,
                        "newsvendor": {"capacity": F5_CAPACITY, "weeks": F5_WEEKS, "scenarios": F5_SCENARIOS}},
            "truth": {"actual": actual, "ratios": [F5_RATIOS[(index + k) % 3][0] for k in range(len(products))],
                      "hindsight_cost": round(hindsight, 6), "series": [s["id"] for s in group]}}


def f5_cost(item, answer):
    if not isinstance(answer, dict) or not isinstance(answer.get("plan"), list) or len(answer["plan"]) != F5_WEEKS:
        return None, "no_decision"
    products, actual = item["payload"]["demand_histories"], item["truth"]["actual"]
    cost = 0.0
    for t, week in enumerate(answer["plan"]):
        if len(week) != len(products) or any(type(q) is not int or q < 0 for q in week) or sum(week) > F5_CAPACITY:
            return None, "wrong"                                  # an infeasible plan
        for k, q in enumerate(week):
            d = actual[k][t]
            cost += products[k]["over_cost"] * max(0.0, q - d) + products[k]["under_cost"] * max(0.0, d - q)
    return round(cost, 6), "decided"


def _scale_to_capacity(week):
    total = sum(week)
    if total <= F5_CAPACITY:
        return week
    return [math.floor(q * F5_CAPACITY / total) for q in week]


def _newsvendor_week(pid, products, scenarios):
    compiled = op(f"{pid}/compile", "compile_newsvendor",
                  {"capacity": F5_CAPACITY, "products": [{"name": p["name"], "over_cost": p["over_cost"],
                                                         "under_cost": p["under_cost"], "scenarios": sc}
                                                        for p, sc in zip(products, scenarios)]})
    if compiled is None:
        return None
    solved = op(f"{pid}/optimize", "optimize", compiled["model"])
    if solved is None or solved.get("solver_status") not in ("OPTIMAL", "FEASIBLE"):
        return None
    return [solved["solution"][f"q{i}"] for i in range(len(products))]


# ------------------------------------------------------------------ arms
def run_arm(item, arm, static_recipe):
    started = time.perf_counter()
    state, stages = "constituent", None
    family, pid, payload = item["family"], item["item_id"], item["payload"]
    answer = None
    if arm == "routed_composition":
        answer, _, receipt = chain(item)
        state, stages = receipt["state"], len(receipt["stages"])
    elif arm == "static_composition":
        answer, _, receipt = chain(item, static_recipe)
        state, stages = receipt["state"], len(receipt["stages"])
    elif family == "F2R":
        out = V1.run_arm({**item, "family": "F2"}, arm)
        return {"result": out["result"], "seconds": out["seconds"], "state": out["state"], "stages": None,
                "answer": out["plan"]}
    elif arm == "graph_alone_greedy":
        answer = op(pid, "reinforce_min_cut", payload["capacity_network"])
        stages = 1
    elif arm == "optimize_flow_blind":
        out = op(pid, "optimize", f3_flow_blind_model(payload["capacity_network"]))
        stages = 1
        if out and out.get("solver_status") in ("OPTIMAL", "FEASIBLE"):
            net = payload["capacity_network"]
            inc = {f"{u}->{v}": 0 for u, v, _ in net["edges"]}
            for i, (u, v, _) in enumerate(net["edges"]):
                if f"x{i}" in out["solution"]:
                    inc[f"{u}->{v}"] = out["solution"][f"x{i}"]
            answer = {"increments": inc}
    elif arm == "bayes_alone":
        post = op(pid, "beta_update", payload["beta_evidence"])
        stages = 1
        if post:
            m = payload["decision_model"]
            launch = m["customers"] * m["value_per_success"] * post["mean"] - m["fixed_cost"] > 0
            answer = {"action": "launch" if launch else "abandon"}
    elif arm == "voi_uninformed":
        pre = op(f"{pid}/pre", "preposterior_scenarios", {"alpha": 1, "beta": 1, **payload["pilot_option"],
                                                          **payload["decision_model"]})
        stages = 1
        if pre:
            voi = op(f"{pid}/voi", "value_of_information",
                     {k: pre[k] for k in ("posterior_scenarios", "prior_best_value", "cost")})
            stages = 2
            if voi:
                answer = {"action": "pilot" if voi["acquire"] else pre["act_now"]}
    elif arm == "forecast_alone":
        products, quantiles = payload["demand_histories"], []
        stages = 0
        for k, p in enumerate(products):
            level = item["truth"]["ratios"][k]
            f = op(f"{pid}/f{k}", "forecast_distribution", {"history": p["history"], "horizon": F5_WEEKS,
                                                            "levels": [level]})
            stages += 1
            quantiles.append(None if f is None else f["quantiles"][f"{level:g}"])
        if all(q is not None for q in quantiles):
            answer = {"plan": [_scale_to_capacity([max(0, int(round(quantiles[k][t]))) for k in range(len(products))])
                               for t in range(F5_WEEKS)]}
    elif arm == "optimize_alone":
        products = payload["demand_histories"]
        week = _newsvendor_week(pid, products, [[int(round(p["history"][-1]))] * 2 for p in products])
        stages = 2
        if week is not None:
            answer = {"plan": [week] * F5_WEEKS}
    elif arm == "historical_mean":
        products = payload["demand_histories"]
        week = [int(math.floor(statistics.fmean(p["history"][-52:]))) for p in products]
        answer, stages = {"plan": [_scale_to_capacity(week)] * F5_WEEKS}, 0
    elif arm == "point_forecast_then_optimize":
        products, points = payload["demand_histories"], []
        stages = 0
        for k, p in enumerate(products):
            f = op(f"{pid}/f{k}", "forecast_distribution", {"history": p["history"], "horizon": F5_WEEKS,
                                                            "levels": [0.5]})
            stages += 1
            points.append(None if f is None else f["point"])
        if all(x is not None for x in points):
            plan = []
            for t in range(F5_WEEKS):
                week = _newsvendor_week(f"{pid}/w{t}", products, [[int(round(points[k][t]))] * 2
                                                                   for k in range(len(products))])
                stages += 2
                if week is None:
                    plan = None
                    break
                plan.append(week)
            answer = {"plan": plan} if plan else None
    else:
        raise ValueError(arm)
    seconds = time.perf_counter() - started
    row = {"seconds": round(seconds, 3), "state": state, "stages": stages}
    if family == "F2R":
        row["result"] = V1.score({**item, "family": "F2"}, answer)
        row["answer"] = (answer or {}).get("model") if isinstance(answer, dict) else None
    elif family == "F3":
        row["result"] = f3_score(item, answer)
        row["answer"] = answer
    elif family == "F4":
        row["result"] = f4_score(item, answer)
        row["answer"] = answer
        row["realised_value"] = round(f4_realised(item, answer["action"]), 4) if row["result"] != "no_decision" else None
    else:
        cost, status = f5_cost(item, answer)
        row["result"], row["cost"], row["answer"] = status, cost, answer
    return row


def arms_for(family):
    return list(CONSTITUENTS[family]) + list(ABLATIONS.get(family, ())) + ["static_composition", "routed_composition"]


# ------------------------------------------------------------------ verdict
def summarize(rows) -> dict:
    out, vpl, total = {}, 0, 0
    for family in ("F2R", "F3", "F4", "F5"):
        fr = [r for r in rows if r["family"] == family]
        if not fr:
            continue
        total += 1
        arms = arms_for(family)
        median = statistics.median(r["arms"]["routed_composition"]["seconds"] for r in fr)
        routed_states = [r["arms"]["routed_composition"]["state"] for r in fr]
        common = {"n": len(fr),
                  "median_seconds": {a: round(statistics.median(r["arms"][a]["seconds"] for r in fr), 3) for a in arms},
                  "median_stages": {a: statistics.median(r["arms"][a]["stages"] or 0 for r in fr) for a in arms},
                  "translation_failure_rate": routed_states.count("TRANSLATION_FAILED") / len(fr),
                  "composition_failure_rate": sum(s not in ("ANSWERED",) for s in routed_states) / len(fr),
                  "model_calls": 0, "money_usd": 0.0}
        if family == "F5":
            costs = {a: [r["arms"][a]["cost"] for r in fr] for a in arms}
            wrong = {a: sum(r["arms"][a]["result"] == "wrong" for r in fr) for a in arms}
            nodec = {a: sum(r["arms"][a]["result"] == "no_decision" for r in fr) for a in arms}
            totals = {a: round(sum(c for c in costs[a] if c is not None), 3) for a in arms}
            best = min(CONSTITUENTS[family], key=lambda a: (wrong[a] + nodec[a], totals[a]))
            wins = sum(1 for r in fr if r["arms"]["routed_composition"]["cost"] is not None and (
                r["arms"][best]["cost"] is None or r["arms"]["routed_composition"]["cost"] < r["arms"][best]["cost"] - 1e-9))
            losses = sum(1 for r in fr if r["arms"][best]["cost"] is not None and (
                r["arms"]["routed_composition"]["cost"] is None or r["arms"][best]["cost"] < r["arms"]["routed_composition"]["cost"] - 1e-9))
            p = V1.sign_test(wins, losses)
            lift = (nodec["routed_composition"] == 0 and totals["routed_composition"] < totals[best]
                    and wrong["routed_composition"] <= wrong[best] and p < 0.05 and median <= CHAIN_BUDGET_S)
            hindsight = round(sum(r["truth"]["hindsight_cost"] for r in fr), 3)
            out[family] = {**common, "total_realised_cost": totals, "infeasible": wrong, "no_decision": nodec,
                           "hindsight_optimal_cost": hindsight, "best_constituent": best, "routed_wins": wins,
                           "routed_losses": losses, "sign_test_p_one_sided": round(p, 6),
                           "cost_reduction_vs_best": round(1 - totals["routed_composition"] / totals[best], 4)
                           if totals[best] else None, "lift": lift}
        else:
            counts = {a: {k: sum(1 for r in fr if r["arms"][a]["result"] == k)
                          for k in ("correct", "wrong", "suboptimal", "no_decision")} for a in arms}
            best = max(CONSTITUENTS[family], key=lambda a: (counts[a]["correct"], -counts[a]["wrong"]))
            wins = sum(1 for r in fr if r["arms"]["routed_composition"]["result"] == "correct"
                       and r["arms"][best]["result"] != "correct")
            losses = sum(1 for r in fr if r["arms"][best]["result"] == "correct"
                         and r["arms"]["routed_composition"]["result"] != "correct")
            p = V1.sign_test(wins, losses)
            lift = (counts["routed_composition"]["correct"] > counts[best]["correct"]
                    and counts["routed_composition"]["wrong"] <= counts[best]["wrong"] and p < 0.05
                    and median <= CHAIN_BUDGET_S)
            extra = {}
            if family == "F4":
                extra["mean_realised_value"] = {a: round(statistics.fmean(r["arms"][a]["realised_value"] for r in fr
                                                                          if r["arms"][a]["realised_value"] is not None), 3)
                                                if any(r["arms"][a]["realised_value"] is not None for r in fr) else None
                                                for a in arms}
            out[family] = {**common, "counts": counts, "best_constituent": best, "routed_wins": wins,
                           "routed_losses": losses, "sign_test_p_one_sided": round(p, 6), "lift": lift, **extra}
        vpl += int(out[family]["lift"])
    out["VPL_v2"] = {"families_with_lift": vpl, "families": total, "rule": VERDICT_RULE}
    return out


# ------------------------------------------------------------------ suite / freeze / run
GENERATORS = {"F2R": f2r, "F3": f3, "F4": f4, "F5": f5}


def build() -> dict:
    items = []
    for family, (dev, held) in SEEDS.items():
        for partition, seeds in (("dev", dev), ("heldout", held)):
            for seed in seeds:
                items.append({**GENERATORS[family](seed), "partition": partition})
    return {"schema": "greg-composition-lift-suite/2", "items": items}


def _sha(path: Path) -> str:
    return V1._sha(path)


def inputs() -> dict:
    return {"suite": _sha(SUITE), "code": {p: _sha(ROOT / p) for p in FROZEN_CODE}, "verdict_rule": VERDICT_RULE,
            "chain_budget_s": CHAIN_BUDGET_S, "seeds": {k: [list(a), list(b)] for k, (a, b) in SEEDS.items()},
            "constituents": CONSTITUENTS, "ablations": ABLATIONS, "evaluation_attach": list(EVAL_ATTACH)}


def dev_correct(item, answer):
    if item["family"] == "F2R":
        return V1.score({**item, "family": "F2"}, answer) == "correct"
    if item["family"] == "F3":
        return f3_score(item, answer) == "correct"
    if item["family"] == "F4":
        return f4_score(item, answer) == "correct"
    return f5_cost(item, answer)[1] == "decided"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    if args.build:
        if SUITE.exists():
            raise SystemExit("refusing to overwrite the suite; create a new version")
        SUITE.write_text(json.dumps(build()) + "\n")
        return
    if args.freeze:
        if MANIFEST.exists():
            raise SystemExit("refusing to overwrite an existing freeze; create a new version")
        MANIFEST.write_text(json.dumps({"frozen_at": datetime.now(timezone.utc).isoformat(), "inputs": inputs()},
                                       indent=2) + "\n")
        return
    if json.loads(MANIFEST.read_text())["inputs"] != inputs():
        raise SystemExit("FROZEN_INPUT_CHANGED: results cannot be reported")
    if not args.out:
        raise SystemExit("--out required")
    items = json.loads(SUITE.read_text())["items"]
    dev = [i for i in items if i["partition"] == "dev"]
    heldout = [i for i in items if i["partition"] == "heldout"]
    from greg.cognition.composition import RECIPES
    dev_counts = {name: sum(1 for item in dev if dev_correct(item, chain(item, name)[0])) for name in sorted(RECIPES)}
    static_recipe = max(sorted(dev_counts), key=lambda n: dev_counts[n])
    print(json.dumps({"dev_recipe_correct": dev_counts, "static_recipe": static_recipe}), flush=True)
    rows = []
    for index, item in enumerate(heldout):
        arms = arms_for(item["family"])
        order = arms[index % len(arms):] + arms[:index % len(arms)]
        row = {"item_id": item["item_id"], "family": item["family"], "truth": item["truth"], "arms": {}}
        for arm in order:
            row["arms"][arm] = run_arm(item, arm, static_recipe)
        row["arms"] = {a: row["arms"][a] for a in arms}
        rows.append(row)
        print(json.dumps({"i": index, "item": item["item_id"],
                          "results": {a: row["arms"][a].get("cost", row["arms"][a]["result"]) for a in arms}}), flush=True)
    report = {"schema": "greg-composition-lift-results/2", "manifest_sha256": _sha(MANIFEST),
              "finished_at": datetime.now(timezone.utc).isoformat(),
              "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "platform": platform.platform(), "python": sys.version.split()[0],
              "development": {"recipe_correct": dev_counts, "static_recipe": static_recipe},
              "heldout": rows, "summary": summarize(rows),
              "limits": ["F2R, F3 and F4 are constructed to need two intelligences; they test the machinery",
                         "F5 uses real M4 data and real outcomes, but the newsvendor costs and capacity are our "
                         "decision layer; M4 Micro/Industry weekly series are demand proxies, not retail sales",
                         "one container; latency is this machine's; F5 groups share no series but weeks within "
                         "a group are not independent (the group is the unit of the sign test)"]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({"development": report["development"], "summary": report["summary"]}, indent=1))


if __name__ == "__main__":
    main()
