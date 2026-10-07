"""P4 frozen comparison: does GREG's learned formal-engine routing beat the fixed policy?

Question. The cortex 0.2.1 route policy is fixed: Z3 leads feasibility/entailment, CP-SAT
leads optimization. GREG now settles competence from its own outcomes
(``greg/cognition/learned_routing.py``) and, in a signed ``learned`` mission, lets that
memory permute the eligible engines. This run measures whether doing so decides more
held-out problems correctly than the fixed policy, under the same latency budget.

Protocol (frozen by ``--freeze`` before the held-out partition is run):

* Suite. Five generated families with ground truth by construction or exact DP:
  pigeonhole (infeasible), disjunctive single-machine schedules (feasible by horizon),
  integer equality systems with a planted solution (feasible), 0/1 knapsack feasibility
  at the exact optimum or one above it (DP), 0/1 knapsack optimization (DP optimum).
  Three sizes each. Seeds 1-3 are development, seeds 4-6 are held out.
* Training (development only). Exploration is the lawful GREG mechanism: one run per
  engine with the other withheld (a founder pin). Each run settles the lead engine
  through ``CompetenceLedger.settle`` with GREG's provenance (internal observation,
  weight 0.6): verified_success when the answer matches ground truth, observed_failure
  when it is wrong or the engine returned no decision. Ground truth stands in for the
  signed check plus separate-process appraisal that GREG requires in production.
* Held out. Arms: ``static`` (no memory), ``learned`` (the trained ledger),
  ``z3_first`` and ``cpsat_first`` (fixed orders, references only). Every arm really
  executes every item; order of arms is rotated per item.
* Scoring. correct = a decision that matches ground truth (feasibility verdict; certified
  optimal objective equal to the DP optimum). wrong = a decision that does not. Anything
  else is no decision.
* Verdict (frozen): REGRESSION if learned adds a wrong answer or decides fewer items
  correctly; GAIN if learned decides more items correctly and the exact one-sided sign test
  over discordant items gives p < 0.05; NO_GAIN if correct counts are equal;
  otherwise INCONCLUSIVE.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import itertools
import json
import math
from pathlib import Path
import platform
import random
import statistics
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from cortex.genome import seed_registry  # noqa: E402
from cortex.memory import CompetenceLedger  # noqa: E402
from cortex.routing import CPSAT, FORMAL, Cortex  # noqa: E402

SUITE = HERE / "suite.json"
MANIFEST = HERE / "freeze-v1.json"
BUDGET_S = 3.0
SIZES = {"pigeonhole": (6, 7, 8), "schedule": (8, 12, 16), "equalities": (4, 6, 8),
         "knapsack_feasibility": (20, 30, 40), "knapsack_optimization": (15, 30, 50)}
DEV_SEEDS, HELDOUT_SEEDS = (1, 2, 3), (4, 5, 6)
ARMS = ("static", "learned", "z3_first", "cpsat_first")
FROZEN_CODE = ["cortex/evaluation/learned_routing/run.py", "greg/cognition/learned_routing.py",
               "cortex/memory.py", "cortex/routing.py", "cortex/organs/formal.py", "cortex/organs/cpsat.py",
               "cortex/organs/formal_eval.py", "cortex/organs/adversarial.py", "requirements-cortex.txt"]
VERDICT_RULE = ("REGRESSION if learned adds a wrong answer or decides fewer correctly; GAIN if more correct and "
                "one-sided exact sign test p < 0.05; NO_GAIN if equal; else INCONCLUSIVE")
DECL = {"consequence_class": "read_only", "reversibility": "reversible"}


# ------------------------------------------------------------------ suite
def _problem(pid, variables, constraints, query=None):
    model = {"requirement": "generated", "variables": variables, "obligations": [{"id": "R", "text": "generated"}],
             "constraints": [{"id": f"C{i}", "covers": ["R"], "expr": e} for i, e in enumerate(constraints)]}
    if query:
        model["query"] = query
    return {"problem_id": pid, "question": "generated formal question",
            "payload": {"formal_model": model, "resources": {"max_latency_s": BUDGET_S}, "declared": DECL}}


def pigeonhole(n, seed):
    v = [{"name": f"p{k}", "sort": "int", "lo": 1, "hi": n} for k in range(n + 1)]
    order = list(itertools.combinations(range(n + 1), 2))
    random.Random(seed).shuffle(order)
    return _problem(f"pigeonhole-{n}-{seed}", v, [["!=", f"p{a}", f"p{b}"] for a, b in order]), {"feasible": False}


def schedule(n, seed):
    r = random.Random(seed)
    d = [r.randint(2, 9) for _ in range(n)]
    horizon = sum(d)
    v = [{"name": f"s{i}", "sort": "int", "lo": 0, "hi": horizon} for i in range(n)]
    cons = [["<=", ["+", f"s{i}", d[i]], horizon] for i in range(n)]
    cons += [["or", ["<=", ["+", f"s{i}", d[i]], f"s{j}"], ["<=", ["+", f"s{j}", d[j]], f"s{i}"]]
             for i, j in itertools.combinations(range(n), 2)]
    return _problem(f"schedule-{n}-{seed}", v, cons), {"feasible": True}


def equalities(n, seed):
    r = random.Random(seed)
    x = [r.randint(0, 50) for _ in range(n)]
    v = [{"name": f"x{i}", "sort": "int", "lo": 0, "hi": 50} for i in range(n)]
    cons = []
    for _ in range(n // 2):
        a = [r.randint(1, 97) for _ in range(n)]
        cons.append(["=", ["+", *[["*", a[i], f"x{i}"] for i in range(n)]], sum(a[i] * x[i] for i in range(n))])
    return _problem(f"equalities-{n}-{seed}", v, cons), {"feasible": True}


def _knapsack(n, seed):
    r = random.Random(seed)
    w = [r.randint(10, 60) for _ in range(n)]
    val = [wi + r.randint(-5, 15) for wi in w]
    cap = sum(w) // 2
    best = [0] * (cap + 1)
    for wi, vi in zip(w, val):
        for c in range(cap, wi - 1, -1):
            best[c] = max(best[c], best[c - wi] + vi)
    return w, val, cap, best[cap]


def knapsack_feasibility(n, seed):
    w, val, cap, opt = _knapsack(n, seed)
    target = opt + (seed % 2)            # odd seeds ask for one more than the optimum: infeasible
    v = [{"name": f"x{i}", "sort": "int", "lo": 0, "hi": 1} for i in range(n)]
    cons = [["<=", ["+", *[["*", w[i], f"x{i}"] for i in range(n)]], cap],
            [">=", ["+", *[["*", val[i], f"x{i}"] for i in range(n)]], target]]
    return _problem(f"knapsack_feasibility-{n}-{seed}", v, cons), {"feasible": target <= opt}


def knapsack_optimization(n, seed):
    w, val, cap, opt = _knapsack(n, seed)
    v = [{"name": f"x{i}", "sort": "int", "lo": 0, "hi": 1} for i in range(n)]
    cons = [["<=", ["+", *[["*", w[i], f"x{i}"] for i in range(n)]], cap]]
    query = {"kind": "optimize", "sense": "maximize", "objective": ["+", *[["*", val[i], f"x{i}"] for i in range(n)]]}
    return _problem(f"knapsack_optimization-{n}-{seed}", v, cons, query), {"objective": opt}


GENERATORS = {"pigeonhole": pigeonhole, "schedule": schedule, "equalities": equalities,
              "knapsack_feasibility": knapsack_feasibility, "knapsack_optimization": knapsack_optimization}


def build() -> dict:
    items = []
    for family, sizes in SIZES.items():
        for n in sizes:
            for partition, seeds in (("dev", DEV_SEEDS), ("heldout", HELDOUT_SEEDS)):
                for seed in seeds:
                    problem, truth = GENERATORS[family](n, seed)
                    items.append({"item_id": problem["problem_id"], "family": family, "size": n, "seed": seed,
                                  "partition": partition, "problem": problem, "truth": truth})
    return {"schema": "greg-learned-routing-suite/1", "budget_s": BUDGET_S, "items": items}


# ------------------------------------------------------------------ execution
class FixedOrder:
    """Reference arm: a fixed engine order over whatever is eligible (never adds an engine)."""
    def __init__(self, order):
        self.order = order

    def reorder(self, keys, geometry, **_):
        return [k for k in self.order if k in keys] + [k for k in keys if k not in self.order]


def score(item, receipt) -> str:
    answer = receipt["output"].get("answer") or {}
    truth = item["truth"]
    if receipt["output"]["state"] in ("CONTESTED",) or not isinstance(answer, dict):
        return "no_decision"
    if "objective" in truth:
        if answer.get("optimal") is not True:
            return "no_decision"
        return "correct" if answer.get("objective") == truth["objective"] else "wrong"
    if answer.get("feasible") is None:
        return "no_decision"
    return "correct" if answer["feasible"] == truth["feasible"] else "wrong"


def execute(problem, *, memory=None, withhold=None) -> tuple[dict, float]:
    registry = seed_registry()
    if withhold:
        registry.withhold(withhold, "evaluation: founder pin of the other engine")
    cortex = Cortex(registry, clock=lambda: "2026-10-07T00:00:00Z", memory=memory)
    started = time.perf_counter()
    receipt = cortex.run(problem)
    return receipt, time.perf_counter() - started


def train(items) -> tuple[CompetenceLedger, list]:
    from greg.cognition.learned_routing import PROVENANCE
    ledger, log = CompetenceLedger(), []
    for item in items:
        for lead, other in ((FORMAL, CPSAT), (CPSAT, FORMAL)):
            receipt, seconds = execute(item["problem"], withhold=other)
            if receipt["route"]["selected"] != [lead]:
                log.append({"item_id": item["item_id"], "lead": lead, "settled": None, "why": "engine not eligible"})
                continue
            result = score(item, receipt)
            status = "verified_success" if result == "correct" else "observed_failure"
            role = "final_answer" if result != "no_decision" else "resource_consumption"
            method, _, version = lead.partition("@")
            ledger.settle(receipt=receipt, method=method, method_version=version, outcome_status=status,
                          provenance={**PROVENANCE, "basis": "ground truth of the generated item"},
                          attribution=[{"method": method, "role": role, "uncertainty": "low"}])
            log.append({"item_id": item["item_id"], "lead": lead, "result": result, "settled": status,
                        "state": receipt["output"]["state"], "seconds": round(seconds, 3),
                        "geometry": receipt["geometry"]["epistemic_class"]})
    return ledger, log


def sign_test(wins: int, losses: int) -> float:
    n = wins + losses
    if n == 0:
        return 1.0
    return sum(math.comb(n, k) for k in range(wins, n + 1)) / 2 ** n


def verdict(rows) -> dict:
    s = [r["arms"]["static"]["result"] for r in rows]
    learned = [r["arms"]["learned"]["result"] for r in rows]
    counts = {arm: {k: sum(1 for r in rows if r["arms"][arm]["result"] == k)
                    for k in ("correct", "wrong", "no_decision")} for arm in ARMS}
    wins = sum(1 for a, b in zip(learned, s) if a == "correct" and b != "correct")
    losses = sum(1 for a, b in zip(learned, s) if b == "correct" and a != "correct")
    p = sign_test(wins, losses)
    if counts["learned"]["wrong"] > counts["static"]["wrong"] or counts["learned"]["correct"] < counts["static"]["correct"]:
        v = "REGRESSION"
    elif counts["learned"]["correct"] > counts["static"]["correct"] and p < 0.05:
        v = "GAIN"
    elif counts["learned"]["correct"] == counts["static"]["correct"]:
        v = "NO_GAIN"
    else:
        v = "INCONCLUSIVE"
    latency = {arm: round(statistics.median(r["arms"][arm]["seconds"] for r in rows), 3) for arm in ARMS}
    return {"verdict": v, "counts": counts, "learned_wins": wins, "learned_losses": losses,
            "sign_test_p_one_sided": round(p, 6), "median_seconds": latency, "rule": VERDICT_RULE}


# ------------------------------------------------------------------ freeze
def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def inputs() -> dict:
    return {"suite": _sha(SUITE), "code": {p: _sha(ROOT / p) for p in FROZEN_CODE}, "budget_s": BUDGET_S,
            "arms": list(ARMS), "dev_seeds": list(DEV_SEEDS), "heldout_seeds": list(HELDOUT_SEEDS),
            "verdict_rule": VERDICT_RULE}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true", help="write suite.json (refuses to overwrite)")
    ap.add_argument("--freeze", action="store_true", help="write the freeze manifest (refuses to overwrite)")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    if args.build:
        if SUITE.exists():
            raise SystemExit("refusing to overwrite the suite; create a new version")
        SUITE.write_text(json.dumps(build(), indent=1) + "\n")
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
    items = json.loads(SUITE.read_text())["items"]
    dev = [i for i in items if i["partition"] == "dev"]
    heldout = [i for i in items if i["partition"] == "heldout"]
    ledger, training = train(dev)
    memories = {"static": None, "learned": ledger, "z3_first": FixedOrder([FORMAL, CPSAT]),
                "cpsat_first": FixedOrder([CPSAT, FORMAL])}
    rows = []
    for index, item in enumerate(heldout):
        arms = ARMS[index % len(ARMS):] + ARMS[:index % len(ARMS)]
        row = {k: item[k] for k in ("item_id", "family", "size", "seed")} | {"arms": {}}
        for arm in arms:
            receipt, seconds = execute(item["problem"], memory=memories[arm])
            row["arms"][arm] = {"result": score(item, receipt), "state": receipt["output"]["state"],
                                "order": receipt["route"]["formal_plan"]["order"],
                                "policy_order": receipt["route"]["formal_plan"]["policy_order"],
                                "seconds": round(seconds, 3), "receipt_id": receipt["receipt_id"]}
        rows.append(row)
    geometries = sorted({t["geometry"] for t in training if t.get("geometry")})
    estimates = [ledger.estimate(k.split("@")[0], k.split("@")[1], g) for g in geometries for k in (FORMAL, CPSAT)]
    learned_orders = {g: ledger.reorder([FORMAL, CPSAT], type("G", (), {"epistemic_class": g})) for g in geometries}
    report = {"schema": "greg-learned-routing-results/1", "manifest_sha256": _sha(MANIFEST),
              "finished_at": datetime.now(timezone.utc).isoformat(),
              "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "platform": platform.platform(), "python": sys.version.split()[0],
              "training": {"runs": training, "ledger_head": ledger.head, "records": len(ledger.records()),
                           "estimates": estimates, "learned_order_by_geometry": learned_orders},
              "heldout": rows, "summary": verdict(rows),
              "limits": ["ground truth stands in for the signed check and separate-process appraisal",
                         "competence is pooled per epistemic class, as the frozen 0.2.1 ledger keys it; "
                         "families inside one class share a single learned order",
                         "the ledger learns decided/undecided and correct/wrong, not latency",
                         "one container, one CPU budget; timing-dependent results may differ on other hardware"]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({"summary": report["summary"], "learned_order_by_geometry": learned_orders}, indent=1))


if __name__ == "__main__":
    main()
