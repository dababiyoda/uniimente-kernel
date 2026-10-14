#!/usr/bin/env python3
"""Verifier v3 for uniimente-kernel: formed-function cortex routing slice (PR #143).

Exit 0 = pass. Every run is appended to verifier/runs/.

V1: layering — the new cortex organs never import greg
V2: regression — executable unit tests green
V3: truthful deficit — nothing attached -> DEPENDENCY_UNAVAILABLE, no answer
V4: certificate control — certificate failure / unproven claim -> INCONCLUSIVE, withheld
V5: certified path — schema-valid receipt, GREG certificate, no authority created
"""
import os, sys, json, datetime, subprocess

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
proc = subprocess.run([sys.executable, "-m", "pytest", "tests/unit", "-q"],
                      capture_output=True, text=True, cwd=ROOT)
tail = (proc.stdout.strip().splitlines() or [""])[-1]
check("V2", proc.returncode == 0, f"pytest tests/unit: {tail}")

from cortex.organs.formed import FormedFunctionError
from cortex.organs.graphsearch import ORGAN_ID as GRAPH_ORGAN, GraphSearchOrgan
from cortex.organs.continuous import ORGAN_ID as CONOPT_ORGAN, ContinuousOptimizationOrgan
from cortex.routing import Cortex
from cortex.schemas import validate

DECL = {"consequence_class": "internal_write", "reversibility": "reversible"}
GRAPH_PROBLEM = {"problem_id": "v3:graph", "question": "shortest path A to C",
                 "payload": {"declared": DECL,
                             "graph": {"kind": "shortest_path", "source": "A", "target": "C",
                                       "edges": [["A", "B", 1], ["B", "C", 2], ["A", "C", 5]]}}}
LP_PROBLEM = {"problem_id": "v3:lp", "question": "minimize cost",
              "payload": {"declared": DECL,
                          "linear_program": {
                              "variables": [{"name": "x", "lower": 0}, {"name": "y", "lower": 0}],
                              "objective": {"sense": "min", "coefficients": {"x": 1, "y": 2}},
                              "constraints": [{"op": ">=", "coefficients": {"x": 1, "y": 1}, "rhs": 4,
                                               "name": "demand"}]}}}
MECH = {"capability_id": "acquired.graph.shortest_path.networkx", "distribution": "networkx",
        "version": "3.6.1", "license": "BSD-3-Clause", "runner": "networkx.shortest_path",
        "package_digest": "sha256:0", "request_sha256": "sha256:1",
        "request_shape": {"nodes": 3, "edges": 3}}


def stub(answer, calls=1):
    def call(params, cpu_seconds):
        return {"answer": answer(), "solver_calls": calls}
    return call


# V3: truthful deficit — nothing attached, no claim, genesis trigger state
try:
    graph = Cortex().run(GRAPH_PROBLEM)
    lp = Cortex().run(LP_PROBLEM)
    ok = (graph["output"]["state"] == "DEPENDENCY_UNAVAILABLE" and graph["output"]["answer"] is None
          and graph["route"]["selected"] == [GRAPH_ORGAN]
          and lp["output"]["state"] == "DEPENDENCY_UNAVAILABLE" and lp["output"]["answer"] is None
          and lp["route"]["selected"] == [CONOPT_ORGAN])
    check("V3", ok, f"nothing attached -> graph {graph['output']['state']}, lp {lp['output']['state']}, "
                    "no answer, genesis-trigger state")
except Exception as exc:
    check("V3", False, f"default cortex run raised {type(exc).__name__}: {exc}")

# V4: certificate control — a certificate failure and an unproven claim are both withheld
try:
    def lying(params, cpu_seconds):
        raise FormedFunctionError("certificate", "engine's claimed optimum fails GREG's exact check")
    cortex = Cortex()
    cortex.organs[GRAPH_ORGAN] = GraphSearchOrgan({"graph.shortest_path": (lying, None)})
    lie = cortex.run(GRAPH_PROBLEM)
    unproven_answer = {"certified": False, "status": "infeasible",
                       "why": "program too large for GREG's proving follow-up solves",
                       "_mechanism": dict(MECH)}
    cortex2 = Cortex()
    cortex2.organs[GRAPH_ORGAN] = GraphSearchOrgan({"graph.shortest_path": (stub(lambda: unproven_answer), None)})
    unproven = cortex2.run(GRAPH_PROBLEM)
    label = (unproven["proof_artifacts"][0].get("engine_claim") or {}).get("label")
    ok = (lie["output"]["state"] == "INCONCLUSIVE" and lie["output"]["answer"] is None
          and unproven["output"]["state"] == "INCONCLUSIVE" and unproven["output"]["answer"] is None
          and label == "unproven; not asserted by this organ")
    check("V4", ok, f"certificate failure -> {lie['output']['state']}; unproven claim -> "
                    f"{unproven['output']['state']} (engine claim labeled {label!r}); nothing asserted")
except Exception as exc:
    check("V4", False, f"certificate-control run raised {type(exc).__name__}: {exc}")

# V5: certified path — schema-valid receipt, GREG certificate in the proof, no authority
try:
    def certified():
        return {"certified": True, "source": "A", "target": "C", "reachable": True, "distance": 3,
                "path": ["A", "B", "C"], "distances": {"A": 0, "B": 1, "C": 3}, "unreachable": [],
                "certificate": {"kind": "feasible potentials realised by predecessor chains",
                                "arithmetic": "exact fractions"},
                "engine": "networkx 3.6.1", "license": "BSD-3-Clause", "authority_created": False,
                "_mechanism": dict(MECH)}
    cortex = Cortex()
    cortex.organs[GRAPH_ORGAN] = GraphSearchOrgan({"graph.shortest_path": (stub(certified), None)})
    receipt = cortex.run(GRAPH_PROBLEM)
    validate(receipt, "cortex-receipt")
    proof = receipt["proof_artifacts"][0]
    ok = (receipt["output"]["state"] == "OK"
          and receipt["output"]["answer"]["certified"] is True
          and receipt["output"]["answer"]["distance"] == 3
          and str(proof.get("certificate", {}).get("kind", "")).startswith("feasible potentials")
          and proof.get("certificate_authority", "").startswith("GREG-owned")
          and "formed:graph.shortest_path" in json.dumps(receipt)
          and receipt["authority_created"] is False)
    check("V5", ok, "certified answer -> schema-valid receipt, GREG certificate in proof, "
                    "formed: dependency named, authority_created false")
except Exception as exc:
    check("V5", False, f"certified-path run raised {type(exc).__name__}: {exc}")

for item in passes:
    print("PASS", item)
for item in skips:
    print("SKIP", item)
for item in failures:
    print("FAIL", item)
status = "PASS" if not failures else "FAIL"
run = {
    "verifier": "v3",
    "ts_utc": datetime.datetime.now(datetime.UTC).isoformat(),
    "command": "python3 verifier/v3/verify.py",
    **BINDING,
    "exit_code": 0 if not failures else 1,
    "passes": passes, "skips": skips, "failures": failures,
}
os.makedirs("verifier/runs", exist_ok=True)
name = f"verifier/runs/v3-{run['ts_utc'].replace(':','-')}.json"
json.dump(run, open(name, "w"), indent=2)
print(f"run recorded -> {name} :: {status}")
sys.exit(run["exit_code"])
