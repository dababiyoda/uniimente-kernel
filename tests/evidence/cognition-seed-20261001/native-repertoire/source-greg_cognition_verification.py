"""Independent falsifier over emitted artifacts; it has no authority or effect adapter."""
from __future__ import annotations

from fractions import Fraction
import math

from .contracts import CognitionError, ProofArtifact, digest


def _polynomial_checks(data, output, artifact):
    """Independent rational polynomial algebra and Sturm root counts, degree <=4.

    No SymPy import, eval, sympify or model-generated program is used here.
    Root intervals prove encoded real-root existence/count, never world facts.
    """
    import ast
    def trim(p):
        p = list(p)
        while len(p) > 1 and not p[-1]:
            p.pop()
        return p
    def multiply(a, b):
        if len(a) + len(b) - 2 > 4:
            raise CognitionError("factor expansion exceeds declared degree four")
        out = [Fraction(0)] * (len(a) + len(b) - 1)
        for i, x in enumerate(a):
            for j, y in enumerate(b):
                out[i+j] += x*y
        if any(max(x.numerator.bit_length(), x.denominator.bit_length()) > 2048 for x in out):
            raise CognitionError("factor arithmetic exceeds bit ceiling")
        return trim(out)
    def divide(a, b):
        a, b = trim(a), trim(b)
        if b == [0]:
            raise CognitionError("zero polynomial divisor")
        quotient = [Fraction(0)] * max(1, len(a) - len(b) + 1)
        while a != [0] and len(a) >= len(b):
            degree, scale = len(a) - len(b), a[-1] / b[-1]
            quotient[degree] = scale
            for i, coefficient in enumerate(b):
                a[i+degree] -= scale * coefficient
            a = trim(a)
        return trim(quotient), a
    def derivative(p):
        return trim([i * p[i] for i in range(1, len(p))] or [Fraction(0)])
    def gcd(a, b):
        while b != [0]:
            a, b = b, divide(a, b)[1]
        return [x/a[-1] for x in a]
    def sturm(p):
        seq = [p, derivative(p)]
        while seq[-1] != [0]:
            remainder = divide(seq[-2], seq[-1])[1]
            if remainder == [0]:
                break
            seq.append([-v for v in remainder])
        return [q for q in seq if q != [0]]
    def evaluate(p, x):
        value = Fraction(0)
        for coefficient in reversed(p):
            value = value * x + coefficient
        return value
    def variations(seq, endpoint, infinity=0):
        signs = []
        for p in seq:
            value = p[-1] * ((-1)**(len(p)-1) if infinity < 0 else 1) if infinity else evaluate(p, endpoint)
            if value:
                signs.append(1 if value > 0 else -1)
        return sum(a != b for a, b in zip(signs, signs[1:]))
    def interval_count(p, lo, hi):
        seq = sturm(p)
        return variations(seq, lo) - variations(seq, hi)
    def rational(text):
        if not isinstance(text, str) or len(text) > 128:
            raise CognitionError("bounded rational isolating endpoint required")
        value = Fraction(text)
        if max(value.numerator.bit_length(), value.denominator.bit_length()) > 256:
            raise CognitionError("isolating endpoint exceeds bit ceiling")
        return value
    def factor_expression(text):
        if not isinstance(text, str) or len(text) > 4096:
            raise CognitionError("bounded factor expression required")
        tree = ast.parse(text, mode="eval")
        if sum(1 for _ in ast.walk(tree)) > 256:
            raise CognitionError("factor expression tree exceeds bound")
        def walk(node):
            if isinstance(node, ast.Constant) and type(node.value) in (int, float):
                return [Fraction(str(node.value))]
            if isinstance(node, ast.Name) and node.id == "x":
                return [Fraction(0), Fraction(1)]
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
                return [(-1 if isinstance(node.op, ast.USub) else 1) * c for c in walk(node.operand)]
            if not isinstance(node, ast.BinOp):
                raise CognitionError("unsupported factor syntax")
            a, b = walk(node.left), walk(node.right)
            if isinstance(node.op, (ast.Add, ast.Sub)):
                sign = -1 if isinstance(node.op, ast.Sub) else 1
                return trim([(a[i] if i < len(a) else 0) + sign * (b[i] if i < len(b) else 0) for i in range(max(len(a), len(b)))])
            if isinstance(node.op, ast.Mult):
                return multiply(a, b)
            if isinstance(node.op, ast.Div) and len(b) == 1 and b[0]:
                return [x/b[0] for x in a]
            if isinstance(node.op, ast.Pow) and len(b) == 1 and b[0].denominator == 1 and 0 <= b[0] <= 4:
                out = [Fraction(1)]
                for _ in range(int(b[0])):
                    out = multiply(out, a)
                return out
            raise CognitionError("unsupported factor operation")
        return walk(tree.body)
    checks = {}
    try:
        p = [Fraction(str(v)) for v in data["polynomial"]]
        intervals = artifact["isolated_real_roots"]
        if len(p) not in range(2, 6) or not p[-1] or not isinstance(intervals, list) or len(intervals) > len(p)-1:
            raise CognitionError("bounded nonzero polynomial and root intervals required")
        previous, labels, multiplicities_ok = None, [], True
        for row in intervals:
            if not isinstance(row, dict) or set(row) != {"lower", "upper", "multiplicity"}:
                raise CognitionError("restricted root interval fields required")
            lo, hi = rational(row["lower"]), rational(row["upper"])
            if lo > hi or previous is not None and lo <= previous:
                raise CognitionError("root intervals must be ordered and disjoint")
            previous = hi
            if lo == hi:
                if evaluate(p, lo):
                    raise CognitionError("claimed rational root does not satisfy polynomial")
                q, multiplicity = p, 0
                while len(q) > 1 and evaluate(q, lo) == 0:
                    multiplicity += 1; q = derivative(q)
                labels.append(str(lo))
            else:
                if not evaluate(p, lo) or not evaluate(p, hi) or interval_count(p, lo, hi) != 1:
                    raise CognitionError("interval does not isolate one source root")
                q, multiplicity = gcd(p, derivative(p)), 1
                while len(q) > 1:
                    multiplicity += interval_count(q, lo, hi)
                    q = gcd(q, derivative(q))
                labels.append(f"root in ({row['lower']}, {row['upper']})")
            multiplicities_ok &= type(row["multiplicity"]) is int and row["multiplicity"] == multiplicity
        seq = sturm(p)
        total = variations(seq, None, -1) - variations(seq, None, 1)
        checks["sturm_real_root_completeness"] = len(intervals) == total
        checks["exact_root_multiplicity"] = multiplicities_ok
        checks["root_display_is_certificate"] = output["real_roots"] == sorted(labels)
        checks["independent_factor_coefficients"] = trim(factor_expression(output["factored"])) == p
        checks["polynomial_source_digest"] = artifact["input_digest"] == digest(data)
    except (CognitionError, TypeError, ValueError, KeyError, IndexError, ZeroDivisionError, SyntaxError) as exc:
        checks["polynomial_certificate_complete"] = False
        return checks, [str(exc)]
    return checks, ["Exact rational Sturm counts certify source-polynomial real roots/multiplicities and factor coefficients; irrational roots are isolating intervals, not empirical claims."]


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
    from .catalog import FAMILIES
    if family not in FAMILIES or proof_class != FAMILIES[family][3]:
        raise CognitionError("false proof type for selected method")
    try:
        ProofArtifact(proof_class, answer["proof"]).validate()
    except CognitionError as exc:
        return {"verdict": "REFUTED", "checks": {"typed_artifact": False}, "dissent": [str(exc)],
                "artifact_digest": digest(answer["proof"]),
                "independence": "separate verification functions in reviewed Kernel code; no independent external evaluator"}
    checks["typed_artifact"] = True
    output, artifact = answer["output"], answer["proof"]
    if family == "exact":
        expression = {"polynomial": data["polynomial"]} if "polynomial" in data else data["expression"]
        checks["artifact_expression_matches_input"] = artifact["expression"] == expression
        checks["artifact_result_matches_output"] = artifact["result"] == output
        if "polynomial" not in data:
            checks["artifact_variables_match_input"] = artifact.get("variables", {}) == data.get("variables", {})
            numerator, denominator = output.get("numerator"), output.get("denominator")
            checks["exact_output_representation"] = (type(numerator) is int and type(denominator) is int and
                denominator > 0 and output.get("exact") == str(Fraction(numerator, denominator)))
    elif family in ("formal", "optimization"):
        checks["artifact_constraints_match_input"] = artifact["constraints"] == data["constraints"]
        checks["artifact_status_matches_output"] = artifact["solver_status"] == output["solver_status"]
        if family == "formal":
            checks["artifact_model_matches_input"] = artifact["model"].get("variables") == data["variables"]
        else:
            checks["artifact_variables_match_input"] = artifact.get("variables") == data["variables"]
            checks["artifact_objective_matches_input"] = artifact["objective"] == data.get("objective")
            checks["artifact_solution_matches_output"] = artifact["solution"] == output["solution"]
        native_status = output["solver_status"]
        if native_status in ("UNKNOWN", "MODEL_INVALID"):
            checks["native_status_contract"] = answer.get("status") in ("UNKNOWN", "ABSTAIN") and answer.get("formal_validity") == "UNKNOWN"
        else:
            checks["native_status_contract"] = answer.get("status") == "ANSWER" and answer.get("formal_validity") == "VALID_CONDITIONAL_ON_MODEL"
    elif family == "estimation":
        checks["artifact_range_matches_output"] = artifact["range"] == output
        checks["artifact_decomposition_matches_input"] = artifact["decomposition"] == data["factors"]
    elif family == "causal":
        checks["artifact_estimate_matches_output"] = artifact["estimate"] == output["effect"]
        checks["artifact_uncertainty_matches_output"] = artifact.get("uncertainty") == output["uncertainty"]
        checks["artifact_data_matches_input"] = artifact.get("data", {}).get("digest") == digest({
            "treated": data.get("treated", []), "control": data.get("control", [])})
    elif family == "evidence":
        checks["artifact_claim_matches_input_output"] = artifact["claim"] == data["claim"] == output["claim"]
        checks["artifact_sources_match_input"] = artifact["sources"] == [{k:v for k,v in s.items() if k != "text"} for s in data["sources"]]
        checks["artifact_bindings_match_input"] = artifact["bindings"] == data["bindings"]
        checks["artifact_contradictions_match_input"] = artifact["contradictions"] == [b for b in data["bindings"] if b["relationship"] == "contradicts"]
    elif family in ("graph", "search"):
        from .network import shortest_request
        req = shortest_request(data)
        checks["artifact_source_model_matches_input"] = artifact["model"] == data and artifact.get("input_digest") == digest(data)
        checks["normalized_graph_matches_input"] = artifact.get("normalized_model") == req and artifact["states"] == req["nodes"]
        checks["artifact_path_matches_output"] = artifact["path"] == output["path"] and artifact["cost"] == output["cost"]
        checks["graph_output_types"] = (type(output.get("reachable")) is bool and type(output.get("path")) is list and
                                         (output.get("cost") is None or type(output.get("cost")) in (int, float)))
    elif family == "flow":
        from .network import flow_request
        checks["artifact_source_model_matches_input"] = artifact["source_model"] == data and artifact["input_digest"] == digest(data)
        checks["normalized_flow_matches_input"] = artifact["model"] == flow_request(data)
        checks["artifact_flow_matches_output"] = artifact["flow"] == output
        cut = output.get("min_cut")
        checks["flow_cut_types"] = (isinstance(cut, dict) and type(cut.get("capacity")) is int and
                                    type(cut.get("source_side")) is list and type(cut.get("arcs")) is list)
    elif family == "linear":
        from .linear import canonical_request
        checks["normalized_lp_matches_input"] = artifact["model"] == canonical_request(data)
        checks["artifact_source_digest"] = artifact["input_digest"] == digest(data)
        checks["artifact_objective_constraints_match_input"] = artifact["objective"] == data["objective"] and artifact["constraints"] == data.get("constraints", [])
        checks["native_lp_status_preserved"] = artifact["solver_status"] == output["solver_status"]
        optimal = output["solver_status"] == "OPTIMAL"
        checks["lp_output_types"] = (type(output.get("solution")) is dict and all(type(v) in (int, float) and math.isfinite(v) for v in output["solution"].values()) and
                                     type(output.get("feasible")) is bool and output["feasible"] is optimal and
                                     output.get("objective_direction") == data["objective"]["sense"] and
                                     (type(output.get("objective_value")) in (int, float) and math.isfinite(output["objective_value"]) if optimal else output.get("objective_value") is None and output["solution"] == {}))
        checks["native_lp_result_scope"] = ((answer["status"] == "ANSWER" and answer["formal_validity"] == "VALID_WITHIN_DECLARED_TOLERANCE") if optimal else
                                          (answer["status"] in ("UNKNOWN", "ABSTAIN") and answer["formal_validity"] == "UNKNOWN"))
        checks["no_fabricated_infeasibility_certificate"] = artifact["infeasibility_certificate"] is None
    if family == "exact" and "polynomial" in data:
        native_checks, native_dissent = _polynomial_checks(data, output, artifact)
        checks.update(native_checks); dissent.extend(native_dissent)
    elif family == "exact" and "polynomial" not in data:
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
        checks["solution_variable_set"] = set(values) == set(data["variables"])
        checks["bounded_solution"] = all(Fraction(str(lo)) <= values[n] <= Fraction(str(hi)) for n, (lo, hi) in data["variables"].items())
        valid = True
        for c in data["constraints"]:
            lhs = sum(Fraction(str(co)) * values[n] for n, co in c["coefficients"].items())
            rhs = Fraction(str(c["rhs"]))
            valid &= {"<=": lhs <= rhs, ">=": lhs >= rhs, "==": lhs == rhs, "!=": lhs != rhs}[c["op"]]
        checks["constraint_substitution"] = bool(valid)
        if family == "optimization":
            checks["integer_domain"] = all(v.denominator == 1 for v in values.values())
            objective = sum(c * values[n] for n, c in data["objective"]["coefficients"].items())
            checks["objective_substitution"] = math.isclose(float(objective), output["objective_value"], abs_tol=1e-6)
    elif family in ("graph", "search"):
        from .network import CertificateError, certify_shortest, shortest_request
        try:
            certified = certify_shortest(shortest_request(data), artifact.get("network_claim"))
            checks["optimal_distance_potential_and_reachability"] = certified["certified"]
            checks["certified_path_matches_output"] = ((certified["path"] or []) == output["path"] and certified["distance"] == output["cost"] and certified["reachable"] == output["reachable"])
        except CertificateError as exc:
            checks["optimal_distance_potential_and_reachability"] = False
            dissent.append(str(exc))
        dissent.append("The certificate covers supplied topology only; edge optimality uses exact Fractions, displayed floating distances permit relative 1e-12 tolerance.")
    elif family == "flow":
        from .network import CertificateError, certify_max_flow, flow_request
        try:
            certified = certify_max_flow(flow_request(data), output)
            checks["capacity_conservation_and_equal_min_cut"] = certified["certified"] and certified["value"] == output["value"] and certified["min_cut"] == output.get("min_cut")
        except CertificateError as exc:
            checks["capacity_conservation_and_equal_min_cut"] = False
            dissent.append(str(exc))
        dissent.append("Exact integer flow/cut check; supplied network capacity and real-world applicability remain unverified.")
    elif family == "linear":
        from .linear import CertificateError, canonical_request, certify_lp
        if output["solver_status"] == "OPTIMAL":
            try:
                certified = certify_lp(canonical_request(data), artifact["claim"])
                checks["primal_dual_certificate"] = certified["certified"]
                checks["certified_assignment_matches_output"] = certified["values"] == output["solution"]
                checks["certified_objective_matches_output"] = math.isclose(certified["objective"], output["objective_value"], rel_tol=1e-7, abs_tol=1e-7)
                checks["certified_bound_gap_matches_artifact"] = (math.isclose(certified["dual_bound"], artifact["bound"], rel_tol=1e-7, abs_tol=1e-7) and
                                                                 math.isclose(abs(certified["certificate"]["gap"]), artifact["gap"], rel_tol=1e-7, abs_tol=1e-7))
            except (CertificateError, TypeError, KeyError) as exc:
                checks["primal_dual_certificate"] = False
                dissent.append(str(exc))
        else:
            checks["nonoptimal_status_not_certified"] = artifact["claim"]["status"] != "optimal" and answer["status"] != "ANSWER"
            checks["nonoptimal_bound_unknown"] = artifact["bound"] is None and artifact["gap"] is None
        dissent.append("LP primal/dual checks use relative 1e-7 numerical tolerance. Native INFEASIBLE/UNBOUNDED is unproven and cannot close a mission.")
    elif family == "estimation":
        checks["ordered_range"] = output["low"] <= output["central"] <= output["high"]
        from decimal import Decimal
        products, units = [Decimal(1)] * 3, {}
        for f in data["factors"]:
            for i, name in enumerate(("low", "central", "high")):
                products[i] *= Decimal(str(f[name]))
            for unit, exponent in f.get("units", {}).items():
                units[unit] = units.get(unit, 0) + exponent
        checks["independent_products"] = all(math.isclose(float(v), output[k], rel_tol=1e-12) for k, v in zip(("low", "central", "high"), products))
        checks["unit_balance"] = output["units"] == {k:v for k,v in units.items() if v}
        checks["expected_units"] = "expected_units" not in data or output["units"] == data["expected_units"]
        dissent.append("Bounds are assumptions; no calibrated probability or external market proof follows.")
    elif family == "causal":
        if output["identified_conditionally"]:
            t, c = data["treated"], data["control"]
            expected = sum(Fraction(str(x)) for x in t)/len(t) - sum(Fraction(str(x)) for x in c)/len(c)
            checks["independent_effect"] = math.isclose(float(expected), output["effect"], abs_tol=1e-12)
            checks["identified_scope"] = data.get("design") == "randomized" and min(len(t),len(c)) >= 2 and data.get("missingness", "none") == "none"
            def sample_var(xs):
                xs = [Fraction(str(x)) for x in xs]; m = sum(xs)/len(xs)
                return sum((x-m)**2 for x in xs)/(len(xs)-1)
            se = math.sqrt(float(sample_var(t)/len(t)+sample_var(c)/len(c)))
            checks["independent_uncertainty"] = math.isclose(se, output["uncertainty"]["standard_error"], abs_tol=1e-12)
        dissent.append("Randomization and identification assumptions have not been independently established in reality.")
    elif family == "semantic":
        sources = {s["id"]: s["text"] for s in data["sources"]}
        checks["artifact_sources_match_input"] = answer["proof"]["sources"] == [{"id": s["id"], "digest": digest(s["text"])} for s in data["sources"]]
        checks["bound_extractions"] = all(c.get("kind") == "proposed" or
            (c.get("kind") == "extracted" and c.get("source_id") in sources and c.get("quote") and
             c["quote"] in sources[c["source_id"]] and c["text"] == c["quote"]) for c in output["claims"])
        checks["claims_match_artifact"] = output["claims"] == answer["proof"]["claims"]
        dissent.append("Only exact extracts are bound; synthesis is provisional. A source may itself be false or contaminated.")
    elif family == "evidence":
        from datetime import datetime, timezone
        sources = {s["id"]: s for s in data["sources"]}
        checks["custody_digests"] = all(s["digest"] == digest(s["text"]) for s in sources.values())
        checks["fresh_sources"] = all(datetime.fromisoformat(s["expires_at"].replace("Z", "+00:00")) > datetime.now(timezone.utc) for s in sources.values())
        checks["span_binding"] = all(b["source_id"] in sources and b["quote"] in sources[b["source_id"]]["text"] for b in data["bindings"])
        checks["contradiction_preserved"] = output["contested"] == any(b["relationship"] == "contradicts" for b in data["bindings"])
        dissent.append("Declared provenance/quality need separate authentication; quote binding does not prove entailment.")
    else:
        dissent.append("Typed artifact verified; solver quality and real-world applicability require separate outcome evidence.")
    if family in ("probabilistic", "control", "information", "simulation", "game", "pattern", "micro", "sequential", "collective", "evolutionary", "human"):
        native_checks, native_dissent = _native_numeric_checks(family, data, answer)
        checks.update(native_checks)
        dissent.extend(native_dissent)
    if family in ("formal", "optimization"):
        requirements = data.get("requirements", [])
        checks["requirement_coverage"] = not requirements or set(requirements) == {c.get("requirement_id") for c in data["constraints"]}
        dissent.append("Formal encoding may omit a material condition. Satisfiability/optimality is conditional on that encoding.")
        if output["solver_status"] in ("UNKNOWN", "MODEL_INVALID"):
            checks["unknown_not_valid"] = answer["formal_validity"] == "UNKNOWN" and answer["status"] != "ANSWER"
        if output["solver_status"] in ("UNSAT", "INFEASIBLE"):
            dissent.append("UNSAT/core and INFEASIBLE are solver reports; no independent infeasibility certificate is established.")
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
