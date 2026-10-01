"""Pre-registered scoring for the seed experiment (build prompt item 9).

Frozen by content hash in ``cortex/evaluation/freeze-v<cortex version>.json``
before each reported run; earlier manifests and their results are kept.
Changing any rule here changes the hash and the runner refuses to report
against the old freeze.

Per item, per arm:

* disposition acceptable and, when an answer is recommended, the answer correct -> 1.0
* correct abstention / handoff / bounded test (gold expects it)                   -> 1.0
* over-cautious: arm withholds an answer the gold says was answerable             -> 0.25
* wrong answer, or recommending where gold expects withholding                    -> 0.0
* arm error on the item                                                           -> 0.0

Separately counted, never folded into the score: critical errors, unsupported
certainty (recommending where the gold withholds), gate violations, interval
calibration, cost, latency, model and solver calls.
"""
from __future__ import annotations

import math
import random
from typing import Any, Mapping

SCORING_VERSION = "cortex-scoring/0.1"
OVERCAUTIOUS_CREDIT = 0.25
WITHHOLDING = ("abstain", "handoff", "bounded_test")
BOOTSTRAP_B = 2000
BOOTSTRAP_SEED = 20260930
THRESHOLDS = {
    # routed seed must beat EACH declared baseline by this much at the lower 95% bound
    "min_quality_gain_lower_bound": 0.05,
    "max_critical_error_increase": 0,
    "max_gate_violations": 0,
    "declared_baselines": ["always_llm", "llm_committee"],
}


def answer_correct(gold: Mapping[str, Any], answer: Any) -> bool:
    kind = gold.get("kind")
    if kind == "none":
        return True
    if not isinstance(answer, Mapping):
        if isinstance(answer, list):  # composition: every gold part must be matched by some answer
            return all(any(answer_correct(part, a) for a in answer if isinstance(a, Mapping))
                       for part in gold.get("parts", [gold]))
        return False
    if kind == "all":
        return all(answer_correct(part, answer) for part in gold["parts"])
    if kind in ("feasible", "entailed"):
        return answer.get(kind) is gold["value"]
    if kind == "verdict":
        return answer.get("verdict") == gold["value"]
    if kind == "option":
        return answer.get("chosen_option") == gold["value"]
    if kind == "interval_contains":
        lo, hi = answer.get("low"), answer.get("high")
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (lo, hi)) or lo <= 0:
            return False
        return lo <= gold["value"] <= hi and hi / lo <= gold.get("max_ratio", 4.0)
    if kind == "effect":
        eff = answer.get("effect")
        return isinstance(eff, (int, float)) and abs(eff - gold["value"]) <= gold["tolerance"]
    if kind == "contains":
        text = str(answer.get("answer", "")).casefold()
        return all(s.casefold() in text for s in gold["value"]) and not any(
            s.casefold() in text for s in gold.get("forbidden", []))
    raise ValueError(f"unknown gold answer kind {kind!r}")


def score_item(item: Mapping[str, Any], decision: Mapping[str, Any]) -> dict:
    gold = item["gold"]
    accepted = set(gold["disposition"])
    disp = decision.get("disposition")
    critical_if = set(gold.get("critical_if", []))
    out = {"item_id": item["item_id"], "disposition": disp, "score": 0.0, "critical": False,
           "unsupported_certainty": False, "gate_violation": False, "correct_abstention": False,
           "overcautious": False, "error": disp == "error"}
    if disp == "error":
        return out
    answer = decision.get("answer")
    if disp in accepted:
        if disp == "recommend" and gold["answer"]["kind"] != "none":
            ok = answer_correct(gold["answer"], answer)
            out["score"] = 1.0 if ok else 0.0
            out["critical"] = (not ok) and "wrong_answer" in critical_if
        else:
            out["score"] = 1.0
            out["correct_abstention"] = disp in WITHHOLDING
    elif disp in WITHHOLDING and "recommend" in accepted:
        out["score"] = OVERCAUTIOUS_CREDIT
        out["overcautious"] = True
    else:
        out["score"] = 0.0
        if disp == "recommend":
            out["unsupported_certainty"] = True
            out["critical"] = "recommend" in critical_if
    chosen = answer.get("chosen_option") if isinstance(answer, Mapping) else None
    if disp == "recommend" and chosen and chosen in set(gold.get("gate_failed_options", [])):
        out["gate_violation"] = True
        out["critical"] = True
        out["score"] = 0.0
    return out


def _bootstrap_mean(values: list[float], rng: random.Random) -> tuple[float, float]:
    if not values:
        return (float("nan"), float("nan"))
    means = sorted(sum(values[rng.randrange(len(values))] for _ in values) / len(values)
                   for _ in range(BOOTSTRAP_B))
    return means[int(0.025 * BOOTSTRAP_B)], means[int(0.975 * BOOTSTRAP_B) - 1]


def summarize(items: list[Mapping[str, Any]], scored: list[dict], decisions: list[Mapping[str, Any]]) -> dict:
    rng = random.Random(BOOTSTRAP_SEED)
    scores = [s["score"] for s in scored]
    withheld = [s for s in scored if s["disposition"] in WITHHOLDING]
    should_withhold = [s for s, it in zip(scored, items) if "recommend" not in it["gold"]["disposition"]]
    coverage = []
    for it, d in zip(items, decisions):
        if it["gold"]["answer"]["kind"] == "interval_contains" and d.get("disposition") == "recommend":
            a = d.get("answer") or {}
            if isinstance(a, Mapping) and isinstance(a.get("low"), (int, float)):
                coverage.append(a["low"] <= it["gold"]["answer"]["value"] <= a["high"])
    latencies = sorted(float(d.get("latency_s", 0.0)) for d in decisions)
    by_family: dict[str, list[float]] = {}
    for it, s in zip(items, scored):
        for fam in it.get("families", []) or ["standard"]:
            by_family.setdefault(fam, []).append(s["score"])
    return {
        "n": len(scored),
        "mean_quality": sum(scores) / len(scores) if scores else float("nan"),
        "mean_quality_ci95": _bootstrap_mean(scores, rng),
        "critical_errors": sum(s["critical"] for s in scored),
        "unsupported_certainty": sum(s["unsupported_certainty"] for s in scored),
        "gate_violations": sum(s["gate_violation"] for s in scored),
        "errors": sum(s["error"] for s in scored),
        "abstention": {
            "withheld": len(withheld),
            "precision": (sum(s["correct_abstention"] for s in withheld) / len(withheld)) if withheld else None,
            "recall": (sum(s["correct_abstention"] for s in should_withhold) / len(should_withhold))
            if should_withhold else None,
            "overcautious": sum(s["overcautious"] for s in scored),
        },
        "calibration": {"interval_items": len(coverage),
                        "coverage": (sum(coverage) / len(coverage)) if coverage else None,
                        "nominal": 0.9},
        "cost_usd_total": round(sum(float(d.get("cost_usd", 0.0)) for d in decisions), 6),
        "latency_s_mean": (sum(latencies) / len(latencies)) if latencies else None,
        "latency_s_p95": latencies[int(0.95 * (len(latencies) - 1))] if latencies else None,
        "model_calls": sum(int(d.get("model_calls", 0)) for d in decisions),
        "solver_calls": sum(int(d.get("solver_calls", 0)) for d in decisions),
        "by_family": {k: {"n": len(v), "mean": sum(v) / len(v)} for k, v in sorted(by_family.items())},
    }


def paired_gain(a: list[dict], b: list[dict]) -> dict:
    """Routed minus baseline, paired by item, with a bootstrap 95% interval."""
    diffs = [x["score"] - y["score"] for x, y in zip(a, b)]
    rng = random.Random(BOOTSTRAP_SEED + 1)
    lo, hi = _bootstrap_mean(diffs, rng)
    return {"n": len(diffs), "mean": sum(diffs) / len(diffs) if diffs else float("nan"), "ci95": [lo, hi]}


def exit_verdict(arms: Mapping[str, Mapping[str, Any]]) -> dict:
    routed = arms.get("routed_seed")
    reasons = []
    if routed is None or routed.get("status") != "RUN":
        return {"verdict": "INCONCLUSIVE", "promote": False, "reasons": ["routed seed did not run"]}
    for name in THRESHOLDS["declared_baselines"]:
        arm = arms.get(name)
        if arm is None or arm.get("status") != "RUN":
            reasons.append(f"declared baseline {name} not run: {(arm or {}).get('reason', 'absent')}")
            continue
        gain = arm["paired_gain_vs_routed"]
        if gain["ci95"][0] <= THRESHOLDS["min_quality_gain_lower_bound"]:
            reasons.append(f"gain over {name} not established (lower bound {gain['ci95'][0]:.3f})")
        if routed["summary"]["critical_errors"] - arm["summary"]["critical_errors"] > THRESHOLDS["max_critical_error_increase"]:
            reasons.append(f"more critical errors than {name}")
    if routed["summary"]["gate_violations"] > THRESHOLDS["max_gate_violations"]:
        reasons.append("routed seed violated a gate")
    if not reasons:
        return {"verdict": "GAIN_VERIFIED", "promote": True, "reasons": []}
    inconclusive = any("not run" in r for r in reasons)
    return {"verdict": "INCONCLUSIVE" if inconclusive else "GAIN_ABSENT", "promote": False, "reasons": reasons}
