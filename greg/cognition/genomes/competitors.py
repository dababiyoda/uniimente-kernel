"""Promoted competitors: the deployable mechanisms that superseded admitted genomes, as genomes of their own.

Genome admission v1 (2026-10-13) and v2 (2026-10-14) found four genomes SUPERSEDED by their deployable
competitors: ``dp_knapsack``, ``search_astar`` and ``game_minimax`` tied their competitors on every held-out
instance and were slower; ``basal_pid`` lost 0-30 on quality to simulation-optimised PI. SUPERSEDED genomes
are excluded from routing, so a request only they fitted ended in CAPABILITY_DEFICIT although the stronger
mechanism was known and installed. Directive section 15 (a method earns its place by native competence, and
the competitor that beat it is a method too) and section 31 item 3: promote those mechanisms.

Each genome here keeps the superseded genome's input contract (``required_inputs``, so the same requests fit
it), native geometry (epistemic class), instance generator, score and subregions, and names that genome in
``Executable.promotes``. Its baseline is the superseded genome's own solve (the former candidate). Its
competitor is the strongest deployable alternative that is not its own mechanism, measured on development
seeds 0-9 and named honestly in the genome; the ablation (its own mechanism without the certificate or
fallback it adds) is reported in its notes, not named as the competitor. Its verifier checks a certificate
with code that shares nothing with the solver it checks.

* ``knapsack_bnb`` (``knapsack_01_branch_bound``): OR-Tools' dedicated 0/1 knapsack solvers - branch and bound
  under a 50 ms slice, then OR-Tools' compiled dynamic program when branch and bound stalls. Verified by an exact
  dynamic program written here (over capacity or over profit, whichever is smaller).
* ``grid_dijkstra`` (``grid_dijkstra_route``): SciPy's compiled Dijkstra on the grid's digraph, returning a
  dual certificate: one potential per cell. The verifier checks the potential is feasible on every edge and
  tight on the route (LP duality for shortest paths); it never searches.
* ``game_lp_dual`` (``zero_sum_lp_dual_equilibrium``): one LP (OR-Tools GLOP) whose dual values are the column
  player's strategy, SciPy HiGHS as a fallback. Verified by exact best responses: both strategies guarantee
  the same value and every supported action is a best response.
* ``pid_simopt`` (``pi_simopt_track``): PI gains by simulation-optimisation on the declared model (Nelder-Mead
  from AMIGO, then a compass polish that makes the answer locally optimal at a declared log step). Verified by
  an independent closed-loop simulator and state-space stability check: the declared-scenario cost and
  limits, and local optimality on the declared optimisation noise.

Nothing here is admitted: every family starts registered and withheld (VERIFIED), like every non-seed family,
until a held-out admission and a founder attach. Everything is read-only computation; no output creates
authority.
"""
from __future__ import annotations

from bisect import bisect_right
import hashlib
import math
import random

from . import basal, solvers_b
from .contract import Executable, GenomeError, IntelligenceGenome, answer

LINEAGE = ("INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION", "INTENT-20261007-VERIFIED-POLYINTELLIGENCE-LIFT",
           "directive section 15 (competitors are methods) and section 31 item 3")
V1 = "docs/evidence/greg-genome-admission/2026-10-13-v1/results.json"
V2 = "docs/evidence/greg-genome-admission/2026-10-14-v2/results.json"
_DEV = "development seeds 0-9 only (admission --dev; not admission evidence; latency in a loaded container): "
_DEV_KX = _DEV + ("DEFAULT_FOR_GEOMETRY: 10 ties with baseline and competitor; median 0.12-0.14 ms vs 0.26-0.28 "
                  "ms (NumPy DP) and 1.5-3.7 ms (CP-SAT) over three runs")


def _common(**kw):
    return dict(buildability="BUILDABLE_NOW", memory_model="stateless",
                learning_rule="none (competence settles per geometry through GREG outcomes)", **kw)


def _abstain(reason, **certificate):
    return answer(None, {"reason": reason, **certificate}, status="ABSTAIN", missing=[reason])


def _cert(certificate):
    return certificate if isinstance(certificate, dict) else {}


def _former(solve):
    """The superseded genome's own solve as a baseline arm: its output, or None when it does not answer."""
    def baseline(data):
        out = solve(data, {"latency_s": 5.0, "compute": 100000})
        return out["output"] if out["status"] == "ANSWER" else None
    return baseline


# =================================================================== 1. 0/1 knapsack by OR-Tools branch and bound
# OR-Tools' Knapsack64ItemsSolver is never used: it ignores its time limit (measured 339 s on a 40-item review
# instance with two item types in multiples), so it cannot honour the bounded-solve contract in process.
KX_BNB = "KNAPSACK_MULTIDIMENSION_BRANCH_AND_BOUND_SOLVER"
KX_DP = "KNAPSACK_DYNAMIC_PROGRAMMING_SOLVER"
KX_BNB_SLICE = 0.05               # seconds: branch and bound proves native instances in well under 1 ms, or stalls
KX_DP_CELLS = 4_000_000           # the compiled DP fallback is O(n x (C + 1)): 0.06-0.6 s at this bound on review
KX_CHECK_CELLS = 4_000_000        # the independent check is an O(n x min(C, total value)) dynamic program


def _kx_cells(v, cap):
    return len(v) * (min(cap, sum(v)) + 1)


def _kx_ortools(kind, v, w, cap, limit=None):
    """Solver side: one OR-Tools knapsack solver; the selection only if the solver reports it optimal."""
    from ortools.algorithms.python import knapsack_solver
    solver = knapsack_solver.KnapsackSolver(getattr(knapsack_solver.SolverType, kind), "greg_knapsack_bnb")
    if limit is not None:
        solver.set_time_limit(limit)
    solver.init(v, [w], [cap])
    solver.solve()
    if not solver.is_solution_optimal():
        return None
    return [i for i in range(len(v)) if solver.best_solution_contains(i)]


def knapsack_bnb_solve(data, budget):
    v, w, cap = solvers_b._knapsack(data)
    n = len(v)
    if _kx_cells(v, cap) > KX_CHECK_CELLS:
        return _abstain(f"the independent exact check (n x min(capacity, total value) <= {KX_CHECK_CELLS} cells) "
                        f"cannot certify this instance", items=n, capacity=cap)
    latency = (budget or {}).get("latency_s", 5.0)
    latency = float(latency) if type(latency) in (int, float) and math.isfinite(latency) and latency > 0 else 5.0
    slice_s = max(0.001, min(KX_BNB_SLICE, 0.25 * latency))
    chosen, solver, tried = _kx_ortools(KX_BNB, v, w, cap, slice_s), KX_BNB, []
    if chosen is None:
        tried.append(f"{KX_BNB}: optimality not proven within {slice_s:g} s")
        if n * (cap + 1) > KX_DP_CELLS:
            return answer(None, {"solvers_tried": tried, "dp_cells": n * (cap + 1), "dp_cell_bound": KX_DP_CELLS},
                          status="UNKNOWN", missing=["branch and bound did not prove optimality within its slice and "
                                                     "the dynamic-programming fallback exceeds its cell bound"])
        chosen, solver = _kx_ortools(KX_DP, v, w, cap), KX_DP
        if chosen is None:
            return answer(None, {"solvers_tried": tried + [f"{KX_DP}: not reported optimal"]}, status="UNKNOWN",
                          missing=["no OR-Tools knapsack solver reported an optimal selection"])
    return answer({"selected": chosen, "value": sum(v[i] for i in chosen), "weight": sum(w[i] for i in chosen)},
                  {"method": "OR-Tools dedicated 0/1 knapsack solvers: branch and bound under a time slice, compiled "
                             "dynamic program when branch and bound stalls", "solver": solver, "solvers_tried": tried,
                   "solver_reports_optimal": True,
                   "limits": "the solver's optimality report is not a checkable proof; the verifier recomputes the "
                             "optimum by its own dynamic program (no LP bound is computed here: it would cost about "
                             "a sixth of the solve and prove nothing the dynamic program does not)"})


def _kx_exact_optimum(v, w, cap):
    """Verifier side: the exact optimum by a dynamic program over the cheaper axis (capacity or total profit)."""
    import numpy as np
    total = sum(v)
    if cap <= total:
        best = np.zeros(cap + 1, dtype=np.int64)          # best[c]: maximum value within weight c
        for vi, wi in zip(v, w):
            if vi and wi <= cap:
                shifted = best[:cap + 1 - wi] + vi          # a copy: every item is used at most once
                np.maximum(best[wi:], shifted, out=best[wi:])
        return int(best[cap])
    lightest = np.full(total + 1, np.iinfo(np.int64).max // 4, dtype=np.int64)   # lightest[p]: min weight of value p
    lightest[0] = 0
    for vi, wi in zip(v, w):
        if vi:
            shifted = lightest[:total + 1 - vi] + wi
            np.minimum(lightest[vi:], shifted, out=lightest[vi:])
    return int(np.flatnonzero(lightest <= cap).max())


def knapsack_bnb_verify(data, output, certificate):
    """Independent of the OR-Tools solver: index validity, capacity, recomputed value and weight, and the exact
    optimum by this module's own dynamic program (over capacity or over profit, whichever is smaller), which the
    selection must reach. The solver's own optimality report must be present but proves nothing by itself.
    Not verified: that the caller's values and weights describe the real decision."""
    v, w, cap = solvers_b._knapsack(data)
    certificate = _cert(certificate)
    sel = output.get("selected") if isinstance(output, dict) else None
    if not (isinstance(sel, list) and all(type(i) is int and 0 <= i < len(v) for i in sel)
            and len(set(sel)) == len(sel)):
        return {"indices_valid_and_distinct": False}
    if _kx_cells(v, cap) > KX_CHECK_CELLS:
        return {"indices_valid_and_distinct": True, "independent_check_within_bounds": False}
    value, weight = sum(v[i] for i in sel), sum(w[i] for i in sel)
    optimum = _kx_exact_optimum(v, w, cap)
    return {"indices_valid_and_distinct": True, "within_capacity": weight <= cap,
            "value_recomputed": type(output.get("value")) is int and output["value"] == value
            and type(output.get("weight")) is int and output["weight"] == weight,
            "optimal_by_independent_dynamic_program": value == optimum,
            "solver_reported_optimal": certificate.get("solver_reports_optimal") is True}


# =================================================================== 2. grid shortest path with a dual certificate
GD_NATIVE = 100          # cells per side; the potential certificate is one integer per cell (<= 10 000)


def grid_dijkstra_solve(data, budget):
    import numpy as np
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import dijkstra
    cells, rows, cols, s, t = solvers_b._grid(data)
    if rows > GD_NATIVE or cols > GD_NATIVE:
        return _abstain(f"grid exceeds {GD_NATIVE} x {GD_NATIVE} (the per-cell certificate would exceed its bound)",
                        rows=rows, cols=cols)
    cost = np.asarray(cells, dtype=np.float64)
    index = np.arange(rows * cols).reshape(rows, cols)
    pairs = ((index[:, :-1], index[:, 1:]), (index[:-1, :], index[1:, :]))
    tail = np.concatenate([x.ravel() for a, b in pairs for x in (a, b)])
    head = np.concatenate([x.ravel() for a, b in pairs for x in (b, a)])
    keep = (cost[tail] > 0) & (cost[head] > 0)
    tail, head = tail[keep], head[keep]
    graph = csr_matrix((cost[head], (tail, head)), shape=(rows * cols, rows * cols))
    dist, pred = dijkstra(graph, directed=True, indices=s, return_predecessors=True)
    settled = np.isfinite(dist)
    method = "SciPy csgraph Dijkstra (compiled) on the digraph whose edge weight is the cost of entering the head cell"
    if not settled[t]:
        return answer({"reachable": False, "moves": None, "cost": None},
                      {"method": method, "component_size": int(settled.sum()),
                       "unreachability": "the start's connected component of passable cells excludes the goal"})
    total = int(round(float(dist[t])))
    parent, u = {}, t
    while u != s:
        parent[u] = int(pred[u])
        u = parent[u]
    moves = solvers_b._moves(parent, s, t, cols)
    # pi(v) = min(dist(v), dist(goal)), and dist(goal) where unreachable: feasible on every edge and tight on the route
    potential = np.where(settled, np.minimum(dist, dist[t]), dist[t]).round().astype(np.int64).reshape(rows, cols)
    return answer({"reachable": True, "moves": moves, "cost": total, "steps": len(moves)},
                  {"method": method, "potential": potential.tolist(), "potential_cap": total,
                   "dual": "pi(start) = 0 and pi(v) <= pi(u) + cost(v) on every passable edge u -> v, so every route "
                           "costs at least pi(goal); the returned route costs exactly pi(goal)",
                   "settled_cells": int(settled.sum())})


def _gd_walk(grid, rows, cols, start, goal, moves):
    """Verifier side: the cost of a move string, or None if it leaves the grid, enters a wall or misses the goal."""
    if not isinstance(moves, str) or len(moves) > rows * cols:
        return None
    step = {"U": (-1, 0), "D": (1, 0), "L": (0, -1), "R": (0, 1)}
    r, c, spent = start[0], start[1], 0
    for m in moves:
        if m not in step:
            return None
        r, c = r + step[m][0], c + step[m][1]
        if not (0 <= r < rows and 0 <= c < cols) or grid[r][c] == 0:
            return None
        spent += grid[r][c]
    return spent if [r, c] == list(goal) else None


def _gd_component(grid, rows, cols, start):
    """Verifier side: every passable cell reachable from the start (iterative flood fill, no priority queue)."""
    seen, stack = {tuple(start)}, [tuple(start)]
    while stack:
        r, c = stack.pop()
        for rr, cc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
            if 0 <= rr < rows and 0 <= cc < cols and grid[rr][cc] and (rr, cc) not in seen:
                seen.add((rr, cc))
                stack.append((rr, cc))
    return seen


def grid_dijkstra_verify(data, output, certificate):
    """A certificate check, never a search: the route is replayed, and the returned potential must be an integer per
    cell with pi(start) = 0, pi(v) <= pi(u) + cost(v) on every passable edge (dual feasibility) and pi(goal) equal
    to the route's cost (tightness). Feasibility bounds every route below by pi(goal), so the route is optimal.
    Unreachability is confirmed by an independent flood fill. Not verified: that the costs describe the terrain."""
    solvers_b._grid(data)                                    # input contract (raises on malformed data)
    grid, start, goal = data["grid"], data["start"], data["goal"]
    rows, cols = len(grid), len(grid[0])
    certificate = _cert(certificate)
    if not isinstance(output, dict) or type(output.get("reachable")) is not bool:
        return {"output_shape": False}
    if not output["reachable"]:
        component = _gd_component(grid, rows, cols, start)
        return {"output_shape": True, "unreachable_confirmed_by_flood_fill": tuple(goal) not in component,
                "component_size_recomputed": certificate.get("component_size") == len(component),
                "no_route_claimed": output.get("moves") is None and output.get("cost") is None}
    moves = output.get("moves")
    spent = _gd_walk(grid, rows, cols, start, goal, moves)
    pi = certificate.get("potential")
    shaped = (isinstance(pi, list) and len(pi) == rows
              and all(isinstance(row, list) and len(row) == cols and all(type(x) is int for x in row) for row in pi))
    checks = {"output_shape": True, "path_valid": spent is not None,
              "cost_recomputed": spent is not None and type(output.get("cost")) is int and output["cost"] == spent,
              "steps_are_move_count": isinstance(moves, str) and type(output.get("steps")) is int
              and output["steps"] == len(moves),
              "potential_well_formed": shaped}
    if not shaped:
        return checks
    feasible = True
    for r in range(rows):
        for c in range(cols):
            if not grid[r][c]:
                continue
            for rr, cc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                if 0 <= rr < rows and 0 <= cc < cols and grid[rr][cc] and pi[rr][cc] > pi[r][c] + grid[rr][cc]:
                    feasible = False
                    break
            if not feasible:
                break
        if not feasible:
            break
    checks.update({"potential_zero_at_start": pi[start[0]][start[1]] == 0,
                   "potential_feasible_on_every_edge": feasible,
                   "route_tight_with_potential": spent is not None and spent == pi[goal[0]][goal[1]]})
    return checks


def grid_networkx_bidirectional(data):
    """Competitor: NetworkX bidirectional Dijkstra on the equivalent weighted digraph (the graph library GREG's
    existing graph family uses). On development seeds it and OR-Tools' compiled min-cost flow (one unit, start to
    goal) were both 10-40x slower than the candidate; no faster deployable alternative was found installed."""
    import networkx as nx
    cells, rows, cols, s, t = solvers_b._grid(data)
    g = nx.DiGraph()
    g.add_nodes_from((s, t))          # an endpoint with no passable neighbour has no edge: unreachable, not absent
    g.add_weighted_edges_from((u, v, cells[v]) for u in range(len(cells)) if cells[u]
                              for v in solvers_b._neighbors(u, rows, cols) if cells[v])
    try:
        total, path = nx.bidirectional_dijkstra(g, s, t, weight="weight")
    except nx.NetworkXNoPath:
        return {"reachable": False, "moves": None, "cost": None}
    parent = {b: a for a, b in zip(path, path[1:])}
    moves = solvers_b._moves(parent, s, t, cols)
    return {"reachable": True, "moves": moves, "cost": int(total), "steps": len(moves)}


# =================================================================== 3. zero-sum matrix game: one LP and its duals
GL_GAP = 1e-9            # solver self-check before answering (fraction of the payoff range)
GL_TOL = 1e-7            # verifier tolerance on bounds and equilibrium gap (fraction of the payoff range)
GL_STATED = 0.5 * GL_TOL  # the stated value and bounds must carry the LP's to within this fraction of the range
GL_SUPPORT = 1e-6        # an action with at least this probability must be a best response ...
GL_SLACK = 1e-6          # ... to within this fraction of the payoff range


def _gl_glop(b):
    """Solver side: maximise v s.t. x B >= v, sum x = 1, x >= 0 (OR-Tools GLOP); y from the dual values."""
    from ortools.linear_solver import pywraplp
    m, n = b.shape
    lp = pywraplp.Solver.CreateSolver("GLOP")
    if lp is None:
        return None
    x = [lp.NumVar(0.0, lp.infinity(), f"x{i}") for i in range(m)]
    v = lp.NumVar(-lp.infinity(), lp.infinity(), "v")
    columns = []
    for j in range(n):
        row = lp.Constraint(0.0, lp.infinity())
        for i in range(m):
            if b[i, j]:
                row.SetCoefficient(x[i], float(b[i, j]))
        row.SetCoefficient(v, -1.0)
        columns.append(row)
    simplex = lp.Constraint(1.0, 1.0)
    for xi in x:
        simplex.SetCoefficient(xi, 1.0)
    lp.Maximize(v)
    if lp.Solve() != pywraplp.Solver.OPTIMAL:
        return None
    return [xi.solution_value() for xi in x], [-row.dual_value() for row in columns]


def _gl_highs(b):
    """Solver-side fallback: the same LP in SciPy HiGHS, y from the inequality marginals."""
    import numpy as np
    from scipy.optimize import linprog
    m, n = b.shape
    res = linprog(np.r_[np.zeros(m), -1.0], A_ub=np.column_stack((-b.T, np.ones(n))), b_ub=np.zeros(n),
                  A_eq=np.r_[np.ones(m), 0.0][None, :], b_eq=[1.0], bounds=[(0, None)] * m + [(None, None)],
                  method="highs")
    if not res.success:
        return None
    return list(res.x[:m]), [-q for q in res.ineqlin.marginals]


def _gl_distribution(vector):
    clipped = [max(0.0, float(p)) for p in vector]
    total = sum(clipped)
    return [p / total for p in clipped] if total > 0 else None


def game_lp_dual_solve(data, budget):
    import numpy as np
    a, general = solvers_b._game(data)
    if general:
        return _abstain("general-sum game: equilibria are not linear programs (PPAD); a Nash solver is required")
    A = np.array(a, dtype=float)
    low, spread = float(A.min()), float(A.max() - A.min())
    scale = spread if spread > 0 else 1.0
    # B = (A - min A) / range lies in [0, 1]: strategies are invariant, and payoffs of any magnitude or common
    # offset reach the LP with the same conditioning (GLOP's feasibility tolerances are absolute). The self-check
    # runs on B too: on A, (x A).min() and (A y).max() carry rounding of order max|A| x eps rather than range x eps,
    # so a large common offset failed exact equilibria. Bounds and value are stated on A as min A + range x (on B).
    B = (A - low) / scale
    tried, unstated = [], []
    for name, engine in (("OR-Tools GLOP", _gl_glop), ("SciPy HiGHS", _gl_highs)):
        solved = engine(B)
        x, y = (_gl_distribution(solved[0]), _gl_distribution(solved[1])) if solved else (None, None)
        if x is None or y is None:
            tried.append(name)
            continue
        lower_b, upper_b = float((np.array(x) @ B).min()), float((B @ np.array(y)).max())
        if upper_b - lower_b > GL_GAP:
            tried.append(name)
            continue
        middle_b = 0.5 * (lower_b + upper_b)
        lower, upper, value = low + scale * lower_b, low + scale * upper_b, low + scale * middle_b
        # When the payoffs agree to about nine significant figures, a float near their offset holds fewer digits
        # than their range needs: never state a value or bound that misses the LP's by a material part of the
        # declared verification tolerance.
        stated = max(abs((s - low) - scale * t) for s, t in ((lower, lower_b), (upper, upper_b), (value, middle_b)))
        if stated > GL_STATED * scale:
            tried.append(name)
            unstated.append(stated / scale)
            continue
        return answer({"row_strategy": x, "column_strategy": y, "value": value},
                      {"method": "one LP (row player's maximin) on the game rescaled to [0, 1]; the column "
                                 "player's strategy is the LP's dual solution", "engine": name,
                       "engines_failed": tried, "lower_bound": lower, "upper_bound": upper,
                       "duality_gap": scale * (upper_b - lower_b),
                       "row_support": [i for i, p in enumerate(x) if p > 1e-12],
                       "column_support": [j for j, q in enumerate(y) if q > 1e-12],
                       "model": "two-player finite zero-sum game; payoff validity is unverified"})
    if unstated:
        return answer(None, {"engines_failed": tried, "stated_error_over_range": max(unstated),
                             "payoff_minimum": low, "payoff_range": spread}, status="UNKNOWN",
                      missing=[f"the payoffs' common offset is so large against their range that no floating-point "
                               f"value or bound can be stated within {GL_STATED:g} of the range"])
    return answer(None, {"engines_failed": tried}, status="UNKNOWN",
                  missing=["no LP engine returned strategies within the duality-gap tolerance"])


def game_lp_dual_verify(data, output, certificate):
    """Exact best responses, computed here with compensated sums (math.fsum), never with the solver's LP: the
    row strategy guarantees min_j (x A)_j, the column strategy concedes at most max_i (A y)_i; the two must meet
    (zero duality gap), bracket the claimed value and match the certificate, and every action played with
    probability >= 1e-6 must be a best response to the opponent's strategy (complementary slackness).
    Every guarantee, and every claimed value and bound, is measured above the smallest payoff (on A - min A): a
    strategy whose mass is off 1 by d (|d| <= 1e-9 is accepted) then moves a guarantee by at most d x the payoff
    range, never by d x the payoffs' common offset, which could carry a false value through every check.
    Not verified: that the payoff matrix describes the real interaction, or that the opponent is adversarial."""
    a, general = solvers_b._game(data)
    certificate = _cert(certificate)
    if not isinstance(output, dict) or general:
        return {"mixed_strategies": False}
    m, n = len(a), len(a[0])
    x, y = output.get("row_strategy"), output.get("column_strategy")
    for vec, size in ((x, m), (y, n)):
        if (not isinstance(vec, list) or len(vec) != size
                or any(type(p) not in (int, float) or not math.isfinite(p) or p < -1e-12 for p in vec)
                or abs(math.fsum(vec) - 1.0) > 1e-9):
            return {"mixed_strategies": False}
    flat = [p for row in a for p in row]
    low = min(flat)
    span = (max(flat) - low) or 1.0
    above = [[p - low for p in row] for row in a]
    guaranteed = [math.fsum(x[i] * above[i][j] for i in range(m)) for j in range(n)]     # column best responses
    conceded = [math.fsum(above[i][j] * y[j] for j in range(n)) for i in range(m)]       # row best responses
    lower, upper = min(guaranteed), max(conceded)
    tol = GL_TOL * span
    value = output.get("value")

    def claimed(number):
        """A claimed payoff measured above the smallest payoff, or None if it is not a finite number."""
        return number - low if type(number) in (int, float) and math.isfinite(number) else None

    def near(number, actual):
        stated = claimed(number)
        return stated is not None and abs(stated - actual) <= tol
    stated_value = claimed(value)
    return {"mixed_strategies": True, "equilibrium_gap_zero": upper - lower <= tol,
            "value_between_bounds": stated_value is not None and lower - tol <= stated_value <= upper + tol,
            "row_support_are_best_responses": all(conceded[i] >= upper - GL_SLACK * span
                                                  for i in range(m) if x[i] >= GL_SUPPORT),
            "column_support_are_best_responses": all(guaranteed[j] <= lower + GL_SLACK * span
                                                     for j in range(n) if y[j] >= GL_SUPPORT),
            "certificate_bounds": near(certificate.get("lower_bound"), lower)
            and near(certificate.get("upper_bound"), upper)}


# =================================================================== 4. PI tuning by simulation-optimisation
PX_MAX_STEPS = 2000      # ~120 closed-loop simulations per answer: bound each one
PX_LOG_STEP = 0.01       # the answer is locally optimal against +-1% moves of Kc and of Ti (log scale)
PX_POLISH_MOVES = 100    # compass moves at the declared step after Nelder-Mead (about 2.7x in either gain at most)
PX_RULE = "simulation-optimised PI on the declared model"


def _px_noise_seed(seed):
    """The optimisation's own noise realisation (it never sees the scored noise), derived from the declared seed."""
    return int(hashlib.sha256(f"pid-competitor-noise:{seed}".encode()).hexdigest()[:7], 16)


def _px_reachable(p):
    loads = {0.0, p["load"]}
    needed = [r / p["gain"] - w for _, r in p["schedule"] for w in loads]
    margin = 0.02 * (p["u_max"] - p["u_min"])
    return all(p["u_min"] + margin <= u <= p["u_max"] - margin for u in needed)


def _px_controller(sign, z):
    return {"law": "pid", "kc": sign * math.exp(z[0]), "ti": math.exp(z[1]), "td": 0.0, "tf": 0.0, "b": 1.0}


def _px_objective(p):
    """Solver side: the declared cost on the optimisation noise; inadmissible gains (unstable, divergent,
    persistently saturated, outside the contract) cost infinity."""
    sign = 1.0 if p["gain"] > 0 else -1.0
    own = dict(p, seed=_px_noise_seed(p["seed"]))
    count = [0]

    def cost(z):
        count[0] += 1
        if max(abs(z[0]), abs(z[1])) > 60.0:
            return math.inf
        ctrl = _px_controller(sign, z)
        if not (abs(ctrl["kc"]) <= basal.PID_KC_LIMIT and basal.PID_TI_RANGE[0] <= ctrl["ti"] <= basal.PID_TI_RANGE[1]):
            return math.inf
        if basal._pid_spectral_radius_poly(own, ctrl) >= 1.0:
            return math.inf
        m = basal._pid_metrics(own, *basal._pid_loop(own, ctrl))
        if (m["max_abs_error"] > basal.PID_DIVERGE * basal._pid_span(own)
                or m["longest_limit_run"] > basal.PID_SAT_FRACTION * own["steps"]):
            return math.inf
        return m["cost"]
    return sign, own, cost, count


def _px_start(data, p):
    start = basal.pid_amigo(data) or {"kc": p["tau"] / (p["gain"] * max(p["theta"], p["dt"])), "ti": p["tau"]}
    return [math.log(abs(start["kc"])), math.log(start["ti"])], "AMIGO PI" if p["theta"] > 0 else "tau / (K dt) PI"


def pid_simopt_solve(data, budget):
    p = basal._pid_inputs(data)
    if p["steps"] > PX_MAX_STEPS:
        return _abstain(f"horizon above {PX_MAX_STEPS} steps: each of ~120 simulations would exceed its budget; "
                        "resample with a larger dt", steps=p["steps"])
    if not _px_reachable(p):
        return _abstain("a setpoint is unreachable within the actuator limits")
    sign, own, cost, count = _px_objective(p)
    z0, start = _px_start(data, p)
    z, value = basal._nelder_mead_2d(cost, z0, 0.5, basal.PID_OPT_ITERATIONS)
    if not math.isfinite(value):
        return _abstain("the local search found no stable, non-divergent, unsaturated PI gains on the declared model")
    # compass polish at the declared step only: it ends when no +-1% move of either gain lowers the cost, which is
    # the local optimality the verifier re-checks (four extra simulations when Nelder-Mead has already settled)
    converged, h = False, PX_LOG_STEP
    for _ in range(PX_POLISH_MOVES):
        around = [[z[0] + h, z[1]], [z[0] - h, z[1]], [z[0], z[1] + h], [z[0], z[1] - h]]
        costs = [cost(q) for q in around]
        k = min(range(4), key=costs.__getitem__)
        if costs[k] < value:
            z, value = around[k], costs[k]
        else:
            converged = True
            break
    if not converged:
        return answer(None, {"evaluations": count[0]}, status="UNKNOWN",
                      missing=["the compass polish did not settle within its move budget"])
    ctrl = _px_controller(sign, z)
    ys, us, rs = basal._pid_loop(p, ctrl)
    m = basal._pid_metrics(p, ys, us, rs)
    rho = basal._pid_spectral_radius_poly(p, ctrl)
    if (rho >= 1.0 or m["max_abs_error"] > basal.PID_DIVERGE * basal._pid_span(p)
            or m["longest_limit_run"] > basal.PID_SAT_FRACTION * p["steps"]):
        return _abstain("the optimised gains fail on the declared scenario's own noise (unstable, divergent or "
                        "persistently saturated)", spectral_radius=rho)
    return answer({**ctrl, "rule": PX_RULE},
                  {"seed": p["seed"], "delay_samples": p["delay"], "iae": m["iae"], "effort_tv": m["effort_tv"],
                   "cost": m["cost"], "effort_weight": basal.PID_EFFORT_WEIGHT, "max_abs_error": m["max_abs_error"],
                   "longest_limit_run": m["longest_limit_run"], "closed_loop_spectral_radius": rho,
                   "optimisation": {"noise_seed": own["seed"], "objective": value, "log_step": PX_LOG_STEP,
                                    "start": start, "search": "Nelder-Mead on (log |Kc|, log Ti), then compass polish",
                                    "evaluations": count[0]},
                   "discretisation": "exact ZOH first-order lag, dead time rounded to whole samples",
                   "anti_windup": "conditional integration (clamping)",
                   "limits": "local, not global, optimality; performance is a simulation of the declared model "
                             "and noise model; plant-model mismatch is not covered"})


def _px_replay(p, kc, ti, seed):
    """Verifier side, written independently of the solver's simulation: a PI law (b = 1, no derivative) in closed
    loop with the declared FOPDT plant - a ring buffer for the dead time, the setpoint found by bisection, the
    metrics accumulated in one pass. Returns cost, IAE, effort, maximum error and the longest run at one limit."""
    n, dt, gain = p["steps"], p["dt"], p["gain"]
    lag = math.exp(-dt / p["tau"])
    feed = gain * (1.0 - lag)
    draw = random.Random(seed)
    jitter = [draw.gauss(0.0, p["noise_sd"]) for _ in range(n)]
    times = [t for t, _ in p["schedule"]]
    levels = [r for _, r in p["schedule"]]
    lo, hi, u0, d = p["u_min"], p["u_max"], p["u0"], p["delay"]
    ring, slot = [u0] * max(d, 1), 0
    y = gain * u0
    acc = u0 - kc * (levels[0] - y)
    gain_i = kc * dt / ti
    iae = worst = tv = 0.0
    previous, side, run, longest = u0, None, 0, 0
    for k in range(n):
        now = k * dt
        ref = levels[bisect_right(times, now) - 1]
        err_true = abs(ref - y)
        iae += err_true
        worst = max(worst, err_true)
        meas = y + jitter[k]
        raw = kc * (ref - meas) + acc
        u = hi if raw > hi else lo if raw < lo else raw
        inc = gain_i * (ref - meas)
        if not ((raw > hi and inc > 0) or (raw < lo and inc < 0)):
            acc += inc
        tv += abs(u - previous)
        previous = u
        at = "hi" if u >= hi else "lo" if u <= lo else None
        run = (run + 1 if at == side else 1) if at else 0
        side = at
        longest = max(longest, run)
        if d:
            applied, ring[slot] = ring[slot], u
            slot = (slot + 1) % d
        else:
            applied = u
        y = lag * y + feed * (applied + (p["load"] if now >= p["load_time"] else 0.0))
    iae *= dt
    return {"cost": iae + basal.PID_EFFORT_WEIGHT * abs(gain) * dt * tv, "iae": iae, "effort_tv": tv,
            "max_abs_error": worst, "longest_limit_run": longest}


def _px_radius(p, kc, ti):
    """Verifier side: spectral radius of the linear closed loop from its own state matrix over
    [y_k, I_k, u_(k-1), ..., u_(k-d)] (the solver uses polynomial roots)."""
    import numpy as np
    dt, d = p["dt"], p["delay"]
    a = math.exp(-dt / p["tau"])
    bu = p["gain"] * (1.0 - a)
    ki = kc * dt / ti
    size = 2 + d
    m = np.zeros((size, size))
    if d == 0:                                    # u_k = -kc y_k + I_k acts at once
        m[0, 0], m[0, 1] = a - bu * kc, bu
    else:
        m[0, 0], m[0, size - 1] = a, bu           # y_(k+1) = a y_k + bu u_(k-d)
        m[2, 0], m[2, 1] = -kc, 1.0               # newest slot holds u_k
        for i in range(3, size):
            m[i, i - 1] = 1.0
    m[1, 0], m[1, 1] = -ki, 1.0                   # I_(k+1) = I_k - ki y_k
    return float(max(abs(np.linalg.eigvals(m))))


def _px_span(p):
    base = p["gain"] * p["u0"]
    return max(max(abs(r - base) for _, r in p["schedule"]), abs(p["gain"] * p["load"]), 10.0 * p["noise_sd"], 1e-6)


def _px_admissible(p, kc, ti, seed):
    if not (abs(kc) <= basal.PID_KC_LIMIT and basal.PID_TI_RANGE[0] <= ti <= basal.PID_TI_RANGE[1]):
        return None
    if _px_radius(p, kc, ti) >= 1.0:
        return None
    sim = _px_replay(p, kc, ti, seed)
    if (sim["max_abs_error"] > basal.PID_DIVERGE * _px_span(p)
            or sim["longest_limit_run"] > basal.PID_SAT_FRACTION * p["steps"]):
        return None
    return sim["cost"]


def pid_simopt_verify(data, output, certificate):
    """Independent closed-loop replay of the returned PI gains on the declared scenario (cost, IAE, effort, maximum
    error, longest limit run recomputed; no divergence, no persistent saturation), linear stability from this
    module's own state matrix, the declared PI form, the declared derivation of the optimisation noise, and local
    optimality there: no +-1% move of Kc or Ti (log scale) is admissible at a lower declared cost.
    Not verified: global optimality, or that the FOPDT model and noise describe the real plant."""
    p = basal._pid_inputs(data)
    try:
        ctrl = basal._pid_controller(output)
    except GenomeError:
        return {"controller_well_formed": False}
    cert = _cert(certificate)
    pi_form = (ctrl["law"] == "pid" and ctrl["td"] == 0.0 and ctrl["tf"] == 0.0 and ctrl["b"] == 1.0
               and output.get("rule") == PX_RULE)
    if not pi_form:
        return {"controller_well_formed": True, "controller_is_declared_pi": False}
    kc, ti = ctrl["kc"], ctrl["ti"]
    sim = _px_replay(p, kc, ti, p["seed"])
    rho = _px_radius(p, kc, ti)
    opt = cert.get("optimisation") if isinstance(cert.get("optimisation"), dict) else {}
    noise = _px_noise_seed(p["seed"])
    centre = _px_admissible(p, kc, ti, noise)
    local = centre is not None and basal._close(centre, opt.get("objective"))
    if local:
        sign, z = (1.0 if kc > 0 else -1.0), (math.log(abs(kc)), math.log(ti))
        for dz in ((PX_LOG_STEP, 0.0), (-PX_LOG_STEP, 0.0), (0.0, PX_LOG_STEP), (0.0, -PX_LOG_STEP)):
            moved = _px_admissible(p, sign * math.exp(z[0] + dz[0]), math.exp(z[1] + dz[1]), noise)
            if moved is not None and moved < centre - 1e-9 * max(1.0, abs(centre)):
                local = False
    return {"controller_well_formed": True, "controller_is_declared_pi": True,
            "gain_sign_matches_plant": (kc > 0) == (p["gain"] > 0),
            "seed_bound": cert.get("seed") == p["seed"] and cert.get("delay_samples") == p["delay"],
            "iae_recomputed": basal._close(sim["iae"], cert.get("iae")),
            "effort_recomputed": basal._close(sim["effort_tv"], cert.get("effort_tv")),
            "cost_recomputed": basal._close(sim["cost"], cert.get("cost")),
            "max_error_recomputed": basal._close(sim["max_abs_error"], cert.get("max_abs_error")),
            "limit_run_recomputed": cert.get("longest_limit_run") == sim["longest_limit_run"],
            "no_divergence": sim["max_abs_error"] <= basal.PID_DIVERGE * _px_span(p),
            "no_persistent_saturation": sim["longest_limit_run"] <= basal.PID_SAT_FRACTION * p["steps"],
            "linear_loop_stable": rho < 1.0,
            "spectral_radius_recomputed": abs(rho - basal._num(cert.get("closed_loop_spectral_radius"))) <= 1e-6,
            "optimisation_noise_is_the_declared_derivation": opt.get("noise_seed") == noise
            and opt.get("log_step") == PX_LOG_STEP,
            "locally_optimal_on_the_optimisation_noise": local}


def pid_powell(data):
    """Competitor: SciPy's Powell direction-set search (scipy.optimize.minimize) on the same objective - the declared
    cost on the same independent noise realisation, inadmissible gains penalised - started from AMIGO. On
    development seeds 0-9 the candidate was better on 5, Powell on 4 (one tie), each by under 1% of the reference
    cost, and Powell's median latency was about twice the candidate's."""
    from scipy.optimize import minimize
    p = basal._pid_inputs(data)
    if not _px_reachable(p):
        return None
    sign, own, cost, _ = _px_objective(p)
    z0, _ = _px_start(data, p)
    res = minimize(lambda z: min(cost(z), 1e300), z0, method="Powell",
                   options={"xtol": 1e-3, "ftol": 1e-9, "maxfev": 400})
    if not math.isfinite(cost(res.x)) or cost(res.x) >= 1e300:
        return None
    return {**_px_controller(sign, [float(res.x[0]), float(res.x[1])]), "rule": "Powell-optimised PI"}


# =================================================================== genomes
INTELLIGENCES = [
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.bnb.knapsack_01", version="1.0.0", family="knapsack_bnb", layer=3,
            operation="knapsack_01_branch_bound", epistemic_class="optimization",
            subgeometry="0/1 knapsack, integer weights (the geometry of dp_knapsack)",
            source_provenance="OR-Tools algorithms.knapsack_solver (multidimension branch and bound, dynamic "
                              "programming); promoted from dp_knapsack's competitor, which superseded it in "
                              "admission v1",
            native_representation="item values, integer weights, integer capacity",
            required_inputs=("values", "weights", "capacity"),
            output_contract={"selected": "[item index]", "value": "int", "weight": "int"},
            algorithm_or_runtime="OR-Tools branch and bound under a 50 ms slice; if it has not proven optimality, "
                                 "OR-Tools' compiled dynamic program over capacity (n x (C + 1) <= 4e6 cells); "
                                 "UNKNOWN when neither proves an optimum",
            parameters={"bnb_slice_s": KX_BNB_SLICE, "dp_cells": KX_DP_CELLS, "check_cells": KX_CHECK_CELLS},
            composition_inputs=("candidate items", "budget"), composition_outputs=("selected", "value"),
            # the solver's optimality report is not a checkable proof: the verifier recomputes the optimum
            evidence_type="exact_calculation",
            verification_method="index/capacity/value recomputation and the exact optimum by an independent "
                                "dynamic program over the cheaper axis (capacity or total value)",
            confidence_semantics="exact within the supplied values and weights",
            resource_profile="compiled branch and bound (<= 50 ms), compiled DP fallback (<= 4e6 cells, about "
                             "0.06-0.6 s); verification O(n min(C, total value)) <= 4e6 cells",
            latency_profile="about 0.1 ms at the benchmark size on development seeds; up to about 0.7 s when "
                            "branch and bound stalls and the DP fallback runs",
            known_strengths=("exact", "compiled; several times faster than the NumPy dynamic program it replaces",
                             "bounded: a branch-and-bound stall costs 50 ms, then a pseudo-polynomial DP answers "
                             "exactly (on review instances with few distinct item types the bare solver spent its "
                             "whole 10 s limit without proving optimality)",
                             "answers beyond the dynamic program's 60-item / 2000-capacity native range whenever "
                             "the independent check can certify the answer"),
            known_failure_modes=("branch and bound is exponential in the worst case; when it stalls and n x (C + 1) "
                                 "exceeds 4e6 the answer is UNKNOWN",
                                 "values and weights supplied by the caller may be wrong"),
            counterindications=("multiple constraints (multi-dimensional knapsack) - not this genome's contract",
                                "real-valued weights"),
            abstention_conditions=("n x min(capacity, total value) above 4e6 cells (the check cannot certify it)",),
            benchmark_suite="dp_knapsack's suite: uncorrelated / weakly / strongly correlated / subset-sum, 20-60 "
                            "items, capacity <= 2000; seeds 0-9 dev; held-out seeds are chosen fresh at admission",
            baseline="dp_knapsack's own solve (exact NumPy dynamic program over capacity; the superseded candidate)",
            competitor="OR-Tools CP-SAT on the 0/1 model (one worker, fixed seed, 10 s): a different exact engine "
                       "that also stayed exact on the branch-and-bound-hard review instances; the bare branch and "
                       "bound that superseded dp_knapsack is this genome's own primary engine (an ablation, in the "
                       "notes), and SciPy HiGHS milp (12-100 ms on dev) was slower", dependency="ortools",
            lineage=LINEAGE + ("superseded genome dp_knapsack 1.0.1", V1 + "#genomes.dp_knapsack"), **_common()),
        solve=knapsack_bnb_solve, verify=knapsack_bnb_verify, instance=solvers_b.knapsack_instance,
        score=solvers_b.knapsack_score, baseline=_former(solvers_b.knapsack_solve),
        competitor=solvers_b.knapsack_cpsat, subregion=solvers_b.knapsack_subregion, tolerance=1e-9,
        promotes="dp_knapsack",
        notes={"bitset_solver_rejected": "OR-Tools' Knapsack64ItemsSolver was the fastest exact arm on dev seeds "
                                         "(about 0.09 ms) but ignores its time limit: 13 s on a 64-item and 339 s "
                                         "on a 40-item review instance (two item types in multiples, drawn from "
                                         "review RNG seed 3100); it is not used",
               "ablation": "the bare branch and bound (solvers_b.knapsack_ortools, 10 s limit, best incumbent on "
                           "timeout) ties this genome on dev seeds at 0.08 ms against 0.08-0.11 ms; on 11 of 40 "
                           "review instances with two item types in multiples (seeds 3400-3439, 40 items) it did not "
                           "prove optimality within 1 s (one incumbent was suboptimal, review seed 3434; at 10 s it "
                           "found that optimum without proving it), where this genome answered all 11 exactly from "
                           "the DP fallback in about 0.06 s",
               "dev_projection": _DEV_KX}),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.graph.grid_dijkstra", version="1.0.0", family="grid_dijkstra", layer=3,
            operation="grid_dijkstra_route", epistemic_class="optimization",
            subgeometry="single-pair shortest path on a weighted 4-connected grid (the geometry of search_astar)",
            source_provenance="Dijkstra (1959); SciPy sparse.csgraph; LP duality for shortest paths (node "
                              "potentials); promoted from search_astar's competitor, which superseded it in "
                              "admission v1",
            native_representation="grid of cell entry costs (0 = blocked), start and goal cells",
            required_inputs=("grid", "start", "goal"),
            output_contract={"reachable": "bool", "moves": "U/D/L/R string or null", "cost": "int or null",
                             "steps": "int"},
            algorithm_or_runtime="compiled single-source Dijkstra on a NumPy-built CSR digraph; potentials = "
                                 "distances capped at the goal's",
            parameters={"native_side": GD_NATIVE},
            composition_inputs=("terrain cost grid",), composition_outputs=("moves", "cost"),
            evidence_type="optimality_certificate",
            verification_method="route replay plus a dual (potential) certificate check: integer potential per "
                                "cell, zero at the start, feasible on every passable edge, tight on the route; "
                                "unreachability by an independent flood fill",
            confidence_semantics="exact shortest path within the supplied costs, with a checkable optimality proof",
            resource_profile="O(N log N) compiled for N <= 10 000 cells; certificate one integer per cell",
            latency_profile="about 0.9-1.5 ms at the benchmark size on development seeds",
            known_strengths=("exact with a proof the verifier checks in linear time without searching",
                             "compiled inner loop", "proves unreachability (connected component)"),
            known_failure_modes=("settles every reachable cell even when the goal is near (no heuristic)",
                                 "certificate size grows with the grid (about 80 KB at 100 x 100)"),
            counterindications=("diagonal or any-angle movement", "time-varying costs",
                                "many queries on one grid (all-pairs or landmark methods amortise better)"),
            abstention_conditions=("grid larger than 100 x 100",),
            benchmark_suite="search_astar's suite: open weighted / uniform-cost obstacle / walls-and-mud grids "
                            "30-60 per side; seeds 0-9 dev; held-out seeds are chosen fresh at admission",
            baseline="search_astar's own solve (pure-Python A*; the superseded candidate)",
            competitor="NetworkX bidirectional Dijkstra on the equivalent digraph: the strongest installed "
                       "implementation that is not this genome's own routine; OR-Tools min-cost flow (one unit, start "
                       "to goal) and SciPy yen (K = 1) were also measured - the first slower, the second the same "
                       "compiled Dijkstra; no faster different deployable alternative was found installed",
            dependency="scipy",
            lineage=LINEAGE + ("superseded genome search_astar 1.0.2", V1 + "#genomes.search_astar"), **_common()),
        solve=grid_dijkstra_solve, verify=grid_dijkstra_verify, instance=solvers_b.astar_instance,
        score=solvers_b.astar_score, baseline=_former(solvers_b.astar_solve), competitor=grid_networkx_bidirectional,
        subregion=solvers_b.astar_subregion, tolerance=1e-9, promotes="search_astar",
        notes={"weak_competitor": "the strongest different alternative found is slower than the baseline; an "
                                  "admission will mostly measure this genome against the A* it replaces",
               "ablation": "the bare SciPy Dijkstra that superseded search_astar (solvers_b.astar_csgraph, no "
                           "potential certificate) took 0.86-0.87 ms against this genome's 0.92-0.94 ms in the same "
                           "runs (1.06-1.09x): the certificate costs little to emit, and without it a verifier must "
                           "search (search_astar's verifier runs a pure-Python Dijkstra)",
               "dev_projection": _DEV + "EXPERIMENTAL: 10 ties; median 1.3-1.5 ms vs 1.4-1.9 ms (A*) and 10.6-14.4 "
                                        "ms (NetworkX) over three runs - cheaper than A* but by less than the rule's "
                                        "1.25x, so no demonstrated edge over the baseline on this suite"}),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.game.zero_sum_lp_dual", version="1.0.0", family="game_lp_dual", layer=3,
            operation="zero_sum_lp_dual_equilibrium", epistemic_class="strategic",
            subgeometry="two-player finite zero-sum matrix game (the geometry of game_minimax)",
            source_provenance="von Neumann minimax theorem; LP duality; OR-Tools GLOP with SciPy HiGHS fallback; "
                              "promoted from game_minimax's competitor (one LP plus its duals), which superseded it "
                              "in admission v1",
            native_representation="row player's payoff matrix", required_inputs=("payoffs",),
            output_contract={"row_strategy": "[float]", "column_strategy": "[float]", "value": "float"},
            algorithm_or_runtime="one LP (maximise v s.t. x B >= v, sum x = 1) on the matrix rescaled to [0, 1]; "
                                 "column strategy = its dual solution; GLOP first, HiGHS if GLOP fails its own "
                                 "duality-gap self-check",
            parameters={"self_check_gap": GL_GAP, "stated_tolerance": GL_STATED, "verify_tolerance": GL_TOL,
                        "support": GL_SUPPORT},
            composition_inputs=("payoff model",), composition_outputs=("row_strategy", "column_strategy", "value"),
            evidence_type="optimality_certificate",
            verification_method="exact best responses with compensated sums, measured above the smallest payoff: "
                                "zero duality gap between the two strategies' guarantees, value bracketed, every "
                                "supported action a best response, certificate bounds recomputed",
            confidence_semantics="exact equilibrium of the supplied matrix (floating point, relative tolerance 1e-7)",
            resource_profile="one LP with m + 1 variables and n + 1 rows (m, n <= 100)",
            latency_profile="about 0.5 ms at the benchmark size on development seeds",
            known_strengths=("both players' strategies from one solve",
                             "scale- and offset-free (rescaled before the LP; self-checked on the rescaled game)",
                             "an engine fallback before any UNKNOWN"),
            known_failure_modes=("payoffs supplied by the caller may be wrong", "assumes a strictly adversarial "
                                 "opponent; overly conservative against a non-adversary",
                                 "degenerate games have many equilibria; one is returned",
                                 "UNKNOWN when payoffs agree to about nine significant figures (a float value cannot "
                                 "be stated within half the verification tolerance)"),
            counterindications=("general-sum games", "sequential games with private information"),
            abstention_conditions=("column_payoffs differ from the negated payoffs",),
            benchmark_suite="game_minimax's suite: random, cyclic (RPS-like) and planted-saddle integer games up to "
                            "15 x 15; seeds 0-9 dev; held-out seeds are chosen fresh at admission",
            baseline="game_minimax's own solve (row and column LPs in SciPy HiGHS; the superseded candidate)",
            competitor="one SciPy HiGHS LP with the column strategy from its dual marginals (game_dual_lp, the "
                       "mechanism that superseded game_minimax; a different engine from this genome's primary GLOP); "
                       "HiGHS interior point and dual simplex were no faster",
            dependency="ortools", lineage=LINEAGE + ("superseded genome game_minimax 1.0.1",
                                                     V1 + "#genomes.game_minimax"), **_common()),
        solve=game_lp_dual_solve, verify=game_lp_dual_verify, instance=solvers_b.game_instance,
        score=solvers_b.game_score, baseline=_former(solvers_b.game_solve), competitor=solvers_b.game_dual_lp,
        subregion=solvers_b.game_subregion, tolerance=1e-9, promotes="game_minimax",
        notes={"choice": "the build specification named SciPy HiGHS for this genome; on dev seeds 0-9 the same LP in "
                         "OR-Tools GLOP was 3-4x faster than through scipy.optimize.linprog (call overhead dominates "
                         "at this size), so GLOP leads, HiGHS is the fallback, and HiGHS alone is the named "
                         "competitor - promoting HiGHS alone would have named a faster competitor than itself",
               "dev_projection": _DEV + "DEFAULT_FOR_GEOMETRY: 10 ties; median 0.49-0.52 ms vs 3.3-3.4 ms (two "
                                        "LPs) and 1.7-1.8 ms (one HiGHS LP) over three runs"}),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.control.simopt_pi", version="1.0.0", family="pid_simopt", layer=3,
            operation="pi_simopt_track", epistemic_class="physical",
            subgeometry="setpoint tracking and load rejection of a declared first-order-plus-dead-time plant (the "
                        "geometry of basal_pid)",
            source_provenance="Nelder & Mead (1965); compass (pattern) search; Astrom & Hagglund (2004) AMIGO start; "
                              "promoted from basal_pid's competitor, which superseded it 0-30 in admission v2",
            native_representation="FOPDT model (K, tau, theta) + sample time + setpoint schedule + load step + "
                                  "noise sd + actuator limits + seed",
            required_inputs=("gain", "tau", "theta", "dt", "steps", "setpoints", "u_min", "u_max", "u0"),
            output_contract={"law": "pid", "kc": "float", "ti": "float", "td": "0.0", "tf": "0.0", "b": "1.0",
                             "rule": "str"},
            algorithm_or_runtime="Nelder-Mead on (log |Kc|, log Ti) minimising the declared cost in closed-loop "
                                 "simulation on an independent noise realisation, then a compass polish to local "
                                 "optimality at a 1% log step; inadmissible gains cost infinity",
            parameters={"nelder_mead_iterations": basal.PID_OPT_ITERATIONS, "log_step": PX_LOG_STEP,
                        "max_steps": PX_MAX_STEPS, "effort_weight": basal.PID_EFFORT_WEIGHT},
            composition_inputs=("plant_model", "setpoints"), composition_outputs=("controller_gains",),
            evidence_type="control_trace",
            verification_method="independent ring-buffer closed-loop replay (cost, IAE, effort, maximum error, "
                                "longest limit run), stability from the verifier's own state matrix, PI form, and "
                                "local optimality on the declared optimisation noise (four +-1% moves re-simulated)",
            confidence_semantics="locally optimal for the declared model and an independent noise realisation; "
                                 "performance on the declared scenario is a simulation, and real plants differ by "
                                 "model error",
            resource_profile="about 120 closed-loop simulations of <= 2000 steps (pure Python)",
            latency_profile="about 0.1-0.4 s at the benchmark size on development seeds (load-dependent)",
            known_strengths=("optimises exactly the declared cost on the declared model",
                             "never emits gains its own simulation shows unstable, divergent or saturated",
                             "local optimality is checkable"),
            known_failure_modes=("local, not global, optimum", "gains are only as good as the FOPDT model",
                                 "two orders of magnitude slower than a tuning rule",
                                 "tuned to the declared cost: no explicit robustness margin to model mismatch"),
            counterindications=("integrating or unstable plants", "plant-model mismatch dominates (prefer a robust "
                                "rule such as SIMC or AMIGO)", "horizons above 2000 steps"),
            abstention_conditions=("more than 2000 steps", "a setpoint unreachable within the actuator limits",
                                   "no admissible gains found", "optimised gains fail on the declared scenario"),
            benchmark_suite="basal_pid's suite: seeded FOPDT plants, theta/tau 0.05-2, two setpoint steps + input "
                            "load step + noise; score -(IAE + effort) / grid-optimal PI cost; seeds 0-9 dev; "
                            "held-out seeds are chosen fresh at admission",
            baseline="basal_pid's own solve (SIMC PI, tau_c = theta; the superseded candidate)",
            competitor="SciPy Powell (scipy.optimize.minimize) on the same objective and noise realisation from the "
                       "same AMIGO start: the strongest optimiser found that is not this genome's own search; on "
                       "dev seeds 0-9 the candidate was better on 5, Powell on 4 (one tie), each by under 1% of the "
                       "reference cost, at about half Powell's latency; a 14 x 10 log grid search on the same noise "
                       "was worse",
            dependency=None, lineage=LINEAGE + ("superseded genome basal_pid 1.0.2", V2 + "#genomes.basal_pid"),
            **_common()),
        solve=pid_simopt_solve, verify=pid_simopt_verify, instance=basal.pid_instance, score=basal.pid_score,
        baseline=_former(basal.pid_solve), competitor=pid_powell, subregion=basal.pid_subregion, tolerance=1e-9,
        promotes="basal_pid",
        notes={"layer": "the answer is a Layer 1 PI law; the intelligence producing it is numerical simulation-"
                        "optimisation, so the genome is Layer 3",
               "dependency": "numpy for the stability check only (as basal_pid); SciPy is used by the competitor",
               "ablation": "Nelder-Mead alone (basal.pid_sim_optimised, the arm that superseded basal_pid) tied on "
                           "all 10 dev seeds - the polish never moved its answer there - at 0.109 s against this "
                           "genome's 0.115 s: the polish costs four simulations and makes local optimality checkable",
               "dev_projection": _DEV + "DEFAULT_FOR_GEOMETRY: 10-0 over SIMC (p = 0.001); 5-4-1 against Powell "
                                        "(p = 0.5); median 0.15-0.37 s vs 0.27-0.89 s (Powell) and 0.001 s (SIMC) "
                                        "over two runs at this version under varying load"}),
]
