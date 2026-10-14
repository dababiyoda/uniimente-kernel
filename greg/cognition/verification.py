"""Independent falsifier over emitted artifacts; it has no authority or effect adapter."""
from __future__ import annotations

from fractions import Fraction
import math
import time

from .contracts import CognitionError, ProofArtifact, digest


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
        dissent.append("Declared provenance/quality need separate authentication; quote binding does not prove entailment.")
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
