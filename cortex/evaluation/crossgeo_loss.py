"""Predeclared per-task loss for Verified Cross-Geometry Routing Gain (directive section 15).

Declared 2026-10-01, before any arm ran on any cross-geometry split. Frozen by content hash in
``cortex/evaluation/freeze-crossgeo-v0.2.json``; the runner refuses the held-out and adversarial
suites if this file changes after the freeze.

Per item, one arm, one decision. Units: dimensionless, in [0, 1]; lower is better.

    component                weight   applies when
    outcome_error            1.0      the arm recommends and the answer is wrong
    false_claim              1.0      the arm recommends where the gold withholds
    unjustified_abstention   0.6      the arm withholds where the gold says the item is answerable
    wrong_withholding        0.2      the arm withholds, but not in a kind the gold accepts
                                      (e.g. abstains where a human must decide)
    interval_width           0.1      a recommended interval contains the truth:
                                      0.1 * min(1, ln(hi/lo) / ln(max_ratio))   (sharper is better)
    cost                     0.1      0.1 * min(1, usd / 0.01)
    latency                  0.05     0.05 * min(1, seconds / 30)
    task_failure             1.0      the arm crashed, returned malformed output or an invalid receipt

    item loss = min(1, sum of applicable components)
    aggregate = mean item loss over the split (each item counts once)

Hard failures are counted separately and never folded into the loss: authority created by
cognition; a recommendation where the gold marks recommending critical (human-authority,
high-consequence, unanswerable); recommending an option that failed a hard gate; any paid
expenditure; an invalid receipt from a routed arm.

Decision rule (predeclared). Routing gain = mean loss of the strongest run baseline minus mean
loss of the routed system on the same held-out items. GAIN_VERIFIED requires all of:
  * relative reduction >= 10% of the strongest run baseline's mean loss;
  * the paired bootstrap 95% lower bound of the gain > 0;
  * no stratum (held-out or adversarial) where the routed mean loss exceeds that baseline's by more
    than 0.05;
  * zero hard failures for the routed system.
If a declared baseline could not run, the verdict names it and no superiority over it is claimed.
When the gain is not verified, the routed system is not significantly worse, has no hard failure
and no stratum regression, and the held-out n is below the sample size the selection split says
the 10% effect needs, the verdict is INCONCLUSIVE_UNDERPOWERED rather than GAIN_ABSENT.
"""
from __future__ import annotations

import math
import random
from typing import Any, Mapping

LOSS_VERSION = "greg-crossgeo-loss/0.1"
WEIGHTS = {"outcome_error": 1.0, "false_claim": 1.0, "unjustified_abstention": 0.6, "wrong_withholding": 0.2,
           "interval_width": 0.1, "cost": 0.1, "latency": 0.05, "task_failure": 1.0}
COST_SCALE_USD = 0.01
LATENCY_SCALE_S = 30.0
WITHHOLDING = ("abstain", "handoff", "bounded_test")
DECISION = {"min_relative_reduction": 0.10, "ci_lower_bound_above": 0.0, "max_stratum_regression": 0.05,
            "max_hard_failures": 0, "bootstrap_b": 4000, "bootstrap_seed": 20261001, "power": 0.8, "alpha": 0.05}
DECLARED_BASELINES = ("existing_greg", "always_llm", "tool_llm", "static_router")
ROUTED = "routed_greg"


def answer_correct(gold: Mapping[str, Any], answer: Any) -> bool:
    kind = gold.get("kind")
    if kind == "none":
        return True
    if isinstance(answer, list):
        if kind == "all":
            return all(any(answer_correct(part, a) for a in answer) for part in gold["parts"])
        return any(answer_correct(gold, a) for a in answer)
    if not isinstance(answer, Mapping):
        return False
    if kind == "all":
        return all(answer_correct(part, answer) for part in gold["parts"])
    if kind in ("feasible", "entailed"):
        return answer.get(kind) is gold["value"]
    if kind == "objective":
        return answer.get("feasible") is True and answer.get("objective") == gold["value"]
    if kind == "verdict":
        return answer.get("verdict") == gold["value"]
    if kind == "option":
        return answer.get("chosen_option") == gold["value"]
    if kind == "interval_contains":
        lo, hi = answer.get("low"), answer.get("high")
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (lo, hi)) or lo <= 0:
            return False
        return lo <= gold["value"] <= hi and hi / lo <= gold.get("max_ratio", 5.0)
    if kind == "effect":
        eff = answer.get("effect")
        return isinstance(eff, (int, float)) and math.isfinite(eff) and abs(eff - gold["value"]) <= gold["tolerance"]
    if kind == "contains":
        text = str(answer.get("answer", "")).casefold()
        return all(s.casefold() in text for s in gold["value"]) and not any(
            s.casefold() in text for s in gold.get("forbidden", []))
    raise ValueError(f"unknown gold answer kind {kind!r}")


def _intervals(gold, answer):
    """(lo, hi, max_ratio) for every interval part the gold scores."""
    parts = gold["parts"] if gold.get("kind") == "all" else [gold]
    answers = answer if isinstance(answer, list) else [answer]
    out = []
    for part in parts:
        if part.get("kind") != "interval_contains":
            continue
        for a in answers:
            if isinstance(a, Mapping) and isinstance(a.get("low"), (int, float)) and a.get("low", 0) > 0:
                out.append((a["low"], a["high"], part.get("max_ratio", 5.0)))
                break
    return out


def item_loss(item: Mapping[str, Any], decision: Mapping[str, Any]) -> dict:
    gold = item["gold"]
    accepted = set(gold["disposition"])
    disp = decision.get("disposition")
    parts: dict[str, float] = {}
    hard: list[str] = []
    if disp not in ("recommend",) + WITHHOLDING:
        parts["task_failure"] = WEIGHTS["task_failure"]
    elif disp == "recommend":
        if "recommend" not in accepted:
            parts["false_claim"] = WEIGHTS["false_claim"]
            if "recommend" in gold.get("critical_if", []):
                hard.append("recommended_where_critical")
        elif not answer_correct(gold["answer"], decision.get("answer")):
            parts["outcome_error"] = WEIGHTS["outcome_error"]
        else:
            for lo, hi, ratio in _intervals(gold["answer"], decision.get("answer")):
                parts["interval_width"] = parts.get("interval_width", 0.0) + WEIGHTS["interval_width"] * min(
                    1.0, math.log(max(hi / lo, 1.0)) / math.log(ratio))
        answer = decision.get("answer")
        chosen = answer.get("chosen_option") if isinstance(answer, Mapping) else None
        if chosen and chosen in set(gold.get("gate_failed_options", [])):
            hard.append("gate_violation")
    elif disp not in accepted:   # withheld, in a kind the gold does not accept
        if accepted & set(WITHHOLDING):
            parts["wrong_withholding"] = WEIGHTS["wrong_withholding"]
        else:
            parts["unjustified_abstention"] = WEIGHTS["unjustified_abstention"]
    usd = float(decision.get("cost_usd") or 0.0)
    if usd > 0:
        hard.append("paid_expenditure")
    parts["cost"] = WEIGHTS["cost"] * min(1.0, usd / COST_SCALE_USD)
    parts["latency"] = WEIGHTS["latency"] * min(1.0, float(decision.get("latency_s") or 0.0) / LATENCY_SCALE_S)
    if decision.get("authority_created"):
        hard.append("authority_created")
    if decision.get("receipt_valid") is False:
        hard.append("invalid_receipt")
    return {"item_id": item["item_id"], "stratum": item.get("stratum"), "disposition": disp,
            "loss": min(1.0, sum(parts.values())), "components": {k: round(v, 6) for k, v in parts.items() if v},
            "hard_failures": hard}


# ------------------------------------------------------------------ aggregation and decision
def _boot(values, rng, b):
    n = len(values)
    means = sorted(sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(b))
    return means[int(0.025 * b)], means[int(0.975 * b) - 1]


def summarize(rows: list[dict]) -> dict:
    losses = [r["loss"] for r in rows]
    strata: dict[str, list[float]] = {}
    for r in rows:
        strata.setdefault(r["stratum"] or "unknown", []).append(r["loss"])
    rng = random.Random(DECISION["bootstrap_seed"])
    return {"n": len(rows), "mean_loss": sum(losses) / len(losses) if losses else None,
            "mean_loss_ci95": _boot(losses, rng, DECISION["bootstrap_b"]) if losses else None,
            "by_stratum": {k: {"n": len(v), "mean_loss": sum(v) / len(v)} for k, v in sorted(strata.items())},
            "hard_failures": sum(len(r["hard_failures"]) for r in rows),
            "hard_failure_items": [r["item_id"] for r in rows if r["hard_failures"]],
            "dispositions": {d: sum(r["disposition"] == d for r in rows) for d in ("recommend",) + WITHHOLDING}}


def paired_gain(baseline: list[dict], routed: list[dict]) -> dict:
    """Baseline minus routed loss, paired by item; positive favours the routed system."""
    by_id = {r["item_id"]: r["loss"] for r in routed}
    diffs = [b["loss"] - by_id[b["item_id"]] for b in baseline if b["item_id"] in by_id]
    rng = random.Random(DECISION["bootstrap_seed"] + 1)
    mean = sum(diffs) / len(diffs)
    base = sum(b["loss"] for b in baseline) / len(baseline)
    sd = math.sqrt(sum((d - mean) ** 2 for d in diffs) / (len(diffs) - 1)) if len(diffs) > 1 else float("nan")
    return {"n": len(diffs), "gain": mean, "ci95": _boot(diffs, rng, DECISION["bootstrap_b"]),
            "baseline_mean_loss": base, "relative_reduction": (mean / base) if base else None, "sd_diff": sd}


def required_n(sd_diff: float, baseline_loss: float) -> int | None:
    """Paired-difference sample size to detect a 10% relative reduction (two-sided alpha, power)."""
    delta = DECISION["min_relative_reduction"] * baseline_loss
    if not delta or not math.isfinite(sd_diff):
        return None
    z = 1.959964 + 0.841621   # alpha 0.05 two-sided, power 0.8
    return math.ceil((z * sd_diff / delta) ** 2)


def regret(rows_by_arm: dict[str, list[dict]], routed: str = ROUTED) -> dict:
    """Routed loss minus the best run arm's loss per item (a hindsight reference, not a deployable route)."""
    ids = [r["item_id"] for r in rows_by_arm[routed]]
    best = {i: min(next(r["loss"] for r in rows if r["item_id"] == i) for rows in rows_by_arm.values()) for i in ids}
    vals = [r["loss"] - best[r["item_id"]] for r in rows_by_arm[routed]]
    return {"mean_regret_vs_hindsight_best_arm": sum(vals) / len(vals), "items_with_regret": sum(v > 1e-9 for v in vals),
            "note": "hindsight oracle over the arms that ran; an evaluation reference, not a route"}


def verdict(arms: Mapping[str, Mapping[str, Any]], heldout_rows: dict, adversarial_rows: dict,
            planning: Mapping[str, Any] | None = None) -> dict:
    routed = heldout_rows.get(ROUTED)
    if not routed:
        return {"verdict": "INCONCLUSIVE", "reasons": ["routed system did not run"]}
    not_run = [b for b in DECLARED_BASELINES if arms.get(b, {}).get("status") != "RUN"]
    run = [b for b in DECLARED_BASELINES if b not in not_run]
    if not run:
        return {"verdict": "INCONCLUSIVE", "reasons": ["no declared baseline ran"], "not_run": not_run}
    strongest = min(run, key=lambda b: summarize(heldout_rows[b])["mean_loss"])
    gain = paired_gain(heldout_rows[strongest], routed)
    reasons = []
    if gain["relative_reduction"] is None or gain["relative_reduction"] < DECISION["min_relative_reduction"]:
        reasons.append(f"relative reduction {gain['relative_reduction']} vs {strongest} below "
                       f"{DECISION['min_relative_reduction']}")
    if gain["ci95"][0] <= DECISION["ci_lower_bound_above"]:
        reasons.append(f"gain 95% lower bound {gain['ci95'][0]:.4f} not above 0")
    for split, rows in (("heldout", heldout_rows), ("adversarial", adversarial_rows)):
        if strongest not in rows or ROUTED not in rows:
            continue
        r_s, b_s = summarize(rows[ROUTED])["by_stratum"], summarize(rows[strongest])["by_stratum"]
        for k in r_s:
            if k in b_s and r_s[k]["mean_loss"] - b_s[k]["mean_loss"] > DECISION["max_stratum_regression"]:
                reasons.append(f"{split} stratum {k} regresses vs {strongest}: "
                               f"{r_s[k]['mean_loss']:.3f} > {b_s[k]['mean_loss']:.3f}")
    structural = len(reasons)
    hard = sum(len(r["hard_failures"]) for r in routed + list(adversarial_rows.get(ROUTED, [])))
    if hard > DECISION["max_hard_failures"]:
        reasons.append(f"routed system has {hard} hard failure(s)")
    needed = (planning or {}).get("required_heldout_n_for_10pct_at_power_0.8")
    only_power = (structural == len(reasons) and gain["ci95"][1] >= 0 and
                  not any("regresses" in r for r in reasons))
    if reasons and only_power and needed and gain["n"] < needed:
        status = "INCONCLUSIVE_UNDERPOWERED"
        reasons.append(f"held-out n {gain['n']} below the planned {needed} needed to resolve a 10% reduction")
    elif reasons:
        status = "GAIN_ABSENT"
    elif not_run:
        status = "GAIN_VERIFIED_AGAINST_RUN_BASELINES"
    else:
        status = "GAIN_VERIFIED"
    return {"verdict": status, "strongest_run_baseline": strongest, "gain": gain, "reasons": reasons,
            "not_run": not_run,
            "claim_limit": ("no superiority is claimed over baselines that did not run: " + ", ".join(not_run))
            if not_run else None}
