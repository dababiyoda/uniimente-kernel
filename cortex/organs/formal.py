"""Formal organ: an actual solver against an inspectable model (build prompt items 5, 7).

Pipeline, preserved in order and recorded in the proof artifact:

    original requirement -> structured model -> reverse translation
      -> discrepancy check -> counterexample search -> solver result

* Reverse translation renders the structured model back to text so a reviewer
  can compare it with the requirement. It helps detect errors; it does not
  establish completeness.
* The discrepancy check is mechanical: every enumerated obligation must be
  covered by a constraint, every constraint must trace to an obligation, and
  the encoding must agree with the requester's satisfying and violating
  witnesses. Disagreement yields FORMALIZATION_INCOMPLETE and no answer.
* Counterexample search asks, per constraint, whether the others still allow
  it to be violated (a constraint implied by the others is flagged), and for
  entailment queries searches for a model of the negated property.
* The result is *formally* valid given the encoding. Unverified real-world
  premises keep it WORLD_UNVERIFIED. Authority is never in scope.

The solver is Z3 (``z3-solver``, MIT licence). Without it the organ returns
DEPENDENCY_UNAVAILABLE; it never guesses.
"""
from __future__ import annotations

import re
import time
from typing import Any, Mapping

from ..contracts import Expenditure, OrganResult

ORGAN_ID = "cortex.formal.z3@0.1.1"
VERSION = "0.1.1"
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_BOOL_OPS = ("and", "or", "not", "implies")
_CMP_OPS = ("=", "!=", "<", "<=", ">", ">=")
_ARITH_OPS = ("+", "-", "*")
_SYMBOL = {"=": "=", "!=": "≠", "<": "<", "<=": "≤", ">": ">", ">=": "≥", "+": "+", "-": "−", "*": "×"}


class FormalModelError(ValueError):
    pass


def _check_expr(node, variables: Mapping[str, str]) -> str:
    """Return the sort ('bool' or 'num') of a well-formed expression."""
    if isinstance(node, bool):
        return "bool"
    if isinstance(node, (int, float)):
        return "num"
    if isinstance(node, str):
        if node not in variables:
            raise FormalModelError(f"unknown variable {node!r}")
        return "bool" if variables[node] == "bool" else "num"
    if not isinstance(node, list) or not node or not isinstance(node[0], str):
        raise FormalModelError(f"bad expression node {node!r}")
    op, args = node[0], node[1:]
    sorts = [_check_expr(a, variables) for a in args]
    if op in _BOOL_OPS:
        if (op == "not" and len(args) != 1) or (op == "implies" and len(args) != 2) or not args:
            raise FormalModelError(f"wrong arity for {op}")
        if any(s != "bool" for s in sorts):
            raise FormalModelError(f"{op} expects boolean arguments")
        return "bool"
    if op in _CMP_OPS:
        if len(args) != 2 or sorts[0] != sorts[1] or (op not in ("=", "!=") and sorts[0] != "num"):
            raise FormalModelError(f"{op} expects two comparable arguments")
        return "bool"
    if op in _ARITH_OPS:
        if len(args) < 2 or any(s != "num" for s in sorts):
            raise FormalModelError(f"{op} expects two or more numeric arguments")
        return "num"
    if op == "ite":
        if len(args) != 3 or sorts[0] != "bool" or sorts[1] != sorts[2]:
            raise FormalModelError("ite expects (bool, x, x)")
        return sorts[1]
    if op == "distinct":
        if len(args) < 2 or len(set(sorts)) != 1:
            raise FormalModelError("distinct expects two or more arguments of one sort")
        return "bool"
    raise FormalModelError(f"unknown operator {op!r}")


def render(node) -> str:
    if isinstance(node, bool):
        return "true" if node else "false"
    if isinstance(node, (int, float, str)):
        return str(node)
    op, args = node[0], node[1:]
    if op == "not":
        return f"not ({render(args[0])})"
    if op == "implies":
        return f"if {render(args[0])} then {render(args[1])}"
    if op in ("and", "or"):
        return f" {op} ".join(f"({render(a)})" for a in args)
    if op == "ite":
        return f"(if {render(args[0])} then {render(args[1])} else {render(args[2])})"
    if op == "distinct":
        return "all different: " + ", ".join(render(a) for a in args)
    joined = f" {_SYMBOL[op]} ".join(render(a) for a in args)
    return joined if op in _CMP_OPS else f"({joined})"


class Spec:
    def __init__(self, model: Mapping[str, Any]):
        if not isinstance(model, Mapping):
            raise FormalModelError("formal_model must be an object")
        self.requirement = model.get("requirement", "")
        self.variables: dict[str, str] = {}
        self.bounds: dict[str, tuple] = {}
        for v in model.get("variables", []):
            name, sort = v.get("name"), v.get("sort")
            if not isinstance(name, str) or not _IDENT.match(name) or name in self.variables:
                raise FormalModelError(f"bad or duplicate variable {name!r}")
            if sort not in ("int", "real", "bool"):
                raise FormalModelError(f"{name}: sort must be int, real or bool")
            self.variables[name] = sort
            if sort != "bool":
                self.bounds[name] = (v.get("lo"), v.get("hi"))
        if not self.variables:
            raise FormalModelError("model declares no variables")
        self.obligations = {o["id"]: o.get("text", "") for o in model.get("obligations", [])}
        self.constraints = []
        seen = set()
        for c in model.get("constraints", []):
            cid = c.get("id")
            if not isinstance(cid, str) or not _IDENT.match(cid) or cid in seen:
                raise FormalModelError(f"bad or duplicate constraint id {cid!r}")
            seen.add(cid)
            if _check_expr(c.get("expr"), self.variables) != "bool":
                raise FormalModelError(f"{cid}: constraint must be boolean")
            self.constraints.append({"id": cid, "covers": list(c.get("covers", [])), "expr": c["expr"]})
        if not self.constraints:
            raise FormalModelError("model declares no constraints")
        self.query = model.get("query", {"kind": "feasibility"})
        if self.query.get("kind") not in ("feasibility", "entailment"):
            raise FormalModelError(f"unsupported query kind {self.query.get('kind')!r}")
        if self.query["kind"] == "entailment" and _check_expr(self.query.get("property"), self.variables) != "bool":
            raise FormalModelError("entailment property must be boolean")
        witnesses = model.get("witnesses", {})
        self.satisfying = list(witnesses.get("satisfying", []))
        self.violating = list(witnesses.get("violating", []))
        for w in self.satisfying + self.violating:
            if set(w) - set(self.variables):
                raise FormalModelError(f"witness names unknown variables: {sorted(set(w) - set(self.variables))}")
        self.premises = list(model.get("premises", []))
        self.timeout_ms = int(model.get("timeout_ms", 5000))


def _z3():
    try:
        import z3  # noqa: F401
        return z3
    except ImportError:
        return None


def _unknown_state(solver) -> str:
    """Z3 reports an exhausted timeout as ``timeout`` or, in recent releases, ``canceled``
    (the timer is this process's only canceller). Anything else undecided is INCONCLUSIVE."""
    reason = str(solver.reason_unknown()).lower()
    return "TIMEOUT" if "timeout" in reason or "canceled" in reason else "INCONCLUSIVE"


class FormalOrgan:
    organ_id = ORGAN_ID
    version = VERSION

    def run(self, problem, geometry, budget) -> OrganResult:
        started = time.perf_counter()
        model = problem.payload.get("formal_model")
        faults = problem.payload.get("faults", {}) or {}
        if model is None:
            return self._fail("INSUFFICIENT_EVIDENCE", "no structured model supplied", started)
        try:
            spec = Spec(model)
        except (FormalModelError, KeyError, TypeError, ValueError) as exc:
            return self._fail("MALFORMED_INPUT", f"model rejected: {exc}", started)

        # reverse translation
        reverse = [f"{v} is {'a boolean' if s == 'bool' else ('an integer' if s == 'int' else 'a real')}"
                   + ("" if s == "bool" else self._bound_text(spec.bounds[v])) for v, s in spec.variables.items()]
        reverse += [f"{c['id']} (covers {', '.join(c['covers']) or 'nothing'}): {render(c['expr'])}"
                    for c in spec.constraints]
        if spec.query["kind"] == "entailment":
            reverse.append(f"question: do the constraints guarantee {render(spec.query['property'])}?")

        # discrepancy check (structural part)
        discrepancies = []
        covered = {o for c in spec.constraints for o in c["covers"]}
        for oid in spec.obligations:
            if oid not in covered:
                discrepancies.append(f"obligation {oid} has no constraint: {spec.obligations[oid]!r}")
        for c in spec.constraints:
            if not c["covers"]:
                discrepancies.append(f"constraint {c['id']} traces to no obligation")
            for oid in c["covers"]:
                if oid not in spec.obligations:
                    discrepancies.append(f"constraint {c['id']} cites unknown obligation {oid}")
        warnings = []
        for oid, text in spec.obligations.items():
            numbers = set(re.findall(r"(?<![A-Za-z_])\d+(?:\.\d+)?", text))
            used = set()
            for c in spec.constraints:
                if oid in c["covers"]:
                    used |= set(re.findall(r"(?<![A-Za-z_])\d+(?:\.\d+)?", str(c["expr"])))
            missing = sorted(numbers - used)
            if missing:
                warnings.append(f"{oid}: numbers {missing} in the requirement text appear in no covering constraint")

        z3 = None if faults.get("solver_available") is False else _z3()
        if z3 is None:
            why = "solver outage injected by fault" if faults.get("solver_available") is False else \
                "z3-solver is not installed"
            return self._fail("DEPENDENCY_UNAVAILABLE", why, started, reverse=reverse,
                              discrepancies=discrepancies, warnings=warnings)

        max_calls = int(getattr(getattr(geometry, "resource_limits", None), "max_solver_calls", 64))
        calls = 0
        env = self._declare(z3, spec)
        exprs = {c["id"]: self._build(z3, c["expr"], env) for c in spec.constraints}
        domain = self._domain(z3, spec, env)

        def check(assertions, track=None):
            nonlocal calls
            calls += 1
            s = z3.Solver()
            s.set("timeout", spec.timeout_ms)
            if track:
                s.set(unsat_core=True)
                for name, e in track.items():
                    s.assert_and_track(e, z3.Bool(f"__track_{name}"))
            for a in assertions:
                s.add(a)
            return s, s.check()

        # discrepancy check (witness part): encoding must agree with requester examples
        witness_results = []
        for kind, items in (("satisfying", spec.satisfying), ("violating", spec.violating)):
            for i, w in enumerate(items):
                if calls >= max_calls:
                    discrepancies.append("witness checks truncated by solver-call budget")
                    break
                bind = [env[k] == self._lit(z3, spec.variables[k], v) for k, v in w.items()]
                ws, res = check(domain + bind + list(exprs.values()))
                if res not in (z3.sat, z3.unsat):
                    # An undecided witness is not agreement: the discrepancy check did not complete.
                    return self._result(_unknown_state(ws), None, spec, z3, started, calls, reverse,
                                        discrepancies, warnings, witness_results, [],
                                        {"status": "UNKNOWN", "reason": str(ws.reason_unknown()),
                                         "during": f"{kind} witness #{i}"})
                holds = res == z3.sat
                ok = holds if kind == "satisfying" else not holds
                witness_results.append({"kind": kind, "index": i, "witness": w, "agrees": ok})
                if not ok:
                    discrepancies.append(f"{kind} witness #{i} {w} disagrees with the encoding")

        if calls >= max_calls:
            return self._fail("BUDGET_EXHAUSTED", "solver-call budget exhausted before the main check", started,
                              reverse=reverse, discrepancies=discrepancies, warnings=warnings, calls=calls)

        if discrepancies:
            return self._result("FORMALIZATION_INCOMPLETE", None, spec, z3, started, calls, reverse,
                                discrepancies, warnings, witness_results, [], {"status": "not_run"})

        # counterexample search
        cex = []
        for c in spec.constraints:
            if calls >= max_calls - 1:
                cex.append({"constraint": c["id"], "result": "skipped: solver-call budget"})
                continue
            others = [e for cid, e in exprs.items() if cid != c["id"]]
            _, res = check(domain + others + [z3.Not(exprs[c["id"]])])
            if res == z3.unsat:
                cex.append({"constraint": c["id"], "result": "implied by the others (redundant or mis-encoded?)"})
            elif res == z3.sat:
                cex.append({"constraint": c["id"], "result": "binding: violable without it"})
            else:
                cex.append({"constraint": c["id"], "result": "unknown"})

        # solver result
        if spec.query["kind"] == "feasibility":
            solver, res = check(domain, track=exprs)
            if res == z3.sat:
                m = solver.model()
                assignment = {k: self._value(z3, m.eval(env[k], model_completion=True)) for k in spec.variables}
                answer = {"feasible": True, "model": assignment}
                solver_out = {"status": "SAT", "model": assignment}
            elif res == z3.unsat:
                core = sorted(str(t).replace("__track_", "") for t in solver.unsat_core())
                answer = {"feasible": False, "unsat_core": core}
                solver_out = {"status": "UNSAT", "unsat_core": core}
            else:
                return self._result(_unknown_state(solver),
                                    None, spec, z3, started, calls, reverse, discrepancies, warnings,
                                    witness_results, cex, {"status": "UNKNOWN",
                                                           "reason": str(solver.reason_unknown())})
        else:
            prop = self._build(z3, spec.query["property"], env)
            solver, res = check(domain + [z3.Not(prop)], track=exprs)
            if res == z3.sat:
                m = solver.model()
                counter = {k: self._value(z3, m.eval(env[k], model_completion=True)) for k in spec.variables}
                answer = {"entailed": False, "counterexample": counter}
                solver_out = {"status": "SAT(negation)", "counterexample": counter}
            elif res == z3.unsat:
                core = sorted(str(t).replace("__track_", "") for t in solver.unsat_core())
                answer = {"entailed": True, "supporting_constraints": core}
                solver_out = {"status": "UNSAT(negation)", "certificate": "unsat core of constraints", "unsat_core": core}
            else:
                return self._result(_unknown_state(solver),
                                    None, spec, z3, started, calls, reverse, discrepancies, warnings,
                                    witness_results, cex, {"status": "UNKNOWN",
                                                           "reason": str(solver.reason_unknown())})
        unverified = [p for p in spec.premises if not p.get("verified")]
        state = "WORLD_UNVERIFIED" if unverified else "OK"
        return self._result(state, answer, spec, z3, started, calls, reverse, discrepancies, warnings,
                            witness_results, cex, solver_out)

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _bound_text(bounds) -> str:
        lo, hi = bounds
        if lo is None and hi is None:
            return " (unbounded)"
        return f" in [{'-∞' if lo is None else lo}, {'∞' if hi is None else hi}]"

    @staticmethod
    def _declare(z3, spec: Spec) -> dict:
        make = {"int": z3.Int, "real": z3.Real, "bool": z3.Bool}
        return {name: make[sort](name) for name, sort in spec.variables.items()}

    @staticmethod
    def _domain(z3, spec: Spec, env) -> list:
        out = []
        for name, (lo, hi) in spec.bounds.items():
            if lo is not None:
                out.append(env[name] >= lo)
            if hi is not None:
                out.append(env[name] <= hi)
        return out

    @staticmethod
    def _lit(z3, sort, value):
        if sort == "bool":
            return z3.BoolVal(bool(value))
        return z3.IntVal(int(value)) if sort == "int" else z3.RealVal(value)

    def _build(self, z3, node, env):
        if isinstance(node, bool):
            return z3.BoolVal(node)
        if isinstance(node, int):
            return z3.IntVal(node)
        if isinstance(node, float):
            return z3.RealVal(node)
        if isinstance(node, str):
            return env[node]
        op, args = node[0], [self._build(z3, a, env) for a in node[1:]]
        if op == "and":
            return z3.And(*args)
        if op == "or":
            return z3.Or(*args)
        if op == "not":
            return z3.Not(args[0])
        if op == "implies":
            return z3.Implies(args[0], args[1])
        if op == "ite":
            return z3.If(args[0], args[1], args[2])
        if op == "distinct":
            return z3.Distinct(*args)
        if op == "=":
            return args[0] == args[1]
        if op == "!=":
            return args[0] != args[1]
        if op == "<":
            return args[0] < args[1]
        if op == "<=":
            return args[0] <= args[1]
        if op == ">":
            return args[0] > args[1]
        if op == ">=":
            return args[0] >= args[1]
        if op == "+":
            return z3.Sum(*args)
        if op == "-":
            out = args[0]
            for a in args[1:]:
                out = out - a
            return out
        if op == "*":
            return z3.Product(*args)
        raise FormalModelError(f"unknown operator {op!r}")

    @staticmethod
    def _value(z3, v):
        if z3.is_true(v):
            return True
        if z3.is_false(v):
            return False
        if z3.is_int_value(v):
            return v.as_long()
        if z3.is_rational_value(v):
            return float(v.numerator_as_long()) / float(v.denominator_as_long())
        return str(v)

    def _result(self, state, answer, spec, z3, started, calls, reverse, discrepancies, warnings,
                witness_results, cex, solver_out) -> OrganResult:
        unverified = [p for p in spec.premises if not p.get("verified")]
        proof = {
            "proof_class": "formal",
            "scope": "valid_given_encoding",
            "original_requirement": spec.requirement,
            "structured_model": {"variables": spec.variables, "bounds": {k: list(v) for k, v in spec.bounds.items()},
                                 "constraints": spec.constraints, "obligations": spec.obligations,
                                 "query": spec.query},
            "reverse_translation": reverse,
            "discrepancy_check": {"discrepancies": discrepancies, "warnings": warnings,
                                  "witnesses": witness_results},
            "counterexample_search": cex,
            "solver": {"name": "z3", "version": z3.get_version_string(), **solver_out},
            "premises": spec.premises,
            "unverified_premises": [p.get("id") for p in unverified],
            "completeness": "not established by reverse translation",
        }
        assumptions = tuple(f"premise {p.get('id')}: {p.get('text')} (verified={bool(p.get('verified'))})"
                            for p in spec.premises)
        return OrganResult(
            organ_id=ORGAN_ID, organ_version=VERSION, state=state, answer=answer, proof=proof,
            assumptions=assumptions,
            uncertainty="formally exact given the encoding; empirical correspondence "
                        + ("unverified" if unverified else "rests on verified premises"),
            expenditure=Expenditure(seconds=time.perf_counter() - started, solver_calls=calls),
            dependencies=("solver:z3",), origin="solver",
            notes=tuple(discrepancies + warnings))

    def _fail(self, state, why, started, *, reverse=(), discrepancies=(), warnings=(), calls=0) -> OrganResult:
        return OrganResult(
            organ_id=ORGAN_ID, organ_version=VERSION, state=state, answer=None,
            proof={"proof_class": "formal", "scope": "valid_given_encoding", "failure": why,
                   "reverse_translation": list(reverse),
                   "discrepancy_check": {"discrepancies": list(discrepancies), "warnings": list(warnings)}},
            uncertainty="no formal result",
            expenditure=Expenditure(seconds=time.perf_counter() - started, solver_calls=calls),
            dependencies=("solver:z3",), origin="solver", notes=(why,))
