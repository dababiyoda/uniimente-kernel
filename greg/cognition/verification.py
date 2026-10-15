"""Independent falsifier over emitted artifacts; it has no authority or effect adapter."""
from __future__ import annotations

from fractions import Fraction
import math
import statistics
import time

from .contracts import CognitionError, ProofArtifact, digest


def _restatement_gaps(claim: str, support: list) -> tuple[bool, bool]:
    """(a figure of the claim is absent from its supporting spans, the claim's polarity differs from theirs)."""
    def numbers(text):
        out, token = set(), ""
        for ch in text.replace(" percent", "%").replace(" per cent", "%") + " ":
            if ch.isdigit() or (token and ch in ",.%"):
                token += ch
            elif token:
                out.add(token.replace(",", "").rstrip(".,"))
                token = ""
        return {n for n in out if n and n[0].isdigit()}

    def negative(text):
        words = ["".join(ch for ch in w.lower() if ch.isalpha() or ch == "'") for w in text.split()]
        return any(w in ("not", "no", "never", "none", "nor", "neither", "without", "nobody", "nothing", "cannot")
                   or w.endswith("n't") for w in words)
    spans = " ".join(support)
    # Spans that spell a number out ("twelve percent") are left to the solver's reading; this recheck reads digits.
    spelled = any(w.strip(".,;:").lower() in ("two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
                                              "eleven", "twelve", "twenty", "thirty", "forty", "fifty", "hundred")
                  for w in spans.split())
    return (not spelled and bool(numbers(claim) - numbers(spans))), negative(claim) != negative(spans)


def verify(family, data, answer, proof_class):
    checks, dissent, cross = {}, [], {}
    from .catalog import FAMILIES
    if family not in FAMILIES or proof_class != FAMILIES[family][3]:
        raise CognitionError("false proof type for selected method")
    ProofArtifact(proof_class, answer["proof"]).validate()
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
        checks["artifact_distortions_match_output"] = artifact.get("distortions") == output.get("distortions")
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
        checks["solution_variable_set"] = set(values) == set(data["variables"])
        checks["bounded_solution"] = all(Fraction(str(lo)) <= values[n] <= Fraction(str(hi)) for n, (lo, hi) in data["variables"].items())
        valid = True
        for c in data["constraints"]:
            lhs = sum(Fraction(str(co)) * values[n] for n, co in c["coefficients"].items())
            rhs = Fraction(str(c["rhs"]))
            valid &= {"<=": lhs <= rhs, ">=": lhs >= rhs, "==": lhs == rhs, "!=": lhs != rhs,
                      "<": lhs < rhs, ">": lhs > rhs}[c["op"]]
        checks["constraint_substitution"] = bool(valid)
        if family == "optimization":
            checks["integer_domain"] = all(v.denominator == 1 for v in values.values())
            objective = sum(c * values[n] for n, c in data["objective"]["coefficients"].items())
            checks["objective_substitution"] = math.isclose(float(objective), output["objective_value"], abs_tol=1e-6)
            if output["solver_status"] == "OPTIMAL":
                # OPTIMAL is a claim about the bound: the proof's best bound must meet the objective (gap 0).
                bound = (answer.get("proof") or {}).get("bound")
                checks["optimality_bound_met"] = bound is not None and math.isclose(
                    float(bound), float(objective), abs_tol=1e-6)
            if output["solver_status"] == "OPTIMAL" and checks["constraint_substitution"] and checks["integer_domain"]:
                # A second engine attacks the optimality claim: no feasible assignment may beat it.
                better = _z3_integer_check(data, strictly_better_than=objective)
                cross["optimality_cross_engine"] = better
                if better is not None:
                    checks["optimality_cross_engine"] = better == "unsat"
                else:
                    dissent.append("OPTIMAL was not re-checked by a second engine (Z3 unavailable or undecided); "
                                   "optimality rests on CP-SAT's report.")
            elif output["solver_status"] == "FEASIBLE":
                dissent.append("FEASIBLE is not OPTIMAL: the assignment satisfies the model; optimality is unproven "
                               f"(reported gap {artifact.get('optimality_gap')}).")
    elif family == "optimization" and output["solver_status"] == "INFEASIBLE":
        verdict = _z3_integer_check(data)
        cross["infeasibility_cross_engine"] = verdict
        if verdict is not None:
            checks["infeasibility_cross_engine"] = verdict == "unsat"
        else:
            dissent.append("INFEASIBLE was not re-checked by a second engine (Z3 unavailable or undecided).")
    elif family == "formal" and output["solver_status"] == "UNSAT":
        cross["unsat_core"] = _z3_core_check(data, artifact.get("unsat_core") or [])
        if cross["unsat_core"]["core_unsat"] is not None:
            checks["unsat_core_recheck"] = cross["unsat_core"]["core_unsat"]
        if cross["unsat_core"]["minimal"] is False:
            dissent.append("The reported unsat core is valid but not minimal: a smaller core exists.")
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
        # Written apart from the solver's tokenizer: a restatement whose figures or polarity differ from its supporting
        # spans may not be reported as unchanged.
        support = [b["quote"] for b in data["bindings"] if b["relationship"] == "supports"]
        if support:
            reported = {c["class"] for c in output.get("distortions") or []}
            figure_gap, polarity_gap = _restatement_gaps(data["claim"], support)
            checks["restatement_rechecked"] = (not figure_gap or "figure" in reported) and \
                (not polarity_gap or "negation" in reported)
        dissent.append("Declared provenance/quality need separate authentication; quote binding does not prove entailment.")
    elif family == "robust_pattern":
        # Recompute the median and MAD with the standard library and re-derive every flag.
        values = [float(v) for v in data["observations"]]
        median = statistics.median(values)
        mad = statistics.median(abs(v - median) for v in values)
        threshold = float(data.get("threshold", 3.5))
        checks["artifact_observations_match_input"] = artifact["observations"] == values
        checks["independent_median_mad"] = math.isclose(output["median"], median) and math.isclose(output["mad"], mad)
        if mad > 0:
            checks["independent_flags"] = output["anomalies"] == [
                i for i, v in enumerate(values) if abs(0.6745 * (v - median) / mad) > threshold]
        else:
            # More than half the values equal the median: the documented fallback scale is 1.253314 x the mean
            # absolute deviation; a constant series flags nothing. Re-derived here, never skipped.
            mean_ad = sum(abs(v - median) for v in values) / len(values)
            expected = ([i for i, v in enumerate(values) if abs(v - median) / (1.253314 * mean_ad) > threshold]
                        if mean_ad > 0 else [])
            checks["independent_flags"] = output["anomalies"] == expected
        dissent.append("Flags are statistical; a flagged value is not shown to be an error or an attack.")
    elif family == "crowd":
        classes = data["classes"]
        post, labels = output["posteriors"], output["labels"]
        checks["posteriors_normalised"] = all(math.isclose(sum(p), 1, abs_tol=1e-6) for p in post.values())
        checks["labels_are_posterior_argmax"] = all(
            labels[i] is None or labels[i] == classes[max(range(len(classes)), key=lambda c: (p[c], -c))]
            for i, p in post.items())
        tally = {}
        for r in data["labels"]:
            key = (str(r["item_id"]), str(r["independence_group"]))
            tally.setdefault(key, []).append(r["label"])
        decided = {item for (item, _), got in tally.items()
                   if sorted(got.count(c) for c in set(got))[-1:] != sorted(got.count(c) for c in set(got))[-2:-1]}
        checks["every_decidable_item_answered"] = set(labels) == decided
        objective = [step["map_objective"] for step in artifact["trace"]["em"]]
        checks["em_objective_non_decreasing"] = all(b >= a - 1e-6 * max(1.0, abs(a)) for a, b in zip(objective, objective[1:]))
        # Tie the answer to the votes (review 2026-10-15, H3): recompute one E-step from the artifact's fitted model
        # and the raw votes, check the model is (near) a fixed point of one M-step from the reported posteriors,
        # and resolve label switching by the standard convention that observers are better than chance.
        k = len(classes)
        model = artifact.get("model") or {}
        prior, confusion = model.get("prior"), model.get("confusion") or {}
        votes = {}
        for (item, group), got in tally.items():
            counts = {c: got.count(c) for c in set(got)}
            top = max(counts.values())
            winners = [c for c in classes if counts.get(c) == top]
            if len(winners) == 1:
                votes.setdefault(item, {})[group] = classes.index(winners[0])
        well_formed = (isinstance(prior, list) and len(prior) == k and set(confusion) >= {g for v in votes.values()
                                                                                         for g in v})
        checks["fitted_model_present"] = well_formed
        if well_formed:
            recomputed = {}
            for item, by_group in votes.items():
                logs = [math.log(prior[c]) + sum(math.log(confusion[g][c][label]) for g, label in by_group.items())
                        for c in range(k)]
                top = max(logs)
                total = sum(math.exp(x - top) for x in logs)
                recomputed[item] = [math.exp(x - top) / total for x in logs]
            checks["posteriors_recomputed_from_votes"] = set(recomputed) == set(post) and all(
                all(math.isclose(a, b, abs_tol=1e-6) for a, b in zip(recomputed[i], post[i])) for i in post)
            smoothing = float(artifact["trace"].get("smoothing", data.get("smoothing", 1.0)))
            em = artifact["trace"]["em"]
            converged = len(em) >= 2 and abs(em[-1]["map_objective"] - em[-2]["map_objective"]) < 1e-7
            if converged:
                counts = {g: [[smoothing] * k for _ in range(k)] for g in confusion}
                for item, by_group in votes.items():
                    for g, label in by_group.items():
                        for c in range(k):
                            counts[g][c][label] += post[item][c]
                checks["model_is_m_step_fixed_point"] = all(
                    math.isclose(counts[g][c][j] / sum(counts[g][c]), confusion[g][c][j], abs_tol=1e-3)
                    for g in counts for c in range(k) for j in range(k))
            else:
                dissent.append("EM stopped at its iteration cap: the M-step fixed-point check was not applied.")
            reliability = [sum(prior[c] * confusion[g][c][c] for c in range(k)) for g in confusion]
            checks["observers_better_than_chance_on_average"] = sum(reliability) / len(reliability) > 1 / k
        dissent.append("Dawid-Skene assumes observers err independently given the true class; correlated error "
                       "outside the declared independence groups is not detected.")
    elif family in ("swarm", "blackbox"):
        # Closed forms written here, independently of greg.cognition.repertoire (review 2026-10-15, M5).
        closed = {"sphere": lambda z: sum(v * v for v in z),
                  "rastrigin": lambda z: 10 * len(z) + sum(v * v - 10 * math.cos(2 * math.pi * v) for v in z),
                  "ackley": lambda z: (-20 * math.exp(-0.2 * math.sqrt(sum(v * v for v in z) / len(z)))
                                       - math.exp(sum(math.cos(2 * math.pi * v) for v in z) / len(z)) + 20 + math.e),
                  # declared with its minimum at the shift: evaluated at z + 1
                  "rosenbrock": lambda z: sum(100 * ((z[i + 1] + 1) - (z[i] + 1) ** 2) ** 2 + (1 - (z[i] + 1)) ** 2
                                              for i in range(len(z) - 1)),
                  "griewank": lambda z: (1 + sum(v * v for v in z) / 4000
                                         - math.prod(math.cos(v / math.sqrt(i + 1)) for i, v in enumerate(z)))}
        shift = [float(v) for v in data["shift"]]
        bounds = [(float(lo), float(hi)) for lo, hi in data["bounds"]]
        budget = int(data["budget"])
        x = output["candidate"]
        checks["candidate_in_bounds"] = len(x) == len(bounds) and all(lo <= v <= hi for v, (lo, hi) in zip(x, bounds))
        checks["independent_fitness"] = (data["function"] in closed and len(x) == len(shift) and math.isclose(
            closed[data["function"]]([a - b for a, b in zip(x, shift)]), output["fitness"], rel_tol=1e-9,
            abs_tol=1e-12))
        checks["evaluation_budget"] = output["evaluations"] <= budget
        trace = artifact.get("trace") or []
        if family == "swarm":                      # the swarm always spends its whole budget
            checks["evaluation_count_matches_method"] = output["evaluations"] == budget
        if trace:                                  # the last recorded improvement is the reported best
            checks["trace_consistent"] = (math.isclose(trace[-1]["fitness"], output["fitness"], rel_tol=1e-12,
                                                       abs_tol=1e-15)
                                          and trace[-1]["evaluation"] <= output["evaluations"])
        dissent.append("A heuristic search returns the best point it evaluated; no global-optimality certificate.")
    elif proof_class == "genome_certificate":
        # IntelligenceGenome library: the genome's own independent check (never its solve path) plus
        # identity, evidence-type and input bindings of the envelope.
        from .genomes import library
        checks.update(library.check(family, data, output, answer["proof"]))
        dissent.append(f"Evidence type {answer['proof']['evidence_type']}: valid within the genome's native model; "
                       "real-world applicability requires separate outcome evidence.")
    else:
        dissent.append("Typed artifact verified; solver quality and real-world applicability require separate outcome evidence.")
    if family in ("formal", "optimization"):
        requirements = data.get("requirements", [])
        checks["requirement_coverage"] = not requirements or set(requirements) == {c.get("requirement_id") for c in data["constraints"]}
        dissent.append("Formal encoding may omit a material condition. Satisfiability/optimality is conditional on that encoding.")
        if output["solver_status"] in ("UNKNOWN", "MODEL_INVALID"):
            checks["unknown_not_valid"] = answer["formal_validity"] == "UNKNOWN" and answer["status"] != "ANSWER"
        if output["solver_status"] in ("UNSAT", "INFEASIBLE"):
            dissent.append("UNSAT/core and INFEASIBLE are solver reports; no independent infeasibility certificate is established.")
        if output["solver_status"] == "INFEASIBLE" and checks.get("infeasibility_cross_engine"):
            dissent.append("INFEASIBLE is corroborated by Z3 on the same integer model (a different engine); "
                           "agreement between two engines is still not a proof certificate.")
        elif output["solver_status"] == "UNSAT" and checks.get("unsat_core_recheck"):
            dissent.append("The unsat core was re-checked by a fresh Z3 solver: same engine, so a Z3 defect would be "
                           f"shared ({cross['unsat_core']['status']}).")
    return {"verdict": "REFUTED" if not all(checks.values()) else "STRUCTURALLY_VERIFIED",
            "checks": checks, "dissent": dissent, "artifact_digest": digest(answer["proof"]),
            "cross_checks": cross,
            "inconclusive": sorted(k for k, v in cross.items() if v is None or (isinstance(v, dict) and v["core_unsat"] is None)),
            "independence": ("separate verification functions in reviewed Kernel code; CP-SAT optimality and "
                             "infeasibility claims are re-checked by Z3 where it is installed; no independent "
                             "external evaluator")}


# The verifier runs inside the cognition worker under the request's latency limit (5 s by default), so the
# second engine gets a fixed share of it. Running out of budget is "undecided", never a pass or a refutation.
CROSS_CHECK_BUDGET_S = 1.5
MINIMALITY_CAP = 16  # cores larger than this are re-checked but not tested for minimality


def _remaining_ms(deadline):
    left = int((deadline - time.monotonic()) * 1000)
    return left if left >= 50 else None


def _z3_integer_check(data, *, strictly_better_than=None, budget_s=CROSS_CHECK_BUDGET_S):
    """'sat' | 'unsat' | None (engine unavailable or undecided). Integer model, as CP-SAT solved it."""
    deadline = time.monotonic() + budget_s
    try:
        import z3
    except ImportError:
        return None

    def whole(x):
        value = Fraction(str(x))
        if value.denominator != 1:
            raise ValueError(x)
        return int(value)

    solver = z3.Solver()
    vs = {n: z3.Int(n) for n in data["variables"]}
    try:
        for n, (lo, hi) in data["variables"].items():
            solver.add(vs[n] >= whole(lo), vs[n] <= whole(hi))
        for c in data["constraints"]:
            lhs = z3.Sum([whole(co) * vs[n] for n, co in c["coefficients"].items()]) if c["coefficients"] else z3.IntVal(0)
            rhs = whole(c["rhs"])
            solver.add(_relation(c["op"], lhs, rhs))
        if strictly_better_than is not None:
            objective = data["objective"]
            expr = z3.Sum([whole(co) * vs[n] for n, co in objective["coefficients"].items()])
            bound = whole(strictly_better_than)
            solver.add(expr < bound if objective["sense"] == "min" else expr > bound)
    except (ValueError, TypeError, ArithmeticError, KeyError):
        return None  # not a model this check can pose; the second engine stays silent rather than truncate or guess
    left = _remaining_ms(deadline)
    if left is None:
        return None
    solver.set(timeout=left)
    return _status(z3, solver.check())


def _z3_core_check(data, core, budget_s=CROSS_CHECK_BUDGET_S):
    """Re-check a reported unsat core with a fresh solver, then test it for minimality."""
    deadline = time.monotonic() + budget_s
    try:
        import z3
    except ImportError:
        return {"core_unsat": None, "minimal": None, "status": "engine unavailable"}

    def check(indices):
        left = _remaining_ms(deadline)
        if left is None:
            return None
        solver = z3.Solver()
        solver.set(timeout=left)
        vs = {n: z3.Real(n) for n in data["variables"]}
        for n, (lo, hi) in data["variables"].items():
            solver.add(vs[n] >= z3.RealVal(str(lo)), vs[n] <= z3.RealVal(str(hi)))
        for i in indices:
            c = data["constraints"][i]
            lhs = (z3.Sum([z3.RealVal(str(co)) * vs[n] for n, co in c["coefficients"].items()])
                   if c["coefficients"] else z3.RealVal(0))
            rhs = z3.RealVal(str(c["rhs"]))
            try:
                solver.add(_relation(c["op"], lhs, rhs))
            except KeyError:
                return None  # an operator this re-check cannot pose is undecided, never a crash
        return _status(z3, solver.check())

    try:
        indices = sorted({int(str(name).removeprefix("constraint_")) for name in core})
    except ValueError:
        return {"core_unsat": False, "minimal": None, "status": "core names do not identify constraints"}
    if not indices or any(not 0 <= i < len(data["constraints"]) for i in indices):
        return {"core_unsat": False, "minimal": None, "status": "core is empty or names unknown constraints"}
    whole = check(indices)
    if whole != "unsat":
        return {"core_unsat": None if whole is None else False, "minimal": None,
                "status": "core re-check undecided" if whole is None else "the reported core is satisfiable"}
    if len(indices) > MINIMALITY_CAP:
        return {"core_unsat": True, "minimal": None,
                "status": f"re-checked; minimality not tested (core of {len(indices)} exceeds {MINIMALITY_CAP})"}
    drops = []
    for i in indices:
        drops.append(check([j for j in indices if j != i]))
        if drops[-1] == "unsat":
            break  # one removable member already proves a smaller core exists
    minimal = False if "unsat" in drops else None if None in drops else True
    return {"core_unsat": True, "minimal": minimal,
            "status": ("re-checked; minimal" if minimal else "re-checked; minimality undecided" if minimal is None
                       else "re-checked; not minimal (a smaller core exists)")}


def _relation(op, lhs, rhs):
    """The constraint operators the solvers accept, strict < and > included (formal models are real-valued)."""
    return {"<=": lambda: lhs <= rhs, ">=": lambda: lhs >= rhs, "==": lambda: lhs == rhs, "!=": lambda: lhs != rhs,
            "<": lambda: lhs < rhs, ">": lambda: lhs > rhs}[op]()


def _status(z3, result):
    return "sat" if result == z3.sat else "unsat" if result == z3.unsat else None


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
