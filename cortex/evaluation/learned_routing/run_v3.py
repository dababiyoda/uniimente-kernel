"""P4 v3: the one decisive, pre-registered retest of conditional competence memory (founder directive 2026-10-07).

P4 v2 (``run_v2.py``, ``freeze-v2.json``) was INCONCLUSIVE: conditional 57 vs static 56 of 66, 3 wins
and 2 losses, with timing noise at the 1 s cliff as large as the effect. v3 changes only what the
directive names and nothing that could tune the memory to the answer:

* Memory, features and buckets: ``greg/cognition/conditional_competence.py`` exactly as frozen in v2
  (hashed below). No size bucket, margin, evidence threshold or shrinkage is changed.
* Training: the v2 development items (seeds 1-3, copied verbatim from ``suite-v2.json``) and the v2
  training protocol (one founder-pinned run per engine, ground-truth settlement, weight 0.6).
* Held out: NEW seeds no arm has seen - seeds 7-14 for the v1 families and the 1 s knapsack
  feasibility family, seeds 7-18 for tight bin packing (the sub-region where the memory's decision
  differs from the fixed policy), labelled by the v2 20 s two-engine reference; unlabelled items are
  excluded and listed before any arm runs.
* Repeats: every arm runs every held-out item ``REPEATS`` = 3 times under identical conditions; the arm
  order rotates per item and per repeat.
* Aggregation (predeclared): an arm's result on an item is the category (correct / wrong / no_decision)
  that occurs in at least 2 of 3 runs; with no majority the result is no_decision. A wrong answer in any
  single run is also counted separately (``wrong_any``).
* Arms: static (cortex 0.2.1 policy), class_learned (v1 ledger), conditional_learned, z3_first,
  cpsat_first; ``oracle`` = correct when either fixed order's majority is correct (upper bound for
  ordering two engines).

Primary verdict, conditional_learned vs static (frozen before the held-out run):
  REGRESSION if conditional adds a wrong answer (majority or wrong_any) or decides fewer correctly;
  NO_GAIN if the correct counts are equal;
  INCONCLUSIVE_UNDERPOWERED if there are fewer than ``MIN_DISCORDANT`` = 6 discordant items;
  GAIN if more correct and the one-sided exact sign test over discordant items gives p < 0.05;
  otherwise INCONCLUSIVE.

Predeclared consequence: anything but GAIN demotes conditional formal-engine routing - the default stays
``shadow`` (memory observed, never applied), and the record states that conditional solver learning is
not currently worth its complexity for this two-engine repertoire. GAIN makes it eligible for the
``learned`` default, which remains a founder decision. Latency (per-item median of 3, distribution
percentiles, paired faster/slower counts on items both arms decide correctly) is a secondary endpoint
and never changes the verdict.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from cortex.evaluation.learned_routing import run as V1  # noqa: E402
from cortex.evaluation.learned_routing import run_v2 as V2  # noqa: E402
from cortex.routing import CPSAT, FORMAL  # noqa: E402

SUITE = HERE / "suite-v3.json"
MANIFEST = HERE / "freeze-v3.json"
ARMS = V2.ARMS
REPEATS = 3
MIN_DISCORDANT = 6
HELDOUT_SEEDS = tuple(range(7, 15))
BINPACK_HELDOUT_SEEDS = tuple(range(7, 19))
FROZEN_CODE = ["cortex/evaluation/learned_routing/run_v3.py", *V2.FROZEN_CODE]
VERDICT_RULE = ("majority of 3 runs per arm and item; REGRESSION if conditional adds a wrong answer (majority or any "
                "run) or decides fewer correctly; NO_GAIN if equal correct; INCONCLUSIVE_UNDERPOWERED if < 6 "
                "discordant items; GAIN if more correct and one-sided exact sign test p < 0.05; else INCONCLUSIVE. "
                "Anything but GAIN keeps the shadow default and demotes conditional formal-engine routing.")


def build() -> dict:
    v2 = json.loads(V2.SUITE.read_text())
    items = [i for i in v2["items"] if i["partition"] == "dev"]
    excluded = [e for e in v2["excluded_unlabelled"] if any(e["item_id"].endswith(f"-{s}") for s in V1.DEV_SEEDS)]
    for family, sizes in V1.SIZES.items():
        for n in sizes:
            for seed in HELDOUT_SEEDS:
                problem, truth = V1.GENERATORS[family](n, seed)
                items.append({"item_id": problem["problem_id"], "family": family, "size": n, "seed": seed,
                              "partition": "heldout", "problem": problem, "truth": truth})
                if family == "knapsack_feasibility":
                    fast = json.loads(json.dumps(problem))
                    fast["problem_id"] = problem["problem_id"].replace("knapsack_feasibility", "knapsack_feasibility_1s")
                    fast["payload"]["resources"]["max_latency_s"] = 1.0
                    items.append({"item_id": fast["problem_id"], "family": "knapsack_feasibility_1s", "size": n,
                                  "seed": seed, "partition": "heldout", "problem": fast, "truth": truth})
    for n, bins in V2.BINPACK:
        for seed in BINPACK_HELDOUT_SEEDS:
            truth, reference = V2.reference_label(n, bins, seed)
            problem = V2.binpack_tight(n, bins, seed, 1.0)
            row = {"item_id": problem["problem_id"], "family": "binpack_tight_1s", "size": n * bins, "seed": seed,
                   "partition": "heldout", "problem": problem, "truth": truth, "reference": reference}
            if truth is None:
                excluded.append({"item_id": row["item_id"], "reference": reference})
            else:
                items.append(row)
    return {"schema": "greg-learned-routing-suite/3", "reference_budget_s": V2.REFERENCE_BUDGET_S,
            "dev_from": "suite-v2.json (dev partition, verbatim)", "items": items, "excluded_unlabelled": excluded}


def majority(results: list[str]) -> str:
    for category in ("correct", "wrong", "no_decision"):
        if results.count(category) >= 2:
            return category
    return "no_decision"


def compare(rows, arm, baseline) -> dict:
    a = [r["arms"][arm]["result"] for r in rows]
    b = [r["arms"][baseline]["result"] for r in rows]
    wins = sum(1 for x, y in zip(a, b) if x == "correct" and y != "correct")
    losses = sum(1 for x, y in zip(a, b) if y == "correct" and x != "correct")
    ca, cb = a.count("correct"), b.count("correct")
    wa, wb = a.count("wrong"), b.count("wrong")
    any_a = sum(r["arms"][arm]["wrong_any"] for r in rows)
    any_b = sum(r["arms"][baseline]["wrong_any"] for r in rows)
    p = V1.sign_test(wins, losses)
    if wa > wb or any_a > any_b or ca < cb:
        verdict = "REGRESSION"
    elif ca == cb:
        verdict = "NO_GAIN"
    elif wins + losses < MIN_DISCORDANT:
        verdict = "INCONCLUSIVE_UNDERPOWERED"
    elif ca > cb and p < 0.05:
        verdict = "GAIN"
    else:
        verdict = "INCONCLUSIVE"
    return {"verdict": verdict, "correct": [ca, cb], "wrong": [wa, wb], "wrong_any_run": [any_a, any_b],
            "wins": wins, "losses": losses, "discordant": wins + losses, "sign_test_p_one_sided": round(p, 6)}


def _pct(values, q):
    values = sorted(values)
    if not values:
        return None
    k = (len(values) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(values) - 1)
    return round(values[lo] + (values[hi] - values[lo]) * (k - lo), 4)


def latency(rows, arm, baseline) -> dict:
    both = [r for r in rows if r["arms"][arm]["result"] == r["arms"][baseline]["result"] == "correct"]
    faster = sum(1 for r in both if r["arms"][arm]["median_s"] < r["arms"][baseline]["median_s"])
    slower = sum(1 for r in both if r["arms"][arm]["median_s"] > r["arms"][baseline]["median_s"])
    diffs = [r["arms"][arm]["median_s"] - r["arms"][baseline]["median_s"] for r in both]
    return {"items_both_correct": len(both), "faster": faster, "slower": slower,
            "median_difference_s": round(statistics.median(diffs), 4) if diffs else None,
            "sign_test_p_faster_one_sided": round(V1.sign_test(faster, slower), 6)}


def summarize(rows) -> dict:
    families = sorted({r["family"] for r in rows})
    counts = {arm: {k: sum(1 for r in rows if r["arms"][arm]["result"] == k) for k in ("correct", "wrong",
                                                                                          "no_decision")}
              | {"wrong_any_run": sum(r["arms"][arm]["wrong_any"] for r in rows)} for arm in ARMS}
    per_family = {f: {arm: sum(1 for r in rows if r["family"] == f and r["arms"][arm]["result"] == "correct")
                      for arm in ARMS} | {"n": sum(1 for r in rows if r["family"] == f),
                                          "oracle": sum(1 for r in rows if r["family"] == f and r["oracle"])}
                  for f in families}
    seconds = {arm: [s for r in rows for s in r["arms"][arm]["seconds"]] for arm in ARMS}
    unstable = {arm: sum(1 for r in rows if len(set(r["arms"][arm]["results"])) > 1) for arm in ARMS}
    return {"primary_conditional_vs_static": compare(rows, "conditional_learned", "static"),
            "conditional_vs_class": compare(rows, "conditional_learned", "class_learned"),
            "class_vs_static": compare(rows, "class_learned", "static"),
            "conditional_vs_z3_first": compare(rows, "conditional_learned", "z3_first"),
            "conditional_vs_cpsat_first": compare(rows, "conditional_learned", "cpsat_first"),
            "counts": counts, "oracle_correct": sum(1 for r in rows if r["oracle"]), "n": len(rows),
            "per_family_correct": per_family,
            "latency_distribution_s": {arm: {"p10": _pct(v, .1), "p50": _pct(v, .5), "p90": _pct(v, .9),
                                             "max": max(v) if v else None} for arm, v in seconds.items()},
            "latency_conditional_vs_static": latency(rows, "conditional_learned", "static"),
            "items_with_unstable_repeats": unstable, "rule": VERDICT_RULE}


def consequence(summary) -> str:
    v = summary["primary_conditional_vs_static"]["verdict"]
    if v == "GAIN":
        return ("GAIN: conditional memory is eligible to become the `learned` default for formal-engine ordering; "
                "changing the default remains a founder decision")
    return (f"{v}: conditional formal-engine routing is demoted. The `shadow` default stays; conditional solver "
            "learning is not currently worth its complexity for this two-engine repertoire. The memory is retained "
            "(observed in shadow, never applied by default) as evidence and as a substrate for wider repertoires.")


def inputs() -> dict:
    return {"suite": V1._sha(SUITE), "code": {p: V1._sha(ROOT / p) for p in FROZEN_CODE}, "arms": list(ARMS),
            "repeats": REPEATS, "min_discordant": MIN_DISCORDANT, "verdict_rule": VERDICT_RULE,
            "dev_seeds": list(V1.DEV_SEEDS), "heldout_seeds": list(HELDOUT_SEEDS),
            "binpack_heldout_seeds": list(BINPACK_HELDOUT_SEEDS)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    if args.build:
        if SUITE.exists():
            raise SystemExit("refusing to overwrite the suite; create a new version")
        SUITE.write_text(json.dumps(build()) + "\n")
        return
    if args.freeze:
        if MANIFEST.exists():
            raise SystemExit("refusing to overwrite an existing freeze; create a new version")
        MANIFEST.write_text(json.dumps({"frozen_at": datetime.now(timezone.utc).isoformat(), "inputs": inputs()},
                                       indent=2) + "\n")
        return
    if json.loads(MANIFEST.read_text())["inputs"] != inputs():
        raise SystemExit("FROZEN_INPUT_CHANGED: results cannot be reported")
    if not args.out:
        raise SystemExit("--out required")
    from greg.cognition.conditional_competence import ConditionalCompetence, features
    suite = json.loads(SUITE.read_text())
    dev = [i for i in suite["items"] if i["partition"] == "dev"]
    heldout = [i for i in suite["items"] if i["partition"] == "heldout"]
    pooled, conditional, training = V2.train(dev)
    records = conditional.records()
    rows = []
    for index, item in enumerate(heldout):
        memories = {"static": None, "class_learned": pooled,
                    "conditional_learned": ConditionalCompetence(records).bind(features(item["problem"]["payload"])),
                    "z3_first": V1.FixedOrder([FORMAL, CPSAT]), "cpsat_first": V1.FixedOrder([CPSAT, FORMAL])}
        runs = {arm: [] for arm in ARMS}
        for repeat in range(REPEATS):
            shift = (index + repeat) % len(ARMS)
            for arm in ARMS[shift:] + ARMS[:shift]:
                receipt, seconds = V1.execute(item["problem"], memory=memories[arm])
                runs[arm].append({"result": V1.score(item, receipt), "state": receipt["output"]["state"],
                                  "order": receipt["route"]["formal_plan"]["order"], "seconds": round(seconds, 3)})
        row = {"item_id": item["item_id"], "family": item["family"], "arms": {}}
        for arm in ARMS:
            results = [r["result"] for r in runs[arm]]
            secs = [r["seconds"] for r in runs[arm]]
            row["arms"][arm] = {"result": majority(results), "results": results, "wrong_any": int("wrong" in results),
                                "orders": [r["order"] for r in runs[arm]], "seconds": secs,
                                "median_s": statistics.median(secs)}
        row["oracle"] = "correct" in (row["arms"]["z3_first"]["result"], row["arms"]["cpsat_first"]["result"])
        if item["family"] in ("binpack_tight_1s", "knapsack_feasibility_1s", "knapsack_feasibility"):
            row["competence"] = memories["conditional_learned"].explain([FORMAL, CPSAT], "constraint_feasibility")
        rows.append(row)
        print(json.dumps({"i": index, "item": item["item_id"],
                          "results": {a: row["arms"][a]["result"] for a in ARMS}}), flush=True)
    summary = summarize(rows)
    report = {"schema": "greg-learned-routing-results/3", "manifest_sha256": V1._sha(MANIFEST),
              "finished_at": datetime.now(timezone.utc).isoformat(),
              "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "platform": platform.platform(), "python": sys.version.split()[0],
              "training": {"runs": training, "records": len(records)},
              "excluded_unlabelled": suite["excluded_unlabelled"], "heldout": rows, "summary": summary,
              "consequence": consequence(summary),
              "limits": ["bin-packing truth is a 20 s reference label, not a proof for every item",
                         "feature buckets are v2's fixed log scale, deliberately not retuned",
                         "one container, one CPU budget; 3 repeats reduce but do not remove timing noise",
                         "two engines only: the conclusion is about ordering Z3 and CP-SAT, not about "
                         "conditional competence over a wider repertoire"]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({"summary": summary, "consequence": report["consequence"]}, indent=1))


if __name__ == "__main__":
    main()
