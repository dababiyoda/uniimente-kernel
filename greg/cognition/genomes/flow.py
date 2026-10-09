"""Layer 3 graph intelligence: max-flow / min-cut control points and capacity-expansion compilation.

Three executables on GREG's cognition path:

* ``flow_maxflow`` (operation ``max_flow``): maximum s-t flow with the minimum cut that certifies it
  (max-flow/min-cut duality is the optimality certificate). The cut edges are the network's control
  points: the decision-relevant bottleneck.
* ``flow_reinforce_greedy`` (operation ``reinforce_min_cut``): graph intelligence acting alone on a
  capacity-expansion decision - repeatedly buy one unit on the cheapest edge of the current minimum cut
  until the budget is spent. A fast, common heuristic; it can waste budget when several minimum cuts tie.
* ``flow_capacity_plan`` (operation ``compile_capacity_expansion``): the typed translation from a network
  with expansion costs and a budget into the integer model the existing CP-SAT optimisation family solves
  (flow variables, conservation, expanded capacities, budget, maximise outflow). It decides nothing on its
  own (COMPOSITION_ONLY); paired with ``optimize`` it is the ``graph_then_allocate`` composition.

Independent verification never reuses NetworkX: flows are checked by arithmetic, cuts by a separate BFS.
"""
from __future__ import annotations

from collections import deque
import random

from .contract import Executable, GenomeError, IntelligenceGenome, answer, bounded_int, finite

LINEAGE = ("INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION", "INTENT-20261007-VERIFIED-POLYINTELLIGENCE-LIFT",
           "greg/cognition/network.py (GREG's own graph code)")
MAX_EDGES, MAX_NODES = 400, 120


# ------------------------------------------------------------------ input
def _graph(data):
    edges = data.get("edges")
    if not isinstance(edges, list) or not 1 <= len(edges) <= MAX_EDGES:
        raise GenomeError(f"1-{MAX_EDGES} edges required")
    out, nodes = [], set()
    for e in edges:
        if not isinstance(e, list) or len(e) != 3 or not all(isinstance(n, str) and n for n in e[:2]):
            raise GenomeError("edge is [from, to, capacity]")
        if e[0] == e[1]:
            raise GenomeError("self-loops are not allowed")
        out.append((e[0], e[1], bounded_int(e[2], low=0, high=1_000_000, name="capacity")))
        nodes.update(e[:2])
    s, t = data.get("source"), data.get("sink")
    if s not in nodes or t not in nodes or s == t or len(nodes) > MAX_NODES:
        raise GenomeError("distinct source and sink in a bounded graph required")
    return out, s, t


def _merged(edges):
    cap = {}
    for u, v, c in edges:
        cap[(u, v)] = cap.get((u, v), 0) + c
    return cap


def _reach(cap, flow, s):
    """Nodes reachable from s in the residual graph (independent of NetworkX)."""
    adj = {}
    for (u, v), c in cap.items():
        adj.setdefault(u, []).append(v)
        adj.setdefault(v, []).append(u)
    seen, queue = {s}, deque([s])
    while queue:
        u = queue.popleft()
        for v in adj.get(u, ()):
            if v in seen:
                continue
            forward = cap.get((u, v), 0) - flow.get((u, v), 0)
            backward = flow.get((v, u), 0)
            if forward > 0 or backward > 0:
                seen.add(v)
                queue.append(v)
    return seen


def edmonds_karp(edges, s, t):
    """A separate exact max-flow (BFS augmenting paths) used for truth and verification."""
    cap = _merged(edges)
    flow = {k: 0 for k in cap}
    value = 0
    while True:
        parent = {s: None}
        queue = deque([s])
        adj = {}
        for (u, v) in cap:
            adj.setdefault(u, []).append((v, 1))
            adj.setdefault(v, []).append((u, -1))
        while queue and t not in parent:
            u = queue.popleft()
            for v, direction in adj.get(u, ()):
                if v in parent:
                    continue
                residual = cap[(u, v)] - flow[(u, v)] if direction == 1 else flow[(v, u)]
                if residual > 0:
                    parent[v] = (u, direction)
                    queue.append(v)
        if t not in parent:
            return value, flow
        path, v = [], t
        while parent[v] is not None:
            u, direction = parent[v]
            path.append((u, v, direction))
            v = u
        push = min(cap[(u, v)] - flow[(u, v)] if d == 1 else flow[(v, u)] for u, v, d in path)
        for u, v, d in path:
            if d == 1:
                flow[(u, v)] += push
            else:
                flow[(v, u)] -= push
        value += push


# ------------------------------------------------------------------ max flow
def maxflow_solve(data, budget):
    import networkx as nx
    edges, s, t = _graph(data)
    g = nx.DiGraph()
    for (u, v), c in _merged(edges).items():
        g.add_edge(u, v, capacity=c)
    value, flows = nx.maximum_flow(g, s, t)
    _, (side, _) = nx.minimum_cut(g, s, t)
    cut = sorted([u, v, g[u][v]["capacity"]] for u in side for v in g.successors(u) if v not in side)
    edge_flow = sorted([u, v, f] for u, row in flows.items() for v, f in row.items() if f > 0)
    return answer({"value": int(value), "cut_edges": cut, "flow": edge_flow},
                  {"source_side": sorted(side), "cut_capacity": sum(c for *_, c in cut),
                   "duality": "max-flow value equals the capacity of the returned s-t cut"})


def maxflow_verify(data, output, certificate):
    edges, s, t = _graph(data)
    cap = _merged(edges)
    flow = {}
    for u, v, f in output.get("flow", []):
        flow[(u, v)] = flow.get((u, v), 0) + f
    bounded = all(0 <= f <= cap.get(k, -1) for k, f in flow.items())
    nodes = {n for k in cap for n in k}
    balance = {n: 0 for n in nodes}
    for (u, v), f in flow.items():
        balance[u] -= f
        balance[v] += f
    conserved = all(balance[n] == 0 for n in nodes if n not in (s, t))
    value_ok = balance.get(t, 0) == output["value"] == -balance.get(s, 0)
    side = set(certificate.get("source_side", []))
    cut_cap = sum(c for (u, v), c in cap.items() if u in side and v not in side)
    reach = _reach(cap, flow, s)
    return {"capacity_respected": bounded, "conservation": conserved, "value_matches_flow": value_ok,
            "cut_separates": s in side and t not in side, "cut_capacity_equals_value": cut_cap == output["value"],
            "no_augmenting_path": t not in reach}


def _network(seed, *, costs=False):
    r = random.Random(seed)
    a = [f"a{i}" for i in range(r.randint(3, 4))]
    b = [f"b{i}" for i in range(r.randint(3, 4))]
    edges = [["s", x, r.randint(4, 14)] for x in a] + [[y, "t", r.randint(4, 14)] for y in b]
    for x in a:
        for y in b:
            if r.random() < 0.55:
                edges.append([x, y, r.randint(1, 9)])
    for x, y in zip(a, a[1:]):
        if r.random() < 0.3:
            edges.append([x, y, r.randint(1, 5)])
    for x in a:                                    # guarantee every relay has an outlet
        if not any(e[0] == x and e[1].startswith("b") for e in edges):
            edges.append([x, r.choice(b), r.randint(1, 9)])
    data = {"edges": edges, "source": "s", "sink": "t"}
    if costs:
        data["unit_cost"] = {f"{u}->{v}": r.randint(1, 5) for u, v, _ in edges}
        data["max_increment"] = 8
        data["budget"] = r.randint(8, 28)
    return data


def _general_network(seed):
    """General sparse digraph (cross and back edges) where augmenting without undo is not enough."""
    r = random.Random(50_000 + seed)
    n = r.randint(14, 26)
    nodes = ["s", *[f"n{i}" for i in range(n)], "t"]
    edges, seen = [], set()
    for i, u in enumerate(nodes[:-1]):
        for v in r.sample(nodes[1:], k=min(len(nodes) - 1, r.randint(2, 4))):
            if v != u and (u, v) not in seen and not (u == "s" and v == "t"):
                seen.add((u, v))
                edges.append([u, v, r.randint(1, 20)])
    for u, v in [("s", x) for x in r.sample(nodes[1:-1], 2)] + [(x, "t") for x in r.sample(nodes[1:-1], 3)]:
        if (u, v) not in seen:
            seen.add((u, v))
            edges.append([u, v, r.randint(1, 20)])
    return {"edges": edges, "source": "s", "sink": "t"}


def maxflow_instance(seed):
    data = _general_network(seed)
    value, _ = edmonds_karp(*_graph(data))
    return data, {"value": value}


def maxflow_score(data, truth, output):
    if not isinstance(output, dict) or "value" not in output:
        return {"quality": -1.0, "category": "abstain"}
    if output["value"] > truth["value"]:
        return {"quality": -2.0, "category": "wrong"}          # claims a flow that cannot exist
    q = output["value"] / truth["value"] if truth["value"] else 1.0
    return {"quality": q, "category": "correct" if output["value"] == truth["value"] else "wrong"}


def maxflow_greedy_paths(data):
    """Baseline: augment along paths in the ORIGINAL graph, never undoing flow (no residual reverse edges)."""
    edges, s, t = _graph(data)
    remaining = dict(_merged(edges))
    value = 0
    while True:
        parent, queue = {s: None}, deque([s])
        while queue and t not in parent:
            u = queue.popleft()
            for (x, y), c in sorted(remaining.items()):
                if x == u and c > 0 and y not in parent:
                    parent[y] = u
                    queue.append(y)
        if t not in parent:
            return {"value": value}
        path, v = [], t
        while parent[v] is not None:
            path.append((parent[v], v))
            v = parent[v]
        push = min(remaining[e] for e in path)
        for e in path:
            remaining[e] -= push
        value += push


def maxflow_trivial_cut(data):
    """Baseline: the bound an engineer reads off without flow reasoning - min(out of source, into sink)."""
    edges, s, t = _graph(data)
    return {"value": min(sum(c for u, _, c in edges if u == s), sum(c for _, v, c in edges if v == t))}


def maxflow_lp(data):
    """Competitor: the same max-flow as a linear program (SciPy HiGHS)."""
    from scipy.optimize import linprog
    edges, s, t = _graph(data)
    keys = sorted(_merged(edges))
    cap = _merged(edges)
    nodes = sorted({n for k in keys for n in k} - {s, t})
    c = [-1.0 if u == s else (1.0 if v == s else 0.0) for u, v in keys]
    a_eq = [[(1.0 if v == n else 0.0) - (1.0 if u == n else 0.0) for u, v in keys] for n in nodes]
    res = linprog(c, A_eq=a_eq or None, b_eq=[0.0] * len(nodes) or None,
                  bounds=[(0, cap[k]) for k in keys], method="highs")
    return {"value": int(round(-res.fun))} if res.success else None


# ------------------------------------------------------------------ capacity expansion
def _expansion(data):
    edges, s, t = _graph(data)
    costs = data.get("unit_cost")
    if not isinstance(costs, dict):
        raise GenomeError("unit_cost maps 'u->v' to an integer cost")
    unit = {}
    for u, v, _ in edges:
        unit[(u, v)] = bounded_int(costs.get(f"{u}->{v}"), low=0, high=10_000, name="unit cost")
    inc = bounded_int(data.get("max_increment"), low=0, high=1000, name="max_increment")
    budget = bounded_int(data.get("budget"), low=0, high=1_000_000, name="budget")
    return edges, s, t, unit, inc, budget


def expansion_value(data, increments):
    edges, s, t, unit, inc, budget = _expansion(data)
    spent = sum(unit[(u, v)] * increments.get(f"{u}->{v}", 0) for u, v, _ in edges)
    if spent > budget or any(not 0 <= increments.get(f"{u}->{v}", 0) <= inc for u, v, _ in edges):
        return None, spent
    value, _ = edmonds_karp([(u, v, c + increments.get(f"{u}->{v}", 0)) for u, v, c in edges], s, t)
    return value, spent


def expansion_truth(data):
    """Exact optimum by a different algorithm: the cheapest way to carry F units is a min-cost flow
    (free arc at existing capacity + paid arc up to max_increment); binary-search the largest F within
    budget. Integral by total unimodularity; NetworkX network simplex, not CP-SAT."""
    import networkx as nx
    edges, s, t, unit, inc, budget = _expansion(data)

    def cheapest(flow_value):
        g = nx.DiGraph()
        g.add_node(s, demand=-flow_value)
        g.add_node(t, demand=flow_value)
        for i, (u, v, c) in enumerate(edges):
            mid = f"__{i}"
            g.add_edge(u, mid, capacity=c, weight=0)
            g.add_edge(u, mid + "x", capacity=inc, weight=unit[(u, v)])
            g.add_edge(mid, v, capacity=c, weight=0)
            g.add_edge(mid + "x", v, capacity=inc, weight=0)
        try:
            return nx.min_cost_flow_cost(g)
        except nx.NetworkXUnfeasible:
            return None
    lo, hi = 0, sum(c + inc for u, v, c in edges if u == s)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        cost = cheapest(mid)
        if cost is not None and cost <= budget:
            lo = mid
        else:
            hi = mid - 1
    return lo


def greedy_solve(data, budget):
    edges, s, t, unit, inc, money = _expansion(data)
    increments = {f"{u}->{v}": 0 for u, v, _ in edges}
    steps = 0
    while steps < 2000:
        steps += 1
        current = [(u, v, c + increments[f"{u}->{v}"]) for u, v, c in edges]
        value, flow = edmonds_karp(current, s, t)
        side = _reach(_merged(current), flow, s)
        options = sorted((unit[(u, v)], u, v) for u, v, _ in edges
                         if u in side and v not in side and increments[f"{u}->{v}"] < inc
                         and unit[(u, v)] <= money)
        if not options:
            break
        cost, u, v = options[0]
        increments[f"{u}->{v}"] += 1
        money -= cost
    value, spent = expansion_value(data, increments)
    return answer({"increments": increments, "flow_value": value, "spent": spent},
                  {"rule": "one unit on the cheapest edge of the current minimum cut, repeated", "steps": steps})


def greedy_verify(data, output, certificate):
    value, spent = expansion_value(data, output["increments"])
    return {"within_budget_and_bounds": value is not None, "flow_value_recomputed": value == output["flow_value"],
            "spend_recomputed": spent == output["spent"]}


def expansion_instance(seed):
    data = _network(seed, costs=True)
    return data, {"optimum": expansion_truth(data)}


def expansion_score(data, truth, output):
    if not isinstance(output, dict) or "increments" not in output:
        return {"quality": 0.0, "category": "abstain"}
    value, _ = expansion_value(data, output["increments"])
    if value is None:
        return {"quality": -1.0, "category": "wrong"}          # over budget or out of bounds
    q = value / truth["optimum"] if truth["optimum"] else 1.0
    return {"quality": q, "category": "correct" if value == truth["optimum"] else "wrong"}


def uniform_spread(data):
    """Baseline: spread the budget one unit at a time round-robin over source and sink edges."""
    edges, s, t, unit, inc, money = _expansion(data)
    increments = {f"{u}->{v}": 0 for u, v, _ in edges}
    ring = [(u, v) for u, v, _ in edges if u == s or v == t]
    progress = True
    while progress:
        progress = False
        for u, v in ring:
            key = f"{u}->{v}"
            if unit[(u, v)] <= money and increments[key] < inc:
                increments[key] += 1
                money -= unit[(u, v)]
                progress = True
    return {"increments": increments}


def compile_model(data):
    """Network + costs + budget -> the integer model of the existing ``optimize`` family."""
    edges, s, t, unit, inc, budget = _expansion(data)
    variables, constraints, nodes = {}, [], sorted({n for e in edges for n in e[:2]})
    names = []
    for i, (u, v, c) in enumerate(edges):
        f, x = f"f{i}", f"x{i}"
        variables[f] = [0, c + inc]
        variables[x] = [0, inc]
        constraints.append({"coefficients": {f: 1, x: -1}, "op": "<=", "rhs": c,
                            "requirement_id": f"capacity:{u}->{v}"})
        names.append((f, x, u, v))
    for n in nodes:
        if n in (s, t):
            continue
        coefficients = {}
        for f, _, u, v in names:
            if v == n:
                coefficients[f] = coefficients.get(f, 0) + 1
            if u == n:
                coefficients[f] = coefficients.get(f, 0) - 1
        constraints.append({"coefficients": coefficients, "op": "==", "rhs": 0, "requirement_id": f"conservation:{n}"})
    constraints.append({"coefficients": {x: unit[(u, v)] for _, x, u, v in names}, "op": "<=", "rhs": budget,
                        "requirement_id": "budget"})
    objective = {}
    for f, _, u, v in names:
        if u == s:
            objective[f] = objective.get(f, 0) + 1
        if v == s:
            objective[f] = objective.get(f, 0) - 1
    return {"variables": variables, "constraints": constraints, "objective": {"coefficients": objective, "sense": "max"}}, \
        {x: f"{u}->{v}" for _, x, u, v in names}


def compile_solve(data, budget):
    model, decode = compile_model(data)
    if len(model["variables"]) > 64:
        return answer(None, {"variables": len(model["variables"])}, status="ABSTAIN",
                      missing=["network exceeds the 64-variable ceiling of the optimisation family"])
    return answer({"model": model, "decode": decode},
                  {"variables": len(model["variables"]), "constraints": len(model["constraints"]),
                   "translation": "flow f_e <= c_e + x_e; conservation at every relay; sum unit_e x_e <= budget; "
                                  "maximise net outflow of the source"})


def compile_verify(data, output, certificate):
    edges, s, t, unit, inc, budget = _expansion(data)
    model = output["model"]
    relays = {n for e in edges for n in e[:2]} - {s, t}
    conservation = [c for c in model["constraints"] if c["requirement_id"].startswith("conservation:")]
    capacity = [c for c in model["constraints"] if c["requirement_id"].startswith("capacity:")]
    return {"one_capacity_row_per_edge": len(capacity) == len(edges),
            "one_conservation_row_per_relay": {c["requirement_id"][13:] for c in conservation} == relays,
            "budget_row": any(c["requirement_id"] == "budget" and c["rhs"] == budget for c in model["constraints"]),
            "decode_covers_every_increment": set(output["decode"]) == {k for k in model["variables"] if k.startswith("x")},
            "maximise": model["objective"]["sense"] == "max"}


def compile_score(data, truth, output):
    if not isinstance(output, dict) or "model" not in output:
        return {"quality": 0.0, "category": "abstain"}
    ok = all(compile_verify(data, output, {}).values())
    return {"quality": 1.0 if ok else -1.0, "category": "correct" if ok else "wrong"}


def _common(**kw):
    return dict(source_provenance="Ford-Fulkerson/Edmonds-Karp; NetworkX (BSD-3) maximum_flow and min-cost flow",
                buildability="BUILDABLE_NOW", memory_model="stateless", learning_rule="none (competence settles "
                "per geometry through GREG outcomes)", confidence_semantics="exact within the supplied network",
                resource_profile="O(V E^2) worst case; <= 400 edges", lineage=LINEAGE, **kw)


INTELLIGENCES = [
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.graph.max_flow", version="1.0.0", family="flow_maxflow", layer=3,
            operation="max_flow", epistemic_class="optimization", subgeometry="s-t max flow / min cut",
            native_representation="directed capacitated graph", required_inputs=("edges", "source", "sink"),
            output_contract={"value": "int", "cut_edges": "[[u, v, capacity]]", "flow": "[[u, v, flow]]"},
            algorithm_or_runtime="networkx.maximum_flow (preflow-push) + minimum_cut", parameters={},
            composition_inputs=("network",), composition_outputs=("value", "cut_edges"),
            evidence_type="optimality_certificate",
            verification_method="arithmetic capacity/conservation check, cut capacity == value, residual BFS",
            latency_profile="milliseconds at benchmark size", known_strengths=("exact", "certifies control points"),
            known_failure_modes=("supplied capacities may be wrong", "single commodity only"),
            counterindications=("multi-commodity or nonlinear flows",), abstention_conditions=("invalid graph",),
            benchmark_suite="general sparse digraphs (14-26 relays), seeds 0-9 dev / 1000-1029 held out",
            baseline="min(capacity out of source, capacity into sink) - the bound read off without flow "
                     "reasoning (greedy augmentation without undo is kept as maxflow_greedy_paths: on these "
                     "digraphs it matched the optimum on every development seed)",
            competitor="linear program (SciPy HiGHS)", dependency="networkx", **_common()),
        solve=maxflow_solve, verify=maxflow_verify, instance=maxflow_instance, score=maxflow_score,
        baseline=maxflow_trivial_cut, competitor=maxflow_lp),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.graph.reinforce_min_cut", version="1.0.0", family="flow_reinforce_greedy",
            layer=3, operation="reinforce_min_cut", epistemic_class="optimization",
            subgeometry="budgeted capacity expansion (heuristic)", native_representation="graph + unit costs + budget",
            required_inputs=("edges", "source", "sink", "unit_cost", "max_increment", "budget"),
            output_contract={"increments": "{u->v: int}", "flow_value": "int", "spent": "int"},
            algorithm_or_runtime="iterated cheapest-edge-on-min-cut, Edmonds-Karp each step",
            parameters={"unit_step": 1}, composition_inputs=("network",), composition_outputs=("increments",),
            evidence_type="heuristic_trace",
            verification_method="budget/bounds check and max-flow recomputation of the reinforced network",
            latency_profile="O(budget) max-flow solves", known_strengths=("fast", "uses control-point structure"),
            known_failure_modes=("wastes budget when several minimum cuts tie", "myopic one-unit steps"),
            counterindications=("problems needing a certified optimum",), abstention_conditions=("invalid input",),
            benchmark_suite="layered relay networks with unit costs, seeds 0-9 dev / 1000-1029 held out",
            baseline="round-robin spread over source and sink edges",
            competitor="exact optimum via graph_then_allocate composition (compile + CP-SAT)", **_common()),
        solve=greedy_solve, verify=greedy_verify, instance=expansion_instance, score=expansion_score,
        baseline=uniform_spread, competitor=lambda data: _composed_expansion(data)),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.graph.capacity_expansion_compiler", version="1.0.0", family="flow_capacity_plan",
            layer=3, operation="compile_capacity_expansion", epistemic_class="optimization",
            subgeometry="graph -> integer program translation", native_representation="graph + unit costs + budget",
            required_inputs=("edges", "source", "sink", "unit_cost", "max_increment", "budget"),
            output_contract={"model": "optimize-family model", "decode": "{x_i: 'u->v'}"},
            algorithm_or_runtime="deterministic translation", parameters={},
            composition_inputs=("network",), composition_outputs=("model", "decode"),
            evidence_type="exact_calculation",
            verification_method="structural re-derivation: one capacity row per edge, one conservation row per relay",
            latency_profile="microseconds", known_strengths=("lossless translation", "typed slots"),
            known_failure_modes=("networks above the optimiser's 64-variable ceiling abstain",),
            counterindications=("multi-commodity networks",), abstention_conditions=("> 64 model variables",),
            benchmark_suite="structural translation checks on the same networks",
            baseline="none (no standalone decision)", competitor="none (no standalone decision)",
            standalone_decision=False, **_common()),
        solve=compile_solve, verify=compile_verify, instance=expansion_instance, score=compile_score,
        baseline=lambda data: None, competitor=lambda data: None),
]


def _composed_expansion(data):
    """In-process twin of graph_then_allocate for the greedy genome's admission competitor."""
    from greg.cognition.solvers import optimization
    model, decode = compile_model(data)
    if len(model["variables"]) > 64:
        return None
    out = optimization(model, {"latency_limit": 10.0, "compute_limit": 100000})["output"]
    if out["solver_status"] not in ("OPTIMAL", "FEASIBLE"):
        return None
    return {"increments": {decode[x]: v for x, v in out["solution"].items() if x in decode}}
