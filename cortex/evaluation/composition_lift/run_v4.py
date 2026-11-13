"""P6 v4: a natural graph-allocation family on real backbone networks (founder directive 2026-10-07, step A).

v1-v3 measured VPL on six families; two were natural (F5 real M4 demand: no lift; F6 real bank arrivals:
lift). Both natural families are "forecast, then decide". F7 is a different geometry: graph bottleneck ->
integer allocation (recipe ``graph_then_allocate``), the recipe whose only lift so far (F3) was on generated
networks. Nothing earlier is re-scored. The pre-registration is ``prereg-v4.json`` (checked by
``vpl_metrics.validate_preregistration``), committed before the held-out partition is generated.

F7, NATURAL INSTANCES: buy capacity for a traffic surge on a real backbone. The data are 25 SNDlib networks
(Orlowski et al., Networks 55:276-286, 2010) as bundled by TopoHub 1.5.1: real nodes, real links with their
lengths, the real demand matrix and each link's directional load under ECMP shortest-path routing of that
demand (``cortex/evaluation/data/sndlib_networks.json.gz``). Each item is one real (network, demand pair):
the pair's demand surges and the operator has a budget to lease extra capacity. Maximise the surge s -> t
throughput that fits within the budget.

The decision layer is declared here, before any held-out arm runs. It is a standard planning formulation; it
is not SNDlib's own capacities or costs, which TopoHub does not carry:

* unit = 1% of the busiest link's ECMP load (TopoHub's normalisation);
* installed capacity per direction = M * m, M = 10 units per module, m = max(1, ceil(load / (0.8 M))): the
  fewest modules that keep utilisation at or below 80%;
* free capacity for the surge = floor(M * m - load) per direction (current traffic keeps its share);
* admissible paths: the K = 4 shortest loop-free s -> t paths by length (Yen); arcs are the union of their
  hops, as in path-based network design. If the union has more than 32 arcs (the optimisation family's
  64-variable ceiling), K drops to 3, then 2; an item still above 32 arcs is out of scope, decided by
  topology alone and counted;
* lease price per unit on an arc = 1 + round(km / 100);
* at most 20 extra units per arc; budget = 20 x the price of the cheapest admissible path.

The outcome is not a realised one. The truth is the exact optimum of this declared problem on real
structure: the cheapest way to carry F units is a min-cost flow (free arc at the free capacity, priced arc
up to 20 units); the largest F within budget is found by bisection (NetworkX network simplex, not CP-SAT).
F7 therefore tests optimisation quality on natural instances, not prediction against reality as F5 and F6 do.

Partition, fixed before any arm ran: networks sorted by name, every fifth (index % 5 == 0) is development
(abilene, di-yuan, india35, nobel-germany, polska); the other 20 networks are held out. Items are the 10
largest demand pairs of each network. Development items informed the design. The corridor sizes of all 25
networks were computed (topology only, no arm) while choosing the admissible-path rule; that is disclosed in
the pre-registration.

Arms (GREG arms through ``greg.cognition.cortex.reason``; genome families attached in an evaluation-only
registry view):

* ``graph_alone_greedy``     constituent: graph intelligence alone (``reinforce_min_cut``: one unit on the
                             cheapest edge of the current minimum cut, repeated).
* ``optimize_flow_blind``    constituent: the optimiser alone without flow structure (maximise units bought
                             on source and sink arcs within budget).
* ``static_composition`` / ``routed_composition``: ``graph_then_allocate`` (compile -> CP-SAT -> max-flow
                             cross-check). The router matches geometry keys, so routed equals static here.
* ``compiled``               the same request through the Competency Compiler: ``{compile: {geometry, data}}``.
* ``shortest_path_upgrade``  practitioner, outside GREG: lease capacity end to end along the cheapest path,
                             one unit per arc per round, until the budget or the arc limit stops it.
* ``parametric_min_cost_flow`` practitioner, outside GREG: what an operations-research practitioner would
                             write. It is the truth algorithm, so it is optimal by construction; it is
                             reported to show what composition does and does not add, never as a constituent.

Verdict (frozen): F7 counts toward VPL when routed composition decides more held-out items optimally than the
best constituent, gives no more wrong answers, the one-sided exact sign test over discordant items gives
p < 0.05, its median latency is within the 60 s chain budget, and its median latency is at most 10x the
best constituent's (the pre-registered latency rule). The best constituent is chosen on held-out results
(most optimal, then fewest wrong). Practitioner comparisons, the compiled arm, a per-network sign test and the
throughput shortfall are reported alongside, not as part of the rule.
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

SUITE = HERE / "suite-v4.json"
MANIFEST = HERE / "freeze-v4.json"
PREREG = HERE / "prereg-v4.json"
DATA = ROOT / "cortex/evaluation/data/sndlib_networks.json.gz"
CHAIN_BUDGET_S = 60.0
LATENCY_MULTIPLIER = 10.0
MODULE, UTILISATION, PATHS, MIN_PATHS, MAX_ARCS = 10, 0.8, 4, 2, 32
MAX_INCREMENT, BUDGET_UNITS, PAIRS_PER_NETWORK = 20, 20, 10
CONSTITUENTS = {"F7": ("graph_alone_greedy", "optimize_flow_blind")}
PRACTITIONERS = {"F7": ("shortest_path_upgrade", "parametric_min_cost_flow")}
EVAL_ATTACH = ("cognition.flow_maxflow", "cognition.flow_capacity_plan", "cognition.flow_reinforce_greedy",
               "cognition.optimization")
ENTRY_POINTS = ("cortex/evaluation/composition_lift/run_v4.py", "greg/cognition/worker.py")
FROZEN_EXTRA = ("cortex/evaluation/data/sndlib_networks.json.gz", "cortex/evaluation/data/build_sndlib_networks.py",
                "cortex/evaluation/composition_lift/prereg-v4.json", "tools/offline_test.py",
                "requirements-cortex.txt", "requirements-cognition.txt")
VERDICT_RULE = ("F7 (natural instances, exact truth): routed optimal > best constituent optimal, routed wrong <= "
                "best constituent wrong, one-sided exact sign test over discordant held-out items p < 0.05, routed "
                "median latency <= 60 s and <= 10x the best constituent's median. Best constituent chosen on "
                "held-out results (most optimal, then fewest wrong). Practitioner, compiled-arm and per-network "
                "comparisons reported, not part of the rule. VPL = families meeting their rule.")


def code_closure() -> list[str]:
    """Every repository file the run can execute, hashed by the freeze (the v3 closure rule)."""
    from cortex.evaluation.closure import code_closure as closure
    return closure(ENTRY_POINTS, packages=("greg/cognition",), extra=FROZEN_EXTRA, root=ROOT)


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
    c = {"question": "lease capacity for a traffic surge within budget", "payload": item["payload"],
         "max_latency_s": CHAIN_BUDGET_S}
    if recipe:
        c["recipe"] = recipe
    started = time.perf_counter()
    r = reason({"problem_id": item["item_id"], "chain": c})
    return (r["answer"] if r["state"] == "ANSWERED" else None), time.perf_counter() - started, r


def compiled(item):
    started = time.perf_counter()
    r = reason({"problem_id": item["item_id"] + "/compiled",
                "compile": {"geometry": {"consequence_class": "read_only"}, "data": item["payload"]}})
    answer = r.get("result") if r["state"] == "ANSWERED" else None
    return answer, time.perf_counter() - started, r


# ------------------------------------------------------------------ F7 data, items and truth
@lru_cache(maxsize=1)
def sndlib() -> dict:
    with gzip.open(DATA, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def partition() -> tuple[list[str], list[str]]:
    names = sorted(sndlib()["networks"])
    return [n for i, n in enumerate(names) if i % 5 == 0], [n for i, n in enumerate(names) if i % 5 != 0]


def free_capacity(load: float) -> int:
    modules = max(1, math.ceil(load / (UTILISATION * MODULE)))
    return int(math.floor(modules * MODULE - load))


def corridor(net: dict, s: str, t: str) -> tuple[list[tuple[str, str]], int] | None:
    """Arcs on the K shortest loop-free s -> t paths by length, K = 4 down to 2 until at most 32 arcs."""
    import networkx as nx
    g = nx.Graph()
    for u, v, km, _, _ in net["links"]:
        g.add_edge(u, v, km=km)
    for k in range(PATHS, MIN_PATHS - 1, -1):
        paths = []
        for p in nx.shortest_simple_paths(g, s, t, weight="km"):
            paths.append(p)
            if len(paths) == k:
                break
        arcs = sorted({(p[i], p[i + 1]) for p in paths for i in range(len(p) - 1)})
        if len(arcs) <= MAX_ARCS:
            return arcs, k
    return None


def cheapest_path_price(arcs, price, s, t) -> int:
    import networkx as nx
    g = nx.DiGraph()
    for u, v in arcs:
        g.add_edge(u, v, w=price[f"{u}->{v}"])
    return int(nx.shortest_path_length(g, s, t, weight="w"))


def f7(network: str, pair: int) -> dict | None:
    """One (network, demand pair) item, or None when the admissible-path union exceeds 32 arcs at K = 2."""
    from greg.cognition.genomes.flow import expansion_truth, expansion_value
    net = sndlib()["networks"][network]
    s, t, demand = net["top_demands"][pair]
    found = corridor(net, s, t)
    if found is None:
        return None
    arcs, k = found
    load, km = {}, {}
    for u, v, length, uv, vu in net["links"]:
        load[(u, v)], load[(v, u)] = uv, vu
        km[(u, v)] = km[(v, u)] = length
    price = {f"{u}->{v}": 1 + round(km[(u, v)] / 100) for u, v in arcs}
    data = {"edges": [[u, v, free_capacity(load[(u, v)])] for u, v in arcs], "source": s, "sink": t,
            "unit_cost": price, "max_increment": MAX_INCREMENT,
            "budget": BUDGET_UNITS * cheapest_path_price(arcs, price, s, t)}
    no_lease, _ = expansion_value(data, {})
    return {"item_id": f"F7-{network}-{pair}", "family": "F7", "network": network, "pair": pair,
            "payload": {"capacity_network": data},
            "truth": {"optimum": expansion_truth(data), "without_lease": no_lease, "paths": k, "arcs": len(arcs),
                      "demand": demand}}


def f7_score(item, answer):
    """(outcome, throughput): optimal, suboptimal, wrong (over budget, out of bounds or a false flow claim)
    or no_decision; throughput is the flow the plan actually achieves, recomputed here."""
    from greg.cognition.genomes.flow import expansion_value
    if not isinstance(answer, dict) or not isinstance(answer.get("increments"), dict):
        return "no_decision", None
    try:
        value, _ = expansion_value(item["payload"]["capacity_network"], answer["increments"])
    except Exception:
        return "wrong", None
    if value is None:
        return "wrong", None
    if answer.get("flow_value") is not None and answer["flow_value"] != value:
        return "wrong", value
    return ("optimal" if value == item["truth"]["optimum"] else "suboptimal"), value


# ------------------------------------------------------------------ arms
def flow_blind_model(net):
    """The optimiser alone, without flow structure: maximise units bought on source and sink arcs (as in F3)."""
    variables, cost = {}, {}
    for i, (u, v, _) in enumerate(net["edges"]):
        if u == net["source"] or v == net["sink"]:
            variables[f"x{i}"] = [0, net["max_increment"]]
            cost[f"x{i}"] = net["unit_cost"][f"{u}->{v}"]
    return {"variables": variables,
            "constraints": [{"coefficients": cost, "op": "<=", "rhs": net["budget"], "requirement_id": "budget"}],
            "objective": {"coefficients": {k: 1 for k in variables}, "sense": "max"}}


def shortest_path_upgrade(net):
    """Practitioner: lease end to end along the cheapest path, one unit per arc per round."""
    import networkx as nx
    g = nx.DiGraph()
    for u, v, _ in net["edges"]:
        g.add_edge(u, v, w=net["unit_cost"][f"{u}->{v}"])
    path = nx.shortest_path(g, net["source"], net["sink"], weight="w")
    hops = [f"{path[i]}->{path[i + 1]}" for i in range(len(path) - 1)]
    round_price = sum(net["unit_cost"][h] for h in hops)
    increments = {f"{u}->{v}": 0 for u, v, _ in net["edges"]}
    money, units = net["budget"], 0
    while money >= round_price and units < net["max_increment"]:
        for h in hops:
            increments[h] += 1
        money -= round_price
        units += 1
    return {"increments": increments}


def parametric_min_cost_flow(net):
    """Practitioner (the truth algorithm, with its plan): the largest surge F whose min-cost flow fits the budget,
    and the leased units that flow uses."""
    import networkx as nx
    edges, s, t = net["edges"], net["source"], net["sink"]

    def solve(volume):
        g = nx.DiGraph()
        g.add_node(s, demand=-volume)
        g.add_node(t, demand=volume)
        for i, (u, v, c) in enumerate(edges):
            g.add_edge(u, f"__{i}", capacity=c, weight=0)
            g.add_edge(u, f"__{i}x", capacity=net["max_increment"], weight=net["unit_cost"][f"{u}->{v}"])
            g.add_edge(f"__{i}", v, capacity=c, weight=0)
            g.add_edge(f"__{i}x", v, capacity=net["max_increment"], weight=0)
        try:
            flow = nx.min_cost_flow(g)
        except nx.NetworkXUnfeasible:
            return None
        return nx.cost_of_flow(g, flow), flow
    lo, hi, best = 0, sum(c + net["max_increment"] for u, v, c in edges if u == s), None
    while lo < hi:
        mid = (lo + hi + 1) // 2
        found = solve(mid)
        if found is not None and found[0] <= net["budget"]:
            lo, best = mid, found
        else:
            hi = mid - 1
    flow = best[1] if best else None
    return {"increments": {f"{u}->{v}": (flow[u][f"__{i}x"] if flow else 0) for i, (u, v, _) in enumerate(edges)},
            "flow_value": lo}


def run_arm(item, arm, static_recipe):
    started, stages, state, answer = time.perf_counter(), None, "constituent", None
    pid, net = item["item_id"], item["payload"]["capacity_network"]
    if arm in ("static_composition", "routed_composition"):
        answer, seconds, r = chain(item, static_recipe if arm == "static_composition" else None)
        stages, state = len(r.get("stages", [])), r["state"]
    elif arm == "compiled":
        answer, seconds, r = compiled(item)
        stages, state = (r.get("resource_use") or {}).get("stages"), r["state"]
    else:
        if arm == "graph_alone_greedy":
            answer = op(pid, "reinforce_min_cut", net)
            stages = 1
        elif arm == "optimize_flow_blind":
            out = op(pid, "optimize", flow_blind_model(net))
            stages = 1
            if out and out.get("solver_status") in ("OPTIMAL", "FEASIBLE"):
                inc = {f"{u}->{v}": 0 for u, v, _ in net["edges"]}
                for i, (u, v, _) in enumerate(net["edges"]):
                    if f"x{i}" in out["solution"]:
                        inc[f"{u}->{v}"] = out["solution"][f"x{i}"]
                answer = {"increments": inc}
        elif arm == "shortest_path_upgrade":
            answer, state = shortest_path_upgrade(net), "practitioner_in_process"
        elif arm == "parametric_min_cost_flow":
            answer, state = parametric_min_cost_flow(net), "practitioner_in_process"
        else:
            raise ValueError(f"unknown arm {arm}")
        seconds = time.perf_counter() - started
    outcome, throughput = f7_score(item, answer)
    return {"result": outcome, "throughput": throughput, "seconds": round(seconds, 4), "stages": stages,
            "state": state, "answer": answer}


def arms_for(family):
    return (list(CONSTITUENTS[family]) + list(PRACTITIONERS[family])
            + ["static_composition", "routed_composition", "compiled"])


# ------------------------------------------------------------------ verdict
def _discordant(rows, a, b):
    wins = sum(1 for r in rows if r["arms"][a]["result"] == "optimal" and r["arms"][b]["result"] != "optimal")
    losses = sum(1 for r in rows if r["arms"][b]["result"] == "optimal" and r["arms"][a]["result"] != "optimal")
    return wins, losses, V1.sign_test(wins, losses)


def summarize(rows) -> dict:
    out, vpl, total = {}, 0, 0
    for family in CONSTITUENTS:
        fr = [r for r in rows if r["family"] == family]
        if not fr:
            continue
        total += 1
        arms = arms_for(family)
        count = {a: {k: sum(r["arms"][a]["result"] == k for r in fr)
                     for k in ("optimal", "suboptimal", "wrong", "no_decision")} for a in arms}
        median = {a: round(statistics.median(r["arms"][a]["seconds"] for r in fr), 4) for a in arms}
        best = max(CONSTITUENTS[family], key=lambda a: (count[a]["optimal"], -count[a]["wrong"]))
        wins, losses, p = _discordant(fr, "routed_composition", best)
        routed = count["routed_composition"]
        latency_ok = (median["routed_composition"] <= CHAIN_BUDGET_S
                      and median["routed_composition"] <= LATENCY_MULTIPLIER * median[best])
        lift = (routed["optimal"] > count[best]["optimal"] and routed["wrong"] <= count[best]["wrong"]
                and p < 0.05 and latency_ok)
        versus = {}
        for other in arms:
            if other != "routed_composition":
                w, l, q = _discordant(fr, "routed_composition", other)
                versus[other] = {"wins": w, "losses": l, "sign_test_p_one_sided": round(q, 6)}
        shortfall = {a: sum(r["truth"]["optimum"] - (r["arms"][a]["throughput"] or 0) for r in fr) for a in arms}
        networks = sorted({r["network"] for r in fr})
        per_network = {}
        for n in networks:
            nr = [r for r in fr if r["network"] == n]
            per_network[n] = {a: sum(r["arms"][a]["result"] == "optimal" for r in nr)
                              for a in ("routed_composition", best)}
        net_wins = sum(v["routed_composition"] > v[best] for v in per_network.values())
        net_losses = sum(v["routed_composition"] < v[best] for v in per_network.values())
        states = [r["arms"]["routed_composition"]["state"] for r in fr]
        out[family] = {"n": len(fr), "networks": len(networks), "outcomes": count, "best_constituent": best,
                       "routed_wins": wins, "routed_losses": losses, "sign_test_p_one_sided": round(p, 6),
                       "median_seconds": median, "latency_rule": {"multiplier": LATENCY_MULTIPLIER,
                                                                  "ratio": round(median["routed_composition"]
                                                                                 / median[best], 3)
                                                                  if median[best] else None, "met": latency_ok},
                       "versus": versus, "throughput_shortfall_vs_optimum": shortfall,
                       "per_network_optimal": per_network,
                       "per_network_sign_test": {"wins": net_wins, "losses": net_losses,
                                                 "p_one_sided": round(V1.sign_test(net_wins, net_losses), 6)},
                       "translation_failure_rate": states.count("TRANSLATION_FAILED") / len(fr),
                       "composition_failure_rate": sum(s != "ANSWERED" for s in states) / len(fr),
                       "model_calls": 0, "money_usd": 0.0, "lift": lift}
        vpl += int(lift)
    out["VPL_v4"] = {"families_with_lift": vpl, "families": total, "rule": VERDICT_RULE}
    return out


# ------------------------------------------------------------------ suite / freeze / run
def build() -> dict:
    dev, held = partition()
    items, out_of_scope = [], []
    for part, networks in (("dev", dev), ("heldout", held)):
        for network in networks:
            for pair in range(PAIRS_PER_NETWORK):
                item = f7(network, pair)
                if item is None:
                    out_of_scope.append({"network": network, "pair": pair, "partition": part})
                else:
                    items.append({**item, "partition": part})
    return {"schema": "greg-composition-lift-suite/4", "items": items, "out_of_scope": out_of_scope}


def inputs() -> dict:
    """JSON-normalised so the comparison with the stored freeze is exact (tuples become lists)."""
    return json.loads(json.dumps({
        "suite": V1._sha(SUITE), "prereg": V1._sha(PREREG),
        "code": {p: V1._sha(ROOT / p) for p in code_closure()}, "verdict_rule": VERDICT_RULE,
        "dependencies": __import__("cortex.evaluation.closure", fromlist=["dependency_versions"]).dependency_versions(),
        "chain_budget_s": CHAIN_BUDGET_S, "latency_multiplier": LATENCY_MULTIPLIER,
        "layer": {"module": MODULE, "utilisation": UTILISATION, "paths": PATHS, "min_paths": MIN_PATHS,
                  "max_arcs": MAX_ARCS, "max_increment": MAX_INCREMENT, "budget_units": BUDGET_UNITS,
                  "pairs_per_network": PAIRS_PER_NETWORK},
        "partition": partition(), "constituents": CONSTITUENTS, "practitioners": PRACTITIONERS,
        "evaluation_attach": list(EVAL_ATTACH)}))


def static_choice(dev) -> tuple[str, dict]:
    """The recipe deciding the most development items optimally; a recipe that leaves any undecided is out."""
    from greg.cognition.composition import RECIPES
    counts = {}
    for name in sorted(RECIPES):
        outcomes = [f7_score(item, chain(item, name)[0])[0] for item in dev]
        counts[name] = None if "no_decision" in outcomes else outcomes.count("optimal")
    eligible = [n for n in sorted(counts) if counts[n] is not None]
    if not eligible:
        raise SystemExit("no recipe decides every development item: there is no static baseline")
    return max(eligible, key=lambda n: counts[n]), counts


def _run_item(index, item, static_recipe):
    arms = arms_for(item["family"])
    order = arms[index % len(arms):] + arms[:index % len(arms)]
    row = {"item_id": item["item_id"], "family": item["family"], "network": item["network"], "truth": item["truth"],
           "arms": {}}
    for arm in order:
        row["arms"][arm] = run_arm(item, arm, static_recipe)
    row["arms"] = {a: row["arms"][a] for a in arms}
    print(json.dumps({"i": index, "item": item["item_id"], "optimum": item["truth"]["optimum"],
                      "throughput": {a: row["arms"][a]["throughput"] for a in arms}}), flush=True)
    return row


def _pin(cores, counter):
    with counter.get_lock():
        slot = counter.value
        counter.value += 1
    os.sched_setaffinity(0, {cores[slot % len(cores)]})


def _job(job):
    return _run_item(*job)


def run_items(items, static_recipe, workers=1, cores=None):
    """Each item runs whole on one process; with ``workers`` > 1 the items are spread over that many processes,
    each pinned to its own core, so per-item latency is still one core's. Rows come back in suite order."""
    jobs = [(index, item, static_recipe) for index, item in enumerate(items)]
    if workers <= 1:
        return [_job(j) for j in jobs]
    import multiprocessing
    cores = sorted(cores or os.sched_getaffinity(0))
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
    ap.add_argument("--dev", type=Path, help="builders only: run the development items, never the held-out items")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--workers", type=int, default=1, help="processes, one pinned core each (latency stays per core)")
    ap.add_argument("--cores", type=str, help="comma-separated cores for the workers (default: all available)")
    args = ap.parse_args()
    cores = [int(c) for c in args.cores.split(",")] if args.cores else None
    if args.build:
        if SUITE.exists():
            raise SystemExit("refusing to overwrite the suite; create a new version")
        from cortex.evaluation.composition_lift.vpl_metrics import validate_preregistration
        problems = validate_preregistration(json.loads(PREREG.read_text()))
        if problems:
            raise SystemExit(f"the pre-registration is incomplete: {problems}")
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
        static_recipe, counts = static_choice(dev)
        rows = run_items(dev, static_recipe, args.workers, cores)
        args.dev.write_text(json.dumps({"partition": "dev", "static_recipe": static_recipe, "recipe_dev_optimal": counts,
                                        "rows": rows, "summary": summarize(rows)}, indent=1) + "\n")
        print(json.dumps(summarize(rows), indent=1))
        return
    if json.loads(MANIFEST.read_text())["inputs"] != inputs():
        raise SystemExit("FROZEN_INPUT_CHANGED: results cannot be reported")
    if not args.out:
        raise SystemExit("--out required")
    heldout = [i for i in items if i["partition"] == "heldout"]
    static_recipe, counts = static_choice(dev)
    print(json.dumps({"recipe_dev_optimal": counts, "static_recipe": static_recipe}), flush=True)
    rows = run_items(heldout, static_recipe, args.workers, cores)
    report = {"schema": "greg-composition-lift-results/4", "manifest_sha256": V1._sha(MANIFEST),
              "finished_at": datetime.now(timezone.utc).isoformat(),
              "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "platform": platform.platform(), "python": sys.version.split()[0], "workers": args.workers,
              "development": {"recipe_dev_optimal": counts, "static_recipe": static_recipe},
              "out_of_scope": json.loads(SUITE.read_text())["out_of_scope"],
              "heldout": rows, "summary": summarize(rows),
              "limits": ["real topologies, link lengths, demand pairs and ECMP loads; module size, utilisation "
                         "target, admissible paths, lease prices, arc limit and budget are a declared planning "
                         "layer, not SNDlib's own capacities or costs",
                         "the truth is the exact optimum of the declared problem, not a realised outcome",
                         "items within one network share its topology; the item sign test treats them as "
                         "independent, so a per-network sign test is reported alongside",
                         "practitioner arms run in process, outside GREG's isolated workers; their latency is "
                         "not comparable with the GREG arms'",
                         "one container; latency is this machine's"]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({"development": report["development"], "summary": report["summary"]}, indent=1))


if __name__ == "__main__":
    main()
