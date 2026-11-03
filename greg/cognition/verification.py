"""Independent falsifier over emitted artifacts; it has no authority or effect adapter."""
from __future__ import annotations

from fractions import Fraction
import math

from .contracts import CognitionError, ProofArtifact, digest


def _close(actual, expected):
    """A reported number agrees with an exact recomputation; booleans and strings never do."""
    return (isinstance(actual, (int, float)) and not isinstance(actual, bool)
            and math.isclose(float(actual), float(expected), rel_tol=1e-9, abs_tol=1e-9))


def verify(family, data, answer, proof_class):
    checks, dissent = {}, []
    ProofArtifact(proof_class, answer["proof"]).validate()
    checks["typed_artifact"] = True
    output = answer["output"]
    if family == "exact" and "polynomial" not in data:
        # A separately parsed Decimal evaluator attacks the Fraction solver.
        import ast
        from decimal import Decimal, localcontext
        def walk(node):
            if isinstance(node, ast.Constant):
                return Decimal(str(node.value))
            if isinstance(node, ast.Name):
                return Decimal(str(data.get("variables", {})[node.id]))
            if isinstance(node, ast.UnaryOp):
                return walk(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
            left, right = walk(node.left), walk(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.Pow):
                return left ** int(right)
            raise CognitionError("unsupported independent arithmetic")
        with localcontext() as context:
            context.prec = 100
            expected = walk(ast.parse(data["expression"], mode="eval").body)
            actual = Decimal(output["numerator"]) / Decimal(output["denominator"])
            checks["independent_arithmetic"] = abs(expected - actual) <= Decimal("1e-90") * max(Decimal(1), abs(expected))
        checks["exact_matches_ratio"] = Fraction(output["exact"]) == Fraction(int(output["numerator"]), int(output["denominator"]))
    elif family == "exact":
        # Roots are re-checked by substitution at 50 digits and the factored form by expansion;
        # neither repeats the solver's solveset.
        import sympy as sp
        x = sp.Symbol("x", real=True)
        expr = sum(sp.Rational(str(c)) * x ** i for i, c in enumerate(data["polynomial"]))
        roots = output["real_roots"]
        if isinstance(roots, list):
            checks["root_count_bounded"] = len(roots) < len(data["polynomial"])
            checks["roots_satisfy_polynomial"] = all(
                abs(expr.subs(x, sp.sympify(r)).evalf(50)) < sp.Float("1e-40") for r in roots)
        else:
            checks["root_set_recognized"] = roots in ("EmptySet", "Reals")
        checks["factored_form_expands_back"] = sp.expand(sp.sympify(output["factored"], locals={"x": x}) - expr) == 0
    elif family in ("formal", "optimization") and output["solver_status"] in ("SAT", "OPTIMAL", "FEASIBLE"):
        values = {n: Fraction(str(v)) for n, v in output["solution"].items()}
        checks["bounded_solution"] = all(Fraction(str(lo)) <= values[n] <= Fraction(str(hi)) for n, (lo, hi) in data["variables"].items())
        valid = True
        for c in data["constraints"]:
            lhs = sum(Fraction(str(co)) * values[n] for n, co in c["coefficients"].items())
            rhs = Fraction(str(c["rhs"]))
            valid &= {"<=": lhs <= rhs, ">=": lhs >= rhs, "==": lhs == rhs, "!=": lhs != rhs}[c["op"]]
        checks["constraint_substitution"] = bool(valid)
        if family == "optimization":
            objective = sum(c * values[n] for n, c in data["objective"]["coefficients"].items())
            checks["objective_substitution"] = math.isclose(float(objective), output["objective_value"], abs_tol=1e-6)
    elif family in ("formal", "optimization"):
        # No solution was reported: the status must be one the engines can emit and the solution empty.
        checks["known_status"] = (output["solver_status"] in ("UNSAT", "UNKNOWN", "INFEASIBLE", "MODEL_INVALID")
                                  and output["solution"] == {})
    elif family in ("graph", "search"):
        # GREG's own Dijkstra (greg/cognition/network.py) shares no code with NetworkX. It refutes a
        # valid but longer path and a false "no path", which form checks alone let through.
        from .network import local_dijkstra
        nodes = {n for a, b, _ in data["edges"] for n in (a, b)}
        best = local_dijkstra({"edges": data["edges"], "directed": data.get("directed", True),
                               "source": data["start"]})["distances"] if data["start"] in nodes else {}
        if output["reachable"]:
            edges = {}
            for a, b, w in data["edges"]:
                for key in ([(a, b)] if data.get("directed", True) else [(a, b), (b, a)]):
                    edges[key] = min(edges.get(key, w), w)
            path = output["path"]
            checks["path_endpoints"] = path[0] == data["start"] and path[-1] == data["goal"]
            checks["path_edges"] = all((a, b) in edges for a, b in zip(path, path[1:]))
            checks["path_cost"] = checks["path_edges"] and math.isclose(sum(edges[a, b] for a, b in zip(path, path[1:])), output["cost"])
            checks["path_optimal"] = data["goal"] in best and math.isclose(output["cost"], best[data["goal"]],
                                                                            rel_tol=1e-9, abs_tol=1e-12)
        else:
            checks["unreachable_confirmed"] = data["goal"] not in best
    elif family == "game" and output:
        # Minimax certificate: the row strategy guarantees at least the value against every column and
        # the column strategy concedes at most the value against every row. Exact fractions; a relative
        # 1e-9 allows the solver's floating point. A missing column strategy is a failed check.
        a = [[Fraction(str(x)) for x in row] for row in data["payoffs"]]
        p, q = ([Fraction(x) for x in output.get(k, [])] for k in ("mixed_strategy", "column_strategy"))
        v, tol = Fraction(output["value"]), Fraction(1, 10**9) * (1 + max(abs(x) for row in a for x in row))
        checks["strategies_are_distributions"] = (len(p) == len(a) and len(q) == len(a[0])
                                                  and all(x >= -tol for x in p + q)
                                                  and abs(sum(p) - 1) <= tol and abs(sum(q) - 1) <= tol)
        checks["row_guarantee"] = checks["strategies_are_distributions"] and min(
            sum(pi * a[i][j] for i, pi in enumerate(p)) for j in range(len(a[0]))) >= v - tol
        checks["column_guarantee"] = checks["strategies_are_distributions"] and max(
            sum(a[i][j] * qj for j, qj in enumerate(q)) for i in range(len(a))) <= v + tol
    elif family == "probabilistic":
        # Beta-Bernoulli conjugacy, recomputed independently in exact fractions.
        a = Fraction(str(data["alpha"])) + int(data["successes"])
        b = Fraction(str(data["beta"])) + int(data["failures"])
        checks["posterior_conjugate"] = (math.isclose(output["alpha"], float(a), rel_tol=1e-12)
                                         and math.isclose(output["beta"], float(b), rel_tol=1e-12))
        checks["posterior_mean"] = math.isclose(output["mean"], float(a / (a + b)), rel_tol=1e-12)
        checks["posterior_variance"] = math.isclose(output["variance"], float(a * b / ((a + b) ** 2 * (a + b + 1))),
                                                    rel_tol=1e-12)
        dissent.append("Conjugacy is exact; exchangeability and observation quality are assumptions.")
    elif family == "estimation":
        # Interval products and unit exponents recomputed in exact fractions.
        bounds, units = [Fraction(1)] * 3, {}
        for factor in data["factors"]:
            for i, key in enumerate(("low", "central", "high")):
                bounds[i] *= Fraction(str(factor[key]))
            for unit, exponent in factor.get("units", {}).items():
                units[unit] = units.get(unit, 0) + int(exponent)
        checks["ordered_range"] = output["low"] <= output["central"] <= output["high"]
        checks["interval_products"] = all(_close(output[k], b) for k, b in zip(("low", "central", "high"), bounds))
        checks["units_resummed"] = output["units"] == {u: e for u, e in units.items() if e}
        dissent.append("Bounds are assumptions; no calibrated probability or external market proof follows.")
    elif family == "causal":
        treated, control = data.get("treated", []), data.get("control", [])
        identified = data.get("design") == "randomized" and bool(treated) and bool(control)
        checks["identification_flag"] = (isinstance(output["identified_conditionally"], bool)
                                         and output["identified_conditionally"] == identified)
        if identified:
            effect = (sum(Fraction(str(v)) for v in treated) / len(treated)
                      - sum(Fraction(str(v)) for v in control) / len(control))
            checks["difference_in_means"] = _close(output["effect"], effect)
        else:
            checks["no_effect_without_identification"] = output["effect"] is None
        dissent.append("Randomization and identification assumptions have not been independently established in reality.")
    elif family == "control":
        observed, target = Fraction(str(data["observed"])), Fraction(str(data["target"]))
        dt = Fraction(str(data.get("dt", 1)))
        kp, ki, kd = (Fraction(str(data.get(k, 0))) for k in ("kp", "ki", "kd"))
        state, limit = data.get("state", {}), Fraction(str(data["correction_limit"]))
        error, prior = target - observed, Fraction(str(state.get("integral", 0)))
        integral = prior + error * dt
        raw = kp * error + ki * integral + kd * (error - Fraction(str(state.get("previous_error", error)))) / dt
        correction = min(limit, max(-limit, raw))
        if correction != raw:              # the solver's conditional-integration anti-windup
            integral = prior
        checks["clamped_pid_law"] = _close(output["correction"], correction)
        checks["controller_state"] = (_close(output["state"]["integral"], integral)
                                      and _close(output["state"]["previous_error"], error))
        dissent.append("Clamped output recomputed; plant stability is unproven without a plant model.")
    elif family == "information":
        gross = (sum(Fraction(str(s["probability"])) * Fraction(str(s["best_value"])) for s in data["posterior_scenarios"])
                 - Fraction(str(data["prior_best_value"])))
        cost = Fraction(str(data["cost"]))
        checks["expected_value_of_information"] = _close(output["gross_value"], gross) and _close(output["net_value"], gross - cost)
        checks["acquire_rule"] = isinstance(output["acquire"], bool) and output["acquire"] == (gross > cost)
        dissent.append("Scenario probabilities and values are supplied beliefs, not measured frequencies.")
    elif family == "simulation":
        steps, samples = int(data["steps"]), int(data["samples"])
        scenarios = answer["proof"].get("scenarios", [])
        mean, low, high = output["mean"], output["minimum"], output["maximum"]
        checks["moments_consistent"] = (0 <= low <= mean <= high <= steps and _close(mean * samples, round(mean * samples)))
        if len(scenarios) == samples:
            checks["moments_recomputed"] = (_close(mean, Fraction(sum(scenarios), samples))
                                            and low == min(scenarios) and high == max(scenarios))
        dissent.append("Seeded iid model; the moments are recomputed, calibration against reality is not.")
    elif family == "pattern":
        values = [Fraction(str(v)) for v in data["observations"]]
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        threshold = Fraction(str(data.get("threshold", 2)))
        # |x - mean| / sd >= threshold  <=>  (x - mean)^2 >= threshold^2 * variance, decided exactly; the
        # solver's float decision may only differ inside a 1e-9 relative band around the threshold.
        def flagged(slack):
            if variance == 0:
                return [i for i in range(len(values)) if threshold <= 0]
            return [i for i, v in enumerate(values) if (v - mean) ** 2 >= threshold ** 2 * variance * slack]
        strict, loose = set(flagged(1 + Fraction(1, 10**9))), set(flagged(1 - Fraction(1, 10**9)))
        checks["population_moments"] = _close(output["mean"], mean) and _close(output["sd"], math.sqrt(variance))
        checks["anomaly_indices"] = (output["anomalies"] == sorted(output["anomalies"])
                                     and strict <= set(output["anomalies"]) <= loose)
        dissent.append("Descriptive z-scores; nonstationarity and contamination may mask anomalies.")
    elif family == "micro":
        observed, low, high = (Fraction(str(data[k])) for k in ("observed", "low", "high"))
        checks["setpoint_rule"] = output["state"] == ("stimulate" if observed < low else "inhibit" if observed > high else "abstain")
    elif family == "sequential":
        transitions, rewards = data["transitions"], data["rewards"]
        gamma = Fraction(str(data.get("discount", 1)))

        def action_value(state, action, values):
            return Fraction(str(rewards[state][action])) + gamma * sum(
                Fraction(str(p)) * values[t] for t, p in transitions[state][action].items())
        values = previous = dict.fromkeys(transitions, Fraction(0))
        for _ in range(int(data["horizon"])):
            previous, values = values, {s: max(action_value(s, a, values) for a in actions)
                                        for s, actions in transitions.items()}
        checks["backward_induction_values"] = (set(output["values"]) == set(values)
                                               and all(_close(output["values"][s], v) for s, v in values.items()))
        checks["policy_maximizes"] = all(output["policy"].get(s) in transitions[s]
                                         and action_value(s, output["policy"][s], previous) == values[s]
                                         for s in values)
        dissent.append("Finite-horizon fully observed model; transition probabilities are supplied, not learned.")
    elif family == "collective":
        scores, groups = {}, set()
        for observation in data["observations"]:
            groups.add(observation["independence_group"])
            choice = observation["choice"]
            scores[choice] = scores.get(choice, Fraction(0)) + Fraction(str(observation["weight"]))
        minimum, threshold = int(data.get("minimum_independent", 3)), Fraction(str(data.get("threshold", .7)))
        total = sum(scores.values(), Fraction(0))
        winner = max(sorted(scores), key=scores.get) if scores else None
        crossed = bool(winner is not None and len(groups) >= minimum and total > 0 and scores[winner] / total >= threshold)
        checks["weighted_scores"] = (set(output["scores"]) == set(scores)
                                     and all(_close(output["scores"][c], v) for c, v in scores.items()))
        checks["quorum_rule"] = output["quorum_crossed"] == crossed and output["choice"] == (winner if crossed else None)
        dissent.append("Independence groups are declared by the caller; correlation inside a group is not detected.")
    elif family == "semantic":
        dissent.append("Source references are supplied data; citation presence does not verify claim entailment.")
    else:
        dissent.append("Typed artifact verified; solver quality and real-world applicability require separate outcome evidence.")
    if family in ("formal", "optimization"):
        dissent.append("Formal encoding may omit a material condition. Satisfiability/optimality is conditional on that encoding.")
    return {"verdict": "REFUTED" if not all(checks.values()) else "STRUCTURALLY_VERIFIED",
            "checks": checks, "dissent": dissent, "artifact_digest": digest(answer["proof"]),
            "independence": "separate verification functions in reviewed Kernel code; no independent external evaluator"}


def metaconsensus(receipts):
    """Preserve epistemic jurisdiction and minority objections; never majority-vote truth."""
    by_class, by_question = {}, {}
    for receipt in receipts:
        by_class.setdefault(receipt["epistemic_class"], []).append(receipt)
        by_question.setdefault((receipt["problem_id"], receipt["epistemic_class"]), []).append(receipt)
    conflicts = [{"problem_id": pid, "epistemic_class": cls} for (pid, cls), rows in by_question.items()
                 if len({digest(r.get("output")) for r in rows if r["abstention_state"] == "NONE"}) > 1]
    human = any(r["epistemic_class"] in ("normative", "legal", "institutional_acceptance") for r in receipts)
    abstained = any(r["abstention_state"] != "NONE" for r in receipts)
    return {"state": "HUMAN_REVIEW_REQUIRED" if human else "CONFLICT" if conflicts else "ABSTAIN" if abstained else "RECOMMENDATION_ONLY",
            "conflicting_questions": conflicts, "conflicting_classes": sorted({c["epistemic_class"] for c in conflicts}),
            "jurisdictions": {cls: [r["receipt_id"] for r in rows] for cls, rows in by_class.items()},
            "questions": [{"problem_id": r["problem_id"], "method": r["method"], "epistemic_class": r["epistemic_class"],
                           "assumptions": r["assumptions"], "proof_type": r["proof_type"],
                           "missing_information": r["missing_information"], "dominance": "not inferred across different questions or classes"}
                          for r in receipts],
            "dissent": [r["strongest_counterargument"] for r in receipts], "authority_created": False}
