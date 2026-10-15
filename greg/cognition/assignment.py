"""Linear assignment answered by an open-source engine and accepted only on GREG's certificate.

Capability Genesis forms ``cognition.mechanism:linear_assignment`` from an installed package when the
Competency Compiler reports a residual deficit whose geometry is an optimisation over a cost matrix
(directive 2026-10-07 section 24: "Do not invent a new subsystem when SciPy, OR-Tools ... already solves
the residual geometry safely"). The engines (SciPy's ``linear_sum_assignment``, OR-Tools'
``SimpleLinearSumAssignment``) are untrusted. NetworkX's ``minimum_weight_full_matching`` defers to
SciPy's routine, so it is the same engine, not an alternative; Genesis records that and does not count it.

The question: assign every row of an m x n cost matrix to a distinct column (or, when m > n, every
column to a distinct row) so that the total cost is least (or, with ``maximize``, the total value is
greatest). GREG normalises the request so rows <= columns and the engine always minimises.

Certificate (GREG-owned, exact, shares no code with any engine). Costs are scaled to integers by their
common denominator (a float is an exact dyadic rational), so every comparison below is exact. From the
claimed assignment GREG derives column potentials v by shortest paths over exchanges (a negative exchange
cycle, or a row cheaper on an unassigned column, refutes the claim), sets u_i = c_i,sigma(i) - v_sigma(i),
and then checks the linear-programming dual directly, over every pair:

    u_i + v_j <= c_ij for every (i, j);  v_j <= 0;  v_j = 0 for every unassigned column;
    sum(u) + sum(v) == the assignment's cost.

By weak duality no assignment costs less. The derivation of v is only a search; the final check is the proof.

Oracle (frozen, GREG-owned, never shown to an engine): fixed edge cases plus cost matrices drawn from the
flock admission instance generator (``greg.cognition.genomes.collective.flock_instance``: agents' starts and
goals; cost = travel distance) on the admission harness's development seeds only. Expected optima come from
brute force over every injective map in exact integers. Competence is enforced before any engine sees input:
a rectangular matrix of 1-200 rows and columns, finite numbers of magnitude at most 1e12.
"""
from __future__ import annotations

from collections import deque
import copy
from fractions import Fraction
from functools import lru_cache
import itertools
import math
import random

from greg.capabilities import CapabilityError

FUNCTION = "cognition.mechanism:linear_assignment"
MAX_SIDE, MAX_ABS = 200, 1e12
# The residual geometry this mechanism serves: an optimisation (or undeclared) request whose inputs are a cost
# matrix and, optionally, the direction. Every input the request carries must be one the mechanism reads, so an
# extra constraint (a budget, a capacity) is never silently ignored.
SIGNATURE = {"classes": ("optimization",), "required": ("costs",), "optional": ("maximize",)}


class CertificateError(Exception):
    """The engine's claim does not prove itself."""


def _invalid(why: str):
    # Wording deliberately avoids the capability-fault markers: a bad request is not a broken engine.
    return CapabilityError(f"assignment request invalid: {why}")


def _cost(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _invalid(f"{value!r} is not a number")
    if isinstance(value, float) and not math.isfinite(value):
        raise _invalid(f"{value!r} is not finite")
    if abs(value) > MAX_ABS:
        raise _invalid("a cost exceeds 1e12 in magnitude")
    return value


def normalize_assignment(params: dict) -> dict:
    """Competence check and canonical form: rows <= columns, minimisation, numbers kept exactly as given."""
    if not isinstance(params, dict):
        raise _invalid("parameters must be an object")
    costs, maximize = params.get("costs"), params.get("maximize", False)
    if not isinstance(maximize, bool):
        raise _invalid("maximize must be true or false")
    if not isinstance(costs, list) or not 1 <= len(costs) <= MAX_SIDE:
        raise _invalid(f"costs must be a list of 1-{MAX_SIDE} rows")
    width = len(costs[0]) if isinstance(costs[0], list) else 0
    if not 1 <= width <= MAX_SIDE or any(not isinstance(row, list) or len(row) != width for row in costs):
        raise _invalid(f"costs must be rectangular with 1-{MAX_SIDE} columns")
    matrix = [[_cost(x) for x in row] for row in costs]
    transposed = len(matrix) > width
    if transposed:
        matrix = [list(column) for column in zip(*matrix)]
    if maximize:
        matrix = [[-x for x in row] for row in matrix]           # exact for every int and float
    return {"costs": matrix, "rows": len(matrix), "cols": len(matrix[0]), "maximize": maximize,
            "transposed": transposed}


# -- engine runners: fixed GREG code executed in the candidate's isolated interpreter --------

RUNNERS = {
    "scipy.assignment": r'''
def solve(req):
    import numpy as np
    rows, cols = MODULE.linear_sum_assignment(np.array(req["costs"], dtype=float))
    return {"pairs": [[int(i), int(j)] for i, j in zip(rows, cols)]}
''',
    "ortools.assignment": r'''
def solve(req):
    costs = req["costs"]
    if any(isinstance(x, float) and not x.is_integer() for row in costs for x in row):
        raise ValueError("non-integer costs are outside OR-Tools' integer assignment")
    m, n = len(costs), len(costs[0])
    solver = MODULE.SimpleLinearSumAssignment()
    for i in range(n):                       # square: rows beyond m are zero-cost dummies (m <= n here)
        for j in range(n):
            solver.add_arc_with_cost(i, j, int(costs[i][j]) if i < m else 0)
    status = solver.solve()
    if status != solver.OPTIMAL:
        raise ValueError(f"OR-Tools assignment status {status}")
    return {"pairs": [[i, int(solver.right_mate(i))] for i in range(m)]}
''',
}


# -- certificate (GREG-owned; exact) ----------------------------------------------------------

def _integers(matrix) -> tuple[list, int]:
    """The matrix times its common denominator, as exact integers, and that denominator."""
    exact = [[Fraction(x) for x in row] for row in matrix]
    scale = 1
    for row in exact:
        for value in row:
            scale = math.lcm(scale, value.denominator)
    return [[int(value * scale) for value in row] for row in exact], scale


def _plain(value: Fraction):
    return int(value) if value.denominator == 1 else float(value)


def _pairs(req: dict, claim) -> dict:
    if not isinstance(claim, dict) or not isinstance(claim.get("pairs"), list):
        raise CertificateError("the claim must carry assignment pairs")
    m, n = req["rows"], req["cols"]
    sigma = {}
    for item in claim["pairs"]:
        if not isinstance(item, list) or len(item) != 2 or any(isinstance(x, bool) or not isinstance(x, int)
                                                                for x in item):
            raise CertificateError(f"pair {item!r} must be [row, column] integers")
        i, j = item
        if not (0 <= i < m and 0 <= j < n) or i in sigma:
            raise CertificateError(f"pair {item!r} names no row/column or repeats a row")
        sigma[i] = j
    if len(sigma) != m or len(set(sigma.values())) != m:
        raise CertificateError("every row must be assigned to a distinct column")
    return sigma


def certify_assignment(req: dict, claim) -> dict:
    sigma = _pairs(req, claim)
    cost, scale = _integers(req["costs"])
    m, n = req["rows"], req["cols"]
    owner = {j: i for i, j in sigma.items()}
    # Search for column potentials: v_k <= v_a + c[i][k] - c[i][a] for a = sigma(i); v <= 0; v = 0 off the
    # assignment. Shortest paths from a virtual root over n + 1 nodes (queue-based Bellman-Ford); a shortest
    # path longer than n arcs repeats a column, so it closes a negative exchange cycle.
    v, arcs = [0] * n, [1] * n
    queue, queued = deque(sorted(owner)), [j in owner for j in range(n)]
    while queue:
        a = queue.popleft()
        queued[a] = False
        i = owner[a]
        row, base = cost[i], v[a] - cost[i][a]
        for k in range(n):
            t = base + row[k]
            if t < v[k]:
                if k not in owner:
                    raise CertificateError(f"moving row {i} to unassigned column {k} lowers the total: the "
                                           "assignment is not optimal")
                v[k], arcs[k] = t, arcs[a] + 1
                if arcs[k] > n:
                    raise CertificateError("a cycle of exchanges lowers the total: the assignment is not optimal")
                if not queued[k]:
                    queued[k] = True
                    queue.append(k)
    # The proof: the LP dual, checked on every pair in exact integers.
    u = [cost[i][sigma[i]] - v[sigma[i]] for i in range(m)]
    for i in range(m):
        ui, row = u[i], cost[i]
        for j in range(n):
            if ui + v[j] > row[j]:
                raise CertificateError(f"dual infeasible at row {i}, column {j}")
    if any(x > 0 for x in v) or any(v[j] for j in range(n) if j not in owner):
        raise CertificateError("column potentials violate their sign or vanish off the assignment")
    total = sum(cost[i][sigma[i]] for i in range(m))
    if sum(u) + sum(v) != total:
        raise CertificateError("the dual objective differs from the assignment's cost")
    sign = -1 if req["maximize"] else 1
    pairs = sorted([j, i] if req["transposed"] else [i, j] for i, j in sigma.items())
    return {"certified": True, "pairs": pairs, "total": _plain(Fraction(sign * total, scale)),
            "objective": "maximize" if req["maximize"] else "minimize",
            "shape": [n, m] if req["transposed"] else [m, n],
            "certificate": {"kind": "linear-programming dual: u_i + v_j <= c_ij on every pair, equality on the "
                                    "assignment, v <= 0 and zero on unassigned columns, equal objectives",
                            "pairs_checked": m * n, "arithmetic": "exact integers (costs times their common "
                                                                  "denominator)"}}


# -- frozen oracle (independent of every engine; development seeds only) ---------------------

FIXED = [
    ("one-by-one", {"costs": [[5]]}),
    ("all-tied", {"costs": [[3, 3], [3, 3]]}),
    ("wide", {"costs": [[4, 1, 3], [2, 0, 5]]}),
    ("tall", {"costs": [[4, 2], [1, 0], [3, 5]]}),
    ("negative", {"costs": [[-5, 2], [3, -1]]}),
    ("maximize", {"costs": [[1, 9, 3], [8, 2, 7], [4, 6, 5]], "maximize": True}),
    ("decimal", {"costs": [[0.1, 0.2], [0.3, 0.1]]}),
    ("one-ulp", {"costs": [[1.0, 1.0000000000000002], [1.0000000000000002, 1.0]]}),
    ("large", {"costs": [[1e12, 0], [0, 1e12]]}),
]


def brute_force(params: dict) -> int | float:
    """The optimum over every injective map, in exact integers; for oracle-sized matrices only."""
    costs, maximize = params["costs"], params.get("maximize", False)
    m, n = len(costs), len(costs[0])
    if math.perm(max(m, n), min(m, n)) > 50_000:
        raise ValueError("brute force is for oracle-sized matrices only")
    ratios = [[x.as_integer_ratio() for x in row] for row in costs]
    common = math.lcm(*(d for row in ratios for _, d in row))
    scaled = [[p * (common // d) for p, d in row] for row in ratios]
    if m > n:                                                    # assign every column to a distinct row
        scaled = [list(column) for column in zip(*scaled)]
        m, n = n, m
    totals = (sum(row[j] for row, j in zip(scaled, chosen)) for chosen in itertools.permutations(range(n), m))
    best = max(totals) if maximize else min(totals)
    return _plain(Fraction(best, common))


def _from_flock(seed: int, variant: int) -> dict:
    """A cost matrix from one flock admission instance: agent i to goal j costs their distance."""
    from greg.cognition.genomes.collective import flock_instance
    data, _ = flock_instance(seed)
    starts, goals = data["starts"], data["goals"]
    distance = [[math.dist(s, g) for g in goals] for s in starts]
    if variant == 0:
        return {"costs": distance}                                               # square, real costs
    if variant == 1:
        return {"costs": [[round(10 * d) for d in row[:-1]] for row in distance]}  # tall, integers, ties
    if variant == 2:
        return {"costs": distance[:-1]}                                          # wide, real costs
    return {"costs": [[round(10 * d) for d in row] for row in distance], "maximize": True}


@lru_cache(maxsize=1)
def _frozen_cases() -> tuple:
    from greg.cognition.genomes.admission import DEV_SEEDS
    cases = [{"name": name, "input": params} for name, params in FIXED]
    cases += [{"name": f"flock-dev{seed}", "input": _from_flock(seed, seed % 4)} for seed in DEV_SEEDS]
    for case in cases:
        case["expected"] = {"total": brute_force(case["input"])}
    return tuple(cases)


def oracle_assignment(seed: int) -> list[dict]:
    """The frozen acceptance vectors. ``seed`` does not choose instances: only development seeds are drawn."""
    return copy.deepcopy(list(_frozen_cases()))


def judge_assignment(answer: dict, expected: dict) -> bool:
    return answer["total"] == expected["total"]


# -- scale probe and the simplest local implementation an engine must be compared with ------

def size(req: dict) -> dict:
    return {"rows": req["rows"], "cols": req["cols"]}


def probe_assignment(seed: int) -> dict:
    rng = random.Random(seed ^ 0x3C3C)
    return {"costs": [[rng.randint(0, 1000) for _ in range(MAX_SIDE)] for _ in range(MAX_SIDE)]}


def local_hungarian(req: dict) -> dict:
    """Shortest-augmenting-path Hungarian algorithm in plain Python (rows <= columns): the simplest local
    alternative to depending on a package. Native numbers, as a local implementation would use."""
    cost = req["costs"]
    m, n = len(cost), len(cost[0])
    u, v, match, way = [0] * (m + 1), [0] * (n + 1), [0] * (n + 1), [0] * (n + 1)
    for i in range(1, m + 1):
        match[0], j0 = i, 0
        least, used = [math.inf] * (n + 1), [False] * (n + 1)
        while True:
            used[j0] = True
            i0, delta, j1 = match[j0], math.inf, 0
            row, ui = cost[i0 - 1], u[i0]
            for j in range(1, n + 1):
                if not used[j]:
                    reduced = row[j - 1] - ui - v[j]
                    if reduced < least[j]:
                        least[j], way[j] = reduced, j0
                    if least[j] < delta:
                        delta, j1 = least[j], j
            for j in range(n + 1):
                if used[j]:
                    u[match[j]] += delta
                    v[j] -= delta
                else:
                    least[j] -= delta
            j0 = j1
            if match[j0] == 0:
                break
        while j0:
            j1 = way[j0]
            match[j0] = match[j1]
            j0 = j1
    pairs = sorted([match[j] - 1, j - 1] for j in range(1, n + 1) if match[j])
    total = sum(Fraction(cost[i][j]) for i, j in pairs)
    return {"pairs": pairs, "total": _plain(-total if req["maximize"] else total)}
