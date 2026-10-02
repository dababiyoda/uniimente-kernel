"""Bounded network normalization and certificates extracted from PR #143.

Lineage: dababiyoda/uniimente-kernel commit 7105a7cbd013edd6bce88b9500e2b4477635c912,
greg/cognition/network.py, MIT (Copyright 2026 Alfonso Lopez). Engine selection,
permission, registration and persistence remain with current canonical owners.
Topology optimality and integer flows use exact arithmetic. Rendered distances
from floating inputs permit declared 1e-12 tolerance; original weights stay exact.
"""
from __future__ import annotations
from collections import defaultdict, deque
from fractions import Fraction
import heapq
import math
import re
from .contracts import CognitionError
from .contracts import digest, integer, number

MAX_NODES, MAX_EDGES = 128, 512
MAX_TOTAL_CAPACITY = 2**31 - 1
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.:-]{0,63}$")

class CertificateError(CognitionError):
    """An emitted candidate does not support its computational claim."""


def _invalid(why: str):
    # Wording deliberately avoids the capability-fault markers: a bad request is not a broken engine.
    return CognitionError(f"network request invalid: {why}")

def _number(value, *, integer: bool):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _invalid(f"{value!r} is not a number")
    if isinstance(value, float) and not math.isfinite(value):
        raise _invalid(f"{value!r} is not finite")
    if value < 0:
        raise _invalid("negative weights are outside this function's competence (no Bellman-Ford engine is "
                       "qualified)" if not integer else "capacities must be nonnegative")
    if not integer and value > 1e9:
        raise _invalid("edge weight exceeds the bounded 1e9 magnitude")
    if integer:
        if isinstance(value, float):
            if not value.is_integer():
                raise _invalid("capacities must be integers")
            value = int(value)
        if value > MAX_TOTAL_CAPACITY:
            raise _invalid("capacity exceeds 2^31-1")
    return value

def _nodes(params, edges) -> list:
    supplied = params.get("nodes", [])
    if not isinstance(supplied, list):
        raise _invalid("nodes must be a list of bounded names")
    names = supplied + [n for u, v, _ in edges for n in (u, v)]
    if any(not isinstance(n, str) or not NAME.fullmatch(n) for n in names):
        raise _invalid("node names must be 1-64 letters, digits, spaces or _.:-")
    nodes = set(names)
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
    if source not in reached or source in pred or set(pred) != reached - {source}:
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
        # Distances realised by source-weight predecessor chains are exact
        # Fractions even when their display is rounded. Edge optimality never
        # receives a rounding allowance that could conceal a suboptimal path.
        if exact[b] > exact[a] + w:
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
                            "tolerance": "none (integer weights)" if integral else "relative 1e-12 on displayed distances; exact edge optimality"}}

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
    if type(claim.get("value")) is not int or -balance[source] != value or claim.get("value") != value:
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


def shortest_request(data):
    allowed = {"edges", "nodes", "start", "goal", "source", "target", "directed"}
    if not isinstance(data, dict) or set(data) - allowed:
        raise CognitionError("restricted shortest-path fields required")
    if "start" in data and "source" in data or "goal" in data and "target" in data:
        raise CognitionError("use one source/target naming contract")
    req = normalize_shortest({"edges": data.get("edges"), "nodes": data.get("nodes", []),
                              "source": data.get("start", data.get("source")),
                              "target": data.get("goal", data.get("target")), "directed": data.get("directed", True)})
    if req["target"] is None:
        raise CognitionError("bounded target required for shortest_path")
    return req


def flow_request(data):
    if not isinstance(data, dict) or set(data) - {"edges", "nodes", "source", "sink", "directed"}:
        raise CognitionError("restricted flow fields required")
    return normalize_max_flow(data)


def _budget(req, geometry, *, flow=False):
    nodes, edges = len(req["nodes"]), len(req["arcs"] if flow else req["edges"])
    # Conservative static workload bounds supplement the existing worker CPU/deadline.
    work = max(1, nodes * edges * edges) if flow else max(1, (nodes + edges) * max(1, nodes.bit_length()))
    if work > integer(geometry["compute_limit"], low=1, high=100000):
        raise CognitionError("BUDGET_EXHAUSTED: network workload exceeds declared compute ceiling")


def _dijkstra(req):
    adjacency = defaultdict(list)
    for (u, v), weight in _min_weights(req).items():
        adjacency[u].append((v, weight))
    distance, predecessor, heap = {req["source"]: Fraction(0)}, {}, [(Fraction(0), req["source"])]
    while heap:
        value, node = heapq.heappop(heap)
        if value != distance[node]:
            continue
        for target, weight in adjacency[node]:
            candidate = value + weight
            if target not in distance or candidate < distance[target]:
                distance[target], predecessor[target] = candidate, node
                heapq.heappush(heap, (candidate, target))
    return {"distances": {n: _plain(v) for n, v in sorted(distance.items())}, "predecessors": predecessor}


def shortest(data, geometry):
    from .solvers import result
    req = shortest_request(data)
    _budget(req, geometry)
    claim = _dijkstra(req)
    target, source = req["target"], req["source"]
    path = []
    if target in claim["distances"]:
        path, node = [target], target
        while node != source:
            node = claim["predecessors"][node]
            path.append(node)
        path.reverse()
    output = {"path": path, "cost": claim["distances"].get(target), "reachable": target in claim["distances"]}
    return result(output, {"states": req["nodes"], "path": path, "cost": output["cost"], "model": data,
                           "normalized_model": req, "network_claim": claim, "input_digest": digest(data),
                           "engine": "bounded stdlib Dijkstra; PR143 certificate lineage", "limits": "nonnegative weights; parallel arcs use minimum; topology validity unverified"},
                  formal="VALID_CONDITIONAL_ON_MODEL")


def _edmonds_karp(req):
    residual = defaultdict(lambda: defaultdict(int))
    for u, v, capacity in req["arcs"]:
        residual[u][v] += capacity
    source, sink, value = req["source"], req["sink"], 0
    while True:
        parent, queue = {source: None}, deque([source])
        while queue and sink not in parent:
            node = queue.popleft()
            for target, capacity in residual[node].items():
                if capacity > 0 and target not in parent:
                    parent[target] = node
                    queue.append(target)
        if sink not in parent:
            flows = [[u, v, max(0, capacity - residual[u][v])] for u, v, capacity in req["arcs"]
                     if capacity - residual[u][v] > 0]
            side = set(parent)
            cut = [[u, v] for u, v, _ in req["arcs"] if u in side and v not in side]
            return {"value": value, "flows": flows,
                    "min_cut": {"source_side": sorted(side), "arcs": cut,
                                "capacity": sum(capacity for u, v, capacity in req["arcs"] if u in side and v not in side)}}
        amount, node = MAX_TOTAL_CAPACITY, sink
        while parent[node] is not None:
            amount, node = min(amount, residual[parent[node]][node]), parent[node]
        node = sink
        while parent[node] is not None:
            residual[parent[node]][node] -= amount
            residual[node][parent[node]] += amount
            node = parent[node]
        value += amount


def max_flow(data, geometry):
    from .solvers import result
    req = flow_request(data)
    _budget(req, geometry, flow=True)
    claim = _edmonds_karp(req)
    return result(claim, {"model": req, "source_model": data, "input_digest": digest(data), "flow": claim,
                          "engine": "bounded stdlib Edmonds-Karp", "solver_version": "greg-network/0.1",
                          "limits": "directed integer capacities; parallel capacities add; no empirical network claim"},
                  formal="VALID_CONDITIONAL_ON_MODEL")
