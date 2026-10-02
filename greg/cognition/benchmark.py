"""Frozen cross-geometry assessment. Missing LLM baselines never imply superiority."""
from __future__ import annotations

import json
from pathlib import Path
import time

from .contracts import digest
from .cortex import reason, registry_view


SUITE = Path(__file__).resolve().parents[2] / "examples" / "cognition" / "frozen-suite.json"


def score(receipt, case, *, require_method=True):
    expected = case["expected"]
    if (require_method and receipt.get("method") != expected["method"]) or receipt.get("abstention_state") != expected.get("state", "NONE"):
        return False
    output = receipt.get("output") or {}
    return all(output.get(k) == v for k, v in expected.get("output", {}).items())


def assess(*, suite=SUITE, baselines=None, include_receipts=False):
    raw = json.loads(Path(suite).read_text())
    registry, rows = registry_view(), []
    baseline_rows = {name: [] for name in (baselines or {})}
    for case in raw["cases"]:
        receipt = reason(case["request"], registry=registry)
        rows.append({"id": case["id"], "correct": score(receipt, case), "method": receipt["method"],
                     "state": receipt["abstention_state"], "latency": receipt["latency"], "cost_usd": receipt["money_cost"]})
        if include_receipts:
            rows[-1].update(original_expected=case["expected"], receipt=receipt,
                            request_digest=digest(case["request"]))
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
            "cross_geometry_regret": None, "characterization": {"responsiveness": "per-case measured latency",
                "memory_depth": "canonical receipt/mission history; restart integration tested separately",
                "prediction_horizon": "declared finite horizons only", "adaptability": "outcome-ranked eligible capabilities",
                "persistence": "existing GREG body, separate integration evidence", "error_correction": "independent artifact falsification",
                "problem_space": "bounded structured operations", "cooperation": "typed composition; measured lift unproven",
                "generalization": "unproven beyond this frozen corpus", "higher_scale_coherence": "unmeasured"},
            "limits": "Structured inputs; local deterministic/math proof. No live LLM comparison, arbitrary-language classification, external outcome or VEPMC increment."}



def compatibility(*, suite=SUITE):
    """Check current default gates without rewriting the original benchmark.

    Gate contracts are fixed before candidate invocation. A disabled method's
    truthful deficit is compatible with the current development boundary,
    while its original unfulfilled capability expectation remains visible.
    Native qualification and held-out performance are separate tests.
    """
    import importlib.metadata
    from .catalog import FAMILIES, SEED_FAMILIES
    from .settlement import _valid_receipt

    raw = json.loads(Path(suite).read_text())
    try:
        importlib.metadata.version("sympy")
        symbolic_installed = True
    except importlib.metadata.PackageNotFoundError:
        symbolic_installed = False
    gate_contracts = {}
    for case in raw["cases"]:
        original = case["expected"]
        operation = case["request"]["operation"]
        supported = [family for family, fields in FAMILIES.items() if operation in fields[1]]
        contract = {"kind": "ACTIVE_OR_EXISTING_ABSTENTION", "expected": original,
                    "require_no_output": False, "required_reason": None}
        if not supported:
            contract = {"kind": "UNKNOWN_GEOMETRY", "expected": {"method": "none", "state": "ABSTAIN"},
                        "require_no_output": True, "required_reason": "UNKNOWN_GEOMETRY"}
        elif original.get("state", "NONE") == "NONE" and all(family not in SEED_FAMILIES for family in supported):
            contract = {"kind": "DEFAULT_UNATTACHED", "expected": {"method": "none", "state": "CAPABILITY_DEFICIT"},
                        "require_no_output": True, "required_reason": "CAPABILITY_UNAVAILABLE"}
        elif operation == "polynomial" and not symbolic_installed:
            contract = {"kind": "OPTIONAL_DEPENDENCY_UNAVAILABLE", "expected": {"method": "none", "state": "CAPABILITY_DEFICIT"},
                        "require_no_output": True, "required_reason": "CAPABILITY_UNAVAILABLE"}
        gate_contracts[case["id"]] = contract
    report = assess(suite=suite, include_receipts=True)
    for row in report["cases"]:
        contract, receipt = gate_contracts[row["id"]], row["receipt"]
        good = (_valid_receipt(receipt) and score(receipt, {"expected": contract["expected"]})
                and receipt.get("authority_created") is False)
        if contract["require_no_output"]:
            good = (good and receipt["output"] is None and not receipt["proof_artifact"]
                    and receipt["evaluator_result"]["verdict"] == "NOT_RUN"
                    and receipt["reason_code"] == contract["required_reason"])
        row.update(default_gate_contract=contract, compatibility_correct=bool(good))
    report.update(scope="DEFAULT_CATALOG_COMPATIBILITY", golden_cases_unchanged=True,
                  compatibility_correct=sum(row["compatibility_correct"] for row in report["cases"]),
                  authority_created=False, superiority_status="UNMEASURED",
                  compatibility_contract_digest=digest(gate_contracts),
                  limits=report["limits"] + " Original capability expectations and failures remain unchanged. Separate gate checks verify truthful default unavailability and epistemic abstention; no capability is attached and no completed machine is inferred.")
    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-compatibility", action="store_true",
                        help="Assess default attachment/abstention compatibility; preserve original legacy results")
    arguments = parser.parse_args()
    report = compatibility() if arguments.catalog_compatibility else assess()
    print(json.dumps(report, indent=2, allow_nan=False))
    gate = report.get("compatibility_correct", report["correct"])
    raise SystemExit(0 if gate == report["total"] else 1)
