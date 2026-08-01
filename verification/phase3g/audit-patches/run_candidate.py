#!/usr/bin/env python3
"""Exact-execution audit runner.

Runs the five real target pytest node IDs (and the full suite) inside a
candidate worktree. Nothing here reimplements, mirrors or approximates a
test: every result is pytest's own verdict on the repository's own test
file, read back out of the JUnit XML that pytest itself wrote.

usage: run_candidate.py <label> <worktree>
"""
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

TARGETS = [
    "tests/unit/test_substrate_v5_single_flight_echo.py::test_A_diamond_convergence_opens_one_canonical_node",
    "tests/unit/test_substrate_v5_single_flight_echo.py::test_J_amplification_scales_with_units_not_paths[0.7]",
    "tests/unit/test_substrate_v5_single_flight_echo.py::test_J_amplification_scales_with_units_not_paths[0.8]",
    "tests/unit/test_substrate_v5_single_flight_echo.py::test_J_amplification_scales_with_units_not_paths[0.9]",
    "tests/unit/test_substrate_v5_single_flight_live_path.py::test_lineage_accumulates_and_a_real_cycle_closes_positively",
]
MODULES = [
    "tests/unit/test_substrate_v5_single_flight_echo.py",
    "tests/unit/test_substrate_v5_single_flight_live_path.py",
]


def _nid(case):
    """Reconstruct the pytest node id from a JUnit <testcase> element."""
    f = case.get("file") or case.get("classname", "").replace(".", "/") + ".py"
    return "%s::%s" % (f, case.get("name"))


def parse(path):
    """Read pytest's own XML. Returns {node_id: {...}} and suite totals."""
    root = ET.parse(path).getroot()
    suite = root.find("testsuite") if root.tag == "testsuites" else root
    totals = {k: int(suite.get(k, 0))
              for k in ("tests", "errors", "failures", "skipped")}
    cases = {}
    for case in suite.iter("testcase"):
        rec = {"outcome": "passed", "message": "", "text": ""}
        for child in case:
            if child.tag == "failure":
                rec["outcome"] = "failed"
            elif child.tag == "error":
                rec["outcome"] = "error"
            elif child.tag == "skipped":
                rec["outcome"] = child.get("type", "skipped")
            else:
                continue
            rec["message"] = child.get("message", "")
            rec["text"] = (child.text or "")
        cases[_nid(case)] = rec
    totals["passed"] = (totals["tests"] - totals["errors"]
                        - totals["failures"] - totals["skipped"])
    return cases, totals


def run(label, worktree, outdir, name, args):
    xml = os.path.join(outdir, name + ".xml")
    log = os.path.join(outdir, name + ".log")
    cmd = [sys.executable, "-m", "pytest", "-p", "no:randomly",
           "-vv", "--tb=long", "-rA", "--junitxml=" + xml] + args
    proc = subprocess.run(cmd, cwd=worktree, capture_output=True, text=True)
    with open(log, "w") as fh:
        fh.write("$ " + " ".join(cmd) + "\n\n")
        fh.write(proc.stdout)
        fh.write(proc.stderr)
    cases, totals = parse(xml)
    return {"cmd": cmd[3:], "returncode": proc.returncode,
            "totals": totals, "cases": cases, "log": log, "xml": xml}


def main():
    label, worktree = sys.argv[1], sys.argv[2]
    outdir = os.path.join("/tmp/uniimente-audit-runs", label)
    os.makedirs(outdir, exist_ok=True)

    result = {"label": label, "worktree": worktree, "shapes": {}}

    # shape 1: each target alone, its own interpreter process
    for i, nid in enumerate(TARGETS):
        result["shapes"]["solo_%d" % i] = run(
            label, worktree, outdir, "solo_%d" % i, [nid])

    # shape 2: the five together
    result["shapes"]["batched"] = run(
        label, worktree, outdir, "batched", list(TARGETS))

    # shape 3: each whole module
    for i, mod in enumerate(MODULES):
        result["shapes"]["module_%d" % i] = run(
            label, worktree, outdir, "module_%d" % i, [mod])

    # shape 4: the whole suite
    result["shapes"]["suite"] = run(label, worktree, outdir, "suite", [])

    # target verdicts per shape
    verdicts = {}
    for nid in TARGETS:
        verdicts[nid] = {}
        for shape, r in result["shapes"].items():
            if nid in r["cases"]:
                verdicts[nid][shape] = r["cases"][nid]["outcome"]
    result["target_verdicts"] = verdicts
    result["target_passes_in_suite"] = sum(
        1 for nid in TARGETS
        if verdicts[nid].get("suite") == "passed")
    result["target_passes_solo"] = sum(
        1 for i, nid in enumerate(TARGETS)
        if verdicts[nid].get("solo_%d" % i) == "passed")

    with open(os.path.join(outdir, "result.json"), "w") as fh:
        json.dump(result, fh, indent=2, sort_keys=True)

    print(label, "suite totals:", result["shapes"]["suite"]["totals"])
    print(label, "targets passing in full suite:",
          result["target_passes_in_suite"], "/", len(TARGETS))
    print(label, "targets passing solo:",
          result["target_passes_solo"], "/", len(TARGETS))
    for nid in TARGETS:
        print("   ", nid.split("::")[-1], verdicts[nid])


if __name__ == "__main__":
    main()
