"""Linear programs answered by open-source engines and accepted only on GREG's duality certificate.

    lp.optimize   maximize or minimize a linear objective under linear constraints and bounds

The engines (SciPy's HiGHS, OR-Tools GLOP) are untrusted. Each GREG runner turns its engine's
output into one canonical form for ``min c.x`` subject to ``A_ub x <= b_ub``, ``A_eq x = b_eq``
and ``l <= x <= u``: a primal point x and multipliers y_ub <= 0, y_eq, z_l >= 0, z_u <= 0. GREG
then checks, sharing no code with either engine:

    primal feasibility     every constraint and bound holds
    dual feasibility       c = A_ub' y_ub + A_eq' y_eq + z_l + z_u, with the signs above
    zero gap               c.x equals b_ub.y_ub + b_eq.y_eq + l.z_l + u.z_u

Weak duality makes the dual objective a lower bound on every feasible point, so a feasible x that
meets it is optimal. Engines work in floating point, so each test allows a relative 1e-7 (the
engines' own default feasibility tolerance); arithmetic in the check itself is exact.
An engine that reports "infeasible" gives no Farkas certificate through these interfaces, so GREG
builds its own: the elastic program (one nonnegative slack per limit, minimize total slack) is
solved by the same engine and its optimum is certified by the same duality check. A certified
positive minimum proves that every point within the bounds breaks the limits by at least that
much, and its nonzero prices name the limits in conflict. A certified zero minimum refutes the
engine. An engine's "unbounded" is proved the same way, with two direct checks: the elastic
program yields a point that meets every limit, and a direction search (inside a unit box) yields a
direction that keeps meeting them while the objective improves. Either missing refutes the engine.

The qualification oracle is GREG's: vertex enumeration in exact fractions over bounded problems.
"""
from __future__ import annotations

from fractions import Fraction
import itertools
import math
import random
import re

from greg.capabilities import CapabilityError

MAX_VARIABLES, MAX_CONSTRAINTS, MAX_COEFFICIENT = 500, 2000, 1e9
MAX_ELASTIC_CELLS = 1_000_000          # dense elastic program: (variables + slacks) x limits
TOLERANCE = Fraction(1, 10**7)
NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,31}$")
OPS = ("<=", ">=", "==")


class CertificateError(Exception):
    """The engine's claim does not prove itself."""


def _invalid(why: str):
    return CapabilityError(f"linear program invalid: {why}")


def _num(value, what: str, *, allow_inf: bool = False):
    if value is None and allow_inf:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise _invalid(f"{what} must be a finite number")
    if abs(value) > MAX_COEFFICIENT:
        raise _invalid(f"{what} exceeds 1e9 in magnitude")
    return value


def normalize_lp(params: dict) -> dict:
    """Validate and put the program in the canonical min form every runner and the certificate share."""
    if not isinstance(params, dict):
        raise _invalid("parameters must be an object")
    variables = params.get("variables")
    if not isinstance(variables, list) or not 1 <= len(variables) <= MAX_VARIABLES:
        raise _invalid(f"1-{MAX_VARIABLES} variables required")
    names, lower, upper = [], [], []
    for v in variables:
        if not isinstance(v, dict) or not isinstance(v.get("name"), str) or not NAME.match(v["name"]):
            raise _invalid(f"variable {v!r} needs a name of letters, digits and _")
        if v["name"] in names:
            raise _invalid(f"variable {v['name']} repeats")
        lo, hi = _num(v.get("lower"), "lower bound", allow_inf=True), _num(v.get("upper"), "upper bound", allow_inf=True)
        if lo is not None and hi is not None and lo > hi:
            raise _invalid(f"{v['name']}: lower bound above upper bound")
        names.append(v["name"])
        lower.append(lo)
        upper.append(hi)
    objective = params.get("objective")
    if not isinstance(objective, dict) or objective.get("sense") not in ("min", "max") \
            or not isinstance(objective.get("coefficients"), dict):
        raise _invalid("objective needs sense min or max and coefficients")
    index = {n: i for i, n in enumerate(names)}

    def row(coefficients, what):
        if not isinstance(coefficients, dict) or not set(coefficients) <= set(index):
            raise _invalid(f"{what} names an unknown variable")
        out = [0] * len(names)
        for n, a in coefficients.items():
            out[index[n]] = _num(a, f"{what} coefficient for {n}")
        return out

    sign = 1 if objective["sense"] == "min" else -1
    c = [sign * a for a in row(objective["coefficients"], "objective")]
    constraints = params.get("constraints", [])
    if not isinstance(constraints, list) or len(constraints) > MAX_CONSTRAINTS:
        raise _invalid(f"at most {MAX_CONSTRAINTS} constraints")
    a_ub, b_ub, a_eq, b_eq, labels_ub, labels_eq, flips = [], [], [], [], [], [], []
    for k, con in enumerate(constraints):
        if not isinstance(con, dict) or con.get("op") not in OPS:
            raise _invalid(f"constraint {k} needs op <=, >= or ==")
        label = str(con.get("name") or f"c{k + 1}")[:40]
        r, rhs = row(con.get("coefficients"), f"constraint {label}"), _num(con.get("rhs"), f"{label} right-hand side")
        if con["op"] == "<=":
            a_ub.append(r), b_ub.append(rhs), labels_ub.append(label), flips.append(1)
        elif con["op"] == ">=":
            a_ub.append([-a for a in r]), b_ub.append(-rhs), labels_ub.append(label), flips.append(-1)
        else:
            a_eq.append(r), b_eq.append(rhs), labels_eq.append(label)
    return {"names": names, "sense": objective["sense"], "c": c, "a_ub": a_ub, "b_ub": b_ub, "a_eq": a_eq,
            "b_eq": b_eq, "lower": lower, "upper": upper, "labels_ub": labels_ub, "labels_eq": labels_eq,
            "flips_ub": flips}


RUNNERS = {
    "scipy.lp": r'''
def solve(req):
    n = len(req["names"])
    result = MODULE.linprog(c=req["c"], A_ub=req["a_ub"] or None, b_ub=req["b_ub"] or None,
                            A_eq=req["a_eq"] or None, b_eq=req["b_eq"] or None,
                            bounds=list(zip(req["lower"], req["upper"])), method="highs")
    status = {0: "optimal", 2: "infeasible", 3: "unbounded"}.get(result.status, "unknown")
    if status != "optimal":
        return {"status": status, "message": str(result.message)[:200]}
    return {"status": "optimal", "x": [float(v) for v in result.x],
            "y_ub": [float(v) for v in result.ineqlin.marginals] if req["a_ub"] else [],
            "y_eq": [float(v) for v in result.eqlin.marginals] if req["a_eq"] else [],
            "z_l": [float(v) for v in result.lower.marginals], "z_u": [float(v) for v in result.upper.marginals]}
''',
    "ortools.lp": r'''
def solve(req):
    s = MODULE.Solver.CreateSolver("GLOP")
    inf = s.infinity()
    xs = [s.NumVar(-inf if lo is None else lo, inf if hi is None else hi, name)
          for name, lo, hi in zip(req["names"], req["lower"], req["upper"])]
    ub = [s.Add(sum(a * x for a, x in zip(row, xs) if a) <= b) for row, b in zip(req["a_ub"], req["b_ub"])]
    eq = [s.Add(sum(a * x for a, x in zip(row, xs) if a) == b) for row, b in zip(req["a_eq"], req["b_eq"])]
    s.Minimize(sum(c * x for c, x in zip(req["c"], xs) if c))
    status = s.Solve()
    if status != s.OPTIMAL:
        return {"status": {s.INFEASIBLE: "infeasible", s.UNBOUNDED: "unbounded"}.get(status, "unknown")}
    # GLOP reports one reduced cost per variable: positive at a lower bound, negative at an upper one.
    costs = [x.reduced_cost() for x in xs]
    return {"status": "optimal", "x": [x.solution_value() for x in xs],
            "y_ub": [c.dual_value() for c in ub], "y_eq": [c.dual_value() for c in eq],
            "z_l": [max(d, 0.0) for d in costs], "z_u": [min(d, 0.0) for d in costs]}
''',
}


def _close(lhs: Fraction, rhs: Fraction, scale: Fraction) -> bool:
    return abs(lhs - rhs) <= TOLERANCE * (1 + abs(scale))


def check_primal(req: dict, x: list) -> None:
    """Every limit and bound holds at x (relative 1e-7), checked in exact arithmetic."""
    F = lambda row: [Fraction(a) for a in row]  # noqa: E731
    for row, b, label in zip(req["a_ub"], req["b_ub"], req["labels_ub"]):
        if sum(a * v for a, v in zip(F(row), x)) > Fraction(b) + TOLERANCE * (1 + abs(Fraction(b))):
            raise CertificateError(f"constraint {label} is violated")
    for row, b, label in zip(req["a_eq"], req["b_eq"], req["labels_eq"]):
        if not _close(sum(a * v for a, v in zip(F(row), x)), Fraction(b), Fraction(b)):
            raise CertificateError(f"constraint {label} is violated")
    for name, v, lo, hi in zip(req["names"], x, req["lower"], req["upper"]):
        if (lo is not None and v < Fraction(lo) - TOLERANCE * (1 + abs(Fraction(lo)))) or \
                (hi is not None and v > Fraction(hi) + TOLERANCE * (1 + abs(Fraction(hi)))):
            raise CertificateError(f"bound on {name} is violated")


def certify_lp(req: dict, claim) -> dict:
    if not isinstance(claim, dict) or claim.get("status") not in ("optimal", "infeasible", "unbounded", "unknown"):
        raise CertificateError("the claim must carry a status")
    names = req["names"]
    if claim["status"] in ("infeasible", "unbounded"):
        # Engines blur these two (GLOP reports an unbounded program as infeasible); GREG decides by proof.
        program = elastic(req)
        follow_up = None if program is None else [program, ray(req)]
        what = "no feasible plan" if claim["status"] == "infeasible" else "no limit to the objective"
        return {"certified": False, "status": claim["status"], "follow_up": follow_up, "certificate": None,
                "why": f"the engine reports {what}; GREG proves or refutes it with follow-up solves"
                       if follow_up else f"the engine reports {what}; the program is too large for GREG to prove it "
                                         "here"}
    if claim["status"] != "optimal":
        return {"certified": False, "status": claim["status"],
                "why": "the engine reports no optimum and gives no certificate; GREG cannot prove the claim",
                "certificate": None}
    def vector(key, size):
        values = claim.get(key)
        if not isinstance(values, list) or len(values) != size:
            raise CertificateError(f"{key} must have {size} entries")
        try:
            return [Fraction(v) for v in values]
        except (TypeError, ValueError) as exc:
            raise CertificateError(f"{key} holds a non-number") from exc
    n = len(names)
    x, y_ub, y_eq = vector("x", n), vector("y_ub", len(req["b_ub"])), vector("y_eq", len(req["b_eq"]))
    z_l, z_u = vector("z_l", n), vector("z_u", n)
    c = [Fraction(a) for a in req["c"]]
    check_primal(req, x)
    # dual feasibility: signs, multipliers only on finite bounds, stationarity
    if any(y > TOLERANCE for y in y_ub) or any(z < -TOLERANCE for z in z_l) or any(z > TOLERANCE for z in z_u):
        raise CertificateError("a multiplier has the wrong sign")
    for name, lo, hi, zl, zu in zip(names, req["lower"], req["upper"], z_l, z_u):
        if (lo is None and abs(zl) > TOLERANCE) or (hi is None and abs(zu) > TOLERANCE):
            raise CertificateError(f"{name} carries a multiplier on an infinite bound")
    for j, name in enumerate(names):
        column = sum(Fraction(row[j]) * y for row, y in zip(req["a_ub"], y_ub)) + \
            sum(Fraction(row[j]) * y for row, y in zip(req["a_eq"], y_eq)) + z_l[j] + z_u[j]
        if not _close(column, c[j], c[j]):
            raise CertificateError(f"the multipliers do not reproduce the objective coefficient of {name}")
    primal = sum(cj * v for cj, v in zip(c, x))
    dual = sum(Fraction(b) * y for b, y in zip(req["b_ub"], y_ub)) + \
        sum(Fraction(b) * y for b, y in zip(req["b_eq"], y_eq)) + \
        sum(Fraction(lo) * z for lo, z in zip(req["lower"], z_l) if lo is not None) + \
        sum(Fraction(hi) * z for hi, z in zip(req["upper"], z_u) if hi is not None)
    if not _close(primal, dual, primal):
        raise CertificateError("primal and dual objectives differ: optimality is not shown")
    sign = 1 if req["sense"] == "min" else -1
    return {"certified": True, "status": "optimal", "sense": req["sense"],
            "objective": float(sign * primal), "values": {name: float(v) for name, v in zip(names, x)},
            "binding": sorted([label for label, y in zip(req["labels_ub"], y_ub) if y != 0]
                              + [label for label, y in zip(req["labels_eq"], y_eq) if y != 0]),
            # change in the stated objective per unit increase of the stated right-hand side
            "shadow_prices": {**{label: float(sign * flip * y) for label, y, flip in
                                 zip(req["labels_ub"], y_ub, req["flips_ub"]) if y != 0},
                              **{label: float(sign * y) for label, y in zip(req["labels_eq"], y_eq) if y != 0}},
            "certificate": {"kind": "primal and dual feasibility with zero duality gap", "gap": float(primal - dual),
                            "tolerance": "relative 1e-7 (engine floating point)", "arithmetic": "exact fractions"}}


def elastic(req: dict) -> dict | None:
    """The same limits with one nonnegative slack each; minimizing total slack measures infeasibility."""
    n, mu, me = len(req["names"]), len(req["b_ub"]), len(req["b_eq"])
    if not mu + me or (n + mu + 2 * me) * (mu + me) > MAX_ELASTIC_CELLS:
        return None

    def unit(k, size, value):
        return [value if j == k else 0 for j in range(size)]
    a_ub = [list(row) + unit(i, mu, -1) + [0] * (2 * me) for i, row in enumerate(req["a_ub"])]
    a_eq = [list(row) + [0] * mu + unit(i, me, -1) + unit(i, me, 1) for i, row in enumerate(req["a_eq"])]
    names = list(req["names"]) + [f"over_{i}" for i in range(mu)] + [f"above_{i}" for i in range(me)] + \
        [f"below_{i}" for i in range(me)]
    return {"elastic": True, "names": names, "sense": "min", "c": [0] * n + [1] * (mu + 2 * me),
            "a_ub": a_ub, "b_ub": list(req["b_ub"]), "a_eq": a_eq, "b_eq": list(req["b_eq"]),
            "lower": list(req["lower"]) + [0] * (mu + 2 * me), "upper": list(req["upper"]) + [None] * (mu + 2 * me),
            "labels_ub": req["labels_ub"], "labels_eq": req["labels_eq"], "flips_ub": req["flips_ub"]}


def ray(req: dict) -> dict:
    """Search, inside a unit box, a direction that keeps every limit and bound and improves the objective."""
    return {"ray": True, "names": list(req["names"]), "sense": "min", "c": list(req["c"]),
            "a_ub": [list(r) for r in req["a_ub"]], "b_ub": [0] * len(req["b_ub"]),
            "a_eq": [list(r) for r in req["a_eq"]], "b_eq": [0] * len(req["b_eq"]),
            "lower": [-1 if lo is None else 0 for lo in req["lower"]],
            "upper": [1 if hi is None else 0 for hi in req["upper"]],
            "labels_ub": req["labels_ub"], "labels_eq": req["labels_eq"], "flips_ub": req["flips_ub"]}


def _least_violation(req: dict, program: dict, claim) -> tuple[dict, float, float]:
    proof = certify_lp(program, claim)
    if not proof["certified"]:
        raise CertificateError("the elastic program has no certified optimum")
    scale = 1 + max([abs(b) for b in req["b_ub"] + req["b_eq"]] or [0])
    return proof, proof["objective"], 1e-6 * scale


def follow_up_lp(req: dict, answer: dict, claims: list) -> dict:
    """Decide by proof what an engine's "no optimum" means: no feasible plan, or no limit to the objective.

    The engine's own label is kept as ``engine_said``; only GREG's proof sets ``status``."""
    proof, least, threshold = _least_violation(req, answer["follow_up"][0], claims[0])
    if least <= threshold:                                   # a plan meets every limit
        found = _unbounded(req, proof, claims[1])
        if found is None:
            raise CertificateError(f"the engine said {answer['status']}, but a plan meets every limit and the "
                                   "objective is bounded")
        return {**found, "engine_said": answer["status"]}
    prices = claims[0]["y_ub"] + claims[0]["y_eq"]
    labels = req["labels_ub"] + req["labels_eq"]
    return {"certified": True, "status": "infeasible", "sense": req["sense"], "engine_said": answer["status"],
            "least_total_violation": least,
            "conflicting": sorted(label for label, y in zip(labels, prices) if abs(y) > 1e-9),
            "closest_values": {name: proof["values"][name] for name in req["names"]},
            "certificate": {"kind": "elastic program optimum certified by duality: every point within the bounds "
                                    "breaks the limits by at least the least total violation",
                            "gap": proof["certificate"]["gap"], "tolerance": proof["certificate"]["tolerance"],
                            "arithmetic": "exact fractions"}}


def _unbounded(req: dict, proof: dict, direction_claim) -> dict | None:
    """A proof of no limit, or None when the direction search shows the objective is bounded."""
    point = [Fraction(proof["values"][name]) for name in req["names"]]
    check_primal(req, point)                              # a plan that meets every limit
    if not isinstance(direction_claim, dict) or direction_claim.get("status") != "optimal" \
            or not isinstance(direction_claim.get("x"), list) or len(direction_claim["x"]) != len(req["names"]):
        raise CertificateError("the direction search returned no direction")
    try:
        d = [Fraction(v) for v in direction_claim["x"]]
    except (TypeError, ValueError) as exc:
        raise CertificateError("the direction holds a non-number") from exc
    scale = Fraction(1) + max([abs(Fraction(a)) for row in req["a_ub"] + req["a_eq"] for a in row] or [0])
    for row, label in zip(req["a_ub"], req["labels_ub"]):
        if sum(Fraction(a) * v for a, v in zip(row, d)) > TOLERANCE * scale:
            raise CertificateError(f"moving along the direction breaks {label}")
    for row, label in zip(req["a_eq"], req["labels_eq"]):
        if abs(sum(Fraction(a) * v for a, v in zip(row, d))) > TOLERANCE * scale:
            raise CertificateError(f"moving along the direction breaks {label}")
    for name, v, lo, hi in zip(req["names"], d, req["lower"], req["upper"]):
        if (lo is not None and v < -TOLERANCE) or (hi is not None and v > TOLERANCE):
            raise CertificateError(f"moving along the direction breaks the bound on {name}")
    rate = sum(Fraction(cj) * v for cj, v in zip(req["c"], d))
    if rate >= -TOLERANCE * (1 + max([abs(Fraction(cj)) for cj in req["c"]] or [0])):
        return None                                        # no improving direction: the objective is bounded
    sign = 1 if req["sense"] == "min" else -1
    return {"certified": True, "status": "unbounded", "sense": req["sense"],
            "feasible_point": {name: float(v) for name, v in zip(req["names"], point)},
            "improving_direction": {name: float(v) for name, v in zip(req["names"], d)},
            "objective_change_per_step": float(sign * rate),
            "certificate": {"kind": "a point meeting every limit plus a direction that keeps meeting them while the "
                                    "objective improves; both checked directly",
                            "tolerance": "relative 1e-7 (engine floating point)", "arithmetic": "exact fractions"}}


# -- GREG's oracle: vertex enumeration in exact fractions (bounded problems only) -------------

def _solve_exact(rows, rhs):
    """Gaussian elimination in fractions; None if singular."""
    n = len(rows)
    m = [list(map(Fraction, r)) + [Fraction(b)] for r, b in zip(rows, rhs)]
    for col in range(n):
        pivot = next((r for r in range(col, n) if m[r][col] != 0), None)
        if pivot is None:
            return None
        m[col], m[pivot] = m[pivot], m[col]
        for r in range(n):
            if r != col and m[r][col] != 0:
                f = m[r][col] / m[col][col]
                m[r] = [a - f * b for a, b in zip(m[r], m[col])]
    return [m[i][n] / m[i][i] for i in range(n)]


def vertex_enumeration(req: dict) -> dict:
    """Exact optimum of a bounded program by trying every basis; for oracle-sized programs only."""
    n = len(req["names"])
    if n > 4 or any(v is None for v in req["lower"] + req["upper"]):
        raise ValueError("vertex enumeration is for small, fully bounded programs")
    planes = [(row, b, "le") for row, b in zip(req["a_ub"], req["b_ub"])] + \
        [(row, b, "eq") for row, b in zip(req["a_eq"], req["b_eq"])]
    for j in range(n):
        unit = [1 if k == j else 0 for k in range(n)]
        planes += [(unit, req["lower"][j], "lo"), (unit, req["upper"][j], "up")]
    eqs = [p for p in planes if p[2] == "eq"]
    best = None
    for chosen in itertools.combinations(range(len(planes)), n):
        if not all(p in [planes[i] for i in chosen] for p in eqs):
            continue
        point = _solve_exact([planes[i][0] for i in chosen], [planes[i][1] for i in chosen])
        if point is None:
            continue
        ok = all(sum(Fraction(a) * v for a, v in zip(row, point)) <= Fraction(b) for row, b in
                 zip(req["a_ub"], req["b_ub"])) and \
            all(sum(Fraction(a) * v for a, v in zip(row, point)) == Fraction(b) for row, b in
                zip(req["a_eq"], req["b_eq"])) and \
            all(Fraction(lo) <= v <= Fraction(hi) for v, lo, hi in zip(point, req["lower"], req["upper"]))
        if ok:
            value = sum(Fraction(c) * v for c, v in zip(req["c"], point))
            best = value if best is None else min(best, value)
    if best is None:
        return {"status": "infeasible"}
    return {"status": "optimal", "objective": (1 if req["sense"] == "min" else -1) * best}


FIXED_LP = [
    ("textbook-max", {"variables": [{"name": "x", "lower": 0, "upper": 3}, {"name": "y", "lower": 0, "upper": 10}],
                      "objective": {"sense": "max", "coefficients": {"x": 3, "y": 2}},
                      "constraints": [{"coefficients": {"x": 1, "y": 1}, "op": "<=", "rhs": 4},
                                      {"coefficients": {"x": 1, "y": 3}, "op": "<=", "rhs": 6}]}),
    ("equality-min", {"variables": [{"name": "a", "lower": 0, "upper": 10}, {"name": "b", "lower": 0, "upper": 10}],
                      "objective": {"sense": "min", "coefficients": {"a": 2, "b": 3}},
                      "constraints": [{"coefficients": {"a": 1, "b": 1}, "op": "==", "rhs": 5},
                                      {"coefficients": {"a": 1}, "op": "<=", "rhs": 3}]}),
    ("greater-equal", {"variables": [{"name": "p", "lower": 0, "upper": 8}, {"name": "q", "lower": 1, "upper": 8}],
                       "objective": {"sense": "min", "coefficients": {"p": 1, "q": 1}},
                       "constraints": [{"coefficients": {"p": 2, "q": 1}, "op": ">=", "rhs": 6}]}),
    ("fractional-optimum", {"variables": [{"name": "x", "lower": 0, "upper": 5}, {"name": "y", "lower": 0, "upper": 5}],
                            "objective": {"sense": "max", "coefficients": {"x": 1, "y": 1}},
                            "constraints": [{"coefficients": {"x": 3, "y": 1}, "op": "<=", "rhs": 7},
                                            {"coefficients": {"x": 1, "y": 3}, "op": "<=", "rhs": 7}]}),
    ("negative-bounds", {"variables": [{"name": "u", "lower": -4, "upper": 2}],
                         "objective": {"sense": "min", "coefficients": {"u": 1}}, "constraints": []}),
    ("infeasible", {"variables": [{"name": "x", "lower": 0, "upper": 1}],
                    "objective": {"sense": "max", "coefficients": {"x": 1}},
                    "constraints": [{"coefficients": {"x": 1}, "op": ">=", "rhs": 2}]}),
    ("infeasible-equality", {"variables": [{"name": "a", "lower": 0, "upper": 4}, {"name": "b", "lower": 0, "upper": 4}],
                             "objective": {"sense": "min", "coefficients": {"a": 1, "b": 1}},
                             "constraints": [{"coefficients": {"a": 1, "b": 1}, "op": "==", "rhs": 3},
                                             {"coefficients": {"a": 1, "b": 1}, "op": ">=", "rhs": 5}]}),
]


# Programs vertex enumeration cannot judge (unbounded feasible region), with their stated answer.
FIXED_LP_STATED = [
    ("unbounded-ray", {"variables": [{"name": "x", "lower": 0, "upper": None}, {"name": "y", "lower": 0, "upper": None}],
                       "objective": {"sense": "max", "coefficients": {"x": 1, "y": 1}},
                       "constraints": [{"coefficients": {"x": 1, "y": -1}, "op": "<=", "rhs": 1}]},
     {"status": "unbounded"}),
]


def oracle_lp(seed: int) -> list[dict]:
    rng = random.Random(seed)
    cases = [{"name": name, "input": params} for name, params in FIXED_LP]
    for index in range(8):
        n = rng.randint(1, 3)
        names = [f"v{i}" for i in range(n)]
        variables = []
        for name in names:
            lo = rng.randint(-3, 2)
            variables.append({"name": name, "lower": lo, "upper": lo + rng.randint(0, 6)})
        constraints = [{"coefficients": {nm: rng.randint(-4, 4) for nm in names}, "op": rng.choice(OPS[:2]),
                        "rhs": rng.randint(-6, 12)} for _ in range(rng.randint(0, 4))]
        if index % 3 == 0 and n > 1:
            constraints.append({"coefficients": {names[0]: 1, names[1]: 1}, "op": "==", "rhs": rng.randint(-2, 6)})
        cases.append({"name": f"random{index}", "input": {
            "variables": variables, "objective": {"sense": rng.choice(["min", "max"]),
                                                  "coefficients": {nm: rng.randint(-5, 5) for nm in names}},
            "constraints": constraints}})
    for case in cases:
        case["expected"] = vertex_enumeration(normalize_lp(case["input"]))
    return cases + [{"name": name, "input": params, "expected": expected} for name, params, expected in FIXED_LP_STATED]


def judge_lp(answer: dict, expected: dict) -> bool:
    if expected["status"] != "optimal":
        return answer["status"] == expected["status"] and answer["certified"] is True
    return answer["certified"] and math.isclose(answer["objective"], float(expected["objective"]),
                                                rel_tol=1e-7, abs_tol=1e-7)


def probe_lp(seed: int) -> dict:
    """A transport problem at the size limit: 20 sources x 25 sinks = 500 variables, 45 constraints."""
    rng = random.Random(seed ^ 0x1F1F)
    sources, sinks = [f"s{i}" for i in range(20)], [f"t{j}" for j in range(25)]
    demand = {t: rng.randint(5, 30) for t in sinks}
    total = sum(demand.values())
    supply = {s: total // len(sources) + 1 + rng.randint(0, 10) for s in sources}
    variables = [{"name": f"{s}_{t}", "lower": 0, "upper": None} for s in sources for t in sinks]
    constraints = [{"name": f"supply_{s}", "coefficients": {f"{s}_{t}": 1 for t in sinks}, "op": "<=", "rhs": supply[s]}
                   for s in sources]
    constraints += [{"name": f"demand_{t}", "coefficients": {f"{s}_{t}": 1 for s in sources}, "op": ">=",
                     "rhs": demand[t]} for t in sinks]
    return {"variables": variables, "objective": {"sense": "min", "coefficients": {
        f"{s}_{t}": rng.randint(1, 40) for s in sources for t in sinks}}, "constraints": constraints}


def size(req: dict) -> dict:
    return {"variables": len(req["names"]), "constraints": len(req["b_ub"]) + len(req["b_eq"])}
