"""P6 v3: a chain no recipe lists, derived by dataflow, against the strongest single and fixed compositions.

Question. ``greg/cognition/composition.py`` now derives a chain from typed stage signatures when no single
recipe fits (``derive``). On held-out problems whose formal template needs BOTH an estimate and identified
causal effects, does the derived chain (estimate + identify -> optimize) decide more problems correctly
than (a) the strongest single intelligence and (b) the best fixed two-stage recipe?

Family F3 ``plan programs within uncertain capacity`` (generated; ground truth independent of every organ):
two programs with confounded observational studies (F2's generator: the true effect is known to the
generator) and a volunteer-hours capacity that is a product of lognormal factors stated as 90 % intervals
(F1's semantics, so the true 5th percentile is analytic). Maximise the true outcome within a money budget
and within capacity that is available with 95 % probability. Scoring, declared before the run:

* no_decision: no certified optimal plan;
* wrong: the plan's hours exceed the true 5th percentile of capacity (it commits hours it lacks);
* correct: within capacity and true value >= 0.95 x the true optimum (optimum enumerated on the true
  effects and floor(true p05));
* suboptimal: within capacity but below 0.95 x the optimum.

Arms (all executed through ``greg.cognition.cortex.reason``):
* singles - ``estimate_alone`` and ``identify_alone`` (no plan) and ``optimize_naive_point`` (the optimiser
  on raw difference-in-means effects and the median capacity);
* fixed recipes - ``recipe_estimate`` (estimate_then_optimize; effects baked in from raw association) and
  ``recipe_identify`` (identify_then_optimize; capacity baked in at the median);
* ``routed`` - no recipe pinned; the payload carries both inputs, so ``route`` finds no single recipe and
  ``derive`` builds estimate + identify -> optimize.

Verdict (frozen, v1's rule applied twice): VPL lift when routed beats the best SINGLE arm (more correct,
no added wrong, one-sided sign test p < 0.05, median latency <= 60 s); "derivation lift" when routed beats
the best FIXED RECIPE by the same rule. Held-out seeds 101-148 (48 items), never generated before.
Limit: F3 is constructed to need both stages; it shows the derived chain delivers, not that natural tasks
need it.
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
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from cortex.evaluation.composition_lift import run as V1  # noqa: E402

MANIFEST = HERE / "freeze-v3.json"
SEEDS = range(101, 149)
FROZEN_CODE = ["cortex/evaluation/composition_lift/run_v3.py", "cortex/evaluation/composition_lift/run.py",
               "greg/cognition/composition.py", "greg/cognition/cortex.py", "greg/cognition/bridge.py",
               "cortex/routing.py", "cortex/genome.py", "cortex/organs/estimation.py", "cortex/organs/formal.py",
               "cortex/organs/cpsat.py", "cortex/organs/evidence_causal.py", "cortex/evaluation/generators.py"]
SINGLES = ("estimate_alone", "identify_alone", "optimize_naive_point")
RECIPES = ("recipe_estimate", "recipe_identify")
ARMS = SINGLES + RECIPES + ("routed",)


def f3(seed: int) -> dict:
    from cortex.evaluation.build_suites import ev
    from cortex.evaluation.generators import confounded
    r = random.Random(3000 + seed)
    progs = {n: {"effect": round(r.uniform(0.5, 3.0), 2), "confounding": round(r.uniform(0.0, 3.0), 2),
                 "cost": r.randint(2, 6), "hours": r.randint(3, 8)} for n in ("a", "b")}
    budget = r.randint(30, 60)
    vol_lo, hpv_lo = r.randint(4, 12), round(r.uniform(2.0, 6.0), 2)
    factors = [("volunteers", "1", vol_lo, round(vol_lo * r.uniform(1.3, 2.0), 2)),
               ("hours_per_volunteer", "h", hpv_lo, round(hpv_lo * r.uniform(1.2, 2.0), 2)),
               ("availability", "1", round(r.uniform(0.5, 0.7), 2), round(r.uniform(0.8, 1.0), 2))]
    mu = sum((math.log(lo) + math.log(hi)) / 2 for _, _, lo, hi in factors)
    sd = math.sqrt(sum(((math.log(hi) - math.log(lo)) / (2 * V1.Z95)) ** 2 for _, _, lo, hi in factors))
    p05, median = math.exp(mu - V1.Z95 * sd), math.exp(mu)

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
                "causal_spec": spec, "as_of": "2026-10-14", "evidence": [ev("E1", "supports", kind="observational")]}
    studies = {name: study(name, i) for i, name in enumerate(progs)}

    def naive(name):
        rows = studies[name]["causal_spec"]["data"]
        return statistics.fmean(x["y"] for x in rows if x["t"] == 1) - statistics.fmean(x["y"] for x in rows if x["t"] == 0)

    def model(coef, capacity):
        return {"requirement": "fund programs within budget and within capacity available with 95% probability",
                "variables": [{"name": n, "sort": "int", "lo": 0, "hi": 10} for n in progs],
                "obligations": [{"id": "B", "text": "spend within budget"},
                                {"id": "H", "text": "commit only hours available with 95% probability"}],
                "constraints": [{"id": "C1", "covers": ["B"],
                                 "expr": ["<=", ["+", *[["*", progs[n]["cost"], n] for n in progs]], budget]},
                                {"id": "C2", "covers": ["H"],
                                 "expr": ["<=", ["+", *[["*", progs[n]["hours"], n] for n in progs]], capacity]}],
                "query": {"kind": "optimize", "sense": "maximize",
                          "objective": ["+", *[["*", coef(n), n] for n in progs]]}}
    est = {"target": {"name": "available_hours", "unit": "h"},
           "variables": [{"name": n, "unit": u, "low": lo, "high": hi} for n, u, lo, hi in factors],
           "expression": ["*", *[n for n, *_ in factors]], "dependencies": [], "reference_class": None, "seed": seed}
    identified = lambda n: {"$param": f"effect.{n}", "scale": 100, "round": "nearest"}  # noqa: E731
    associated = lambda n: int(round(naive(n) * 100))  # noqa: E731
    cap = math.floor(p05 + 1e-9)
    best = max(progs["a"]["effect"] * a + progs["b"]["effect"] * b for a in range(11) for b in range(11)
               if progs["a"]["cost"] * a + progs["b"]["cost"] * b <= budget
               and progs["a"]["hours"] * a + progs["b"]["hours"] * b <= cap)
    return {"item_id": f"F3-{seed}", "family": "F3", "seed": seed,
            "payload": {"estimation_model": est, "causal_studies": studies,
                        "formal_template": model(identified, {"$param": "estimate.low", "round": "floor"})},
            "recipe_estimate_payload": {"estimation_model": est,
                                        "formal_template": model(associated, {"$param": "estimate.low", "round": "floor"})},
            "recipe_identify_payload": {"causal_studies": studies,
                                        "formal_template": model(identified, math.floor(median))},
            "naive_point_model": model(associated, math.floor(median)),
            "truth": {"effects": {n: p["effect"] for n, p in progs.items()},
                      "hours": {n: p["hours"] for n, p in progs.items()}, "p05": p05, "median": median,
                      "optimal_value": best}}


def score(item, answer) -> str:
    if not isinstance(answer, dict) or answer.get("optimal") is not True or "model" not in answer:
        return "no_decision"
    t, plan = item["truth"], answer["model"]
    if sum(t["hours"][n] * plan[n] for n in t["hours"]) > t["p05"] + 1e-9:
        return "wrong"
    value = sum(t["effects"][n] * plan[n] for n in t["effects"])
    return "correct" if value >= 0.95 * t["optimal_value"] - 1e-9 else "suboptimal"


def _chain(item_id, payload, recipe=None):
    from greg.cognition.cortex import reason
    chain = {"question": "generated", "payload": payload, "max_latency_s": V1.CHAIN_BUDGET_S}
    if recipe:
        chain["recipe"] = recipe
    started = time.perf_counter()
    r = reason({"problem_id": item_id, "chain": chain}, registry=V1._registry())
    return (r["answer"] if r["state"] == "ANSWERED" else None), time.perf_counter() - started, r["state"], r.get("chain")


def run_arm(item, arm):
    chain = None
    if arm == "routed":
        answer, seconds, state, chain = _chain(item["item_id"], item["payload"])
    elif arm == "recipe_estimate":
        answer, seconds, state, chain = _chain(item["item_id"], item["recipe_estimate_payload"], "estimate_then_optimize")
    elif arm == "recipe_identify":
        answer, seconds, state, chain = _chain(item["item_id"], item["recipe_identify_payload"], "identify_then_optimize")
    elif arm == "estimate_alone":
        answer, seconds = V1._single({"estimation_model": item["payload"]["estimation_model"]}, item["item_id"])
        answer, state = (answer if isinstance(answer, dict) and "model" in answer else None), "no plan from an estimate"
    elif arm == "identify_alone":
        start = time.perf_counter()
        for name, study in sorted(item["payload"]["causal_studies"].items()):
            V1._single(study, f"{item['item_id']}-{name}")
        answer, seconds, state = None, time.perf_counter() - start, "no plan from effects alone"
    else:
        answer, seconds = V1._single({"formal_model": item["naive_point_model"]}, item["item_id"])
        state = "single optimiser"
    return {"result": score(item, answer), "seconds": round(seconds, 3), "state": state, "chain": chain,
            "plan": (answer or {}).get("model")}


def verdict(rows, against) -> dict:
    counts = {a: {k: sum(1 for r in rows if r["arms"][a]["result"] == k)
                  for k in ("correct", "wrong", "suboptimal", "no_decision")} for a in ARMS}
    best = max(against, key=lambda a: (counts[a]["correct"], -counts[a]["wrong"]))
    wins = sum(1 for r in rows if r["arms"]["routed"]["result"] == "correct" and r["arms"][best]["result"] != "correct")
    losses = sum(1 for r in rows if r["arms"][best]["result"] == "correct" and r["arms"]["routed"]["result"] != "correct")
    p = V1.sign_test(wins, losses)
    median = statistics.median(r["arms"]["routed"]["seconds"] for r in rows)
    return {"best": best, "wins": wins, "losses": losses, "sign_test_p_one_sided": round(p, 6),
            "lift": counts["routed"]["correct"] > counts[best]["correct"]
            and counts["routed"]["wrong"] <= counts[best]["wrong"] and p < 0.05 and median <= V1.CHAIN_BUDGET_S,
            "counts": counts}


def inputs() -> dict:
    return {"code": {p: V1._sha(ROOT / p) for p in FROZEN_CODE}, "seeds": [SEEDS.start, SEEDS.stop - 1],
            "arms": list(ARMS), "verdict_rule": V1.VERDICT_RULE}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    if args.freeze:
        if MANIFEST.exists():
            raise SystemExit("refusing to overwrite an existing freeze; create a new version")
        MANIFEST.write_text(json.dumps({"frozen_at": datetime.now(timezone.utc).isoformat(), "inputs": inputs()},
                                       indent=2) + "\n")
        return
    if json.loads(MANIFEST.read_text())["inputs"] != inputs():
        raise SystemExit("FROZEN_INPUT_CHANGED: results cannot be reported")
    rows = []
    for seed in SEEDS:
        item = f3(seed)
        rows.append({"item_id": item["item_id"], "family": "F3",
                     "arms": {arm: run_arm(item, arm) for arm in ARMS}})
    summary = {"vs_best_single": verdict(rows, SINGLES), "vs_best_fixed_recipe": verdict(rows, RECIPES),
               "median_seconds": {a: round(statistics.median(r["arms"][a]["seconds"] for r in rows), 3) for a in ARMS},
               "routed_chains": sorted({"+".join(r["arms"]["routed"]["chain"] or []) for r in rows})}
    report = {"schema": "greg-composition-lift-results/3", "manifest_sha256": V1._sha(MANIFEST),
              "finished_at": datetime.now(timezone.utc).isoformat(),
              "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "platform": platform.platform(), "python": sys.version.split()[0], "heldout": rows,
              "summary": summary,
              "limits": ["F3 is constructed to need both stages; not a natural task distribution",
                         "capacity truth assumes the generator's lognormal semantics, which the estimation organ shares"]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
