"""Frozen comparison: learned cortex routing (the shadow's ledger) against the fixed policy (P4 exit test).

Freeze first, then run; the runner refuses a suite whose digest differs from its freeze.

Design (declared in the freeze, before any result):
- Problems: seeded random one-machine schedules (2-4 jobs, durations 1-5, shift 6-14, optional
  precedence), half feasibility and half optimization (minimize the sum of start times). Exact
  truth by brute-force enumeration (cortex.evaluation.build_suites.brute), never by an engine.
- Both formal engines run pinned on every problem, so either routing order's first engine has a
  measured outcome: the comparison is an exact counterfactual replay, not an estimate.
- Learning: a fresh CompetenceLedger (cortex/memory.py) settles every development-split outcome of
  both engines (founder-pinned exploration, internally observed). The held-out split is never
  settled.
- Policies: static = the routing policy's own order; learned = ledger.reorder(static order).
- Loss per item: 1.0 if the first engine's answer is wrong (feasibility verdict, or optimum value),
  else its measured latency in seconds divided by 5 (capped at 1). Hard failures (an authority
  claim, a wrong answer stated as optimal) are counted separately.
- Gain: mean over held-out items of (static loss - learned loss), with a paired 95% interval. The
  predeclared verdict is GAIN only if relative gain >= 10% and the interval's lower bound > 0;
  NO_GAIN if the interval lies within +-0.01 of zero or the policies never differ; else
  INCONCLUSIVE.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from pathlib import Path
import random
from types import SimpleNamespace

from cortex.evaluation.build_suites import brute, schedule
from cortex.memory import CompetenceLedger

from .contracts import digest

ROOT = Path(__file__).resolve().parents[2]
ENGINES = ("cognition.cortex.formal.z3", "cognition.cortex.optimization.cpsat")
KEY_OF = {"cognition.cortex.formal.z3": "cortex.formal.z3@0.2.0",
          "cognition.cortex.optimization.cpsat": "cortex.optimization.cpsat@0.2.0"}
DECLARATION = {
    "generator": "greg.cognition.routing_eval/0.1", "split": {"development": 30, "heldout": 60},
    "loss": "1.0 if wrong, else min(latency_s, 5) / 5; hard failures counted separately",
    "learning": "CompetenceLedger settles both engines' development outcomes (internally_observed, weight 0.6)",
    "verdict": "GAIN if relative gain >= 0.10 and paired 95% lower bound > 0; NO_GAIN if the interval lies "
               "within +-0.01 of zero or the policies never differ; else INCONCLUSIVE",
}


def _item(rng: random.Random, index: int) -> dict:
    count = rng.randint(2, 4)
    names = "ABCD"[:count]
    jobs = [(n, rng.randint(1, 5)) for n in names]
    shift = rng.randint(6, 14)
    precedence = [(names[0], names[1])] if rng.random() < 0.4 else []
    optimize = rng.random() < 0.5
    query = ({"kind": "optimize", "sense": "minimize", "objective": ["+", *[f"s_{n}" for n in names]]}
             if optimize else None)
    model, feasible, _ = schedule(jobs, shift, precedence, query=query)
    best = _optimum(jobs, shift, precedence) if optimize and feasible else None
    return {"id": f"item-{index:03d}", "kind": "optimize" if optimize else "feasibility",
            "truth": {"feasible": feasible, "objective": best},
            "params": {"problem_id": f"routing-eval:{index:03d}", "problem": {
                "question": "Schedule the jobs", "payload": {"formal_model": model, "declared": {
                    "consequence_class": "internal_write", "reversibility": "reversible"}}}}}


def _optimum(jobs, shift, precedence):
    import itertools
    names, dur = [j for j, _ in jobs], dict(jobs)
    best = None
    for starts in itertools.product(range(shift + 1), repeat=len(names)):
        s = dict(zip(names, starts))
        if any(s[j] + dur[j] > shift for j in names):
            continue
        if any(not (s[a] + dur[a] <= s[b] or s[b] + dur[b] <= s[a]) for a, b in itertools.combinations(names, 2)):
            continue
        if any(s[b] < s[a] + dur[a] for a, b in precedence):
            continue
        total = sum(starts)
        best = total if best is None else min(best, total)
    return best


def suite(seed: int = 20261014) -> dict:
    rng = random.Random(seed)
    n = DECLARATION["split"]["development"] + DECLARATION["split"]["heldout"]
    items = [_item(rng, i) for i in range(n)]
    dev = DECLARATION["split"]["development"]
    return {"seed": seed, "development": items[:dev], "heldout": items[dev:]}


def freeze(seed: int = 20261014) -> dict:
    s = suite(seed)
    return {"schema": "greg-shadow-vs-static/0.1", "declaration": DECLARATION, "seed": seed,
            "suite_digest": digest(s), "items": {"development": len(s["development"]), "heldout": len(s["heldout"])},
            "frozen_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}


def correct(item: dict, receipt: dict) -> bool:
    answer = (receipt.get("output") or {}).get("answer") or {}
    if receipt.get("abstention_state") != "NONE" or answer.get("feasible") is not item["truth"]["feasible"]:
        return False
    if item["kind"] == "optimize" and item["truth"]["feasible"]:
        return answer.get("objective") == item["truth"]["objective"] and answer.get("optimal") is True
    return True


def loss(item: dict, receipt: dict) -> float:
    return 1.0 if not correct(item, receipt) else min(float(receipt["latency"]), 5.0) / 5.0


def _run_both(items, registry):
    from .cortex import reason
    out = []
    for item in items:
        runs = {engine: reason(item["params"], registry=registry, forced_family=engine) for engine in ENGINES}
        out.append((item, runs))
    return out


def run(frozen: dict, *, registry=None) -> dict:
    from .cortex import registry_view
    s = suite(frozen["seed"])
    if digest(s) != frozen["suite_digest"]:
        raise ValueError("suite does not match its freeze; refusing to run")
    registry = registry or registry_view()
    _run_both(s["development"][:1], registry)                       # one warm-up, discarded
    dev, held = _run_both(s["development"], registry), _run_both(s["heldout"], registry)
    ledger = CompetenceLedger()
    for item, runs in dev:
        for engine, receipt in runs.items():
            cortex = receipt["proof_artifact"]
            method, _, version = KEY_OF[engine].partition("@")
            ledger.settle(receipt=cortex, method=method, method_version=version,
                          outcome_status="verified_success" if correct(item, receipt) else "observed_failure",
                          provenance={"kind": "internal_observation", "validation_status": "internally_observed"},
                          attribution=[{"method": method, "role": "final_answer", "uncertainty": "low"}])
    rows, hard = [], 0
    by_key = {v: k for k, v in KEY_OF.items()}
    for item, runs in held:
        cortex = next(iter(runs.values()))["proof_artifact"]
        static = (cortex["route"].get("formal_plan") or {}).get("policy_order") or list(KEY_OF.values())
        learned = ledger.reorder(list(static), SimpleNamespace(epistemic_class=cortex["geometry"]["epistemic_class"]))
        s_receipt, l_receipt = runs[by_key[static[0]]], runs[by_key[learned[0]]]
        hard += sum(r.get("authority_created") is not False for r in runs.values())
        rows.append({"id": item["id"], "kind": item["kind"], "static_first": static[0], "learned_first": learned[0],
                     "static_loss": loss(item, s_receipt), "learned_loss": loss(item, l_receipt),
                     "engine_loss": {by_key_short: loss(item, runs[e]) for e, by_key_short in
                                     ((e, e.removeprefix("cognition.cortex.")) for e in ENGINES)},
                     "engine_latency": {e.removeprefix("cognition.cortex."): round(runs[e]["latency"], 4) for e in ENGINES}})
    diffs = [r["static_loss"] - r["learned_loss"] for r in rows]
    n = len(diffs)
    mean = sum(diffs) / n
    sd = math.sqrt(sum((d - mean) ** 2 for d in diffs) / (n - 1)) if n > 1 else 0.0
    ci = [mean - 1.96 * sd / math.sqrt(n), mean + 1.96 * sd / math.sqrt(n)]
    static_mean = sum(r["static_loss"] for r in rows) / n
    differ = sum(r["static_first"] != r["learned_first"] for r in rows)
    relative = mean / static_mean if static_mean else 0.0
    if differ and relative >= 0.10 and ci[0] > 0:
        verdict = "GAIN"
    elif not differ or (ci[0] >= -0.01 and ci[1] <= 0.01):
        verdict = "NO_GAIN"
    else:
        verdict = "INCONCLUSIVE"
    oracle = sum(min(r["engine_loss"].values()) for r in rows) / n
    cells = [ledger.estimate(*KEY_OF[e].partition("@")[::2], g) for e in ENGINES
             for g in ("optimization", "constraint_feasibility")]
    return {"schema": frozen["schema"], "freeze_digest": digest(frozen), "suite_digest": frozen["suite_digest"],
            "verdict": verdict, "gain": mean, "ci95": ci, "relative_gain": relative, "n": n,
            "policies_differ_on": differ, "static_mean_loss": static_mean,
            "learned_mean_loss": sum(r["learned_loss"] for r in rows) / n,
            "hindsight_best_engine_mean_loss": oracle, "hard_failures": hard,
            "accuracy": {e.removeprefix("cognition.cortex."): sum(r["engine_loss"][e.removeprefix("cognition.cortex.")] < 1
                                                                  for r in rows) / n for e in ENGINES},
            "ledger_cells": cells, "rows": rows,
            "run_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "claim_limit": "container CPU, one run; latency varies with load; synthetic schedules only"}


if __name__ == "__main__":
    import sys
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "tests" / "evidence" / "greg-shadow-vs-static-v0.1"
    out.mkdir(parents=True, exist_ok=True)
    if sys.argv[1] == "freeze":
        (out / "freeze.json").write_text(json.dumps(freeze(), indent=1) + "\n")
    else:
        result = run(json.loads((out / "freeze.json").read_text()))
        (out / "results.json").write_text(json.dumps(result, indent=1) + "\n")
        print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=1))
