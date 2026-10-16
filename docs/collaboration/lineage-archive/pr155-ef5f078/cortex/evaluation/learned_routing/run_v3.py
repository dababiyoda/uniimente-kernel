"""P4 v3: the one pre-registered decisive retest of conditional competence (founder directive 2026-10-07).

v2 was INCONCLUSIVE (57 vs 56 of 66) and single runs at a 1 s budget carried timing noise as large as the
effect. v3 changes only the measurement, never the memory: the features, size buckets, thresholds and
training data are v2's, frozen before v3's held-out items exist.

* Training: v2's development items, the same founder-pinned exploration and settlement as v2.
* Held out: fresh seeds 7-12 (never generated before) for every v2 family; bin packing labelled by the same
  20 s two-engine reference, unlabelled items excluded and listed.
* Repeats: the timing-sensitive arms (static, class_learned, conditional_learned) run 3 times per item in
  rotated order; an item counts as correct when at least 2 of 3 runs are correct (majority), wrong when at
  least 2 are wrong. Every run's latency is kept. The fixed-order references run once.
* Verdict (frozen, as v2): REGRESSION if conditional adds a wrong answer or decides fewer correctly than
  static; GAIN if more correct and the one-sided exact sign test over discordant items gives p < 0.05;
  NO_GAIN if equal; otherwise INCONCLUSIVE. The founder's instruction stands: if this does not show lift,
  record that conditional solver learning is not currently worth its complexity for this repertoire.
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
HELDOUT_SEEDS = (7, 8, 9, 10, 11, 12)
REPEATED = ("static", "class_learned", "conditional_learned")
REPEATS = 3
ARMS = V2.ARMS
FROZEN_CODE = ["cortex/evaluation/learned_routing/run_v3.py"] + V2.FROZEN_CODE + [
    "cortex/evaluation/learned_routing/suite-v2.json"]


def build() -> dict:
    items, excluded = [], []
    for family, sizes in V1.SIZES.items():
        for n in sizes:
            for seed in HELDOUT_SEEDS:
                problem, truth = V1.GENERATORS[family](n, seed)
                items.append({"item_id": problem["problem_id"], "family": family, "partition": "heldout",
                              "problem": problem, "truth": truth})
                if family == "knapsack_feasibility":
                    fast = json.loads(json.dumps(problem))
                    fast["problem_id"] = problem["problem_id"].replace("knapsack_feasibility", "knapsack_feasibility_1s")
                    fast["payload"]["resources"]["max_latency_s"] = 1.0
                    items.append({"item_id": fast["problem_id"], "family": "knapsack_feasibility_1s",
                                  "partition": "heldout", "problem": fast, "truth": truth})
    for n, bins in V2.BINPACK:
        for seed in HELDOUT_SEEDS:
            truth, reference = V2.reference_label(n, bins, seed)
            problem = V2.binpack_tight(n, bins, seed, 1.0)
            row = {"item_id": problem["problem_id"], "family": "binpack_tight_1s", "partition": "heldout",
                   "problem": problem, "truth": truth, "reference": reference}
            (items if truth is not None else excluded).append(row)
    return {"schema": "greg-learned-routing-suite/3", "training_suite": "suite-v2.json (dev partition)",
            "items": items, "excluded_unlabelled": [{"item_id": r["item_id"], "reference": r["reference"]}
                                                     for r in excluded]}


def majority(results: list[str]) -> str:
    for label in ("correct", "wrong"):
        if sum(r == label for r in results) * 2 > len(results):
            return label
    return "no_decision"


def inputs() -> dict:
    return {"suite": V1._sha(SUITE), "code": {p: V1._sha(ROOT / p) for p in FROZEN_CODE}, "arms": list(ARMS),
            "repeated": list(REPEATED), "repeats": REPEATS, "verdict_rule": V2.VERDICT_RULE,
            "heldout_seeds": list(HELDOUT_SEEDS)}


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
    dev = [i for i in json.loads((HERE / "suite-v2.json").read_text())["items"] if i["partition"] == "dev"]
    suite = json.loads(SUITE.read_text())
    pooled, conditional, training = V2.train(dev)
    rows = []
    for index, item in enumerate(suite["items"]):
        memories = {"static": None, "class_learned": pooled,
                    "conditional_learned": ConditionalCompetence(conditional.records()).bind(
                        features(item["problem"]["payload"])),
                    "z3_first": V1.FixedOrder([FORMAL, CPSAT]), "cpsat_first": V1.FixedOrder([CPSAT, FORMAL])}
        runs = {arm: [] for arm in ARMS}
        schedule = [(arm, r) for r in range(REPEATS) for arm in REPEATED] + \
                   [(arm, 0) for arm in ARMS if arm not in REPEATED]
        shift = index % len(schedule)
        for arm, _ in schedule[shift:] + schedule[:shift]:
            receipt, seconds = V1.execute(item["problem"], memory=memories[arm])
            runs[arm].append({"result": V1.score(item, receipt), "seconds": round(seconds, 3),
                              "order": receipt["route"]["formal_plan"]["order"]})
        row = {"item_id": item["item_id"], "family": item["family"], "arms": {}}
        for arm in ARMS:
            row["arms"][arm] = {"result": majority([r["result"] for r in runs[arm]]),
                                "runs": [r["result"] for r in runs[arm]],
                                "seconds": [r["seconds"] for r in runs[arm]], "order": runs[arm][0]["order"]}
        rows.append(row)
    summary = V2.summarize([{**r, "arms": {a: {**v, "seconds": statistics.median(v["seconds"])}
                                           for a, v in r["arms"].items()}} for r in rows])
    summary["latency_p90"] = {arm: round(statistics.quantiles([s for r in rows for s in r["arms"][arm]["seconds"]],
                                                              n=10)[-1], 3) for arm in ARMS}
    summary["split_runs"] = {arm: sum(1 for r in rows if len(set(r["arms"][arm]["runs"])) > 1) for arm in REPEATED}
    report = {"schema": "greg-learned-routing-results/3", "manifest_sha256": V1._sha(MANIFEST),
              "finished_at": datetime.now(timezone.utc).isoformat(),
              "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "platform": platform.platform(), "python": sys.version.split()[0],
              "training": {"runs": len(training), "records": len(conditional.records())},
              "excluded_unlabelled": suite["excluded_unlabelled"], "heldout": rows, "summary": summary}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
