"""Layer 3 graph and operations-research intelligences, pack A: assignment, matching, critical path, min-cost flow.

Four executables on GREG's one cognition path (``greg.cognition.cortex.reason`` -> isolated worker ->
independent verifier -> CognitiveReceipt). Each is an ordinary, well-understood algorithm; the genome records
where it is natively competent, what it is compared against and how its output is checked. No verifier here
calls the library its solver uses.

* ``assignment_lsa`` (``min_cost_assignment``): minimum-cost assignment of rows to distinct columns by
  ``scipy.optimize.linear_sum_assignment``, with LP dual potentials derived from the optimal assignment
  (Bellman-Ford over the column difference-constraint graph). Verified by an arithmetic check of those
  potentials and by an independent pure-Python Hungarian method whose dual objective must equal the cost.
* ``graph_matching`` (``max_weight_matching``): maximum-weight matching on general graphs by Edmonds' blossom
  algorithm (``networkx.max_weight_matching``). Verified for validity by arithmetic and for optimality by an
  independent exact method chosen by structure: an LP dual checked arithmetically on bipartite graphs,
  exhaustive enumeration up to 16 vertices, otherwise a dual of Edmonds' odd-set matching LP found by cutting
  planes with exact (Padberg-Rao) odd-set separation and checked in exact rational arithmetic. Where that does
  not close, optimality is reported not established; no floating-point solver's report certifies it.
* ``critical_path`` (``project_critical_path``): critical path method (forward and backward passes in a Kahn
  topological order). Verified by an independent explicit-stack depth-first recomputation of earliest and
  latest finishes, floats and makespan, and a source-to-sink chain check of the returned path.
* ``min_cost_flow`` (``min_cost_flow_plan``): single-commodity minimum-cost flow by OR-Tools SimpleMinCostFlow
  with node potentials (queue-based Bellman-Ford on the residual graph) or an infeasibility cut. Verified by
  capacity/supply/conservation arithmetic, reduced costs under the returned potentials, an independent classic
  Bellman-Ford over the residual graph (no negative cycle) and an independent Edmonds-Karp feasibility check.

Everything is read-only computation: no files, network, subprocesses or environment access, and no output of
any method here creates authority.
"""
from __future__ import annotations

from collections import deque
import heapq
import math
import random

from .contract import Executable, GenomeError, IntelligenceGenome, answer, bounded_int

LINEAGE = ("INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION", "INTENT-20261007-VERIFIED-POLYINTELLIGENCE-LIFT",
           "greg/cognition/network.py and greg/cognition/genomes/flow.py (GREG's own graph code)")
NAME_MAX = 64                       # node and activity names; longer names are reserved for internal sentinels


def _common(**kw):
    return dict(buildability="BUILDABLE_NOW", memory_model="stateless",
                learning_rule="none (competence settles per geometry through GREG outcomes)", lineage=LINEAGE, **kw)


def _abstain(reason, **certificate):
    return answer(None, {"reason": reason, **certificate}, status="ABSTAIN", missing=[reason])


def _unknown(reason, **certificate):
    return answer(None, {"reason": reason, **certificate}, status="UNKNOWN", missing=[reason])


def _mapping(data):
    """Every input is a JSON object; anything else is invalid input, never an AttributeError."""
    if not isinstance(data, dict):
        raise GenomeError("data must be a JSON object")
    return data


def _cert(certificate):
    """A verifier reads the certificate defensively: a non-object certificate binds nothing."""
    return certificate if isinstance(certificate, dict) else {}


def _name(value, what):
    if not isinstance(value, str) or not 0 < len(value) <= NAME_MAX:
        raise GenomeError(f"{what}: a non-empty string of at most {NAME_MAX} characters")
    return value


def _int_list(value, length):
    return isinstance(value, list) and len(value) == length and all(type(x) is int for x in value)


# =================================================================== 1. linear sum assignment
LSA_MAX_SIDE, LSA_NATIVE_SIDE, LSA_MAX_COST = 1000, 100, 1_000_000


def _costs(data):
    rows = _mapping(data).get("cost_matrix")
    if not isinstance(rows, list) or not 1 <= len(rows) <= LSA_MAX_SIDE or not isinstance(rows[0], list):
        raise GenomeError(f"cost_matrix: 1-{LSA_MAX_SIDE} rows of integer costs")
    m = len(rows[0])
    if not len(rows) <= m <= LSA_MAX_SIDE or any(not isinstance(r, list) or len(r) != m for r in rows):
        raise GenomeError(f"cost_matrix: rectangular with rows <= columns <= {LSA_MAX_SIDE} (transpose a matrix "
                          "with more rows than columns)")
    return [[bounded_int(x, low=-LSA_MAX_COST, high=LSA_MAX_COST, name="cost") for x in r] for r in rows]


def assignment_solve(data, budget):
    import numpy as np
    from scipy.optimize import linear_sum_assignment
    from scipy.sparse.csgraph import NegativeCycleError, csgraph_from_dense, shortest_path
    c = _costs(data)
    n, m = len(c), len(c[0])
    if m > LSA_NATIVE_SIDE:
        return _abstain(f"assignment above {LSA_NATIVE_SIDE} columns exceeds the bounded independently "
                        "verifiable size", rows=n, columns=m)
    a = np.array(c, dtype=np.int64)
    _, cols = linear_sum_assignment(a)
    col = [int(j) for j in cols]
    cost = sum(c[i][col[i]] for i in range(n))
    # Dual potentials from the optimal assignment sigma: v_j - v_sigma(i) <= c_ij - c_i,sigma(i) (moving row i
    # to column j), v_j <= v_Z = 0, and v_j = 0 on unused columns; shortest distances from Z satisfy all of them
    # exactly when sigma is optimal (no negative cycle). Then u_i = c_i,sigma(i) - v_sigma(i).
    w = np.full((m + 1, m + 1), np.inf)
    w[m, :m] = 0.0
    used = set(col)
    for j in range(m):
        if j not in used:
            w[j, m] = 0.0
    for i in range(n):
        s = col[i]
        w[s, :m] = (a[i] - a[i, s]).astype(float)
        w[s, s] = np.inf
    try:
        d = shortest_path(csgraph_from_dense(w, null_value=np.inf), method="BF", directed=True, indices=m)
    except NegativeCycleError:
        return _unknown("the assignment returned is not optimal (a negative exchange cycle exists)")
    v = [int(round(x)) for x in d[:m]]
    u = [c[i][col[i]] - v[col[i]] for i in range(n)]
    return answer({"assignment": col, "cost": cost},
                  {"method": "scipy.optimize.linear_sum_assignment (shortest augmenting path); potentials by "
                             "Bellman-Ford over the column exchange graph",
                   "row_potentials": u, "column_potentials": v, "dual_objective": sum(u) + sum(v),
                   "duality": "u_i + v_j <= c_ij for all pairs, v_j <= 0, equality on the assignment, v_j = 0 on "
                              "unused columns; sum(u) + sum(v) = cost proves optimality"})


def hungarian(c):
    """Independent exact method: Kuhn-Munkres with potentials (shortest augmenting path, O(n^2 m), integers).

    Returns (row potentials u, column potentials v, column of each row, optimum). The potentials are a feasible
    dual of the rectangular assignment LP: u_i + v_j <= c_ij, v_j <= 0, zero on unmatched columns."""
    n, m = len(c), len(c[0])
    inf = float("inf")
    u, v, p, way = [0] * (n + 1), [0] * (m + 1), [0] * (m + 1), [0] * (m + 1)
    for i in range(1, n + 1):
        p[0], j0 = i, 0
        minv, used = [inf] * (m + 1), [False] * (m + 1)
        while True:
            used[j0] = True
            i0, delta, j1 = p[j0], inf, 0
            row, ui0 = c[i0 - 1], u[i0]
            for j in range(1, m + 1):
                if not used[j]:
                    cur = row[j - 1] - ui0 - v[j]
                    if cur < minv[j]:
                        minv[j], way[j] = cur, j0
                    if minv[j] < delta:
                        delta, j1 = minv[j], j
            for j in range(m + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while j0:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
    col = [0] * n
    for j in range(1, m + 1):
        if p[j]:
            col[p[j] - 1] = j - 1
    return u[1:], v[1:], col, sum(c[i][col[i]] for i in range(n))


def _dual_feasible(c, u, v):
    return (all(x <= 0 for x in v)
            and all(ui + vj <= cij for ui, row in zip(u, c) for vj, cij in zip(v, row)))


def assignment_verify(data, output, certificate):
    c = _costs(data)
    certificate = _cert(certificate)
    n, m = len(c), len(c[0])
    col = output.get("assignment") if isinstance(output, dict) else None
    if not (_int_list(col, n) and all(0 <= j < m for j in col) and len(set(col)) == n):
        return {"assignment_is_injective_row_to_column": False}
    if m > LSA_NATIVE_SIDE:
        # the solver answers only native instances; a larger answer cannot be checked in bounded time
        return {"assignment_is_injective_row_to_column": True, "independent_check_within_bounds": False}
    cost = sum(c[i][col[i]] for i in range(n))
    u, v = certificate.get("row_potentials"), certificate.get("column_potentials")
    used = set(col)
    certified = (_int_list(u, n) and _int_list(v, m) and _dual_feasible(c, u, v)
                 and all(u[i] + v[col[i]] == c[i][col[i]] for i in range(n))
                 and all(v[j] == 0 for j in range(m) if j not in used) and sum(u) + sum(v) == cost
                 and certificate.get("dual_objective") == cost)
    hu, hv, _, _ = hungarian(c)
    return {"assignment_is_injective_row_to_column": True,
            "cost_recomputed": type(output.get("cost")) is int and output["cost"] == cost,
            "certificate_potentials_dual_feasible_and_tight": certified,
            "optimal_by_independent_hungarian_dual": _dual_feasible(c, hu, hv) and sum(hu) + sum(hv) == cost}


def assignment_instance(seed):
    r = random.Random(f"genome:assignment_lsa:{seed}")
    kind = ("uniform", "geometric", "machine_job", "few_levels", "rectangular")[seed % 5]
    n = r.randint(20, 80)
    m = min(LSA_NATIVE_SIDE, n + r.randint(5, 40)) if kind == "rectangular" else n
    if kind == "geometric":                                  # workers to jobs by travel distance
        workers = [(r.uniform(0, 1000), r.uniform(0, 1000)) for _ in range(n)]
        jobs = [(r.uniform(0, 1000), r.uniform(0, 1000)) for _ in range(m)]
        c = [[1 + round(math.dist(w, j)) for j in jobs] for w in workers]
    elif kind == "machine_job":                              # skill x effort plus noise
        skill = [r.randint(1, 40) for _ in range(n)]
        effort = [r.randint(1, 40) for _ in range(m)]
        c = [[s * e + r.randint(0, 25) for e in effort] for s in skill]
    elif kind == "few_levels":
        c = [[r.randint(1, 5) for _ in range(m)] for _ in range(n)]
    else:
        c = [[r.randint(1, 1000) for _ in range(m)] for _ in range(n)]
    return {"cost_matrix": c}, {"optimum": hungarian(c)[3]}


def assignment_subregion(data):
    c = data["cost_matrix"]
    if len(c) < len(c[0]):
        return "rectangular"
    if len({x for row in c for x in row}) <= 10:
        return "few_distinct_costs"
    return "square_small" if len(c) <= 40 else "square_large"


def _assignment_cost(c, col):
    """The cost of a well-formed injective assignment, or None."""
    n, m = len(c), len(c[0])
    if not (isinstance(col, list) and len(col) == n and all(type(j) is int and 0 <= j < m for j in col)
            and len(set(col)) == n):
        return None
    return sum(c[i][col[i]] for i in range(n))


def _ratio(cost, optimum):
    """Quality of a minimisation answer: 1 at the optimum, falling toward 0 with the relative excess."""
    return 1.0 / (1.0 + (cost - optimum) / max(1, abs(optimum)))


def assignment_score(data, truth, output):
    if not isinstance(output, dict) or not isinstance(output.get("assignment"), list):
        return {"quality": 0.0, "category": "abstain"}
    c = _costs(data)
    cost = _assignment_cost(c, output["assignment"])
    if cost is None or output.get("cost", cost) != cost or cost < truth["optimum"]:
        return {"quality": -1.0, "category": "wrong"}         # not an assignment, or a false cost claim
    return {"quality": _ratio(cost, truth["optimum"]),
            "category": "correct" if cost == truth["optimum"] else "wrong"}


def assignment_greedy(data):
    """Baseline: global greedy - take the cheapest remaining (row, column) pair until every row is assigned."""
    c = _costs(data)
    n, m = len(c), len(c[0])
    col, taken = [None] * n, set()
    for cost, i, j in sorted((c[i][j], i, j) for i in range(n) for j in range(m)):
        if col[i] is None and j not in taken:
            col[i] = j
            taken.add(j)
            if len(taken) == n:
                break
    return {"assignment": col, "cost": sum(c[i][col[i]] for i in range(n))}


def assignment_ortools(data):
    """Competitor: OR-Tools' dedicated assignment solver (cost scaling) on square matrices; on rectangular ones,
    where it requires a perfect matching, OR-Tools SimpleMinCostFlow on rows -> columns -> sink."""
    import numpy as np
    c = _costs(data)
    n, m = len(c), len(c[0])
    left, right = np.repeat(np.arange(n), m), np.tile(np.arange(m), n)
    flat = np.array(c, dtype=np.int64).ravel()
    if n == m:
        from ortools.graph.python import linear_sum_assignment
        solver = linear_sum_assignment.SimpleLinearSumAssignment()
        solver.add_arcs_with_cost(left, right, flat)
        if solver.solve() != solver.OPTIMAL:
            return None
        col = [int(solver.right_mate(i)) for i in range(n)]
    else:
        from ortools.graph.python import min_cost_flow
        flow = min_cost_flow.SimpleMinCostFlow()
        arcs = flow.add_arcs_with_capacity_and_unit_cost(left, n + right, np.ones(n * m, dtype=np.int64), flat)
        flow.add_arcs_with_capacity_and_unit_cost(n + np.arange(m), np.full(m, n + m), np.ones(m, dtype=np.int64),
                                                  np.zeros(m, dtype=np.int64))
        flow.set_nodes_supplies(np.arange(n + m + 1), np.array([1] * n + [0] * m + [-n], dtype=np.int64))
        if flow.solve() != flow.OPTIMAL:
            return None
        used = np.nonzero(flow.flows(arcs) > 0)[0]
        col = [0] * n
        for k in used:
            col[int(k) // m] = int(k) % m
    return {"assignment": col, "cost": sum(c[i][col[i]] for i in range(n))}


# =================================================================== 2. maximum-weight matching (general graphs)
MATCH_MAX_VERTICES, MATCH_MAX_EDGES, MATCH_MAX_WEIGHT = 400, 2000, 1_000_000
MATCH_NATIVE_VERTICES, MATCH_NATIVE_EDGES, MATCH_EXHAUSTIVE_VERTICES = 80, 400, 16
MATCH_CUT_ROUNDS = 100                    # odd-set cutting-plane rounds; optimality is not established after
MATCH_TIE_BREAK = 0.01                    # largest per-edge objective nudge that breaks LP ties (never certifies)


def _matching_graph(data):
    edges = _mapping(data).get("weighted_edges")
    if not isinstance(edges, list) or not 1 <= len(edges) <= MATCH_MAX_EDGES:
        raise GenomeError(f"weighted_edges: 1-{MATCH_MAX_EDGES} edges [u, v, weight]")
    out, seen, vertices = [], set(), set()
    for e in edges:
        if not isinstance(e, list) or len(e) != 3:
            raise GenomeError("edge is [u, v, weight]")
        u, v = _name(e[0], "vertex"), _name(e[1], "vertex")
        if u == v:
            raise GenomeError("self-loops are not allowed")
        key = frozenset((u, v))
        if key in seen:
            raise GenomeError(f"duplicate edge {u}-{v}: keep one weight per pair")
        seen.add(key)
        out.append((u, v, bounded_int(e[2], low=0, high=MATCH_MAX_WEIGHT, name="weight")))
        vertices.update((u, v))
    if len(vertices) > MATCH_MAX_VERTICES:
        raise GenomeError(f"at most {MATCH_MAX_VERTICES} vertices")
    return out


def _vertices(edges):
    return sorted({x for u, v, _ in edges for x in (u, v)})


def matching_solve(data, budget):
    import networkx as nx
    edges = _matching_graph(data)
    n = len(_vertices(edges))
    if n > MATCH_NATIVE_VERTICES or len(edges) > MATCH_NATIVE_EDGES:
        return _abstain(f"graph above {MATCH_NATIVE_VERTICES} vertices or {MATCH_NATIVE_EDGES} edges exceeds the "
                        "bounded independently verifiable size", vertices=n, edges=len(edges))
    g = nx.Graph()
    g.add_weighted_edges_from(edges)
    pairs = sorted(sorted(p) for p in nx.max_weight_matching(g, maxcardinality=False, weight="weight"))
    return answer({"matching": pairs, "weight": sum(g[u][v]["weight"] for u, v in pairs)},
                  {"method": "Edmonds blossom algorithm (networkx.max_weight_matching, primal-dual, O(V^3))",
                   "vertices": n, "edges": len(edges), "matched_pairs": len(pairs),
                   "limits": "the blossom dual is not exported; optimality is checked by an independent method"})


def _two_colouring(edges):
    """{vertex: 0 or 1} when the graph is bipartite, else None (breadth-first search per component)."""
    adj = {}
    for u, v, _ in edges:
        adj.setdefault(u, []).append(v)
        adj.setdefault(v, []).append(u)
    colour = {}
    for root in sorted(adj):
        if root in colour:
            continue
        colour[root] = 0
        queue = deque([root])
        while queue:
            x = queue.popleft()
            for y in adj[x]:
                if y not in colour:
                    colour[y] = 1 - colour[x]
                    queue.append(y)
                elif colour[y] == colour[x]:
                    return None
    return colour


def _matching_exhaustive(edges):
    """Exact by enumeration: the lowest free vertex is either left unmatched or matched to a free neighbour."""
    names = _vertices(edges)
    index = {x: i for i, x in enumerate(names)}
    adj = [[] for _ in names]
    for u, v, w in edges:
        adj[index[u]].append((index[v], w))
        adj[index[v]].append((index[u], w))
    memo = {0: 0}

    def best(mask):
        if mask not in memo:
            i = (mask & -mask).bit_length() - 1
            rest = mask & ~(1 << i)
            value = best(rest)
            for j, w in adj[i]:
                if rest >> j & 1:
                    value = max(value, w + best(rest & ~(1 << j)))
            memo[mask] = value
        return memo[mask]
    return best((1 << len(names)) - 1)


def _matching_bipartite_dual(edges, colour):
    """Exact on bipartite graphs: max-weight matching as a rectangular assignment (left side to right side plus
    one 'unmatched' column per left vertex, cost -w on edges and 0 elsewhere) solved by the independent
    Hungarian method; its integral potentials are checked here as an LP dual before the optimum is trusted."""
    left = sorted(x for x, k in colour.items() if k == 0)
    right = sorted(x for x, k in colour.items() if k == 1)
    if len(left) > len(right):
        left, right = right, left
    weight = {frozenset((u, v)): w for u, v, w in edges}
    c = [[-weight.get(frozenset((a, b)), 0) for b in right] + [0] * len(left) for a in left]
    u, v, _, optimum = hungarian(c)
    if not _dual_feasible(c, u, v) or sum(u) + sum(v) != optimum:
        return None
    return -optimum


def _odd_components(ends, x, n, keep):
    """Vertex sets (index frozensets) of the connected components with an odd number (>= 3) of vertices in the
    subgraph of edges ``k`` with ``keep(x[k])``."""
    adj = [[] for _ in range(n)]
    for k, (i, j) in enumerate(ends):
        if keep(x[k]):
            adj[i].append(j)
            adj[j].append(i)
    seen, out = [False] * n, []
    for root in range(n):
        if seen[root] or not adj[root]:
            continue
        seen[root], stack, component = True, [root], [root]
        while stack:
            for nxt in adj[stack.pop()]:
                if not seen[nxt]:
                    seen[nxt] = True
                    stack.append(nxt)
                    component.append(nxt)
        if len(component) >= 3 and len(component) % 2:
            out.append(frozenset(component))
    return out


_FLOW_EPS, _SUPPORT_EPS = 1e-12, 1e-9


def _min_cut(cap, s, t):
    """Maximum s-t flow on an undirected graph with float capacities ``cap[u][v] == cap[v][u]`` by shortest
    augmenting paths (Edmonds-Karp). Returns (value, the s side of a minimum cut)."""
    res = {u: dict(nbrs) for u, nbrs in cap.items()}
    value = 0.0
    while True:
        prev, queue = {s: None}, deque([s])
        while queue and t not in prev:
            u = queue.popleft()
            for v, c in res[u].items():
                if c > _FLOW_EPS and v not in prev:
                    prev[v] = u
                    queue.append(v)
        if t not in prev:
            return value, set(prev)
        path, v = [], t
        while prev[v] is not None:
            path.append((prev[v], v))
            v = prev[v]
        push = min(res[u][v] for u, v in path)
        for u, v in path:
            res[u][v] -= push
            res[v][u] += push
        value += push


def _gomory_hu(cap, n):
    """Gomory-Hu cut tree of nodes 0..n-1 by Gusfield's method (n - 1 minimum cuts, no contraction): node i >= 1
    hangs from ``parent[i]`` (root 0) by an edge of weight ``value[i]``, and the subtree of i is the i side of a
    minimum cut between i and ``parent[i]``."""
    parent, value = [0] * n, [0.0] * n
    for s in range(1, n):
        t = parent[s]
        f, side = _min_cut(cap, s, t)
        value[s] = f
        for i in range(n):
            if i != s and i in side and parent[i] == t:
                parent[i] = s
        if parent[t] in side:
            parent[s], parent[t] = parent[t], s
            value[s], value[t] = value[t], f
    return parent, value


def _violated_odd_sets(ends, x, n):
    """Every odd set S (index frozensets, |S| >= 3) whose fundamental Gomory-Hu cut violates x(E(S)) <=
    (|S| - 1) / 2: exact Padberg-Rao separation. With slacks s_v = 1 - x(delta(v)) on edges to an extra node t,
    the odd-set row for S is x(delta(S)) + s(S) >= 1, a cut whose side without t is odd; a minimum such cut is a
    fundamental cut of a Gomory-Hu tree, so an empty answer means no odd-set row is violated (up to float
    tolerance). Only vertices that x touches can lie in a violated set (any other has slack 1)."""
    degree = [0.0] * n
    for k, (i, j) in enumerate(ends):
        degree[i] += x[k]
        degree[j] += x[k]
    support = [i for i in range(n) if degree[i] > _SUPPORT_EPS]
    local = {v: a for a, v in enumerate(support)}
    t = len(support)
    cap = {a: {} for a in range(t + 1)}
    for k, (i, j) in enumerate(ends):
        if x[k] > _SUPPORT_EPS:
            a, b = local[i], local[j]
            cap[a][b] = cap[b][a] = cap[a].get(b, 0.0) + x[k]
    for v, a in local.items():
        if 1.0 - degree[v] > _SUPPORT_EPS:
            cap[a][t] = cap[t][a] = 1.0 - degree[v]
    if t < 3:
        return []
    parent, value = _gomory_hu(cap, t + 1)
    children = [[] for _ in range(t + 1)]
    for i in range(1, t + 1):
        children[parent[i]].append(i)
    out = []
    for i in range(1, t + 1):
        if value[i] >= 1.0 - 1e-6:
            continue
        subtree, stack = set(), [i]
        while stack:
            a = stack.pop()
            subtree.add(a)
            stack.extend(children[a])
        side = subtree if t not in subtree else set(range(t)) - subtree
        if len(side) >= 3 and len(side) % 2:
            s = frozenset(support[a] for a in side)
            if s not in out:
                out.append(s)
    return out


def _checked_dual_objective(ends, weights, sets, n, y, z):
    """Weak duality, checked in exact rational arithmetic: when y, z >= 0 and every edge is covered,
    y_u + y_v + sum_{S contains u and v} z_S >= w_uv, then every matching weighs at most
    D = sum y + sum z_S floor(|S| / 2). Returns D, or None when the dual is infeasible."""
    if len(y) != n or len(z) != len(sets) or any(v < 0 for v in y) or any(v < 0 for v in z):
        return None
    for (i, j), w in zip(ends, weights):
        if y[i] + y[j] + sum(zs for zs, s in zip(z, sets) if i in s and j in s) < w:
            return None
    return sum(y) + sum(zs * (len(s) // 2) for zs, s in zip(z, sets))


def _exact_dual_bound(ends, weights, member, sets, n, marginals):
    """An exact upper bound on every matching's weight built from HiGHS's floating dual (y_v per degree row,
    z_S per odd-set row), or None.

    The float dual only proposes. Each value is taken as an exact rational (and also rounded to a few small
    denominators); any edge it leaves short by float error is covered by raising y at one end by the shortfall,
    so the dual is feasible by construction; ``_checked_dual_objective`` then checks it in exact arithmetic.
    The smallest checked objective is returned."""
    from fractions import Fraction
    duals = [max(0.0, -float(d)) for d in marginals]
    if len(duals) != n + len(sets) or not all(math.isfinite(d) for d in duals):
        return None
    best = None
    for den in (None, 1, 2, 6, 60, 2520):
        q = [Fraction(d) if den is None else Fraction(d).limit_denominator(den) for d in duals]
        y, z = q[:n], q[n:]
        for k, ((i, j), w) in enumerate(zip(ends, weights)):
            short = w - y[i] - y[j] - sum(z[s] for s in member[k])
            if short > 0:
                y[i] += short
        bound = _checked_dual_objective(ends, weights, sets, n, y, z)
        if bound is not None and (best is None or bound < best):
            best = bound
    return best


def _matching_odd_set_dual(edges, lower=None):
    """Exact maximum matching weight certified by an exactly checked dual of Edmonds' matching LP, or None.

    Cutting planes: degree rows x(delta(v)) <= 1, then odd-set rows x(E(S)) <= (|S| - 1) / 2. Each round adds
    the odd components of the fractional (or the positive) part of the LP optimum whose edge mass exceeds that
    bound and every violated fundamental cut of a Gomory-Hu tree (exact Padberg-Rao separation,
    ``_violated_odd_sets``), so the loop heads for Edmonds' LP optimum, which is the maximum matching weight.
    SciPy HiGHS only proposes: its dual is checked exactly (``_exact_dual_bound``) and bounds every matching by
    D, so with integer weights by floor(D). The optimum is certified only when a matching in hand weighs exactly
    floor(D): the LP optimum rounded to a matching (checked to be one, weighed in integers) or ``lower``, the
    weight of a matching the caller has already validated. None when the rounds run out, separation finds
    nothing more, or HiGHS fails: optimality is then not established either way."""
    import numpy as np
    from scipy.optimize import linprog
    names = _vertices(edges)
    index = {x: i for i, x in enumerate(names)}
    ends = [(index[u], index[v]) for u, v, _ in edges]
    weights = [w for _, _, w in edges]
    n, m = len(names), len(edges)
    rows = [np.zeros(m) for _ in range(n)]
    for k, (i, j) in enumerate(ends):
        rows[i][k] = rows[j][k] = 1.0
    sets, member = [], [[] for _ in range(m)]          # member[k]: odd sets containing both ends of edge k
    # a fixed nudge in [0, MATCH_TIE_BREAK) per edge picks one LP optimum among many equal ones, so degenerate
    # weights (two levels, near-equal) do not cycle through equally good fractional optima; it is nonnegative,
    # so HiGHS's dual still covers the true weights, and at most 80 * 0.01 / 2 = 0.4 rides on any matching
    nudge = np.array([MATCH_TIE_BREAK * ((k * 0.6180339887498949) % 1.0) for k in range(m)])
    for _ in range(MATCH_CUT_ROUNDS):
        res = linprog(-(np.array(weights, dtype=float) + nudge), A_ub=np.array(rows),
                      b_ub=[1.0] * n + [float((len(s) - 1) // 2) for s in sets], bounds=(0, None), method="highs")
        if res.status != 0:
            return None
        x = res.x
        chosen = [k for k in range(m) if x[k] > 0.5]
        covered = [i for k in chosen for i in ends[k]]
        found = sum(weights[k] for k in chosen) if len(set(covered)) == len(covered) else None
        best = max((w for w in (lower, found) if w is not None), default=None)
        # the exact check is worth running only once the LP value is within reach of a matching in hand
        if best is not None and -res.fun < best + 2:
            bound = _exact_dual_bound(ends, weights, member, sets, n, res.ineqlin.marginals)
            if bound is not None and math.floor(bound) == best:
                return best
        new = []
        for keep in (lambda v: 1e-7 < v < 1.0 - 1e-7, lambda v: v > 1e-7):
            for s in _odd_components(ends, x, n, keep):
                mass = sum(x[k] for k, (i, j) in enumerate(ends) if i in s and j in s)
                if mass > (len(s) - 1) // 2 + 1e-6 and s not in sets and s not in new:
                    new.append(s)
        new += [s for s in _violated_odd_sets(ends, x, n) if s not in sets and s not in new]
        if not new:
            return None
        for s in new:
            row = np.zeros(m)
            for k, (i, j) in enumerate(ends):
                if i in s and j in s:
                    row[k] = 1.0
                    member[k].append(len(sets))
            sets.append(s)
            rows.append(row)
    return None


def _matching_milp(edges):
    """SciPy HiGHS branch-and-cut's reported optimum of the degree-constrained 0/1 program (gap 0), weighed in
    integers from its rounded solution, or None when HiGHS reports no optimum. A floating-point solver's
    report, not a certificate: HiGHS has reported a matching one unit lighter than the optimum as optimal on a
    native graph with weights near 10^6, so this is a retained cross-check only and never certifies."""
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
    names = _vertices(edges)
    index = {x: i for i, x in enumerate(names)}
    a = np.zeros((len(names), len(edges)))
    for k, (u, v, _) in enumerate(edges):
        a[index[u], k] = a[index[v], k] = 1.0
    res = milp(-np.array([float(e[2]) for e in edges]), constraints=LinearConstraint(a, -np.inf, 1.0),
               integrality=np.ones(len(edges)), bounds=Bounds(0.0, 1.0),
               options={"mip_rel_gap": 0.0, "time_limit": 20.0})
    if res.status != 0 or res.x is None:
        return None
    chosen = [k for k, v in enumerate(res.x) if v > 0.5]
    covered = [x for k in chosen for x in (index[edges[k][0]], index[edges[k][1]])]
    if len(set(covered)) != len(covered):
        return None
    return sum(edges[k][2] for k in chosen)


def matching_optimum(edges, lower=None):
    """(optimum, method) by an exact method independent of the blossom solver, chosen by structure: a checked
    bipartite LP dual, exhaustive enumeration, else a checked odd-set LP dual. ``lower`` is the weight of an
    already validated matching (it lets the odd-set dual certify without an integral LP). The optimum is None
    when the method does not close: optimality is then not established, neither certified nor refuted."""
    colour = _two_colouring(edges)
    if colour is not None:
        return _matching_bipartite_dual(edges, colour), "bipartite_lp_dual"
    if len(_vertices(edges)) <= MATCH_EXHAUSTIVE_VERTICES:
        return _matching_exhaustive(edges), "exhaustive_enumeration"
    return _matching_odd_set_dual(edges, lower), "odd_set_lp_dual"


def _matching_weight(edges, pairs):
    """Weight of a well-formed matching (existing edges, vertex-disjoint), or None."""
    weight = {frozenset((u, v)): w for u, v, w in edges}
    if not isinstance(pairs, list) or not all(isinstance(p, list) and len(p) == 2
                                              and all(isinstance(x, str) for x in p) for p in pairs):
        return None
    ends = [x for p in pairs for x in p]
    keys = [frozenset(p) for p in pairs]
    if len(set(ends)) != len(ends) or not all(k in weight for k in keys):
        return None
    return sum(weight[k] for k in keys)


def matching_verify(data, output, certificate):
    edges = _matching_graph(data)
    pairs = output.get("matching") if isinstance(output, dict) else None
    if not isinstance(pairs, list) or not all(isinstance(p, list) and len(p) == 2
                                              and all(isinstance(x, str) for x in p) for p in pairs):
        return {"matching_well_formed": False}
    weight = _matching_weight(edges, pairs)
    if weight is None:
        return {"matching_well_formed": True, "edges_exist_and_are_vertex_disjoint": False}
    if len(_vertices(edges)) > MATCH_NATIVE_VERTICES or len(edges) > MATCH_NATIVE_EDGES:
        return {"matching_well_formed": True, "edges_exist_and_are_vertex_disjoint": True,
                "independent_check_within_bounds": False}
    certificate = _cert(certificate)
    checks = {"matching_well_formed": True, "edges_exist_and_are_vertex_disjoint": True,
              "weight_recomputed": type(output.get("weight")) is int and output["weight"] == weight,
              "certificate_counts_recomputed": certificate.get("vertices") == len(_vertices(edges))
              and certificate.get("edges") == len(edges) and certificate.get("matched_pairs") == len(pairs)}
    optimum, method = matching_optimum(edges, lower=weight)
    if optimum is None:
        # the exact method did not close: optimality is not established, so it is neither certified nor
        # refuted; no floating-point solver's report stands in for a certificate
        return {**checks, "independent_check_within_bounds": False}
    # every method is checked here in exact arithmetic; the check's name records which one established it
    return {**checks, f"optimal_by_{method}": weight == optimum}


def matching_instance(seed):
    r = random.Random(f"genome:graph_matching:{seed}")
    kind = ("general_sparse", "odd_clusters", "bipartite", "geometric")[seed % 4]
    edges, seen = [], set()

    def add(u, v, w):
        if u != v and frozenset((u, v)) not in seen:
            seen.add(frozenset((u, v)))
            edges.append([u, v, w] if r.random() < 0.5 else [v, u, w])
    if kind == "general_sparse":
        n = r.randint(24, 60)
        p = r.uniform(3.0, 6.0) / n
        for i in range(n):
            for j in range(i + 1, n):
                if r.random() < p:
                    add(f"v{i:02d}", f"v{j:02d}", r.randint(1, 100))
    elif kind == "odd_clusters":                              # odd cycles everywhere: blossoms matter
        clusters, k, target = [], 0, r.randint(30, 60)
        while k < target:
            size = r.choice((3, 3, 5, 5, 7))
            clusters.append([f"v{k + i:02d}" for i in range(size)])
            k += size
        for members in clusters:
            for i, a in enumerate(members):
                add(a, members[(i + 1) % len(members)], r.randint(40, 100))
                if r.random() < 0.3:
                    add(a, r.choice(members), r.randint(40, 100))
        flat = [x for members in clusters for x in members]
        for _ in range(len(flat)):
            add(r.choice(flat), r.choice(flat), r.randint(1, 60))
    elif kind == "bipartite":
        a, b = r.randint(12, 30), r.randint(12, 30)
        for i in range(a):
            for j in range(b):
                if r.random() < 0.15:
                    add(f"l{i:02d}", f"r{j:02d}", r.randint(1, 100))
    else:                                                     # pair nearby points; closer pairs are worth more
        pts = [(r.uniform(0, 100), r.uniform(0, 100)) for _ in range(r.randint(24, 60))]
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                d = math.dist(pts[i], pts[j])
                if d < 20:
                    add(f"v{i:02d}", f"v{j:02d}", 150 - round(d))
    if not edges:
        add("v00", "v01", 1)
    r.shuffle(edges)
    data = {"weighted_edges": edges}
    optimum = matching_optimum(_matching_graph(data))[0]
    if optimum is None:                                       # never score against an uncertified truth
        raise GenomeError(f"graph_matching seed {seed}: the optimum is not established by an exact method")
    return data, {"optimum": optimum}


def matching_subregion(data):
    """bipartite; triangle_clustered (at least one triangle per vertex: geometric or community structure, many
    short odd cycles); general_dense (mean degree >= 5); general_sparse."""
    edges = _matching_graph(data)
    if _two_colouring(edges) is not None:
        return "bipartite"
    adj = {}
    for u, v, _ in edges:
        adj.setdefault(u, set()).add(v)
        adj.setdefault(v, set()).add(u)
    triangles = sum(len(adj[u] & adj[v]) for u, v, _ in edges) // 3
    if triangles >= len(adj):
        return "triangle_clustered"
    return "general_dense" if 2 * len(edges) >= 5 * len(adj) else "general_sparse"


def matching_score(data, truth, output):
    if not isinstance(output, dict) or not isinstance(output.get("matching"), list):
        return {"quality": 0.0, "category": "abstain"}
    weight = _matching_weight(_matching_graph(data), output["matching"])
    if weight is None or output.get("weight", weight) != weight or weight > truth["optimum"]:
        return {"quality": -1.0, "category": "wrong"}         # not a matching, or a false weight claim
    q = weight / truth["optimum"] if truth["optimum"] else 1.0
    return {"quality": q, "category": "correct" if weight == truth["optimum"] else "wrong"}


def matching_greedy(data):
    """Baseline: greedy by descending weight (a 1/2-approximation)."""
    edges = _matching_graph(data)
    used, pairs = set(), []
    for w, u, v in sorted(((w, *sorted((u, v))) for u, v, w in edges), key=lambda t: (-t[0], t[1], t[2])):
        if u not in used and v not in used:
            used.update((u, v))
            pairs.append([u, v])
    weight = {frozenset((u, v)): w for u, v, w in edges}
    return {"matching": sorted(pairs), "weight": sum(weight[frozenset(p)] for p in pairs)}


def matching_cpsat(data):
    """Competitor: OR-Tools CP-SAT on the degree-constrained 0/1 program (one worker, fixed seed, 10 s)."""
    from ortools.sat.python import cp_model
    edges = _matching_graph(data)
    model = cp_model.CpModel()
    x = [model.new_bool_var(f"x{k}") for k in range(len(edges))]
    incident = {}
    for k, (u, v, _) in enumerate(edges):
        incident.setdefault(u, []).append(x[k])
        incident.setdefault(v, []).append(x[k])
    for xs in incident.values():
        model.add_at_most_one(xs)
    model.maximize(sum(w * xk for (_, _, w), xk in zip(edges, x)))
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    solver.parameters.max_time_in_seconds = 10.0
    if solver.solve(model) not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    pairs = sorted(sorted((u, v)) for (u, v, _), xk in zip(edges, x) if solver.value(xk))
    return {"matching": pairs, "weight": sum(w for (_, _, w), xk in zip(edges, x) if solver.value(xk))}


# =================================================================== 3. critical path method
CPM_MAX_ACTIVITIES, CPM_NATIVE_ACTIVITIES, CPM_MAX_DURATION, CPM_MAX_LINKS = 2000, 1000, 1_000_000, 20_000


def _project(data):
    """(ids in input order, duration by id, predecessors by id), validated: unique ids, known predecessors and
    no precedence cycle (a cyclic network has no schedule)."""
    acts = _mapping(data).get("activities")
    if not isinstance(acts, list) or not 1 <= len(acts) <= CPM_MAX_ACTIVITIES:
        raise GenomeError(f"activities: 1-{CPM_MAX_ACTIVITIES} objects {{id, duration, after}}")
    ids, dur, preds = [], {}, {}
    for a in acts:
        if not isinstance(a, dict) or not {"id", "duration"} <= set(a) <= {"id", "duration", "after"}:
            raise GenomeError("activity is {id, duration, after: [predecessor ids]}")
        name = _name(a["id"], "activity id")
        if name in dur:
            raise GenomeError(f"duplicate activity id {name}")
        dur[name] = bounded_int(a["duration"], low=0, high=CPM_MAX_DURATION, name="duration")
        after = a.get("after", [])
        if not isinstance(after, list) or not all(isinstance(x, str) for x in after) or len(set(after)) != len(after):
            raise GenomeError("after: a list of distinct predecessor ids")
        ids.append(name)
        preds[name] = list(after)
    if sum(len(p) for p in preds.values()) > CPM_MAX_LINKS:
        raise GenomeError(f"at most {CPM_MAX_LINKS} precedence links")
    for name, after in preds.items():
        for p in after:
            if p not in dur or p == name:
                raise GenomeError(f"{name}: unknown or self predecessor {p!r}")
    colour = dict.fromkeys(ids, 0)                 # cycle check: iterative three-colour depth-first search
    for root in ids:
        if colour[root]:
            continue
        stack = [(root, iter(preds[root]))]
        colour[root] = 1
        while stack:
            node, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                colour[node] = 2
                stack.pop()
            elif colour[nxt] == 1:
                raise GenomeError(f"precedence cycle through {nxt}")
            elif colour[nxt] == 0:
                colour[nxt] = 1
                stack.append((nxt, iter(preds[nxt])))
    return ids, dur, preds


def _cpm_passes(ids, dur, preds):
    """The solver's forward and backward passes in a Kahn topological order."""
    succ = {a: [] for a in ids}
    indeg = {a: len(preds[a]) for a in ids}
    for a in ids:
        for p in preds[a]:
            succ[p].append(a)
    queue, order = deque(a for a in ids if not indeg[a]), []
    while queue:
        a = queue.popleft()
        order.append(a)
        for s in succ[a]:
            indeg[s] -= 1
            if not indeg[s]:
                queue.append(s)
    es = dict.fromkeys(ids, 0)
    for a in order:
        for s in succ[a]:
            es[s] = max(es[s], es[a] + dur[a])
    makespan = max(es[a] + dur[a] for a in ids)
    lf = dict.fromkeys(ids, makespan)
    for a in reversed(order):
        for p in preds[a]:
            lf[p] = min(lf[p], lf[a] - dur[a])
    return es, lf, makespan, succ


def cpm_solve(data, budget):
    ids, dur, preds = _project(data)
    if len(ids) > CPM_NATIVE_ACTIVITIES:
        return _abstain(f"more than {CPM_NATIVE_ACTIVITIES} activities exceeds the bounded answer size",
                        activities=len(ids))
    es, lf, makespan, succ = _cpm_passes(ids, dur, preds)
    end = next(a for a in ids if not succ[a] and es[a] + dur[a] == makespan)
    path = [end]
    while preds[path[-1]]:                         # trace back through a predecessor that finishes just in time
        path.append(next(p for p in preds[path[-1]] if es[p] + dur[p] == es[path[-1]]))
    path.reverse()
    total_float = {a: lf[a] - dur[a] - es[a] for a in ids}
    return answer({"makespan": makespan, "critical_path": path, "earliest_start": es, "total_float": total_float},
                  {"method": "critical path method: forward and backward passes in a Kahn topological order",
                   "activities": len(ids), "precedences": sum(len(p) for p in preds.values()),
                   "critical_activities": sum(1 for a in ids if total_float[a] == 0)})


def cpm_independent(ids, dur, preds):
    """Independent recomputation (no topological queue, no shared code with the solver): earliest finish by an
    explicit-stack depth-first pull over predecessors, latest finish by the mirror pull over successors.
    Returns (earliest finish, latest finish, makespan, successors)."""
    succ = {a: [] for a in ids}
    for a in ids:
        for p in preds[a]:
            succ[p].append(a)

    def pull(links, value):
        out = {}
        for root in ids:
            stack = [(root, False)]
            while stack:
                a, ready = stack.pop()
                if a in out:
                    continue
                if ready:
                    out[a] = value(a, [out[x] for x in links[a]])
                else:
                    stack.append((a, True))
                    stack.extend((x, False) for x in links[a] if x not in out)
        return out
    ef = pull(preds, lambda a, before: dur[a] + max(before, default=0))           # earliest finish
    makespan = max(ef.values())
    ls = pull(succ, lambda a, after: min(after, default=makespan) - dur[a])         # latest start
    return {a: ef[a] for a in ids}, {a: ls[a] + dur[a] for a in ids}, makespan, succ


def _chain_ok(path, dur, preds, succ):
    return (isinstance(path, list) and len(path) >= 1 and all(isinstance(a, str) and a in dur for a in path)
            and len(set(path)) == len(path) and not preds[path[0]] and not succ[path[-1]]
            and all(path[k] in preds[path[k + 1]] for k in range(len(path) - 1)))


def cpm_verify(data, output, certificate):
    ids, dur, preds = _project(data)
    shape = (isinstance(output, dict) and type(output.get("makespan")) is int
             and isinstance(output.get("critical_path"), list)
             and all(isinstance(output.get(k), dict) and all(type(x) is int for x in output[k].values())
                     for k in ("earliest_start", "total_float")))
    if not shape:
        return {"output_shape": False}
    if len(ids) > CPM_NATIVE_ACTIVITIES:
        return {"output_shape": True, "independent_check_within_bounds": False}
    certificate = _cert(certificate)
    ef, lf, makespan, succ = cpm_independent(ids, dur, preds)
    path = output["critical_path"]
    chain = _chain_ok(path, dur, preds, succ)
    return {"output_shape": True,
            "makespan_is_the_longest_path": output["makespan"] == makespan,
            "critical_path_is_a_source_to_sink_chain": chain,
            "critical_path_length_equals_makespan": chain and sum(dur[a] for a in path) == makespan,
            "earliest_starts_recomputed": output["earliest_start"] == {a: ef[a] - dur[a] for a in ids},
            "total_floats_recomputed": output["total_float"] == {a: lf[a] - ef[a] for a in ids},
            "certificate_counts_recomputed": certificate.get("activities") == len(ids)
            and certificate.get("precedences") == sum(len(p) for p in preds.values())
            and certificate.get("critical_activities") == sum(1 for a in ids if lf[a] == ef[a])}


def cpm_instance(seed):
    r = random.Random(f"genome:critical_path:{seed}")
    kind = ("layered", "random_dag", "chain_heavy", "wide")[seed % 4]
    n = r.randint(30, 200)
    names = [f"T{k:03d}" for k in range(n)]               # index order is a topological order
    preds = {a: [] for a in names}
    if kind == "layered":
        layer = sorted(r.randrange(r.randint(5, 12)) for _ in range(n))
        for k, a in enumerate(names):
            before = [names[j] for j in range(k) if layer[j] == layer[k] - 1]
            if before:
                preds[a] = r.sample(before, min(len(before), r.randint(1, 3)))
    elif kind == "random_dag":
        for k, a in enumerate(names[1:], 1):
            window = names[max(0, k - 30):k]
            preds[a] = r.sample(window, min(len(window), r.randint(0, 3)))
    elif kind == "chain_heavy":
        spine = set(r.sample(range(n), n // 3))
        last = None
        for k, a in enumerate(names):
            if k in spine:
                preds[a] = [last] if last else []
                last = a
            elif k:
                preds[a] = r.sample(names[:k], min(k, r.randint(0, 2)))
    else:
        for k, a in enumerate(names[1:], 1):
            if r.random() < 0.6:
                preds[a] = [r.choice(names[:k])]
    dur = {a: 0 if r.random() < 0.05 else r.randint(1, 30) for a in names}
    acts = [{"id": a, "duration": dur[a], "after": preds[a]} for a in names]
    r.shuffle(acts)
    data = {"activities": acts}
    ids, dur, preds = _project(data)
    ef, lf, makespan, _ = cpm_independent(ids, dur, preds)
    return data, {"makespan": makespan, "earliest_start": {a: ef[a] - dur[a] for a in ids},
                  "total_float": {a: lf[a] - ef[a] for a in ids}}


def cpm_subregion(data):
    ids, dur, preds = _project(data)
    depth = cpm_independent(ids, dict.fromkeys(ids, 1), preds)[2]
    if 4 * depth >= len(ids):
        return "deep"                              # a long chain dominates: few activities carry float
    return "dense" if 2 * sum(len(p) for p in preds.values()) >= 3 * len(ids) else "sparse"


def cpm_score(data, truth, output):
    if not isinstance(output, dict) or type(output.get("makespan")) is not int:
        return {"quality": 0.0, "category": "abstain"}
    ids, dur, preds = _project(data)
    succ = {a: [] for a in ids}
    for a in ids:
        for p in preds[a]:
            succ[p].append(a)
    path = output.get("critical_path")
    if (not _chain_ok(path, dur, preds, succ) or sum(dur[a] for a in path) != output["makespan"]
            or any(k in output and output[k] != truth[k] for k in ("earliest_start", "total_float"))):
        return {"quality": -1.0, "category": "wrong"}         # a false path, makespan, start or float claim
    q = output["makespan"] / truth["makespan"] if truth["makespan"] else 1.0
    return {"quality": q, "category": "correct" if output["makespan"] == truth["makespan"] else "wrong"}


def cpm_greedy_chain(data):
    """Baseline: a naive planner's chain - start at the longest source activity, step to the longest successor."""
    ids, dur, preds = _project(data)
    succ = {a: [] for a in ids}
    for a in ids:
        for p in preds[a]:
            succ[p].append(a)
    path = [max((a for a in ids if not preds[a]), key=lambda a: dur[a])]
    while succ[path[-1]]:
        path.append(max(succ[path[-1]], key=lambda a: dur[a]))
    return {"makespan": sum(dur[a] for a in path), "critical_path": path}


def cpm_networkx(data):
    """Competitor: networkx.dag_longest_path on the activity-on-arc expansion (each precedence arc weighs its
    predecessor's duration; sentinel start and finish nodes are tuples, never activity ids). Every arc into
    finish weighs one more than its activity, so finish is the unique farthest node: the longest path cannot
    stop early at a zero-duration milestone that ties with it, and its weight is the makespan plus one."""
    import networkx as nx
    ids, dur, preds = _project(data)
    start, finish = ("start",), ("finish",)
    g = nx.DiGraph()
    g.add_nodes_from(ids)
    has_succ = set()
    for a in ids:
        if not preds[a]:
            g.add_edge(start, a, weight=0)
        for p in preds[a]:
            g.add_edge(p, a, weight=dur[p])
            has_succ.add(p)
    for a in ids:
        if a not in has_succ:
            g.add_edge(a, finish, weight=dur[a] + 1)
    path = nx.dag_longest_path(g, weight="weight")
    return {"makespan": int(nx.path_weight(g, path, weight="weight")) - 1, "critical_path": path[1:-1]}


def cpm_cpsat_makespan(data):
    """Retained exact cross-check: OR-Tools CP-SAT minimum makespan (start variables, precedence constraints)."""
    from ortools.sat.python import cp_model
    ids, dur, preds = _project(data)
    horizon = sum(dur.values())
    model = cp_model.CpModel()
    start = {a: model.new_int_var(0, horizon, f"s{k}") for k, a in enumerate(ids)}
    end = model.new_int_var(0, horizon, "makespan")
    for a in ids:
        model.add(end >= start[a] + dur[a])
        for p in preds[a]:
            model.add(start[a] >= start[p] + dur[p])
    model.minimize(end)
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    solver.parameters.max_time_in_seconds = 10.0
    return int(solver.value(end)) if solver.solve(model) == cp_model.OPTIMAL else None


# =================================================================== 4. minimum-cost flow
MCF_MAX_NODES, MCF_MAX_ARCS, MCF_NATIVE_NODES, MCF_NATIVE_ARCS = 1000, 5000, 200, 1200
MCF_MAX_CAPACITY, MCF_MAX_COST, MCF_MAX_SUPPLY = 1_000_000, 100_000, 1_000_000
_SOURCE, _SINK = "~" * (NAME_MAX + 1) + "source", "~" * (NAME_MAX + 1) + "sink"      # never a valid node name


def _network(data):
    """(arcs as (from, to, capacity, cost), supply by node with 0 default, sorted nodes)."""
    _mapping(data)
    arcs, supplies = data.get("arcs"), data.get("supplies")
    if not isinstance(arcs, list) or not 1 <= len(arcs) <= MCF_MAX_ARCS:
        raise GenomeError(f"arcs: 1-{MCF_MAX_ARCS} arcs [from, to, capacity, unit_cost]")
    out = []
    for e in arcs:
        if not isinstance(e, list) or len(e) != 4:
            raise GenomeError("arc is [from, to, capacity, unit_cost]")
        u, v = _name(e[0], "node"), _name(e[1], "node")
        if u == v:
            raise GenomeError("self-loops are not allowed")
        out.append((u, v, bounded_int(e[2], low=0, high=MCF_MAX_CAPACITY, name="capacity"),
                    bounded_int(e[3], low=-MCF_MAX_COST, high=MCF_MAX_COST, name="unit cost")))
    if not isinstance(supplies, dict) or not supplies:
        raise GenomeError("supplies: {node: integer} (positive supply, negative demand)")
    supply = {}
    for k, s in supplies.items():
        supply[_name(k, "node")] = bounded_int(s, low=-MCF_MAX_SUPPLY, high=MCF_MAX_SUPPLY, name="supply")
    if sum(supply.values()):
        raise GenomeError("supplies must sum to zero")
    nodes = sorted({x for u, v, _, _ in out for x in (u, v)} | set(supply))
    if len(nodes) > MCF_MAX_NODES:
        raise GenomeError(f"at most {MCF_MAX_NODES} nodes")
    return out, {n: supply.get(n, 0) for n in nodes}, nodes


def _residual(arcs, flow):
    out = []
    for (u, v, cap, cost), f in zip(arcs, flow):
        if f < cap:
            out.append((u, v, cost))
        if f > 0:
            out.append((v, u, -cost))
    return out


def _spfa_potentials(nodes, residual):
    """The solver's potentials: queue-based Bellman-Ford from a virtual root at distance 0 to every node, so
    c(u, v) + p(u) - p(v) >= 0 on every residual arc; None if a negative cycle keeps it relaxing."""
    dist = dict.fromkeys(nodes, 0)
    adj = {n: [] for n in nodes}
    for u, v, c in residual:
        adj[u].append((v, c))
    queue, queued, pops, limit = deque(nodes), set(nodes), 0, (len(nodes) + 1) * (len(residual) + 1)
    while queue:
        u = queue.popleft()
        queued.discard(u)
        pops += 1
        if pops > limit:
            return None
        for v, c in adj[u]:
            if dist[u] + c < dist[v]:
                dist[v] = dist[u] + c
                if v not in queued:
                    queued.add(v)
                    queue.append(v)
    return dist


def mcf_solve(data, budget):
    import numpy as np
    from ortools.graph.python import max_flow, min_cost_flow
    arcs, supply, nodes = _network(data)
    if len(nodes) > MCF_NATIVE_NODES or len(arcs) > MCF_NATIVE_ARCS:
        return _abstain(f"network above {MCF_NATIVE_NODES} nodes or {MCF_NATIVE_ARCS} arcs exceeds the bounded "
                        "independently verifiable size", nodes=len(nodes), arcs=len(arcs))
    index = {n: i for i, n in enumerate(nodes)}
    tails = np.array([index[u] for u, _, _, _ in arcs], dtype=np.int64)
    heads = np.array([index[v] for _, v, _, _ in arcs], dtype=np.int64)
    caps = np.array([c for _, _, c, _ in arcs], dtype=np.int64)
    smcf = min_cost_flow.SimpleMinCostFlow()
    ids = smcf.add_arcs_with_capacity_and_unit_cost(tails, heads, caps,
                                                    np.array([c for *_, c in arcs], dtype=np.int64))
    smcf.set_nodes_supplies(np.arange(len(nodes)), np.array([supply[n] for n in nodes], dtype=np.int64))
    status = smcf.solve()
    if status == smcf.INFEASIBLE:
        # Gale's condition fails on the source side X of a minimum cut of the supply/demand max-flow network:
        # supply inside X exceeds the capacity of arcs leaving X.
        smf = max_flow.SimpleMaxFlow()
        s, t = len(nodes), len(nodes) + 1
        smf.add_arcs_with_capacity(tails, heads, caps)
        for n in nodes:
            if supply[n] > 0:
                smf.add_arc_with_capacity(s, index[n], supply[n])
            elif supply[n] < 0:
                smf.add_arc_with_capacity(index[n], t, -supply[n])
        if smf.solve(s, t) != smf.OPTIMAL:
            return _unknown("the infeasibility cut could not be computed")
        side = {nodes[i] for i in smf.get_source_side_min_cut() if i < len(nodes)}
        out_cap = sum(c for u, v, c, _ in arcs if u in side and v not in side)
        return answer({"feasible": False, "flow": None, "cost": None},
                      {"method": "OR-Tools SimpleMinCostFlow reported infeasible; cut from OR-Tools SimpleMaxFlow",
                       "cut": sorted(side), "supply_inside_cut": sum(supply[n] for n in side),
                       "capacity_leaving_cut": out_cap})
    if status != smcf.OPTIMAL:
        return _unknown(f"min-cost flow status {status}")
    flow = [int(f) for f in smcf.flows(ids)]
    potentials = _spfa_potentials(nodes, _residual(arcs, flow))
    if potentials is None:
        return _unknown("the residual graph of the returned flow has a negative cycle")
    return answer({"feasible": True, "flow": flow, "cost": sum(f * a[3] for f, a in zip(flow, arcs))},
                  {"method": "OR-Tools SimpleMinCostFlow (cost scaling); potentials by queue-based Bellman-Ford on "
                             "the residual graph", "potentials": potentials,
                   "optimality": "c(u, v) + p(u) - p(v) >= 0 on every residual arc (no negative cycle)"})


def _feasible_by_edmonds_karp(arcs, supply):
    """Independent feasibility: GREG's own Edmonds-Karp (flow genome) on supplies -> network -> demands."""
    from .flow import edmonds_karp
    edges = [(u, v, c) for u, v, c, _ in arcs if c > 0]
    edges += [(_SOURCE, n, s) for n, s in supply.items() if s > 0] + [(n, _SINK, -s) for n, s in supply.items()
                                                                        if s < 0]
    total = sum(s for s in supply.values() if s > 0)
    if not total:
        return True
    if not any(u == _SOURCE for u, _, _ in edges) or not any(v == _SINK for _, v, _ in edges):
        return False
    return edmonds_karp(edges, _SOURCE, _SINK)[0] == total


def _bellman_ford_clean(nodes, residual):
    """Independent optimality test: classic Bellman-Ford, full passes over the residual arc list from a virtual
    root at 0; True when it settles and every residual arc then has a nonnegative reduced cost."""
    dist = dict.fromkeys(nodes, 0)
    for _ in range(len(nodes) + 1):
        changed = False
        for u, v, c in residual:
            if dist[u] + c < dist[v]:
                dist[v] = dist[u] + c
                changed = True
        if not changed:
            return all(c + dist[u] - dist[v] >= 0 for u, v, c in residual)
    return False


def mcf_verify(data, output, certificate):
    arcs, supply, nodes = _network(data)
    certificate = _cert(certificate)
    if not isinstance(output, dict) or type(output.get("feasible")) is not bool:
        return {"output_shape": False}
    if len(nodes) > MCF_NATIVE_NODES or len(arcs) > MCF_NATIVE_ARCS:
        return {"output_shape": True, "independent_check_within_bounds": False}
    if not output["feasible"]:
        cut = certificate.get("cut")
        side = set(cut) if isinstance(cut, list) and all(isinstance(n, str) for n in cut) else None
        inside = sum(supply[n] for n in side) if side is not None and side <= set(supply) else None
        leaving = sum(c for u, v, c, _ in arcs if u in side and v not in side) if inside is not None else None
        cut_ok = (inside is not None and len(side) == len(cut) and inside > leaving
                  and certificate.get("supply_inside_cut") == inside
                  and certificate.get("capacity_leaving_cut") == leaving)
        return {"output_shape": output.get("flow") is None and output.get("cost") is None,
                "cut_certifies_infeasibility": cut_ok,
                "infeasible_by_independent_max_flow": not _feasible_by_edmonds_karp(arcs, supply)}
    flow = output.get("flow")
    if not _int_list(flow, len(arcs)):
        return {"output_shape": False}
    balance = dict.fromkeys(nodes, 0)
    for (u, v, _, _), f in zip(arcs, flow):
        balance[u] += f
        balance[v] -= f
    # the residual graph, built here rather than by the solver's helper: spare forward capacity at the arc's cost,
    # cancellable flow backward at the negated cost
    residual = ([(u, v, cost) for (u, v, cap, cost), f in zip(arcs, flow) if f < cap]
                + [(v, u, -cost) for (u, v, _, cost), f in zip(arcs, flow) if f > 0])
    p = certificate.get("potentials")
    return {"output_shape": True,
            "capacity_respected": all(0 <= f <= a[2] for f, a in zip(flow, arcs)),
            "supplies_met_and_flow_conserved": balance == supply,
            "cost_recomputed": type(output.get("cost")) is int
            and output["cost"] == sum(f * a[3] for f, a in zip(flow, arcs)),
            "certificate_potentials_give_nonnegative_reduced_costs": isinstance(p, dict) and set(p) == set(nodes)
            and all(type(x) is int for x in p.values()) and all(c + p[u] - p[v] >= 0 for u, v, c in residual),
            "optimal_by_independent_residual_bellman_ford": _bellman_ford_clean(nodes, residual)}


def mcf_lp_optimum(arcs, supply, nodes):
    """Evaluation truth by a third method: the min-cost-flow LP (SciPy HiGHS); integral by total unimodularity.
    None when infeasible."""
    import numpy as np
    from scipy.optimize import linprog
    index = {n: i for i, n in enumerate(nodes)}
    a = np.zeros((len(nodes), len(arcs)))
    for k, (u, v, _, _) in enumerate(arcs):
        a[index[u], k] += 1.0
        a[index[v], k] -= 1.0
    res = linprog([float(e[3]) for e in arcs], A_eq=a, b_eq=[float(supply[n]) for n in nodes],
                  bounds=[(0, e[2]) for e in arcs], method="highs")
    if res.status == 2:
        return None
    if res.status != 0 or abs(res.fun - round(res.fun)) > 1e-6:
        raise GenomeError("reference LP did not solve to an integral optimum")
    return int(round(res.fun))


def mcf_instance(seed):
    r = random.Random(f"genome:min_cost_flow:{seed}")
    kind = ("transportation", "transshipment", "rebates")[seed % 3]
    arcs = []
    if kind == "transportation":
        sources = [f"plant{i}" for i in range(r.randint(4, 10))]
        sinks = [f"store{j}" for j in range(r.randint(5, 15))]
        supply = {s: r.randint(10, 60) for s in sources}
        total = sum(supply.values())
        cuts = sorted(r.sample(range(1, total), len(sinks) - 1))
        for d, (lo, hi) in zip(sinks, zip([0] + cuts, cuts + [total])):
            supply[d] = -(hi - lo)
        for s in sources:
            for d in sinks:
                cost = r.randint(1, 60)
                if r.random() < 0.7:
                    arcs.append([s, d, r.randint(5, 40), cost])
                arcs.append([s, d, total, cost + r.randint(100, 150)])        # premium freight, always open
    else:
        sources = [f"src{i}" for i in range(r.randint(3, 6))]
        hubs = [f"hub{i}" for i in range(r.randint(5, 12))]
        sinks = [f"dst{j}" for j in range(r.randint(4, 10))]
        supply = {s: r.randint(10, 50) for s in sources}
        total = sum(supply.values())
        cuts = sorted(r.sample(range(1, total), len(sinks) - 1))
        for d, (lo, hi) in zip(sinks, zip([0] + cuts, cuts + [total])):
            supply[d] = -(hi - lo)
        for s in sources:
            for h in hubs:
                if r.random() < 0.6:
                    arcs.append([s, h, r.randint(5, 30), r.randint(1, 30)])
        for h in hubs:
            for k in hubs:
                if h != k and r.random() < 0.15:
                    arcs.append([h, k, r.randint(5, 30), r.randint(1, 15)])
            for d in sinks:
                if r.random() < 0.5:
                    rebate = kind == "rebates" and r.random() < 0.3
                    arcs.append([h, d, r.randint(5, 30), -r.randint(1, 10) if rebate else r.randint(1, 30)])
        for s in sources:                                                    # premium courier, always open
            arcs.append([s, "courier", total, r.randint(80, 120)])
        for d in sinks:
            arcs.append(["courier", d, total, 0])
    r.shuffle(arcs)
    data = {"arcs": arcs, "supplies": supply}
    return data, {"optimum": mcf_lp_optimum(*_network(data))}


def mcf_subregion(data):
    arcs, supply, _ = _network(data)
    if all(supply[u] > 0 and supply[v] < 0 for u, v, _, _ in arcs):
        return "transportation"
    return "rebates" if any(c < 0 for *_, c in arcs) else "transshipment"


def _flow_cost(arcs, supply, flow):
    """Cost of a feasible flow (bounds and supplies met), or None."""
    if not _int_list(flow, len(arcs)) or not all(0 <= f <= a[2] for f, a in zip(flow, arcs)):
        return None
    balance = dict.fromkeys(supply, 0)
    for (u, v, _, _), f in zip(arcs, flow):
        balance[u] += f
        balance[v] -= f
    return sum(f * a[3] for f, a in zip(flow, arcs)) if balance == supply else None


def mcf_score(data, truth, output):
    if not isinstance(output, dict) or type(output.get("feasible")) is not bool:
        return {"quality": 0.0, "category": "abstain"}
    arcs, supply, _ = _network(data)
    if truth["optimum"] is None:
        ok = output["feasible"] is False
        return {"quality": 1.0 if ok else -1.0, "category": "correct" if ok else "wrong"}
    cost = _flow_cost(arcs, supply, output.get("flow")) if output["feasible"] else None
    if cost is None or output.get("cost", cost) != cost or cost < truth["optimum"]:
        return {"quality": -1.0, "category": "wrong"}         # infeasible flow, false cost or false infeasibility
    return {"quality": _ratio(cost, truth["optimum"]), "category": "correct" if cost == truth["optimum"] else "wrong"}


def mcf_greedy(data):
    """Baseline: repeatedly ship along the cheapest path of remaining capacity from any node with supply left to
    any node with demand left (multi-source Dijkstra), never rerouting earlier shipments (no residual reverse
    arcs). Abstains on negative costs (Dijkstra needs nonnegative ones) and when it gets stuck."""
    arcs, supply, nodes = _network(data)
    if any(c < 0 for *_, c in arcs):
        return None
    left = [c for _, _, c, _ in arcs]
    flow = [0] * len(arcs)
    rest = dict(supply)
    out = {n: [] for n in nodes}
    for k, (u, _, _, _) in enumerate(arcs):
        out[u].append(k)
    while any(s > 0 for s in rest.values()):
        dist, via = {n: 0 for n in nodes if rest[n] > 0}, {}
        heap = [(0, n) for n in sorted(dist)]
        done, target = set(), None
        while heap:
            d, u = heapq.heappop(heap)
            if u in done:
                continue
            done.add(u)
            if rest[u] < 0:
                target = u
                break
            for k in out[u]:
                v = arcs[k][1]
                if left[k] > 0 and v not in done and d + arcs[k][3] < dist.get(v, math.inf):
                    dist[v] = d + arcs[k][3]
                    via[v] = k
                    heapq.heappush(heap, (dist[v], v))
        if target is None:
            return None                                            # stuck without rerouting
        path, v = [], target
        while v in via:
            path.append(via[v])
            v = arcs[via[v]][0]
        push = min([rest[v], -rest[target]] + [left[k] for k in path])
        for k in path:
            left[k] -= push
            flow[k] += push
        rest[v] -= push
        rest[target] += push
    return {"feasible": True, "flow": flow, "cost": sum(f * a[3] for f, a in zip(flow, arcs))}


def mcf_networkx(data):
    """Competitor: networkx.network_simplex on a MultiDiGraph (parallel arcs kept by key)."""
    import networkx as nx
    arcs, supply, nodes = _network(data)
    g = nx.MultiDiGraph()
    for n in nodes:
        g.add_node(n, demand=-supply[n])
    for k, (u, v, cap, cost) in enumerate(arcs):
        g.add_edge(u, v, key=k, capacity=cap, weight=cost)
    try:
        cost, flows = nx.network_simplex(g)
    except nx.NetworkXUnfeasible:
        return {"feasible": False, "flow": None, "cost": None}
    return {"feasible": True, "flow": [int(flows[u][v][k]) for k, (u, v, _, _) in enumerate(arcs)], "cost": int(cost)}


# =================================================================== genomes
INTELLIGENCES = [
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.or.linear_assignment", version="1.0.0", family="assignment_lsa", layer=3,
            operation="min_cost_assignment", epistemic_class="optimization",
            subgeometry="linear sum assignment: each row to a distinct column at minimum total cost (rows <= columns)",
            source_provenance="Kuhn (1955) Hungarian method; Crouse (2016) shortest augmenting path as in "
                              "scipy.optimize.linear_sum_assignment (BSD-3); LP duality",
            native_representation="integer cost matrix, rows = agents, columns = tasks",
            required_inputs=("cost_matrix",),
            output_contract={"assignment": "[column per row]", "cost": "int"},
            algorithm_or_runtime="scipy.optimize.linear_sum_assignment; dual potentials by Bellman-Ford over the "
                                 "column exchange graph (scipy.sparse.csgraph)",
            parameters={"native_side": LSA_NATIVE_SIDE},
            composition_inputs=("cost model",), composition_outputs=("assignment", "cost", "column potentials"),
            evidence_type="optimality_certificate",
            verification_method="arithmetic LP-duality check of the returned potentials (u_i + v_j <= c_ij for every "
                                "pair, v_j <= 0, equality on the assignment, zero on unused columns, dual objective "
                                "= cost) and an independent pure-Python Hungarian method whose feasible dual must "
                                "equal the claimed cost",
            confidence_semantics="exact optimum of the supplied matrix, certified by LP duality in integer arithmetic",
            resource_profile="O(n^2 m) assignment plus O(m^3) Bellman-Ford for the potentials; <= 100 columns native",
            latency_profile="milliseconds at benchmark size",
            known_strengths=("exact with a checkable dual certificate", "rectangular matrices (rows <= columns)",
                             "column potentials price each task: the cost of one more unit of that column"),
            known_failure_modes=("the cost matrix supplied by the caller may be wrong",
                                 "one task per agent only: no capacities or side constraints",
                                 "with ties one of several optimal assignments is returned"),
            counterindications=("agents that take several tasks (use min_cost_flow)",
                                "side constraints such as budgets or conflicts (use an integer program)",
                                "interaction costs between assignments (quadratic assignment)"),
            abstention_conditions=(f"more than {LSA_NATIVE_SIDE} columns (beyond the bounded independently "
                                   "verifiable size)",),
            benchmark_suite="uniform, geometric (Euclidean worker-job), machine-job product, few-level and "
                            "rectangular integer matrices with 20-80 rows; seeds 0-9 dev, held-out seeds fixed by "
                            "the admission freeze",
            baseline="global greedy: take the cheapest remaining (row, column) pair until every row is assigned",
            competitor="OR-Tools SimpleLinearSumAssignment (cost scaling) on square matrices, OR-Tools "
                       "SimpleMinCostFlow on rectangular ones", dependency="scipy", **_common()),
        solve=assignment_solve, verify=assignment_verify, instance=assignment_instance, score=assignment_score,
        baseline=assignment_greedy, competitor=assignment_ortools, subregion=assignment_subregion, tolerance=1e-9),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.graph.max_weight_matching", version="1.0.0", family="graph_matching", layer=3,
            operation="max_weight_matching", epistemic_class="optimization",
            subgeometry="maximum-weight matching on general (non-bipartite) undirected graphs",
            source_provenance="Edmonds (1965) blossom algorithm; Galil (1986); networkx.max_weight_matching (BSD-3)",
            native_representation="undirected weighted graph as an edge list", required_inputs=("weighted_edges",),
            output_contract={"matching": "[[u, v]]", "weight": "int"},
            algorithm_or_runtime="networkx.max_weight_matching (primal-dual blossom algorithm, O(V^3))",
            parameters={"native_vertices": MATCH_NATIVE_VERTICES, "native_edges": MATCH_NATIVE_EDGES,
                        "maxcardinality": False},
            composition_inputs=("pairing preferences as edge weights",), composition_outputs=("matching", "weight"),
            evidence_type="exact_calculation",
            verification_method="matching validity, weight and certificate counts by arithmetic; optimality against an "
                                "independent exact method chosen by structure, named in the check: an integral LP "
                                "dual (Hungarian potentials) checked arithmetically on bipartite graphs; exhaustive "
                                f"enumeration up to {MATCH_EXHAUSTIVE_VERTICES} vertices; otherwise a dual of "
                                "Edmonds' odd-set matching LP (HiGHS cutting planes with exact Padberg-Rao odd-set "
                                "separation over a Gomory-Hu tree) made feasible and checked in exact rational "
                                "arithmetic, which bounds every matching by its floor and is closed by a matching "
                                "of exactly that weight. When it does not close the check is reported not within "
                                "bounds: optimality is neither certified nor refuted",
            confidence_semantics="exact maximum weight, certified in exact arithmetic: on bipartite graphs by an LP "
                                 f"dual, up to {MATCH_EXHAUSTIVE_VERTICES} vertices by exhaustive enumeration, and "
                                 "on larger general graphs by a checked dual of Edmonds' odd-set LP. A floating-point "
                                 "solver's report never certifies. Where the cutting planes do not close within "
                                 f"{MATCH_CUT_ROUNDS} rounds optimality is not established; that did not happen on "
                                 "the 308 non-bipartite graphs of development seeds 0-9 and review seeds 3000-3399 "
                                 "nor on 1,898 random review graphs with adversarial weights (uniform to 10^6, near "
                                 "10^6, two-level 1 or 10^6, unit, 0-3)",
            resource_profile="O(V^3) pure Python; <= 80 vertices and 400 edges native",
            latency_profile="tens of milliseconds at benchmark size",
            known_strengths=("exact on general graphs where bipartite methods and the degree LP fail (odd cycles)",
                             "polynomial time without integer programming"),
            known_failure_modes=("the blossom dual is not exported: the answer carries no checkable certificate of "
                                 "its own; the verifier constructs one, and on a general graph where its cutting "
                                 "planes do not close it reports optimality not established, which the canonical "
                                 "path records as a failed check although the answer may be optimal",
                                 "pure Python O(V^3): slow beyond a few hundred vertices",
                                 "maximum weight, not maximum cardinality: a heavier matching may leave more "
                                 "vertices unmatched"),
            counterindications=("bipartite pairing with a dense cost matrix (use assignment_lsa)",
                                "capacitated or b-matching (use min_cost_flow or an integer program)",
                                "pairings that must cover every vertex (perfect matching is not enforced)"),
            abstention_conditions=(f"more than {MATCH_NATIVE_VERTICES} vertices or {MATCH_NATIVE_EDGES} edges",),
            benchmark_suite="general sparse, odd-cycle cluster, bipartite and geometric graphs of at most 66 "
                            "vertices: vertex targets of 24-60, which the odd-cycle cluster kind overshoots by up to "
                            "one cluster of 7, less any vertex left without an edge (18-66 vertices on development "
                            "seeds 0-9 and review seeds 3000-3999); seeds 0-9 dev, held-out seeds fixed by the "
                            "admission freeze",
            baseline="greedy by descending weight (a 1/2-approximation)",
            competitor="OR-Tools CP-SAT on the degree-constrained 0/1 program (one worker, fixed seed)",
            dependency="networkx", **_common()),
        solve=matching_solve, verify=matching_verify, instance=matching_instance, score=matching_score,
        baseline=matching_greedy, competitor=matching_cpsat, subregion=matching_subregion, tolerance=1e-9),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.or.critical_path", version="1.0.0", family="critical_path", layer=3,
            operation="project_critical_path", epistemic_class="optimization",
            subgeometry="activity-on-node project network: fixed durations, finish-to-start precedences",
            source_provenance="Kelley and Walker (1959) critical path method; longest path in a DAG",
            native_representation="activities with integer durations and predecessor lists",
            required_inputs=("activities",),
            output_contract={"makespan": "int", "critical_path": "[activity id]", "earliest_start": "{id: int}",
                             "total_float": "{id: int}"},
            algorithm_or_runtime="forward and backward passes in a Kahn topological order; the critical path traced "
                                 "back from a sink that finishes at the makespan",
            parameters={"native_activities": CPM_NATIVE_ACTIVITIES},
            composition_inputs=("work breakdown with durations",),
            composition_outputs=("makespan", "critical_path", "total_float"),
            evidence_type="exact_calculation",
            verification_method="independent explicit-stack depth-first recomputation of earliest and latest finishes "
                                "(pull from predecessors and from successors), total float and makespan; the path must "
                                "be a source-to-sink precedence chain whose durations sum to the makespan; the "
                                "certificate's activity, precedence and critical-activity counts are recomputed",
            confidence_semantics="exact for the supplied deterministic durations and precedences; a plan, not an "
                                 "observation of how long the work will take",
            resource_profile="O(activities + precedences)", latency_profile="milliseconds at benchmark size",
            known_strengths=("linear time", "total float says which activities may slip and by how much",
                             "names the schedule's control points"),
            known_failure_modes=("durations are point estimates: with uncertain durations the expected makespan "
                                 "exceeds the CPM makespan (merge bias)",
                                 "ignores resource limits: two critical activities may need the same crew",
                                 "finish-to-start links without lags only"),
            counterindications=("uncertain durations (PERT or Monte Carlo schedule risk)",
                                "shared limited resources (resource-constrained scheduling, e.g. CP-SAT)",
                                "start-to-start or lagged precedences"),
            abstention_conditions=(f"more than {CPM_NATIVE_ACTIVITIES} activities",),
            benchmark_suite="layered, random-order DAG, chain-heavy and wide project networks of 30-200 activities "
                            "with zero-duration milestones in shuffled input order; seeds 0-9 dev, held-out seeds "
                            "fixed by the admission freeze",
            baseline="greedy chain: start at the longest source activity and step to the longest successor",
            competitor="networkx.dag_longest_path on the activity-on-arc expansion (CP-SAT makespan minimisation "
                       "retained as an exact cross-check)", **_common()),
        solve=cpm_solve, verify=cpm_verify, instance=cpm_instance, score=cpm_score,
        baseline=cpm_greedy_chain, competitor=cpm_networkx, subregion=cpm_subregion, tolerance=1e-9),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.graph.min_cost_flow", version="1.0.0", family="min_cost_flow", layer=3,
            operation="min_cost_flow_plan", epistemic_class="optimization",
            subgeometry="single-commodity minimum-cost flow with node supplies and arc capacities "
                        "(transportation, transshipment)",
            source_provenance="Ford and Fulkerson (1962); Goldberg-Tarjan cost scaling as in OR-Tools "
                              "SimpleMinCostFlow (Apache-2.0); negative-cycle optimality criterion",
            native_representation="arcs [from, to, capacity, unit cost] and node supplies (positive supply, "
                                  "negative demand)",
            required_inputs=("arcs", "supplies"),
            output_contract={"feasible": "bool", "flow": "[int per arc] or null", "cost": "int or null"},
            algorithm_or_runtime="OR-Tools SimpleMinCostFlow; node potentials by queue-based Bellman-Ford on the "
                                 "residual graph; an infeasibility cut from OR-Tools SimpleMaxFlow",
            parameters={"native_nodes": MCF_NATIVE_NODES, "native_arcs": MCF_NATIVE_ARCS},
            composition_inputs=("network", "supply and demand forecast"),
            composition_outputs=("flow", "cost", "node potentials"),
            evidence_type="optimality_certificate",
            verification_method="capacity, supply and conservation arithmetic; reduced costs of every residual arc "
                                "under the returned potentials; an independent classic Bellman-Ford over the residual "
                                "graph must find no negative cycle; infeasibility by the returned cut (supply inside "
                                "exceeds capacity out) and an independent Edmonds-Karp max flow",
            confidence_semantics="exact optimum, or proven infeasibility, of the supplied network, certified by "
                                 "reduced costs and cut capacities in integer arithmetic",
            resource_profile="cost-scaling min-cost flow plus O(V E) potentials; <= 200 nodes and 1200 arcs native",
            latency_profile="milliseconds at benchmark size",
            known_strengths=("exact with a checkable potentials certificate",
                             "node potentials are the shadow price of one more unit supplied at each node",
                             "proves infeasibility with a cut instead of failing silently"),
            known_failure_modes=("single commodity: different goods sharing arcs are not separated",
                                 "linear costs only: fixed charges and economies of scale are not modelled",
                                 "supplied capacities and costs may be wrong"),
            counterindications=("multi-commodity flows", "fixed-charge or concave costs (use an integer program)",
                                "lot sizes other than single units"),
            abstention_conditions=(f"more than {MCF_NATIVE_NODES} nodes or {MCF_NATIVE_ARCS} arcs",),
            benchmark_suite="transportation, transshipment with tight capacities and a premium courier, and rebate "
                            "(negative-cost) networks of 9-29 nodes; seeds 0-9 dev, held-out seeds fixed by the "
                            "admission freeze",
            baseline="greedy cheapest remaining path from supply to demand without rerouting (no residual reverse "
                     "arcs); abstains on negative costs or when stuck",
            competitor="networkx.network_simplex", dependency="ortools", **_common()),
        solve=mcf_solve, verify=mcf_verify, instance=mcf_instance, score=mcf_score,
        baseline=mcf_greedy, competitor=mcf_networkx, subregion=mcf_subregion, tolerance=1e-9),
]
