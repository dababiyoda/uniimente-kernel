"""The cheapest network connecting every site, from open-source engines, accepted only on GREG's certificate.

One function Capability Genesis can form from installed packages (greg/mechanisms.py):

    graph.spanning_tree   the minimum spanning forest of an undirected weighted graph

The engines (NetworkX's Kruskal, SciPy's csgraph) are untrusted. GREG checks every answer itself, in
exact arithmetic, sharing no code with either:

    the claimed edges are input edges (at their lightest parallel weight) and contain no cycle;
    they span: every input edge joins two sites the forest already connects;
    they are minimum (cycle property): every edge left out weighs at least as much as the heaviest
    forest edge on the path it would close. Path maxima come from binary lifting, O((V + E) log V).

A tree has n - 1 edges whatever its weights, so adding one constant to every weight changes no
optimum; the SciPy runner uses this because csgraph reads a zero weight as "no edge". Competence:
at most 2,000 sites and 20,000 links, finite weights up to 1e9 in size. The frozen oracle (brute
force over every edge subset) is GREG's and is never shown to an engine.
"""
from __future__ import annotations

from collections import defaultdict
from fractions import Fraction
import itertools
import math
import random
import re

from greg.capabilities import CapabilityError

MAX_NODES, MAX_EDGES, MAX_WEIGHT = 2000, 20000, 10**9
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.:-]{0,63}$")


class CertificateError(Exception):
    """The engine's claim does not prove itself."""


def _invalid(why: str):
    # Wording deliberately avoids the capability-fault markers: a bad request is not a broken engine.
    return CapabilityError(f"spanning request invalid: {why}")


def normalize_spanning(params: dict) -> dict:
    if not isinstance(params, dict):
        raise _invalid("parameters must be an object")
    edges = params.get("edges")
    if not isinstance(edges, list) or len(edges) > MAX_EDGES:
        raise _invalid(f"edges must be a list of at most {MAX_EDGES} [site, site, weight]")
    best, nodes, loops = {}, set(params.get("nodes") or []), 0
    for e in edges:
        if not isinstance(e, (list, tuple)) or len(e) != 3:
            raise _invalid(f"edge {e!r} must be [site, site, weight]")
        u, v, w = e
        if isinstance(w, bool) or not isinstance(w, (int, float)) or not math.isfinite(w) or abs(w) > MAX_WEIGHT:
            raise _invalid(f"weight {w!r} must be a finite number up to 1e9 in size")
        nodes.update((u, v))
        if u == v:
            loops += 1                       # a self-loop never belongs to a tree
            continue
        key = (min(u, v), max(u, v)) if isinstance(u, str) and isinstance(v, str) else (u, v)
        best[key] = min(best.get(key, w), w)
    for n in nodes:
        if not isinstance(n, str) or not NAME.match(n):
            raise _invalid(f"site name {n!r} must be 1-64 letters, digits, spaces or _.:-")
    if len(nodes) > MAX_NODES:
        raise _invalid(f"more than {MAX_NODES} sites")
    return {"nodes": sorted(nodes), "edges": [[u, v, w] for (u, v), w in sorted(best.items())],
            "dropped_self_loops": loops}


# -- engine runners: fixed GREG code executed in the candidate's isolated interpreter --------

RUNNERS = {
    "networkx.spanning_tree": r'''
def solve(req):
    nx = MODULE
    g = nx.Graph()
    g.add_nodes_from(req["nodes"])
    for u, v, w in req["edges"]:
        g.add_edge(u, v, weight=w)
    forest = nx.minimum_spanning_tree(g, weight="weight", algorithm="kruskal")
    return {"edges": [[u, v, d["weight"]] for u, v, d in forest.edges(data=True)]}
''',
    "scipy.spanning_tree": r'''
def solve(req):
    import numpy as np
    from scipy.sparse import csr_matrix
    nodes = req["nodes"]
    index = {n: i for i, n in enumerate(nodes)}
    edges = req["edges"]
    if not edges:
        return {"edges": []}
    # csgraph reads 0 as "no edge"; a tree's edge count is fixed, so a constant shift keeps every optimum.
    shift = 1 - min(w for _, _, w in edges) if min(w for _, _, w in edges) <= 0 else 0
    m = csr_matrix((np.array([w + shift for _, _, w in edges], dtype=float),
                    (np.array([index[u] for u, _, _ in edges], dtype=np.int64),
                     np.array([index[v] for _, v, _ in edges], dtype=np.int64))), shape=(len(nodes), len(nodes)))
    weight = {}
    for u, v, w in edges:
        weight[index[u], index[v]] = weight[index[v], index[u]] = w
    tree = MODULE.minimum_spanning_tree(m).tocoo()
    return {"edges": [[nodes[i], nodes[j], weight[i, j]] for i, j in zip(tree.row, tree.col)]}
''',
}


# -- certificate (GREG-owned; exact) ----------------------------------------------------------

def _plain(value: Fraction):
    return int(value) if value.denominator == 1 else float(value)


class _Union:
    def __init__(self, items):
        self.parent = {x: x for x in items}

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def join(self, a, b) -> bool:
        a, b = self.find(a), self.find(b)
        if a == b:
            return False
        self.parent[a] = b
        return True


def certify_spanning(req: dict, claim) -> dict:
    if not isinstance(claim, dict) or not isinstance(claim.get("edges"), list):
        raise CertificateError("the claim must carry the forest's edges")
    weight = {}
    for u, v, w in req["edges"]:
        weight[u, v] = weight[v, u] = Fraction(w)
    forest, union, adjacency = [], _Union(req["nodes"]), defaultdict(list)
    for item in claim["edges"]:
        if not isinstance(item, list) or len(item) != 3:
            raise CertificateError(f"edge {item!r} must be [site, site, weight]")
        u, v, _ = item
        if (u, v) not in weight:
            raise CertificateError(f"{u} - {v} is not a link in the network")
        if not union.join(u, v):
            raise CertificateError(f"{u} - {v} closes a cycle; the claim is not a forest")
        forest.append((u, v, weight[u, v]))
        adjacency[u].append((v, weight[u, v]))
        adjacency[v].append((u, weight[u, v]))
    for u, v, _ in req["edges"]:
        if union.find(u) != union.find(v):
            raise CertificateError(f"{u} and {v} are linked in the network but not by the forest")
    # Binary lifting over the rooted forest: up[k][x] and the heaviest edge on that 2^k climb.
    parent, depth, up_weight = {}, {}, {}
    for root in req["nodes"]:
        if root in depth:
            continue
        depth[root], parent[root], up_weight[root] = 0, root, Fraction(-10**30)
        stack = [root]
        while stack:
            x = stack.pop()
            for y, w in adjacency[x]:
                if y not in depth:
                    depth[y], parent[y], up_weight[y] = depth[x] + 1, x, w
                    stack.append(y)
    levels = max(1, max(depth.values(), default=0).bit_length())
    up, heavy = [parent], [up_weight]
    for k in range(1, levels):
        prev_up, prev_heavy = up[-1], heavy[-1]
        up.append({x: prev_up[prev_up[x]] for x in prev_up})
        heavy.append({x: max(prev_heavy[x], prev_heavy[prev_up[x]]) for x in prev_up})

    def path_max(a, b):
        best = Fraction(-10**30)
        if depth[a] < depth[b]:
            a, b = b, a
        diff, k = depth[a] - depth[b], 0
        while diff:
            if diff & 1:
                best, a = max(best, heavy[k][a]), up[k][a]
            diff, k = diff >> 1, k + 1
        if a == b:
            return best
        for k in reversed(range(levels)):
            if up[k][a] != up[k][b]:
                best = max(best, heavy[k][a], heavy[k][b])
                a, b = up[k][a], up[k][b]
        return max(best, heavy[0][a], heavy[0][b])

    in_forest = {(u, v) for u, v, _ in forest} | {(v, u) for u, v, _ in forest}
    for u, v, w in req["edges"]:
        if (u, v) not in in_forest and Fraction(w) < path_max(u, v):
            raise CertificateError(f"link {u} - {v} is cheaper than a forest edge on the path it would close")
    total = sum(w for _, _, w in forest)
    components = len({union.find(n) for n in req["nodes"]})
    return {"certified": True, "edges": sorted([u, v, _plain(w)] for u, v, w in forest), "total": _plain(total),
            "components": components, "connected": components == 1,
            "dropped_self_loops": req["dropped_self_loops"],
            "certificate": {"kind": "cycle property: every link left out weighs at least the heaviest forest edge "
                                    "on the path it would close", "links_checked": len(req["edges"]),
                            "arithmetic": "exact fractions"}}


# -- frozen oracle, judge, probe, local baseline ----------------------------------------------

def brute_force(req: dict) -> dict:
    """The lightest spanning forest over every edge subset; oracle-sized graphs only."""
    nodes, edges = req["nodes"], req["edges"]
    union = _Union(nodes)
    for u, v, _ in edges:
        union.join(u, v)
    size = len(nodes) - len({union.find(n) for n in nodes})
    if math.comb(len(edges), size) > 20000:
        raise ValueError("brute-force spanning forest is for oracle-sized graphs only")
    best = None
    for subset in itertools.combinations(edges, size):
        u2 = _Union(nodes)
        if all(u2.join(u, v) for u, v, _ in subset):
            total = sum(Fraction(w) for _, _, w in subset)
            best = total if best is None else min(best, total)
    return {"total": _plain(best if best is not None else Fraction(0))}


FIXED_SPANNING = [
    ("textbook", {"edges": [["a", "b", 4], ["a", "h", 8], ["b", "c", 8], ["b", "h", 11], ["c", "d", 7],
                            ["c", "f", 4], ["c", "i", 2], ["d", "e", 9], ["d", "f", 14], ["e", "f", 10],
                            ["f", "g", 2], ["g", "h", 1], ["g", "i", 6], ["h", "i", 7]]}),
    ("zero-and-negative", {"edges": [["a", "b", 0], ["b", "c", -3], ["a", "c", 1], ["c", "d", 0]]}),
    ("parallel-min", {"edges": [["a", "b", 5], ["b", "a", 2], ["b", "c", 1]]}),
    ("two-components", {"edges": [["a", "b", 1], ["c", "d", 2], ["d", "e", 1], ["c", "e", 3]]}),
    ("isolated-site", {"edges": [["a", "b", 1]], "nodes": ["a", "b", "z"]}),
    ("self-loop", {"edges": [["a", "a", -9], ["a", "b", 2]]}),
    ("fractional", {"edges": [["a", "b", 0.25], ["b", "c", 0.5], ["a", "c", 0.625]]}),
    ("ties", {"edges": [["a", "b", 1], ["b", "c", 1], ["a", "c", 1]]}),
]


def oracle_spanning(seed: int) -> list[dict]:
    rng = random.Random(seed)
    cases = [{"name": name, "input": params} for name, params in FIXED_SPANNING]
    for index in range(8):
        n = rng.randint(2, 7)
        names = [f"s{i}" for i in range(n)]
        value = (lambda r: r.randint(-5, 20)) if index % 2 else (lambda r: r.randint(0, 40) / 8)
        edges = [[rng.choice(names), rng.choice(names), value(rng)] for _ in range(rng.randint(0, 10))]
        cases.append({"name": f"random{index}", "input": {"edges": edges, "nodes": names}})
    for case in cases:
        case["expected"] = brute_force(normalize_spanning(case["input"]))
    return cases


def judge_spanning(answer: dict, expected: dict) -> bool:
    return answer["total"] == expected["total"]


def size(req: dict) -> dict:
    return {"nodes": len(req["nodes"]), "edges": len(req["edges"])}


def probe_spanning(seed: int) -> dict:
    rng = random.Random(seed ^ 0x6E6E)
    names = [f"n{i}" for i in range(MAX_NODES)]
    edges = [[names[i], names[rng.randrange(i)], rng.randint(1, 1000)] for i in range(1, MAX_NODES)]
    edges += [[rng.choice(names), rng.choice(names), rng.randint(1, 1000)] for _ in range(8000)]
    return {"edges": edges, "nodes": names}


def local_kruskal(req: dict) -> dict:
    """Kruskal with a plain union-find: the simplest local alternative to depending on a package."""
    union, total = _Union(req["nodes"]), 0
    for u, v, w in sorted(req["edges"], key=lambda e: e[2]):
        if union.join(u, v):
            total += w
    return {"total": total}
