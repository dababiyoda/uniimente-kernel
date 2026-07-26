#!/usr/bin/env python3
"""Required check 4 — sealed developmental work produces zero outside effects.

Package 1 scope: verifies the RC's own declared sealed-state invariants on the
TARGET_FORM_001 report. This is a DECLARATION check, not an enforcement check.

A stronger out-of-process enforcement harness (audit hooks + rlimits, asserted
from a parent process) is queued as part of the PR #44 extraction at step 11.
Until that lands, this check can be satisfied by a report that merely claims
external_effects=0. That limitation is deliberate and recorded so nobody
mistakes this for proof of inertness.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

REQUIRED = {
    "external_effects": 0,
    "authorization_state": "SIMULATED_NOT_AUTHORIZED",
    "exact_restoration_attempts": 0,
    "false_activations": 0,
}
ALLOWED_VERDICTS = {
    "MECHANICS_VALIDATED_NOT_PRODUCTION_AUTHORIZED",
    "MECHANICS_NOT_VALIDATED",
}


def main():
    proc = subprocess.run(
        [sys.executable, "-m", "developmental"],
        capture_output=True, text=True, cwd=ROOT, timeout=900,
    )
    if proc.returncode != 0:
        print(f"FAIL developmental benchmark exited {proc.returncode}")
        print(proc.stderr[-2000:])
        return 1

    try:
        report = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        print(f"FAIL benchmark did not emit JSON: {exc}")
        print(proc.stdout[:1000])
        return 1

    failures = []
    for field, expected in REQUIRED.items():
        actual = report.get(field, "<missing>")
        status = "ok" if actual == expected else "FAIL"
        print(f"  {status:<4} {field} = {actual!r} (required {expected!r})")
        if actual != expected:
            failures.append(f"{field}={actual!r}, required {expected!r}")

    verdict = report.get("verdict", "<missing>")
    if verdict in ALLOWED_VERDICTS:
        print(f"  ok   verdict = {verdict}")
    else:
        print(f"  FAIL verdict = {verdict!r} not in {sorted(ALLOWED_VERDICTS)}")
        failures.append(f"verdict={verdict!r} may not grant production authority")

    print()
    if failures:
        print(f"{len(failures)} sealed-state failure(s):")
        for failure in failures:
            print(f"  {failure}")
        return 1
    print("sealed developmental state declared and intact "
          "(declaration check only — see module docstring)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
