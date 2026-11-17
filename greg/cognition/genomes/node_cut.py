"""Layer 3 graph intelligence: the exact minimum S-T vertex cut ("control points") of a directed graph.

``graph_node_cut_exact`` (operation ``min_vertex_cut``) answers the question natops-2026-10-21 asked of GREG's own
import graph: which smallest set of intermediate vertices must be removed so that no directed path from S reaches T?
Before this genome, GREG could answer it only by translating the graph by hand into a node-split unit-capacity
network for ``flow_maxflow`` (whose 120-node / 400-edge bounds then excluded 25 of 1,427 natural held-out items),
while ``networkx.minimum_node_cut`` in process was exact on all 1,427 (docs/evidence/greg-natural-ops-2026-10-21).

* ``solve``: the installed NetworkX engine. One auxiliary node-split network and one residual network are built and
  shared by ``minimum_st_node_cut`` (the cut) and ``node_disjoint_paths`` (the Menger packing that certifies it).
* ``verify``: independent of the engine (no NetworkX, nothing shared with ``solve``). It re-reads the input graph and
  checks (a) removing the returned cut leaves T unreachable from S (its own BFS) and (b) the certificate holds exactly
  ``k = |cut|`` S-T paths, each a directed path of the input with no repeated vertex, whose interiors are pairwise
  disjoint. Every separating set must take a distinct vertex from each path, so no separating set has fewer than k
  vertices (Menger's easy direction): (a) and (b) together prove the cut is a minimum one.
* Truth for the native benchmark (``instance``): a separate from-scratch unit-capacity augmenting-path max flow on
  the node-split graph (Menger's theorem), written here without NetworkX.
* Baseline: S-T betweenness greedy (delete by rank until separated, then prune); the stronger of the two greedy
  baselines on the natops development part. Competitor: the admitted ``flow_maxflow`` genome's solve on the
  node-split translation, in process (deployable); ``competitor_ilp`` (an exact HiGHS integer program,
  ``scipy.optimize.milp``) is the independent exact competitor reported beside it.

Input limits (``MAX_NODES``, ``MAX_EDGES``) were set from measured in-process latency, not copied from
``flow_maxflow``: see ``docs/evidence/greg-node-cut-2026-10-21/README.md`` (DEVELOPMENT ONLY measurements).
"""
from __future__ import annotations

from collections import deque
import random

from .contract import Executable, GenomeError, IntelligenceGenome, answer

LINEAGE = ("INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION", "INTENT-20261007-VERIFIED-POLYINTELLIGENCE-LIFT",
           "docs/evidence/greg-natural-ops-2026-10-21 (verified deficit: flow_maxflow bounds, practitioner exact)")
# Set from measured latency (DEVELOPMENT ONLY; docs/evidence/greg-node-cut-2026-10-21/latency.json), not copied from
# flow_maxflow: on one pinned core of the shared 4-core host, the slowest solve + independent verify on probe graphs
# built to be slow for augmenting paths (dense, layered, long sparse and native dependency shapes) at every probed edge
# cap up to these bounds took under LATENCY_TARGET_S CPU seconds, a quarter of the worker's share of the default 5 s
# cognition budget (0.45 x 5 s, less process start-up). Wall-clock is recorded beside it and inflates with host load.
# Latency did not bind below 10,000 edges, the cognition path's own input-list limit (contracts.strict_data); through
# cortex.reason the 64 KiB request limit binds first (about 1,000-1,300 edges at natural module-name lengths).
MAX_NODES, MAX_EDGES = 10_000, 10_000
LATENCY_TARGET_S = 0.5
MAX_NAME = 256
RETAINED_ITEMS = 1000              # receipt retention: at most 1000 items per proof list (contracts.retained_data)
CERTIFICATE_VERTICES = 20_000      # path vertices a certificate may carry (worker output is capped at 256 KiB)


# ------------------------------------------------------------------ input
def _graph(data):
    """(adjacency with every vertex present, sorted edge list, s, t) or GenomeError."""
    edges = data.get("edges")
    if not isinstance(edges, list) or not 1 <= len(edges) <= MAX_EDGES:
        raise GenomeError(f"1-{MAX_EDGES} edges required")
    adj, seen = {}, set()
    for e in edges:
        if (not isinstance(e, list) or len(e) != 2
                or not all(isinstance(n, str) and 0 < len(n) <= MAX_NAME for n in e)):
            raise GenomeError("edge is [from, to] with non-empty vertex names")
        if e[0] == e[1]:
            raise GenomeError("self-loops are not allowed")
        adj.setdefault(e[0], set()).add(e[1])
        adj.setdefault(e[1], set())
        seen.add((e[0], e[1]))           # a repeated edge is the same dependency; it changes no cut
    s, t = data.get("source"), data.get("target")
    if not isinstance(s, str) or not isinstance(t, str) or s not in adj or t not in adj or s == t:
        raise GenomeError("distinct source and target vertices of the graph required")
    if len(adj) > MAX_NODES:
        raise GenomeError(f"at most {MAX_NODES} vertices")
    return {u: sorted(vs) for u, vs in adj.items()}, sorted(seen), s, t


def _reaches(adj, s, t, removed=frozenset()):
    seen, queue = {s}, deque([s])
    while queue:
        for v in adj.get(queue.popleft(), ()):
            if v not in seen and v not in removed:
                if v == t:
                    return True
                seen.add(v)
                queue.append(v)
    return False


# ------------------------------------------------------------------ solve (NetworkX engine)
def node_cut_solve(data, budget):
    import networkx as nx
    from networkx.algorithms.connectivity import (build_auxiliary_node_connectivity, minimum_st_node_cut,
                                                  node_disjoint_paths)
    from networkx.algorithms.flow import build_residual_network
    adj, edges, s, t = _graph(data)
    if t in adj[s]:
        return answer(None, {}, status="ABSTAIN",
                      missing=["a direct edge S->T: no set of intermediate vertices separates them"])
    if not _reaches(adj, s, t):
        return answer({"cut": [], "k": 0}, {"paths": [], "engine": f"networkx {nx.__version__}",
                                            "claim": "T is unreachable from S: the empty set separates them"})
    g = nx.DiGraph()
    g.add_nodes_from(adj)
    g.add_edges_from(edges)
    aux = build_auxiliary_node_connectivity(g)
    residual = build_residual_network(aux, "capacity")
    cut = sorted(minimum_st_node_cut(g, s, t, auxiliary=aux, residual=residual))
    paths = [list(p) for p in node_disjoint_paths(g, s, t, auxiliary=aux, residual=residual)]
    if len(paths) != len(cut):
        return answer(None, {"cut_size": len(cut), "paths": len(paths)}, status="UNKNOWN",
                      missing=["the engine's cut and its disjoint-path packing disagree in size"])
    if (sum(len(p) for p in paths) > CERTIFICATE_VERTICES or len(paths) > RETAINED_ITEMS
            or any(len(p) > RETAINED_ITEMS for p in paths)):
        return answer(None, {"paths": len(paths), "certificate_vertices": sum(len(p) for p in paths)}, status="ABSTAIN",
                      missing=[f"the Menger certificate exceeds receipt retention ({RETAINED_ITEMS} paths or vertices "
                               f"per path, {CERTIFICATE_VERTICES} path vertices in all)"])
    return answer({"cut": cut, "k": len(cut)},
                  {"paths": paths, "engine": f"networkx {nx.__version__} minimum_st_node_cut + node_disjoint_paths",
                   "claim": "k internally vertex-disjoint S-T paths (Menger): every separating set takes a distinct "
                            "vertex from each, so none has fewer than k; the returned cut of size k separates"})


# ------------------------------------------------------------------ independent verification (no NetworkX)
def node_cut_verify(data, output, certificate):
    """Independent of the engine: separation by its own BFS, minimality by a Menger packing checked path by path."""
    adj, _, s, t = _graph(data)
    if not isinstance(output, dict) or set(output) != {"cut", "k"}:
        return {"output_well_formed": False}
    cut, k = output["cut"], output["k"]
    if (not isinstance(cut, list) or not all(isinstance(v, str) for v in cut) or len(set(cut)) != len(cut)
            or type(k) is not int or k != len(cut)):
        return {"output_well_formed": False}
    certificate = certificate if isinstance(certificate, dict) else {}
    paths = certificate.get("paths")
    paths_ok = isinstance(paths, list) and all(
        isinstance(p, list) and p and all(isinstance(v, str) for v in p) for p in paths)
    checks = {"output_well_formed": True,
              "cut_vertices_are_intermediate": set(cut) <= set(adj) - {s, t},
              "cut_separates_s_from_t": not _reaches(adj, s, t, frozenset(cut)),
              "certificate_well_formed": paths_ok}
    if not paths_ok:
        return checks
    edge = {(u, v) for u, vs in adj.items() for v in vs}
    interiors = [p[1:-1] for p in paths]
    used = [v for inner in interiors for v in inner]
    checks.update({
        "certificate_has_k_paths": len(paths) == k,
        "every_path_runs_s_to_t_on_input_edges": all(
            p[0] == s and p[-1] == t and len(p) >= 2 and all((a, b) in edge for a, b in zip(p, p[1:]))
            for p in paths),
        "every_path_is_simple": all(len(set(p)) == len(p) for p in paths),
        "path_interiors_pairwise_disjoint": len(used) == len(set(used)),
        # with no direct S->T edge every path has an interior vertex; a bare [S, T] would certify nothing
        "every_path_has_an_intermediate_vertex": all(len(p) >= 3 for p in paths),
    })
    return checks


# ------------------------------------------------------------------ truth (from scratch, no NetworkX)
def menger_k(adj, s, t):
    """Maximum number of internally vertex-disjoint S-T paths by unit-capacity augmenting paths on the node-split graph
    (each vertex v becomes (v, 0) -> (v, 1) of capacity 1, S and T unbounded). Equals the minimum vertex cut."""
    if t in adj[s]:
        raise GenomeError("direct edge S->T")
    big = len(adj) + 1
    cap = {}

    def arc(a, b, c):
        cap[(a, b)] = cap.get((a, b), 0) + c
        cap.setdefault((b, a), 0)
    for v in adj:
        arc((v, 0), (v, 1), big if v in (s, t) else 1)
    for u, vs in adj.items():
        for v in vs:
            arc((u, 1), (v, 0), big)
    nbr = {}
    for a, b in cap:
        nbr.setdefault(a, []).append(b)
    src, snk, k = (s, 1), (t, 0), 0
    while True:
        parent, queue = {src: None}, deque([src])
        while queue and snk not in parent:
            a = queue.popleft()
            for b in nbr[a]:
                if b not in parent and cap[(a, b)] > 0:
                    parent[b] = a
                    queue.append(b)
        if snk not in parent:
            return k
        b = snk
        while parent[b] is not None:
            a = parent[b]
            cap[(a, b)] -= 1
            cap[(b, a)] += 1
            b = a
        k += 1


def node_cut_score(data, truth, output):
    if not isinstance(output, dict) or not isinstance(output.get("cut"), list):
        return {"quality": 0.0, "category": "abstain"}
    adj, _, s, t = _graph(data)
    cut = output["cut"]
    if (not all(isinstance(v, str) for v in cut) or len(set(cut)) != len(cut) or not set(cut) <= set(adj) - {s, t}
            or _reaches(adj, s, t, frozenset(cut))):
        return {"quality": -1.0, "category": "wrong"}               # not a separating set of intermediate vertices
    if len(cut) == truth["k"]:
        return {"quality": 1.0, "category": "correct"}
    return {"quality": truth["k"] / len(cut), "category": "wrong"}  # separates, but is not minimum


# ------------------------------------------------------------------ native benchmark generator
def dependency_graph(r: random.Random, n: int) -> dict:
    """A sparse directed dependency-like graph. Modules are ordered from high level (index 0, S) to low level; each
    module imports 1-4 lower-level modules within a window of 40, with preferential attachment to modules already
    imported often (shared utilities, the hubs that make single points of failure), and 5% of modules add one
    upward import (an import cycle). T is a lower-half module drawn in proportion to how often it is imported. The
    instance is the relevant subgraph (descendants of S that are ancestors of T), with any direct S->T edge removed
    (natops excluded targets that S imports directly)."""
    names = [f"pkg{r.randint(0, 9)}.mod{i:04d}" for i in range(n)]
    out = {i: set() for i in range(n)}
    popularity = [1.0] * n
    for i in range(n - 1):
        pool = range(i + 1, min(n, i + 41))
        for _ in range(r.choice((1, 2, 2, 3, 3, 4))):
            j = r.choices(pool, weights=[popularity[x] for x in pool])[0]
            out[i].add(j)                                # i imports j
            popularity[j] += 1.0
        if r.random() < 0.05 and i > 1:
            out[i].add(r.randrange(1, i))                # an upward import: a cycle
    lower = range(n // 2, n)
    s, t = 0, r.choices(lower, weights=[popularity[x] for x in lower])[0]
    out[s].discard(t)

    def reach(adj, x):
        seen, q = {x}, deque([x])
        while q:
            for y in adj[q.popleft()]:
                if y not in seen:
                    seen.add(y)
                    q.append(y)
        return seen
    rev = {i: set() for i in range(n)}
    for i, js in out.items():
        for j in js:
            rev[j].add(i)
    keep = reach(out, s) & reach(rev, t)
    edges = sorted([names[i], names[j]] for i in keep for j in out[i] if j in keep)
    return {"edges": edges, "source": names[s], "target": names[t]}


def node_cut_instance(seed):
    r = random.Random(f"graph_node_cut_exact/{seed}")
    while True:
        data = dependency_graph(r, r.randint(10, 160))
        adj, _, s, t = _graph(data) if data["edges"] else (None, None, None, None)
        if adj is not None and _reaches(adj, s, t):
            return data, {"k": menger_k(adj, s, t)}


def subregion(data):
    """Whether the instance fits the admitted flow_maxflow genome's declared bounds after node splitting."""
    from .flow import MAX_EDGES as FLOW_EDGES, MAX_NODES as FLOW_NODES
    nodes = {v for e in data["edges"] for v in e}
    fits = 2 * len(nodes) <= FLOW_NODES and len(nodes) + len({tuple(e) for e in data["edges"]}) <= FLOW_EDGES
    return "within_flow_maxflow_bounds" if fits else "beyond_flow_maxflow_bounds"


# ------------------------------------------------------------------ baseline and competitors
def betweenness_greedy(data):
    """Baseline: rank intermediate vertices by S-T betweenness (desc, name asc), delete in that order until T is
    unreachable, then restore every deleted vertex (reverse order) whose restoration keeps T unreachable."""
    import networkx as nx
    adj, edges, s, t = _graph(data)
    if t in adj[s]:
        return None
    g = nx.DiGraph()
    g.add_nodes_from(adj)
    g.add_edges_from(edges)
    bc = nx.betweenness_centrality_subset(g, [s], [t])
    order = sorted((v for v in adj if v not in (s, t)), key=lambda v: (-bc[v], v))
    removed = []
    for v in order:
        if not _reaches(adj, s, t, frozenset(removed)):
            break
        removed.append(v)
    for v in reversed(list(removed)):
        if not _reaches(adj, s, t, frozenset(removed) - {v}):
            removed.remove(v)
    return {"cut": sorted(removed), "k": len(removed)}


def degree_greedy(data):
    """Second greedy baseline (reported, not the declared one): total degree rank, then the same prune."""
    adj, _, s, t = _graph(data)
    if t in adj[s]:
        return None
    deg = {v: 0 for v in adj}
    for u, vs in adj.items():
        for v in vs:
            deg[u] += 1
            deg[v] += 1
    removed = []
    for v in sorted((v for v in adj if v not in (s, t)), key=lambda v: (-deg[v], v)):
        if not _reaches(adj, s, t, frozenset(removed)):
            break
        removed.append(v)
    for v in reversed(list(removed)):
        if not _reaches(adj, s, t, frozenset(removed) - {v}):
            removed.remove(v)
    return {"cut": sorted(removed), "k": len(removed)}


def split_network(data):
    """The node-split unit-capacity translation the natops arms used for flow_maxflow."""
    adj, edges, s, t = _graph(data)
    big = len(adj) + 1
    out = [[f"{v}#in", f"{v}#out", big if v in (s, t) else 1] for v in sorted(adj)]
    out += [[f"{u}#out", f"{v}#in", big] for u, v in edges]
    return {"edges": out, "source": f"{s}#in", "sink": f"{t}#out"}


def competitor_flow_maxflow(data):
    """Competitor: the admitted flow_maxflow genome's solve on the node-split translation, in process. Outside its
    declared bounds it raises GenomeError, which the admission harness scores as an abstention."""
    from .flow import maxflow_solve
    adj, _, s, t = _graph(data)
    if t in adj[s]:
        return None
    out = maxflow_solve(split_network(data), None)["output"]
    cut = []
    for u, v, c in out["cut_edges"]:
        if not (u.endswith("#in") and v == u[:-3] + "#out" and c == 1):
            return None                                   # not a vertex cut: an output translation failure
        cut.append(u[:-3])
    return {"cut": sorted(cut), "k": len(cut)}


def competitor_ilp(data):
    """Independent exact competitor: binary x_v per intermediate vertex, reachability r in [0, 1] with r_S = 1,
    r_T = 0 and r_v >= r_u - x_v on every edge u -> v; minimise sum x_v (SciPy HiGHS milp, gap 0)."""
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
    adj, edges, s, t = _graph(data)
    if t in adj[s]:
        return None
    nodes = sorted(adj)
    mids = [v for v in nodes if v not in (s, t)]
    xi = {v: i for i, v in enumerate(mids)}
    ri = {v: len(mids) + i for i, v in enumerate(nodes)}
    n = len(mids) + len(nodes)
    rows = np.zeros((len(edges), n))
    for row, (u, v) in enumerate(edges):
        rows[row, ri[v]] += 1
        rows[row, ri[u]] -= 1
        if v in xi:
            rows[row, xi[v]] += 1
    c = np.zeros(n)
    c[:len(mids)] = 1
    lb, ub = np.zeros(n), np.ones(n)
    lb[ri[s]] = 1
    ub[ri[t]] = 0
    integrality = np.zeros(n)
    integrality[:len(mids)] = 1
    res = milp(c, constraints=[LinearConstraint(rows, 0, np.inf)], bounds=Bounds(lb, ub), integrality=integrality,
               options={"mip_rel_gap": 0})
    if not res.success:
        return None
    return {"cut": sorted(v for v in mids if res.x[xi[v]] > 0.5), "k": int(round(res.fun))}


INTELLIGENCES = [
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.graph.min_vertex_cut", version="1.0.0", family="graph_node_cut_exact", layer=3,
            operation="min_vertex_cut", epistemic_class="optimization",
            subgeometry="directed S-T minimum vertex cut (control points / single points of failure)",
            source_provenance="Menger's theorem; NetworkX (BSD-3) minimum_st_node_cut and node_disjoint_paths on "
                              "an auxiliary node-split network (Even's construction)",
            buildability="BUILDABLE_NOW", native_representation="directed graph as [from, to] edges + source + target",
            required_inputs=("edges", "source", "target"),
            output_contract={"cut": "[vertex]", "k": "int"},
            algorithm_or_runtime="networkx minimum_st_node_cut + node_disjoint_paths sharing one auxiliary and one "
                                 "residual network (unit-capacity augmenting paths)",
            parameters={}, memory_model="stateless",
            learning_rule="none (competence settles per geometry through GREG outcomes)",
            composition_inputs=("graph",), composition_outputs=("cut", "k"),
            evidence_type="optimality_certificate",
            verification_method="independent of NetworkX: separation by BFS with the cut removed; minimality by k "
                                 "S-T paths on input edges, each simple, with pairwise-disjoint interiors (Menger)",
            confidence_semantics="exact within the supplied graph", resource_profile=(
                f"<= {MAX_NODES} vertices and {MAX_EDGES} edges; measured solve + verify stayed under "
                f"{LATENCY_TARGET_S} CPU s at these bounds on one pinned core (development); a reason request is "
                "separately capped at 64 KiB, which binds first (about 1,000-1,300 edges at natural name lengths)"),
            latency_profile="about 1-10 ms in process at natural sizes (45 vertices, 116 edges median); through "
                            "cortex.reason dominated by two isolated worker processes",
            known_strengths=("exact", "certifies minimality with a Menger path packing",
                             "native vertex-cut input: no hand node-split translation",
                             "bounds set from measured latency, far above flow_maxflow's 120/400 node-split bounds"),
            known_failure_modes=("the supplied graph may omit or invent edges (an import graph is a model of runtime "
                                 "dependency)", "vertex weights are not supported (every intermediate vertex costs 1)",
                                 "one minimum cut is returned when several tie; which one is engine-defined"),
            counterindications=("weighted vertex cuts", "edge cuts (use flow_maxflow)",
                                "undirected graphs unless both directions are supplied",
                                "multi-terminal or multi-commodity separation"),
            abstention_conditions=("invalid graph (self-loop, malformed edge, missing or equal S and T)",
                                   f"more than {MAX_NODES} vertices or {MAX_EDGES} edges",
                                   "a direct S->T edge (no vertex cut exists)",
                                   "engine cut and path packing disagree (UNKNOWN)",
                                   f"certificate above receipt retention ({RETAINED_ITEMS} paths or vertices per "
                                   f"path, {CERTIFICATE_VERTICES} in all)",
                                   "a reason request above 64 KiB is refused before the genome runs"),
            benchmark_suite="sparse directed dependency-like graphs (8-140 modules before restriction to the S-T "
                            "relevant subgraph, preferential attachment, 5% back edges), seeds 0-9 dev; held-out "
                            "seeds recorded by each admission freeze",
            baseline="S-T betweenness greedy with pruning (degree greedy also reported)",
            competitor="flow_maxflow 1.0.1 (admitted DEFAULT) on the node-split translation, in process; independent "
                       "exact ILP (scipy.optimize.milp, HiGHS) reported beside it",
            lineage=LINEAGE, dependency="networkx"),
        solve=node_cut_solve, verify=node_cut_verify, instance=node_cut_instance, score=node_cut_score,
        baseline=betweenness_greedy, competitor=competitor_flow_maxflow, subregion=subregion,
        notes={"second_competitor": "competitor_ilp (scipy.optimize.milp, HiGHS): exact, independent",
               "second_baseline": "degree_greedy",
               "deficit": "docs/evidence/greg-natural-ops-2026-10-21/README.md"}),
]
