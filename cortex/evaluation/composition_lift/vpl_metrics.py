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

Usage: python -I cortex/evaluation/composition_lift/vpl_metrics.py <results.json> [<more results.json>]
"""
from __future__ import annotations

import json
from pathlib import Path
import statistics
import sys


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


def metrics(report: dict) -> dict:
    families = [f for f in report["summary"] if not f.startswith("VPL")]
    return {"source_commit": report.get("source_commit"), "role": "reported metrics, never a verdict",
            "families": {f: m for f in families if (m := family_metrics(report, f)) is not None}}


def main(argv: list[str]) -> None:
    for path in argv:
        print(json.dumps({"file": path, **metrics(json.loads(Path(path).read_text()))}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
