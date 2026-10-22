"""F8 fallback diagnostic: recombine F8's frozen per-item rows; run nothing new. Diagnostic only.

Founder review 2026-10-15. F8 (#158, frozen at ``202b932``) met its rule against the best constituent, but its total
modelled cost was 4.7% above the EWMA-quantile ablation, because the tracker's 203 fallbacks to the standing plan
cost 47,638 more than the ablation on those items. This script asks one question of the frozen rows:

    what would the composition have cost had it fallen back to the ablation instead of the standing plan?

It reads ``results-v5.json`` and writes nothing back to it. The answer is **diagnostic, not a claim**: the
alternative fallback was suggested by these same held-out data, so its cost here is biased in its favour. A
generalisation claim needs the pre-registered evaluation in ``prereg-draft.json``, on fresh data, under one owner.
Refusal reasons are inferred from the number of stages run: the frozen run recorded ``STAGE_ABSTAINED``, not why.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[3]
FROZEN = ROOT / "docs/evidence/greg-composition-lift/2026-10-14-v5/results-v5.json"
OUT = ROOT / "docs/evidence/pr155-f8-fallback-diagnostic/2026-10-15/results.json"
REFUSAL = {0: "INSUFFICIENT_MEASUREMENTS (no stage ran: fewer than 3 usable measurements)",
           1: "TRACKER_REFUSED (one stage ran: the tracker's own abstention contract, read as its NIS test)"}


def _tail(excess: list[float]) -> dict:
    xs = sorted(excess)
    q = lambda p: xs[min(len(xs) - 1, int(p * len(xs)))]  # noqa: E731
    return {"p95_excess": q(0.95), "p99_excess": q(0.99), "max_excess": xs[-1], "sum_excess": sum(xs)}


def diagnose(rows: list[dict]) -> dict:
    arms = {"unchanged (routed composition, standing-plan fallback)": [],
            "simpler ablation (EWMA ratio + quantile, then Erlang)": [],
            "proposed fallback (routed composition; EWMA-quantile when the tracker abstains)": []}
    names = list(arms)
    refusals: dict[str, int] = {}
    for row in rows:
        routed, ablation = row["arms"]["routed_composition"], row["arms"]["ewma_ratio_quantile_then_staff"]
        hindsight = row["truth"]["hindsight_cost"]
        fell_back = routed["result"] != "decided"
        if fell_back:
            reason = REFUSAL.get(routed["stages"], f"UNCLASSIFIED ({routed['stages']} stages)")
            refusals[reason] = refusals.get(reason, 0) + 1
        hybrid_cost = ablation["cost"] if fell_back else routed["cost"]
        hybrid_seconds = routed["seconds"] + (ablation["seconds"] if fell_back else 0.0)
        for name, cost, seconds, decided in (
                (names[0], routed["cost"], routed["seconds"], not fell_back),
                (names[1], ablation["cost"], ablation["seconds"], ablation["result"] == "decided"),
                (names[2], hybrid_cost, hybrid_seconds, True)):
            arms[name].append({"cost": cost, "excess": cost - hindsight, "seconds": seconds, "decided": decided})
    out = {}
    for name, xs in arms.items():
        out[name] = {"total_cost": sum(x["cost"] for x in xs),
                     "coverage_without_fallback": sum(x["decided"] for x in xs) / len(xs),
                     "median_seconds": statistics.median(x["seconds"] for x in xs),
                     **_tail([x["excess"] for x in xs])}
    base = out[names[1]]["total_cost"]
    for name in names:
        out[name]["vs_simpler_ablation"] = out[name]["total_cost"] / base - 1
    return {"arms": out, "fallbacks": sum(refusals.values()), "refusal_reasons_inferred": refusals,
            "simpler_method_wins_total_cost": min(out, key=lambda n: out[n]["total_cost"]) == names[1]}


def main() -> int:
    data = FROZEN.read_bytes()
    digest = "sha256:" + hashlib.sha256(data).hexdigest()
    frozen = json.loads(data)
    result = {"schema": "pr155-f8-fallback-diagnostic/1", "status": "DIAGNOSTIC_ON_EXPOSED_DATA_NOT_A_CLAIM",
              "frozen_source": {"path": str(FROZEN.relative_to(ROOT)), "sha256": digest,
                                "source_commit": frozen["source_commit"]},
              "latency_note": "the ablation runs in process, so its latency is not comparable with the GREG arms'; "
                              "the proposed arm adds the ablation's in-process time on fallback items",
              "selection_bias": "the proposed fallback was suggested by these held-out rows (README, 'two "
                                "improvements are suggested by the data'); its cost here is biased in its favour",
              **diagnose(frozen["heldout"])}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    print(json.dumps(result, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
