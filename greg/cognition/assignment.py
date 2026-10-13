"""Assignment answered by open-source engines and accepted only on GREG's certificate.

One function Capability Genesis can form from installed packages (greg/mechanisms.py):

    assignment.optimize   give every row its own column, at the lowest (or highest) total

Rows are people, vehicles or machines; columns are jobs, routes or slots. A missing (None) cost
means the pair is not allowed. Rows may be fewer than columns; then some columns stay free.

The engines (SciPy's linear_sum_assignment, OR-Tools' SimpleLinearSumAssignment) are untrusted.
GREG checks every answer itself, in exact integers, sharing no code with either:

an assignment: every row has exactly one allowed column and no column is used twice. It is
    optimal exactly when its residual graph has no negative cycle (no exchange of columns among
    rows, and no move to a free column, lowers the total). Bellman-Ford from a virtual root finds
    any such cycle; when none exists its distances are dual prices that prove the total.
"no full assignment exists": GREG runs its own augmenting-path matching. If that matches every
    row, the engine's claim is false. Otherwise the rows reachable from an unmatched row allow
    fewer columns than there are of them (Hall's condition fails), and GREG names both sets.

Competence is enforced here, before an engine sees the input: at most 120 rows and 120 columns,
costs up to 1e9 with at most six decimal places. GREG scales decimal costs to integers once (OR-Tools
takes integers only), so both engines and the certificate see the same exact problem. The frozen
oracle (brute force over every assignment) is GREG's and is never shown to an engine.
"""
from __future__ import annotations

from collections import deque
from fractions import Fraction
import itertools
import math
import random
import re

from greg.capabilities import CapabilityError

MAX_SIDE = 120
MAX_COST = 10**9
MAX_SCALE = 10**6                   # at most six decimal places
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.:-]{0,63}$")


class CertificateError(Exception):
    """The engine's claim does not prove itself."""


def _invalid(why: str):
    # Wording deliberately avoids the capability-fault markers: a bad request is not a broken engine.
    return CapabilityError(f"assignment request invalid: {why}")


def _cost(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _invalid(f"{value!r} is not a number (use null for a pair that is not allowed)")
    if isinstance(value, float) and not math.isfinite(value):
        raise _invalid(f"{value!r} is not finite")
    if abs(value) > MAX_COST:
        raise _invalid("a cost exceeds 1e9 in size")
    exact = Fraction(str(value)) if isinstance(value, float) else Fraction(value)
    if MAX_SCALE % exact.denominator:
        raise _invalid(f"{value!r} has more than six decimal places")
    return exact


def _names(given, count: int, prefix: str) -> list:
    names = list(given) if given is not None else [f"{prefix}{k + 1}" for k in range(count)]
    if len(names) != count:
        raise _invalid(f"{len(names)} {prefix} names for {count} {prefix}s")
    for n in names:
        if not isinstance(n, str) or not NAME.match(n):
            raise _invalid(f"name {n!r} must be 1-64 letters, digits, spaces or _.:-")
    if len(set(names)) != len(names):
        raise _invalid(f"{prefix} names repeat")
    return names


def normalize_assignment(params: dict) -> dict:
    if not isinstance(params, dict):
        raise _invalid("parameters must be an object")
    costs = params.get("costs")
    if not isinstance(costs, list) or not costs or not all(isinstance(r, list) for r in costs):
        raise _invalid("costs must be a non-empty list of rows")
    n, m = len(costs), len(costs[0])
    if m == 0 or any(len(r) != m for r in costs):
        raise _invalid("every row must list the same number of columns")
    if n > m:
        raise _invalid(f"{n} rows but {m} columns: every row needs its own column")
    if m > MAX_SIDE:
        raise _invalid(f"more than {MAX_SIDE} columns")
    maximize = params.get("maximize", False)
    if not isinstance(maximize, bool):
        raise _invalid("maximize must be true or false")
    exact = [[_cost(x) for x in row] for row in costs]
    scale = 1
    for row in exact:
        for x in row:
            if x is not None:
                scale = scale * x.denominator // math.gcd(scale, x.denominator)
    return {"rows": _names(params.get("rows"), n, "row"), "columns": _names(params.get("columns"), m, "column"),
            "costs": [[None if x is None else int(x * scale) for x in row] for row in exact],
            "scale": scale, "sense": "max" if maximize else "min"}


# -- engine runners: fixed GREG code executed in the candidate's isolated interpreter --------

RUNNERS = {
    "scipy.assignment": r'''
def solve(req):
    import numpy as np
    forbidden = -np.inf if req["sense"] == "max" else np.inf
    m = np.array([[forbidden if c is None else float(c) for c in row] for row in req["costs"]], dtype=float)
    try:
        rows, cols = MODULE.linear_sum_assignment(m, maximize=req["sense"] == "max")
    except ValueError as exc:
        if "infeasible" in str(exc):
            return {"status": "infeasible"}
        raise
    return {"status": "optimal", "pairs": [[int(i), int(j)] for i, j in zip(rows, cols)]}
''',
    "ortools.assignment": r'''
def solve(req):
    solver = MODULE.SimpleLinearSumAssignment()
    n, m = len(req["costs"]), len(req["costs"][0])
    sign = -1 if req["sense"] == "max" else 1
    for i, row in enumerate(req["costs"]):
        for j, c in enumerate(row):
            if c is not None:
                solver.add_arc_with_cost(i, j, sign * c)
    for i in range(n, m):                 # OR-Tools needs a perfect matching: free columns go to zero-cost rows
        for j in range(m):
            solver.add_arc_with_cost(i, j, 0)
    status = solver.solve()
    if status == solver.INFEASIBLE:
        return {"status": "infeasible"}
    if status != solver.OPTIMAL:
        raise RuntimeError(f"OR-Tools status {status}")
    return {"status": "optimal", "pairs": [[i, int(solver.right_mate(i))] for i in range(n)]}
''',
}


# -- certificates (GREG-owned; exact) ---------------------------------------------------------

def _plain(value: Fraction):
    return int(value) if value.denominator == 1 else float(value)


def _allowed(req) -> dict:
    return {(i, j): c for i, row in enumerate(req["costs"]) for j, c in enumerate(row) if c is not None}


def _negative_cycle_free(req, pairs: dict) -> dict | None:
    """Bellman-Ford over the residual graph of a full assignment, in exact integers (minimization form).

    Nodes: rows, columns and one sink. Unused allowed pair i-j: row -> column at w. Used pair:
    column -> row at -w. Free column: column -> sink at 0. Used column: sink -> column at 0. Every
    row is matched, so the source cannot lie on a cycle and is left out. Returns potentials, or None
    when a negative cycle (a cheaper exchange) exists."""
    sign = 1 if req["sense"] == "min" else -1
    n, m = len(req["costs"]), len(req["columns"])
    sink, used_columns = n + m, set(pairs.values())
    tails, heads, weights = [], [], []
    for (i, j), c in _allowed(req).items():
        w = sign * c
        a, b, w = (n + j, i, -w) if pairs.get(i) == j else (i, n + j, w)
        tails.append(a), heads.append(b), weights.append(w)
    for j in range(m):
        a, b = (sink, n + j) if j in used_columns else (n + j, sink)
        tails.append(a), heads.append(b), weights.append(0)
    dist = [0] * (n + m + 1)
    arcs = list(zip(tails, heads, weights))
    for _ in range(len(dist)):
        changed = False
        for a, b, w in arcs:
            if dist[a] + w < dist[b]:
                dist[b] = dist[a] + w
                changed = True
        if not changed:
            return {("r", i): dist[i] for i in range(n)} | {("c", j): dist[n + j] for j in range(m)}
    return None


def _match(req) -> dict:
    """GREG's own maximum bipartite matching (augmenting paths); row -> column."""
    adjacency = {i: [j for j, c in enumerate(row) if c is not None] for i, row in enumerate(req["costs"])}
    owner = {}

    def augment(i, seen):
        for j in adjacency[i]:
            if j not in seen:
                seen.add(j)
                if j not in owner or augment(owner[j], seen):
                    owner[j] = i
                    return True
        return False

    for i in adjacency:
        augment(i, set())
    return {i: j for j, i in owner.items()}


def _hall_violation(req, matched: dict) -> tuple[list, list]:
    """Rows reachable by alternating paths from an unmatched row, and the columns they allow."""
    adjacency = {i: [j for j, c in enumerate(row) if c is not None] for i, row in enumerate(req["costs"])}
    owner = {j: i for i, j in matched.items()}
    start = next(i for i in adjacency if i not in matched)
    rows, columns, queue = {start}, set(), deque([start])
    while queue:
        for j in adjacency[queue.popleft()]:
            if j not in columns:
                columns.add(j)
                if j in owner and owner[j] not in rows:
                    rows.add(owner[j])
                    queue.append(owner[j])
    return sorted(rows), sorted(columns)


def certify_assignment(req: dict, claim) -> dict:
    if not isinstance(claim, dict) or claim.get("status") not in ("optimal", "infeasible"):
        raise CertificateError("the claim must say optimal (with pairs) or infeasible")
    n, rows, columns, scale = len(req["costs"]), req["rows"], req["columns"], req["scale"]
    allowed = _allowed(req)
    if claim["status"] == "infeasible":
        matched = _match(req)
        if len(matched) == n:
            raise CertificateError("the engine said no full assignment exists, but one does")
        conflict, allow = _hall_violation(req, matched)
        reachable = {j for i in conflict for j in range(len(columns)) if (i, j) in allowed}
        if not (reachable <= set(allow) and len(reachable) < len(conflict)):
            raise CertificateError("GREG could not prove that no full assignment exists")
        return {"certified": True, "status": "infeasible", "sense": req["sense"],
                "rows_in_conflict": [rows[i] for i in conflict],
                "columns_they_allow": [columns[j] for j in sorted(reachable)], "engine_said": "infeasible",
                "certificate": {"kind": "Hall's condition fails: these rows allow fewer columns than there are "
                                        "rows", "pairs_checked": len(allowed), "arithmetic": "exact counting"}}
    pairs = claim.get("pairs")
    if not isinstance(pairs, list) or len(pairs) != n:
        raise CertificateError("the claim must give one [row, column] pair per row")
    chosen = {}
    for item in pairs:
        if not isinstance(item, list) or len(item) != 2 or any(isinstance(x, bool) or not isinstance(x, int)
                                                                for x in item):
            raise CertificateError(f"pair {item!r} must be [row index, column index]")
        i, j = item
        if (i, j) not in allowed:
            raise CertificateError(f"pair {item!r} is not an allowed pair")
        if i in chosen:
            raise CertificateError(f"row {rows[i]} is assigned twice")
        chosen[i] = j
    if len(set(chosen.values())) != n:
        raise CertificateError("a column is used twice")
    potentials = _negative_cycle_free(req, chosen)
    if potentials is None:
        raise CertificateError("a cheaper exchange of columns exists; the assignment is not optimal"
                               if req["sense"] == "min" else
                               "a more valuable exchange of columns exists; the assignment is not optimal")
    total = Fraction(sum(allowed[i, j] for i, j in chosen.items()), scale)
    used = set(chosen.values())
    return {"certified": True, "status": "optimal", "sense": req["sense"],
            "assignment": [[rows[i], columns[j], _plain(Fraction(allowed[i, j], scale))]
                           for i, j in sorted(chosen.items())],
            "total": _plain(total), "free_columns": [columns[j] for j in range(len(columns)) if j not in used],
            "certificate": {"kind": "no improving exchange: the residual graph has no negative cycle "
                                    "(Bellman-Ford over every allowed pair)",
                            "pairs_checked": len(allowed), "arithmetic": "exact integers",
                            "dual_prices": {"rows": {rows[i]: _plain(Fraction(potentials["r", i], scale))
                                                     for i in range(n)},
                                            "columns": {columns[j]: _plain(Fraction(potentials["c", j], scale))
                                                        for j in range(len(columns))}}}}


# -- frozen oracle (independent of every engine) ----------------------------------------------

def brute_force(req: dict) -> dict:
    """Every assignment, in exact integers; for oracle-sized problems only."""
    n, m = len(req["costs"]), len(req["columns"])
    if math.perm(m, n) > 50000:
        raise ValueError("brute-force assignment is for oracle-sized problems only")
    best = None
    for perm in itertools.permutations(range(m), n):
        if all(req["costs"][i][j] is not None for i, j in enumerate(perm)):
            total = sum(req["costs"][i][j] for i, j in enumerate(perm))
            if best is None or (total < best if req["sense"] == "min" else total > best):
                best = total
    if best is None:
        return {"status": "infeasible", "total": None}
    return {"status": "optimal", "total": _plain(Fraction(best, req["scale"]))}


FIXED_ASSIGNMENT = [
    ("textbook", {"costs": [[9, 2, 7, 8], [6, 4, 3, 7], [5, 8, 1, 8], [7, 6, 9, 4]]}),
    ("rectangular", {"costs": [[4, 1, 3], [2, 0, 5]]}),
    ("free-column-is-cheaper", {"costs": [[5, 1, 9], [1, 9, 9]]}),
    ("forbidden", {"costs": [[None, 3, 1], [2, None, 4], [3, 1, None]]}),
    ("no-full-assignment", {"costs": [[1, None, None], [2, None, None], [None, 5, 1]]}),
    ("row-with-no-column", {"costs": [[None, None], [1, 2]]}),
    ("maximize", {"costs": [[7, 3, 1], [2, 8, 4], [5, 6, 9]], "maximize": True}),
    ("maximize-forbidden", {"costs": [[None, 5], [3, 1]], "maximize": True}),
    ("negative", {"costs": [[-3, 2], [4, -1]]}),
    ("decimals", {"costs": [[0.5, 1.25, 2], [1.75, 0.125, 3.5]]}),
    ("ties", {"costs": [[1, 1], [1, 1]]}),
    ("single", {"costs": [[42]]}),
]


def oracle_assignment(seed: int) -> list[dict]:
    rng = random.Random(seed)
    cases = [{"name": name, "input": params} for name, params in FIXED_ASSIGNMENT]
    for index in range(8):
        n = rng.randint(1, 6)
        m = rng.randint(n, 7)
        value = (lambda r: r.randint(-5, 20)) if index % 3 else (lambda r: r.randint(0, 80) / 8)
        costs = [[None if rng.random() < 0.2 else value(rng) for _ in range(m)] for _ in range(n)]
        cases.append({"name": f"random{index}", "input": {"costs": costs, "maximize": index % 4 == 3}})
    for case in cases:
        case["expected"] = brute_force(normalize_assignment(case["input"]))
    return cases


def judge_assignment(answer: dict, expected: dict) -> bool:
    return answer["status"] == expected["status"] and answer.get("total") == expected["total"]


# -- scale probe and the simplest local implementation an engine must be compared with --------

def size(req: dict) -> dict:
    return {"rows": len(req["costs"]), "columns": len(req["columns"]), "allowed_pairs": len(_allowed(req))}


def probe_assignment(seed: int) -> dict:
    rng = random.Random(seed ^ 0x3C3C)
    return {"costs": [[rng.randint(0, 1000) for _ in range(MAX_SIDE)] for _ in range(MAX_SIDE)]}


def local_hungarian(req: dict) -> dict:
    """The O(n^2 m) Hungarian method in plain Python (minimization; every pair allowed)."""
    sign = 1 if req["sense"] == "min" else -1
    a = [[sign * c for c in row] for row in req["costs"]]
    n, m = len(a), len(a[0])
    u, v, p, way = [0] * (n + 1), [0] * (m + 1), [0] * (m + 1), [0] * (m + 1)
    for i in range(1, n + 1):
        p[0], j0 = i, 0
        minv, used = [math.inf] * (m + 1), [False] * (m + 1)
        while p[j0]:
            used[j0], i0, delta, j1 = True, p[j0], math.inf, 0
            for j in range(1, m + 1):
                if not used[j]:
                    cur = a[i0 - 1][j - 1] - u[i0] - v[j]
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
        while j0:
            j1 = way[j0]
            p[j0], j0 = p[j1], j1
    total = sum(req["costs"][p[j] - 1][j - 1] for j in range(1, m + 1) if p[j])
    return {"total": _plain(Fraction(total, req["scale"]))}
