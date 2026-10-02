"""Bounded GLOP adapter with a primal/dual certificate extracted from PR #143.

Lineage: dababiyoda/uniimente-kernel commit 7105a7cbd013edd6bce88b9500e2b4477635c912,
greg/cognition/linear.py, MIT (Copyright 2026 Alfonso Lopez). No engine-generated
code is executed. A native infeasibility report is unproven and abstains.
The numerical certificate uses exact Fraction checks with declared 1e-7 tolerance.
"""
from __future__ import annotations
from fractions import Fraction
import importlib.metadata
import math
import re
from .contracts import CognitionError, digest, integer, number

MAX_VARIABLES, MAX_CONSTRAINTS, MAX_COEFFICIENT = 32, 64, 1e9
TOLERANCE = Fraction(1, 10**7)
NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,31}$")
OPS = ("<=", ">=", "==")

class CertificateError(CognitionError):
    """An emitted candidate does not support its numerical optimality claim."""


def _invalid(why: str):
    return CognitionError(f"linear program invalid: {why}")

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

def _close(lhs: Fraction, rhs: Fraction, scale: Fraction) -> bool:
    return abs(lhs - rhs) <= TOLERANCE * (1 + abs(scale))

def certify_lp(req: dict, claim) -> dict:
    if not isinstance(claim, dict) or claim.get("status") not in ("optimal", "infeasible", "unbounded", "unknown"):
        raise CertificateError("the claim must carry a status")
    names = req["names"]
    if claim["status"] != "optimal":
        return {"certified": False, "status": claim["status"],
                "why": "the engine reports no optimum and gives no certificate; GREG cannot prove the claim",
                "certificate": None}
    def vector(key, size):
        values = claim.get(key)
        if not isinstance(values, list) or len(values) != size:
            raise CertificateError(f"{key} must have {size} entries")
        try:
            for value in values:
                number(value)
            return [Fraction(v) for v in values]
        except (TypeError, ValueError) as exc:
            raise CertificateError(f"{key} holds a non-number") from exc
    n = len(names)
    x, y_ub, y_eq = vector("x", n), vector("y_ub", len(req["b_ub"])), vector("y_eq", len(req["b_eq"]))
    z_l, z_u = vector("z_l", n), vector("z_u", n)
    F = lambda row: [Fraction(a) for a in row]  # noqa: E731
    c = F(req["c"])
    # primal feasibility
    for row, b, label in zip(req["a_ub"], req["b_ub"], req["labels_ub"]):
        lhs = sum(a * v for a, v in zip(F(row), x))
        if lhs > Fraction(b) + TOLERANCE * (1 + abs(Fraction(b))):
            raise CertificateError(f"constraint {label} is violated")
    for row, b, label in zip(req["a_eq"], req["b_eq"], req["labels_eq"]):
        if not _close(sum(a * v for a, v in zip(F(row), x)), Fraction(b), Fraction(b)):
            raise CertificateError(f"constraint {label} is violated")
    for name, v, lo, hi in zip(names, x, req["lower"], req["upper"]):
        if (lo is not None and v < Fraction(lo) - TOLERANCE * (1 + abs(Fraction(lo)))) or \
                (hi is not None and v > Fraction(hi) + TOLERANCE * (1 + abs(Fraction(hi)))):
            raise CertificateError(f"bound on {name} is violated")
    # dual feasibility: signs, multipliers only on finite bounds, stationarity
    # Directional signs are mathematical conditions. A tiny wrong-sign
    # multiplier can be amplified by a wide bound; tolerance cannot excuse it.
    if any(y > 0 for y in y_ub) or any(z < 0 for z in z_l) or any(z > 0 for z in z_u):
        raise CertificateError("a multiplier has the wrong sign")
    for name, lo, hi, zl, zu in zip(names, req["lower"], req["upper"], z_l, z_u):
        if (lo is None and abs(zl) > TOLERANCE) or (hi is None and abs(zu) > TOLERANCE):
            raise CertificateError(f"{name} carries a multiplier on an infinite bound")
    residuals = []
    for j, name in enumerate(names):
        column = sum(Fraction(row[j]) * y for row, y in zip(req["a_ub"], y_ub)) + \
            sum(Fraction(row[j]) * y for row, y in zip(req["a_eq"], y_eq)) + z_l[j] + z_u[j]
        if not _close(column, c[j], c[j]):
            raise CertificateError(f"the multipliers do not reproduce the objective coefficient of {name}")
        residuals.append(c[j] - column)
    primal = sum(cj * v for cj, v in zip(c, x))
    dual = sum(Fraction(b) * y for b, y in zip(req["b_ub"], y_ub)) + \
        sum(Fraction(b) * y for b, y in zip(req["b_eq"], y_eq)) + \
        sum(Fraction(lo) * z for lo, z in zip(req["lower"], z_l) if lo is not None) + \
        sum(Fraction(hi) * z for hi, z in zip(req["upper"], z_u) if hi is not None)
    # Convert approximate stationarity into a valid dual bound over the finite
    # source bounds, rather than multiplying an unchecked residual by x. This
    # detects near-zero coefficient errors amplified by a large problem domain.
    adjustment = Fraction(0)
    for name, residual, lo, hi in zip(names, residuals, req["lower"], req["upper"]):
        if residual:
            if lo is None or hi is None:
                raise CertificateError(f"stationarity residual for {name} requires finite bounds")
            adjustment += min(residual * Fraction(lo), residual * Fraction(hi))
    dual += adjustment
    if not _close(primal, dual, primal):
        raise CertificateError("primal and rigorously corrected dual objectives differ: optimality is not shown")
    sign = 1 if req["sense"] == "min" else -1
    return {"certified": True, "status": "optimal", "sense": req["sense"],
            "objective": float(sign * primal), "values": {name: float(v) for name, v in zip(names, x)},
            "dual_bound": float(sign * dual),
            "binding": sorted([label for label, y in zip(req["labels_ub"], y_ub) if y != 0]
                              + [label for label, y in zip(req["labels_eq"], y_eq) if y != 0]),
            # change in the stated objective per unit increase of the stated right-hand side
            "shadow_prices": {**{label: float(sign * flip * y) for label, y, flip in
                                 zip(req["labels_ub"], y_ub, req["flips_ub"]) if y != 0},
                              **{label: float(sign * y) for label, y in zip(req["labels_eq"], y_eq) if y != 0}},
            "certificate": {"kind": "bounded primal feasibility and residual-corrected dual bound", "gap": float(primal - dual),
                            "stationarity_bound_adjustment": float(adjustment),
                            "tolerance": "relative 1e-7 (engine floating point)", "arithmetic": "exact fractions"}}


def canonical_request(data):
    allowed = {"variables", "constraints", "objective", "solver_budget_seconds"}
    if not isinstance(data, dict) or set(data) - allowed or not isinstance(data.get("variables"), dict):
        raise CognitionError("bounded declarative LP variable map required")
    variables = []
    for name, bounds in data["variables"].items():
        if not isinstance(bounds, list) or len(bounds) != 2 or any(value is None for value in bounds):
            raise CognitionError("this LP method requires two finite bounds per variable")
        variables.append({"name": name, "lower": bounds[0], "upper": bounds[1]})
    req = normalize_lp({"variables": variables, "constraints": data.get("constraints", []), "objective": data.get("objective")})
    if set(data["objective"]) - {"sense", "coefficients"}:
        raise CognitionError("unknown LP objective clause")
    # No ignored constraint clauses or automatic model-generated expression execution.
    for constraint in data.get("constraints", []):
        if set(constraint) - {"coefficients", "op", "rhs", "name"}:
            raise CognitionError("unknown LP constraint clause")
        if "name" in constraint and (not isinstance(constraint["name"], str) or not 1 <= len(constraint["name"]) <= 40):
            raise CognitionError("LP constraint name must be 1-40 characters")
    if len(set(req["labels_ub"] + req["labels_eq"])) != len(req["labels_ub"] + req["labels_eq"]):
        raise CognitionError("LP constraint labels must be unique")
    return req


def solve(data, geometry):
    from ortools.linear_solver import pywraplp
    from .solvers import result
    req = canonical_request(data)
    count = len(req["names"])
    work = count * (len(req["a_ub"]) + len(req["a_eq"]) + count)
    ceiling = integer(geometry["compute_limit"], low=1, high=100000)
    if work > ceiling:
        raise CognitionError("BUDGET_EXHAUSTED: LP model exceeds the declared compute ceiling")
    seconds = min(number(geometry["latency_limit"], low=.001, high=30) * .8,
                  number(data.get("solver_budget_seconds", 30), low=0, high=30))
    solver = pywraplp.Solver.CreateSolver("GLOP")
    if solver is None:
        raise CognitionError("CAPABILITY_UNAVAILABLE: installed GLOP engine unavailable")
    solver.SetTimeLimit(max(1, int(seconds * 1000)))
    if not solver.SetSolverSpecificParametersAsString(f"max_number_of_iterations: {ceiling}"):
        raise CognitionError("installed GLOP rejected its iteration ceiling")
    xs = [solver.NumVar(lo, hi, name) for name, lo, hi in zip(req["names"], req["lower"], req["upper"])]
    upper, equal = [], []
    for rows, rhs_values, labels, target, equality in ((req["a_ub"], req["b_ub"], req["labels_ub"], upper, False),
                                                     (req["a_eq"], req["b_eq"], req["labels_eq"], equal, True)):
        for row, rhs, label in zip(rows, rhs_values, labels):
            constraint = solver.RowConstraint(rhs if equality else -solver.infinity(), rhs, label)
            for coefficient, variable in zip(row, xs):
                constraint.SetCoefficient(variable, coefficient)
            target.append(constraint)
    objective = solver.Objective()
    for coefficient, variable in zip(req["c"], xs):
        objective.SetCoefficient(variable, coefficient)
    objective.SetMinimization()
    native = solver.NOT_SOLVED if seconds == 0 else solver.Solve()
    statuses = {solver.OPTIMAL: "OPTIMAL", solver.FEASIBLE: "FEASIBLE", solver.INFEASIBLE: "INFEASIBLE",
                solver.UNBOUNDED: "UNBOUNDED", solver.ABNORMAL: "ABNORMAL", solver.MODEL_INVALID: "MODEL_INVALID", solver.NOT_SOLVED: "NOT_SOLVED"}
    status = statuses[native]
    claim = {"status": "optimal" if native == solver.OPTIMAL else "infeasible" if native == solver.INFEASIBLE else "unbounded" if native == solver.UNBOUNDED else "unknown"}
    if native == solver.OPTIMAL:
        costs = [v.reduced_cost() for v in xs]
        claim.update({"x": [v.solution_value() for v in xs], "y_ub": [c.dual_value() for c in upper], "y_eq": [c.dual_value() for c in equal],
                      "z_l": [max(value, 0.) for value in costs], "z_u": [min(value, 0.) for value in costs]})
    feasible = native == solver.OPTIMAL
    sign = 1 if req["sense"] == "min" else -1
    # Native multipliers provide a candidate bound, checked separately by the
    # Fraction certificate verifier. No bound is claimed for non-optimal states.
    bound = gap = None
    if feasible:
        nominal = (sum(b * y for b, y in zip(req["b_ub"], claim["y_ub"])) +
                        sum(b * y for b, y in zip(req["b_eq"], claim["y_eq"])) +
                        sum(lo * z for lo, z in zip(req["lower"], claim["z_l"])) +
                        sum(hi * z for hi, z in zip(req["upper"], claim["z_u"])))
        residual = [coefficient - (sum(row[j] * y for row, y in zip(req["a_ub"], claim["y_ub"])) +
                                   sum(row[j] * y for row, y in zip(req["a_eq"], claim["y_eq"])) + claim["z_l"][j] + claim["z_u"][j])
                    for j, coefficient in enumerate(req["c"])]
        bound = sign * (nominal + sum(min(r * lo, r * hi) for r, lo, hi in zip(residual, req["lower"], req["upper"])))
        gap = abs(sign * objective.Value() - bound)
    output = {"solver_status": status, "solution": {name: v.solution_value() for name, v in zip(req["names"], xs)} if feasible else {},
              "objective_direction": req["sense"], "feasible": feasible,
              "objective_value": sign * objective.Value() if feasible else None}
    proof = {"model": req, "input_digest": digest(data), "objective": data["objective"], "constraints": data.get("constraints", []),
             "claim": claim, "solver_status": status, "solver_version": importlib.metadata.version("ortools"),
             "engine": "OR-Tools GLOP", "limits": {"seconds": seconds, "iteration_ceiling": ceiling, "certificate_tolerance": "relative 1e-7"},
             "bound": bound, "gap": gap, "infeasibility_certificate": None}
    return result(output, proof, status="ANSWER" if native == solver.OPTIMAL else "UNKNOWN" if native in (solver.NOT_SOLVED, solver.FEASIBLE) else "ABSTAIN",
                  formal="VALID_WITHIN_DECLARED_TOLERANCE" if native == solver.OPTIMAL else "UNKNOWN",
                  missing=() if native == solver.OPTIMAL else ("native LP status has no independently checked optimum or infeasibility certificate",))
