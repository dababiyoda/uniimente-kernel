"""Antifragility v3 (PREREGISTRATION.md). Run from the repository root, once, after the freeze.

    python tests/evidence/antifragility-v3-2026-10-22/experiment.py --check   # workload and #189 generator frozen
    python tests/evidence/antifragility-v3-2026-10-22/experiment.py           # stress, then every holdout arm

The generator, objectives, tolerances, strata and mission shape are imported from #189's harness, whose bytes the
freeze pins. Every key is a per-run test key, not Alfonso's. Nothing leaves this machine.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import statistics
import sys
import tempfile
import time

sys.path.insert(0, os.getcwd())
HERE = Path(__file__).parent
V189 = Path("tests/evidence/antifragility-2026-10-15/experiment.py")
_spec = importlib.util.spec_from_file_location("antifragility_v189", V189)
v189 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v189)
FUNCTIONS, TOLERANCE, STRATA, instance, request, mission_for = (
    v189.FUNCTIONS, v189.TOLERANCE, v189.STRATA, v189.instance, v189.request, v189.mission_for)

STRESS_SEEDS = range(500, 536)            # #189's 500-511 first, in their order, then 512-535 continuing the cycle
HOLDOUT_SEEDS = range(2000, 2010)
INCUMBENTS = ("cognition.swarm", "cognition.blackbox")
ALTERNATIVE = "cognition.blackbox_multistart_lbfgsb"
ATTACHED = INCUMBENTS + (ALTERNATIVE,)    # founder-attached (per-run test key) in every arm


def workload() -> dict:
    stress = [{"id": f"stress-{s}", "stratum": "HIGH", **instance(FUNCTIONS[i % 5], "HIGH", s)}
              for i, s in enumerate(STRESS_SEEDS)]
    holdout = [{"id": f"hold-{st}-{f}-{s}", "stratum": st, **instance(f, st, s)}
               for st in STRATA for f in FUNCTIONS for s in HOLDOUT_SEEDS]
    return {"tolerance": TOLERANCE, "strata": STRATA, "attached": list(ATTACHED), "stress": stress,
            "holdout": holdout}


def digest(obj) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def file_digest(path) -> str:
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stress(home: Path, key, body_id: str, items: list) -> dict:
    """The bounded disturbance: 36 signed HIGH missions settled through the real path, mechanism on."""
    from greg.body import Body
    from greg.cognition import condition_competence as cc
    from tests.greg_fixtures import Clock, signed
    clock, log = Clock(), []
    cc.MODE = "on"
    with Body(home, clock=clock) as body:
        body.boot()
        for cid in ATTACHED:
            body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": cid}))
        for item in items:
            body.apply(signed(key, body_id, "MISSION", mission_for(item)))
            for _ in range(3):
                body.tick()
                clock.advance(31)
            ev = cc.evidence_from(body.journal)
            cell = cc.condition_key("optimization", request(item))
            pref = cc.preference(cell, ev)
            log.append({"id": item["id"], "function": item["function"], "cell": cell,
                        "evidence": ev.get(cell), "fired": bool(pref and pref["fired"])})
        achieved = {e.payload["mission_id"] for e in body.journal.replay("mission.achieved")}
        pairs = cc.pairs_from(body.journal)
    first = next((i + 1 for i, row in enumerate(log) if row["fired"]), None)
    return {"missions": len(items),
            "damage_failed_missions": sum(1 for item in items if f"m:{item['id']}" not in achieved),
            "shadow_trials": len(pairs), "shadow_evaluations": sum(p["shadow_evaluations"] for p in pairs),
            "shadow_seconds": round(sum(p["shadow_seconds"] for p in pairs), 3),
            "preference_fired": first is not None, "recovery_cost_missions_until_preference": first, "log": log}


def _reason(item, req, registry, journal):
    from greg.cognition.cortex import reason
    return reason({"problem_id": item["id"], "compile": {"geometry": {"geometry": "optimization"}, "data": req}},
                  registry=registry, journal=journal)


def _row(item, r, started, evaluations):
    result = r.get("result") or {}
    fitness = result.get("fitness")
    return {"id": item["id"], "stratum": item["stratum"], "function": item["function"],
            "method": r.get("method_or_composition_selected"), "state": r.get("state"), "fitness": fitness,
            "evaluations": evaluations, "seconds": round(time.monotonic() - started, 3),
            "shadow_evaluations": (r.get("condition_shadow") or {}).get("evaluations", 0),
            "pass": r.get("state") == "ANSWERED" and fitness is not None and fitness <= TOLERANCE[item["function"]]}


def holdout(items: list, *, journal, mode: str, high_budget: int | None = None) -> list:
    """One arm. Holdout instances are compiled directly, so they never settle and never feed learning."""
    from greg.cognition import condition_competence as cc
    from greg.cognition.cortex import registry_view
    registry = registry_view(None)
    for cid in ATTACHED:
        registry.set_state(cid, "ATTACHED")
    saved, cc.MODE = cc.MODE, mode
    rows = []
    try:
        for item in items:
            req = request(item)
            if high_budget is not None and item["stratum"] == "HIGH":
                req = {**req, "budget": high_budget}
            started = time.monotonic()
            r = _reason(item, req, registry, journal)
            rows.append(_row(item, r, started, (r.get("result") or {}).get("evaluations") or 0))
    finally:
        cc.MODE = saved
    return rows


def best_of_both(items: list) -> list:
    """B2: the incumbent and the alternative on every instance, the better verified answer kept (2x compute)."""
    from greg.cognition import condition_competence as cc
    rows = holdout(items, journal=None, mode="off")
    for row, item in zip(rows, items):
        started = time.monotonic()
        shadow = cc.shadow_trial(request(item))
        row["seconds"] = round(row["seconds"] + time.monotonic() - started, 3)
        row["evaluations"] += shadow["evaluations"]
        if shadow["verified"] and (row["fitness"] is None or shadow["fitness"] < row["fitness"]):
            row.update(method=cc.ALTERNATIVE, fitness=shadow["fitness"])
            row["pass"] = shadow["fitness"] <= TOLERANCE[item["function"]]
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
                                "evaluations": sum(r["evaluations"] + r.get("shadow_evaluations", 0) for r in cell),
                                "methods": sorted({str(r["method"]) for r in cell})}
    return out


def total(s: dict, stratum: str | None = None) -> int:
    return sum(c["passes"] for k, c in s.items() if stratum is None or k.startswith(stratum + "/"))


def verdict(arms: dict, rows: dict, fired: bool) -> dict:
    """The pre-registered rule (PREREGISTRATION.md section 5), in its declared order."""
    from greg.cognition.condition_competence import sign_test
    s = arms
    learn = total(s["LEARN"])
    by_id = {r["id"]: r["pass"] for r in rows["CONTROL"]}
    wins = sum(1 for r in rows["LEARN"] if r["pass"] and not by_id[r["id"]])
    losses = sum(1 for r in rows["LEARN"] if not r["pass"] and by_id[r["id"]])
    p = sign_test(wins, losses)
    fewer = [k for k in s["PRE"] if s["LEARN"][k]["passes"] < s["PRE"][k]["passes"]]
    out = {"passes": {arm: total(v) for arm, v in s.items()},
           "low_passes": {arm: total(v, "LOW") for arm, v in s.items()},
           "learn_vs_control_discordant": [wins, losses], "learn_vs_control_p": round(p, 6),
           "cells_with_fewer_passes_than_pre": fewer, "preference_fired_in_stress": fired}
    if total(s["LEARN"], "LOW") < total(s["PRE"], "LOW") or learn < total(s["CONTROL"]):
        name = "REGRESSION"
    elif not fired or not (learn > total(s["PRE"]) and learn > total(s["CONTROL"])):
        name = "NO_GAIN"
    elif not learn > total(s["B1"]):
        name = "NO_GAIN (compute-attributed)"
    elif not learn > total(s["S"]):
        name = "NO_GAIN (condition not causal)"
    elif not fewer and p < 0.05:
        name = "GAIN"
    elif not fewer:
        name = "INCONCLUSIVE"
    else:
        name = "NO_GAIN"                       # rule 5 requires no cell below PRE; rule 6 needs rule 5's counts
    out["verdict"] = name
    return out


def main(argv) -> int:
    frozen = json.loads((HERE / "workload.json").read_text())
    if (digest(workload()) != frozen["digest"] or digest(frozen["workload"]) != frozen["digest"]
            or file_digest(V189) != frozen["v189_experiment_sha256"]):
        print("the workload or #189's generator differs from the frozen one")
        return 1
    if "--check" in argv:
        print("workload matches", frozen["digest"])
        return 0
    from tests.greg_fixtures import make_body
    w = frozen["workload"]
    tmp = Path(tempfile.mkdtemp(prefix="greg-antifragility-v3-"))
    home, key, body_id, _ = make_body(tmp)
    stressed = stress(home, key, body_id, w["stress"])
    from greg.body import Body
    rows = {}
    with Body(home) as body:
        rows["PRE"] = holdout(w["holdout"], journal=None, mode="on")
        rows["LEARN"] = holdout(w["holdout"], journal=body.journal, mode="on")
        rows["CONTROL"] = holdout(w["holdout"], journal=body.journal, mode="off")
        rows["A"] = holdout(w["holdout"], journal=body.journal, mode="pooled")
        rows["S"] = holdout(w["holdout"], journal=body.journal, mode="shuffled")
        # B1: no learning; the incumbent's HIGH budget raised so B1's total evaluations equal LEARN's holdout
        # evaluations (shadows included) plus the stress shadow evaluations
        learn_evals = sum(r["evaluations"] + r["shadow_evaluations"] for r in rows["LEARN"])
        low_evals = sum(STRATA["LOW"]["budget"] for r in w["holdout"] if r["stratum"] == "LOW")
        n_high = sum(1 for r in w["holdout"] if r["stratum"] == "HIGH")
        b1_budget = (learn_evals + stressed["shadow_evaluations"] - low_evals) // n_high
        rows["B1"] = holdout(w["holdout"], journal=None, mode="off", high_budget=b1_budget)
    rows["B2"] = best_of_both(w["holdout"])
    summary = {arm: summarise(r) for arm, r in rows.items()}
    report = {"workload_digest": frozen["digest"], "stress": stressed, "b1_high_budget": b1_budget,
              "summary": summary, "verdict": verdict(summary, rows, stressed["preference_fired"]), "rows": rows}
    print(json.dumps(report, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    if "--freeze" in sys.argv:
        w = workload()
        (HERE / "workload.json").write_text(json.dumps({"digest": digest(w), "workload": w,
                                                        "v189_experiment_sha256": file_digest(V189)},
                                                       sort_keys=True) + "\n")
        print("frozen", digest(w))
    else:
        raise SystemExit(main(sys.argv[1:]))
