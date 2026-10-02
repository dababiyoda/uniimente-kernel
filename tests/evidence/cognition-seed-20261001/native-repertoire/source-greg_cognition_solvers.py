"""Pure, bounded solver adapters. Library engines are lazy; no input becomes code."""
from __future__ import annotations

import ast
from fractions import Fraction
import importlib.metadata
import math
import random

from .contracts import CognitionError, digest, integer, number


def result(output, proof, *, status="ANSWER", formal="NOT_APPLICABLE", missing=()):
    return {"output": output, "proof": proof, "status": status, "formal_validity": formal,
            "missing_information": list(missing), "empirical_validity": "WORLD_UNVERIFIED"}


def _request(data, *, required, optional=()):
    """Source clauses are consumed or refused, never silently formalized away."""
    if not isinstance(data, dict) or not set(required) <= set(data) or set(data) - set(required) - set(optional):
        raise CognitionError("restricted native request fields required")


def _work(geometry, operations):
    if operations > integer(geometry["compute_limit"], low=1, high=100000):
        raise CognitionError("BUDGET_EXHAUSTED: native workload exceeds declared compute ceiling")


def _native_source(data, proof):
    return {**proof, "source_model": data, "input_digest": digest(data)}


def exact_value(expression, variables=None):
    if not isinstance(expression, str) or len(expression) > 4096:
        raise CognitionError("bounded arithmetic expression required")
    tree = ast.parse(expression, mode="eval")
    if sum(1 for _ in ast.walk(tree)) > 256:
        raise CognitionError("arithmetic tree exceeds 256 nodes")
    variables = variables or {}

    def walk(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            number(node.value)
            value = Fraction(str(node.value))
        elif isinstance(node, ast.Name) and node.id in variables:
            number(variables[node.id])
            value = Fraction(str(variables[node.id]))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            value = walk(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)):
            left, right = walk(node.left), walk(node.right)
            if isinstance(node.op, ast.Add):
                value = left + right
            elif isinstance(node.op, ast.Sub):
                value = left - right
            elif isinstance(node.op, ast.Mult):
                value = left * right
            elif isinstance(node.op, ast.Div):
                value = left / right
            else:
                if right.denominator != 1 or not -32 <= right.numerator <= 32:
                    raise CognitionError("bounded integer exponent required")
                value = left ** right.numerator
        else:
            raise CognitionError("only numeric expressions and declared variables are accepted")
        if value.numerator.bit_length() > 2048 or value.denominator.bit_length() > 2048:
            raise CognitionError("exact arithmetic exceeds bit ceiling")
        return value
    return walk(tree.body)


def exact(data, geometry):
    if "polynomial" in data:
        import sympy as sp
        _request(data, required=("polynomial",))
        coefficients = data["polynomial"]
        if not isinstance(coefficients, list) or not 2 <= len(coefficients) <= 5:
            raise CognitionError("polynomial degree must be one to four")
        if number(coefficients[-1]) == 0:
            raise CognitionError("declared polynomial needs a nonzero leading coefficient")
        _work(geometry, 8 * (len(coefficients) - 1)**4)
        x = sp.Symbol("x", real=True)
        expr = sum(sp.Rational(str(number(c))) * x ** i for i, c in enumerate(coefficients))
        intervals = [{"lower": str(lo), "upper": str(hi), "multiplicity": multiplicity}
                     for (lo, hi), multiplicity in sp.Poly(expr, x).intervals(eps=sp.Rational(1, 10**8))]
        # Display only independently checkable root objects, never parse model-
        # generated SymPy expressions. Irrational values remain scoped intervals.
        labels = [row["lower"] if row["lower"] == row["upper"] else f"root in ({row['lower']}, {row['upper']})" for row in intervals]
        out = {"real_roots": sorted(labels),
               "factored": str(sp.factor(expr))}
        return result(out, {"expression": {"polynomial": coefficients}, "result": out, "engine": "SymPy",
                            "solver_version": importlib.metadata.version("sympy"), "input_digest": digest(data),
                            "isolated_real_roots": intervals,
                            "root_representation": "exact rational root or rational interval isolating one real root; multiplicity separate",
                            "domain": "real numbers; coefficients in ascending degree"}, formal="VALID_CONDITIONAL_ON_INPUT")
    value = exact_value(data["expression"], data.get("variables"))
    out = {"exact": str(value), "numerator": value.numerator, "denominator": value.denominator}
    return result(out, {"expression": data["expression"], "variables": data.get("variables", {}), "result": out},
                  formal="VALID_CONDITIONAL_ON_INPUT")


def fermi(data, geometry):
    factors = data["factors"]
    if not isinstance(factors, list) or not 1 <= len(factors) <= 32:
        raise CognitionError("one to 32 named factors required")
    products = [1.0, 1.0, 1.0]
    sensitivities, units, names = {}, {}, set()
    for f in factors:
        name = f["name"]
        if not isinstance(name, str) or not name or name in names:
            raise CognitionError("unique named factors required")
        names.add(name)
        values = [number(f[k], low=0) for k in ("low", "central", "high")]
        if values != sorted(values):
            raise CognitionError("factor bounds must be ordered")
        for i, v in enumerate(values):
            products[i] *= v
            if not math.isfinite(products[i]) or products[i] > 1e100:
                raise CognitionError("estimate exceeds magnitude ceiling")
        sensitivities[name] = (values[2] - values[0]) / max(values[1], 1e-12)
        for unit, exponent in f.get("units", {}).items():
            units[unit] = units.get(unit, 0) + integer(exponent, low=-12, high=12)
    units = {u: e for u, e in units.items() if e}
    if "expected_units" in data and units != data["expected_units"]:
        raise CognitionError("dimensional mismatch")
    out = {"low": products[0], "central": products[1], "high": products[2], "units": units}
    proof = {"decomposition": factors, "assumptions": data.get("assumptions", []), "range": out,
             "sensitivity": sensitivities, "dominant_variable": max(sensitivities, key=sensitivities.get),
             "outside_view_anchor": data.get("outside_view_anchor"),
             "dependence": "interval enclosure; no independence assumption or probabilistic interval",
             "cheapest_evidence": data.get("next_measurement", "measure the dominant uncertain factor")}
    return result(out, proof)


def _model(data, *, integers=False):
    variables, constraints = data["variables"], data["constraints"]
    if not isinstance(variables, dict) or not 1 <= len(variables) <= 64:
        raise CognitionError("bounded named variables required")
    if not isinstance(constraints, list) or len(constraints) > 256:
        raise CognitionError("constraint count exceeds ceiling")
    for name, bounds in variables.items():
        if not name.isidentifier() or len(name) > 64:
            raise CognitionError("invalid variable name")
        if not isinstance(bounds, list) or len(bounds) != 2:
            raise CognitionError("two variable bounds required")
        validator = (lambda v: integer(v, low=-1000000, high=1000000)) if integers else number
        low, high = (validator(x) for x in bounds)
        if low > high:
            raise CognitionError("invalid variable bounds")
    for c in constraints:
        if c["op"] not in ("<=", ">=", "==", "!=") or not set(c["coefficients"]) <= set(variables):
            raise CognitionError("invalid linear constraint")
        for x in [*c["coefficients"].values(), c["rhs"]]:
            (integer(x, low=-1000000, high=1000000) if integers else number(x))
    return variables, constraints


def formal(data, geometry):
    import z3
    variables, constraints = _model(data)
    solver = z3.Solver()
    solver.set(timeout=max(1, int(geometry["latency_limit"] * 800)))
    solver.set(rlimit=geometry["compute_limit"])
    vs = {n: z3.Real(n) for n in variables}
    for n, (low, high) in variables.items():
        solver.add(vs[n] >= z3.RealVal(str(low)), vs[n] <= z3.RealVal(str(high)))
    descriptions = []
    for i, c in enumerate(constraints):
        lhs = sum(z3.RealVal(str(v)) * vs[n] for n, v in c["coefficients"].items())
        rhs = z3.RealVal(str(c["rhs"]))
        expr = {"<=": lambda: lhs <= rhs, ">=": lambda: lhs >= rhs, "==": lambda: lhs == rhs,
                "!=": lambda: lhs != rhs}[c["op"]]()
        solver.assert_and_track(expr, f"constraint_{i}")
        descriptions.append(f"sum({c['coefficients']}) {c['op']} {c['rhs']}")
    status = solver.check()
    out = {"solver_status": str(status).upper(), "solution": {}}
    if status == z3.sat:
        m = solver.model()
        out["solution"] = {n: str(m.eval(v, model_completion=True)) for n, v in vs.items()}
    proof = {"model": {"variables": variables}, "constraints": constraints, "solver_version": z3.get_version_string(),
             "solver_status": out["solver_status"], "reverse_translation": descriptions,
             "unsat_core": [str(v) for v in solver.unsat_core()] if status == z3.unsat else [],
             "formalization_completeness": data.get("formalization_complete", False),
             "unknown_reason": solver.reason_unknown() if status == z3.unknown else None}
    return result(out, proof, status="UNKNOWN" if status == z3.unknown else "ANSWER",
                  formal="UNKNOWN" if status == z3.unknown else "VALID_CONDITIONAL_ON_MODEL")


def optimization(data, geometry):
    from ortools.sat.python import cp_model
    variables, constraints = _model(data, integers=True)
    model = cp_model.CpModel()
    vs = {n: model.new_int_var(*bounds, n) for n, bounds in variables.items()}
    for c in constraints:
        lhs = sum(v * vs[n] for n, v in c["coefficients"].items())
        rhs = c["rhs"]
        model.add({"<=": lambda: lhs <= rhs, ">=": lambda: lhs >= rhs, "==": lambda: lhs == rhs,
                   "!=": lambda: lhs != rhs}[c["op"]]())
    objective = data["objective"]
    if not set(objective["coefficients"]) <= set(vs):
        raise CognitionError("unknown objective variable")
    for v in objective["coefficients"].values():
        integer(v, low=-1000000, high=1000000)
    expr = sum(v * vs[n] for n, v in objective["coefficients"].items())
    if objective["sense"] == "min":
        model.minimize(expr)
    elif objective["sense"] == "max":
        model.maximize(expr)
    else:
        raise CognitionError("objective sense must be min or max")
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = min(geometry["latency_limit"] * .8, number(data.get("solver_budget_seconds", geometry["latency_limit"] * .8), low=0, high=30))
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    status = solver.solve(model)
    feasible = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    out = {"solver_status": solver.status_name(status), "solution": {n: solver.value(v) for n, v in vs.items()} if feasible else {},
           "objective_value": solver.objective_value if feasible else None}
    proof = {"objective": objective, "constraints": constraints, "variables": variables, "solution": out["solution"],
             "solver_status": out["solver_status"], "bound": solver.best_objective_bound if feasible else None,
             "optimality_gap": abs(solver.objective_value - solver.best_objective_bound) if feasible else None,
             "solver_version": importlib.metadata.version("ortools")}
    return result(out, proof, status="ABSTAIN" if status == cp_model.MODEL_INVALID else "UNKNOWN" if status == cp_model.UNKNOWN else "ANSWER",
                  formal="VALID_CONDITIONAL_ON_MODEL" if status in (cp_model.OPTIMAL, cp_model.FEASIBLE, cp_model.INFEASIBLE) else "UNKNOWN")


def graph(data, geometry):
    from .network import shortest
    return shortest(data, geometry)


def bayesian(data, geometry):
    _request(data, required=("alpha", "beta", "successes", "failures"))
    _work(geometry, 12)
    alpha, beta = number(data["alpha"], low=1e-9), number(data["beta"], low=1e-9)
    successes, failures = integer(data["successes"], high=1000000), integer(data["failures"], high=1000000)
    a, b = alpha + successes, beta + failures
    mean = a / (a + b)
    out = {"alpha": a, "beta": b, "mean": mean, "variance": a * b / ((a + b) ** 2 * (a + b + 1))}
    return result(out, _native_source(data, {"prior": {"alpha": alpha, "beta": beta}, "likelihood": "iid Bernoulli observations",
                        "posterior": out, "sensitivity": {"uniform_prior_mean": (successes + 1) / (successes + failures + 2)},
                        "calibration": "unmeasured until outcomes", "assumptions": ["exchangeability", "observation quality"]}))


def causal(data, geometry):
    # Checked Welch uncertainty for a declared randomized two-arm sample. The
    # randomization claim remains an assumption, never inferred from outcomes.
    from statistics import mean, variance
    treated, control = data.get("treated", []), data.get("control", [])
    identified = (data.get("design") == "randomized" and isinstance(treated, list) and isinstance(control, list)
                  and min(len(treated), len(control)) >= 2 and max(len(treated), len(control)) <= 1000
                  and data.get("missingness", "none") == "none" and data.get("selection", "complete") == "complete")
    effect, uncertainty, refutations = None, None, {"randomization_verified": False}
    if identified:
        treated, control = [number(x) for x in treated], [number(x) for x in control]
        effect = mean(treated) - mean(control)
        a, b = variance(treated)/len(treated), variance(control)/len(control)
        se = math.sqrt(a+b)
        # A conservative Chebyshev interval for independent sample means with
        # plug-in variance is only approximate; do not relabel it a valid CI.
        uncertainty = {"standard_error": se, "normal_approximation_95": [effect-1.96*se, effect+1.96*se],
                       "scope": "large-sample approximation using sample variance; small samples may undercover"}
        halves = [mean(treated[i::2])-mean(control[i::2]) for i in (0,1)]
        refutations.update({"split_sample_effects": halves, "selection_bias_sensitivity":
                            {"additive_bias": data.get("bias_range", [-se, se]),
                             "interpretation": "subtract a supplied bias from the estimate; no identification proof"}})
    proof = {"dag": [["random_assignment", "treatment"], ["treatment", "outcome"]],
             "identification_assumptions": ["random assignment", "consistency", "no interference", "complete observations", "independent units"],
             "estimand": data.get("estimand", "difference in mean outcomes in the supplied trial population"),
             "estimate": effect, "treatment": data.get("treatment", "declared two-arm assignment"),
             "outcome": data.get("outcome", "numeric observed response"), "population": data.get("population", "supplied sample only"),
             "confounders": data.get("confounders", []), "refutations": refutations, "uncertainty": uncertainty,
             "missingness": data.get("missingness", "none"), "selection": data.get("selection", "complete"),
             "data": {"digest": __import__("greg.cognition.contracts", fromlist=["digest"]).digest({"treated":treated,"control":control}), "sample_sizes": [len(treated),len(control)]}, "synthetic": data.get("synthetic", False),
             "limits": "conditional randomized sample estimate; no general causal inference or randomization audit"}
    return result({"effect": effect, "identified_conditionally": identified, "uncertainty": uncertainty}, proof,
                  status="ANSWER" if identified else "UNIDENTIFIED",
                  missing=() if identified else ("NON_IDENTIFIABLE: verified randomized design, complete observations and two units per arm required",))


def control(data, geometry):
    _request(data, required=("observed", "target", "correction_limit"), optional=("dt", "kp", "ki", "kd", "state"))
    _work(geometry, 24)
    observed, target = number(data["observed"]), number(data["target"])
    dt = number(data.get("dt", 1), low=.001)
    kp, ki, kd = (number(data.get(k, 0), low=0, high=10000) for k in ("kp", "ki", "kd"))
    error = target - observed
    state = data.get("state", {})
    if not isinstance(state, dict) or set(state) - {"integral", "previous_error"}:
        raise CognitionError("restricted PID state required")
    integral = number(state.get("integral", 0)) + error * dt
    limit = number(data["correction_limit"], low=0)
    raw = kp * error + ki * integral + kd * (error - number(state.get("previous_error", error))) / dt
    correction = min(limit, max(-limit, raw))
    if correction != raw:  # conditional integration anti-windup
        integral = number(state.get("integral", 0))
    out = {"correction": correction, "state": {"integral": integral, "previous_error": error}}
    return result(out, _native_source(data, {"target": target, "error": error, "correction": correction, "state": out["state"],
                        "stability_limit": "clamped numeric proposal only; no plant stability or actuation authority"}))


def information(data, geometry):
    _request(data, required=("posterior_scenarios", "prior_best_value", "cost"))
    scenarios = data["posterior_scenarios"]
    if not isinstance(scenarios, list) or not 1 <= len(scenarios) <= 512:
        raise CognitionError("one to 512 decision-value scenarios required")
    for scenario in scenarios:
        _request(scenario, required=("probability", "best_value"))
    _work(geometry, 4 * len(scenarios) + 4)
    probabilities = [number(s["probability"], low=0, high=1) for s in scenarios]
    if not math.isclose(sum(probabilities), 1.0, rel_tol=0, abs_tol=1e-9):
        raise CognitionError("scenario probabilities must sum to one")
    prior = number(data["prior_best_value"])
    gross = sum(p * number(s["best_value"]) for p, s in zip(probabilities, scenarios)) - prior
    cost = number(data["cost"], low=0)
    out = {"net_value": gross - cost, "acquire": gross > cost, "gross_value": gross}
    return result(out, _native_source(data, {"prior": prior, "posterior_scenarios": scenarios, "expected_value": gross, "cost": cost,
                                          "limits": "declared decision values, probabilities and costs; no empirical calibration"}))


def simulation(data, geometry):
    _request(data, required=("seed", "samples", "steps", "step_probability"))
    rng = random.Random(integer(data["seed"], high=2147483647))
    count = integer(data["samples"], low=1, high=10000)
    steps = integer(data["steps"], low=1, high=1000)
    _work(geometry, count * steps)
    probability = number(data["step_probability"], low=0, high=1)
    scenarios = [sum(rng.random() < probability for _ in range(steps)) for _ in range(count)]
    out = {"mean": sum(scenarios) / count, "minimum": min(scenarios), "maximum": max(scenarios)}
    return result(out, _native_source(data, {"model": "iid Bernoulli steps", "seed": data["seed"], "scenarios": scenarios[:100],
                        "samples": count, "scenario_digest": digest(scenarios), "scenario_prefix_only": count > 100,
                        "model_validity": "uncalibrated against reality; seeded numeric scenarios are simulated evidence"}))


def game(data, geometry):
    from scipy.optimize import linprog
    import numpy as np
    _request(data, required=("payoffs",), optional=("solver_budget_seconds",))
    matrix = data["payoffs"]
    if not isinstance(matrix, list) or not matrix or len(matrix) > 32 or any(not isinstance(row, list) for row in matrix) or not matrix[0] or len(matrix[0]) > 32 or any(len(row) != len(matrix[0]) for row in matrix):
        raise CognitionError("bounded rectangular payoff matrix required")
    _work(geometry, 2 * len(matrix) * len(matrix[0]) * (len(matrix) + len(matrix[0])))
    a = np.array([[number(x) for x in row] for row in matrix])
    count = len(a)
    seconds = min(number(data.get("solver_budget_seconds", 30), low=0, high=30),
                  number(geometry["latency_limit"], low=.001, high=30) * .35)
    native_names = {0: "OPTIMAL", 1: "LIMIT_REACHED", 2: "INFEASIBLE", 3: "UNBOUNDED", 4: "SOLVER_ERROR"}
    if not seconds:
        return result({"solver_status": "NOT_SOLVED"}, _native_source(data, {"payoffs": matrix, "strategies": [], "value": None,
                      "constraints": "zero-sum simplex", "native_statuses": ["NOT_SOLVED", "NOT_SOLVED"]}), status="UNKNOWN", formal="UNKNOWN", missing=("SOLVER_UNKNOWN: zero solver budget",))
    lp = linprog([0] * count + [-1], A_ub=np.column_stack((-a.T, np.ones(a.shape[1]))),
                 b_ub=np.zeros(a.shape[1]), A_eq=[[1] * count + [0]], b_eq=[1],
                 bounds=[(0, 1)] * count + [(None, None)], method="highs", options={"time_limit": seconds, "maxiter": geometry["compute_limit"]})
    # A second, dual numerical candidate supplies a checkable minimax bound.
    columns = a.shape[1]
    dual = linprog([0] * columns + [1], A_ub=np.column_stack((a, -np.ones(count))),
                   b_ub=np.zeros(count), A_eq=[[1] * columns + [0]], b_eq=[1],
                   bounds=[(0, 1)] * columns + [(None, None)], method="highs", options={"time_limit": seconds, "maxiter": geometry["compute_limit"]})
    native = [native_names.get(lp.status, "SOLVER_ERROR"), native_names.get(dual.status, "SOLVER_ERROR")]
    if not lp.success or not dual.success:
        return result({"solver_status": native[0]}, _native_source(data, {"payoffs": matrix, "strategies": [], "value": None,
                      "constraints": "zero-sum simplex", "native_statuses": native}), status="UNKNOWN", formal="UNKNOWN",
                      missing=("SOLVER_UNKNOWN: an independently checkable primal and dual candidate is required",))
    out = {"mixed_strategy": lp.x[:count].tolist(), "value": float(lp.x[-1]), "solver_status": "OPTIMAL"}
    return result(out, _native_source(data, {"payoffs": matrix, "strategies": out["mixed_strategy"], "value": out["value"],
                        "opponent_strategy": dual.x[:columns].tolist(), "native_statuses": native,
                        "solver_version": importlib.metadata.version("scipy"), "solver_limits": {"per_program_seconds": seconds, "iterations": geometry["compute_limit"]},
                        "constraints": "two-player finite zero-sum game; payoff validity unverified; numerical bound tolerance relative 1e-7"}))


def pattern(data, geometry):
    _request(data, required=("observations",), optional=("threshold",))
    if not isinstance(data["observations"], list) or not 3 <= len(data["observations"]) <= 1000:
        raise CognitionError("3 to 1000 observations required")
    _work(geometry, 5 * len(data["observations"]))
    values = [number(x) for x in data["observations"]]
    if len(values) < 3:
        raise CognitionError("at least three observations required")
    mean = sum(values) / len(values)
    sd = math.sqrt(sum((x - mean) ** 2 for x in values) / len(values))
    scores = [(x - mean) / sd if sd else 0 for x in values]
    threshold = number(data.get("threshold", 2), low=0, high=10)
    out = {"anomalies": [i for i, x in enumerate(scores) if abs(x) >= threshold], "mean": mean, "sd": sd}
    return result(out, _native_source(data, {"observations": values, "model": "population z-score", "scores": scores,
                        "limits": "descriptive statistic; nonstationarity and contamination may mask anomalies"}))


def micro(data, geometry):
    _request(data, required=("observed", "low", "high"))
    _work(geometry, 3)
    observed = number(data["observed"])
    low, high = number(data["low"]), number(data["high"])
    if low > high:
        raise CognitionError("ordered set-point bounds required")
    out = {"state": "stimulate" if observed < low else "inhibit" if observed > high else "abstain"}
    return result(out, _native_source(data, {"observations": [observed], "model": {"low": low, "high": high}, "scores": [out["state"]],
                        "limits": "ternary set-point rule only; no consequence execution"}))


def sequential(data, geometry):
    # Finite-horizon fully observed MDP: backward induction, no open-world RL claim.
    _request(data, required=("transitions", "rewards", "horizon"), optional=("discount",))
    transitions, rewards = data["transitions"], data["rewards"]
    if not isinstance(transitions, dict) or not isinstance(rewards, dict) or set(transitions) != set(rewards):
        raise CognitionError("MDP states must have matching transition and reward maps")
    states = list(transitions)
    if any(not isinstance(s, str) or not 1 <= len(s) <= 64 for s in states):
        raise CognitionError("bounded MDP state names required")
    horizon = integer(data["horizon"], low=1, high=100)
    gamma = number(data.get("discount", 1), low=0, high=1)
    count = sum(len(actions) * len(states) for actions in transitions.values()) * horizon
    if not states or len(states) > 128 or count > geometry["compute_limit"]:
        raise CognitionError("BUDGET_EXHAUSTED: MDP operation budget exceeded")
    for state, actions in transitions.items():
        if not isinstance(actions, dict) or not actions or not isinstance(rewards[state], dict) or set(actions) != set(rewards[state]):
            raise CognitionError("MDP actions must have matching transition and reward maps")
        if any(not isinstance(a, str) or not 1 <= len(a) <= 64 for a in actions):
            raise CognitionError("bounded MDP action names required")
        for action, distribution in actions.items():
            if not isinstance(distribution, dict) or not distribution or set(distribution) - set(states):
                raise CognitionError("MDP transitions must name existing states")
            probabilities = [number(p, low=0, high=1) for p in distribution.values()]
            if not math.isclose(sum(probabilities), 1, rel_tol=0, abs_tol=1e-9):
                raise CognitionError("MDP transition probabilities must sum to one")
            number(rewards[state][action])
    values, policy, trace, value_trace = dict.fromkeys(states, 0.0), {}, [], []
    for _ in range(horizon):
        next_values = {}
        for state, actions in transitions.items():
            scores = {}
            for action, distribution in actions.items():
                scores[action] = number(rewards[state][action]) + gamma * sum(
                    number(p, low=0, high=1) * values[s] for s, p in distribution.items())
            if not scores:
                raise CognitionError("MDP state has no action")
            action = max(sorted(scores), key=scores.get)
            next_values[state], policy[state] = scores[action], action
        values = next_values
        trace.append(dict(policy))
        value_trace.append(dict(values))
    out = {"values": values, "policy": policy}
    return result(out, {"states": states, "path": trace, "cost": None, "model": data,
                        "value_trace": value_trace, "input_digest": digest(data),
                        "limits": "fully observed finite-horizon supplied model; no learned policy or external action"})


def human(data, geometry):
    _request(data, required=(), optional=("participants", "expertise", "conflicts", "dissent", "decision_authority"))
    _work(geometry, 5)
    required = ("participants", "expertise", "conflicts", "dissent", "decision_authority")
    proof = {k: data.get(k) for k in required}
    # Recording a panel does not authenticate participants or confer their authority.
    return result({"panel": proof, "decision": None}, _native_source(data, proof), status="HUMAN_REVIEW_REQUIRED",
                  missing=("authenticated qualified human judgment through existing authority path",))


def quorum(data, geometry):
    _request(data, required=("observations",), optional=("minimum_independent", "threshold"))
    observations = data["observations"]
    if not isinstance(observations, list) or len(observations) > 100:
        raise CognitionError("at most 100 declared quorum observations required")
    _work(geometry, 5 * len(observations) + 5)
    ids, groups, scores, dissent = set(), set(), {}, []
    for observation in observations:
        _request(observation, required=("observer_id", "independence_group", "choice", "weight"), optional=("reason",))
        identity, group = observation["observer_id"], observation["independence_group"]
        if any(not isinstance(v, str) or not 1 <= len(v) <= 128 for v in (identity, group, observation["choice"])):
            raise CognitionError("bounded quorum identities, group labels and choices required")
        if "reason" in observation and (not isinstance(observation["reason"], str) or len(observation["reason"]) > 512):
            raise CognitionError("bounded quorum dissent required")
        if identity in ids or group in groups:
            raise CognitionError("quorum cannot count duplicate or correlated observers as independent")
        ids.add(identity)
        groups.add(group)
        weight = number(observation["weight"], low=0, high=1)
        choice = observation["choice"]
        scores[choice] = scores.get(choice, 0) + weight
        dissent.append({"observer_id": identity, "choice": choice, "reason": observation.get("reason", "unsupplied")})
    minimum = integer(data.get("minimum_independent", 3), low=2, high=100)
    threshold = number(data.get("threshold", .7), low=.5, high=1)
    total = sum(scores.values())
    winner = max(sorted(scores), key=scores.get) if scores else None
    crossed = bool(winner is not None and len(groups) >= minimum and total > 0 and scores[winner] / total >= threshold)
    out = {"choice": winner if crossed else None, "quorum_crossed": crossed, "scores": scores}
    return result(out, _native_source(data, {"participants": sorted(ids), "independence": sorted(groups), "dissent": dissent,
                        "trace": out, "baseline_status": "not compared against strongest individual or ordinary committee",
                        "independence_authentication": "unverified group labels; no empirical independence or truth established"}),
                  status="ANSWER" if crossed else "NO_QUORUM")


def evolutionary(data, geometry):
    from scipy.optimize import differential_evolution
    _request(data, required=("center", "bounds", "seed"), optional=("generations", "population"))
    if not isinstance(data["center"], list) or not isinstance(data["bounds"], list):
        raise CognitionError("vector center and bounds lists required")
    center = [number(v) for v in data["center"]]
    bounds = data["bounds"]
    generations = integer(data.get("generations", 5), low=1, high=100)
    population = integer(data.get("population", 5), low=2, high=20)
    if not center or len(center) > 16 or len(center) != len(bounds):
        raise CognitionError("bounded quadratic target and matching bounds required")
    for pair in bounds:
        if not isinstance(pair, list) or len(pair) != 2:
            raise CognitionError("two finite bounds per evolutionary variable required")
        low, high = pair
        if number(low) >= number(high):
            raise CognitionError("ordered evolutionary bounds required")
    # SciPy enforces a minimum of five individuals even for popsize=2, dim=1.
    # Count the objective's arithmetic as well as calls before launching search.
    evaluation_ceiling = (generations + 1) * max(5, population * len(center))
    _work(geometry, evaluation_ceiling * (4 * len(center) + 1))
    trace = []
    def evaluate(candidate):
        return sum((number(float(v)) - c) ** 2 for v, c in zip(candidate, center))
    def retain(candidate, convergence):
        trace.append({"candidate": candidate.tolist(), "fitness": evaluate(candidate)})
    optimum = differential_evolution(evaluate, bounds, maxiter=generations, popsize=population,
                                    seed=integer(data["seed"], high=2147483647), callback=retain, polish=False,
                                    workers=1, tol=0)
    out = {"candidate": optimum.x.tolist(), "fitness": float(optimum.fun), "evaluations": optimum.nfev}
    analytic = [min(hi, max(lo, c)) for c, (lo, hi) in zip(center, bounds)]
    return result(out, _native_source(data, {"participants": "bounded vector population", "independence": "one seeded search",
                        "dissent": [], "trace": trace, "baseline_status": "analytic quadratic minimum is the stronger baseline",
                        "evaluator": "fixed squared-distance function, no generated code or authority",
                        "solver_version": importlib.metadata.version("scipy"), "evaluation_ceiling": evaluation_ceiling,
                        "analytic_baseline": {"candidate": analytic, "fitness": evaluate(analytic)},
                        "limits": "candidate search only, not claimed optimum, new algorithm or capability generation"}))


SOLVERS = {"evidence": __import__("greg.cognition.evidence", fromlist=["assess"]).assess, "exact": exact, "estimation": fermi, "formal": formal, "optimization": optimization,
           "graph": graph, "search": graph, "probabilistic": bayesian, "causal": causal,
           "control": control, "information": information, "simulation": simulation, "game": game,
           "pattern": pattern, "micro": micro, "sequential": sequential, "human": human}
SOLVERS.update({"collective": quorum, "evolutionary": evolutionary})
from .protection import assess as protection
SOLVERS["protection"] = protection
SOLVERS.update({"flow": __import__("greg.cognition.network", fromlist=["max_flow"]).max_flow,
                "linear": __import__("greg.cognition.linear", fromlist=["solve"]).solve})
