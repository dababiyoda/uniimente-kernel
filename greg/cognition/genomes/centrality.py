"""Layer 3 graph intelligence: the exact top-k betweenness-critical nodes of an undirected graph.

The 2026-10-21 coverage record (``docs/collaboration/MIND-COVERAGE-2026-10-21.json``) lists ``L3.graph.centrality``
as ABSENT. Stated, verifiable objective: return the k nodes with the largest exact shortest-path betweenness
(Freeman 1977; the number of shortest paths between other pairs that pass through a node, each pair counted once
and split by the number of its shortest paths), with their values. These are the nodes whose failure breaks the
most shortest routes - the critical relays of a dependency, communication or road network.

* ``graph_betweenness_topk`` (``betweenness_top_k``): Brandes' (2001) algorithm, batched over sources as sparse
  matrix products (SciPy CSR x dense NumPy blocks; the algebraic formulation of Kepner and Gilbert's graph
  algorithms in linear algebra): forward breadth-first levels count shortest paths, the backward sweep accumulates
  dependencies level by level. Exact; floating-point sums of integers and rationals.
* Verified by an independent pure-Python queue-based Brandes written here (no SciPy, no NetworkX): every returned
  value must equal the recomputed one, the k nodes must be distinct and in non-increasing order, and no unreturned node may have a
  larger betweenness than any returned one.
* Baseline: the k highest-degree nodes (the cheap proxy). Competitor: NetworkX's exact
  ``betweenness_centrality`` (BSD-3), the strongest deployable installed method (igraph and graph-tool are not
  installed; sampled NetworkX betweenness is faster but inexact, so it cannot answer the stated objective).

Read-only computation: no files, network, subprocesses or environment access; no output creates authority.
Development seeds 0-9 only.
"""
from __future__ import annotations

from collections import deque
import random

from .contract import Executable, GenomeError, IntelligenceGenome, answer, bounded_int

LINEAGE = ("INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION", "INTENT-20261007-VERIFIED-POLYINTELLIGENCE-LIFT",
           "INTENT-20261021-MIND-MAXIMUM-CONTINUATION section 4 (restore the full five-layer scope)",
           "docs/collaboration/MIND-COVERAGE-2026-10-21.json (L3.graph.centrality ABSENT)")
NAME_MAX = 64
BC_MAX_NODES, BC_MAX_EDGES, BC_NATIVE_NODES = 5000, 50000, 3000
BC_BATCH = 256
BC_REL_TOL = 1e-9


def _graph(data):
    """(sorted node names, {node: index}, edge index pairs, k)."""
    if not isinstance(data, dict):
        raise GenomeError("data must be a JSON object")
    edges = data.get("graph_edges")
    if not isinstance(edges, list) or not 1 <= len(edges) <= BC_MAX_EDGES:
        raise GenomeError(f"graph_edges: 1-{BC_MAX_EDGES} [u, v] pairs")
    seen = set()
    for e in edges:
        if not isinstance(e, list) or len(e) != 2:
            raise GenomeError("edge: [u, v]")
        u, v = e
        if not all(isinstance(x, str) and 0 < len(x) <= NAME_MAX for x in (u, v)) or u == v:
            raise GenomeError("edge ends: distinct node names of 1-64 characters")
        key = (u, v) if u < v else (v, u)
        if key in seen:
            raise GenomeError(f"duplicate edge {key}")
        seen.add(key)
    nodes = sorted({x for k in seen for x in k})
    if len(nodes) > BC_MAX_NODES:
        raise GenomeError(f"at most {BC_MAX_NODES} nodes")
    k = bounded_int(data.get("top_k"), low=1, high=len(nodes), name="top_k")
    index = {v: i for i, v in enumerate(nodes)}
    return nodes, index, sorted((index[u], index[v]) for u, v in seen), k


def _ranked(nodes, values, k):
    """Top k by value descending, ties by name ascending."""
    order = sorted(range(len(nodes)), key=lambda i: (-values[i], nodes[i]))[:k]
    return {"top": [nodes[i] for i in order], "betweenness": [float(values[i]) for i in order]}


def brandes_reference(n, pairs):
    """Independent reference (verifier, truth): queue-based Brandes in pure Python; undirected pair counts."""
    adj = [[] for _ in range(n)]
    for a, b in pairs:
        adj[a].append(b)
        adj[b].append(a)
    bc = [0.0] * n
    for s in range(n):
        stack, pred = [], [[] for _ in range(n)]
        sigma = [0] * n
        sigma[s] = 1
        dist = [-1] * n
        dist[s] = 0
        queue = deque([s])
        while queue:
            v = queue.popleft()
            stack.append(v)
            for w in adj[v]:
                if dist[w] < 0:
                    dist[w] = dist[v] + 1
                    queue.append(w)
                if dist[w] == dist[v] + 1:
                    sigma[w] += sigma[v]
                    pred[w].append(v)
        delta = [0.0] * n
        while stack:
            w = stack.pop()
            for v in pred[w]:
                delta[v] += sigma[v] / sigma[w] * (1 + delta[w])
            if w != s:
                bc[w] += delta[w]
    return [x / 2 for x in bc]


def _brandes_sparse(n, pairs):
    """Solver side: batched algebraic Brandes (SciPy CSR adjacency x dense NumPy source blocks)."""
    import numpy as np
    from scipy.sparse import csr_matrix
    rows = [a for a, b in pairs] + [b for a, b in pairs]
    cols = [b for a, b in pairs] + [a for a, b in pairs]
    adj = csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(n, n))
    bc = np.zeros(n)
    for start in range(0, n, BC_BATCH):
        sources = np.arange(start, min(n, start + BC_BATCH))
        b = len(sources)
        sigma = np.zeros((b, n))
        sigma[np.arange(b), sources] = 1.0
        reached = sigma > 0
        levels = [reached.copy()]
        frontier = sigma.copy()
        while True:
            nxt = np.asarray((adj @ frontier.T).T)            # path counts into every node from the frontier
            new = (nxt > 0) & ~reached
            if not new.any():
                break
            sigma[new] = nxt[new]
            reached |= new
            levels.append(new)
            frontier = np.where(new, nxt, 0.0)
        delta = np.zeros((b, n))
        for depth in range(len(levels) - 1, 0, -1):
            at, below = levels[depth], levels[depth - 1]
            coef = np.where(at, (1.0 + delta) / np.where(at, sigma, 1.0), 0.0)
            pull = np.asarray((adj @ coef.T).T)
            delta += np.where(below, sigma * pull, 0.0)
        delta[np.arange(b), sources] = 0.0
        bc += delta.sum(0)
    return (bc / 2).tolist()


def bc_solve(data, budget):
    nodes, index, pairs, k = _graph(data)
    if len(nodes) > BC_NATIVE_NODES:
        return answer(None, {"reason": f"more than {BC_NATIVE_NODES} nodes"}, status="ABSTAIN",
                      missing=[f"more than {BC_NATIVE_NODES} nodes"])
    values = _brandes_sparse(len(nodes), pairs)
    out = _ranked(nodes, values, k)
    kth = out["betweenness"][-1]
    rest = sorted((values[i] for i in range(len(nodes)) if nodes[i] not in set(out["top"])), reverse=True)
    return answer(out, {"method": f"exact Brandes, batched over {BC_BATCH} sources as sparse matrix products",
                        "nodes": len(nodes), "edges": len(pairs), "k": k, "kth_value": kth,
                        "next_value": rest[0] if rest else None,
                        "semantics": "unnormalised undirected betweenness: each unordered pair counted once"})


def _close(a, b):
    return abs(a - b) <= BC_REL_TOL * max(1.0, abs(a), abs(b))


def bc_verify(data, output, certificate):
    nodes, index, pairs, k = _graph(data)
    if (not isinstance(output, dict) or set(output) != {"top", "betweenness"} or not isinstance(output["top"], list)
            or not isinstance(output["betweenness"], list)):
        return {"output_shape": False}
    top, vals = output["top"], output["betweenness"]
    shape = (len(top) == k == len(vals) and all(isinstance(v, str) and v in index for v in top)
             and len(set(top)) == k and all(type(x) in (int, float) for x in vals))
    if not shape:
        return {"output_shape": True, "k_distinct_nodes_of_the_graph": False, "values_recomputed": False,
                "no_unreturned_node_ranks_higher": False}
    ref = brandes_reference(len(nodes), pairs)
    chosen = {index[v] for v in top}
    lowest = min(ref[index[v]] for v in top)
    highest_rest = max((ref[i] for i in range(len(nodes)) if i not in chosen), default=-1.0)
    return {"output_shape": True, "k_distinct_nodes_of_the_graph": True,
            "values_recomputed": all(_close(ref[index[v]], x) for v, x in zip(top, vals)),
            "sorted_by_value": all(vals[i] >= vals[i + 1] or _close(vals[i], vals[i + 1]) for i in range(k - 1)),
            "no_unreturned_node_ranks_higher": highest_rest <= lowest + BC_REL_TOL * max(1.0, lowest)}


def _scale_free(r, n):
    m = r.choice((1, 2, 3))
    edges, targets = set(), list(range(m + 1))
    for a in range(m + 1):
        for b in range(a + 1, m + 1):
            edges.add((a, b))
    pool = [x for e in edges for x in e]
    for v in range(m + 1, n):
        picks = set()
        while len(picks) < m:
            picks.add(r.choice(pool))
        for t in picks:
            edges.add((t, v))
            pool += [t, v]
    del targets
    return edges


def _small_world(r, n):
    half, p = r.choice((2, 3)), r.uniform(0.02, 0.2)
    edges = set()
    for v in range(n):
        for d in range(1, half + 1):
            w = (v + d) % n
            if r.random() < p:
                w = r.randrange(n)
                if w == v:
                    continue
            edges.add((min(v, w), max(v, w)))
    return edges


def _communities(r, n):
    blocks = r.randint(4, 10)
    block = [r.randrange(blocks) for _ in range(n)]
    edges = set()
    for a in range(n):
        for b in range(a + 1, n):
            if r.random() < (8.0 / max(1, n / blocks) if block[a] == block[b] else 0.4 / n):
                edges.add((a, b))
    return edges


def _spatial(r, n):
    pts = [(r.random(), r.random()) for _ in range(n)]
    radius = (2.2 / n) ** 0.5
    edges = set()
    for a in range(n):
        for b in range(a + 1, n):
            if (pts[a][0] - pts[b][0]) ** 2 + (pts[a][1] - pts[b][1]) ** 2 <= radius ** 2:
                edges.add((a, b))
    return edges


BC_KINDS = (("scale_free", _scale_free), ("small_world", _small_world), ("communities", _communities),
            ("spatial", _spatial))


def bc_instance(seed):
    r = random.Random(f"genome:graph_betweenness_topk:{seed}")
    kind, make = BC_KINDS[seed % 4]
    n = r.choice((200, 300, 400, 500, 600))
    edges = make(r, n)
    data = {"graph_edges": [[f"n{a:04d}", f"n{b:04d}"] for a, b in sorted(edges)], "top_k": r.choice((5, 10, 20))}
    nodes, index, pairs, k = _graph(data)
    k = min(k, len(nodes))
    data["top_k"] = k
    ref = brandes_reference(len(nodes), pairs)
    return data, {"kind": kind, "betweenness": ref, "nodes": nodes}


def bc_subregion(data):
    nodes, index, pairs, k = _graph(data)
    deg = [0] * len(nodes)
    for a, b in pairs:
        deg[a] += 1
        deg[b] += 1
    return "hub_skewed" if max(deg) > 5 * (2 * len(pairs) / len(nodes)) else "flat_degree"


def bc_score(data, truth, output):
    if not isinstance(output, dict) or not isinstance(output.get("top"), list):
        return {"quality": -0.5, "category": "abstain"}
    nodes, index, pairs, k = _graph(data)
    top, vals = output["top"], output.get("betweenness")
    if len(top) != k or len(set(top)) != k or not all(isinstance(v, str) and v in index for v in top):
        return {"quality": -1.0, "category": "wrong"}
    ref = truth["betweenness"]
    kth = sorted(ref, reverse=True)[k - 1]
    hits = sum(1 for v in top if ref[index[v]] >= kth - BC_REL_TOL * max(1.0, kth))
    values_ok = (isinstance(vals, list) and len(vals) == k
                 and all(type(x) in (int, float) and _close(ref[index[v]], x) for v, x in zip(top, vals)))
    return {"quality": hits / k, "category": "correct" if hits == k and values_ok else "wrong"}


def bc_degree(data):
    """Baseline: the k highest-degree nodes (ties by name). A degree ranking computes no betweenness, so it claims
    the set only (values null): it is scored on the set and counts as wrong unless that set is a true top-k with
    values."""
    nodes, index, pairs, k = _graph(data)
    deg = [0] * len(nodes)
    for a, b in pairs:
        deg[a] += 1
        deg[b] += 1
    order = sorted(range(len(nodes)), key=lambda i: (-deg[i], nodes[i]))[:k]
    return {"top": [nodes[i] for i in order], "betweenness": None}


def bc_networkx(data):
    """Competitor: NetworkX exact betweenness_centrality (normalized=False, undirected), ranked like the
    candidate."""
    import networkx as nx
    nodes, index, pairs, k = _graph(data)
    g = nx.Graph()
    g.add_nodes_from(range(len(nodes)))
    g.add_edges_from(pairs)
    bc = nx.betweenness_centrality(g, normalized=False)
    return _ranked(nodes, [bc[i] for i in range(len(nodes))], k)


INTELLIGENCES = [
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.graph.betweenness_top_k", version="1.0.0", family="graph_betweenness_topk",
            layer=3, operation="betweenness_top_k", epistemic_class="optimization",
            subgeometry="rank the nodes of an undirected unweighted graph by exact shortest-path betweenness and "
                        "return the k most critical relays with their values",
            source_provenance="Freeman (1977) betweenness; Brandes (2001) accumulation; Kepner and Gilbert (2011) "
                              "linear-algebraic BFS; SciPy sparse (BSD-3); NetworkX (BSD-3) as the competitor",
            native_representation="undirected edge list [u, v] with string node names, and k",
            required_inputs=("graph_edges", "top_k"),
            output_contract={"top": "[node] k names, by betweenness descending (ties by name)",
                             "betweenness": "[float] their unnormalised betweenness"},
            algorithm_or_runtime=f"Brandes batched over {BC_BATCH} sources: sparse adjacency x dense frontier "
                                 "blocks for shortest-path counts, then the level-by-level dependency sweep",
            parameters={"batch": BC_BATCH, "native_nodes": BC_NATIVE_NODES, "relative_tolerance": BC_REL_TOL},
            composition_inputs=("dependency or communication graph",),
            composition_outputs=("critical relays", "betweenness values"),
            evidence_type="exact_calculation",
            verification_method="an independent pure-Python queue-based Brandes recomputes every node's "
                                "betweenness: the returned values must match, the k nodes be distinct and in "
                                "non-increasing order, and no unreturned node rank higher",
            confidence_semantics="exact betweenness up to floating-point rounding (relative 1e-9); criticality "
                                 "means shortest-path load, not resilience under rerouting",
            resource_profile="O(n m) work in compiled sparse products; dense blocks of 256 x n floats",
            latency_profile="tens to hundreds of milliseconds at benchmark size",
            known_strengths=("exact, with a checkable claim", "compiled sparse kernels: faster than the "
                             "pure-Python NetworkX loop at the same answer"),
            known_failure_modes=("high-diameter graphs (long chains, grids) need many levels and lose much of the "
                                 "batching advantage",
                                 "ties at the k-th value are broken by name; another valid top-k may exist",
                                 "betweenness is shortest-path load: a node can be critical for flow or "
                                 "connectivity without high betweenness (use node cuts)"),
            counterindications=("weighted or directed graphs (not supported in this version)",
                                "graphs above 3000 nodes without a time budget (use sampled approximation with a "
                                "stated error bound)", "connectivity criticality (use graph_node_cut_exact)"),
            abstention_conditions=(f"more than {BC_NATIVE_NODES} nodes",),
            benchmark_suite="scale-free (preferential attachment), small-world (rewired ring), planted communities "
                            "and spatial (random geometric) graphs with 200-600 nodes, k 5-20; truth by the "
                            "independent reference Brandes; quality is the fraction of returned nodes in the true "
                            "top-k (correct only with exact values); seeds 0-9 dev, held-out seeds fixed by the "
                            "admission freeze",
            baseline="the k highest-degree nodes (no betweenness values)",
            competitor="NetworkX exact betweenness_centrality (pure-Python Brandes), ranked identically",
            dependency="scipy", buildability="BUILDABLE_NOW", memory_model="stateless",
            learning_rule="none (competence settles per geometry through GREG outcomes)", lineage=LINEAGE),
        solve=bc_solve, verify=bc_verify, instance=bc_instance, score=bc_score, baseline=bc_degree,
        competitor=bc_networkx, subregion=bc_subregion, tolerance=1e-12),
]
