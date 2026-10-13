"""P4 v2 frozen comparison: conditional competence memory vs the fixed policy and the class-level ledger.

Founder review of #155: the class-level ledger (v1) learned the fixed policy back because it pooled
competence per epistemic class. v2 asks whether GREG's conditional memory
(``greg/cognition/conditional_competence.py``: problem features + hierarchical fallback) decides
more held-out problems correctly than the fixed cortex 0.2.1 policy, with no added wrong answers.

Suite (generated; v1 families unchanged plus two feasibility sub-regions with opposite winners):
* v1: pigeonhole, schedules, planted equalities, knapsack feasibility and optimisation at 3 s;
* ``knapsack_feasibility_1s`` - the same generator at a 1 s budget;
* ``binpack_tight_1s`` - 0/1 bin packing with capacity at the average load (ceil), 1 s budget. Truth is
  a reference label written at build time: both engines pinned with a 20 s budget; feasible when either
  returns a feasible assignment (re-checked by the cortex evaluator), infeasible when one proves it and
  none finds a witness; otherwise the item is excluded and listed.
Seeds 1-3 development, 4-6 held out.

Training (development only), as v1: one founder-pinned run per engine per item, settled through
``CompetenceLedger.settle`` with GREG's provenance (internal observation, weight 0.6). The class ledger
settles with no conditions (the v1 method); the conditional memory settles with the item's features.

Arms (held out, every arm executes): static, class_learned, conditional_learned, z3_first and
cpsat_first (references). Verdict (frozen) for conditional_learned vs static: REGRESSION if it adds a
wrong answer or decides fewer correctly; GAIN if more correct and the one-sided exact sign test over
discordant items gives p < 0.05; NO_GAIN if equal; otherwise INCONCLUSIVE. The same rule is reported
for conditional_learned vs class_learned.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform
import random
import statistics
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from cortex.evaluation.learned_routing import run as V1  # noqa: E402
from cortex.memory import CompetenceLedger  # noqa: E402
from cortex.routing import CPSAT, FORMAL  # noqa: E402

SUITE = HERE / "suite-v2.json"
MANIFEST = HERE / "freeze-v2.json"
ARMS = ("static", "class_learned", "conditional_learned", "z3_first", "cpsat_first")
BINPACK = ((24, 6), (36, 6), (48, 8), (60, 10))
REFERENCE_BUDGET_S = 20.0
FROZEN_CODE = ["cortex/evaluation/learned_routing/run_v2.py", "cortex/evaluation/learned_routing/run.py",
               "greg/cognition/conditional_competence.py", "greg/cognition/learned_routing.py", "cortex/memory.py",
               "cortex/routing.py", "cortex/organs/formal.py", "cortex/organs/cpsat.py", "cortex/organs/formal_eval.py",
               "cortex/organs/adversarial.py", "requirements-cortex.txt"]
VERDICT_RULE = V1.VERDICT_RULE


def binpack_tight(n, bins, seed, budget):
    r = random.Random(3000 + seed)
    sizes = [r.randint(5, 30) for _ in range(n)]
    cap = math.ceil(sum(sizes) / bins)
    v = [{"name": f"b{i}_{k}", "sort": "int", "lo": 0, "hi": 1} for i in range(n) for k in range(bins)]
    cons = [["=", ["+", *[f"b{i}_{k}" for k in range(bins)]], 1] for i in range(n)]
    cons += [["<=", ["+", *[["*", sizes[i], f"b{i}_{k}"] for i in range(n)]], cap] for k in range(bins)]
    problem = V1._problem(f"binpack_tight_1s-{n}x{bins}-{seed}", v, cons)
    problem["payload"]["resources"]["max_latency_s"] = budget
    return problem


def reference_label(n, bins, seed) -> tuple[dict | None, dict]:
    problem = binpack_tight(n, bins, seed, REFERENCE_BUDGET_S)
    found = {}
    for lead, other in ((FORMAL, CPSAT), (CPSAT, FORMAL)):
        receipt, seconds = V1.execute(problem, withhold=other)
        found[lead] = {"feasible": (receipt["output"].get("answer") or {}).get("feasible"),
                       "state": receipt["output"]["state"], "seconds": round(seconds, 2)}
    values = {f["feasible"] for f in found.values()}
    if True in values:
        return {"feasible": True}, found
    if False in values:
        return {"feasible": False}, found
    return None, found


def build() -> dict:
    items, excluded = [], []
    for family, sizes in V1.SIZES.items():
        for n in sizes:
            for partition, seeds in (("dev", V1.DEV_SEEDS), ("heldout", V1.HELDOUT_SEEDS)):
                for seed in seeds:
                    problem, truth = V1.GENERATORS[family](n, seed)
                    items.append({"item_id": problem["problem_id"], "family": family, "size": n, "seed": seed,
                                  "partition": partition, "problem": problem, "truth": truth})
                    if family == "knapsack_feasibility":
                        fast = json.loads(json.dumps(problem))
                        fast["problem_id"] = problem["problem_id"].replace("knapsack_feasibility",
                                                                          "knapsack_feasibility_1s")
                        fast["payload"]["resources"]["max_latency_s"] = 1.0
                        items.append({"item_id": fast["problem_id"], "family": "knapsack_feasibility_1s", "size": n,
                                      "seed": seed, "partition": partition, "problem": fast, "truth": truth})
    for n, bins in BINPACK:
        for partition, seeds in (("dev", V1.DEV_SEEDS), ("heldout", V1.HELDOUT_SEEDS)):
            for seed in seeds:
                truth, reference = reference_label(n, bins, seed)
                problem = binpack_tight(n, bins, seed, 1.0)
                row = {"item_id": problem["problem_id"], "family": "binpack_tight_1s", "size": n * bins, "seed": seed,
                       "partition": partition, "problem": problem, "truth": truth, "reference": reference}
                (items if truth is not None else excluded).append(row)
    return {"schema": "greg-learned-routing-suite/2", "reference_budget_s": REFERENCE_BUDGET_S,
            "items": items, "excluded_unlabelled": [{"item_id": r["item_id"], "reference": r["reference"]}
                                                     for r in excluded]}


def train(items):
    from greg.cognition.conditional_competence import conditions, features
    from greg.cognition.learned_routing import PROVENANCE
    pooled, conditional, log = CompetenceLedger(), CompetenceLedger(), []
    for item in items:
        conds = conditions(features(item["problem"]["payload"]))
        for lead, other in ((FORMAL, CPSAT), (CPSAT, FORMAL)):
            receipt, seconds = V1.execute(item["problem"], withhold=other)
            if receipt["route"]["selected"] != [lead]:
                log.append({"item_id": item["item_id"], "lead": lead, "settled": None, "why": "not eligible"})
                continue
            result = V1.score(item, receipt)
            status = "verified_success" if result == "correct" else "observed_failure"
            method, _, version = lead.partition("@")
            kw = dict(receipt=receipt, method=method, method_version=version, outcome_status=status,
                      provenance={**PROVENANCE, "basis": "ground truth of the generated item"},
                      attribution=[{"method": method, "role": "final_answer" if result != "no_decision"
                                    else "resource_consumption", "uncertainty": "low"}])
            pooled.settle(**kw)
            conditional.settle(**kw, conditions=conds)
            log.append({"item_id": item["item_id"], "family": item["family"], "lead": lead, "result": result,
                        "seconds": round(seconds, 3), "conditions": list(conds)})
    return pooled, conditional, log


def compare(rows, arm, baseline) -> dict:
    a = [r["arms"][arm]["result"] for r in rows]
    b = [r["arms"][baseline]["result"] for r in rows]
    wins = sum(1 for x, y in zip(a, b) if x == "correct" and y != "correct")
    losses = sum(1 for x, y in zip(a, b) if y == "correct" and x != "correct")
    ca, cb = a.count("correct"), b.count("correct")
    wa, wb = a.count("wrong"), b.count("wrong")
    p = V1.sign_test(wins, losses)
    if wa > wb or ca < cb:
        verdict = "REGRESSION"
    elif ca > cb and p < 0.05:
        verdict = "GAIN"
    elif ca == cb:
        verdict = "NO_GAIN"
    else:
        verdict = "INCONCLUSIVE"
    return {"verdict": verdict, "correct": [ca, cb], "wrong": [wa, wb], "wins": wins, "losses": losses,
            "sign_test_p_one_sided": round(p, 6)}


def summarize(rows) -> dict:
    families = sorted({r["family"] for r in rows})
    per_family = {f: {arm: sum(1 for r in rows if r["family"] == f and r["arms"][arm]["result"] == "correct")
                      for arm in ARMS} | {"n": sum(1 for r in rows if r["family"] == f)} for f in families}
    counts = {arm: {k: sum(1 for r in rows if r["arms"][arm]["result"] == k) for k in ("correct", "wrong",
                                                                                          "no_decision")}
              for arm in ARMS}
    oracle = sum(1 for r in rows if "correct" in (r["arms"]["z3_first"]["result"], r["arms"]["cpsat_first"]["result"]))
    return {"conditional_vs_static": compare(rows, "conditional_learned", "static"),
            "conditional_vs_class": compare(rows, "conditional_learned", "class_learned"),
            "class_vs_static": compare(rows, "class_learned", "static"),
            "counts": counts, "per_family_correct": per_family, "oracle_either_fixed_order": oracle,
            "median_seconds": {arm: round(statistics.median(r["arms"][arm]["seconds"] for r in rows), 3)
                               for arm in ARMS}, "rule": VERDICT_RULE}


def inputs() -> dict:
    return {"suite": V1._sha(SUITE), "code": {p: V1._sha(ROOT / p) for p in FROZEN_CODE}, "arms": list(ARMS),
            "verdict_rule": VERDICT_RULE, "dev_seeds": list(V1.DEV_SEEDS), "heldout_seeds": list(V1.HELDOUT_SEEDS)}


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
    pooled, conditional, training = train(dev)
    rows = []
    for index, item in enumerate(heldout):
        memories = {"static": None, "class_learned": pooled,
                    "conditional_learned": ConditionalCompetence(conditional.records()).bind(
                        features(item["problem"]["payload"])),
                    "z3_first": V1.FixedOrder([FORMAL, CPSAT]), "cpsat_first": V1.FixedOrder([CPSAT, FORMAL])}
        order = ARMS[index % len(ARMS):] + ARMS[:index % len(ARMS)]
        row = {"item_id": item["item_id"], "family": item["family"], "arms": {}}
        for arm in order:
            receipt, seconds = V1.execute(item["problem"], memory=memories[arm])
            row["arms"][arm] = {"result": V1.score(item, receipt), "state": receipt["output"]["state"],
                                "order": receipt["route"]["formal_plan"]["order"], "seconds": round(seconds, 3)}
        row["arms"] = {a: row["arms"][a] for a in ARMS}
        if item["family"] in ("binpack_tight_1s", "knapsack_feasibility_1s", "knapsack_feasibility"):
            row["competence"] = memories["conditional_learned"].explain([FORMAL, CPSAT],
                                                                        "constraint_feasibility")
        rows.append(row)
    report = {"schema": "greg-learned-routing-results/2", "manifest_sha256": V1._sha(MANIFEST),
              "finished_at": datetime.now(timezone.utc).isoformat(),
              "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "platform": platform.platform(), "python": sys.version.split()[0],
              "training": {"runs": training, "records": len(conditional.records())},
              "excluded_unlabelled": suite["excluded_unlabelled"], "heldout": rows, "summary": summarize(rows),
              "limits": ["bin-packing truth is a 20 s reference label, not a proof for every item",
                         "size buckets are a fixed log scale (10/30/100/300/1000), not tuned to this suite",
                         "one container, one CPU budget; timing-dependent results may differ elsewhere"]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report["summary"], indent=1))


if __name__ == "__main__":
    main()
