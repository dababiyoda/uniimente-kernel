"""Independent falsifier over emitted artifacts; it has no authority or effect adapter."""
from __future__ import annotations

from fractions import Fraction
import math
import statistics

from .contracts import CognitionError, ProofArtifact, digest


def verify(family, data, answer, proof_class):
    checks, dissent = {}, []
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
            elif output["solver_status"] == "FEASIBLE":
                dissent.append("FEASIBLE: the plan is feasible; optimality is unproven (solver stopped early).")
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
