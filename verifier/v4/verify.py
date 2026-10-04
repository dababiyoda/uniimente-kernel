#!/usr/bin/env python3
"""Verifier v4 for uniimente-kernel: bounded n-part composition with cap honesty (0.4.0).

Exit 0 = pass. Every run is appended to verifier/runs/.

V1: layering — the formed-function organs stay GREG-free (passthrough from v3)
V2: regression — executable unit tests green
V3: bounded composition — three-part payload -> three selected routes, three typed proofs
V4: cap honesty — five-part payload -> four selected; the dropped part is named cap-dropped
V5: aggregate budget — solver-call demand beyond budget refuses before any organ runs
V6: freeze non-contamination — prior freezes hash-pinned; v0.4.0 freeze is a new manifest
"""
import os, sys, json, hashlib, datetime, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from verifier.run_binding import head_commit, tree_state  # PR #85 Finding 3, ported
BINDING = {"head_commit": head_commit(), "tracked_tree": tree_state()}  # before anything runs

failures, passes, skips = [], [], []


def check(cid, ok, msg):
    (passes if ok else failures).append(f"{cid}: {msg}")


# V1: layering — cortex organs stay GREG-free; formed callables are worker-injected
import re
bad = []
for rel in ("cortex/organs/formed.py", "cortex/organs/graphsearch.py", "cortex/organs/continuous.py"):
    if not os.path.isfile(rel):
        bad.append(f"{rel}: missing")
        continue
    if re.search(r"^\s*(from|import)\s+greg\b", open(rel, encoding="utf-8").read(), re.M):
        bad.append(f"{rel}: imports greg")
check("V1", not bad, "; ".join(bad) if bad else "formed/graphsearch/continuous organs exist and never import greg")

# V2: all unit tests
proc = subprocess.run([sys.executable, "-I", "-m", "pytest", "tests/unit", "-q"],
                      capture_output=True, text=True, cwd=ROOT)
tail = (proc.stdout.strip().splitlines() or [""])[-1]
check("V2", proc.returncode == 0, f"pytest tests/unit: {tail}")

from cortex.evaluation.build_suites import schedule
from cortex.organs.continuous import ORGAN_ID as CONOPT_ORGAN, ContinuousOptimizationOrgan
from cortex.organs.graphsearch import ORGAN_ID as GRAPH_ORGAN, GraphSearchOrgan
from cortex.routing import DETERRENCE, EVIDENCE, FERMI, FORMAL, MAX_COMPOSITION, Cortex
from cortex.schemas import validate

CLOCK = lambda: "2026-09-30T00:00:00Z"  # noqa: E731
DECL = {"consequence_class": "internal_write", "reversibility": "reversible"}
GRAPH_PART = {"kind": "shortest_path", "source": "A", "target": "C",
              "edges": [["A", "B", 1], ["B", "C", 2], ["A", "C", 5]]}
LP_PART = {"variables": [{"name": "x", "lower": 0}, {"name": "y", "lower": 0}],
           "objective": {"sense": "min", "coefficients": {"x": 1, "y": 2}},
           "constraints": [{"op": ">=", "coefficients": {"x": 1, "y": 1}, "rhs": 4, "name": "demand"}]}
EST_PART = {"target": {"name": "c", "unit": "USD/week"}, "expression": ["*", "h", "r"],
            "variables": [{"name": "h", "unit": "hour/week", "low": 30, "high": 50},
                          {"name": "r", "unit": "USD/hour", "low": 40, "high": 60}]}
CLAIM_PART = {"id": "C", "type": "intervention",
              "statement": "raising the detection probability lowers duplicate invoicing",
              "evidence": [{"id": "E1", "kind": "randomized_trial", "effect": -0.4, "se": 0.1}]}
DET_PART = {"actor_role": "vendor submitting invoices", "behavior": "duplicate invoicing",
            "parameters": {"gain_usd": {"low": 2000, "high": 6000}, "p_detect": {"low": 0.05, "high": 0.15},
                           "p_sanction": {"low": 0.5, "high": 0.8},
                           "sanction_usd": {"low": 10000, "high": 30000}},
            "interventions": [{"id": "I_match", "kind": "detection", "cost_usd": 3000,
                               "effects": {"p_detect": {"set": 0.9}}}],
            "seed": 7}
MECH = {"capability_id": "acquired.graph.shortest_path.networkx", "distribution": "networkx",
        "version": "3.6.1", "license": "BSD-3-Clause", "runner": "networkx.shortest_path",
        "package_digest": "sha256:0", "request_sha256": "sha256:1",
        "request_shape": {"nodes": 3, "edges": 3}}
LP_MECH = {**MECH, "capability_id": "acquired.lp.optimize.scipy", "distribution": "scipy",
           "version": "1.17.1", "license": "BSD-3-Clause", "runner": "scipy.lp",
           "request_shape": {"variables": 2, "constraints": 1}}


def _shortest():
    return {"certified": True, "source": "A", "target": "C", "reachable": True, "distance": 3,
            "path": ["A", "B", "C"], "distances": {"A": 0, "B": 1, "C": 3}, "unreachable": [],
            "certificate": {"kind": "feasible potentials realised by predecessor chains",
                            "arithmetic": "exact fractions"},
            "engine": "networkx 3.6.1", "license": "BSD-3-Clause", "authority_created": False,
            "_mechanism": dict(MECH)}


def _lp():
    return {"certified": True, "status": "optimal", "sense": "min", "objective": 4.0,
            "values": {"x": 4.0, "y": 0.0}, "binding": ["demand"], "shadow_prices": {"demand": 1.0},
            "certificate": {"kind": "primal and dual feasibility with zero duality gap", "gap": 0.0,
                            "tolerance": "relative 1e-7 (engine floating point)",
                            "arithmetic": "exact fractions"},
            "engine": "scipy 1.17.1", "license": "BSD-3-Clause", "authority_created": False,
            "_mechanism": dict(LP_MECH)}


def _stub(answer, recorder=None):
    def call(params, cpu_seconds):
        if recorder is not None:
            recorder.append((params, cpu_seconds))
        return {"answer": answer(), "solver_calls": 1}
    return call


def cortex_with_formed(calls=None):
    cortex = Cortex(clock=CLOCK)
    cortex.organs[GRAPH_ORGAN] = GraphSearchOrgan({"graph.shortest_path": (_stub(_shortest, calls), None)})
    cortex.organs[CONOPT_ORGAN] = ContinuousOptimizationOrgan({"lp.optimize": (_stub(_lp, calls), None)})
    return cortex


def formal_part():
    model, _, _ = schedule([("A", 3), ("B", 4), ("C", 2)], 10)
    return model


# V3: bounded composition — three parts selected, three typed proofs
try:
    receipt = Cortex(clock=CLOCK).run({"problem_id": "v4:three", "question": "plan, cost, cause",
                                       "payload": {"declared": DECL, "formal_model": formal_part(),
                                                   "estimation_model": EST_PART, "claim": CLAIM_PART}})
    classes = {p["proof_class"] for p in receipt["proof_artifacts"]}
    ok = (receipt["route"]["selected"] == [FORMAL, FERMI, EVIDENCE]
          and receipt["route"]["composition"] is True
          and receipt["route"]["max_parts"] == MAX_COMPOSITION == 4
          and receipt["route"]["cap_dropped"] == []
          and {"formal", "estimation", "evidence_assessment"} <= classes
          and len(receipt["output"]["per_route"]) == 3)
    validate(receipt, "cortex-receipt")
    check("V3", ok, f"three-part payload -> selected {receipt['route']['selected']}, "
                    f"proofs {sorted(classes)}, max_parts {receipt['route']['max_parts']}")
except Exception as exc:
    check("V3", False, f"composition run raised {type(exc).__name__}: {exc}")

# V4: cap honesty — five eligible parts, one cap-dropped and named honestly
try:
    receipt = cortex_with_formed().run({"problem_id": "v4:five", "question": "everything at once",
                                        "payload": {"declared": DECL, "formal_model": formal_part(),
                                                    "estimation_model": EST_PART, "graph": GRAPH_PART,
                                                    "linear_program": LP_PART,
                                                    "deterrence_model": DET_PART}})
    by_route = {a["route"]: a["why_not"] for a in receipt["alternatives"]}
    dropped = by_route.get(DETERRENCE, [])
    ok = (len(receipt["route"]["selected"]) == MAX_COMPOSITION
          and receipt["route"]["cap_dropped"] == [DETERRENCE]
          and any("dropped by the composition bound" in w for w in dropped)
          and not any("not required by this payload" in w for w in dropped))
    validate(receipt, "cortex-receipt")
    check("V4", ok, f"five-part payload -> {len(receipt['route']['selected'])} selected, "
                    f"cap_dropped {receipt['route']['cap_dropped']}, why_not {dropped}")
except Exception as exc:
    check("V4", False, f"cap-honesty run raised {type(exc).__name__}: {exc}")

# V5: aggregate budget refusal — at-least-3 solver calls planned, budget 2, nothing runs
try:
    calls = []
    receipt = cortex_with_formed(calls).run({"problem_id": "v4:budget", "question": "q",
                                             "payload": {"declared": DECL, "formal_model": formal_part(),
                                                         "graph": GRAPH_PART, "linear_program": LP_PART,
                                                         "resources": {"max_solver_calls": 2}}})
    ok = (receipt["output"]["state"] == "BUDGET_EXHAUSTED"
          and receipt["disposition"]["kind"] == "abstain"
          and "at least 3 solver call(s)" in receipt["disposition"]["reason"]
          and calls == []
          and receipt["output"]["per_route"] == [])
    validate(receipt, "cortex-receipt")
    check("V5", ok, f"aggregate solver demand 3 > budget 2 -> {receipt['output']['state']}; "
                    f"formed organs fired: {len(calls)}")
except Exception as exc:
    check("V5", False, f"budget run raised {type(exc).__name__}: {exc}")

# V6: freeze non-contamination — prior freezes pinned; v0.4.0 is a new manifest
try:
    pinned = {
        "freeze-v0.3.0.json": "4a4d2122ae0a511c8c624bf20109f4fdad80d3ec2decd1d35ad1d90a9ec16298",
        "freeze-crossgeo-v0.2.json": "ce9abbc1af4181d30369ac4d794f7ed3d7cd4f20e8417118688ede8850ff6dde",
        "freeze-crossgeo-v0.3.json": "75ca409e9f3aca775e4423d8625c10d0e6bdd24d70d06758711b99fb40ea611d",
    }
    bad = []
    for name, want in pinned.items():
        path = os.path.join(ROOT, "cortex", "evaluation", name)
        got = hashlib.sha256(open(path, "rb").read()).hexdigest() if os.path.isfile(path) else "missing"
        if got != want:
            bad.append(f"{name}: {got}")
    new = os.path.join(ROOT, "cortex", "evaluation", "freeze-v0.4.0.json")
    new_hash = hashlib.sha256(open(new, "rb").read()).hexdigest() if os.path.isfile(new) else None
    ok = not bad and new_hash and new_hash not in set(pinned.values())
    check("V6", ok, "; ".join(bad) if bad else f"prior freezes pinned; freeze-v0.4.0.json {new_hash}")
except Exception as exc:
    check("V6", False, f"freeze check raised {type(exc).__name__}: {exc}")

for item in passes:
    print("PASS", item)
for item in skips:
    print("SKIP", item)
for item in failures:
    print("FAIL", item)
status = "PASS" if not failures else "FAIL"
run = {
    "verifier": "v4",
    "ts_utc": datetime.datetime.now(datetime.UTC).isoformat(),
    "command": "python3 verifier/v4/verify.py",
    **BINDING,
    "exit_code": 0 if not failures else 1,
    "passes": passes, "skips": skips, "failures": failures,
}
os.makedirs("verifier/runs", exist_ok=True)
name = f"verifier/runs/v4-{run['ts_utc'].replace(':','-')}.json"
json.dump(run, open(name, "w"), indent=2)
print(f"run recorded -> {name} :: {status}")
sys.exit(run["exit_code"])
