"""Independent falsifier over emitted artifacts; it has no authority or effect adapter."""
from __future__ import annotations

from fractions import Fraction
import math

from .contracts import CognitionError, ProofArtifact, digest


def _native_numeric_checks(family, data, answer):
    """Failure-diverse source checks; no solver call, authority or learned evaluator.

    Fraction arithmetic checks small analytic models. Simulation replay shares
    Python's PRNG, disclosed below; minimax checks both candidates by substitution.
    These establish encoded behavior only, not forecast calibration or regulation.
    """
    output, artifact = answer["output"], answer["proof"]
    checks, dissent = {}, []
    def F(value):
        if type(value) is Fraction:  # locally derived oracle arithmetic, never JSON output
            return value
        if type(value) not in (int, float) or not math.isfinite(value):
            raise CognitionError("native certificate numeric field is invalid")
        return Fraction(str(value))
    def close(a, b):
        a, b = F(a), F(b)
        return abs(a - b) <= Fraction(1, 10**10) * max(1, abs(a), abs(b))
    def same_numbers(expected, actual):
        return (isinstance(actual, dict) and set(actual) == set(expected) and
                all(close(expected[k], actual[k]) for k in expected))
    try:
        if family != "sequential" and (family != "micro" or "source_model" in artifact):
            checks["native_source_bound"] = artifact.get("source_model") == data and artifact.get("input_digest") == digest(data)
        if family == "probabilistic":
            a, b = F(data["alpha"]) + data["successes"], F(data["beta"]) + data["failures"]
            expected = {"alpha": a, "beta": b, "mean": a / (a + b), "variance": a * b / ((a + b)**2 * (a + b + 1))}
            checks["posterior_conjugate_update"] = same_numbers(expected, output)
            checks["posterior_artifact_binding"] = artifact["prior"] == {"alpha": data["alpha"], "beta": data["beta"]} and artifact["posterior"] == output
            checks["prior_sensitivity"] = close(artifact["sensitivity"]["uniform_prior_mean"], Fraction(data["successes"] + 1, data["successes"] + data["failures"] + 2))
            dissent.append("Conditional Beta-Bernoulli conjugacy; exchangeability, observation quality and predictive calibration are unverified.")
        elif family == "control":
            e, dt = F(data["target"]) - F(data["observed"]), F(data.get("dt", 1))
            prior = data.get("state", {})
            initial = F(prior.get("integral", 0))
            integral = initial + e * dt
            raw = F(data.get("kp", 0)) * e + F(data.get("ki", 0)) * integral + F(data.get("kd", 0)) * (e - F(prior.get("previous_error", float(e)))) / dt
            limit = F(data["correction_limit"])
            correction = min(limit, max(-limit, raw))
            retained = initial if raw != correction else integral
            checks["independent_pid_and_antiwindup"] = close(correction, output["correction"]) and same_numbers({"integral": retained, "previous_error": e}, output["state"])
            checks["pid_artifact_binding"] = artifact["target"] == data["target"] and close(artifact["error"], e) and artifact["correction"] == output["correction"] and artifact["state"] == output["state"]
            checks["bounded_correction"] = abs(F(output["correction"])) <= limit
            dissent.append("One bounded numeric PID proposal, without a plant/stability model or physical actuation authority.")
        elif family == "information":
            scenarios = data["posterior_scenarios"]
            total = sum(F(s["probability"]) for s in scenarios)
            gross = sum(F(s["probability"]) * F(s["best_value"]) for s in scenarios) - F(data["prior_best_value"])
            cost = F(data["cost"])
            checks["voi_probability_model"] = abs(total - 1) <= Fraction(1, 10**9) and all(0 <= F(s["probability"]) <= 1 for s in scenarios)
            checks["decision_value_not_entropy"] = close(output["gross_value"], gross) and close(output["net_value"], gross - cost) and type(output["acquire"]) is bool and output["acquire"] == (gross > cost)
            checks["voi_artifact_binding"] = artifact["prior"] == data["prior_best_value"] and artifact["posterior_scenarios"] == scenarios and artifact["cost"] == data["cost"] and close(artifact["expected_value"], gross)
            dissent.append("Decision-value calculation depends on declared scenarios, utilities and costs; mandatory authority and verification remain outside optional VOI ranking.")
        elif family == "simulation":
            import random
            rng = random.Random(data["seed"])
            rows = []
            for _ in range(data["samples"]):
                count = 0
                for _ in range(data["steps"]):
                    if rng.random() < data["step_probability"]:
                        count += 1
                rows.append(count)
            checks["seeded_distribution_replay"] = same_numbers({"mean": Fraction(sum(rows), len(rows)), "minimum": min(rows), "maximum": max(rows)}, output)
            checks["full_distribution_digest"] = (artifact["scenario_digest"] == digest(rows) and
                type(artifact["scenarios"]) is list and all(type(v) is int for v in artifact["scenarios"]) and
                artifact["scenarios"] == rows[:100] and type(artifact["samples"]) is int and
                artifact["samples"] == len(rows) and artifact["seed"] == data["seed"])
            checks["prefix_disclosed"] = artifact.get("scenario_prefix_only") is (len(rows) > 100)
            dissent.append("Synthetic Bernoulli simulation replay shares Python's PRNG algorithm; no real-world calibration, forecast correctness or independent random generator is established.")
        elif family == "game":
            checks["game_original_payoffs"] = artifact["payoffs"] == data["payoffs"]
            if answer["status"] != "ANSWER":
                checks["game_unknown_scope"] = answer["status"] == "UNKNOWN" and answer["formal_validity"] == "UNKNOWN" and artifact["value"] is None and artifact["strategies"] == []
            else:
                rows, columns = len(data["payoffs"]), len(data["payoffs"][0])
                p, q = [F(x) for x in output["mixed_strategy"]], [F(x) for x in artifact["opponent_strategy"]]
                valid = len(p) == rows and len(q) == columns and min(p + q) >= 0 and all(abs(sum(v) - 1) <= Fraction(1, 10**9) for v in (p, q))
                checks["minimax_simplex_domains"] = valid
                lower = min(sum(p[i] * F(data["payoffs"][i][j]) for i in range(rows)) for j in range(columns))
                upper = max(sum(q[j] * F(data["payoffs"][i][j]) for j in range(columns)) for i in range(rows))
                tolerance = Fraction(1, 10**7) * max(1, abs(lower), abs(upper))
                value = F(output["value"])
                checks["independent_minimax_primal_dual"] = upper - lower <= tolerance and lower - tolerance <= value <= upper + tolerance
                checks["game_candidate_binding"] = artifact["strategies"] == output["mixed_strategy"] and artifact["value"] == output["value"] and artifact["native_statuses"] == ["OPTIMAL", "OPTIMAL"] and output["solver_status"] == "OPTIMAL"
            dissent.append("Finite two-player zero-sum numerical equilibrium within relative 1e-7; payoff realism, strategic applicability and human consent remain unverified.")
        elif family in ("pattern", "micro"):
            if family == "micro":
                expected = "stimulate" if data["observed"] < data["low"] else "inhibit" if data["observed"] > data["high"] else "abstain"
                checks["deterministic_ternary_transition"] = (output == {"state": expected} and
                    all(type(v) in (int, float) for v in artifact["observations"]) and artifact["observations"] == [data["observed"]] and
                    all(type(v) in (int, float) for v in artifact["model"].values()) and
                    artifact["model"] == {"low": data["low"], "high": data["high"]} and artifact["scores"] == [expected])
            else:
                xs = [F(x) for x in data["observations"]]
                mean = sum(xs) / len(xs)
                variance = sum((x - mean)**2 for x in xs) / len(xs)
                sd = math.sqrt(float(variance))
                scores = [float(x - mean) / sd if sd else 0 for x in xs]
                indices = [i for i, z in enumerate(scores) if abs(z) >= data.get("threshold", 2)]
                checks["independent_population_moments"] = close(output["mean"], mean) and close(output["sd"], sd)
                checks["anomaly_indices"] = type(output["anomalies"]) is list and all(type(v) is int for v in output["anomalies"]) and output["anomalies"] == indices
                checks["zscore_source_binding"] = all(type(v) in (int, float) for v in artifact["observations"]) and artifact["observations"] == data["observations"] and len(artifact["scores"]) == len(scores) and all(close(a, b) for a, b in zip(artifact["scores"], scores))
            dissent.append("Primitive/descriptive local state only; unfamiliarity is not an attack and anomalies are not proven harmful events.")
        elif family == "sequential":
            from functools import lru_cache
            transitions, rewards = data["transitions"], data["rewards"]
            @lru_cache(None)
            def value(state, horizon):
                if not horizon:
                    return Fraction(0)
                return max(F(rewards[state][action]) + F(data.get("discount", 1)) * sum(F(p) * value(target, horizon - 1) for target, p in distribution.items()) for action, distribution in transitions[state].items())
            def policy(state, horizon):
                scores = {action: F(rewards[state][action]) + F(data.get("discount", 1)) * sum(F(p) * value(target, horizon - 1) for target, p in distribution.items()) for action, distribution in transitions[state].items()}
                return max(sorted(scores), key=scores.get)
            expected_values = {state: value(state, data["horizon"]) for state in transitions}
            expected_policy = {state: policy(state, data["horizon"]) for state in transitions}
            checks["independent_bellman_values"] = same_numbers(expected_values, output["values"]) and output["policy"] == expected_policy
            checks["sequential_original_model"] = artifact["model"] == data and artifact["input_digest"] == digest(data) and artifact["states"] == list(transitions) and artifact["cost"] is None
            checks["all_horizon_policies"] = artifact["path"] == [{s: policy(s, h) for s in transitions} for h in range(1, data["horizon"] + 1)]
            checks["all_horizon_values"] = len(artifact["value_trace"]) == data["horizon"] and all(same_numbers({s: value(s, h) for s in transitions}, values) for h, values in enumerate(artifact["value_trace"], 1))
            dissent.append("Finite-horizon fully observed supplied MDP; no open-world RL, exploration permission or empirical transition identification.")
        elif family == "collective":
            observations, ids, groups, scores = data["observations"], set(), set(), {}
            for row in observations:
                if row["observer_id"] in ids or row["independence_group"] in groups:
                    raise CognitionError("duplicate or correlated declared observers")
                ids.add(row["observer_id"]); groups.add(row["independence_group"])
                scores[row["choice"]] = scores.get(row["choice"], Fraction(0)) + F(row["weight"])
            winner = max(sorted(scores), key=scores.get) if scores else None
            crossed = bool(winner is not None and len(groups) >= data.get("minimum_independent", 3) and sum(scores.values()) > 0 and scores[winner] / sum(scores.values()) >= F(data.get("threshold", .7)))
            checks["declared_quorum_not_truth_vote"] = output["choice"] == (winner if crossed else None) and output["quorum_crossed"] is crossed and same_numbers(scores, output["scores"]) and answer["status"] == ("ANSWER" if crossed else "NO_QUORUM")
            checks["all_dissent_preserved"] = artifact["participants"] == sorted(ids) and artifact["independence"] == sorted(groups) and artifact["dissent"] == [{"observer_id": row["observer_id"], "choice": row["choice"], "reason": row.get("reason", "unsupplied")} for row in observations] and artifact["trace"] == output
            dissent.append("Quorum checks declared distinct labels only; common sources, actual observer independence and empirical truth are not established or created by votes.")
        elif family == "evolutionary":
            center, bounds = [F(v) for v in data["center"]], data["bounds"]
            def fitness(candidate):
                return sum((F(v) - c)**2 for v, c in zip(candidate, center))
            candidate = output["candidate"]
            valid = len(candidate) == len(center) and all(F(lo) <= F(v) <= F(hi) for v, (lo, hi) in zip(candidate, bounds))
            analytic = [min(F(hi), max(F(lo), c)) for c, (lo, hi) in zip(center, bounds)]
            expected_ceiling = (data.get("generations", 5) + 1) * max(5, data.get("population", 5) * len(center))
            checks["bounded_candidate_fitness"] = valid and close(fitness(candidate), output["fitness"])
            checks["fixed_evaluator_analytic_control"] = same_numbers({str(i): v for i, v in enumerate(analytic)}, {str(i): v for i, v in enumerate(artifact["analytic_baseline"]["candidate"])}) and close(artifact["analytic_baseline"]["fitness"], fitness(analytic)) and F(output["fitness"]) + Fraction(1, 10**9) >= fitness(analytic)
            checks["actual_evaluation_ceiling"] = type(output["evaluations"]) is int and 1 <= output["evaluations"] <= expected_ceiling and artifact["evaluation_ceiling"] == expected_ceiling
            checks["population_lineage_fitness"] = len(artifact["trace"]) <= data.get("generations", 5) and all(len(row["candidate"]) == len(center) and all(F(lo) <= F(v) <= F(hi) for v, (lo, hi) in zip(row["candidate"], bounds)) and close(row["fitness"], fitness(row["candidate"])) for row in artifact["trace"])
            dissent.append("A bounded seeded search against a fixed quadratic, checked against its analytic optimum; no invented algorithm, program synthesis, global superiority or automatic promotion.")
        elif family == "human":
            panel = {k: data.get(k) for k in ("participants", "expertise", "conflicts", "dissent", "decision_authority")}
            checks["human_judgment_remains_required"] = output == {"panel": panel, "decision": None} and answer["status"] == "HUMAN_REVIEW_REQUIRED" and all(artifact[k] == v for k, v in panel.items())
            dissent.append("Untrusted proposed participation cannot authenticate professional competence or legitimate human authority; actual judgment uses the existing human process.")
    except (CognitionError, TypeError, ValueError, KeyError, IndexError, ZeroDivisionError, OverflowError) as exc:
        checks["native_certificate_complete"] = False
        dissent.append(str(exc))
    return checks, dissent

def verify(family, data, answer, proof_class):
    checks, dissent = {}, []
    from .catalog import FAMILIES, NATIVE_QUALIFIED
    if family not in FAMILIES or proof_class != FAMILIES[family][3]:
        raise CognitionError("false proof type for selected method")
    try:
        ProofArtifact(proof_class, answer["proof"]).validate()
    except CognitionError as exc:
        return {"verdict": "REFUTED", "checks": {"typed_artifact": False},
                "dissent": [str(exc)], "artifact_digest": digest(answer["proof"]),
                "independence": "separate reviewed verification code; no external evaluator"}
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
    elif family == "estimation":
        checks["ordered_range"] = output["low"] <= output["central"] <= output["high"]
        dissent.append("Bounds are assumptions; no calibrated probability or external market proof follows.")
    elif family == "causal":
        dissent.append("Randomization and identification assumptions have not been independently established in reality.")
    elif family == "semantic":
        dissent.append("Source references are supplied data; citation presence does not verify claim entailment.")
    else:
        dissent.append("Typed artifact verified; solver quality and real-world applicability require separate outcome evidence.")
    if family in ("formal", "optimization"):
        dissent.append("Formal encoding may omit a material condition. Satisfiability/optimality is conditional on that encoding.")
    if family in NATIVE_QUALIFIED:
        native_checks, native_dissent = _native_numeric_checks(family, data, answer)
        checks.update(native_checks)
        dissent.extend(native_dissent)
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
