"""Independent falsifier over emitted artifacts; it has no authority or effect adapter."""
from __future__ import annotations

from fractions import Fraction
import math

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
        dissent.append("The certificate covers the supplied topology only; integer weights are exact, floating weights permit relative 1e-12 tolerance.")
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
