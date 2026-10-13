"""Independent falsifier over emitted artifacts; it has no authority or effect adapter."""
from __future__ import annotations

from fractions import Fraction
import math

from .contracts import CognitionError, ProofArtifact, digest


def verify(family, data, answer, proof_class):
    checks, dissent, cross = {}, [], {}
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
            if output["solver_status"] == "OPTIMAL" and checks["constraint_substitution"]:
                # A different engine attacks the optimality claim: nothing feasible may beat it.
                better = _z3_integer_check(data, strictly_better_than=objective)
                cross["optimality_cross_engine"] = better
                if better is not None:
                    checks["optimality_cross_engine"] = better == "unsat"
            elif output["solver_status"] == "FEASIBLE":
                dissent.append("FEASIBLE is not OPTIMAL: the assignment satisfies the model; optimality is unproven "
                               f"(reported gap {answer['proof'].get('optimality_gap')}).")
    elif family == "optimization" and output["solver_status"] == "INFEASIBLE":
        verdict = _z3_integer_check(data)
        cross["infeasibility_cross_engine"] = verdict
        if verdict is not None:
            checks["infeasibility_cross_engine"] = verdict == "unsat"
    elif family == "formal" and output["solver_status"] == "UNSAT":
        core = answer["proof"].get("unsat_core") or []
        recheck = _z3_core_check(data, core)
        cross["unsat_core"] = recheck
        if recheck["core_unsat"] is not None:
            checks["unsat_core_recheck"] = recheck["core_unsat"]
        dissent.append("The core was re-checked by a fresh Z3 solver: same engine, so a Z3 defect would be shared.")
    elif family in ("graph", "search") and not output["reachable"]:
        checks["unreachable_recheck"] = _reachable(data) is False
    elif family in ("graph", "search") and output["reachable"]:
        edges = {(a, b): w for a, b, w in data["edges"]}
        if not data.get("directed", True):
            edges.update({(b, a): w for (a, b), w in list(edges.items())})
        path = output["path"]
        checks["path_endpoints"] = path[0] == data["start"] and path[-1] == data["goal"]
        checks["path_edges"] = all((a, b) in edges for a, b in zip(path, path[1:]))
        checks["path_cost"] = checks["path_edges"] and math.isclose(sum(edges[a, b] for a, b in zip(path, path[1:])), output["cost"])
        if family == "graph":
            # Independent standard-library Dijkstra attacks the NetworkX optimality claim.
            best = _shortest(edges, data["start"], data["goal"])
            checks["path_optimal_recheck"] = best is not None and math.isclose(best, output["cost"])
    elif family == "estimation":
        checks["ordered_range"] = output["low"] <= output["central"] <= output["high"]
        dissent.append("Bounds are assumptions; no calibrated probability or external market proof follows.")
    elif family == "causal":
        if output.get("effect") is not None:
            treated = [x for x in data["treated"] if x is not None]
            control = [x for x in data["control"] if x is not None]
            recomputed = sum(treated) / len(treated) - sum(control) / len(control)
            checks["estimate_recompute"] = math.isclose(recomputed, output["effect"], rel_tol=1e-9, abs_tol=1e-9)
        dissent.append("Randomization and identification assumptions have not been independently established in reality.")
    elif family == "probabilistic" and "alpha" in output:
        checks["posterior_recompute"] = (math.isclose(output["alpha"], data["alpha"] + data["successes"]) and
                                         math.isclose(output["beta"], data["beta"] + data["failures"]))
        dissent.append("Typed artifact verified; the prior and exchangeability remain assumptions.")
    elif family == "semantic":
        dissent.append("Source references are supplied data; citation presence does not verify claim entailment.")
    else:
        dissent.append("Typed artifact verified; solver quality and real-world applicability require separate outcome evidence.")
    if family in ("formal", "optimization"):
        dissent.append("Formal encoding may omit a material condition. Satisfiability/optimality is conditional on that encoding.")
    inconclusive = sorted(k for k, v in cross.items() if v is None)
    return {"verdict": "REFUTED" if not all(checks.values()) else "STRUCTURALLY_VERIFIED",
            "checks": checks, "dissent": dissent, "artifact_digest": digest(answer["proof"]),
            "cross_checks": cross, "inconclusive": inconclusive,
            "independence": ("separate verification functions in reviewed Kernel code; optimization and "
                             "infeasibility claims re-checked by a different engine (Z3) where available; "
                             "no independent external evaluator")}


def _z3_integer_check(data, *, strictly_better_than=None, timeout_ms=4000):
    """'sat' | 'unsat' | None (engine unavailable or undecided). Integer model, as CP-SAT solved it."""
    try:
        import z3
    except ImportError:
        return None
    solver = z3.Solver()
    solver.set(timeout=timeout_ms)
    vs = {n: z3.Int(n) for n in data["variables"]}
    for n, (lo, hi) in data["variables"].items():
        solver.add(vs[n] >= int(lo), vs[n] <= int(hi))
    for c in data["constraints"]:
        lhs = z3.Sum([int(co) * vs[n] for n, co in c["coefficients"].items()]) if c["coefficients"] else z3.IntVal(0)
        rhs = int(c["rhs"])
        solver.add({"<=": lhs <= rhs, ">=": lhs >= rhs, "==": lhs == rhs, "!=": lhs != rhs}[c["op"]])
    if strictly_better_than is not None:
        objective = data["objective"]
        expr = z3.Sum([int(co) * vs[n] for n, co in objective["coefficients"].items()])
        bound = int(strictly_better_than)
        solver.add(expr < bound if objective["sense"] == "min" else expr > bound)
    return _status(z3, solver.check())


def _z3_core_check(data, core, timeout_ms=4000):
    """Re-check a reported unsat core with a fresh solver, then test it for minimality."""
    try:
        import z3
    except ImportError:
        return {"core_unsat": None, "minimal": None, "status": "engine unavailable"}

    def check(indices):
        solver = z3.Solver()
        solver.set(timeout=timeout_ms)
        vs = {n: z3.Real(n) for n in data["variables"]}
        for n, (lo, hi) in data["variables"].items():
            solver.add(vs[n] >= z3.RealVal(str(lo)), vs[n] <= z3.RealVal(str(hi)))
        for i in indices:
            c = data["constraints"][i]
            lhs = (z3.Sum([z3.RealVal(str(co)) * vs[n] for n, co in c["coefficients"].items()])
                   if c["coefficients"] else z3.RealVal(0))
            rhs = z3.RealVal(str(c["rhs"]))
            solver.add({"<=": lhs <= rhs, ">=": lhs >= rhs, "==": lhs == rhs, "!=": lhs != rhs}[c["op"]])
        return _status(z3, solver.check())

    try:
        indices = [int(str(name).removeprefix("constraint_")) for name in core]
    except ValueError:
        return {"core_unsat": False, "minimal": None, "status": "core names do not identify constraints"}
    if not indices or any(not 0 <= i < len(data["constraints"]) for i in indices):
        return {"core_unsat": False, "minimal": None, "status": "core is empty or names unknown constraints"}
    whole = check(indices)
    if whole != "unsat":
        return {"core_unsat": None if whole is None else False, "minimal": None,
                "status": "core re-check undecided" if whole is None else "the reported core is satisfiable"}
    drops = [check([j for j in indices if j != i]) for i in indices]
    minimal = None if None in drops else all(d == "sat" for d in drops)
    return {"core_unsat": True, "minimal": minimal,
            "status": ("re-checked; minimal" if minimal else "re-checked; minimality undecided" if minimal is None
                       else "re-checked; not minimal (a smaller core exists)")}


def _status(z3, result):
    return "sat" if result == z3.sat else "unsat" if result == z3.unsat else None


def _shortest(edges, start, goal):
    import heapq
    best, queue = {start: 0.0}, [(0.0, start)]
    while queue:
        dist, node = heapq.heappop(queue)
        if node == goal:
            return dist
        if dist > best.get(node, math.inf):
            continue
        for (a, b), w in edges.items():
            if a == node and dist + w < best.get(b, math.inf):
                best[b] = dist + w
                heapq.heappush(queue, (dist + w, b))
    return None


def _reachable(data):
    edges = {(a, b) for a, b, _ in data["edges"]}
    if not data.get("directed", True):
        edges |= {(b, a) for a, b in edges}
    seen, stack = {data["start"]}, [data["start"]]
    while stack:
        node = stack.pop()
        for a, b in edges:
            if a == node and b not in seen:
                seen.add(b)
                stack.append(b)
    return data["goal"] in seen


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
    governing = _jurisdiction(receipts)
    state = ("HUMAN_REVIEW_REQUIRED" if human else "CONFLICT" if conflicts else
             "BLOCKED_BY_JURISDICTION" if governing else "ABSTAIN" if abstained else "RECOMMENDATION_ONLY")
    return {"state": state, "governing_findings": governing, "next_decisive_test": _next_test(receipts, conflicts, governing),
            "conflicting_questions": conflicts, "conflicting_classes": sorted({c["epistemic_class"] for c in conflicts}),
            "jurisdictions": {cls: [r["receipt_id"] for r in rows] for cls, rows in by_class.items()},
            "questions": [{"problem_id": r["problem_id"], "method": r["method"], "epistemic_class": r["epistemic_class"],
                           "assumptions": r["assumptions"], "proof_type": r["proof_type"],
                           "missing_information": r["missing_information"], "dominance": "not inferred across different questions or classes"}
                          for r in receipts],
            "dissent": [r["strongest_counterargument"] for r in receipts], "authority_created": False}


# A finding inside its own jurisdiction that no other method may outvote (directive §8).
_VETO = {
    ("causal", "UNIDENTIFIED"): "a non-identified causal effect is not established by plausibility elsewhere",
    ("constraint_feasibility", "UNSAT"): "an infeasible model cannot be averaged with enthusiasm",
    ("optimization", "INFEASIBLE"): "an infeasible model cannot be averaged with enthusiasm",
}


def _jurisdiction(receipts):
    """Claims shared across receipts are settled by the finding that holds jurisdiction over them."""
    by_claim = {}
    for r in receipts:
        for claim in r.get("claim_ids") or []:
            by_claim.setdefault(claim, []).append(r)
    governing = []
    for claim, rows in sorted(by_claim.items()):
        for r in rows:
            status = (r.get("output") or {}).get("solver_status") or r["abstention_state"]
            why = _VETO.get((r["epistemic_class"], status))
            if r["abstention_state"] in ("REFUTED", "PROHIBITED"):
                why = f"{r['abstention_state'].lower()} findings govern every claim they touch"
            if why and len(rows) > 1:
                governing.append({"claim_id": claim, "receipt_id": r["receipt_id"], "method": r["method"],
                                  "epistemic_class": r["epistemic_class"], "finding": status, "why": why,
                                  "overrides": [o["receipt_id"] for o in rows if o is not r]})
    return governing


def _next_test(receipts, conflicts, governing):
    """The cheapest test that could settle the disagreement, or None when nothing is in dispute."""
    if not conflicts and not governing:
        return None
    # The governing jurisdiction names the decisive test before any route's own suggestion.
    if any(g["finding"] == "UNIDENTIFIED" for g in governing):
        return {"test": "a randomized comparison of the claimed intervention, or a verified identification design",
                "source": "causal jurisdiction"}
    if conflicts:
        return {"test": "independent recomputation of the disputed question by a third method with separate dependencies",
                "source": "conflicting answers to one question"}
    for r in receipts:
        proof = r.get("proof_artifact") or {}
        if proof.get("cheapest_evidence"):
            return {"test": proof["cheapest_evidence"], "source": r["receipt_id"]}
    missing = [m for r in receipts for m in r.get("missing_information") or []]
    return {"test": missing[0], "source": "missing information"} if missing else None
