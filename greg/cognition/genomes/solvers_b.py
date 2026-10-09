"""Layer 3 direct mathematical intelligences, batch B: six exact or statistically certified solvers.

Six executables on GREG's one cognition path (``greg.cognition.cortex.reason`` -> isolated worker ->
independent verifier -> CognitiveReceipt). Each is an ordinary, well-understood algorithm; the genome
records where it is natively competent, what it is compared against, and how its output is checked.

* ``dp_knapsack`` (``knapsack_01_select``): exact 0/1 knapsack by dynamic programming over capacity.
  Verified by an independent dynamic program over profit (minimum weight per value).
* ``search_astar`` (``grid_astar_route``): A* on weighted 4-connected grids with the admissible and
  consistent heuristic ``min cell cost x Manhattan distance``. Verified by path replay and an
  independent Dijkstra.
* ``mc_importance`` (``tilted_tail_probability``): rare-event probability ``P(X_1 + ... + X_n > t)`` for
  iid exponential components by exponentially tilted importance sampling at a fixed, seeded sample
  budget. Verified by the Chernoff bound and an independent pure-Python replication.
* ``queue_erlang`` (``erlang_c_staffing``): minimum M/M/c staffing meeting ``P(wait > T) <= alpha`` by the
  exact Erlang-C formula (Erlang-B recursion). Verified by a log-space Poisson-sum evaluation.
* ``bayes_interval`` (``jeffreys_credible_interval``): equal-tailed Jeffreys Beta-binomial credible
  interval (Brown-Cai-DasGupta boundary rule). Verified by the forward regularised incomplete beta.
* ``game_minimax`` (``zero_sum_lp_equilibrium``): two-player zero-sum matrix game solved by the
  primal/dual linear programs (SciPy HiGHS). Verified by arithmetic exploitability (duality gap).

Everything is read-only computation: no files, network, subprocesses or environment access, and no
output of any method here creates authority.
"""
from __future__ import annotations

from collections import deque
import heapq
import math
import random
from statistics import NormalDist

from .contract import Executable, GenomeError, IntelligenceGenome, answer, bounded_int, finite

LINEAGE = ("INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION", "INTENT-20261007-VERIFIED-POLYINTELLIGENCE-LIFT",
           "greg/cognition/solvers.py (GREG's existing bounded solvers)")


def _common(**kw):
    return dict(buildability="BUILDABLE_NOW", memory_model="stateless",
                learning_rule="none (competence settles per geometry through GREG outcomes)", lineage=LINEAGE, **kw)


def _abstain(reason, **certificate):
    return answer(None, {"reason": reason, **certificate}, status="ABSTAIN", missing=[reason])


def _mapping(data):
    """Every input is a JSON object; anything else is invalid input, never an AttributeError."""
    if not isinstance(data, dict):
        raise GenomeError("data must be a JSON object")
    return data


def _cert(certificate):
    """A verifier reads the certificate defensively: a non-object certificate binds nothing."""
    return certificate if isinstance(certificate, dict) else {}


# =================================================================== 1. 0/1 knapsack by dynamic programming
KS_NATIVE_ITEMS, KS_NATIVE_CAPACITY = 60, 2000           # native DP size (n x (C + 1) cells)
KS_MAX_ITEMS, KS_MAX_CAPACITY, KS_MAX_VALUE = 500, 1_000_000, 10_000
KS_VERIFY_MAX_TOTAL = KS_NATIVE_ITEMS * KS_MAX_VALUE      # the profit DP is O(n x total value): bound it


def _knapsack(data):
    _mapping(data)
    values, weights = data.get("values"), data.get("weights")
    if (not isinstance(values, list) or not isinstance(weights, list) or len(values) != len(weights)
            or not 1 <= len(values) <= KS_MAX_ITEMS):
        raise GenomeError(f"values and weights: equal-length lists of 1-{KS_MAX_ITEMS} items")
    v = [bounded_int(x, low=0, high=KS_MAX_VALUE, name="value") for x in values]
    w = [bounded_int(x, low=1, high=KS_MAX_CAPACITY, name="weight") for x in weights]
    cap = bounded_int(data.get("capacity"), low=0, high=KS_MAX_CAPACITY, name="capacity")
    return v, w, cap


def _dantzig_bound(v, w, cap):
    """LP-relaxation (fractional) upper bound: fill by value density, split the first item that does not fit."""
    room, bound = cap, 0.0
    for i in sorted(range(len(v)), key=lambda i: (-v[i] / w[i], i)):
        if w[i] <= room:
            room -= w[i]
            bound += v[i]
        else:
            bound += v[i] * room / w[i]
            break
    return bound


def knapsack_solve(data, budget):
    import numpy as np
    v, w, cap = _knapsack(data)
    n = len(v)
    if n > KS_NATIVE_ITEMS or cap > KS_NATIVE_CAPACITY:
        return _abstain(f"pseudo-polynomial DP is native only to <= {KS_NATIVE_ITEMS} items and capacity "
                        f"<= {KS_NATIVE_CAPACITY}", items=n, capacity=cap)
    dp = np.zeros(cap + 1, dtype=np.int64)            # dp[c] = best value with weight <= c, items 0..i
    keep = np.zeros((n, cap + 1), dtype=bool)
    for i in range(n):
        wi = w[i]
        if wi > cap or v[i] == 0:
            continue
        cand = dp[:cap + 1 - wi] + v[i]               # built from the previous row: 0/1 semantics
        take = cand > dp[wi:]
        keep[i, wi:] = take
        dp[wi:] = np.where(take, cand, dp[wi:])
    best, c, chosen = int(dp[cap]), cap, []
    for i in range(n - 1, -1, -1):
        if keep[i, c]:
            chosen.append(i)
            c -= w[i]
    chosen.sort()
    used = sum(w[i] for i in chosen)
    bound = _dantzig_bound(v, w, cap)
    return answer({"selected": chosen, "value": best, "weight": used},
                  {"method": "exact dynamic program over capacities 0..C", "dp_optimum": best, "cells": n * (cap + 1),
                   "lp_upper_bound": round(bound, 9), "gap_to_lp_bound": round(bound - best, 9)})


def _profit_dp_optimum(v, w, cap):
    """Independent exact method: minimum weight achieving each total value; optimum = largest value within C."""
    import numpy as np
    total = sum(v)
    big = np.int64(10 ** 15)
    minw = np.full(total + 1, big, dtype=np.int64)
    minw[0] = 0
    for vi, wi in zip(v, w):
        if vi == 0:
            continue
        minw[vi:] = np.minimum(minw[vi:], minw[:total + 1 - vi] + wi)
    return int(np.nonzero(minw <= cap)[0].max())


def knapsack_verify(data, output, certificate):
    v, w, cap = _knapsack(data)
    certificate = _cert(certificate)
    sel = output.get("selected") if isinstance(output, dict) else None
    valid = (isinstance(sel, list) and all(type(i) is int and 0 <= i < len(v) for i in sel)
             and len(set(sel)) == len(sel))
    if not valid:
        return {"indices_valid_and_distinct": False}
    if sum(v) > KS_VERIFY_MAX_TOTAL:
        # The solver answers only native instances; an answer outside the bound cannot be checked cheaply,
        # so it is not verified (a refusal, never a pass).
        return {"indices_valid_and_distinct": True, "independent_check_within_bounds": False}
    value, weight = sum(v[i] for i in sel), sum(w[i] for i in sel)
    optimum = _profit_dp_optimum(v, w, cap)
    bound = certificate.get("lp_upper_bound")
    return {"indices_valid_and_distinct": True, "within_capacity": weight <= cap,
            "value_recomputed": value == output.get("value") and weight == output.get("weight"),
            "certificate_matches": certificate.get("dp_optimum") == value
            and type(bound) in (int, float) and bound >= optimum - 1e-6,     # a valid bound covers the optimum
            "optimal_by_independent_profit_dp": value == optimum}


def knapsack_instance(seed):
    r = random.Random(910_000 + seed)
    kind = ("uncorrelated", "weakly_correlated", "strongly_correlated", "subset_sum")[seed % 4]
    n = r.randint(20, KS_NATIVE_ITEMS)
    w = [r.randint(5, 120) for _ in range(n)]
    if kind == "uncorrelated":
        v = [r.randint(1, 150) for _ in w]
    elif kind == "weakly_correlated":
        v = [max(1, wi + r.randint(-20, 20)) for wi in w]
    elif kind == "strongly_correlated":
        v = [wi + 20 for wi in w]
    else:
        v = list(w)
    cap = min(KS_NATIVE_CAPACITY, int(sum(w) * r.uniform(0.25, 0.6)))
    data = {"values": v, "weights": w, "capacity": cap}
    return data, {"optimum": _profit_dp_optimum(v, w, cap)}


def knapsack_subregion(data):
    v, w = data["values"], data["weights"]
    if v == w:
        return "subset_sum"
    if len({a - b for a, b in zip(v, w)}) == 1:
        return "strongly_correlated"
    if all(abs(a - b) <= 20 for a, b in zip(v, w)):
        return "weakly_correlated"
    return "uncorrelated"


def knapsack_score(data, truth, output):
    if not isinstance(output, dict) or not isinstance(output.get("selected"), list):
        return {"quality": 0.0, "category": "abstain"}
    v, w, cap = _knapsack(data)
    sel = output["selected"]
    if (any(type(i) is not int or not 0 <= i < len(v) for i in sel) or len(set(sel)) != len(sel)
            or sum(w[i] for i in sel) > cap or output.get("value", sum(v[i] for i in sel)) != sum(v[i] for i in sel)):
        return {"quality": -1.0, "category": "wrong"}         # overweight, malformed or a false value claim
    value = sum(v[i] for i in sel)
    q = value / truth["optimum"] if truth["optimum"] else 1.0
    return {"quality": q, "category": "correct" if value == truth["optimum"] else "wrong"}


def knapsack_greedy(data):
    """Baseline: greedy by value density, scanning every item and taking each one that still fits."""
    v, w, cap = _knapsack(data)
    room, chosen = cap, []
    for i in sorted(range(len(v)), key=lambda i: (-v[i] / w[i], i)):
        if w[i] <= room:
            chosen.append(i)
            room -= w[i]
    chosen.sort()
    return {"selected": chosen, "value": sum(v[i] for i in chosen), "weight": cap - room}


def knapsack_ortools(data):
    """Competitor: OR-Tools' dedicated 0/1 knapsack solver (compiled branch and bound, the solver of the OR-Tools
    knapsack guide). Exact unless its time limit stops it; then its best solution is returned and scored."""
    from ortools.algorithms.python import knapsack_solver
    v, w, cap = _knapsack(data)
    solver = knapsack_solver.KnapsackSolver(
        knapsack_solver.SolverType.KNAPSACK_MULTIDIMENSION_BRANCH_AND_BOUND_SOLVER, "greg_knapsack")
    solver.set_time_limit(10.0)
    solver.init(v, [w], [cap])
    solver.solve()
    chosen = [i for i in range(len(v)) if solver.best_solution_contains(i)]
    return {"selected": chosen, "value": sum(v[i] for i in chosen), "weight": sum(w[i] for i in chosen)}


def knapsack_cpsat(data):
    """Former competitor (1.0.0 builder run), retained as an exact cross-check: OR-Tools CP-SAT, one worker,
    fixed seed. A general CP model whose construction dominates its latency on this geometry; the dedicated
    knapsack solver above is the stronger reasonable alternative."""
    from ortools.sat.python import cp_model
    v, w, cap = _knapsack(data)
    model = cp_model.CpModel()
    x = [model.new_bool_var(f"x{i}") for i in range(len(v))]
    model.add(sum(wi * xi for wi, xi in zip(w, x)) <= cap)
    model.maximize(sum(vi * xi for vi, xi in zip(v, x)))
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    solver.parameters.max_time_in_seconds = 10.0
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    chosen = [i for i, xi in enumerate(x) if solver.value(xi)]
    return {"selected": chosen, "value": sum(v[i] for i in chosen), "weight": sum(w[i] for i in chosen)}


# =================================================================== 2. A* on weighted 4-connected grids
GRID_NATIVE, GRID_MAX, CELL_MAX = 60, 200, 1000
_MOVES = {"U": (-1, 0), "D": (1, 0), "L": (0, -1), "R": (0, 1)}


def _cell(value, rows, cols, name):
    if not isinstance(value, list) or len(value) != 2:
        raise GenomeError(f"{name} is [row, col]")
    r = bounded_int(value[0], low=0, high=rows - 1, name=f"{name} row")
    c = bounded_int(value[1], low=0, high=cols - 1, name=f"{name} col")
    return r * cols + c


def _grid(data):
    grid = _mapping(data).get("grid")
    if not isinstance(grid, list) or not 1 <= len(grid) <= GRID_MAX or not isinstance(grid[0], list):
        raise GenomeError(f"grid: 1-{GRID_MAX} rows of cell costs (0 = blocked)")
    cols = len(grid[0])
    if not 1 <= cols <= GRID_MAX or any(not isinstance(row, list) or len(row) != cols for row in grid):
        raise GenomeError(f"grid: rectangular, 1-{GRID_MAX} columns")
    cells = [bounded_int(x, low=0, high=CELL_MAX, name="cell cost") for row in grid for x in row]
    rows = len(grid)
    s, t = _cell(data.get("start"), rows, cols, "start"), _cell(data.get("goal"), rows, cols, "goal")
    if cells[s] == 0 or cells[t] == 0:
        raise GenomeError("start and goal cells must be passable")
    return cells, rows, cols, s, t


def _neighbors(u, rows, cols):
    r, c = divmod(u, cols)
    if r > 0:
        yield u - cols
    if r < rows - 1:
        yield u + cols
    if c > 0:
        yield u - 1
    if c < cols - 1:
        yield u + 1


def _moves(parent, s, t, cols):
    path, u = [], t
    while u != s:
        p = parent[u]
        d = u - p
        path.append("D" if d == cols else "U" if d == -cols else "R" if d == 1 else "L")
        u = p
    return "".join(reversed(path))


def astar_solve(data, budget):
    cells, rows, cols, s, t = _grid(data)
    if rows > GRID_NATIVE or cols > GRID_NATIVE:
        return _abstain(f"grid exceeds the {GRID_NATIVE}x{GRID_NATIVE} bounded search size", rows=rows, cols=cols)
    minc = min(c for c in cells if c > 0)
    tr, tc = divmod(t, cols)
    inf = float("inf")
    g = [inf] * len(cells)
    parent = [-1] * len(cells)
    closed = bytearray(len(cells))
    g[s] = 0
    heap = [(minc * (abs(s // cols - tr) + abs(s % cols - tc)), 0, s)]
    expanded = 0
    while heap:
        _, neg_g, u = heapq.heappop(heap)
        if closed[u]:
            continue
        closed[u] = 1
        expanded += 1
        if u == t:
            break
        gu = -neg_g
        for v in _neighbors(u, rows, cols):
            cv = cells[v]
            if cv == 0 or closed[v]:
                continue
            nv = gu + cv
            if nv < g[v]:
                g[v] = nv
                parent[v] = u
                vr, vc = divmod(v, cols)
                heapq.heappush(heap, (nv + minc * (abs(vr - tr) + abs(vc - tc)), -nv, v))
    heuristic = "min passable cell cost x Manhattan distance (admissible and consistent on a 4-connected grid)"
    if not closed[t]:
        return answer({"reachable": False, "moves": None, "cost": None},
                      {"method": "A* exhausted the reachable component", "expanded": expanded, "heuristic": heuristic})
    moves = _moves(parent, s, t, cols)
    return answer({"reachable": True, "moves": moves, "cost": int(g[t]), "steps": len(moves)},
                  {"method": "A* with closed list; goal popped first at cost g = f", "heuristic": heuristic,
                   "min_cell_cost": minc, "expanded": expanded, "cells": len(cells),
                   "optimality": "a consistent heuristic makes the first goal expansion optimal"})


def _walk(cells, rows, cols, s, t, moves):
    """Replay a move string; the cost of entering each cell, or None if the path is invalid."""
    if not isinstance(moves, str) or len(moves) > rows * cols:
        return None
    r, c = divmod(s, cols)
    cost = 0
    for m in moves:
        d = _MOVES.get(m)
        if d is None:
            return None
        r, c = r + d[0], c + d[1]
        if not (0 <= r < rows and 0 <= c < cols) or cells[r * cols + c] == 0:
            return None
        cost += cells[r * cols + c]
    return cost if r * cols + c == t else None


def _dijkstra_cost(cells, rows, cols, s, t):
    """Independent exact shortest-path cost (plain Dijkstra, no heuristic); None when unreachable."""
    dist = {s: 0}
    heap = [(0, s)]
    done = set()
    while heap:
        d, u = heapq.heappop(heap)
        if u in done:
            continue
        if u == t:
            return d
        done.add(u)
        r, c = divmod(u, cols)
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            rr, cc = r + dr, c + dc
            if 0 <= rr < rows and 0 <= cc < cols:
                v = rr * cols + cc
                if cells[v] and v not in done and d + cells[v] < dist.get(v, float("inf")):
                    dist[v] = d + cells[v]
                    heapq.heappush(heap, (dist[v], v))
    return None


def astar_verify(data, output, certificate):
    cells, rows, cols, s, t = _grid(data)
    if not isinstance(output, dict) or type(output.get("reachable")) is not bool:
        return {"output_shape": False}
    optimum = _dijkstra_cost(cells, rows, cols, s, t)
    if not output["reachable"]:
        return {"output_shape": True, "unreachable_confirmed_by_dijkstra": optimum is None}
    cost = _walk(cells, rows, cols, s, t, output.get("moves"))
    return {"output_shape": True, "path_valid": cost is not None, "cost_recomputed": cost == output.get("cost"),
            "optimal_by_independent_dijkstra": cost is not None and cost == optimum}


def _reachable(cells, rows, cols, s, t):
    seen, queue = {s}, deque([s])
    while queue:
        u = queue.popleft()
        if u == t:
            return True
        for v in _neighbors(u, rows, cols):
            if cells[v] and v not in seen:
                seen.add(v)
                queue.append(v)
    return False


def astar_instance(seed):
    r = random.Random(920_000 + seed)
    kind = ("open_weighted", "obstacle_uniform", "walls_and_mud")[seed % 3]
    rows, cols = r.randint(30, GRID_NATIVE), r.randint(30, GRID_NATIVE)
    if kind == "open_weighted":
        grid = [[0 if r.random() < 0.08 else r.randint(1, 9) for _ in range(cols)] for _ in range(rows)]
    elif kind == "obstacle_uniform":
        grid = [[0 if r.random() < 0.3 else 1 for _ in range(cols)] for _ in range(rows)]
    else:
        grid = [[1] * cols for _ in range(rows)]
        for _ in range(r.randint(3, 7)):                       # cost patches ("mud")
            r0, c0 = r.randrange(rows), r.randrange(cols)
            cost = r.randint(4, 9)
            for rr in range(r0, min(rows, r0 + r.randint(4, 14))):
                for cc in range(c0, min(cols, c0 + r.randint(4, 14))):
                    grid[rr][cc] = cost
        for _ in range(r.randint(4, 9)):                       # walls with one or two gaps
            if r.random() < 0.5:
                row, c0, length = r.randrange(rows), r.randrange(cols // 2), r.randint(cols // 3, cols)
                gaps = {r.randrange(c0, min(cols, c0 + length)) for _ in range(r.randint(1, 2))}
                for cc in range(c0, min(cols, c0 + length)):
                    if cc not in gaps:
                        grid[row][cc] = 0
            else:
                col, r0, length = r.randrange(cols), r.randrange(rows // 2), r.randint(rows // 3, rows)
                gaps = {r.randrange(r0, min(rows, r0 + length)) for _ in range(r.randint(1, 2))}
                for rr in range(r0, min(rows, r0 + length)):
                    if rr not in gaps:
                        grid[rr][col] = 0
    start = [r.randrange(rows // 4), r.randrange(cols // 4)]
    goal = [rows - 1 - r.randrange(rows // 4), cols - 1 - r.randrange(cols // 4)]
    for rr, cc in (start, goal):
        grid[rr][cc] = grid[rr][cc] or 1
    data = {"grid": grid, "start": start, "goal": goal}
    cells, rows, cols, s, t = _grid(data)
    if not _reachable(cells, rows, cols, s, t):                # carve a random monotone corridor
        rr, cc = start
        while [rr, cc] != goal:
            if rr != goal[0] and (cc == goal[1] or r.random() < 0.5):
                rr += 1 if goal[0] > rr else -1
            else:
                cc += 1 if goal[1] > cc else -1
            grid[rr][cc] = grid[rr][cc] or 1
        cells, rows, cols, s, t = _grid(data)
    return data, {"cost": _dijkstra_cost(cells, rows, cols, s, t)}


def astar_subregion(data):
    passable = [x for row in data["grid"] for x in row if x]
    ones = sum(1 for x in passable if x == 1) / len(passable)
    return "obstacle_uniform" if ones == 1.0 else "walls_and_mud" if ones > 0.5 else "open_weighted"


def astar_score(data, truth, output):
    if not isinstance(output, dict) or "reachable" not in output:
        return {"quality": -10.0, "category": "abstain"}
    cells, rows, cols, s, t = _grid(data)
    optimum = truth["cost"]
    if not output["reachable"]:
        return {"quality": 0.0, "category": "correct"} if optimum is None else {"quality": -11.0, "category": "wrong"}
    cost = _walk(cells, rows, cols, s, t, output.get("moves"))
    if cost is None or optimum is None or cost != output.get("cost"):
        return {"quality": -11.0, "category": "wrong"}          # invalid path or a false cost claim
    ratio = cost / optimum if optimum else (1.0 if cost == 0 else 9.9)
    return {"quality": -min(ratio, 9.9), "category": "correct" if cost == optimum else "wrong"}


def astar_greedy(data):
    """Baseline: greedy best-first search (priority = Manhattan distance only, closed set)."""
    cells, rows, cols, s, t = _grid(data)
    tr, tc = divmod(t, cols)
    parent = {s: s}
    heap = [(abs(s // cols - tr) + abs(s % cols - tc), s)]
    while heap:
        _, u = heapq.heappop(heap)
        if u == t:
            break
        for v in _neighbors(u, rows, cols):
            if cells[v] and v not in parent:
                parent[v] = u
                heapq.heappush(heap, (abs(v // cols - tr) + abs(v % cols - tc), v))
    if t not in parent:
        return {"reachable": False, "moves": None, "cost": None}
    moves = _moves(parent, s, t, cols)
    return {"reachable": True, "moves": moves, "cost": _walk(cells, rows, cols, s, t, moves)}


def astar_csgraph(data):
    """Competitor: SciPy's compiled Dijkstra (scipy.sparse.csgraph) on the equivalent directed graph, edge weight =
    cost of entering the head cell; the graph is built with vectorised NumPy (no Python-level edge loop)."""
    import numpy as np
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import dijkstra
    cells, rows, cols, s, t = _grid(data)
    cost = np.asarray(cells, dtype=np.float64)
    index = np.arange(rows * cols).reshape(rows, cols)
    pairs = ((index[:, :-1], index[:, 1:]), (index[:-1, :], index[1:, :]))
    tail = np.concatenate([x.ravel() for a, b in pairs for x in (a, b)])
    head = np.concatenate([x.ravel() for a, b in pairs for x in (b, a)])
    keep = (cost[tail] > 0) & (cost[head] > 0)
    tail, head = tail[keep], head[keep]
    graph = csr_matrix((cost[head], (tail, head)), shape=(rows * cols, rows * cols))
    dist, pred = dijkstra(graph, directed=True, indices=s, return_predecessors=True)
    if not np.isfinite(dist[t]):
        return {"reachable": False, "moves": None, "cost": None}
    parent, u = {}, t
    while u != s:
        parent[u] = int(pred[u])
        u = parent[u]
    return {"reachable": True, "moves": _moves(parent, s, t, cols), "cost": int(round(float(dist[t])))}


def astar_networkx(data):
    """Former competitor (1.0.0 builder run), retained as a cross-check: NetworkX Dijkstra on the equivalent
    directed graph. Pure Python, and its dict-of-dicts graph construction dominates its latency; SciPy's compiled
    Dijkstra above is the stronger reasonable alternative (GREG's existing ``graph`` family uses NetworkX)."""
    import networkx as nx
    cells, rows, cols, s, t = _grid(data)
    g = nx.DiGraph()
    g.add_node(s)
    g.add_weighted_edges_from((u, v, cells[v]) for u in range(len(cells)) if cells[u]
                              for v in _neighbors(u, rows, cols) if cells[v])
    try:
        path = nx.dijkstra_path(g, s, t, weight="weight")
    except nx.NetworkXNoPath:
        return {"reachable": False, "moves": None, "cost": None}
    parent = {b: a for a, b in zip(path, path[1:])}
    moves = _moves(parent, s, t, cols)
    return {"reachable": True, "moves": moves, "cost": sum(cells[u] for u in path[1:])}


# =================================================================== 3. rare-event probability by tilted IS
MC_MAX_DRAWS = 2_000_000
MC_COMPONENTS = ("exponential", "lognormal", "pareto")
MC_LOG_FLOOR = math.log(1e-290)            # below this an estimate is UNKNOWN (outside the float contract)
MC_SE_RATIO = 2.0                          # claimed vs replicated relative SE agree within 2x (0.73-1.26 observed)
MC_MIN_ESS = 50.0                          # below this the CLT standard error is not trustworthy: UNKNOWN


def _tail(data):
    component = _mapping(data).get("component")
    if component not in MC_COMPONENTS:
        raise GenomeError(f"component is one of {MC_COMPONENTS}")
    n = bounded_int(data.get("terms"), low=1, high=500, name="terms")
    thr = finite(data.get("threshold"), low=1e-9, high=1e9, name="threshold")
    samples = bounded_int(data.get("samples"), low=100, high=200_000, name="samples")
    seed = bounded_int(data.get("seed"), low=0, high=2 ** 31 - 1, name="seed")
    rate = finite(data.get("rate"), low=1e-6, high=1e6, name="rate") if component == "exponential" else None
    return component, n, rate, thr, samples, seed


def _log_chernoff(n, rate, thr):
    """Optimal Chernoff bound for a Gamma(n, rate) upper tail at thr > n / rate: n log(rate t / n) - rate t + n."""
    return n * math.log(rate * thr / n) - rate * thr + n


def mc_solve(data, budget):
    import numpy as np
    component, n, rate, thr, samples, seed = _tail(data)
    if component != "exponential":
        return _abstain(f"{component} components are heavy-tailed: no moment generating function, so exponential "
                        "tilting is undefined (conditional Monte Carlo / Asmussen-Kroese is the native method)")
    if thr <= n / rate:
        return _abstain("threshold at or below the mean: not a rare upper-tail event (crude Monte Carlo suffices)")
    if n * samples > MC_MAX_DRAWS:
        return _abstain(f"terms x samples exceeds the {MC_MAX_DRAWS} draw budget", draws=n * samples)
    tilt = n / thr                                     # tilted rate: the tilted mean of the sum equals thr
    rng = np.random.default_rng(seed)
    total = rng.exponential(1.0 / tilt, size=(samples, n)).sum(axis=1)
    hit = total > thr
    hits = int(hit.sum())
    if hits < 2:
        return answer(None, {"seed": seed, "samples": samples, "hits": hits}, status="UNKNOWN",
                      missing=["too few tilted samples reached the event for an estimate"])
    # Likelihood ratios in log space, scaled by the largest one: the mean, variance and ESS stay finite and
    # nonzero for probabilities far below the square root of the smallest double (no false zero SE, no NaN).
    log_w = n * math.log(rate / tilt) - (rate - tilt) * total[hit]
    top = float(log_w.max())
    scaled = np.exp(log_w - top)                       # in (0, 1]; zero weights for misses are implicit
    s1, s2 = float(scaled.sum()), float((scaled * scaled).sum())
    log_est = top + math.log(s1 / samples)
    if log_est < MC_LOG_FLOOR:
        return answer(None, {"seed": seed, "samples": samples, "hits": hits,
                             "log10_estimate": log_est / math.log(10)}, status="UNKNOWN",
                      missing=["the probability is below the double-precision range this output contract carries"])
    est = math.exp(log_est)
    se = math.exp(top) * math.sqrt(max(0.0, s2 - s1 * s1 / samples) / (samples - 1)) / math.sqrt(samples)
    ess = s1 * s1 / s2
    if ess < MC_MIN_ESS:
        # A few likelihood ratios dominate: the estimate and its CLT standard error are both unreliable (off the
        # benchmark, errors of several decades were observed with a claimed relative SE near 1).
        return answer(None, {"seed": seed, "samples": samples, "hits": hits, "effective_sample_size": round(ess, 3)},
                      status="UNKNOWN", missing=[f"degenerate importance weights: effective sample size {ess:.1f} < "
                                                 f"{MC_MIN_ESS:.0f}; more samples or a better proposal are needed"])
    return answer({"probability": est, "std_error": se,
                   "ci95": [max(0.0, est - 1.959964 * se), min(1.0, est + 1.959964 * se)]},
                  {"estimator": "exponentially tilted importance sampling (likelihood-ratio weighted indicator)",
                   "rng": "numpy default_rng (PCG64)", "seed": seed, "samples": samples, "tilted_rate": tilt,
                   "hits": hits, "estimate": est, "std_error": se, "relative_error": se / est,
                   "effective_sample_size": round(ess, 3),
                   "log10_chernoff_bound": _log_chernoff(n, rate, thr) / math.log(10),
                   "model": "iid exponential components; validity of that model is not established here"})


def _python_replication(n, rate, thr, samples, seed):
    """Independent re-estimate: pure-Python sampler, different stream, same tilted-IS identity, log-space weights.
    Returns (log estimate, relative standard error), or None when fewer than two samples hit the event."""
    rng = random.Random(seed ^ 0x5BD1E995)
    tilt = n / thr
    const = n * math.log(rate / tilt)
    logs = []
    for _ in range(samples):
        total = 0.0
        for _ in range(n):
            total += rng.expovariate(tilt)
        if total > thr:
            logs.append(const - (rate - tilt) * total)
    if len(logs) < 2:
        return None
    top = max(logs)
    s1 = s2 = 0.0
    for x in logs:
        y = math.exp(x - top)
        s1 += y
        s2 += y * y
    rel_se = math.sqrt(max(0.0, s2 - s1 * s1 / samples) / (samples - 1)) / math.sqrt(samples) / (s1 / samples)
    return top + math.log(s1 / samples), rel_se


def mc_verify(data, output, certificate):
    component, n, rate, thr, samples, seed = _tail(data)
    certificate = _cert(certificate)
    p = output.get("probability") if isinstance(output, dict) else None
    if component != "exponential" or type(p) is not float or not 0.0 < p <= 1.0 or not math.isfinite(p):
        return {"probability_in_unit_interval": False}
    replication = _python_replication(n, rate, thr, samples, seed)
    if replication is None:
        return {"probability_in_unit_interval": True, "independent_replication_agrees": False}
    log_rep, rep_rel = replication
    se = output.get("std_error")
    se_ok = type(se) is float and math.isfinite(se) and se > 0
    # Both runs use the same estimator and sample size. The claimed SE may widen the agreement tolerance only up
    # to 2x the independently replicated SE, so an inflated self-reported SE cannot buy agreement.
    claimed_rel = se / p if se_ok else math.inf
    tolerance = 6.0 * math.hypot(min(claimed_rel, MC_SE_RATIO * rep_rel), rep_rel) + 0.02
    ci, z = output.get("ci95"), 1.959964
    ci_ok = (se_ok and isinstance(ci, list) and len(ci) == 2 and all(type(x) is float for x in ci)
             and abs(ci[0] - max(0.0, p - z * se)) <= 1e-9 * p and abs(ci[1] - min(1.0, p + z * se)) <= 1e-9 * p)
    return {"probability_in_unit_interval": True, "std_error_valid": se_ok,
            "std_error_consistent_with_replication": se_ok and rep_rel > 0
            and 1.0 / MC_SE_RATIO <= claimed_rel / rep_rel <= MC_SE_RATIO,
            "below_chernoff_bound": math.log(p) <= _log_chernoff(n, rate, thr) + 1e-9,
            "ci95_matches_std_error": ci_ok,
            "certificate_bound": certificate.get("seed") == seed and certificate.get("samples") == samples
            and certificate.get("estimate") == p,
            "independent_replication_agrees": abs(math.log(p) - log_rep) <= tolerance}


def mc_instance(seed):
    from scipy.stats import gamma
    r = random.Random(930_000 + seed)
    n = int(round(10 ** r.uniform(0.0, math.log10(40))))
    rate = round(r.uniform(0.2, 5.0), 3)
    target = 10 ** r.uniform(-10.0, -3.0)
    thr = float(f"{gamma.isf(target, n, scale=1.0 / rate):.6g}")
    data = {"component": "exponential", "terms": n, "rate": rate, "threshold": thr, "samples": 4000,
            "seed": r.randrange(2 ** 31)}
    return data, {"probability": float(gamma.sf(thr, n, scale=1.0 / rate))}     # analytic Gamma tail


def mc_subregion(data):
    n = data["terms"]
    return "terms_1_2" if n <= 2 else "terms_3_10" if n <= 10 else "terms_11_plus"


MC_CORRECT_LOG10 = math.log10(1.25)          # within 25% of the truth counts as a correct estimate


def mc_score(data, truth, output):
    if not isinstance(output, dict) or "probability" not in output:
        return {"quality": -11.0, "category": "abstain"}
    p = output["probability"]
    if type(p) not in (int, float) or not math.isfinite(p) or not 0 < p <= 1:
        return {"quality": -12.0, "category": "wrong"}          # zero claims impossibility: a false answer
    err = abs(math.log10(p / truth["probability"]))
    return {"quality": -min(err, 10.0), "category": "correct" if err <= MC_CORRECT_LOG10 else "wrong"}


def mc_crude(data):
    """Baseline: crude Monte Carlo at the same sample budget; with zero hits it cannot estimate (abstains)."""
    import numpy as np
    component, n, rate, thr, samples, seed = _tail(data)
    if component != "exponential":
        return None
    total = np.random.default_rng(seed).exponential(1.0 / rate, size=(samples, n)).sum(axis=1)
    hits = int((total > thr).sum())
    return {"probability": hits / samples} if hits else None


def mc_saddlepoint(data):
    """Competitor: Lugannani-Rice saddle-point tail approximation from the closed-form CGF (deterministic).
    Stronger than the CLT/normal approximation, which misses rare tails by orders of magnitude."""
    component, n, rate, thr, samples, seed = _tail(data)
    if component != "exponential" or thr == n / rate:
        return None
    theta = rate - n / thr                              # K'(theta) = n / (rate - theta) = thr
    cgf = n * math.log(rate * thr / n)                  # K(theta) = -n log(1 - theta / rate)
    w = math.copysign(math.sqrt(max(0.0, 2.0 * (theta * thr - cgf))), theta)
    u = theta * thr / math.sqrt(n)                      # theta * sqrt(K''(theta)), K'' = thr^2 / n
    tail = 0.5 * math.erfc(w / math.sqrt(2.0))
    density = math.exp(-0.5 * w * w) / math.sqrt(2.0 * math.pi)
    p = tail + density * (1.0 / u - 1.0 / w)
    return {"probability": p} if 0 < p <= 1 and math.isfinite(p) else None


# =================================================================== 4. Erlang-C minimum staffing
Q_MAX_LOAD, Q_MAX_AGENTS = 20_000.0, 40_000


def _queue(data):
    lam = finite(_mapping(data).get("arrival_rate"), low=1e-9, high=1e6, name="arrival_rate")
    aht = finite(data.get("mean_service_time"), low=1e-9, high=1e7, name="mean_service_time")
    target = finite(data.get("target_wait"), low=0.0, high=1e7, name="target_wait")
    alpha = finite(data.get("max_wait_probability"), low=1e-6, high=0.999, name="max_wait_probability")
    abandonment = finite(data.get("abandonment_rate", 0.0), low=0.0, high=1e6, name="abandonment_rate")
    cv = finite(data.get("service_time_cv", 1.0), low=0.0, high=100.0, name="service_time_cv")
    load = lam * aht
    if load > Q_MAX_LOAD:
        raise GenomeError(f"offered load {load:.1f} Erlangs exceeds {Q_MAX_LOAD:.0f}")
    return lam, aht, target, alpha, load, abandonment, cv


def _p_exceed(erlang_c, agents, lam, aht, target):
    return erlang_c * math.exp(-(agents / aht - lam) * target)


def erlang_solve(data, budget):
    lam, aht, target, alpha, load, abandonment, cv = _queue(data)
    if abandonment > 0:
        return _abstain("callers abandon: Erlang-C ignores patience (Erlang-A / M/M/c+M is the native model)")
    if abs(cv - 1.0) > 0.25:
        return _abstain("service times are not exponential (cv != 1): M/G/c needs an approximation or simulation")
    agents = math.floor(load) + 1
    erlang_b = 1.0
    for k in range(1, agents + 1):                     # Erlang-B recursion, numerically stable
        erlang_b = load * erlang_b / (k + load * erlang_b)
    previous = None
    while True:
        erlang_c = agents * erlang_b / (agents - load * (1.0 - erlang_b))
        p = _p_exceed(erlang_c, agents, lam, aht, target)
        if p <= alpha:
            break
        previous = p
        agents += 1
        if agents > Q_MAX_AGENTS:
            return answer(None, {"agents_searched": Q_MAX_AGENTS}, status="UNKNOWN",
                          missing=["no staffing level within the search bound meets the target"])
        erlang_b = load * erlang_b / (agents + load * erlang_b)
    return answer({"agents": agents, "p_wait_exceeds_target": p, "erlang_c": erlang_c, "occupancy": load / agents},
                  {"method": "exact Erlang-C via the Erlang-B recursion; P(W > T) = C(c, a) exp(-(c mu - lambda) T)",
                   "offered_load": load, "p_at_agents": p,
                   "p_at_agents_minus_one": previous if previous is not None else "unstable (c - 1 <= offered load)",
                   "minimality": "P(W > T) is decreasing in c, so the first c meeting the target is the minimum",
                   "model": "M/M/c, FCFS, no abandonment; real arrival and service processes are unverified"})


def _erlang_c_logsum(agents, load):
    """Independent evaluation: log-space Poisson terms (lgamma) with log-sum-exp."""
    logs = [k * math.log(load) - math.lgamma(k + 1) for k in range(agents)]
    last = agents * math.log(load) - math.lgamma(agents + 1) + math.log(agents / (agents - load))
    top = max(max(logs), last)
    return math.exp(last - top) / (sum(math.exp(x - top) for x in logs) + math.exp(last - top))


def erlang_verify(data, output, certificate):
    lam, aht, target, alpha, load, abandonment, cv = _queue(data)
    c = output.get("agents") if isinstance(output, dict) else None
    if type(c) is not int or not load < c <= Q_MAX_AGENTS:
        return {"stable_staffing": False}
    p = _p_exceed(_erlang_c_logsum(c, load), c, lam, aht, target)
    below = c - 1
    minimal = below <= load or _p_exceed(_erlang_c_logsum(below, load), below, lam, aht, target) > alpha
    claimed = output.get("p_wait_exceeds_target")
    return {"stable_staffing": True, "meets_target": p <= alpha * (1 + 1e-9), "minimal": minimal,
            "probability_recomputed": type(claimed) is float and abs(claimed - p) <= 1e-9 + 1e-6 * p,
            # an M/M/c answer to a question the model does not cover is not verified (the solver abstains there)
            "model_preconditions_hold": abandonment == 0.0 and abs(cv - 1.0) <= 0.25}


def _erlang_c_poisson(agents, load):
    """Truth path: Erlang-B as a truncated Poisson ratio (SciPy), converted to Erlang-C."""
    from scipy.stats import poisson
    erlang_b = math.exp(float(poisson.logpmf(agents, load)) - float(poisson.logcdf(agents, load)))
    return erlang_b / (1.0 - (load / agents) * (1.0 - erlang_b))


def erlang_truth(data):
    lam, aht, target, alpha, load, *_ = _queue(data)
    agents = math.floor(load) + 1
    while _p_exceed(_erlang_c_poisson(agents, load), agents, lam, aht, target) > alpha:
        agents += 1
    return agents


def erlang_instance(seed):
    r = random.Random(940_000 + seed)
    load = 10 ** r.uniform(math.log10(2.0), math.log10(400.0))
    aht = float(r.choice((120, 180, 240, 300, 420, 600)))
    data = {"arrival_rate": round(load / aht, 6), "mean_service_time": aht,
            "target_wait": float(r.choice((10, 20, 30, 60, 120))),
            "max_wait_probability": r.choice((0.05, 0.1, 0.15, 0.2, 0.3))}
    return data, {"agents": erlang_truth(data)}


def erlang_subregion(data):
    load = data["arrival_rate"] * data["mean_service_time"]
    return "load_under_10" if load < 10 else "load_10_100" if load < 100 else "load_over_100"


def erlang_score(data, truth, output):
    if not isinstance(output, dict) or "agents" not in output:
        return {"quality": -1.5, "category": "abstain"}
    c, best = output["agents"], truth["agents"]
    if type(c) is not int or c < 1:
        return {"quality": -3.0, "category": "wrong"}
    if c == best:
        return {"quality": 0.0, "category": "correct"}
    if c > best:                                              # meets the SLA, wastes staff
        return {"quality": -min((c - best) / best, 1.0), "category": "wrong"}
    return {"quality": -2.0 - min((best - c) / best, 1.0), "category": "wrong"}   # violates the SLA


def erlang_utilisation(data):
    """Baseline: the utilisation rule of thumb, agents = ceil(offered load / 0.85)."""
    lam, aht, *_ = _queue(data)
    return {"agents": max(1, math.ceil(lam * aht / 0.85 - 1e-12))}


def erlang_halfin_whitt(data):
    """Competitor: square-root staffing c = ceil(a + beta sqrt(a)), beta from the Halfin-Whitt QED delay
    probability [1 + beta Phi(beta)/phi(beta)]^-1 times the conditional tail exp(-beta sqrt(a) T / aht)."""
    lam, aht, target, alpha, load, *_ = _queue(data)
    root = math.sqrt(load)

    def p_exceed(b):
        phi = math.exp(-0.5 * b * b) / math.sqrt(2.0 * math.pi)
        if phi == 0.0:
            return 0.0
        delay = 1.0 / (1.0 + b * (0.5 * math.erfc(-b / math.sqrt(2.0))) / phi)
        return delay * math.exp(-b * root * target / aht)

    lo, hi = 0.0, 1.0
    while p_exceed(hi) > alpha and hi < 64:
        hi *= 2.0
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        lo, hi = (lo, mid) if p_exceed(mid) <= alpha else (mid, hi)
    return {"agents": max(math.floor(load) + 1, math.ceil(load + hi * root - 1e-12))}


# =================================================================== 5. Jeffreys credible interval
def _binomial(data):
    k = bounded_int(_mapping(data).get("successes"), low=0, high=10_000_000, name="successes")
    n = bounded_int(data.get("trials"), low=1, high=10_000_000, name="trials")
    if k > n:
        raise GenomeError("successes cannot exceed trials")
    level = finite(data.get("level", 0.9), low=0.5, high=0.999, name="level")
    independent = data.get("independent_trials", True)
    if type(independent) is not bool:
        raise GenomeError("independent_trials is a boolean")
    return k, n, level, independent


def jeffreys_solve(data, budget):
    from scipy.stats import beta
    k, n, level, independent = _binomial(data)
    if not independent:
        return _abstain("trials are not independent (clustered or overdispersed): the binomial likelihood is "
                        "invalid; a beta-binomial or hierarchical model is required")
    a, b, tail = k + 0.5, n - k + 0.5, (1.0 - level) / 2.0
    lower = 0.0 if k == 0 else float(beta.ppf(tail, a, b))
    upper = 1.0 if k == n else float(beta.ppf(1.0 - tail, a, b))
    mass = float(beta.cdf(upper, a, b) - beta.cdf(lower, a, b))
    return answer({"lower": lower, "upper": upper, "level": level, "posterior_mean": a / (a + b)},
                  {"prior": "Jeffreys Beta(1/2, 1/2)", "posterior": [a, b], "tail_mass": tail,
                   "boundary_rule": "Brown-Cai-DasGupta: lower = 0 when k = 0, upper = 1 when k = n",
                   "posterior_mass_in_interval": mass,
                   "model": "exchangeable Bernoulli trials; the prior is a convention, not evidence"})


def jeffreys_verify(data, output, certificate):
    from scipy.special import betainc                   # forward CDF: independent of the solver's inverse
    k, n, level, independent = _binomial(data)
    certificate = _cert(certificate)
    lo = output.get("lower") if isinstance(output, dict) else None
    hi = output.get("upper") if isinstance(output, dict) else None
    if type(lo) is not float or type(hi) is not float or not 0.0 <= lo <= hi <= 1.0:
        return {"ordered_unit_interval": False}
    a, b, tail = k + 0.5, n - k + 0.5, (1.0 - level) / 2.0
    cdf_lo, cdf_hi = float(betainc(a, b, lo)), float(betainc(a, b, hi))
    return {"ordered_unit_interval": True,
            "lower_is_posterior_quantile": lo == 0.0 if k == 0 else abs(cdf_lo - tail) <= 1e-7,
            "upper_is_posterior_quantile": hi == 1.0 if k == n else abs(cdf_hi - (1.0 - tail)) <= 1e-7,
            "posterior_mass_at_least_level": cdf_hi - cdf_lo >= level - 1e-7,
            "posterior_parameters": certificate.get("posterior") == [a, b],
            "level_as_requested": output.get("level") == level,
            "binomial_model_applies": independent}


def bayes_instance(seed):
    r = random.Random(950_000 + seed)
    n = r.randint(5, 40)
    u = r.random()
    if u < 0.2:
        p = r.uniform(0.002, 0.06)
    elif u < 0.4:
        p = 1.0 - r.uniform(0.002, 0.06)
    else:
        p = r.uniform(0.06, 0.94)
    k = sum(r.random() < p for _ in range(n))
    return {"successes": k, "trials": n, "level": 0.9}, {"p": p}      # truth: the generating parameter


def bayes_subregion(data):
    k, n = data["successes"], data["trials"]
    return "boundary_count" if k in (0, n) else "near_boundary" if min(k, n - k) <= 2 else "interior"


def interval_score(data, truth, output):
    """Negative Gneiting-Raftery interval score at alpha = 1 - level; a covering interval is correct."""
    if not isinstance(output, dict) or "lower" not in output or "upper" not in output:
        return {"quality": -1.0, "category": "abstain"}       # equal to the vacuous interval [0, 1]
    lo, hi = output["lower"], output["upper"]
    if (type(lo) not in (int, float) or type(hi) not in (int, float) or not math.isfinite(lo)
            or not math.isfinite(hi) or not 0.0 <= lo <= hi <= 1.0):
        return {"quality": -25.0, "category": "wrong"}
    alpha, p = 1.0 - _binomial(data)[2], truth["p"]
    s = (hi - lo) + (2.0 / alpha) * max(0.0, lo - p) + (2.0 / alpha) * max(0.0, p - hi)
    return {"quality": -s, "category": "correct" if lo <= p <= hi else "wrong"}


def _z(level):
    return NormalDist().inv_cdf(1.0 - (1.0 - level) / 2.0)


def wald_interval(data):
    """Baseline: Wald interval p_hat +- z sqrt(p_hat (1 - p_hat) / n), clipped to [0, 1]."""
    k, n, level, _ = _binomial(data)
    p, z = k / n, _z(level)
    half = z * math.sqrt(p * (1.0 - p) / n)
    return {"lower": max(0.0, p - half), "upper": min(1.0, p + half), "level": level}


def wilson_interval(data):
    """Competitor: Wilson score interval."""
    k, n, level, _ = _binomial(data)
    p, z = k / n, _z(level)
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2.0 * n)) / denom
    half = z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n)) / denom
    return {"lower": max(0.0, centre - half), "upper": min(1.0, centre + half), "level": level}


# =================================================================== 6. zero-sum matrix game by LP
GAME_NATIVE, GAME_MAX = 40, 100


def _game(data):
    rows = _mapping(data).get("payoffs")
    if not isinstance(rows, list) or not 1 <= len(rows) <= GAME_MAX or not isinstance(rows[0], list):
        raise GenomeError(f"payoffs: 1-{GAME_MAX} rows")
    n = len(rows[0])
    if not 1 <= n <= GAME_MAX or any(not isinstance(r, list) or len(r) != n for r in rows):
        raise GenomeError(f"payoffs: rectangular, 1-{GAME_MAX} columns")
    a = [[finite(x, low=-1e9, high=1e9, name="payoff") for x in r] for r in rows]
    general = False
    col = data.get("column_payoffs")
    if col is not None:
        if (not isinstance(col, list) or len(col) != len(a) or any(not isinstance(r, list) or len(r) != n for r in col)):
            raise GenomeError("column_payoffs must match the payoff matrix shape")
        b = [[finite(x, low=-1e9, high=1e9, name="column payoff") for x in r] for r in col]
        general = any(abs(a[i][j] + b[i][j]) > 1e-12 for i in range(len(a)) for j in range(n))
    return a, general


def _clean(vector):
    clipped = [max(0.0, float(x)) for x in vector]
    total = sum(clipped)
    return [x / total for x in clipped]


def game_solve(data, budget):
    import numpy as np
    from scipy.optimize import linprog
    a, general = _game(data)
    if general:
        return _abstain("general-sum game: equilibria are not linear programs (PPAD); a Nash solver is required")
    m, n = len(a), len(a[0])
    if m > GAME_NATIVE or n > GAME_NATIVE:
        return _abstain(f"game exceeds the {GAME_NATIVE}x{GAME_NATIVE} bounded size", rows=m, cols=n)
    A = np.array(a, dtype=float)
    # B = 1 + (A - min A) / range lies in [1, 2]: positive (so the game value is positive) and scale-free, so
    # payoffs of any magnitude reach the LP with the same conditioning. Strategies are invariant to this map.
    spread = float(A.max() - A.min())
    B = 1.0 + (A - float(A.min())) / (spread if spread > 0 else 1.0)
    row = linprog(np.ones(m), A_ub=-B.T, b_ub=-np.ones(n), bounds=[(0, None)] * m, method="highs")
    col = linprog(-np.ones(n), A_ub=B, b_ub=np.ones(m), bounds=[(0, None)] * n, method="highs")
    if not (row.success and col.success):
        return answer(None, {"row_lp": row.message, "column_lp": col.message}, status="UNKNOWN",
                      missing=["the linear programs did not solve"])
    x, y = _clean(row.x), _clean(col.x)
    lower = float(min(np.array(x) @ A))
    upper = float(max(A @ np.array(y)))
    return answer({"row_strategy": x, "column_strategy": y, "value": 0.5 * (lower + upper)},
                  {"method": "row and column linear programs (SciPy HiGHS) on the game rescaled to payoffs in [1, 2]",
                   "lower_bound": lower, "upper_bound": upper, "duality_gap": upper - lower,
                   "row_support": [i for i, p in enumerate(x) if p > 1e-12],
                   "column_support": [j for j, q in enumerate(y) if q > 1e-12],
                   "model": "two-player finite zero-sum game; payoff validity is unverified"})


def _exploitability(a, x, y):
    """Duality gap max_i (A y)_i - min_j (x A)_j, by plain arithmetic; None if not mixed strategies."""
    m, n = len(a), len(a[0])
    for vec, size in ((x, m), (y, n)):
        if (not isinstance(vec, list) or len(vec) != size or any(type(p) not in (int, float) or not math.isfinite(p)
                                                                  or p < -1e-12 for p in vec)
                or abs(sum(vec) - 1.0) > 1e-9):
            return None
    lower = min(sum(x[i] * a[i][j] for i in range(m)) for j in range(n))
    upper = max(sum(a[i][j] * y[j] for j in range(n)) for i in range(m))
    return lower, upper


def _payoff_range(a):
    flat = [v for r in a for v in r]
    return (max(flat) - min(flat)) or 1.0


def game_verify(data, output, certificate):
    a, general = _game(data)
    certificate = _cert(certificate)
    if not isinstance(output, dict) or general:          # a zero-sum certificate says nothing about a general game
        return {"mixed_strategies": False}
    bounds = _exploitability(a, output.get("row_strategy"), output.get("column_strategy"))
    if bounds is None:
        return {"mixed_strategies": False}
    lower, upper = bounds
    tol = 1e-7 * _payoff_range(a)
    value = output.get("value")
    return {"mixed_strategies": True, "equilibrium_gap_zero": upper - lower <= tol,
            "value_between_bounds": type(value) is float and lower - tol <= value <= upper + tol,
            "certificate_bounds": abs(certificate.get("lower_bound", math.inf) - lower) <= tol
            and abs(certificate.get("upper_bound", math.inf) - upper) <= tol}


def game_instance(seed):
    from scipy.optimize import linprog
    r = random.Random(960_000 + seed)
    kind = ("random", "cyclic", "saddle")[seed % 3]
    m, n = r.randint(2, 15), r.randint(2, 15)
    if kind == "random":
        a = [[r.randint(-10, 10) for _ in range(n)] for _ in range(m)]
    elif kind == "cyclic":                               # generalised rock-paper-scissors plus noise
        a = [[(3 if (j - i) % max(m, n) in (1, 2) else -3 if (i - j) % max(m, n) in (1, 2) else 0)
              + r.randint(-2, 2) for j in range(n)] for i in range(m)]
    else:                                                # a planted pure saddle point
        a = [[r.randint(-10, 10) for _ in range(n)] for _ in range(m)]
        i0, j0, v = r.randrange(m), r.randrange(n), r.randint(-3, 3)
        for j in range(n):
            a[i0][j] = max(a[i0][j], v)
        for i in range(m):
            a[i][j0] = min(a[i][j0], v)
        a[i0][j0] = v
    # truth: game value from the column player's LP alone, interior-point method (a different formulation)
    shift = 1 - min(min(row) for row in a)
    for method in ("highs-ipm", "highs-ds"):
        res = linprog([-1.0] * n, A_ub=[[x + shift for x in row] for row in a], b_ub=[1.0] * m,
                      bounds=[(0, None)] * n, method=method)
        if res.success:
            return {"payoffs": a}, {"value": 1.0 / float(-res.fun) - shift}
    raise GenomeError("reference LP failed for this instance")


def game_subregion(data):
    a = data["payoffs"]
    maximin = max(min(row) for row in a)
    minimax = min(max(a[i][j] for i in range(len(a))) for j in range(len(a[0])))
    return "pure_saddle" if maximin == minimax else "mixed"


def game_score(data, truth, output):
    """Quality = -(exploitability / payoff range), computed independently of every solver."""
    if not isinstance(output, dict) or "row_strategy" not in output:
        return {"quality": -1.5, "category": "abstain"}
    a, _ = _game(data)
    bounds = _exploitability(a, output.get("row_strategy"), output.get("column_strategy"))
    if bounds is None:
        return {"quality": -2.0, "category": "wrong"}
    lower, upper = bounds
    rng = _payoff_range(a)
    gap = max(0.0, upper - lower) / rng
    value = output.get("value")
    if type(value) not in (int, float) or not lower - 1e-7 * rng <= value <= upper + 1e-7 * rng:
        return {"quality": -2.0, "category": "wrong"}          # a claimed value no strategy pair supports
    return {"quality": -gap, "category": "correct" if gap <= 1e-6 else "wrong"}


def game_security(data):
    """Baseline: pure security strategies, what one does without an LP - the row player's maximin row and the
    column player's minimax column. Exact when the game has a pure saddle point; exploitable otherwise. The
    claimed value is the payoff of that pure pair, which lies between maximin and minimax."""
    a, _ = _game(data)
    m, n = len(a), len(a[0])
    i = max(range(m), key=lambda r: (min(a[r]), -r))
    j = min(range(n), key=lambda c: (max(a[r][c] for r in range(m)), c))
    x, y = [0.0] * m, [0.0] * n
    x[i], y[j] = 1.0, 1.0
    return {"row_strategy": x, "column_strategy": y, "value": float(a[i][j])}


def game_dual_lp(data):
    """Competitor: one HiGHS LP in the formulation of GREG's existing ``cognition.game`` (maximise v subject to
    x A >= v, sum x = 1, x >= 0), with the column player's strategy read from that LP's dual marginals: both
    equilibrium strategies from a single exact solve."""
    import numpy as np
    from scipy.optimize import linprog
    a, general = _game(data)
    if general:
        return None
    A = np.array(a, dtype=float)
    m, n = A.shape
    res = linprog(np.r_[np.zeros(m), -1.0], A_ub=np.column_stack((-A.T, np.ones(n))), b_ub=np.zeros(n),
                  A_eq=np.r_[np.ones(m), 0.0][None, :], b_eq=[1.0], bounds=[(0, None)] * m + [(None, None)],
                  method="highs")
    if not res.success:
        return None
    x, dual = [max(0.0, float(p)) for p in res.x[:m]], [max(0.0, -float(q)) for q in res.ineqlin.marginals]
    if sum(x) <= 0 or sum(dual) <= 0:
        return None
    return {"row_strategy": [p / sum(x) for p in x], "column_strategy": [q / sum(dual) for q in dual],
            "value": float(res.x[-1])}


def game_uniform(data):
    """Former baseline (1.0.0 builder run), retained: both players mix uniformly. Weaker than the pure security
    strategies above, which are exact on every saddle-point game."""
    a, general = _game(data)
    m, n = len(a), len(a[0])
    x, y = [1.0 / m] * m, [1.0 / n] * n
    return {"row_strategy": x, "column_strategy": y,
            "value": sum(x[i] * a[i][j] * y[j] for i in range(m) for j in range(n))}


def game_fictitious_play(data, iterations=5000):
    """Former competitor (1.0.0 builder run), retained as a reference learning dynamic: simultaneous fictitious
    play (Brown-Robinson), fixed iterations, empirical frequencies. It converges slowly and never reached the
    1e-6 equilibrium tolerance on development seeds, so it was a weak stand-in for an exact method."""
    import numpy as np
    a, general = _game(data)
    if general:
        return None
    A = np.array(a, dtype=float)
    m, n = A.shape
    row_count, col_count = np.zeros(m), np.zeros(n)
    row_payoff, col_payoff = np.zeros(m), np.zeros(n)
    i = j = 0
    for _ in range(iterations):
        row_count[i] += 1.0
        col_count[j] += 1.0
        row_payoff += A[:, j]
        col_payoff += A[i, :]
        i, j = int(np.argmax(row_payoff)), int(np.argmin(col_payoff))
    x, y = (row_count / iterations).tolist(), (col_count / iterations).tolist()
    return {"row_strategy": x, "column_strategy": y, "value": float(np.array(x) @ A @ np.array(y))}


# =================================================================== genomes
INTELLIGENCES = [
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.dp.knapsack_01", version="1.0.1", family="dp_knapsack", layer=3,
            operation="knapsack_01_select", epistemic_class="optimization", subgeometry="0/1 knapsack, integer weights",
            source_provenance="Bellman dynamic programming (textbook); NumPy vectorised rows",
            native_representation="item values, integer weights, integer capacity",
            required_inputs=("values", "weights", "capacity"),
            output_contract={"selected": "[item index]", "value": "int", "weight": "int"},
            algorithm_or_runtime="DP over capacities 0..C with a take-table for reconstruction",
            parameters={"native_items": KS_NATIVE_ITEMS, "native_capacity": KS_NATIVE_CAPACITY},
            composition_inputs=("candidate items", "budget"), composition_outputs=("selected", "value"),
            # An exact calculation, not an optimality certificate: the LP (Dantzig) bound it carries is generally
            # above the optimum, so nothing in the certificate alone proves optimality; the verifier recomputes.
            evidence_type="exact_calculation",
            verification_method="index/capacity/value recomputation, the certificate's LP bound must cover the "
                                "optimum, and an independent DP over profit (minimum weight per value) that must "
                                "reach the same optimum (refused above 600000 total value)",
            confidence_semantics="exact within the supplied values and weights",
            resource_profile="O(n C) time and n (C + 1) booleans; <= 60 x 2001 cells",
            latency_profile="about 0.1-0.2 ms at native size (NumPy row operations)",
            known_strengths=("exact", "pseudo-polynomial: independent of value correlation structure",
                             "deterministic; no compiled solver dependency"),
            known_failure_modes=("time and memory grow with capacity, not just item count",
                                 "values and weights supplied by the caller may be wrong",
                                 "about 3-5x slower than OR-Tools' compiled knapsack solver at native size on "
                                 "development seeds (same optimum)"),
            counterindications=("large or real-valued capacities", "multiple constraints (multi-dimensional knapsack)"),
            abstention_conditions=("more than 60 items or capacity above 2000",),
            benchmark_suite="uncorrelated / weakly / strongly correlated / subset-sum instances, 20-60 items, "
                            "capacity <= 2000; seeds 0-9 dev / 1000-1029 held out",
            baseline="greedy by value density (take every item that still fits)",
            competitor="OR-Tools KnapsackSolver, branch and bound (the library's dedicated 0/1 knapsack solver; "
                       "replaced CP-SAT, a general CP model, in review)", **_common()),
        solve=knapsack_solve, verify=knapsack_verify, instance=knapsack_instance, score=knapsack_score,
        baseline=knapsack_greedy, competitor=knapsack_ortools, subregion=knapsack_subregion, tolerance=1e-9,
        notes={"review": "1.0.1: competitor strengthened from CP-SAT to OR-Tools' dedicated knapsack solver; evidence "
                         "relabelled exact_calculation; verifier bounded; LP bound checked against the optimum"}),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.search.astar_grid", version="1.0.1", family="search_astar", layer=3,
            operation="grid_astar_route", epistemic_class="optimization",
            subgeometry="single-pair shortest path on a weighted 4-connected grid",
            source_provenance="Hart, Nilsson and Raphael (1968) A*; stdlib heapq",
            native_representation="grid of cell entry costs (0 = blocked), start and goal cells",
            required_inputs=("grid", "start", "goal"),
            output_contract={"reachable": "bool", "moves": "U/D/L/R string or null", "cost": "int or null"},
            algorithm_or_runtime="A* with closed list; heuristic = min cell cost x Manhattan distance",
            parameters={"native_side": GRID_NATIVE, "tie_break": "larger g first"},
            composition_inputs=("terrain cost grid",), composition_outputs=("moves", "cost"),
            # Exact search, but the certificate is a summary (expanded count, heuristic), not a checkable proof of
            # optimality; optimality is established by the verifier's independent Dijkstra.
            evidence_type="exact_calculation",
            verification_method="move replay (bounds, blocked cells, cost) and an independent plain Dijkstra",
            confidence_semantics="exact shortest path within the supplied costs",
            resource_profile="O(N log N) for N <= 3600 cells", latency_profile="about 0.5-3 ms at native size",
            known_strengths=("exact", "heuristic prunes expansions when costs are near the minimum",
                             "proves unreachability by exhaustion"),
            known_failure_modes=("weak heuristic when cell costs vary widely (degrades towards Dijkstra)",
                                 "pure-Python inner loop: at the native size (<= 60 x 60) SciPy's compiled "
                                 "Dijkstra, which settles every node, was faster on most development seeds"),
            counterindications=("diagonal or any-angle movement", "time-varying costs", "many queries on one grid "
                                "(an all-pairs or landmark method amortises better)"),
            abstention_conditions=("grid larger than 60 x 60",),
            benchmark_suite="open weighted / uniform-cost obstacle / walls-and-mud grids 30-60 per side; "
                            "seeds 0-9 dev / 1000-1029 held out",
            baseline="greedy best-first search (Manhattan priority only)",
            competitor="SciPy csgraph Dijkstra (compiled) on the equivalent weighted digraph built with NumPy; "
                       "replaced NetworkX dijkstra_path (pure Python) in review", **_common()),
        solve=astar_solve, verify=astar_verify, instance=astar_instance, score=astar_score,
        baseline=astar_greedy, competitor=astar_csgraph, subregion=astar_subregion, tolerance=1e-9,
        notes={"review": "1.0.1: competitor strengthened from NetworkX to SciPy's compiled Dijkstra; evidence "
                         "relabelled exact_calculation; verifier requires a boolean 'reachable'"}),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.montecarlo.tilted_importance", version="1.0.1", family="mc_importance", layer=3,
            operation="tilted_tail_probability", epistemic_class="estimate",
            subgeometry="rare upper-tail probability of a sum of iid light-tailed (exponential) components",
            source_provenance="Siegmund (1976) exponential tilting; Asmussen and Glynn, Stochastic Simulation (2007)",
            native_representation="component law, number of terms, rate, threshold, sample budget, seed",
            required_inputs=("component", "terms", "rate", "threshold", "samples", "seed"),
            output_contract={"probability": "float in (0, 1]", "std_error": "float", "ci95": "[lo, hi]"},
            algorithm_or_runtime="sample under the tilted law Exp(n / t); weight hits by the likelihood ratio",
            parameters={"tilt": "tilted mean of the sum equals the threshold", "draw_budget": MC_MAX_DRAWS},
            composition_inputs=("loss or demand model with a closed-form MGF",),
            composition_outputs=("probability", "std_error"),
            evidence_type="statistical_estimate",
            verification_method="optimal Chernoff bound; an independent pure-Python replication on a different "
                                "random stream (agreement within six combined standard errors, the claimed SE "
                                "capped at 2x the replication's); claimed relative SE within 2x of the "
                                "replication's; ci95 recomputed from the claimed SE",
            confidence_semantics="unbiased estimate with a CLT standard error; seeded and reproducible",
            resource_profile="terms x samples exponential draws (<= 2e6)",
            latency_profile="milliseconds at 4000 samples",
            known_strengths=("bounded relative error where crude Monte Carlo sees no hits",
                             "estimate never exceeds the Chernoff bound", "the same tilting mechanism carries "
                             "to events with no closed-form tail (path functionals); not implemented in 1.0.0"),
            known_failure_modes=("needs the component MGF; heavy tails break it",
                                 "standard error can be underestimated when the likelihood ratio is heavy-tailed",
                                 "probabilities below 1e-290 are reported UNKNOWN (outside the float contract)",
                                 "far tails with few terms (e.g. one term at 200x the mean) give degenerate weights; "
                                 "reported UNKNOWN when the effective sample size is below 50",
                                 "loses to a closed-form saddle-point approximation when the CGF is known and the "
                                 "event is a plain sum"),
            counterindications=("heavy-tailed components (lognormal, Pareto)", "events that are not rare",
                                "a closed-form tail is available"),
            abstention_conditions=("non-exponential component", "threshold at or below the mean",
                                   "terms x samples above the draw budget"),
            benchmark_suite="Gamma(n, rate) upper tails, n 1-40, truth P in [1e-10, 1e-3] from scipy.stats.gamma.sf, "
                            "4000 samples; seeds 0-9 dev / 1000-1029 held out",
            baseline="crude Monte Carlo at the same sample budget (abstains when it sees no hits)",
            competitor="Lugannani-Rice saddle-point approximation from the closed-form CGF (the CLT normal "
                       "approximation is the weaker analytic option and is not used)", **_common()),
        solve=mc_solve, verify=mc_verify, instance=mc_instance, score=mc_score,
        baseline=mc_crude, competitor=mc_saddlepoint, subregion=mc_subregion, tolerance=1e-3,
        notes={"tolerance": "quality is -|log10 error|; differences below 0.001 decades (0.23%) are ties",
               "review": "1.0.1: weights in log space (a NaN ESS and a false zero SE for probabilities below about "
                         "1e-154 fixed); UNKNOWN when the effective sample size is below 50 (off-benchmark answers "
                         "were several decades wrong); the verifier caps the claimed SE at 2x the replication's, so "
                         "an inflated self-reported SE cannot widen its agreement tolerance"}),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.queue.erlang_c_staffing", version="1.0.1", family="queue_erlang", layer=3,
            operation="erlang_c_staffing", epistemic_class="prediction",
            subgeometry="M/M/c minimum staffing for a waiting-time service level",
            source_provenance="Erlang (1917) delay formula; Erlang-B recursion (textbook queueing theory)",
            native_representation="arrival rate, mean service time, target wait, maximum P(wait > target)",
            required_inputs=("arrival_rate", "mean_service_time", "target_wait", "max_wait_probability"),
            output_contract={"agents": "int", "p_wait_exceeds_target": "float", "erlang_c": "float",
                             "occupancy": "float"},
            algorithm_or_runtime="Erlang-B recursion to floor(a)+1, then increase c until C(c,a) e^{-(c mu - lambda) T} "
                                 "<= alpha",
            parameters={"max_agents": Q_MAX_AGENTS},
            composition_inputs=("demand forecast",), composition_outputs=("agents",),
            evidence_type="exact_calculation",
            verification_method="independent log-space Poisson-sum Erlang-C at c (meets target) and c - 1 "
                                "(fails target or unstable); the M/M/c preconditions must hold for the input",
            confidence_semantics="exact under M/M/c assumptions; a prediction of service level, not an observation",
            resource_profile="O(c) arithmetic", latency_profile="microseconds to a millisecond",
            known_strengths=("exact minimum under the model", "certifies minimality at c - 1"),
            known_failure_modes=("real arrivals are rarely exactly Poisson", "ignores abandonment and retrials",
                                 "assumes exponential service and FCFS"),
            counterindications=("abandonment (Erlang-A)", "non-exponential service time (cv far from 1)",
                                "time-varying arrival rates within the interval"),
            abstention_conditions=("abandonment_rate > 0", "|service_time_cv - 1| > 0.25"),
            benchmark_suite="offered load 2-400 Erlangs, service 2-10 minutes, target wait 10-120 s, "
                            "alpha 0.05-0.3; seeds 0-9 dev / 1000-1029 held out",
            baseline="utilisation rule agents = ceil(load / 0.85)",
            competitor="square-root (Halfin-Whitt) staffing with the QED delay probability and wait-time tail",
            **_common()),
        solve=erlang_solve, verify=erlang_verify, instance=erlang_instance, score=erlang_score,
        baseline=erlang_utilisation, competitor=erlang_halfin_whitt, subregion=erlang_subregion, tolerance=1e-9,
        notes={"review": "1.0.1: verifier also requires the M/M/c preconditions (no abandonment, cv near 1); "
                         "non-object input raises GenomeError"}),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.bayes.jeffreys_interval", version="1.0.1", family="bayes_interval", layer=3,
            operation="jeffreys_credible_interval", epistemic_class="estimate",
            subgeometry="binomial proportion, small samples, including counts at or near 0 or n",
            source_provenance="Jeffreys prior; Brown, Cai and DasGupta (2001) interval comparison",
            native_representation="successes, trials, credibility level",
            required_inputs=("successes", "trials"),
            output_contract={"lower": "float", "upper": "float", "level": "float", "posterior_mean": "float"},
            algorithm_or_runtime="equal-tailed quantiles of Beta(k + 1/2, n - k + 1/2) (scipy.stats.beta.ppf)",
            parameters={"default_level": 0.9, "boundary_rule": "Brown-Cai-DasGupta"},
            composition_inputs=("binary outcome counts",), composition_outputs=("lower", "upper"),
            evidence_type="posterior",
            verification_method="forward regularised incomplete beta (scipy.special.betainc) at both endpoints, "
                                "posterior mass >= level, the requested level and the independence precondition",
            confidence_semantics="posterior credibility under the Jeffreys prior; frequentist coverage close to "
                                 "nominal but not guaranteed",
            resource_profile="two beta quantiles", latency_profile="sub-millisecond",
            known_strengths=("sensible at k = 0 or k = n where Wald collapses", "narrower than Wilson near the "
                             "boundary"),
            known_failure_modes=("undercovers for some p very close to 0 or 1 at small n",
                                 "a single realised interval can miss the true p (10% at level 0.9)"),
            counterindications=("clustered or overdispersed trials", "strong genuine prior information"),
            abstention_conditions=("independent_trials is false",),
            benchmark_suite="n 5-40, true p uniform or within 0.06 of 0 or 1, level 0.9, interval score; "
                            "seeds 0-9 dev / 1000-1029 held out",
            baseline="Wald interval", competitor="Wilson score interval", dependency="scipy", **_common()),
        solve=jeffreys_solve, verify=jeffreys_verify, instance=bayes_instance, score=interval_score,
        baseline=wald_interval, competitor=wilson_interval, subregion=bayes_subregion, tolerance=1e-9,
        notes={"review": "1.0.1: verifier also checks the returned level and the independence precondition; "
                         "non-object input raises GenomeError"}),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.game.zero_sum_lp", version="1.0.1", family="game_minimax", layer=3,
            operation="zero_sum_lp_equilibrium", epistemic_class="strategic",
            subgeometry="two-player finite zero-sum matrix game",
            source_provenance="von Neumann minimax theorem; LP duality (Dantzig); SciPy HiGHS",
            native_representation="row player's payoff matrix", required_inputs=("payoffs",),
            output_contract={"row_strategy": "[float]", "column_strategy": "[float]", "value": "float"},
            algorithm_or_runtime="row-player and column-player LPs on the matrix rescaled to [1, 2] "
                                 "(scipy.optimize.linprog HiGHS)",
            parameters={"native_side": GAME_NATIVE},
            composition_inputs=("payoff model",), composition_outputs=("row_strategy", "column_strategy", "value"),
            evidence_type="optimality_certificate",
            verification_method="arithmetic exploitability: max_i (A y)_i - min_j (x A)_j must be zero and bracket "
                                "the claimed value",
            confidence_semantics="exact equilibrium of the supplied matrix (floating point)",
            resource_profile="two LPs with <= 40 variables", latency_profile="milliseconds",
            known_strengths=("exact equilibrium with a duality-gap certificate", "both players' strategies"),
            known_failure_modes=("payoffs supplied by the caller may be wrong", "assumes a strictly adversarial "
                                 "opponent; overly conservative against a non-adversary",
                                 "solves two LPs where one LP and its dual marginals give both strategies: about "
                                 "twice the latency of that single-LP route on development seeds"),
            counterindications=("general-sum games", "sequential games with private information (use a game tree "
                                "method)"),
            abstention_conditions=("column_payoffs differ from the negated payoffs", "more than 40 actions per player"),
            benchmark_suite="random, cyclic (RPS-like) and planted-saddle integer games up to 15 x 15; "
                            "seeds 0-9 dev / 1000-1029 held out",
            baseline="pure security strategies (maximin row, minimax column); replaced uniform play in review",
            competitor="one HiGHS LP in GREG's existing cognition.game formulation, column strategy from its dual "
                       "marginals; replaced 5000-iteration fictitious play in review", dependency="scipy", **_common()),
        solve=game_solve, verify=game_verify, instance=game_instance, score=game_score,
        baseline=game_security, competitor=game_dual_lp, subregion=game_subregion, tolerance=1e-9,
        notes={"review": "1.0.1: LP rescaled to payoffs in [1, 2] (small-magnitude games no longer refute their own "
                         "answer); baseline strengthened to pure security strategies and competitor to the exact "
                         "single-LP-plus-duals route; fictitious play and uniform play retained as functions"}),
]
