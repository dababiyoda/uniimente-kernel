"""Network questions answered by open-source engines and accepted only on GREG's certificate.

Two functions Capability Genesis can form from installed packages (greg/mechanisms.py):

    graph.shortest_path   every distance from a source, and the path to an optional target
    graph.max_flow        the maximum flow from a source to a sink, and a minimum cut

The engines (NetworkX, SciPy's csgraph) are untrusted. GREG checks every answer itself, in
O(edges), sharing no code with either engine:

shortest path: the claimed predecessor chains are walked to give exact path weights D. If
    D(source) = 0 and D(v) <= D(u) + w for every edge out of a reached node, D is a feasible
    potential, so no path is shorter than D; the chains realise D, so D is exact. The same
    inequality closes the reached set: a node outside it has no path from the source.
max flow: capacities and conservation hold, and the residual graph has no path from source
    to sink. Its reachable side is then a cut whose capacity equals the flow value.

Competence is enforced here, before an engine sees the input: nonnegative finite weights,
integer capacities, bounded size. Arithmetic is exact (fractions). With non-integer weights,
engines sum in floating point, so the certificate allows a relative 1e-12; with integers it
allows nothing. The oracles that qualify an engine (Bellman-Ford in fractions, brute-force
minimum cut) are GREG's and are never shown to it.
"""
from __future__ import annotations

from collections import defaultdict, deque
from fractions import Fraction
import heapq
import itertools
import math
import random
import re

from greg.capabilities import CapabilityError

MAX_NODES, MAX_EDGES = 5000, 20000
MAX_TOTAL_CAPACITY = 2**31 - 1          # SciPy's maximum_flow works in int32; one domain for both engines
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.:-]{0,63}$")


class CertificateError(Exception):
    """The engine's claim does not prove itself."""


def _invalid(why: str):
    # Wording deliberately avoids the capability-fault markers: a bad request is not a broken engine.
    return CapabilityError(f"network request invalid: {why}")


def _number(value, *, integer: bool):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _invalid(f"{value!r} is not a number")
    if isinstance(value, float) and not math.isfinite(value):
        raise _invalid(f"{value!r} is not finite")
    if value < 0:
        raise _invalid("negative weights are outside this function's competence (no Bellman-Ford engine is "
                       "qualified)" if not integer else "capacities must be nonnegative")
    if integer:
        if isinstance(value, float):
            if not value.is_integer():
                raise _invalid("capacities must be integers")
            value = int(value)
        if value > MAX_TOTAL_CAPACITY:
            raise _invalid("capacity exceeds 2^31-1")
    return value


def _nodes(params, edges) -> list:
    nodes = set(params.get("nodes") or [])
    for u, v, _ in edges:
        nodes.update((u, v))
    for n in nodes:
        if not isinstance(n, str) or not NAME.match(n):
            raise _invalid(f"node name {n!r} must be 1-64 letters, digits, spaces or _.:-")
    if len(nodes) > MAX_NODES:
        raise _invalid(f"more than {MAX_NODES} nodes")
    return sorted(nodes)


def _edges(params, *, integer: bool) -> list:
    edges = params.get("edges")
    if not isinstance(edges, list) or len(edges) > MAX_EDGES:
        raise _invalid(f"edges must be a list of at most {MAX_EDGES} [from, to, number]")
    out = []
    for e in edges:
        if not isinstance(e, (list, tuple)) or len(e) != 3:
            raise _invalid(f"edge {e!r} must be [from, to, number]")
        out.append([e[0], e[1], _number(e[2], integer=integer)])
    return out


def normalize_shortest(params: dict) -> dict:
    if not isinstance(params, dict):
        raise _invalid("parameters must be an object")
    edges = _edges(params, integer=False)
    nodes = _nodes(params, edges)
    directed = params.get("directed", True)
    if not isinstance(directed, bool):
        raise _invalid("directed must be true or false")
    source, target = params.get("source"), params.get("target")
    if source not in nodes:
        raise _invalid(f"source {source!r} is not a node")
    if target is not None and target not in nodes:
        raise _invalid(f"target {target!r} is not a node")
    return {"directed": directed, "nodes": nodes, "edges": edges, "source": source, "target": target}


def normalize_max_flow(params: dict) -> dict:
    if not isinstance(params, dict):
        raise _invalid("parameters must be an object")
    if params.get("directed", True) is not True:
        raise _invalid("maximum flow is defined here on directed arcs only; state each direction")
    edges = _edges(params, integer=True)
    nodes = _nodes(params, edges)
    source, sink = params.get("source"), params.get("sink")
    if source not in nodes or sink not in nodes:
        raise _invalid("source and sink must both be nodes")
    if source == sink:
        raise _invalid("source and sink must differ")
    arcs = defaultdict(int)
    loops = 0
    for u, v, c in edges:
        if u == v:
            loops += 1                    # a self-loop can carry no flow from source to sink
            continue
        arcs[u, v] += c                   # parallel arcs add capacity
    if sum(arcs.values()) > MAX_TOTAL_CAPACITY:
        raise _invalid("total capacity exceeds 2^31-1")
    return {"nodes": nodes, "arcs": [[u, v, c] for (u, v), c in sorted(arcs.items())], "source": source,
            "sink": sink, "dropped_self_loops": loops}


# -- engine runners: fixed GREG code executed in the candidate's isolated interpreter --------

RUNNERS = {
    "networkx.shortest_path": r'''
def solve(req):
    nx = MODULE
    g = nx.DiGraph() if req["directed"] else nx.Graph()
    g.add_nodes_from(req["nodes"])
    for u, v, w in req["edges"]:
        if g.has_edge(u, v):
            g[u][v]["weight"] = min(g[u][v]["weight"], w)
        else:
            g.add_edge(u, v, weight=w)
    pred, dist = nx.dijkstra_predecessor_and_distance(g, req["source"], weight="weight")
    # NetworkX lists every tied predecessor; across a zero-weight self-loop that includes the
    # node itself (the source becomes its own predecessor). Found by the frozen oracle.
    pred = {v: [p for p in ps if p != v] for v, ps in pred.items()}
    return {"distances": dist, "predecessors": {v: ps[0] for v, ps in pred.items() if ps}}
''',
    "scipy.shortest_path": r'''
def solve(req):
    import numpy as np
    from scipy.sparse import csr_matrix
    nodes = req["nodes"]
    index = {n: i for i, n in enumerate(nodes)}
    best = {}
    for u, v, w in req["edges"]:
        for a, b in ([(u, v)] if req["directed"] else [(u, v), (v, u)]):
            key = (index[a], index[b])
            best[key] = min(best.get(key, w), w)      # csr_matrix would sum parallel edges
    keys = list(best)
    m = csr_matrix((np.array([best[k] for k in keys], dtype=float),
                    (np.array([k[0] for k in keys], dtype=np.int64), np.array([k[1] for k in keys], dtype=np.int64))),
                   shape=(len(nodes), len(nodes)))
    dist, pred = MODULE.dijkstra(m, directed=True, indices=index[req["source"]], return_predecessors=True)
    return {"distances": {nodes[i]: float(d) for i, d in enumerate(dist) if np.isfinite(d)},
            "predecessors": {nodes[i]: nodes[p] for i, p in enumerate(pred) if p >= 0}}
''',
    "networkx.max_flow": r'''
def solve(req):
    nx = MODULE
    g = nx.DiGraph()
    g.add_nodes_from(req["nodes"])
    for u, v, c in req["arcs"]:
        g.add_edge(u, v, capacity=c)
    value, flow = nx.maximum_flow(g, req["source"], req["sink"], capacity="capacity")
    return {"value": value, "flows": [[u, v, f] for u, row in flow.items() for v, f in row.items() if f]}
''',
    "scipy.max_flow": r'''
def solve(req):
    import numpy as np
    from scipy.sparse import csr_matrix
    nodes = req["nodes"]
    index = {n: i for i, n in enumerate(nodes)}
    m = csr_matrix((np.array([c for _, _, c in req["arcs"]], dtype=np.int32),
                    (np.array([index[u] for u, _, _ in req["arcs"]], dtype=np.int64),
                     np.array([index[v] for _, v, _ in req["arcs"]], dtype=np.int64))),
                   shape=(len(nodes), len(nodes)))
    result = MODULE.maximum_flow(m, index[req["source"]], index[req["sink"]])
    net = result.flow.tocoo()                         # skew-symmetric net flow; positive entries are arc flows
    return {"value": int(result.flow_value),
            "flows": [[nodes[i], nodes[j], int(x)] for i, j, x in zip(net.row, net.col, net.data) if x > 0]}
''',
}


# -- certificates (GREG-owned; exact) ---------------------------------------------------------

def _exactly(value) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise CertificateError(f"{value!r} is not a finite number")
    return Fraction(value)


def _plain(value: Fraction):
    return int(value) if value.denominator == 1 else float(value)


def _min_weights(req) -> dict:
    best = {}
    for u, v, w in req["edges"]:
        for a, b in ([(u, v)] if req["directed"] else [(u, v), (v, u)]):
            w = Fraction(w)
            if (a, b) not in best or w < best[a, b]:
                best[a, b] = w
    return best


def certify_shortest(req: dict, claim) -> dict:
    if not isinstance(claim, dict) or not isinstance(claim.get("distances"), dict) \
            or not isinstance(claim.get("predecessors"), dict):
        raise CertificateError("the claim must carry distances and predecessors")
    best = _min_weights(req)
    integral = all(w.denominator == 1 for w in best.values())
    tolerance = (lambda x: Fraction(0)) if integral else (lambda x: Fraction(1, 10**12) * max(1, abs(x)))
    nodes, source = set(req["nodes"]), req["source"]
    claimed, pred = claim["distances"], claim["predecessors"]
    reached = set(claimed)
    if not reached <= nodes:
        raise CertificateError(f"distances name unknown nodes {sorted(reached - nodes)[:3]}")
    if source not in reached or source in pred:
        raise CertificateError("the source must be reached at distance 0 with no predecessor")
    exact = {source: Fraction(0)}
    for v in sorted(reached):
        chain, x = [], v
        while x not in exact:
            if x not in reached or x not in pred or len(chain) > len(nodes):
                raise CertificateError(f"no predecessor chain from {v} back to the source")
            if (pred[x], x) not in best:
                raise CertificateError(f"claimed predecessor edge {pred[x]} -> {x} is not in the graph")
            chain.append(x)
            x = pred[x]
        for y in reversed(chain):
            exact[y] = exact[pred[y]] + best[pred[y], y]
    for v in reached:
        if abs(_exactly(claimed[v]) - exact[v]) > tolerance(exact[v]):
            raise CertificateError(f"claimed distance to {v} differs from the weight of its own path")
    for (a, b), w in best.items():
        if a not in reached:
            continue
        if b not in reached:
            raise CertificateError(f"{b} is reachable through {a} but was claimed unreachable")
        if exact[b] > exact[a] + w + tolerance(exact[a] + w):
            raise CertificateError(f"edge {a} -> {b} gives a shorter path to {b}")
    target = req.get("target")
    path = None
    if target in reached:
        path, x = [target], target
        while x != source:
            x = pred[x]
            path.append(x)
        path.reverse()
    return {"certified": True, "source": source, "target": target,
            "reachable": (target in reached) if target is not None else None,
            "distance": _plain(exact[target]) if target in reached else None, "path": path,
            "distances": {v: _plain(exact[v]) for v in sorted(reached)},
            "unreachable": sorted(nodes - reached),
            "certificate": {"kind": "feasible potentials realised by predecessor chains",
                            "edges_checked": len(best), "arithmetic": "exact fractions",
                            "tolerance": "none (integer weights)" if integral else "relative 1e-12 (non-integer weights)"}}


def certify_max_flow(req: dict, claim) -> dict:
    if not isinstance(claim, dict) or not isinstance(claim.get("flows"), list):
        raise CertificateError("the claim must carry arc flows")
    cap = {(u, v): c for u, v, c in req["arcs"]}
    flow = {}
    for item in claim["flows"]:
        if not isinstance(item, list) or len(item) != 3:
            raise CertificateError(f"flow entry {item!r} must be [from, to, amount]")
        u, v, x = item
        if isinstance(x, bool) or not isinstance(x, int):
            raise CertificateError(f"flow on {u} -> {v} is not an integer")
        if (u, v) not in cap or (u, v) in flow:
            raise CertificateError(f"flow on {u} -> {v} names no arc or repeats one")
        if not 0 <= x <= cap[u, v]:
            raise CertificateError(f"flow {x} on {u} -> {v} breaks its capacity {cap[u, v]}")
        flow[u, v] = x
    balance = defaultdict(int)
    for (u, v), x in flow.items():
        balance[u] -= x
        balance[v] += x
    source, sink = req["source"], req["sink"]
    for n in req["nodes"]:
        if n not in (source, sink) and balance[n]:
            raise CertificateError(f"flow is not conserved at {n}")
    value = balance[sink]
    if -balance[source] != value or claim.get("value") != value:
        raise CertificateError("the claimed value is not the flow that leaves the source")
    residual = defaultdict(list)
    for (u, v), c in cap.items():
        if flow.get((u, v), 0) < c:
            residual[u].append(v)
        if flow.get((u, v), 0) > 0:
            residual[v].append(u)
    side, queue = {source}, deque([source])
    while queue:
        for v in residual[queue.popleft()]:
            if v not in side:
                side.add(v)
                queue.append(v)
    if sink in side:
        raise CertificateError("an augmenting path remains; the flow is not maximum")
    cut = sorted((u, v) for (u, v) in cap if u in side and v not in side)
    if sum(cap[e] for e in cut) != value:
        raise CertificateError("the residual cut does not match the flow value")
    return {"certified": True, "source": source, "sink": sink, "value": value,
            "flows": sorted([u, v, x] for (u, v), x in flow.items() if x),
            "min_cut": {"source_side": sorted(side), "arcs": [list(e) for e in cut],
                        "capacity": sum(cap[e] for e in cut)},
            "dropped_self_loops": req["dropped_self_loops"],
            "certificate": {"kind": "no augmenting path in the residual graph; equal-capacity cut",
                            "arcs_checked": len(cap), "arithmetic": "exact integers"}}


# -- frozen oracles (independent of every engine) -------------------------------------------

def bellman_ford(req: dict) -> dict:
    """Reference distances in exact fractions; O(VE); for oracle-sized graphs only."""
    best = _min_weights(req)
    dist = {req["source"]: Fraction(0)}
    for _ in range(len(req["nodes"])):
        changed = False
        for (a, b), w in best.items():
            if a in dist and (b not in dist or dist[a] + w < dist[b]):
                dist[b] = dist[a] + w
                changed = True
        if not changed:
            break
    return {v: _plain(d) for v, d in sorted(dist.items())}


def min_cut_brute_force(req: dict) -> int:
    """The minimum s-t cut by enumerating every source side; independent of any flow algorithm."""
    others = [n for n in req["nodes"] if n not in (req["source"], req["sink"])]
    if len(others) > 12:
        raise ValueError("brute-force cut is for oracle-sized graphs only")
    best = None
    for k in range(len(others) + 1):
        for chosen in itertools.combinations(others, k):
            side = {req["source"], *chosen}
            total = sum(c for u, v, c in req["arcs"] if u in side and v not in side)
            best = total if best is None else min(best, total)
    return best


FIXED_SHORTEST = [
    ("zero-weight", {"edges": [["a", "b", 0], ["b", "c", 0], ["a", "c", 1]], "source": "a", "target": "c"}),
    ("parallel-min", {"edges": [["a", "b", 5], ["a", "b", 2], ["b", "c", 1]], "source": "a", "target": "c"}),
    ("self-loop", {"edges": [["a", "a", 0], ["a", "b", 3]], "source": "a", "target": "b"}),
    ("unreachable", {"edges": [["a", "b", 1], ["c", "d", 1]], "source": "a", "target": "d"}),
    ("lone-source", {"edges": [], "nodes": ["only"], "source": "only", "target": "only"}),
    ("undirected", {"edges": [["a", "b", 2], ["c", "b", 2], ["a", "c", 7]], "source": "c", "target": "a",
                    "directed": False}),
    ("fractional", {"edges": [["s", "x", 0.25], ["x", "t", 0.5], ["s", "t", 0.75], ["s", "y", 0.125],
                              ["y", "t", 0.5]], "source": "s", "target": "t"}),
    ("tie", {"edges": [["s", "x", 1], ["x", "t", 1], ["s", "y", 1], ["y", "t", 1]], "source": "s", "target": "t"}),
]

FIXED_FLOW = [
    ("textbook", {"edges": [["s", "v1", 16], ["s", "v2", 13], ["v1", "v3", 12], ["v2", "v1", 4], ["v2", "v4", 14],
                            ["v3", "v2", 9], ["v3", "t", 20], ["v4", "v3", 7], ["v4", "t", 4]],
                  "source": "s", "sink": "t"}),
    ("parallel-add", {"edges": [["s", "a", 3], ["s", "a", 4], ["a", "t", 10]], "source": "s", "sink": "t"}),
    ("antiparallel", {"edges": [["s", "a", 5], ["a", "s", 3], ["a", "t", 4]], "source": "s", "sink": "t"}),
    ("cut-off", {"edges": [["s", "a", 5], ["b", "t", 5]], "source": "s", "sink": "t"}),
    ("zero-capacity", {"edges": [["s", "a", 0], ["a", "t", 9], ["s", "t", 1]], "source": "s", "sink": "t"}),
    ("self-loop", {"edges": [["s", "s", 7], ["s", "t", 2]], "source": "s", "sink": "t"}),
]


def _random_graph(rng, n, m, weight):
    names = [f"n{i}" for i in range(n)]
    return names, [[rng.choice(names), rng.choice(names), weight(rng)] for _ in range(m)]


def oracle_shortest(seed: int) -> list[dict]:
    rng = random.Random(seed)
    cases = [{"name": name, "input": params} for name, params in FIXED_SHORTEST]
    for index in range(6):
        n = rng.choice([2, 5, 12, 30, rng.randint(3, 40)])
        weight = (lambda r: r.randint(0, 20)) if index % 2 == 0 else (lambda r: r.randint(0, 40) / 4)
        names, edges = _random_graph(rng, n, rng.randint(0, 3 * n), weight)
        cases.append({"name": f"random{index}", "input": {"edges": edges, "nodes": names, "source": names[0],
                                                          "target": names[-1], "directed": index != 3}})
    for case in cases:
        case["expected"] = {"distances": bellman_ford(normalize_shortest(case["input"]))}
    return cases


def oracle_max_flow(seed: int) -> list[dict]:
    rng = random.Random(seed)
    cases = [{"name": name, "input": params} for name, params in FIXED_FLOW]
    for index in range(6):
        n = rng.randint(2, 10)
        names, edges = _random_graph(rng, n, rng.randint(0, 4 * n), lambda r: r.randint(0, 10))
        cases.append({"name": f"random{index}", "input": {"edges": edges, "nodes": names, "source": names[0],
                                                          "sink": names[-1]}})
    for case in cases:
        case["expected"] = {"value": min_cut_brute_force(normalize_max_flow(case["input"]))}
    return cases


def judge_shortest(answer: dict, expected: dict) -> bool:
    return answer["distances"] == expected["distances"]


def judge_max_flow(answer: dict, expected: dict) -> bool:
    return answer["value"] == expected["value"]


# -- scale probes and the simplest local implementation each engine must be compared with ----

def size(req: dict) -> dict:
    return {"nodes": len(req["nodes"]), "edges": len(req.get("edges") or req.get("arcs") or [])}


def probe_shortest(seed: int) -> dict:
    rng = random.Random(seed ^ 0x5A5A)
    names, edges = _random_graph(rng, 2000, 10000, lambda r: r.randint(1, 100))
    return {"edges": edges, "nodes": names, "source": names[0], "target": names[-1]}


def probe_max_flow(seed: int) -> dict:
    rng = random.Random(seed ^ 0xA5A5)
    names, edges = _random_graph(rng, 300, 3000, lambda r: r.randint(1, 50))
    return {"edges": edges, "nodes": names, "source": names[0], "sink": names[-1]}


def local_dijkstra(req: dict) -> dict:
    """Binary-heap Dijkstra in plain Python: the simplest local alternative to depending on a package."""
    adjacency = defaultdict(list)
    for u, v, w in req["edges"]:                     # native numbers, as a local implementation would use
        adjacency[u].append((v, w))
        if not req["directed"]:
            adjacency[v].append((u, w))
    dist, heap = {req["source"]: 0}, [(0, req["source"])]
    while heap:
        d, u = heapq.heappop(heap)
        if d > dist[u]:
            continue
        for v, w in adjacency[u]:
            if v not in dist or d + w < dist[v]:
                dist[v] = d + w
                heapq.heappush(heap, (d + w, v))
    return {"distances": dict(sorted(dist.items()))}


def local_edmonds_karp(req: dict) -> dict:
    """Breadth-first augmenting paths in plain Python: the simplest local maximum-flow alternative."""
    residual = defaultdict(lambda: defaultdict(int))
    for u, v, c in req["arcs"]:
        residual[u][v] += c
    source, sink, value = req["source"], req["sink"], 0
    while True:
        parent, queue = {source: None}, deque([source])
        while queue and sink not in parent:
            u = queue.popleft()
            for v, c in residual[u].items():
                if c > 0 and v not in parent:
                    parent[v] = u
                    queue.append(v)
        if sink not in parent:
            return {"value": value}
        push, v = math.inf, sink
        while parent[v] is not None:
            push, v = min(push, residual[parent[v]][v]), parent[v]
        v = sink
        while parent[v] is not None:
            residual[parent[v]][v] -= push
            residual[v][parent[v]] += push
            v = parent[v]
        value += push
