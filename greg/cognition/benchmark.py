"""Frozen cross-geometry assessment. Missing LLM baselines never imply superiority.

Suite v2 (``frozen-suite-v2.json``) supersedes v1 operationally and keeps v1 on disk: v1 passed 22/22 at
3ced61d and 11/22 after the 4baf534 convergence, because (a) cataloguing never attaches the P5+ families
on a body and (b) an unimplemented operation now abstains as UNKNOWN_GEOMETRY before eligibility. The
assessment measures the catalogued repertoire, so it attaches every catalogued family in an
evaluation-only registry view (``EVALUATION_ATTACH``); a body's attach state is untouched.
"""
from __future__ import annotations

import json
from pathlib import Path
import time

from .contracts import digest
from .cortex import reason, registry_view


SUITE = Path(__file__).resolve().parents[2] / "examples" / "cognition" / "frozen-suite-v2.json"
SUITE_V1 = SUITE.with_name("frozen-suite.json")


def assessment_registry():
    """Evaluation-only view: every catalogued cognition family attached; nothing persists or reaches a body."""
    from .catalog import FAMILIES
    registry = registry_view()
    attached = []
    for family in FAMILIES:
        cid = "cognition." + family
        if cid in registry.manifests and registry.state[cid] != "ATTACHED":
            registry.set_state(cid, "ATTACHED")
            attached.append(cid)
    return registry, sorted(attached)


def score(receipt, case, *, require_method=True):
    expected = case["expected"]
    if (require_method and receipt.get("method") != expected["method"]) or receipt.get("abstention_state") != expected.get("state", "NONE"):
        return False
    output = receipt.get("output") or {}
    return all(output.get(k) == v for k, v in expected.get("output", {}).items())


def assess(*, suite=SUITE, baselines=None):
    raw = json.loads(Path(suite).read_text())
    registry, evaluation_attach = assessment_registry()
    rows = []
    baseline_rows = {name: [] for name in (baselines or {})}
    for case in raw["cases"]:
        receipt = reason(case["request"], registry=registry)
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
    return {"suite_digest": digest(raw), "suite": Path(suite).name, "evaluation_attach": evaluation_attach,
            "cases": rows, "correct": sum(r["correct"] for r in rows), "total": len(rows),
            "baselines": baseline_rows, "superiority_status": "COMPARISON_REQUIRES_PREDECLARED_ACCEPTANCE" if measured else "UNMEASURED",
            "cross_geometry_regret": None, "characterization": {"responsiveness": "per-case measured latency",
                "memory_depth": "canonical receipt/mission history; restart integration tested separately",
                "prediction_horizon": "declared finite horizons only", "adaptability": "outcome-ranked eligible capabilities",
                "persistence": "existing GREG body, separate integration evidence", "error_correction": "independent artifact falsification",
                "problem_space": "bounded structured operations", "cooperation": "typed composition; measured lift unproven",
                "generalization": "unproven beyond this frozen corpus", "higher_scale_coherence": "unmeasured"},
            "limits": "Structured inputs; local deterministic/math proof. No live LLM comparison, arbitrary-language classification, external outcome or VEPMC increment."}


if __name__ == "__main__":
    report = assess()
    print(json.dumps(report, indent=2, allow_nan=False))
    raise SystemExit(0 if report["correct"] == report["total"] else 1)
