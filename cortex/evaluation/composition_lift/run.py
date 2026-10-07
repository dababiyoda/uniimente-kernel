"""P6 cognitive composition lift: the first Verified Polyintelligence Lift (VPL) measurement.

Question (INTENT-20261007-VERIFIED-POLYINTELLIGENCE-LIFT). On held-out problems whose answer needs
two intelligences with complementary partial competence, does geometry-routed composition
(``greg/cognition/composition.py``) decide more problems correctly than the strongest single
intelligence, without more false answers, inside the latency budget?

Families (generated; ground truth independent of every organ under test):

* F1 ``estimate_then_optimize`` - staff a week to cover the 95th percentile of demand at least cost.
  Demand is a product of lognormal factors stated as 90% intervals (the estimation organ's own
  semantics), so the true quantile is analytic; the true least-cost plan is found by enumeration.
  correct: capacity >= true p95 and cost <= 1.10 x true optimum. wrong: capacity < true p95 (a plan
  that claims a coverage it lacks). suboptimal: covers but costs more than 1.10 x optimum.
* F2 ``identify_then_optimize`` - fund two programs under a budget. Each program's outcome data are
  confounded (the generator knows the true effect); the true optimal allocation is enumerated on the
  true effects. correct: the chosen allocation's true value equals the true optimum. wrong: lower.

Arms. Every arm really executes through ``greg.cognition.cortex.reason`` (bounded isolated worker):

* constituents alone - F1: ``estimate_alone`` (no plan), ``optimize_at_point`` (optimiser on the
  product of interval midpoints), ``optimize_at_worst_case`` (product of interval highs);
  F2: ``identify_alone`` (no allocation), ``optimize_on_association`` (optimiser on the raw
  difference in means). The best constituent is the one with the most correct held-out decisions.
* ``static_composition`` - one fixed recipe for every problem: the recipe with the most correct
  development decisions across both families.
* ``routed_composition`` - the geometry router chooses the recipe.

Verdict (frozen): a family counts toward VPL when routed composition decides more held-out items
correctly than the best constituent, adds no wrong answer, the one-sided exact sign test over
discordant items gives p < 0.05, and its median latency is inside the declared 60 s chain budget.
Limit stated up front: these families are constructed to need composition. A VPL > 0 here shows the
composition machinery delivers the complementary answer faithfully against real constituents; it is
not evidence that naturally occurring tasks need composition.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
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

SUITE = HERE / "suite.json"
MANIFEST = HERE / "freeze-v1.json"
Z95 = 1.6448536269514722
DEV_SEEDS, HELDOUT_SEEDS = range(1, 9), range(9, 25)
CHAIN_BUDGET_S = 60.0
DECL = {"consequence_class": "read_only", "reversibility": "reversible"}
FROZEN_CODE = ["cortex/evaluation/composition_lift/run.py", "greg/cognition/composition.py",
               "greg/cognition/cortex.py", "greg/cognition/bridge.py", "cortex/routing.py",
               "cortex/organs/estimation.py", "cortex/organs/evidence_causal.py", "cortex/organs/cpsat.py",
               "cortex/organs/formal.py", "cortex/evaluation/generators.py", "requirements-cortex.txt"]
VERDICT_RULE = ("family lift: routed correct > best constituent correct, routed wrong <= best constituent wrong, "
                "one-sided exact sign test p < 0.05, routed median latency <= 60 s; VPL = families with lift")


# ------------------------------------------------------------------ F1
def f1(seed: int) -> dict:
    r = random.Random(1000 + seed)
    jobs_lo = r.randint(10, 40)
    hours_lo = round(r.uniform(0.5, 3.0), 2)
    factors = [("jobs", "1", jobs_lo, round(jobs_lo * r.uniform(1.2, 2.0), 2)),
               ("hours_per_job", "h", hours_lo, round(hours_lo * r.uniform(1.2, 2.5), 2)),
               ("rework", "1", 1.0, round(r.uniform(1.1, 1.6), 2))]
    full, part = r.randint(900, 1100), r.randint(500, 620)
    mu = sum((math.log(lo) + math.log(hi)) / 2 for _, _, lo, hi in factors)
    sd = math.sqrt(sum(((math.log(hi) - math.log(lo)) / (2 * Z95)) ** 2 for _, _, lo, hi in factors))
    p95, median = math.exp(mu + Z95 * sd), math.exp(mu)
    worst = math.prod(hi for *_, hi in factors)
    f_hi, p_hi = 60, 120
    def plan_cost(need):
        best = None
        for f in range(f_hi + 1):
            p = max(0, math.ceil((need - 40 * f) / 20 - 1e-12))
            if p <= p_hi:
                cost = full * f + part * p
                best = cost if best is None or cost < best else best
        return best
    est = {"target": {"name": "weekly_hours", "unit": "h"},
           "variables": [{"name": n, "unit": u, "low": lo, "high": hi} for n, u, lo, hi in factors],
           "expression": ["*", *[n for n, *_ in factors]], "dependencies": [], "reference_class": None,
           "seed": seed}
    def model(need):
        return {"requirement": "cover the 95th percentile of weekly demand at least cost",
                "variables": [{"name": "f", "sort": "int", "lo": 0, "hi": f_hi},
                              {"name": "p", "sort": "int", "lo": 0, "hi": p_hi}],
                "obligations": [{"id": "R", "text": "capacity covers the 95th percentile of weekly demand"}],
                "constraints": [{"id": "C1", "covers": ["R"],
                                 "expr": [">=", ["+", ["*", 40, "f"], ["*", 20, "p"]], need]}],
                "query": {"kind": "optimize", "sense": "minimize",
                          "objective": ["+", ["*", full, "f"], ["*", part, "p"]]}}
    return {"item_id": f"F1-{seed}", "family": "F1", "seed": seed,
            "payload": {"estimation_model": est, "formal_template": model({"$param": "estimate.high"})},
            "point_model": model(math.ceil(median)), "worst_model": model(math.ceil(worst)),
            "truth": {"p95": p95, "optimal_cost": plan_cost(p95), "costs": [full, part]}}


# ------------------------------------------------------------------ F2
def f2(seed: int) -> dict:
    from cortex.evaluation.build_suites import ev
    from cortex.evaluation.generators import confounded
    r = random.Random(2000 + seed)
    progs = {}
    for name in ("a", "b"):
        progs[name] = {"effect": round(r.uniform(0.5, 3.0), 2), "confounding": round(r.uniform(0.0, 3.0), 2),
                       "cost": r.randint(2, 6)}
    budget = r.randint(20, 40)
    def study(name, i):
        p = progs[name]
        rows = confounded(n=400, effect=p["effect"], confounding=p["confounding"], seed=seed * 10 + i)
        spec = {"estimand": "average treatment effect of t on y", "treatment": "t", "outcome": "y",
                "adjustment_set": ["z"],
                "identification_assumptions": ["z blocks every backdoor path from t to y",
                                               "no unmeasured confounding", "positivity within strata of z"],
                "identification_basis": {"origin": "declared_by_domain_expert", "ref": "program design"},
                "method": "stratified", "limitations": ["observational"], "data": rows}
        return {"claim": {"id": f"C-{name}", "type": "intervention", "statement": f"program {name} raises outcome"},
                "causal_spec": spec, "as_of": "2026-10-07", "evidence": [ev("E1", "supports", kind="observational")]}
    studies = {name: study(name, i) for i, name in enumerate(progs)}
    def naive(name):
        rows = studies[name]["causal_spec"]["data"]
        t1 = [x["y"] for x in rows if x["t"] == 1]
        t0 = [x["y"] for x in rows if x["t"] == 0]
        return statistics.fmean(t1) - statistics.fmean(t0)
    def model(coef):
        return {"requirement": "fund programs within budget for the largest outcome gain",
                "variables": [{"name": n, "sort": "int", "lo": 0, "hi": 10} for n in progs],
                "obligations": [{"id": "B", "text": "spend within budget"}],
                "constraints": [{"id": "C1", "covers": ["B"],
                                 "expr": ["<=", ["+", *[["*", progs[n]["cost"], n] for n in progs]], budget]}],
                "query": {"kind": "optimize", "sense": "maximize",
                          "objective": ["+", *[["*", coef(n), n] for n in progs]]}}
    best = max(progs["a"]["effect"] * a + progs["b"]["effect"] * b
               for a in range(11) for b in range(11) if progs["a"]["cost"] * a + progs["b"]["cost"] * b <= budget)
    return {"item_id": f"F2-{seed}", "family": "F2", "seed": seed,
            "payload": {"causal_studies": studies,
                        "formal_template": model(lambda n: {"$param": f"effect.{n}", "scale": 100, "round": "nearest"})},
            "association_model": model(lambda n: int(round(naive(n) * 100))),
            "truth": {"effects": {n: p["effect"] for n, p in progs.items()}, "optimal_value": best,
                      "costs": {n: p["cost"] for n, p in progs.items()}, "budget": budget}}


def build() -> dict:
    items = []
    for gen in (f1, f2):
        for partition, seeds in (("dev", DEV_SEEDS), ("heldout", HELDOUT_SEEDS)):
            for seed in seeds:
                items.append({**gen(seed), "partition": partition})
    return {"schema": "greg-composition-lift-suite/1", "items": items}


# ------------------------------------------------------------------ execution and scoring
def _registry():
    from greg.cognition.cortex import registry_view
    return registry_view()


def _single(payload, pid):
    from greg.cognition.cortex import reason
    started = time.perf_counter()
    r = reason({"problem_id": pid, "problem": {"question": "generated", "payload": {**payload, "declared": DECL}}},
               registry=_registry())
    answer = (r.get("output") or {}).get("answer") if r["abstention_state"] == "NONE" else None
    return answer, time.perf_counter() - started


def _chain(item, recipe=None):
    from greg.cognition.cortex import reason
    chain = {"question": "generated", "payload": item["payload"], "max_latency_s": CHAIN_BUDGET_S}
    if recipe:
        chain["recipe"] = recipe
    started = time.perf_counter()
    r = reason({"problem_id": item["item_id"], "chain": chain}, registry=_registry())
    return (r["answer"] if r["state"] == "ANSWERED" else None), time.perf_counter() - started, r["state"]


def score(item, answer) -> str:
    if not isinstance(answer, dict) or answer.get("optimal") is not True or "model" not in answer:
        return "no_decision"
    t = item["truth"]
    if item["family"] == "F1":
        f, p = answer["model"]["f"], answer["model"]["p"]
        if 40 * f + 20 * p < t["p95"] - 1e-9:
            return "wrong"
        cost = t["costs"][0] * f + t["costs"][1] * p
        return "correct" if cost <= 1.10 * t["optimal_cost"] + 1e-9 else "suboptimal"
    value = sum(t["effects"][n] * answer["model"][n] for n in t["effects"])
    return "correct" if value >= t["optimal_value"] - 1e-9 else "wrong"


CONSTITUENTS = {"F1": ("estimate_alone", "optimize_at_point", "optimize_at_worst_case"),
                "F2": ("identify_alone", "optimize_on_association")}


def run_arm(item, arm, static_recipe=None):
    if arm == "routed_composition":
        answer, seconds, state = _chain(item)
    elif arm == "static_composition":
        answer, seconds, state = _chain(item, static_recipe)
    elif arm == "estimate_alone":
        answer, seconds = _single({"estimation_model": item["payload"]["estimation_model"]}, item["item_id"])
        state = "no plan from an estimate alone"
        answer = None if not (isinstance(answer, dict) and "model" in answer) else answer
    elif arm == "identify_alone":
        start = time.perf_counter()
        for name, study in sorted(item["payload"]["causal_studies"].items()):
            _single(study, f"{item['item_id']}-{name}")
        answer, seconds, state = None, time.perf_counter() - start, "no allocation from effects alone"
    else:
        key = {"optimize_at_point": "point_model", "optimize_at_worst_case": "worst_model",
               "optimize_on_association": "association_model"}[arm]
        answer, seconds = _single({"formal_model": item[key]}, item["item_id"])
        state = "single optimiser"
    return {"result": score(item, answer), "seconds": round(seconds, 3), "state": state,
            "plan": (answer or {}).get("model")}


def sign_test(wins: int, losses: int) -> float:
    n = wins + losses
    return 1.0 if n == 0 else sum(math.comb(n, k) for k in range(wins, n + 1)) / 2 ** n


def summarize(rows) -> dict:
    out, vpl = {}, 0
    for family in ("F1", "F2"):
        fr = [r for r in rows if r["family"] == family]
        arms = list(fr[0]["arms"])
        counts = {a: {k: sum(1 for r in fr if r["arms"][a]["result"] == k)
                      for k in ("correct", "wrong", "suboptimal", "no_decision")} for a in arms}
        best = max(CONSTITUENTS[family], key=lambda a: (counts[a]["correct"], -counts[a]["wrong"]))
        wins = sum(1 for r in fr if r["arms"]["routed_composition"]["result"] == "correct"
                   and r["arms"][best]["result"] != "correct")
        losses = sum(1 for r in fr if r["arms"][best]["result"] == "correct"
                     and r["arms"]["routed_composition"]["result"] != "correct")
        p = sign_test(wins, losses)
        median = statistics.median(r["arms"]["routed_composition"]["seconds"] for r in fr)
        lift = (counts["routed_composition"]["correct"] > counts[best]["correct"]
                and counts["routed_composition"]["wrong"] <= counts[best]["wrong"] and p < 0.05
                and median <= CHAIN_BUDGET_S)
        vpl += int(lift)
        out[family] = {"n": len(fr), "counts": counts, "best_constituent": best, "routed_wins": wins,
                       "routed_losses": losses, "sign_test_p_one_sided": round(p, 6),
                       "median_seconds": {a: round(statistics.median(r["arms"][a]["seconds"] for r in fr), 3)
                                          for a in arms}, "lift": lift}
    static = sum(1 for r in rows if r["arms"]["static_composition"]["result"] == "correct")
    routed = sum(1 for r in rows if r["arms"]["routed_composition"]["result"] == "correct")
    out["routing_over_static_composition"] = {"static_correct": static, "routed_correct": routed, "n": len(rows)}
    out["VPL"] = {"families_with_lift": vpl, "families": 2, "rule": VERDICT_RULE}
    return out


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def inputs() -> dict:
    return {"suite": _sha(SUITE), "code": {p: _sha(ROOT / p) for p in FROZEN_CODE}, "verdict_rule": VERDICT_RULE,
            "chain_budget_s": CHAIN_BUDGET_S, "dev_seeds": list(DEV_SEEDS), "heldout_seeds": list(HELDOUT_SEEDS)}


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
    items = json.loads(SUITE.read_text())["items"]
    dev = [i for i in items if i["partition"] == "dev"]
    heldout = [i for i in items if i["partition"] == "heldout"]
    # Development is used for one choice only: which single fixed recipe is the static composition.
    from greg.cognition.composition import RECIPES
    dev_correct = {name: sum(1 for item in dev if score(item, _chain(item, name)[0]) == "correct")
                   for name in RECIPES}
    static_recipe = max(sorted(dev_correct), key=lambda n: dev_correct[n])
    rows = []
    for index, item in enumerate(heldout):
        arms = list(CONSTITUENTS[item["family"]]) + ["static_composition", "routed_composition"]
        arms = arms[index % len(arms):] + arms[:index % len(arms)]
        row = {"item_id": item["item_id"], "family": item["family"], "truth": item["truth"], "arms": {}}
        for arm in arms:
            row["arms"][arm] = run_arm(item, arm, static_recipe)
        row["arms"] = {a: row["arms"][a] for a in list(CONSTITUENTS[item["family"]]) +
                       ["static_composition", "routed_composition"]}
        rows.append(row)
    report = {"schema": "greg-composition-lift-results/1", "manifest_sha256": _sha(MANIFEST),
              "finished_at": datetime.now(timezone.utc).isoformat(),
              "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "platform": platform.platform(), "python": sys.version.split()[0],
              "development": {"recipe_correct": dev_correct, "static_recipe": static_recipe},
              "heldout": rows, "summary": summarize(rows),
              "limits": ["families are constructed to need composition; VPL here tests the machinery, not "
                         "whether natural tasks need composition",
                         "F1 truth assumes the stated intervals are calibrated lognormal 90% intervals",
                         "one container, one CPU budget"]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({"development": report["development"], "summary": report["summary"]}, indent=1))


if __name__ == "__main__":
    main()
