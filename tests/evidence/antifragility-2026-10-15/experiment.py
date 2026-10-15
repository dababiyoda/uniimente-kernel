"""The pre-registered antifragility experiment (PREREGISTRATION.md). Run from the repository root.

    python tests/evidence/antifragility-2026-10-15/experiment.py --check   # the workload is the frozen one
    python tests/evidence/antifragility-2026-10-15/experiment.py           # stress, then the three-arm holdout

Every key is a per-test key, not Alfonso's. Nothing leaves this machine.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import random
import statistics
import sys
import tempfile
import time

sys.path.insert(0, os.getcwd())
HERE = Path(__file__).parent
FUNCTIONS = ("sphere", "ackley", "griewank", "rosenbrock", "rastrigin")
TOLERANCE = {"sphere": 0.5, "ackley": 2.0, "griewank": 0.3, "rosenbrock": 200, "rastrigin": 60}
STRATA = {"LOW": {"dims": 10, "budget": 5000}, "HIGH": {"dims": 20, "budget": 10000}}
STRESS_SEEDS = range(500, 512)
HOLDOUT_SEEDS = range(1000, 1006)
METHODS = ("cognition.swarm", "cognition.blackbox")


def instance(function: str, stratum: str, seed: int) -> dict:
    rnd = random.Random(seed)
    dims, budget = STRATA[stratum]["dims"], STRATA[stratum]["budget"]
    return {"function": function, "shift": [round(rnd.uniform(-2, 2), 3) for _ in range(dims)],
            "bounds": [[-5.12, 5.12]] * dims, "budget": budget, "seed": seed}


def workload() -> dict:
    stress = [{"id": f"stress-{s}", "stratum": "HIGH", **instance(FUNCTIONS[i % 5], "HIGH", s)}
              for i, s in enumerate(STRESS_SEEDS)]
    holdout = [{"id": f"hold-{st}-{f}-{s}", "stratum": st, **instance(f, st, s)}
               for st in STRATA for f in FUNCTIONS for s in HOLDOUT_SEEDS]
    return {"tolerance": TOLERANCE, "strata": STRATA, "methods": list(METHODS), "stress": stress, "holdout": holdout}


def digest(obj) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def request(item: dict) -> dict:
    return {k: item[k] for k in ("function", "shift", "bounds", "budget", "seed")}


def mission_for(item: dict) -> dict:
    from tests.greg_fixtures import mission
    params = {"problem_id": f"real:{item['id']}", "compile": {"geometry": {"geometry": "optimization"},
                                                               "data": request(item)}}
    return mission(f"m:{item['id']}", checks=[{
        "check_id": "good", "description": f"fitness within the frozen tolerance {TOLERANCE[item['function']]}",
        "sensor": {"capability": "cognition.solve", "target": "cognition:bb", "params": params},
        "predicate": {"op": "lte", "field": "result.fitness", "value": TOLERANCE[item["function"]]}}],
        strategies=[{"action_id": "compile", "capability": "cognition.solve", "target": "cognition:bb",
                     "params": params, "advances": ["good"], "rationale": "minimise the declared objective"}],
        capabilities=["cognition.solve"], targets=("cognition:*",), ceiling="read_only")


def stress(home: Path, key, body_id: str, items: list) -> dict:
    """The bounded disturbance: real signed missions in the HIGH stratum, settled through the real path."""
    from greg.body import Body
    from greg.cognition import compiler, settlement
    from tests.greg_fixtures import Clock, signed
    clock, log = Clock(), []
    with Body(home, clock=clock) as body:
        body.boot()
        for cid in METHODS:
            body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": cid}))
        for item in items:
            body.apply(signed(key, body_id, "MISSION", mission_for(item)))
            for _ in range(3):
                body.tick()
                clock.advance(31)
            counts = compiler._settled_counts(body.journal)
            n, k = counts.get("cognition.swarm", (0, 0))
            log.append({"id": item["id"], "function": item["function"],
                        "swarm_settled": [n, k], "demoted": compiler._settled_inhibition(n, k) is not None})
        outcomes = [(o["method"], o["correct"]) for o in settlement.measured_outcomes(body.journal)]
        achieved = {e.payload["mission_id"] for e in body.journal.replay("mission.achieved")}
    first = next((i + 1 for i, row in enumerate(log) if row["demoted"]), None)
    # Damage is counted from the missions themselves, not from settled outcomes: run 1 showed that settlement
    # heard only successes, so a settled count reported no damage while five of twelve missions had failed.
    return {"missions": len(items), "settled": len(outcomes),
            "damage_failed_missions": sum(1 for item in items if f"m:{item['id']}" not in achieved),
            "settled_failures": sum(1 for _, ok in outcomes if not ok),
            "by_method": {m: [sum(1 for x, _ in outcomes if x == m), sum(1 for x, ok in outcomes if x == m and ok)]
                          for m in METHODS},
            "recovery_cost_missions_until_demotion": first, "log": log}


def holdout(items: list, *, journal, inhibition: bool) -> list:
    from greg.cognition import compiler
    from greg.cognition.cortex import reason, registry_view
    registry = registry_view(None)
    for cid in METHODS:
        registry.set_state(cid, "ATTACHED")
    saved = compiler.SETTLED_MIN_N
    if not inhibition:
        compiler.SETTLED_MIN_N = 10 ** 9               # the no-learning control: the same history, never read
    rows = []
    try:
        for item in items:
            started = time.monotonic()
            r = reason({"problem_id": item["id"], "compile": {"geometry": {"geometry": "optimization"},
                                                               "data": request(item)}},
                       registry=registry, journal=journal)
            fitness = (r.get("result") or {}).get("fitness")
            rows.append({"id": item["id"], "stratum": item["stratum"], "function": item["function"],
                         "method": r.get("method_or_composition_selected"), "state": r.get("state"),
                         "fitness": fitness, "seconds": round(time.monotonic() - started, 3),
                         "pass": r.get("state") == "ANSWERED" and fitness is not None
                         and fitness <= TOLERANCE[item["function"]]})
    finally:
        compiler.SETTLED_MIN_N = saved
    return rows


def summarise(rows: list) -> dict:
    out = {}
    for st in STRATA:
        for f in FUNCTIONS:
            cell = [r for r in rows if r["stratum"] == st and r["function"] == f]
            fits = [r["fitness"] for r in cell if r["fitness"] is not None]
            out[f"{st}/{f}"] = {"passes": sum(r["pass"] for r in cell), "n": len(cell),
                                "median_fitness": statistics.median(fits) if fits else None,
                                "median_seconds": statistics.median(r["seconds"] for r in cell),
                                "methods": sorted({str(r["method"]) for r in cell})}
    return out


def verdict(pre: dict, learn: dict, control: dict) -> dict:
    total = lambda s: sum(c["passes"] for c in s.values())                      # noqa: E731
    fewer = [k for k in pre if learn[k]["passes"] < pre[k]["passes"]]
    worse = [k for k in pre if pre[k]["median_fitness"] not in (None, 0) and learn[k]["median_fitness"] is not None
             and learn[k]["median_fitness"] > 10 * pre[k]["median_fitness"]]
    improved = total(learn) > total(pre) and total(learn) > total(control)
    name = ("ANTIFRAGILE_EVIDENCE" if improved and not fewer and not worse else
            "IMPROVED_WITH_REGRESSION" if improved else "NO_GAIN")
    return {"verdict": name, "passes": {"PRE": total(pre), "LEARN": total(learn), "CONTROL": total(control)},
            "strata_with_fewer_passes": fewer, "strata_with_quality_regression_over_10x": worse}


def main(argv) -> int:
    frozen = json.loads((HERE / "workload.json").read_text())
    if digest(workload()) != frozen["digest"] or digest(frozen["workload"]) != frozen["digest"]:
        print("the workload differs from the frozen one")
        return 1
    if "--check" in argv:
        print("workload matches", frozen["digest"])
        return 0
    from tests.greg_fixtures import make_body
    w = frozen["workload"]
    tmp = Path(tempfile.mkdtemp(prefix="greg-antifragility-"))
    home, key, body_id, _ = make_body(tmp)
    stressed = stress(home, key, body_id, w["stress"])
    from greg.body import Body
    with Body(home) as body:
        arms = {"PRE": holdout(w["holdout"], journal=None, inhibition=True),
                "LEARN": holdout(w["holdout"], journal=body.journal, inhibition=True),
                "CONTROL": holdout(w["holdout"], journal=body.journal, inhibition=False)}
    summary = {arm: summarise(rows) for arm, rows in arms.items()}
    report = {"workload_digest": frozen["digest"], "stress": stressed, "summary": summary,
              "verdict": verdict(summary["PRE"], summary["LEARN"], summary["CONTROL"]), "rows": arms}
    print(json.dumps(report, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    if "--freeze" in sys.argv:
        w = workload()
        (HERE / "workload.json").write_text(json.dumps({"digest": digest(w), "workload": w}, sort_keys=True) + "\n")
        print("frozen", digest(w))
    else:
        raise SystemExit(main(sys.argv[1:]))
