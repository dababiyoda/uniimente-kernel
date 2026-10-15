"""Independent falsifier over emitted artifacts; it has no authority or effect adapter."""
from __future__ import annotations

from fractions import Fraction
import math

from .contracts import CognitionError, ProofArtifact, digest

# The Z3 check below is bounded by a deterministic resource count (the same answer gets the same verdict); the
# wall-clock limit is a backstop inside the verifier worker's own CPU and time budget. Calibration (2026-10-15): every
# composition model on dev and review seeds and F7's development items certifies within 10k units in under 40 ms;
# 100k certified as many honest random answers (review seeds 3000-3999) as 2M did, and the 8 it leaves UNKNOWN stop
# within 0.7 s.
Z3_RLIMIT = 100_000
Z3_TIMEOUT_MS = 1000


def _exact(value):
    """A finite JSON number as an exact Fraction, else None."""
    if type(value) not in (int, float) or not math.isfinite(value):
        return None
    return Fraction(str(value))


def _near(value, exact):
    """``value`` is a finite number within 1/2 of ``exact``. The optimisation family's objectives are integers, so 1/2
    tells any two apart at every magnitude, where a relative tolerance does not (review V1: at 1e11 rel_tol=1e-9 let a
    plan 100 units short pass); it is not equality either, since CP-SAT can report an integer objective as a double
    with rounding noise (-172467568588.00003 for -172467568588, review seed 3082)."""
    value = _exact(value)
    return value is not None and abs(value - exact) < Fraction(1, 2)


def _z3_certificate(data, *, integers, better_than=None, sense="max"):
    """Ask Z3 for an assignment within the model's bounds and constraints, strictly better than ``better_than`` when
    it is given. Z3 shares no code with CP-SAT: sat REFUTES the claim (the witness is returned), unsat certifies it,
    and unknown (the resource or time limit) leaves it uncertified, never refuted."""
    limits = {"rlimit": Z3_RLIMIT, "timeout_ms": Z3_TIMEOUT_MS}
    try:
        import z3
    except ImportError:
        return {"engine": "z3", "status": "NOT_RUN", "reason": "z3-solver is not installed", "limits": limits}
    numbers = [b for bounds in data["variables"].values() for b in bounds]
    numbers += [x for c in data["constraints"] for x in (*c["coefficients"].values(), c["rhs"])]
    numbers += list((data.get("objective") or {}).get("coefficients", {}).values())
    if integers and any(type(x) is not int for x in numbers):
        return {"engine": "z3", "status": "NOT_RUN", "reason": "an integer model with a non-integer number",
                "limits": limits}

    def const(x):
        if integers:
            return z3.IntVal(x)
        x = Fraction(str(x))
        return z3.Q(x.numerator, x.denominator)
    vs = {n: (z3.Int if integers else z3.Real)(n) for n in data["variables"]}

    def linear(coefficients):
        return z3.Sum([const(co) * vs[n] for n, co in coefficients.items()]) if coefficients else const(0)
    solver = z3.Solver()
    solver.set("rlimit", Z3_RLIMIT)
    solver.set("timeout", Z3_TIMEOUT_MS)
    for n, (lo, hi) in data["variables"].items():
        solver.add(vs[n] >= const(lo), vs[n] <= const(hi))
    for c in data["constraints"]:
        lhs, rhs = linear(c["coefficients"]), const(c["rhs"])
        solver.add({"<=": lhs <= rhs, ">=": lhs >= rhs, "==": lhs == rhs, "!=": lhs != rhs,
                    "<": lhs < rhs, ">": lhs > rhs}[c["op"]])
    if better_than is not None:
        objective = linear(data["objective"]["coefficients"])
        value = (z3.IntVal(better_than.numerator) if integers and better_than.denominator == 1
                 else z3.Q(better_than.numerator, better_than.denominator))
        solver.add(objective > value if sense == "max" else objective < value)
    status = solver.check()
    out = {"engine": "z3", "version": z3.get_version_string(), "limits": limits,
           "question": ("an assignment within the bounds and constraints" +
                        (f" with objective {'>' if sense == 'max' else '<'} {better_than}" if better_than is not None
                         else ""))}
    if status == z3.sat:
        model = solver.model()
        value = (lambda v: model.eval(v, model_completion=True).as_long()) if integers else \
            (lambda v: str(model.eval(v, model_completion=True).as_fraction()))
        return {**out, "status": "REFUTED", "witness": {n: value(v) for n, v in vs.items()}}
    if status == z3.unsat:
        return {**out, "status": "CERTIFIED"}
    return {**out, "status": "UNKNOWN", "reason": str(solver.reason_unknown())[:200]}


def verify(family, data, answer, proof_class):
    checks, dissent, claimed_optimum = {}, [], None
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
            # the family is integer, so the solution's objective is an exact integer the reported numbers must round to
            objective = sum(Fraction(str(c)) * values[n] for n, c in data["objective"]["coefficients"].items())
            checks["objective_substitution"] = _near(output["objective_value"], objective)
            # Self-consistency of the solver's own report, not a certificate (review V2, V5): an OPTIMAL claim meets
            # its bound (zero gap, review of #179 M6); a FEASIBLE claim's bound lies on the far side of its
            # objective; a reported gap is |objective - bound|.
            maximise = data["objective"]["sense"] == "max"
            bound, gap = _exact(artifact.get("bound")), artifact.get("optimality_gap")
            if output["solver_status"] == "OPTIMAL":
                checks["optimal_objective_meets_its_bound"] = _near(artifact.get("bound"), objective)
            elif output["solver_status"] == "FEASIBLE":
                checks["feasible_bound_beyond_its_objective"] = bound is not None and (
                    bound > objective - Fraction(1, 2) if maximise else bound < objective + Fraction(1, 2))
            if gap is not None:
                checks["optimality_gap_recomputed"] = bound is not None and _near(gap, abs(objective - bound))
            claimed_optimum = objective if output["solver_status"] == "OPTIMAL" else None
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
        claim, certificate = output["solver_status"], None
        negative = claim in ("UNSAT", "INFEASIBLE")
        if (negative or claimed_optimum is not None) and all(checks.values()):
            # A negative claim is checked like a positive one (review: a false INFEASIBLE or UNSAT verified on
            # artifact coherence alone), and an OPTIMAL claim gets a certificate rather than the solver's own bound
            # (review V2): any assignment within the bounds and constraints (strictly better, for OPTIMAL) refutes.
            certificate = {"claim": claim, **_z3_certificate(
                data, integers=family == "optimization", better_than=claimed_optimum,
                sense=(data.get("objective") or {}).get("sense", "max")),
                # the formal family's own engine is Z3: its re-check catches a forged or corrupted claim, not a Z3
                # defect
                "independence": "same engine as the solver (Z3), separate encoding and process" if family == "formal"
                else "different engine from the solver (Z3 against CP-SAT)"}
            checks["no_feasible_assignment_found" if negative else "no_strictly_better_assignment_found"] = (
                certificate["status"] != "REFUTED")
        settled = certificate["status"] if certificate else None
        why = f"Z3: {certificate.get('reason')}" if certificate else "Z3 did not run"
        if settled == "REFUTED":
            dissent.append(f"Z3 found {certificate['question']}: {certificate['witness']}; the {claim} claim is false.")
        elif settled == "CERTIFIED" and family == "optimization":
            dissent.append(f"{claim} independently certified: Z3, a different engine from CP-SAT, finds no "
                           f"{certificate['question']}.")
        elif negative:
            dissent.append("UNSAT/core and INFEASIBLE are solver reports; no independent infeasibility certificate is "
                           "established (" + ("the verifier's Z3 re-check finds no assignment, but Z3 is also the "
                                              "solver's engine" if settled == "CERTIFIED" else
                                              f"the verifier's check was not conclusive; {why}") + ").")
        elif claim == "OPTIMAL":
            dissent.append("Optimality is solver-reported (CP-SAT OPTIMAL; bound equals objective) and not "
                           f"independently certified ({why}).")
        elif claim == "FEASIBLE":
            dissent.append("FEASIBLE claims a verified feasible assignment only; its optimality and CP-SAT's bound are "
                           "not independently certified.")
    else:
        certificate = None
    return {"verdict": "REFUTED" if not all(checks.values()) else "STRUCTURALLY_VERIFIED",
            "checks": checks, "dissent": dissent, "artifact_digest": digest(answer["proof"]),
            **({"certificate": certificate} if certificate else {}),
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
