"""OR-Tools CP-SAT engine for the cortex ``formal_model`` contract (directive section 7C).

The same structured model the Z3 organ accepts, solved by a different engine
with different failure modes. Two engines behind one input contract make the
Formal/Optimization slice fault-diverse: the router can fall back when one is
unavailable, and can obtain a certificate from the other.

Scope (declared; anything else is refused by ``unsupported`` before routing):

* integer and boolean variables only; every integer variable has finite bounds;
* linear arithmetic (``*`` has at most one non-constant factor, integer constants);
* comparisons, ``and``/``or``/``not``/``implies``/``distinct`` and boolean ``ite``;
* queries ``feasibility``, ``entailment`` and ``optimize`` with a linear objective.

Native statuses are preserved: OPTIMAL, FEASIBLE, INFEASIBLE, MODEL_INVALID,
UNKNOWN. FEASIBLE is never reported as optimal. An INFEASIBLE core comes from
CP-SAT's *sufficient assumptions for infeasibility*: sufficient, not proven
minimal. Every returned assignment is re-checked against the source constraints
by ``formal_eval`` (plain Python, solver-independent) before anything is
claimed; a failed check yields no answer.

Formal and Optimization share this delivery slice but keep separate evidence:
feasibility and entailment emit the ``formal`` proof class; optimization emits
the ``optimization`` proof class (objective, constraints, assignment,
feasibility check, native status, bound/gap, budget, timeout).
"""
from __future__ import annotations

import importlib.metadata
import importlib.util
import time
from typing import Any, Mapping

from ..contracts import Expenditure, OrganResult
from . import formal_eval
from .formal import FormalModelError, Spec, review

ORGAN_ID = "cortex.optimization.cpsat@0.2.0"
VERSION = "0.2.0"
SEED = 0
WORKERS = 1   # one worker + fixed seed: deterministic search, reproducible receipts
_NEGATE = {"<=": ">", "<": ">=", ">=": "<", ">": "<=", "=": "!=", "!=": "="}


def available() -> bool:
    return importlib.util.find_spec("ortools") is not None


def unsupported(model: Mapping[str, Any]) -> list[str]:
    """Reasons this engine cannot faithfully encode ``model`` (empty when it can).

    Used as a hard eligibility filter: the router never sends a model here that
    the engine would have to approximate."""
    try:
        spec = Spec(model)
    except (FormalModelError, KeyError, TypeError, ValueError) as exc:
        return [f"model rejected: {exc}"]
    reasons = []
    for name, sort in spec.variables.items():
        if sort == "real":
            reasons.append(f"{name} is real-valued; CP-SAT is integer-only")
        elif sort == "int":
            lo, hi = spec.bounds[name]
            if lo is None or hi is None:
                reasons.append(f"{name} is unbounded; CP-SAT needs finite integer bounds")
    nodes = [c["expr"] for c in spec.constraints]
    if spec.query["kind"] == "entailment":
        nodes.append(spec.query["property"])
    if spec.query["kind"] == "optimize":
        nodes.append(spec.query["objective"])
    for node in nodes:
        reasons.extend(_fragment_problems(node, spec.variables))
    return list(dict.fromkeys(reasons))


def _fragment_problems(node, variables) -> list[str]:
    if isinstance(node, bool) or isinstance(node, str):
        return []
    if isinstance(node, float):
        return [] if node.is_integer() else [f"non-integral constant {node}"]
    if isinstance(node, int):
        return []
    op, args = node[0], node[1:]
    out = []
    for a in args:
        out.extend(_fragment_problems(a, variables))
    if op == "*":
        non_constant = [a for a in args if not isinstance(a, (int, float)) or isinstance(a, bool)]
        if len(non_constant) > 1:
            out.append("non-linear product of variables")
    if op == "ite" and not _is_boolean(args[1], variables):
        out.append("numeric if-then-else is outside the CP-SAT fragment")
    return out


def _is_boolean(node, variables) -> bool:
    if isinstance(node, bool):
        return True
    if isinstance(node, str):
        return variables.get(node) == "bool"
    if isinstance(node, list) and node:
        return node[0] in ("and", "or", "not", "implies", "distinct", "=", "!=", "<", "<=", ">", ">=") or (
            node[0] == "ite" and _is_boolean(node[2], variables))
    return False


class _Encoder:
    """Translate the s-expression fragment into one CP-SAT model."""

    def __init__(self, cp_model, spec: Spec):
        self.cp = cp_model
        self.spec = spec
        self.model = cp_model.CpModel()
        self.vars = {}
        for name, sort in spec.variables.items():
            if sort == "bool":
                self.vars[name] = self.model.new_bool_var(name)
            else:
                lo, hi = spec.bounds[name]
                self.vars[name] = self.model.new_int_var(int(lo), int(hi), name)
        self.true = self.model.new_bool_var("__true")
        self.model.add_bool_or([self.true])
        self._n = 0

    def _fresh(self):
        self._n += 1
        return self.model.new_bool_var(f"__b{self._n}")

    def linear(self, node):
        if isinstance(node, bool):
            raise FormalModelError("boolean in arithmetic")
        if isinstance(node, (int, float)):
            return int(node)
        if isinstance(node, str):
            return self.vars[node]
        op, args = node[0], [self.linear(a) for a in node[1:]]
        if op == "+":
            return sum(args[1:], args[0])
        if op == "-":
            out = args[0]
            for a in args[1:]:
                out = out - a
            return out
        if op == "*":
            const, var = 1, None
            for a in args:
                if isinstance(a, int):
                    const *= a
                else:
                    var = a
            return const if var is None else var * const
        raise FormalModelError(f"{op} is not linear arithmetic")

    def literal(self, node):
        """A CP-SAT literal equivalent to the boolean expression ``node``."""
        if isinstance(node, bool):
            return self.true if node else self.true.Not()
        if isinstance(node, str):
            return self.vars[node]
        op, args = node[0], node[1:]
        if op == "not":
            return self.literal(args[0]).Not()
        if op in ("and", "or"):
            lits = [self.literal(a) for a in args]
            b = self._fresh()
            neg = [lit.Not() for lit in lits]
            if op == "and":
                self.model.add_bool_and(lits).only_enforce_if(b)
                self.model.add_bool_or(neg).only_enforce_if(b.Not())
            else:
                self.model.add_bool_or(lits).only_enforce_if(b)
                self.model.add_bool_and(neg).only_enforce_if(b.Not())
            return b
        if op == "implies":
            return self.literal(["or", ["not", args[0]], args[1]])
        if op == "ite":
            return self.literal(["or", ["and", args[0], args[1]], ["and", ["not", args[0]], args[2]]])
        if op == "distinct":
            pairs = [["!=", a, b] for i, a in enumerate(args) for b in args[i + 1:]]
            return self.literal(["and", *pairs]) if len(pairs) > 1 else self.literal(pairs[0])
        if op in _NEGATE:
            left, right = args
            if _is_boolean(left, self.spec.variables):   # boolean (in)equality
                lhs, rhs = self.literal(left), self.literal(right)
            else:
                lhs, rhs = self.linear(left), self.linear(right)
            b = self._fresh()
            self.model.add(self._cmp(op, lhs, rhs)).only_enforce_if(b)
            self.model.add(self._cmp(_NEGATE[op], lhs, rhs)).only_enforce_if(b.Not())
            return b
        raise FormalModelError(f"unknown operator {op!r}")

    @staticmethod
    def _cmp(op, lhs, rhs):
        return {"<=": lambda: lhs <= rhs, "<": lambda: lhs < rhs, ">=": lambda: lhs >= rhs,
                ">": lambda: lhs > rhs, "=": lambda: lhs == rhs, "!=": lambda: lhs != rhs}[op]()


class CpSatOrgan:
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
        reverse, discrepancies, warnings = review(spec)
        outside = unsupported(model)
        if outside:
            return self._fail("MALFORMED_INPUT", "outside the CP-SAT fragment: " + "; ".join(outside), started,
                              reverse=reverse, discrepancies=discrepancies, warnings=warnings)
        if faults.get("cpsat_available") is False or not available():
            why = "CP-SAT outage injected by fault" if faults.get("cpsat_available") is False else \
                "ortools is not installed"
            return self._fail("DEPENDENCY_UNAVAILABLE", why, started, reverse=reverse,
                              discrepancies=discrepancies, warnings=warnings)
        from ortools.sat.python import cp_model
        max_calls = int(getattr(getattr(geometry, "resource_limits", None), "max_solver_calls", 64))
        seconds = max(spec.timeout_ms, 1) / 1000.0
        calls = 0
        timed_out = []
        # The declared latency budget caps every solve: no fresh timeout per solve.
        latency = float(getattr(budget, "max_latency_s", 0) or 0)
        deadline = started + latency if latency > 0 else None

        def left(until=None) -> float:
            end = until if until is not None else deadline
            return seconds if end is None else min(seconds, end - time.perf_counter())

        def solve(extra=None, *, objective=None, assumptions=False, constraints=None, until=None):
            """One CP-SAT solve over ``constraints`` (default: all) plus ``extra`` boolean nodes."""
            nonlocal calls
            calls += 1
            limit = max(0.001, left(until))
            enc = _Encoder(cp_model, spec)
            guards = {}
            for c in spec.constraints if constraints is None else constraints:
                lit = enc.literal(c["expr"])
                if assumptions:
                    g = enc.model.new_bool_var(f"__guard_{c['id']}")
                    enc.model.add_implication(g, lit)
                    guards[g.index] = (g, c["id"])
                else:
                    enc.model.add_bool_or([lit])
            for node in extra or ():
                enc.model.add_bool_or([enc.literal(node)])
            if assumptions:
                enc.model.add_assumptions([g for g, _ in guards.values()])
            if objective is not None:
                expr = enc.linear(objective)
                (enc.model.minimize if spec.query["sense"] == "minimize" else enc.model.maximize)(expr)
            invalid = enc.model.validate()
            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = limit
            solver.parameters.num_workers = WORKERS
            solver.parameters.random_seed = SEED
            t0 = time.perf_counter()
            status = solver.solve(enc.model) if not invalid else cp_model.MODEL_INVALID
            name = solver.status_name(status) if not invalid else "MODEL_INVALID"
            if name == "UNKNOWN" and time.perf_counter() - t0 >= 0.95 * limit:
                timed_out.append(True)
            return enc, solver, name, guards, invalid

        def assignment(enc, solver):
            return {k: (bool(solver.value(v)) if spec.variables[k] == "bool" else int(solver.value(v)))
                    for k, v in enc.vars.items()}

        def undecided(name):
            return "TIMEOUT" if name == "UNKNOWN" and timed_out else "INCONCLUSIVE"

        # discrepancy check, witness part: full witnesses are evaluated without any solver
        witness_results = []
        for kind, items in (("satisfying", spec.satisfying), ("violating", spec.violating)):
            for i, w in enumerate(items):
                if set(w) == set(spec.variables):
                    holds = formal_eval.check_assignment(spec, w)["holds"]
                    how = "python re-evaluation"
                else:
                    if calls >= max_calls:
                        discrepancies.append("witness checks truncated by solver-call budget")
                        break
                    _, _, name, _, _ = solve([["=", k, v] for k, v in w.items()])
                    if name not in ("OPTIMAL", "FEASIBLE", "INFEASIBLE"):
                        return self._result(undecided(name), None, spec, started, calls, reverse, discrepancies,
                                            warnings, witness_results, [], {"status": name,
                                                                            "during": f"{kind} witness #{i}"})
                    holds, how = name != "INFEASIBLE", "CP-SAT completion search"
                ok = holds if kind == "satisfying" else not holds
                witness_results.append({"kind": kind, "index": i, "witness": w, "agrees": ok, "checked_by": how})
                if not ok:
                    discrepancies.append(f"{kind} witness #{i} {w} disagrees with the encoding")
        if calls >= max_calls:
            return self._fail("BUDGET_EXHAUSTED", "solver-call budget exhausted before the main check", started,
                              reverse=reverse, discrepancies=discrepancies, warnings=warnings, calls=calls)
        if discrepancies:
            return self._result("FORMALIZATION_INCOMPLETE", None, spec, started, calls, reverse, discrepancies,
                                warnings, witness_results, [], {"status": "not_run"})

        # counterexample search: is each constraint violable given the others? A diagnostic, so it
        # may spend at most half of what remains of the latency budget.
        cex = []
        cex_until = None if deadline is None else time.perf_counter() + (deadline - time.perf_counter()) / 2
        for c in spec.constraints:
            if calls >= max_calls - 1:
                cex.append({"constraint": c["id"], "result": "skipped: solver-call budget"})
                continue
            if cex_until is not None and left(cex_until) <= 0:
                cex.append({"constraint": c["id"], "result": "skipped: latency budget"})
                continue
            others = [x for x in spec.constraints if x["id"] != c["id"]]
            _, _, name, _, _ = solve([["not", c["expr"]]], constraints=others, until=cex_until)
            cex.append({"constraint": c["id"], "result": {
                "INFEASIBLE": "implied by the others (redundant or mis-encoded?)",
                "OPTIMAL": "binding: violable without it", "FEASIBLE": "binding: violable without it"}.get(
                    name, "unknown")})

        kind = spec.query["kind"]
        if kind == "entailment":
            enc, solver, name, _, invalid = solve([["not", spec.query["property"]]])
            if name in ("OPTIMAL", "FEASIBLE"):
                counter = assignment(enc, solver)
                check = formal_eval.check_assignment(spec, counter)
                prop_false = formal_eval.evaluate(spec.query["property"], counter, spec.variables) is False
                if not (check["holds"] and prop_false):
                    return self._unchecked(spec, started, calls, reverse, discrepancies, warnings, witness_results,
                                           cex, name, check)
                answer = {"entailed": False, "counterexample": counter}
                solver_out = {"status": name, "query": "constraints and not(property)", "counterexample": counter,
                              "independent_check": {**check, "property_violated": prop_false}}
            elif name == "INFEASIBLE":
                answer = {"entailed": True}
                solver_out = {"status": name, "query": "constraints and not(property)",
                              "certificate": "CP-SAT infeasibility of the negated property (solver-asserted; "
                                             "not independently re-checked)"}
            else:
                return self._native_failure(name, invalid, bool(timed_out), spec, started, calls, reverse,
                                            discrepancies, warnings, witness_results, cex)
            proof_class = "formal"
        else:
            enc, solver, name, guards, invalid = solve(assumptions=True)
            if name == "INFEASIBLE":
                core = sorted(guards[i][1] for i in solver.sufficient_assumptions_for_infeasibility()
                              if i in guards)
                answer = {"feasible": False, "unsat_core": core}
                solver_out = {"status": name, "unsat_core": core,
                              "core_kind": "sufficient assumptions for infeasibility; not proven minimal"}
                proof_class = "formal" if kind == "feasibility" else "optimization"
            elif name not in ("OPTIMAL", "FEASIBLE"):
                return self._native_failure(name, invalid, bool(timed_out), spec, started, calls, reverse,
                                            discrepancies, warnings, witness_results, cex)
            elif kind == "feasibility":
                found = assignment(enc, solver)
                check = formal_eval.check_assignment(spec, found)
                if not check["holds"]:
                    return self._unchecked(spec, started, calls, reverse, discrepancies, warnings, witness_results,
                                           cex, name, check)
                answer = {"feasible": True, "model": found}
                solver_out = {"status": name, "model": found, "independent_check": check}
                proof_class = "formal"
            else:
                if calls >= max_calls:
                    return self._fail("BUDGET_EXHAUSTED", "solver-call budget exhausted before optimization",
                                      started, reverse=reverse, discrepancies=discrepancies, warnings=warnings,
                                      calls=calls)
                enc, solver, name, _, invalid = solve(objective=spec.query["objective"])
                if name not in ("OPTIMAL", "FEASIBLE"):
                    return self._native_failure(name, invalid, bool(timed_out), spec, started, calls, reverse,
                                                discrepancies, warnings, witness_results, cex)
                found = assignment(enc, solver)
                check = formal_eval.check_assignment(spec, found)
                value = formal_eval.objective_value(spec, found)
                reported = int(round(solver.objective_value))
                bound = int(round(solver.best_objective_bound))
                if not check["holds"] or value != reported:
                    check = {**check, "objective_recomputed": value, "objective_reported": reported}
                    return self._unchecked(spec, started, calls, reverse, discrepancies, warnings, witness_results,
                                           cex, name, check, proof_class="optimization")
                optimal = name == "OPTIMAL"
                answer = {"feasible": True, "optimal": optimal, "sense": spec.query["sense"], "objective": value,
                          "model": found}
                if not optimal:
                    answer.update(best_bound=bound, gap=abs(value - bound))
                solver_out = {"status": name, "objective": value, "best_bound": bound, "gap": abs(value - bound),
                              "model": found, "independent_check": {**check, "objective_recomputed": value,
                                                                    "objective_reported": reported}}
                proof_class = "optimization"
                if not optimal:
                    unverified = [p for p in spec.premises if not p.get("verified")]
                    return self._result("INCONCLUSIVE", answer, spec, started, calls, reverse, discrepancies,
                                        warnings + ["FEASIBLE is not OPTIMAL: the search stopped with a gap of "
                                                    f"{abs(value - bound)}"] +
                                        ([f"unverified premises {[p.get('id') for p in unverified]}"]
                                         if unverified else []),
                                        witness_results, cex, solver_out, proof_class=proof_class)
        unverified = [p for p in spec.premises if not p.get("verified")]
        state = "WORLD_UNVERIFIED" if unverified else "OK"
        return self._result(state, answer, spec, started, calls, reverse, discrepancies, warnings, witness_results,
                            cex, solver_out, proof_class=proof_class)

    # ---------------------------------------------------------------- outcomes
    def _native_failure(self, name, invalid, timed_out, spec, started, calls, reverse, discrepancies, warnings,
                        witness_results, cex):
        if name == "MODEL_INVALID":
            return self._fail("MALFORMED_INPUT", f"CP-SAT MODEL_INVALID: {invalid or 'rejected by the solver'}",
                              started, reverse=reverse, discrepancies=discrepancies, warnings=warnings, calls=calls)
        state = "TIMEOUT" if name == "UNKNOWN" and timed_out else "INCONCLUSIVE"
        return self._result(state, None, spec, started, calls, reverse, discrepancies, warnings, witness_results, cex,
                            {"status": name, "timed_out": timed_out})

    def _unchecked(self, spec, started, calls, reverse, discrepancies, warnings, witness_results, cex, name, check,
                   proof_class="formal"):
        """The engine's assignment failed independent re-evaluation: nothing is claimed."""
        return self._result("INCONCLUSIVE", None, spec, started, calls, reverse, discrepancies,
                            warnings + [f"solver assignment failed independent re-evaluation: {check}"],
                            witness_results, cex, {"status": name, "independent_check": check,
                                                   "claim": "withheld"}, proof_class=proof_class)

    def _result(self, state, answer, spec, started, calls, reverse, discrepancies, warnings, witness_results, cex,
                solver_out, *, proof_class="formal") -> OrganResult:
        unverified = [p for p in spec.premises if not p.get("verified")]
        solver = {"name": "ortools-cpsat", "version": _version(), "workers": WORKERS, "seed": SEED,
                  "max_time_s_per_solve": max(spec.timeout_ms, 1) / 1000.0, **solver_out}
        common = {
            "scope": "valid_given_encoding",
            "original_requirement": spec.requirement,
            "structured_model": {"variables": spec.variables, "bounds": {k: list(v) for k, v in spec.bounds.items()},
                                 "constraints": spec.constraints, "obligations": spec.obligations,
                                 "query": spec.query},
            "reverse_translation": reverse,
            "discrepancy_check": {"discrepancies": discrepancies, "warnings": warnings, "witnesses": witness_results},
            "counterexample_search": cex,
            "solver": solver,
            "premises": spec.premises,
            "unverified_premises": [p.get("id") for p in unverified],
            "completeness": "not established by reverse translation",
        }
        if proof_class == "optimization":
            proof = {"proof_class": "optimization", **common,
                     "objective": {"sense": spec.query.get("sense"), "expression": spec.query.get("objective"),
                                   "value": (answer or {}).get("objective")},
                     "assignment": (answer or {}).get("model"),
                     "feasibility_check": solver_out.get("independent_check"),
                     "native_status": solver_out.get("status"),
                     "bound": solver_out.get("best_bound"), "gap": solver_out.get("gap"),
                     "budget": {"max_solver_calls_used": calls, "workers": WORKERS, "seed": SEED},
                     "timeout_s": max(spec.timeout_ms, 1) / 1000.0,
                     "optimality": ("proven by CP-SAT search (bound equals objective); independent certificate "
                                    "recorded separately when obtained") if (answer or {}).get("optimal") else
                     "not proven"}
        else:
            proof = {"proof_class": "formal", **common}
        assumptions = tuple(f"premise {p.get('id')}: {p.get('text')} (verified={bool(p.get('verified'))})"
                            for p in spec.premises)
        return OrganResult(
            organ_id=ORGAN_ID, organ_version=VERSION, state=state, answer=answer, proof=proof,
            assumptions=assumptions,
            uncertainty="exact given the encoding; empirical correspondence "
                        + ("unverified" if unverified else "rests on verified premises"),
            expenditure=Expenditure(seconds=time.perf_counter() - started, solver_calls=calls),
            dependencies=("solver:ortools-cpsat",), origin="solver", notes=tuple(discrepancies + warnings))

    def _fail(self, state, why, started, *, reverse=(), discrepancies=(), warnings=(), calls=0) -> OrganResult:
        return OrganResult(
            organ_id=ORGAN_ID, organ_version=VERSION, state=state, answer=None,
            proof={"proof_class": "formal", "scope": "valid_given_encoding", "failure": why,
                   "reverse_translation": list(reverse),
                   "discrepancy_check": {"discrepancies": list(discrepancies), "warnings": list(warnings)}},
            uncertainty="no result",
            expenditure=Expenditure(seconds=time.perf_counter() - started, solver_calls=calls),
            dependencies=("solver:ortools-cpsat",), origin="solver", notes=(why,))


def _version() -> str:
    try:
        return importlib.metadata.version("ortools")
    except importlib.metadata.PackageNotFoundError:
        return "unavailable"


def z3_optimality_certificate(model: Mapping[str, Any], value, timeout_ms: int = 5000) -> dict:
    """Fault-diverse certificate for a CP-SAT optimum: ask Z3 for a strictly better feasible assignment.

    UNSAT from a *different* engine is an independent check of the optimality
    claim (both share only the parser). Returns {"status": ..., "engine": "z3"}."""
    try:
        import z3
    except ImportError:
        return {"status": "NOT_RUN", "why": "z3-solver is not installed", "engine": "z3"}
    from .formal import FormalOrgan
    spec = Spec(model)
    organ = FormalOrgan()
    env = organ._declare(z3, spec)
    s = z3.Solver()
    s.set("timeout", timeout_ms)
    for a in organ._domain(z3, spec, env):
        s.add(a)
    for c in spec.constraints:
        s.add(organ._build(z3, c["expr"], env))
    objective = organ._build(z3, spec.query["objective"], env)
    s.add(objective < value if spec.query["sense"] == "minimize" else objective > value)
    res = s.check()
    if res == z3.unsat:
        return {"status": "CERTIFIED", "engine": "z3", "version": z3.get_version_string(),
                "claim": f"no feasible assignment has objective {'<' if spec.query['sense'] == 'minimize' else '>'} "
                         f"{value}"}
    if res == z3.sat:
        better = s.model()
        return {"status": "REFUTED", "engine": "z3", "version": z3.get_version_string(),
                "better_assignment": {k: organ._value(z3, better.eval(env[k], model_completion=True))
                                      for k in spec.variables}}
    return {"status": "UNKNOWN", "engine": "z3", "version": z3.get_version_string(),
            "why": str(s.reason_unknown())}
