"""Run every test the one-machine adversarial matrix names and record each outcome.

Writes ``observed-run.json`` beside the matrix: the code head it ran on, the command, the totals and
one entry per pytest case (parametrized cases separately). The matrix test requires an entry for
every listed test, so a row cannot point at a test whose outcome was never observed.

Usage (live organ checkouts named by UNIIMENTE_DALEOBANKS_* / UNIIMENTE_WEALTHMACHINE_*):
    python scripts/observe_adversarial_matrix.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "tests" / "evidence" / "one-machine-20261014"
ORGANS = ("UNIIMENTE_DALEOBANKS_ROOT", "UNIIMENTE_DALEOBANKS_PYTHON", "UNIIMENTE_WEALTHMACHINE_ROOT",
          "UNIIMENTE_WEALTHMACHINE_PYTHON")


def nodes() -> list[str]:
    matrix = json.loads((EVIDENCE / "adversarial-matrix.json").read_text())
    return sorted({t for row in matrix["attacks"] + matrix["additional_attacks"] for t in row["tests"]})


def main() -> int:
    if not all(os.environ.get(k) for k in ORGANS):
        print("live organ checkouts are required: " + ", ".join(ORGANS), file=sys.stderr)
        return 2
    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True,
                          check=True).stdout.strip()
    listed = nodes()
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "junit.xml"
        subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={report}",
                        *listed], cwd=ROOT, env={**os.environ, "UNIIMENTE_REQUIRE_ORGANS": "1",
                                                 "GREG_REQUIRE_LANDLOCK": "1"})
        cases = ET.parse(report).getroot().iter("testcase")
        results = {}
        for case in cases:
            outcome = next((tag for tag in ("failure", "error", "skipped") if case.find(tag) is not None), "passed")
            results[f"{case.get('classname')}::{case.get('name')}"] = {
                "outcome": outcome, "seconds": round(float(case.get("time") or 0), 3)}
    totals = {k: sum(1 for r in results.values() if r["outcome"] == k)
              for k in ("passed", "failure", "error", "skipped")}
    (EVIDENCE / "observed-run.json").write_text(json.dumps({
        "trunk_head": head,
        "command": f"python scripts/observe_adversarial_matrix.py (pytest on the {len(listed)} test ids in "
                   "adversarial-matrix.json, live organ checkouts, Landlock required)",
        "organs": 2, "totals": totals, "results": results}, indent=1) + "\n")
    print(json.dumps(totals))
    return 0 if totals["failure"] == totals["error"] == totals["skipped"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
