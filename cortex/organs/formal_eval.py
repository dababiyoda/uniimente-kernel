"""Solver-independent evaluation of a formal model on a concrete assignment.

Directive section 7C: "Check the returned assignment independently against source
constraints." Both formal engines (Z3, OR-Tools CP-SAT) return assignments; this
module re-evaluates every source constraint, every declared bound and the
objective with plain Python arithmetic, so a solver bug, a mistranslation inside
an engine adapter or a forged proof artifact cannot pass by agreeing with itself.

Shared dependency, disclosed: the model is parsed by ``formal.Spec`` (the same
parser the engines use). A parser defect is therefore *not* caught here; the
reverse translation and the requester's witnesses remain the defence for that.

Integers are evaluated exactly. Reals use ``fractions.Fraction`` when the value
is supplied as an exact rational string, else float with a stated tolerance.
"""
from __future__ import annotations

from fractions import Fraction
from typing import Any, Mapping

TOLERANCE = 1e-9


class EvalError(ValueError):
    """The assignment cannot be evaluated (missing variable, wrong sort)."""


def _num(value: Any, sort: str):
    if isinstance(value, bool):
        raise EvalError("boolean where a number is required")
    if sort == "int":
        if isinstance(value, float) and not value.is_integer():
            raise EvalError(f"non-integral value {value!r} for an integer variable")
        return int(value)
    if isinstance(value, str):
        return Fraction(value)
    return Fraction(value) if isinstance(value, int) else value


def evaluate(node: Any, assignment: Mapping[str, Any], sorts: Mapping[str, str]):
    """Value of ``node`` under ``assignment``. Raises EvalError when undefined."""
    if isinstance(node, bool):
        return node
    if isinstance(node, (int, float)):
        return node
    if isinstance(node, str):
        if node not in assignment:
            raise EvalError(f"assignment lacks {node!r}")
        value = assignment[node]
        if sorts.get(node) == "bool":
            if not isinstance(value, bool):
                raise EvalError(f"{node!r} must be boolean")
            return value
        return _num(value, sorts.get(node, "real"))
    op, args = node[0], node[1:]
    if op == "and":
        return all(evaluate(a, assignment, sorts) for a in args)
    if op == "or":
        return any(evaluate(a, assignment, sorts) for a in args)
    if op == "not":
        return not evaluate(args[0], assignment, sorts)
    if op == "implies":
        return (not evaluate(args[0], assignment, sorts)) or evaluate(args[1], assignment, sorts)
    if op == "ite":
        return evaluate(args[1] if evaluate(args[0], assignment, sorts) else args[2], assignment, sorts)
    vals = [evaluate(a, assignment, sorts) for a in args]
    if op == "distinct":
        return len(set(vals)) == len(vals)
    if op == "+":
        return sum(vals[1:], vals[0])
    if op == "-":
        out = vals[0]
        for v in vals[1:]:
            out = out - v
        return out
    if op == "*":
        out = vals[0]
        for v in vals[1:]:
            out = out * v
        return out
    left, right = vals
    exact = all(isinstance(v, (int, Fraction)) for v in vals)
    if op == "=":
        return left == right if exact else abs(left - right) <= TOLERANCE
    if op == "!=":
        return left != right if exact else abs(left - right) > TOLERANCE
    if op == "<":
        return left < right
    if op == "<=":
        return left <= right if exact else left <= right + TOLERANCE
    if op == ">":
        return left > right
    if op == ">=":
        return left >= right if exact else left + TOLERANCE >= right
    raise EvalError(f"unknown operator {op!r}")


def check_assignment(spec, assignment: Mapping[str, Any]) -> dict:
    """Re-evaluate bounds and every source constraint. ``spec`` is a ``formal.Spec``."""
    violations, bound_violations = [], []
    try:
        missing = sorted(set(spec.variables) - set(assignment))
        if missing:
            return {"holds": False, "violated_constraints": [], "bound_violations": [],
                    "error": f"assignment omits {missing}"}
        for name, (lo, hi) in spec.bounds.items():
            v = _num(assignment[name], spec.variables[name])
            if (lo is not None and v < lo) or (hi is not None and v > hi):
                bound_violations.append(name)
        for c in spec.constraints:
            if evaluate(c["expr"], assignment, spec.variables) is not True:
                violations.append(c["id"])
    except (EvalError, ZeroDivisionError, TypeError, ValueError) as exc:
        return {"holds": False, "violated_constraints": violations, "bound_violations": bound_violations,
                "error": str(exc)}
    return {"holds": not violations and not bound_violations, "violated_constraints": violations,
            "bound_violations": bound_violations, "error": None,
            "method": "python exact re-evaluation of every source constraint (shares only the parser)"}


def objective_value(spec, assignment: Mapping[str, Any]):
    value = evaluate(spec.query["objective"], assignment, spec.variables)
    return int(value) if isinstance(value, int) or (isinstance(value, Fraction) and value.denominator == 1) \
        else float(value)
