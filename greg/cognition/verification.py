"""Independent falsifier over emitted artifacts; it has no authority or effect adapter."""
from __future__ import annotations

from fractions import Fraction
import math
import statistics
import time

from .contracts import CognitionError, ProofArtifact, digest

# The Z3 check below is bounded by a deterministic resource count and by a wall-clock backstop inside the verifier
# worker's own CPU and time budget. The count gives the same answer the same certificate only because each check runs
# in a fresh Z3 context: in the shared default context Z3's work on a question depends on what the process asked
# before (one answer re-verified in one process took 1,999,353, then 1,745,208, then over 2,000,000 units). The
# backstop is not deterministic: on a slow or loaded machine it can end a check before the resource count does, which
# leaves the claim UNKNOWN (uncertified and unrefuted; the certificate's reason is 'timeout' rather than 'canceled').
# Calibration (2026-10-15, one core of a shared machine): every composition model on dev and review seeds and F7's
# development items certifies within 10k units in under 60 ms. Of the honest random answers on review seeds
# 3000-3999, 100k leaves 8 UNKNOWN, each reaching the resource limit in 0.06-1.0 s, so close to the backstop; 2M
# certifies one of them (seed 3082, in 1.0-1.3 s, so only without the 1 s backstop) and stops the other 7 after 2-9 s.
# The backstop is also cut to the time the verifier has left (``deadline``): a fixed 1 s spent on an answer's
# certificate at a tight latency limit timed out answers c360103 verified without one (review seeds 3181 and 3356
# through cortex.reason at a 1.8 s limit). A check the remaining budget cannot afford is NOT_RUN, so an uncertifiable
# check never costs the answer; the claim then stays uncertified and unrefuted, as an UNKNOWN one does. A timeout of 0
# is not a short check: Z3 reads it as no limit.
Z3_RLIMIT = 100_000
Z3_TIMEOUT_MS = 1000
Z3_MIN_TIMEOUT_MS = 20
# CP-SAT reports the optimisation family's integer bound and objective as doubles computed from integers (a scaling
# factor times an integer plus an offset), so an honest one sits within a few units in the last place of its integer
# (review seed 3082: -172467568588.00003, one unit at that magnitude). A reported bound or gap is checked to that noise,
# never to 1/2 (fix review r3: a bound and a gap each allowed 1/2 stacked, so a plan 1 short was certified with a gap
# of 0.02): relative 1e-13 (at least 450 units in the last place at any magnitude, yet at most 0.1 up to the receipt's
# 1e12 ceiling, where relative 1e-9 would allow 1000, review V1) with an absolute floor of 1e-9 near zero.
# Calibration (2026-10-16, review seeds 3000-3999, honest CP-SAT answers from the review's, the round-3 fixer's and two
# large-magnitude generators at full and 1-100 ms budgets): of 7,738 OPTIMAL and 1,112 FEASIBLE answers (1,198 of
# them at magnitude 1e9 or more), 17 reported a bound, objective or gap off its exact value, each by at most one unit
# in the last place (relative 2.1e-16).
NOISE_REL, NOISE_ABS = Fraction(1, 10**13), Fraction(1, 10**9)

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


def _noise(*values):
    """The largest difference CP-SAT's honest rounding noise explains between numbers of these magnitudes."""
    return max(NOISE_ABS, NOISE_REL * max(abs(v) for v in values))


def _z3_certificate(data, *, integers, better_than=None, sense="max", deadline=None):
    """Ask Z3 for an assignment within the model's bounds and constraints, strictly better than ``better_than`` when
    it is given. Z3 shares no code with CP-SAT: sat REFUTES the claim (the witness is returned), unsat certifies it,
    and unknown (the resource or time limit) leaves it uncertified, never refuted. A ``deadline`` (time.monotonic())
    cuts the time limit to what is left before it; with less than Z3_MIN_TIMEOUT_MS left the check is NOT_RUN."""
    limits = {"rlimit": Z3_RLIMIT, "timeout_ms": Z3_TIMEOUT_MS}

    def unaffordable():
        if deadline is None:
            return None
        left = math.floor(min(max(0.0, deadline - time.monotonic()), Z3_TIMEOUT_MS / 1000) * 1000)
        limits["timeout_ms"] = left
        if left < Z3_MIN_TIMEOUT_MS:            # nor may the timeout reach 0, which Z3 reads as no limit
            return {"engine": "z3", "status": "NOT_RUN", "limits": limits,
                    "reason": f"the verifier's remaining latency budget ({left} ms) cannot afford the check"}
        return None
    # asked before importing Z3 and building the model too, which take time of their own (0.1-0.2 s on a loaded core)
    if spent := unaffordable():
        return spent
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
    ctx = z3.Context()                      # fresh per check, so the resource count is deterministic (above)

    def const(x):
        if integers:
            return z3.IntVal(x, ctx)
        x = Fraction(str(x))
        return z3.Q(x.numerator, x.denominator, ctx)
    vs = {n: (z3.Int if integers else z3.Real)(n, ctx) for n in data["variables"]}

    def linear(coefficients):
        return z3.Sum([const(co) * vs[n] for n, co in coefficients.items()]) if coefficients else const(0)
    solver = z3.Solver(ctx=ctx)
    solver.set("rlimit", Z3_RLIMIT)
    for n, (lo, hi) in data["variables"].items():
        solver.add(vs[n] >= const(lo), vs[n] <= const(hi))
    for c in data["constraints"]:
        lhs, rhs = linear(c["coefficients"]), const(c["rhs"])
        solver.add({"<=": lhs <= rhs, ">=": lhs >= rhs, "==": lhs == rhs, "!=": lhs != rhs,
                    "<": lhs < rhs, ">": lhs > rhs}[c["op"]])
    if better_than is not None:
        objective = linear(data["objective"]["coefficients"])
        value = (z3.IntVal(better_than.numerator, ctx) if integers and better_than.denominator == 1
                 else z3.Q(better_than.numerator, better_than.denominator, ctx))
        solver.add(objective > value if sense == "max" else objective < value)
    if spent := unaffordable():
        return spent
    solver.set("timeout", limits["timeout_ms"])
    status = solver.check()
    out = {"engine": "z3", "version": z3.get_version_string(), "limits": limits,
           "question": ("assignment within the bounds and constraints" +
                        (f" with objective {'>' if sense == 'max' else '<'} {better_than}" if better_than is not None
                         else "")),
           # the bound the question tests: once CERTIFIED, no assignment's objective lies beyond it
           **({"bound": int(better_than)} if better_than is not None and better_than.denominator == 1 else {})}
    if status == z3.sat:
        model = solver.model()
        value = (lambda v: model.eval(v, model_completion=True).as_long()) if integers else \
            (lambda v: str(model.eval(v, model_completion=True).as_fraction()))
        return {**out, "status": "REFUTED", "witness": {n: value(v) for n, v in vs.items()}}
    if status == z3.unsat:
        return {**out, "status": "CERTIFIED"}
    return {**out, "status": "UNKNOWN", "reason": str(solver.reason_unknown())[:200]}


def verify(family, data, answer, proof_class, *, deadline=None):
    """``deadline`` (time.monotonic()) bounds the Z3 certificate's time, never the checks; the verifier worker passes
    the end of its caller's budget less a reserve for returning the answer. Without one (an in-process caller) the
    certificate has its fixed backstop."""
    checks, dissent, beyond, own_report, cross = {}, [], None, None, {}
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
            # the family is integer, so the solution's objective is an exact integer the reported numbers must round to
            objective = sum(Fraction(str(c)) * values[n] for n, c in data["objective"]["coefficients"].items())
            checks["objective_substitution"] = _near(output["objective_value"], objective)
            # Self-consistency of the solver's own report, not a certificate (review V2, V5): an OPTIMAL claim meets
            # its bound (zero gap, review of #179 M6); a FEASIBLE claim's bound lies on the far side of its
            # objective; a reported gap is |objective - bound|. Each to CP-SAT's rounding noise only (NOISE above).
            maximise = data["objective"]["sense"] == "max"
            bound, gap = _exact(artifact.get("bound")), artifact.get("optimality_gap")
            noise = _noise(objective, bound) if bound is not None else None
            if output["solver_status"] == "OPTIMAL":
                checks["optimal_objective_meets_its_bound"] = bound is not None and abs(bound - objective) <= noise
            elif output["solver_status"] == "FEASIBLE":
                checks["feasible_bound_beyond_its_objective"] = bound is not None and (
                    bound >= objective - noise if maximise else bound <= objective + noise)
            if gap is not None:
                checks["optimality_gap_recomputed"] = bound is not None and _exact(gap) is not None and \
                    abs(_exact(gap) - abs(objective - bound)) <= noise
            failed = [k for k in ("optimal_objective_meets_its_bound", "feasible_bound_beyond_its_objective",
                                  "optimality_gap_recomputed") if checks.get(k) is False]
            if failed:
                own_report = (f"its solution's objective is {objective}, its bound {artifact.get('bound')} and its gap "
                              f"{gap} ({' and '.join(failed)} failed)")
            # What the certificate below asks Z3 to beat: an OPTIMAL claim's own objective, or a FEASIBLE claim's
            # bound (review r2: a forged bound, and the gap measured from it, verified unchecked). Objectives are
            # integers, so a bound b stands for the integer floor(b + noise) (max) or ceil(b - noise) (min), the noise
            # at b's own magnitude (the plan's objective may be far larger): any assignment beyond b by more than
            # CP-SAT's rounding noise refutes it (fix review r3: with 1/2 here a bound 0.49 short of the optimum was
            # certified), and an honest bound is never refuted. The certificate carries that integer as its bound,
            # from which a consumer measures the gap, never from the artifact's own.
            if output["solver_status"] == "OPTIMAL":
                beyond = objective
            elif output["solver_status"] == "FEASIBLE" and bound is not None:
                beyond = Fraction(math.floor(bound + _noise(bound)) if maximise else math.ceil(bound - _noise(bound)))
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
        claim, certificate = output["solver_status"], None
        negative = claim in ("UNSAT", "INFEASIBLE")
        if (negative or beyond is not None) and all(checks.values()):
            # A negative claim is checked like a positive one (review: a false INFEASIBLE or UNSAT verified on
            # artifact coherence alone), and an OPTIMAL or FEASIBLE claim gets a certificate rather than the solver's
            # own bound (review V2): any assignment within the bounds and constraints (strictly better than the
            # OPTIMAL objective, or beyond the FEASIBLE bound) refutes.
            certificate = {"claim": claim, **_z3_certificate(
                data, integers=family == "optimization", better_than=beyond,
                sense=(data.get("objective") or {}).get("sense", "max"), deadline=deadline),
                # the formal family's own engine is Z3: its re-check catches a forged or corrupted claim, not a Z3
                # defect
                "independence": "same engine as the solver (Z3), separate encoding and process" if family == "formal"
                else "different engine from the solver (Z3 against CP-SAT)"}
            checks["no_feasible_assignment_found" if negative else "no_strictly_better_assignment_found"
                   if claim == "OPTIMAL" else "no_assignment_beyond_its_bound_found"] = (
                certificate["status"] != "REFUTED")
        if family == "formal" and claim == "UNSAT" and (certificate or {}).get("status") != "REFUTED":
            # The certificate re-checks the whole model. The reported core is a further claim, that these
            # constraints alone contradict each other (and minimally), so it is re-checked on its own; once the
            # model is shown satisfiable every core is too, and the certificate's witness already says so.
            cross["unsat_core"] = _z3_core_check(data, artifact.get("unsat_core") or [], deadline=deadline)
            if cross["unsat_core"]["core_unsat"] is not None:
                checks["unsat_core_recheck"] = cross["unsat_core"]["core_unsat"]
            if cross["unsat_core"]["minimal"] is False:
                dissent.append("The reported unsat core is valid but not minimal: a smaller core exists.")
        settled = certificate["status"] if certificate else None
        why = f"Z3: {certificate.get('reason')}" if certificate else "Z3 did not run"
        violated = [k for k in ("solution_variable_set", "bounded_solution", "constraint_substitution",
                                "integer_domain") if checks.get(k) is False]
        if settled == "REFUTED":
            dissent.append(f"Z3 found an {certificate['question']}: {certificate['witness']}; the " +
                           (f"FEASIBLE claim's bound {artifact['bound']} is false." if claim == "FEASIBLE" else
                            f"{claim} claim is false."))
        elif violated:
            # a solution outside its own model: never a solver-reported optimum or a verified feasible plan (fix
            # review r3: an x+y=10 plan for x+y<=4, claimed OPTIMAL, was called solver-reported)
            dissent.append(f"The {claim} claim is refuted: its solution violates its own model "
                           f"({' and '.join(violated)} failed).")
        elif own_report:
            # its bound or gap contradicts its own solution: neither solver-reported optimality nor a certificate
            dissent.append(f"The {claim} claim is refuted by its own report: {own_report}.")
        elif refuted := [k for k, ok in checks.items() if not ok]:
            dissent.append(f"The {claim} claim is refuted: {' and '.join(refuted)} failed.")
        elif claim == "FEASIBLE":
            dissent.append("FEASIBLE claims a verified feasible assignment only; its optimality is not established, "
                           + (f"and its bound {artifact['bound']} is independently certified: Z3, a different engine "
                              f"from CP-SAT, finds no {certificate['question']}." if settled == "CERTIFIED" else
                              f"and CP-SAT's bound is not independently certified ({why})."))
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
        if claim == "UNSAT" and checks.get("unsat_core_recheck"):
            dissent.append("The unsat core was re-checked by a fresh Z3 solver: same engine, so a Z3 defect would be "
                           f"shared ({cross['unsat_core']['status']}).")
    else:
        certificate = None
    return {"verdict": "REFUTED" if not all(checks.values()) else "STRUCTURALLY_VERIFIED",
            "checks": checks, "dissent": dissent, "artifact_digest": digest(answer["proof"]),
            **({"certificate": certificate} if certificate else {}),
            "cross_checks": cross,
            "inconclusive": sorted(k for k, v in cross.items() if v["core_unsat"] is None),
            "independence": "separate verification functions in reviewed Kernel code; no independent external evaluator"}


# The core re-check runs inside the verifier worker after the certificate, so it gets a fixed share of the time and
# never more than the caller's deadline leaves. Running out is "undecided", never a pass or a refutation.
CROSS_CHECK_BUDGET_S = 1.5
MINIMALITY_CAP = 16  # cores larger than this are re-checked but not tested for minimality


def _remaining_ms(deadline):
    left = int((deadline - time.monotonic()) * 1000)
    return left if left >= Z3_MIN_TIMEOUT_MS else None   # a timeout of 0 is no limit to Z3


def _z3_core_check(data, core, budget_s=CROSS_CHECK_BUDGET_S, deadline=None):
    """Re-check a reported unsat core with a fresh solver (and Z3 context), then test it for minimality."""
    end = time.monotonic() + budget_s
    deadline = end if deadline is None else min(end, deadline)
    try:
        import z3
    except ImportError:
        return {"core_unsat": None, "minimal": None, "status": "engine unavailable"}

    def check(indices):
        left = _remaining_ms(deadline)
        if left is None:
            return None
        ctx = z3.Context()
        solver = z3.Solver(ctx=ctx)
        solver.set("timeout", left)
        vs = {n: z3.Real(n, ctx) for n in data["variables"]}
        for n, (lo, hi) in data["variables"].items():
            solver.add(vs[n] >= z3.RealVal(str(lo), ctx), vs[n] <= z3.RealVal(str(hi), ctx))
        for i in indices:
            c = data["constraints"][i]
            lhs = (z3.Sum([z3.RealVal(str(co), ctx) * vs[n] for n, co in c["coefficients"].items()])
                   if c["coefficients"] else z3.RealVal(0, ctx))
            try:
                solver.add(_relation(c["op"], lhs, z3.RealVal(str(c["rhs"]), ctx)))
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
