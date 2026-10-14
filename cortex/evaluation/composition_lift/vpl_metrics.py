"""VPL tracking metrics (directive 2026-10-07, section 16) computed from a frozen P6 results file.

A reader, never part of a verdict: it recomputes nothing a frozen rule decided and changes no evidence. For each
family with per-item arm results it reports, routed composition against the best constituent:

* ``cost_delta``           total realised cost difference (negative = composition cheaper), and relative;
* ``latency_delta_s``      median latency difference per item;
* ``false_answer_delta``   wrong (infeasible) answers, routed minus best constituent;
* ``abstention_delta``     no-decision items, routed minus best constituent;
* ``routing_regret``       mean and total of routed cost minus the cheapest arm on that item in hindsight
                           (regret 0 = routing always picked the best available arm, ablations included);
* ``calibration``          (staffing families only) the share of blocks staffed at or above the realised
                           requirement, per critical fractile q* = 1 - c/P, against q* itself. Staffing to the
                           q* quantile of a calibrated predictive distribution covers about q* of blocks; a
                           large gap means the forecaster's distribution is miscalibrated on these data.

Section 16 accounting (``accounting``), computed after the runs and labelled POST_HOC; no frozen verdict changes:

* ``latency``              routed and best-constituent median seconds, their ratio and the seconds added. No
                           netting rule was declared before these runs, so none is applied now: the count of
                           frozen lifts is reported at several latency multipliers (a sensitivity table), never
                           as one new verdict chosen after seeing the ratios;
* ``routed_vs_static``     routed composition against the static (development-chosen) recipe on the family's own
                           win criterion; a static arm that decides no item is reported as DEGENERATE, so routing's
                           measured contribution there is choosing the recipe that fits the inputs at all;
* ``practitioner``         routed composition against each declared practitioner pipeline in the run.

``validate_preregistration`` checks a future family's pre-registration for what these runs lacked: a
non-degenerate static arm, a compiled arm through the Competency Compiler, at least one practitioner pipeline and
a latency rule declared before the held-out partition is generated.

Usage: python -I cortex/evaluation/composition_lift/vpl_metrics.py <results.json> [<more results.json>]
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import statistics
import sys

# Practitioner pipelines present in the frozen runs (declared by each run's design, never chosen here).
PRACTITIONER_ARMS = {"F5": ("historical_mean", "point_forecast_then_optimize"),
                     "F6": ("weekly_mean_then_staff", "median_forecast_then_staff"),
                     "F7": ("shortest_path_upgrade", "parametric_min_cost_flow")}
LATENCY_MULTIPLIERS = (1.0, 1.5, 2.0, 5.0)
COST_FAMILIES = ("F5", "F6")
CORRECT = ("correct", "optimal")                 # F1-F4 say "correct"; F7 (exact optimum as truth) says "optimal"


def _rows(report: dict) -> list[dict]:
    return report.get("heldout") or report.get("rows") or []


def family_metrics(report: dict, family: str) -> dict | None:
    summary = report["summary"].get(family)
    rows = [r for r in _rows(report) if r.get("family") == family]
    if not summary or not rows or "best_constituent" not in summary:
        return None
    best, routed = summary["best_constituent"], "routed_composition"
    costs = [(r["arms"][routed].get("cost"), r["arms"][best].get("cost")) for r in rows]
    paired = [(a, b) for a, b in costs if a is not None and b is not None]
    out = {"items": len(rows), "best_constituent": best}
    if paired:
        total_r, total_b = sum(a for a, _ in paired), sum(b for _, b in paired)
        out["cost_delta"] = {"absolute": round(total_r - total_b, 6),
                             "relative": round((total_r - total_b) / total_b, 6) if total_b else None,
                             "paired_items": len(paired)}
        regrets = []
        for r in rows:
            arm_costs = [a.get("cost") for a in r["arms"].values() if a.get("cost") is not None]
            if r["arms"][routed].get("cost") is not None and arm_costs:
                regrets.append(r["arms"][routed]["cost"] - min(arm_costs))
        out["routing_regret"] = {"mean": round(statistics.fmean(regrets), 6) if regrets else None,
                                 "total": round(sum(regrets), 6), "items_with_zero_regret":
                                 sum(abs(x) <= 1e-9 for x in regrets), "items": len(regrets)}
    secs = [(r["arms"][routed]["seconds"], r["arms"][best]["seconds"]) for r in rows]
    out["latency_delta_s"] = round(statistics.median(a for a, _ in secs) - statistics.median(b for _, b in secs), 4)
    for key, outcome in (("false_answer_delta", "wrong"), ("abstention_delta", "no_decision")):
        out[key] = (sum(r["arms"][routed]["result"] == outcome for r in rows)
                    - sum(r["arms"][best]["result"] == outcome for r in rows))
    if all("required" in r.get("truth", {}) for r in rows):
        out["calibration"] = staffing_calibration(rows, routed, best)
    return out


def _fractile(item_id: str) -> float | None:
    """F6 rotates the shortage penalty P in {3, 10, 30} by day index (c = 1): q* = 1 - 1/P."""
    try:
        day = int(item_id.rsplit("-", 1)[1])
    except (IndexError, ValueError):
        return None
    return round(1 - 1 / (3.0, 10.0, 30.0)[day % 3], 6)


def staffing_calibration(rows: list[dict], *arms: str) -> dict:
    out = {}
    for arm in arms:
        by_q: dict[float, list[int]] = {}
        for r in rows:
            q = _fractile(r["item_id"])
            agents = (r["arms"][arm].get("answer") or {}).get("agents")
            if q is None or not isinstance(agents, list):
                continue
            covered = [int(n >= need) for n, need in zip(agents, r["truth"]["required"])]
            by_q.setdefault(q, []).extend(covered)
        out[arm] = {f"{q:g}": {"nominal": q, "covered": round(statistics.fmean(v), 4), "blocks": len(v),
                               "gap": round(statistics.fmean(v) - q, 4)} for q, v in sorted(by_q.items())}
    return out


def _sign_p(wins: int, losses: int) -> float:
    n = wins + losses
    return 1.0 if n == 0 else sum(math.comb(n, k) for k in range(wins, n + 1)) / 2 ** n


def _compare(rows: list[dict], family: str, a: str, b: str) -> dict:
    """a against b on the family's own frozen criterion: lower realised cost (F5, F6) or a correct answer where
    the other's is not (F1-F4; F7 names a correct answer "optimal"). A missing answer loses to any answer."""
    wins = losses = ties = 0
    for r in rows:
        x, y = r["arms"][a], r["arms"][b]
        if family in COST_FAMILIES:
            cx, cy = x.get("cost"), y.get("cost")
            better = cx is not None and (cy is None or cx < cy - 1e-9)
            worse = cy is not None and (cx is None or cy < cx - 1e-9)
        else:
            better = x.get("result") in CORRECT and y.get("result") not in CORRECT
            worse = y.get("result") in CORRECT and x.get("result") not in CORRECT
        wins, losses, ties = wins + better, losses + worse, ties + (not better and not worse)
    return {"wins": wins, "losses": losses, "ties": ties, "sign_test_p_one_sided": round(_sign_p(wins, losses), 6)}


def family_accounting(report: dict, family: str) -> dict | None:
    summary = report["summary"].get(family)
    rows = [r for r in _rows(report) if r.get("family") == family]
    if not summary or not rows:
        return None
    best, routed = summary["best_constituent"], "routed_composition"
    med = {a: statistics.median(r["arms"][a]["seconds"] for r in rows) for a in (routed, best)}
    out = {"items": len(rows), "frozen_lift": bool(summary["lift"]), "best_constituent": best,
           "latency": {"routed_median_s": round(med[routed], 4), "best_constituent_median_s": round(med[best], 4),
                       "ratio": round(med[routed] / med[best], 3) if med[best] > 0 else None,
                       "added_s": round(med[routed] - med[best], 4)}}
    if "static_composition" in rows[0]["arms"]:
        decided = sum(1 for r in rows if (r["arms"]["static_composition"].get("cost") is not None
                                          if family in COST_FAMILIES
                                          else r["arms"]["static_composition"].get("result") != "no_decision"))
        def answer(arm):
            return arm.get("answer", arm.get("plan"))
        same = sum(1 for r in rows if answer(r["arms"]["static_composition"]) is not None
                   and answer(r["arms"]["static_composition"]) == answer(r["arms"][routed]))
        out["routed_vs_static"] = {**_compare(rows, family, routed, "static_composition"),
                                   "static_decided": decided, "identical_answers": same,
                                   "static_arm": "DEGENERATE" if decided == 0 else "DECIDES"}
    out["practitioner"] = {a: {**_compare(rows, family, routed, a),
                               **({"total_cost": round(sum(r["arms"][a]["cost"] or 0 for r in rows), 3)}
                                  if family in COST_FAMILIES else {})}
                           for a in PRACTITIONER_ARMS.get(family, ()) if a in rows[0]["arms"]}
    return out


def accounting(reports: list[dict]) -> dict:
    """Section 16 accounting across frozen P6 runs (POST_HOC: it changes no frozen verdict)."""
    families = {}
    for report in reports:
        for f in report["summary"]:
            if not f.startswith("VPL") and (row := family_accounting(report, f)) is not None:
                families[f] = {**row, "source_commit": report.get("source_commit")}    # a later run replaces
    lifts = {f: r for f, r in families.items() if r["frozen_lift"]}
    by_multiplier = {f"{m:g}x": sorted(f for f, r in lifts.items()
                                       if r["latency"]["ratio"] is not None and r["latency"]["ratio"] <= m)
                     for m in LATENCY_MULTIPLIERS}
    static_decides = {f: r["routed_vs_static"] for f, r in lifts.items()
                      if r.get("routed_vs_static", {}).get("static_arm") == "DECIDES"}
    practitioner = {f: {a: v["sign_test_p_one_sided"] < 0.05 for a, v in r["practitioner"].items()}
                    for f, r in lifts.items() if r["practitioner"]}
    return {"label": "POST_HOC: computed after the runs; no frozen verdict is changed",
            "families": families,
            "remeasured": {"F2": "F2R (the same identify_then_optimize recipe, redesigned and re-measured in v2)"},
            "frozen_vpl": {"families_with_lift": sorted(lifts), "families": sorted(families)},
            "latency_sensitivity": {"lifts_within_multiplier_of_best_constituent_median": by_multiplier,
                                    "note": "no netting rule was pre-registered, so none is applied; this is a "
                                            "table, not a verdict"},
            "routing_beyond_static": {
                "families_where_static_decides": {f: {"routed_wins": v["wins"], "routed_losses": v["losses"],
                                                      "identical_answers": v["identical_answers"]}
                                                  for f, v in static_decides.items()},
                "families_where_static_is_degenerate": sorted(f for f, r in lifts.items()
                                                              if r.get("routed_vs_static", {}).get("static_arm")
                                                              == "DEGENERATE"),
                "note": "where the static recipe decides, routing chose it on every item; where it is degenerate, "
                        "routing's contribution is choosing a recipe that fits the inputs at all"},
            "practitioner_beaten_significantly": practitioner,
            "authority_created": False}


PREREG_REQUIRED = ("family_id", "natural", "data_provenance", "n_heldout", "partition_rule", "constituents",
                   "static_arm", "routed_arm", "compiled_arm", "practitioner_arms", "cost_metric", "latency_rule",
                   "rule", "alpha", "declared_before_heldout")


def validate_preregistration(doc: dict) -> list[str]:
    """Problems with a future P6 family's pre-registration (empty list = complete). Requires what the frozen
    runs lacked: a static arm that must decide, a compiled arm, a practitioner pipeline and a latency rule."""
    if not isinstance(doc, dict):
        return ["a pre-registration is a mapping"]
    problems = [f"missing {k}" for k in PREREG_REQUIRED if k not in doc]
    if problems:
        return problems
    if not (isinstance(doc["n_heldout"], int) and doc["n_heldout"] >= 30):
        problems.append("n_heldout must be an integer of at least 30")
    if not (isinstance(doc["constituents"], list) and len(doc["constituents"]) >= 2):
        problems.append("at least two constituent intelligences")
    static = doc["static_arm"]
    if not (isinstance(static, dict) and static.get("chosen_on") == "development" and static.get("must_decide") is True):
        problems.append("static_arm is chosen on development items and must decide every held-out item "
                        "(a recipe that cannot run is not a static baseline)")
    if not (isinstance(doc["compiled_arm"], dict) and doc["compiled_arm"].get("entry") == "compile"):
        problems.append("compiled_arm sends {compile: {geometry, data}} through the Competency Compiler")
    if not (isinstance(doc["practitioner_arms"], list) and doc["practitioner_arms"]):
        problems.append("at least one practitioner pipeline (the simplest method a practitioner would use)")
    rule = doc["latency_rule"]
    if not (isinstance(rule, dict) and rule.get("kind") in ("multiplier", "value_of_time")
            and isinstance(rule.get("value"), (int, float)) and not isinstance(rule.get("value"), bool)
            and rule["value"] > 0):
        problems.append("latency_rule is {kind: multiplier | value_of_time, value > 0}")
    if doc["natural"] is True and not (isinstance(doc["data_provenance"], dict)
                                       and {"source", "sha256", "licence"} <= set(doc["data_provenance"])):
        problems.append("a natural family names its data source, digest and licence")
    if not (isinstance(doc["alpha"], (int, float)) and 0 < doc["alpha"] <= 0.05):
        problems.append("alpha in (0, 0.05]")
    if doc["declared_before_heldout"] is not True:
        problems.append("the pre-registration is committed before the held-out partition is generated")
    return problems


def metrics(report: dict) -> dict:
    families = [f for f in report["summary"] if not f.startswith("VPL")]
    return {"source_commit": report.get("source_commit"), "role": "reported metrics, never a verdict",
            "families": {f: m for f in families if (m := family_metrics(report, f)) is not None}}


def main(argv: list[str]) -> None:
    reports = [json.loads(Path(path).read_text()) for path in argv]
    for path, report in zip(argv, reports):
        print(json.dumps({"file": path, **metrics(report)}, indent=1))
    print(json.dumps({"accounting": accounting(reports)}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
