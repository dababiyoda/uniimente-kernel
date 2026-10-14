"""P6 v3: a natural composition family on real call-centre data (founder directive 2026-10-07, step A).

v1 measured VPL 1 of 2 constructed families. v2 measured 3 of 4: three constructed families lifted, and
the one natural family (F5, real M4 weekly demand -> newsvendor) did not. Nothing earlier is re-scored.
The P6 v2 diagnosis behind this design is recorded in docs/evidence/greg-composition-lift/2026-10-13-v3/:
F5's shared capacity bound the composed plan in 113 of 120 held-out weeks (the optimiser-alone plan in
108; realised demand exceeded capacity in 83), leaving composition little to improve, and the sign test
over 30 groups had little power (results-v2.json, recomputed).

F6, NATURAL: staff a real call centre. The data are the 5-minute call counts of a large North American
commercial bank (fpp3 ``bank_calls``; 164 weekdays, March-October 2003), aggregated to 28 half-hour
blocks per day (``cortex/evaluation/data/bank_calls_halfhour.json.gz``). Each held-out item is one day.
Using only the days before it, choose agents for each block; score the plan on the calls that actually
arrived. Cost per block = c * agents + P * max(0, required - agents), where ``required`` is the Erlang C
requirement at the REALISED arrival rate for an 80/20-style service target (P(wait > 20 s) <= 0.2, mean
handle time 240 s). The data and outcomes are independent of every intelligence and of this design.
The decision layer (handle time, target, c = 1, P in {3, 10, 30} rotated by day) is a standard workforce-
management formulation we declare here, before any held-out arm runs.

Arms (all through ``greg.cognition.cortex.reason``; genome families attached in an evaluation-only
registry view):

* ``erlang_alone``     constituent: the queueing intelligence on the latest observed count (it has no
                        predictive distribution of its own).
* ``forecast_alone``   constituent: the forecasting intelligence's q* quantile, staffed by the 85%-occupancy
                        rule a forecaster without a queueing model would use.
* ``median_forecast_then_staff``   ablation: the median forecast -> Erlang C (isolates the value of the
                        predictive distribution).
* ``weekly_mean_then_staff``       ablation: the mean of the last five weekdays -> Erlang C (the common
                        practitioner pipeline; reported, and named in the verdict text whether or not lift
                        holds against it).
* ``static_composition`` / ``routed_composition``: recipe ``forecast_then_staff`` (q* = 1 - c/P quantile
  -> Erlang C). The router here matches geometry keys, so within one family routed equals static; v3
  reports both and claims nothing about routing.

Verdict (frozen): F6 counts toward VPL when routed composition has no no-decision, its total cost over
the 90 held-out days is below the best constituent's (constituent with fewest wrong + no-decision, then
lowest total, chosen on held-out results: conservative toward constituents), it has no more infeasible
plans, the one-sided exact sign test over days (cost lower by more than 1e-9 = win) gives p < 0.05, and
its median latency per day is within the 120 s chain budget. A one-sided Wilcoxon signed-rank p and the
comparisons with both ablations are reported alongside, not as part of the rule.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from functools import lru_cache
import gzip
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from cortex.evaluation.composition_lift import run as V1  # noqa: E402

SUITE = HERE / "suite-v3.json"
MANIFEST = HERE / "freeze-v3.json"
DATA = ROOT / "cortex/evaluation/data/bank_calls_halfhour.json.gz"
CHAIN_BUDGET_S = 120.0
STAFFING = {"block_seconds": 1800.0, "mean_service_time": 240.0, "target_wait": 20.0,
            "max_wait_probability": 0.2, "agent_cost": 1.0}
PENALTIES = (3.0, 10.0, 30.0)                         # shortage penalty per missing agent, rotated by day
OCCUPANCY_RULE = 0.85
WEEK = 5
SEEDS = {"F6": (range(60, 74), range(74, 164))}       # day indices: >= 60 days of history each
CONSTITUENTS = {"F6": ("erlang_alone", "forecast_alone")}
ABLATIONS = {"F6": ("median_forecast_then_staff", "weekly_mean_then_staff")}
EVAL_ATTACH = ("cognition.forecast_quantile", "cognition.queue_erlang")
ENTRY_POINTS = ("cortex/evaluation/composition_lift/run_v3.py", "greg/cognition/worker.py")
FROZEN_EXTRA = ("cortex/evaluation/data/bank_calls_halfhour.json.gz", "cortex/evaluation/data/build_bank_calls.py",
                "tools/offline_test.py", "requirements-cortex.txt", "requirements-cognition.txt")


def code_closure() -> list[str]:
    """Every repository file the run can execute, hashed by the freeze (``cortex.evaluation.closure``): the
    import closure of the runner and the isolated worker, all of ``greg/cognition`` (its genome library imports
    modules by name), the sandbox filter, the data, its build script and the dependency pins. v1/v2 hashed a
    hand-picked list that missed modules on the path (``greg/capabilities.py`` among them)."""
    from cortex.evaluation.closure import code_closure as closure
    return closure(ENTRY_POINTS, packages=("greg/cognition",), extra=FROZEN_EXTRA, root=ROOT)


VERDICT_RULE = ("F6 (natural, continuous cost): routed no-decision = 0, routed total realised cost < best "
                "constituent total, routed infeasible <= best constituent infeasible, one-sided exact sign "
                "test over held-out days p < 0.05, routed median latency <= 120 s. Best constituent chosen on "
                "held-out results (fewest wrong + no-decision, then lowest total). Wilcoxon and ablation "
                "comparisons reported, not part of the rule. VPL = families meeting their rule.")


# ------------------------------------------------------------------ registry and canonical calls
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
    c = {"question": "staff the call centre for the next day", "payload": item["payload"],
         "max_latency_s": CHAIN_BUDGET_S}
    if recipe:
        c["recipe"] = recipe
    started = time.perf_counter()
    r = reason({"problem_id": item["item_id"], "chain": c})
    return (r["answer"] if r["state"] == "ANSWERED" else None), time.perf_counter() - started, r


# ------------------------------------------------------------------ F6 data, items and truth
@lru_cache(maxsize=1)
def bank_calls() -> dict:
    with gzip.open(DATA, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def requirement(arrivals: int) -> int:
    """Evaluation-side Erlang C requirement at the realised rate (SciPy Poisson path, not the genome's solve)."""
    if arrivals <= 0:
        return 0
    from greg.cognition.genomes.solvers_b import erlang_truth
    return erlang_truth({"arrival_rate": arrivals / STAFFING["block_seconds"],
                         "mean_service_time": STAFFING["mean_service_time"], "target_wait": STAFFING["target_wait"],
                         "max_wait_probability": STAFFING["max_wait_probability"]})


def f6(day: int) -> dict:
    data = bank_calls()
    days, starts = data["days"], data["block_starts"]
    if not SEEDS["F6"][0].start <= day < len(days):
        raise ValueError("day index out of the declared range")
    history = [[d["blocks"][b] for d in days[:day]] for b in range(len(starts))]
    actual = days[day]["blocks"]
    required = [requirement(n) for n in actual]
    penalty = PENALTIES[day % len(PENALTIES)]
    return {"item_id": f"F6-{day}", "family": "F6", "seed": day,
            "payload": {"arrival_histories": [{"block": starts[b], "history": history[b]} for b in range(len(starts))],
                        "staffing": {**STAFFING, "shortage_penalty": penalty}},
            "truth": {"date": days[day]["date"], "actual": actual, "required": required,
                      "hindsight_cost": STAFFING["agent_cost"] * sum(required)}}


def f6_cost(item, answer):
    """(realised cost, outcome): outcome is decided, wrong (infeasible plan) or no_decision."""
    if not isinstance(answer, dict) or answer.get("agents") is None:
        return None, "no_decision"
    agents = answer["agents"]
    required = item["truth"]["required"]
    if (not isinstance(agents, list) or len(agents) != len(required)
            or not all(type(n) is int and 0 <= n <= 40_000 for n in agents)):
        return None, "wrong"
    c, penalty = STAFFING["agent_cost"], item["payload"]["staffing"]["shortage_penalty"]
    return sum(c * n + penalty * max(0, r - n) for n, r in zip(agents, required)), "decided"


def f6_shortage(item, answer):
    agents = (answer or {}).get("agents") if isinstance(answer, dict) else None
    if not isinstance(agents, list) or len(agents) != len(item["truth"]["required"]):
        return None
    gaps = [max(0, r - n) for n, r in zip(agents, item["truth"]["required"])]
    return {"short_blocks": sum(g > 0 for g in gaps), "agents_short": sum(gaps), "agents_paid": sum(agents)}


# ------------------------------------------------------------------ arms
def _erlang(pid, arrivals, plan):
    out = op(pid, "erlang_c_staffing", {"arrival_rate": arrivals / plan["block_seconds"],
                                        "mean_service_time": plan["mean_service_time"],
                                        "target_wait": plan["target_wait"],
                                        "max_wait_probability": plan["max_wait_probability"]})
    return None if out is None else out["agents"]


def _forecast(pid, history, level):
    out = op(pid, "forecast_distribution", {"history": history, "horizon": 1, "levels": [level]})
    return None if out is None else out["quantiles"][f"{level:g}"][0]


def run_arm(item, arm, static_recipe):
    from greg.cognition.composition import staffing_quantile
    started, stages, state, answer = time.perf_counter(), 0, "ANSWERED", None
    plan, blocks = item["payload"]["staffing"], item["payload"]["arrival_histories"]
    if arm in ("static_composition", "routed_composition"):
        answer, seconds, r = chain(item, static_recipe if arm == "static_composition" else None)
        stages, state = len(r.get("stages", [])), r["state"]
    else:
        agents = []
        level = staffing_quantile(plan)
        for b in blocks:
            pid = f"{item['item_id']}/{arm}/{b['block']}"
            history = b["history"]
            if arm == "erlang_alone":
                n = _erlang(pid, history[-1], plan)
                stages += 1
            elif arm == "weekly_mean_then_staff":
                n = _erlang(pid, statistics.fmean(history[-WEEK:]), plan)
                stages += 1
            elif arm == "median_forecast_then_staff":
                q = _forecast(pid + "/f", history, 0.5)
                n = None if q is None else _erlang(pid + "/s", q, plan)
                stages += 2
            elif arm == "forecast_alone":
                q = _forecast(pid, history, level)
                n = None if q is None else math.ceil(q / plan["block_seconds"] * plan["mean_service_time"]
                                                     / OCCUPANCY_RULE)
                stages += 1
            else:
                raise ValueError(f"unknown arm {arm}")
            if n is None:
                state = "STAGE_ABSTAINED"
                agents = None
                break
            agents.append(n)
        answer = None if agents is None else {"agents": agents}
        seconds = time.perf_counter() - started
    cost, outcome = f6_cost(item, answer)
    return {"result": outcome, "cost": cost, "seconds": round(seconds, 4), "stages": stages, "state": state,
            "shortage": f6_shortage(item, answer), "answer": answer}


def arms_for(family):
    return list(CONSTITUENTS[family]) + list(ABLATIONS.get(family, ())) + ["static_composition", "routed_composition"]


# ------------------------------------------------------------------ verdict
def _paired(rows, a, b):
    wins = sum(1 for r in rows if r["arms"][a]["cost"] is not None and (
        r["arms"][b]["cost"] is None or r["arms"][a]["cost"] < r["arms"][b]["cost"] - 1e-9))
    losses = sum(1 for r in rows if r["arms"][b]["cost"] is not None and (
        r["arms"][a]["cost"] is None or r["arms"][b]["cost"] < r["arms"][a]["cost"] - 1e-9))
    return wins, losses, V1.sign_test(wins, losses)


def _wilcoxon(rows, a, b):
    diffs = [r["arms"][a]["cost"] - r["arms"][b]["cost"] for r in rows
             if r["arms"][a]["cost"] is not None and r["arms"][b]["cost"] is not None]
    if not any(abs(d) > 1e-9 for d in diffs):
        return None
    from scipy.stats import wilcoxon
    return float(wilcoxon(diffs, alternative="less", zero_method="wilcox").pvalue)


def summarize(rows) -> dict:
    out, vpl, total = {}, 0, 0
    for family in CONSTITUENTS:
        fr = [r for r in rows if r["family"] == family]
        if not fr:
            continue
        total += 1
        arms = arms_for(family)
        median = statistics.median(r["arms"]["routed_composition"]["seconds"] for r in fr)
        routed_states = [r["arms"]["routed_composition"]["state"] for r in fr]
        costs = {a: [r["arms"][a]["cost"] for r in fr] for a in arms}
        wrong = {a: sum(r["arms"][a]["result"] == "wrong" for r in fr) for a in arms}
        nodec = {a: sum(r["arms"][a]["result"] == "no_decision" for r in fr) for a in arms}
        totals = {a: round(sum(c for c in costs[a] if c is not None), 3) for a in arms}
        best = min(CONSTITUENTS[family], key=lambda a: (wrong[a] + nodec[a], totals[a]))
        wins, losses, p = _paired(fr, "routed_composition", best)
        lift = (nodec["routed_composition"] == 0 and totals["routed_composition"] < totals[best]
                and wrong["routed_composition"] <= wrong[best] and p < 0.05 and median <= CHAIN_BUDGET_S)
        versus = {}
        for other in arms:
            if other == "routed_composition":
                continue
            w, l, q = _paired(fr, "routed_composition", other)
            versus[other] = {"wins": w, "losses": l, "sign_test_p_one_sided": round(q, 6),
                             "wilcoxon_p_one_sided": _wilcoxon(fr, "routed_composition", other),
                             "cost_reduction": round(1 - totals["routed_composition"] / totals[other], 4)
                             if totals[other] else None}
        shortage = {a: {k: sum((r["arms"][a]["shortage"] or {}).get(k, 0) for r in fr)
                        for k in ("short_blocks", "agents_short", "agents_paid")} for a in arms}
        out[family] = {"n": len(fr), "total_realised_cost": totals, "infeasible": wrong, "no_decision": nodec,
                       "hindsight_optimal_cost": round(sum(r["truth"]["hindsight_cost"] for r in fr), 3),
                       "shortage": shortage, "best_constituent": best, "routed_wins": wins, "routed_losses": losses,
                       "sign_test_p_one_sided": round(p, 6),
                       "wilcoxon_p_one_sided_vs_best": _wilcoxon(fr, "routed_composition", best),
                       "versus": versus,
                       "median_seconds": {a: round(statistics.median(r["arms"][a]["seconds"] for r in fr), 3)
                                          for a in arms},
                       "median_stages": {a: statistics.median(r["arms"][a]["stages"] or 0 for r in fr) for a in arms},
                       "translation_failure_rate": routed_states.count("TRANSLATION_FAILED") / len(fr),
                       "composition_failure_rate": sum(s != "ANSWERED" for s in routed_states) / len(fr),
                       "model_calls": 0, "money_usd": 0.0, "lift": lift}
        vpl += int(lift)
    out["VPL_v3"] = {"families_with_lift": vpl, "families": total, "rule": VERDICT_RULE}
    return out


# ------------------------------------------------------------------ suite / freeze / run
GENERATORS = {"F6": f6}


def build() -> dict:
    items = []
    for family, (dev, held) in SEEDS.items():
        for partition, seeds in (("dev", dev), ("heldout", held)):
            for seed in seeds:
                items.append({**GENERATORS[family](seed), "partition": partition})
    return {"schema": "greg-composition-lift-suite/3", "items": items}


def inputs() -> dict:
    """JSON-normalised so the comparison with the stored freeze is exact (tuples become lists)."""
    return json.loads(json.dumps({
        "suite": V1._sha(SUITE), "code": {p: V1._sha(ROOT / p) for p in code_closure()}, "verdict_rule": VERDICT_RULE,
        "dependencies": __import__("cortex.evaluation.closure", fromlist=["dependency_versions"]).dependency_versions(),
        "chain_budget_s": CHAIN_BUDGET_S, "staffing": STAFFING, "penalties": PENALTIES,
        "occupancy_rule": OCCUPANCY_RULE, "week": WEEK,
        "seeds": {k: [list(a), list(b)] for k, (a, b) in SEEDS.items()},
        "constituents": CONSTITUENTS, "ablations": ABLATIONS, "evaluation_attach": list(EVAL_ATTACH)}))


def static_choice(dev) -> tuple[str, dict]:
    """The recipe with the lowest total development cost (a recipe that does not answer costs infinity)."""
    from greg.cognition.composition import RECIPES
    totals = {}
    for name in sorted(RECIPES):
        costs = [f6_cost(item, chain(item, name)[0])[0] for item in dev]
        totals[name] = sum(costs) if all(c is not None for c in costs) else math.inf
    return min(sorted(totals), key=lambda n: totals[n]), {k: (v if math.isfinite(v) else None) for k, v in totals.items()}


def _run_item(index, item, static_recipe):
    arms = arms_for(item["family"])
    order = arms[index % len(arms):] + arms[:index % len(arms)]
    row = {"item_id": item["item_id"], "family": item["family"], "truth": item["truth"], "arms": {}}
    for arm in order:
        row["arms"][arm] = run_arm(item, arm, static_recipe)
    row["arms"] = {a: row["arms"][a] for a in arms}
    print(json.dumps({"i": index, "item": item["item_id"],
                      "cost": {a: row["arms"][a]["cost"] for a in arms}}), flush=True)
    return row


def _pin(cores, counter):
    with counter.get_lock():
        slot = counter.value
        counter.value += 1
    os.sched_setaffinity(0, {cores[slot % len(cores)]})


def _job(job):
    return _run_item(*job)


def run_items(items, static_recipe, workers=1):
    """Each day runs whole on one process; with ``workers`` > 1 the days are spread over that many processes,
    each pinned to its own core, so per-day latency is still one core's. Rows come back in suite order."""
    jobs = [(index, item, static_recipe) for index, item in enumerate(items)]
    if workers <= 1:
        return [_job(j) for j in jobs]
    import multiprocessing
    cores = sorted(os.sched_getaffinity(0))
    if len(cores) < workers:
        raise SystemExit(f"{workers} workers need {workers} cores; {len(cores)} available")
    context = multiprocessing.get_context("fork")
    counter = context.Value("i", 0)
    with context.Pool(workers, initializer=_pin, initargs=(cores[:workers], counter), maxtasksperchild=None) as pool:
        return list(pool.imap(_job, jobs, chunksize=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--dev", type=Path, help="builders only: run the development days, never the held-out days")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--workers", type=int, default=1, help="processes, one pinned core each (latency stays per core)")
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
    items = json.loads(SUITE.read_text())["items"]
    dev = [i for i in items if i["partition"] == "dev"]
    if args.dev:
        static_recipe, totals = static_choice(dev)
        rows = run_items(dev, static_recipe, args.workers)
        args.dev.write_text(json.dumps({"partition": "dev", "static_recipe": static_recipe, "recipe_dev_cost": totals,
                                        "rows": rows, "summary": summarize(rows)}, indent=1) + "\n")
        print(json.dumps(summarize(rows), indent=1))
        return
    if json.loads(MANIFEST.read_text())["inputs"] != inputs():
        raise SystemExit("FROZEN_INPUT_CHANGED: results cannot be reported")
    if not args.out:
        raise SystemExit("--out required")
    heldout = [i for i in items if i["partition"] == "heldout"]
    static_recipe, totals = static_choice(dev)
    print(json.dumps({"recipe_dev_cost": totals, "static_recipe": static_recipe}), flush=True)
    rows = run_items(heldout, static_recipe, args.workers)
    report = {"schema": "greg-composition-lift-results/3", "manifest_sha256": V1._sha(MANIFEST),
              "finished_at": datetime.now(timezone.utc).isoformat(),
              "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "platform": platform.platform(), "python": sys.version.split()[0], "workers": args.workers,
              "development": {"recipe_dev_cost": totals, "static_recipe": static_recipe},
              "heldout": rows, "summary": summarize(rows),
              "limits": ["real arrivals and real outcomes; the handle time, service target and cost weights are a "
                         "declared decision layer, not the bank's",
                         "the required staffing is the Erlang C model's at the realised rate: the outcome is "
                         "real, the queueing model is an assumption shared by every arm",
                         "days are consecutive weekdays from one bank in 2003; the day is the unit of the sign "
                         "test but days are not independent draws from a population of call centres",
                         "one container; latency is this machine's"]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({"development": report["development"], "summary": report["summary"]}, indent=1))


if __name__ == "__main__":
    main()
