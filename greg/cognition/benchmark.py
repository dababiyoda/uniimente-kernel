"""Frozen cross-geometry assessment and measured competency characterization.

Missing LLM baselines never imply superiority. Every characterization dimension carries a number
measured on a native workload, or says why it does not apply to the method, or names what would
measure it. Prose never stands in for a measurement.
"""
from __future__ import annotations

from fractions import Fraction
import json
from pathlib import Path
import time

from .catalog import FAMILIES, profile
from .contracts import CognitionError, digest
from .cortex import reason, registry_view
from .verification import metaconsensus, verify


ROOT = Path(__file__).resolve().parents[2]
SUITE = ROOT / "examples" / "cognition" / "frozen-suite.json"
CROSSGEO = ROOT / "tests" / "evidence" / "greg-crossgeo-v0.3"
CORTEX_METHOD = "cognition.cortex"
DIMENSIONS = ("responsiveness", "memory_depth", "prediction_horizon", "adaptability", "persistence",
              "error_correction", "problem_space", "cooperation", "generalization", "higher_scale_coherence")
STATUSES = ("measured", "not_applicable", "not_measured_here")
HORIZON_FIELDS = ("steps", "horizon")
REQUEST_CEILING_BYTES = 64 * 1024                      # compile_problem refuses larger requests
# Higher-scale GREG capabilities whose deliveries depend on a cognition operation. The venture
# template test keeps this map honest against what venture_assessment actually asks for.
HIGHER_SCALE_CONSUMERS = {"estimate": ("venture.assess",), "treatment_effect": ("venture.assess",)}
HIGHER_SCALE_RULES = {"venture.assess": "a revenue figure may not outrun its causal support "
                                        "(greg/ventures.py verify_delivery; tests/unit/test_greg_ventures.py)"}
PERSISTENCE_EVIDENCE = (
    "tests/integration/test_greg_cognition_mission.py::test_detachment_survives_restart_and_solver_cannot_bypass_it",
    "tests/integration/test_greg_cortex_mission.py::test_cortex_mission_closes_on_reobserved_evidence_and_settles_once",
    "tests/integration/test_greg_cortex_rehearsal.py")
VERIFY_ERRORS = (CognitionError, ValueError, TypeError, KeyError, ArithmeticError)


def score(receipt, case, *, require_method=True):
    expected = case["expected"]
    if (require_method and receipt.get("method") != expected["method"]) or receipt.get("abstention_state") != expected.get("state", "NONE"):
        return False
    output = receipt.get("output") or {}
    return all(output.get(k) == v for k, v in expected.get("output", {}).items())


# --- characterization -------------------------------------------------------------------------

def _measured(value, workload, **more):
    return {"status": "measured", "value": value, "workload": workload, **more}


def _not_applicable(reason, **more):
    return {"status": "not_applicable", "value": None, "reason": reason, **more}


def _not_measured(reason, would_measure):
    return {"status": "not_measured_here", "value": None, "reason": reason, "would_measure": would_measure}


def quantile(values, q):
    """Linear interpolation on sorted values; a single value is every quantile of itself."""
    if not values:
        return None
    ordered = sorted(values)
    position = q * (len(ordered) - 1)
    low, high = int(position), min(int(position) + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def _numeric_string(value):
    try:
        Fraction(value)
    except (ValueError, ZeroDivisionError):
        return False
    return True


LARGE = 10**6                                           # a corruption no bounded answer survives


def perturbations(output, path=()):
    """Yield (field path, corrupted copy) once per leaf of an answer.

    Each corruption changes exactly one leaf to a value that cannot be the correct answer: a number
    or numeric string moves by one million (a feasible point leaves its bounds, a mean leaves its
    range), a boolean flips, any other string gains a suffix. An accepted corruption names the field
    the verifier does not check.
    """
    if isinstance(output, bool):
        yield path, not output
    elif isinstance(output, (int, float)):
        yield path, output + LARGE
    elif isinstance(output, str) and _numeric_string(output):
        yield path, str(Fraction(output) + LARGE)
    elif isinstance(output, str):
        yield path, output + "~"
    elif isinstance(output, dict):
        for key, value in output.items():
            for sub, changed in perturbations(value, path + (key,)):
                yield sub, {**output, key: changed}
    elif isinstance(output, list):
        for index, value in enumerate(output):
            for sub, changed in perturbations(value, path + (index,)):
                yield sub, output[:index] + [changed] + output[index + 1:]


def perturbation_trials(family, data, receipt):
    """Run the independent falsifier against every single-leaf corruption of a verified answer."""
    if receipt.get("output") is None or receipt["evaluator_result"].get("verdict") != "STRUCTURALLY_VERIFIED":
        return []
    trials = []
    for path, changed in perturbations(receipt["output"]):
        try:
            verdict = verify(family, data, {"output": changed, "proof": receipt["proof_artifact"]}, receipt["proof_type"])
            outcome = "refuted" if verdict["verdict"] == "REFUTED" else "accepted"
        except VERIFY_ERRORS as exc:          # a raise is a refusal, never a silent acceptance
            outcome = "raised:" + type(exc).__name__
        trials.append({"field": ".".join(map(str, path)), "outcome": outcome})
    return trials


def refutations_to_demote(chosen, competitors):
    """Settled refutations after which Laplace quality drops this method below its best rival."""
    if not competitors:
        return None
    quality, evidence = Fraction(str(chosen["quality"])), int(chosen["evidence"])
    correct = round(quality * (evidence + 2) - 1)
    rival = max(Fraction(str(c["quality"])) for c in competitors)
    k = 0
    while Fraction(correct + 1, evidence + k + 2) >= rival:
        k += 1
    return k


def _responsiveness(method, rows, spec):
    latencies = [r["latency"] for r in rows if r["method"] == method]
    return _measured({"p50_seconds": quantile(latencies, .5), "p95_seconds": quantile(latencies, .95),
                      "max_seconds": max(latencies), "n": len(latencies),
                      "declared_estimate_seconds": spec.latency_estimate_seconds,
                      "p95_within_declared_estimate": quantile(latencies, .95) <= spec.latency_estimate_seconds},
                     "wall-clock per receipt over this suite's cases routed to the method; includes the "
                     "isolated worker process start")


def _memory_depth(method, receipts, journal_supplied):
    consulted = [row["evidence"] for receipt in receipts for row in receipt["alternative_methods_considered"]
                 if row["method"] == method]
    return _measured({"settled_outcomes_consulted": max(consulted, default=0), "journal_supplied": journal_supplied,
                      "forgetting": "none; competence is recomputed by full replay of the canonical journal"},
                     "settled outcomes for (method, version, geometry) replayed by greg/cognition/settlement.py "
                     "into this run's candidate ranking" + ("" if journal_supplied else
                     "; no body journal was supplied, so depth is zero by construction"))


def _prediction_horizon(method, cases, spec):
    horizons = [(field, case["request"]["data"][field]) for case in cases for field in HORIZON_FIELDS
                if field in case["request"]["data"]]
    if horizons:
        return _measured({"max_declared_steps": max(v for _, v in horizons), "fields": sorted({f for f, _ in horizons}),
                          "beyond_declared_horizon": "not computed; the receipt reports finite horizons only"},
                         "declared finite horizon in this suite's requests to the method")
    return _not_applicable(f"operations {list(spec.operations)} carry no time horizon")


def _adaptability(method, receipts, spec):
    demote = []
    for receipt in receipts:
        rows = receipt["alternative_methods_considered"]
        chosen = next((r for r in rows if r["method"] == method), None)
        rivals = [r for r in rows if r["eligible"] and r["method"] != method]
        if chosen is not None:
            demote.append((len(rivals), refutations_to_demote(chosen, rivals)))
    alternatives = max((n for n, _ in demote), default=0)
    k = min((k for _, k in demote if k is not None), default=None)
    return _measured({"eligible_alternatives": alternatives, "selection_can_change": alternatives > 0,
                      "refutations_to_demote": k, "update_rule": spec.update_rule},
                     "re-ranking by settled-outcome Laplace quality over this run's eligible candidates; "
                     "founder detach re-routing is measured by the integration tests named under persistence")


def _error_correction(family, cases_by_id, receipts):
    trials = [t for receipt in receipts for t in perturbation_trials(
        family, cases_by_id[receipt["_case"]]["request"]["data"], receipt)]
    if not trials:
        return _not_measured("no structurally verified answer for this method in the frozen suite",
                             "one frozen case whose receipt carries an output and a STRUCTURALLY_VERIFIED verdict")
    detected = [t for t in trials if t["outcome"] != "accepted"]
    return _measured({"perturbations": len(trials), "detected": len(detected),
                      "detection_rate": len(detected) / len(trials),
                      "refuted": sum(t["outcome"] == "refuted" for t in trials),
                      "raised": sum(t["outcome"].startswith("raised") for t in trials),
                      "undetected_fields": sorted({t["field"] for t in trials if t["outcome"] == "accepted"})},
                     "every single-leaf corruption (number or numeric string +1e6, boolean flip, string suffix) "
                     "of each verified answer re-run through the independent falsifier "
                     "(greg/cognition/verification.py); a typed-artifact-only check detects nothing")


def _problem_space(method, cases, spec):
    return _measured({"operations": list(spec.operations), "epistemic_classes": list(spec.epistemic_classes),
                      "layer": spec.layer, "compute_ceiling": spec.compute_ceiling,
                      "request_ceiling_bytes": REQUEST_CEILING_BYTES, "frozen_cases": len(cases)},
                     "ceilings enforced by compile_problem and CognitiveCapabilityProfile.validate; "
                     "cases routed to the method in this suite")


def _cooperation(method, receipts, anchors):
    answered = [r for r in receipts if r["abstention_state"] == "NONE"]
    partner = next((a for a in anchors if a["method"] != method and a["abstention_state"] == "NONE"), None)
    if not answered or partner is None:
        return _not_measured("no answered receipt pair to compose in this run",
                             "two answered receipts of different methods under one metaconsensus")
    consensus = metaconsensus([answered[0], partner])
    return _measured({"composed_with": partner["method"], "metaconsensus_state": consensus["state"],
                      "jurisdiction_preserved": answered[0]["receipt_id"] in
                      consensus["jurisdictions"].get(answered[0]["epistemic_class"], []),
                      "cross_class_dominance_inferred": False,
                      "lift_vs_best_constituent": None},
                     "metaconsensus over this method's receipt and one other method's receipt",
                     unmeasured="lift over the best constituent requires a predeclared acceptance criterion "
                                "(cognition.compose reports superiority as unproven)")


def _generalization_family():
    return _not_measured("the frozen cross-geometry comparison v0.3 measured the cortex router arm, "
                         "not this family worker",
                         "a frozen held-out partition over this operation family (v0.4; founder-gated because "
                         "it changes the comparison)")


def _higher_scale_coherence(spec):
    consumers = {op: HIGHER_SCALE_CONSUMERS[op] for op in spec.operations if op in HIGHER_SCALE_CONSUMERS}
    if not consumers:
        return _not_measured(f"no higher-scale GREG capability consumes {list(spec.operations)} yet",
                             "a delivery capability whose verify_delivery depends on this method's receipt")
    names = sorted({c for cs in consumers.values() for c in cs})
    return _measured({"consumers": names, "operations_consumed": sorted(consumers),
                      "coherence_rules": {n: HIGHER_SCALE_RULES[n] for n in names}},
                     "delivery capabilities that request this operation through cognition.solve and whose "
                     "appraisal refutes a delivery whose conclusion outruns the receipt")


def characterize_family(method, *, rows, receipts, cases, anchors, journal_supplied):
    family = method.removeprefix("cognition.")
    spec = profile(family)
    cases_by_id = {case["id"]: case for case in cases}
    mine = [r for r in receipts if r["method"] == method]
    my_cases = [cases_by_id[r["_case"]] for r in mine]
    return {"responsiveness": _responsiveness(method, rows, spec),
            "memory_depth": _memory_depth(method, receipts, journal_supplied),
            "prediction_horizon": _prediction_horizon(method, my_cases, spec),
            "adaptability": _adaptability(method, mine, spec),
            "persistence": _not_applicable(f"the method is a stateless bounded worker ({spec.state}); persistence "
                                           "is a property of the body", measured_at_body_scale_by=list(PERSISTENCE_EVIDENCE)),
            "error_correction": _error_correction(family, cases_by_id, mine),
            "problem_space": _problem_space(method, my_cases, spec),
            "cooperation": _cooperation(method, mine, anchors),
            "generalization": _generalization_family(),
            "higher_scale_coherence": _higher_scale_coherence(spec)}


def cortex_evidence(root=CROSSGEO):
    """Frozen v0.3 comparison: the routed cortex arm on the selection and held-out partitions."""
    try:
        heldout = json.loads((Path(root) / "results.json").read_text())
        selection = json.loads((Path(root) / "selection-results.json").read_text())
    except (OSError, ValueError):
        return None
    arm_h, arm_s = heldout["heldout"]["arms"]["routed_greg"], selection["arms"]["routed_greg"]
    strata = {}
    for name, held in arm_h["summary"]["by_stratum"].items():
        sel = arm_s["summary"]["by_stratum"].get(name, {})
        strata[name] = {"heldout_mean_loss": held["mean_loss"], "heldout_n": held["n"],
                        "selection_mean_loss": sel.get("mean_loss"), "selection_n": sel.get("n"),
                        "gap_heldout_minus_selection": None if sel.get("mean_loss") is None else held["mean_loss"] - sel["mean_loss"]}
    rows = heldout["heldout"]["rows"]["routed_greg"]
    return {"frozen_at": heldout.get("frozen_at"), "cortex_version": heldout.get("cortex_version"),
            "verdict": heldout["verdict"]["verdict"], "not_run": heldout["verdict"]["not_run"],
            "by_stratum": strata, "heldout_mean_loss": arm_h["summary"]["mean_loss"],
            "heldout_mean_loss_ci95": arm_h["summary"]["mean_loss_ci95"],
            "hard_failures": arm_h["summary"]["hard_failures"],
            "regret_vs_hindsight_best_arm": heldout["heldout"]["regret"]["mean_regret_vs_hindsight_best_arm"],
            "latencies": [r["latency_s"] for r in rows if isinstance(r.get("latency_s"), (int, float))]}


def characterize_cortex(evidence):
    absent = _not_measured("this frozen suite does not route to the cortex",
                           "tests/unit/test_greg_cortex_bridge.py and a cortex-problem suite")
    if evidence is None:
        return {**{d: absent for d in DIMENSIONS},
                "generalization": _not_measured(f"frozen comparison files absent under {CROSSGEO}", "the v0.3 evidence files")}
    latencies = evidence.pop("latencies")
    out = {d: absent for d in DIMENSIONS}
    out["responsiveness"] = _measured({"p50_seconds": quantile(latencies, .5), "p95_seconds": quantile(latencies, .95),
                                       "max_seconds": max(latencies), "n": len(latencies)},
                                      "frozen v0.3 held-out rows of the routed cortex arm (latency_s per item)")
    out["error_correction"] = _measured({"hard_failures": evidence["hard_failures"], "items": len(latencies)},
                                        "hard failures (confident wrong answers) counted by the frozen v0.3 loss over "
                                        "held-out items; perturbation trials are not run against frozen rows")
    out["generalization"] = _measured(evidence, "frozen v0.3 comparison: the same routed arm on the selection "
                                      "partition and on fresh held-out samples; gap > 0 means worse on held-out",
                                      claim_limit=f"no superiority over baselines that did not run: {evidence['not_run']}")
    return out


def characterize(*, rows, receipts, cases, journal_supplied=False, evidence_root=CROSSGEO):
    methods = sorted({r["method"] for r in rows if r["method"].startswith("cognition.") and
                      r["method"].removeprefix("cognition.") in FAMILIES})
    anchors = [r for r in receipts if r["method"] in methods]
    report = {m: characterize_family(m, rows=rows, receipts=receipts, cases=cases, anchors=anchors,
                                     journal_supplied=journal_supplied) for m in methods}
    report[CORTEX_METHOD] = characterize_cortex(cortex_evidence(evidence_root))
    counts = {s: sum(d["status"] == s for dims in report.values() for d in dims.values()) for s in STATUSES}
    return {"dimensions": list(DIMENSIONS), "methods": report, "summary": {"methods": len(report), **counts},
            "rule": "a number from a native workload, or why the dimension does not apply, or what would measure it"}


# --- assessment -------------------------------------------------------------------------------

def assess(*, suite=SUITE, baselines=None, journal=None, evidence_root=CROSSGEO):
    raw = json.loads(Path(suite).read_text())
    registry, rows, receipts = registry_view(journal), [], []
    baseline_rows = {name: [] for name in (baselines or {})}
    for case in raw["cases"]:
        receipt = reason(case["request"], registry=registry, journal=journal)
        receipts.append({**receipt, "_case": case["id"]})
        rows.append({"id": case["id"], "correct": score(receipt, case), "method": receipt["method"],
                     "state": receipt["abstention_state"], "latency": receipt["latency"], "cost_usd": receipt["money_cost"]})
        for name, baseline in (baselines or {}).items():
            started = time.monotonic()
            try:
                answer = baseline(case["request"])
                good = score(answer, case, require_method=False)
            except Exception as exc:
                good, answer = False, {"error": type(exc).__name__}
            baseline_rows[name].append({"id": case["id"], "correct": good, "latency": time.monotonic() - started,
                                        "cost_usd": answer.get("money_cost"), "authorship": answer.get("method")})
    measured = (set(raw["baseline_required_for_superiority"]) <= set(baseline_rows) and
                all(all(r["cost_usd"] is not None for r in b) for b in baseline_rows.values()))
    return {"suite_digest": digest(raw), "cases": rows, "correct": sum(r["correct"] for r in rows), "total": len(rows),
            "baselines": baseline_rows, "superiority_status": "COMPARISON_REQUIRES_PREDECLARED_ACCEPTANCE" if measured else "UNMEASURED",
            "cross_geometry_regret": None,
            "characterization": characterize(rows=rows, receipts=receipts, cases=raw["cases"],
                                             journal_supplied=journal is not None, evidence_root=evidence_root),
            "limits": "Structured inputs; local deterministic/math proof. No live LLM comparison, arbitrary-language classification, external outcome or VEPMC increment."}


if __name__ == "__main__":
    report = assess()
    print(json.dumps(report, indent=2, allow_nan=False))
    raise SystemExit(0 if report["correct"] == report["total"] else 1)
