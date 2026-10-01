"""Pure, bounded solver adapters. Library engines are lazy; no input becomes code."""
from __future__ import annotations

import ast
from fractions import Fraction
import importlib.metadata
import math
import random

from .contracts import CognitionError, integer, number


def result(output, proof, *, status="ANSWER", formal="NOT_APPLICABLE", missing=()):
    return {"output": output, "proof": proof, "status": status, "formal_validity": formal,
            "missing_information": list(missing), "empirical_validity": "WORLD_UNVERIFIED"}


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
        coefficients = data["polynomial"]
        if not isinstance(coefficients, list) or not 2 <= len(coefficients) <= 5:
            raise CognitionError("polynomial degree must be one to four")
        x = sp.Symbol("x", real=True)
        expr = sum(sp.Rational(str(number(c))) * x ** i for i, c in enumerate(coefficients))
        roots = sp.solveset(expr, x, domain=sp.S.Reals)
        out = {"real_roots": sorted(str(v) for v in roots) if isinstance(roots, sp.FiniteSet) else str(roots),
               "factored": str(sp.factor(expr))}
        return result(out, {"expression": {"polynomial": coefficients}, "result": out, "engine": "SymPy",
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
    import networkx as nx
    g = nx.DiGraph() if data.get("directed", True) else nx.Graph()
    edges = data["edges"]
    if not isinstance(edges, list) or len(edges) > min(10000, geometry["compute_limit"]):
        raise CognitionError("graph edge budget exceeded")
    for edge in edges:
        if len(edge) != 3 or any(not isinstance(n, str) for n in edge[:2]):
            raise CognitionError("edges require two string nodes and nonnegative cost")
        g.add_edge(edge[0], edge[1], weight=number(edge[2], low=0))
    try:
        path = nx.shortest_path(g, data["start"], data["goal"], weight="weight")
        cost = nx.path_weight(g, path, "weight")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        path, cost = [], None
    out = {"path": path, "cost": cost, "reachable": bool(path)}
    return result(out, {"states": list(g.nodes), "path": path, "cost": cost, "model": data,
                        "engine": "networkx.dijkstra", "limits": "nonnegative weights; supplied topology only"})


def bayesian(data, geometry):
    alpha, beta = number(data["alpha"], low=1e-9), number(data["beta"], low=1e-9)
    successes, failures = integer(data["successes"], high=1000000), integer(data["failures"], high=1000000)
    a, b = alpha + successes, beta + failures
    mean = a / (a + b)
    out = {"alpha": a, "beta": b, "mean": mean, "variance": a * b / ((a + b) ** 2 * (a + b + 1))}
    return result(out, {"prior": {"alpha": alpha, "beta": beta}, "likelihood": "iid Bernoulli observations",
                        "posterior": out, "sensitivity": {"uniform_prior_mean": (successes + 1) / (successes + failures + 2)},
                        "calibration": "unmeasured until outcomes", "assumptions": ["exchangeability", "observation quality"]})


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
    observed, target = number(data["observed"]), number(data["target"])
    dt = number(data.get("dt", 1), low=.001)
    kp, ki, kd = (number(data.get(k, 0), low=0, high=10000) for k in ("kp", "ki", "kd"))
    error = target - observed
    state = data.get("state", {})
    integral = number(state.get("integral", 0)) + error * dt
    limit = number(data["correction_limit"], low=0)
    raw = kp * error + ki * integral + kd * (error - number(state.get("previous_error", error))) / dt
    correction = min(limit, max(-limit, raw))
    if correction != raw:  # conditional integration anti-windup
        integral = number(state.get("integral", 0))
    out = {"correction": correction, "state": {"integral": integral, "previous_error": error}}
    return result(out, {"target": target, "error": error, "correction": correction, "state": out["state"],
                        "stability_limit": "clamped output; plant stability unproven without a plant model"})


def information(data, geometry):
    scenarios = data["posterior_scenarios"]
    probabilities = [number(s["probability"], low=0, high=1) for s in scenarios]
    if not math.isclose(sum(probabilities), 1.0, abs_tol=1e-9):
        raise CognitionError("scenario probabilities must sum to one")
    prior = number(data["prior_best_value"])
    gross = sum(p * number(s["best_value"]) for p, s in zip(probabilities, scenarios)) - prior
    cost = number(data["cost"], low=0)
    out = {"net_value": gross - cost, "acquire": gross > cost, "gross_value": gross}
    return result(out, {"prior": prior, "posterior_scenarios": scenarios, "expected_value": gross, "cost": cost})


def simulation(data, geometry):
    rng = random.Random(integer(data["seed"], high=2147483647))
    count = integer(data["samples"], low=1, high=min(10000, geometry["compute_limit"]))
    steps = integer(data["steps"], low=1, high=1000)
    if count * steps > geometry["compute_limit"]:
        raise CognitionError("simulation operation budget exceeded")
    probability = number(data["step_probability"], low=0, high=1)
    scenarios = [sum(rng.random() < probability for _ in range(steps)) for _ in range(count)]
    out = {"mean": sum(scenarios) / count, "minimum": min(scenarios), "maximum": max(scenarios)}
    return result(out, {"model": "iid Bernoulli steps", "seed": data["seed"], "scenarios": scenarios[:100],
                        "samples": count, "model_validity": "uncalibrated against reality"})


def game(data, geometry):
    from scipy.optimize import linprog
    import numpy as np
    matrix = data["payoffs"]
    if not matrix or len(matrix) > 32 or not matrix[0] or len(matrix[0]) > 32 or any(len(row) != len(matrix[0]) for row in matrix):
        raise CognitionError("bounded rectangular payoff matrix required")
    a = np.array([[number(x) for x in row] for row in matrix])
    count = len(a)
    lp = linprog([0] * count + [-1], A_ub=np.column_stack((-a.T, np.ones(a.shape[1]))),
                 b_ub=np.zeros(a.shape[1]), A_eq=[[1] * count + [0]], b_eq=[1],
                 bounds=[(0, 1)] * count + [(None, None)], method="highs")
    if not lp.success:
        return result({}, {"payoffs": matrix, "strategies": [], "value": None, "constraints": "zero-sum simplex"}, status="UNKNOWN")
    out = {"mixed_strategy": lp.x[:count].tolist(), "value": float(lp.x[-1])}
    return result(out, {"payoffs": matrix, "strategies": out["mixed_strategy"], "value": out["value"],
                        "constraints": "two-player finite zero-sum game; payoff validity unverified"})


def pattern(data, geometry):
    values = [number(x) for x in data["observations"]]
    if len(values) < 3:
        raise CognitionError("at least three observations required")
    mean = sum(values) / len(values)
    sd = math.sqrt(sum((x - mean) ** 2 for x in values) / len(values))
    scores = [(x - mean) / sd if sd else 0 for x in values]
    threshold = number(data.get("threshold", 2), low=0, high=10)
    out = {"anomalies": [i for i, x in enumerate(scores) if abs(x) >= threshold], "mean": mean, "sd": sd}
    return result(out, {"observations": values, "model": "population z-score", "scores": scores,
                        "limits": "descriptive statistic; nonstationarity and contamination may mask anomalies"})


def micro(data, geometry):
    observed = number(data["observed"])
    low, high = number(data["low"]), number(data["high"])
    if low > high:
        raise CognitionError("ordered set-point bounds required")
    out = {"state": "stimulate" if observed < low else "inhibit" if observed > high else "abstain"}
    return result(out, {"observations": [observed], "model": {"low": low, "high": high}, "scores": [out["state"]],
                        "limits": "ternary set-point rule only; no consequence execution"})


def sequential(data, geometry):
    # Finite-horizon fully observed MDP: backward induction, no open-world RL claim.
    transitions, rewards = data["transitions"], data["rewards"]
    states = list(transitions)
    horizon = integer(data["horizon"], low=1, high=100)
    gamma = number(data.get("discount", 1), low=0, high=1)
    count = sum(len(actions) * len(states) for actions in transitions.values()) * horizon
    if not states or len(states) > 128 or count > geometry["compute_limit"]:
        raise CognitionError("MDP operation budget exceeded")
    values, policy, trace = dict.fromkeys(states, 0.0), {}, []
    for _ in range(horizon):
        next_values = {}
        for state, actions in transitions.items():
            scores = {}
            for action, distribution in actions.items():
                if set(distribution) - set(states) or not math.isclose(sum(distribution.values()), 1, abs_tol=1e-9):
                    raise CognitionError("MDP transition probabilities must sum to one")
                scores[action] = number(rewards[state][action]) + gamma * sum(
                    number(p, low=0, high=1) * values[s] for s, p in distribution.items())
            if not scores:
                raise CognitionError("MDP state has no action")
            action = max(sorted(scores), key=scores.get)
            next_values[state], policy[state] = scores[action], action
        values = next_values
        trace.append(dict(policy))
    out = {"values": values, "policy": policy}
    return result(out, {"states": states, "path": trace, "cost": None, "model": data})


def human(data, geometry):
    required = ("participants", "expertise", "conflicts", "dissent", "decision_authority")
    proof = {k: data.get(k) for k in required}
    # Recording a panel does not authenticate participants or confer their authority.
    return result({"panel": proof, "decision": None}, proof, status="HUMAN_REVIEW_REQUIRED",
                  missing=("authenticated qualified human judgment through existing authority path",))


def quorum(data, geometry):
    observations = data["observations"]
    ids, groups, scores, dissent = set(), set(), {}, []
    for observation in observations:
        identity, group = observation["observer_id"], observation["independence_group"]
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
    return result(out, {"participants": sorted(ids), "independence": sorted(groups), "dissent": dissent,
                        "trace": out, "baseline_status": "not compared against strongest individual or ordinary committee"},
                  status="ANSWER" if crossed else "NO_QUORUM")


def evolutionary(data, geometry):
    from scipy.optimize import differential_evolution
    center = [number(v) for v in data["center"]]
    bounds = data["bounds"]
    generations = integer(data.get("generations", 5), low=1, high=100)
    population = integer(data.get("population", 5), low=2, high=20)
    if not center or len(center) > 16 or len(center) != len(bounds):
        raise CognitionError("bounded quadratic target and matching bounds required")
    for low, high in bounds:
        if number(low) >= number(high):
            raise CognitionError("ordered evolutionary bounds required")
    if (generations + 1) * population * len(center) > geometry["compute_limit"]:
        raise CognitionError("evolutionary evaluation budget exceeded")
    trace = []
    def evaluate(candidate):
        return sum((number(float(v)) - c) ** 2 for v, c in zip(candidate, center))
    def retain(candidate, convergence):
        trace.append({"candidate": candidate.tolist(), "fitness": evaluate(candidate)})
    optimum = differential_evolution(evaluate, bounds, maxiter=generations, popsize=population,
                                    seed=integer(data["seed"], high=2147483647), callback=retain, polish=False,
                                    workers=1, tol=0)
    out = {"candidate": optimum.x.tolist(), "fitness": float(optimum.fun), "evaluations": optimum.nfev}
    return result(out, {"participants": "bounded vector population", "independence": "one seeded search",
                        "dissent": [], "trace": trace, "baseline_status": "analytic quadratic minimum is the stronger baseline",
                        "evaluator": "fixed squared-distance function, no generated code or authority"})


SOLVERS = {"evidence": __import__("greg.cognition.evidence", fromlist=["assess"]).assess, "exact": exact, "estimation": fermi, "formal": formal, "optimization": optimization,
           "graph": graph, "search": graph, "probabilistic": bayesian, "causal": causal,
           "control": control, "information": information, "simulation": simulation, "game": game,
           "pattern": pattern, "micro": micro, "sequential": sequential, "human": human}
SOLVERS.update({"collective": quorum, "evolutionary": evolutionary})
from .protection import assess as protection
SOLVERS["protection"] = protection
