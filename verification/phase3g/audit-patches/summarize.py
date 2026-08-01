#!/usr/bin/env python3
"""Read back what pytest itself recorded and separate the two failure kinds.

A strict-xfail specification that starts PASSING is reported by pytest as a
failure, with the message "[XPASS(strict)] ...". That is a pre-registered
prediction coming true, and it is the opposite of a regression. Counting it
as one is how a correct change gets read as a break.
"""
import json
import os
import re
import sys

LABELS = ["baseline", "instr", "5g-reader", "5g-writer", "5g", "5l", "5gl"]
BASE = "/tmp/uniimente-audit-runs"


def load(label):
    with open(os.path.join(BASE, label, "result.json")) as fh:
        return json.load(fh)


def classify(rec):
    msg = (rec.get("message") or "") + " " + (rec.get("text") or "")
    if "XPASS(strict)" in msg or "[XPASS" in msg:
        return "XPASS_STRICT"
    return "ASSERTION_FAILURE"


def main():
    out = {}
    base_suite = load("baseline")["shapes"]["suite"]["cases"]
    for label in LABELS:
        r = load(label)
        suite = r["shapes"]["suite"]["cases"]
        xpass, fails = [], []
        for nid, rec in sorted(suite.items()):
            if rec["outcome"] not in ("failed", "error"):
                continue
            (xpass if classify(rec) == "XPASS_STRICT" else fails).append(nid)
        # a REGRESSION is a case that passed at baseline and no longer does
        regressed = [n for n in fails
                     if base_suite.get(n, {}).get("outcome") == "passed"]
        out[label] = {
            "suite_totals": r["shapes"]["suite"]["totals"],
            "target_passes_in_suite": r["target_passes_in_suite"],
            "target_passes_solo": r["target_passes_solo"],
            "xpass_strict": xpass,
            "assertion_failures": fails,
            "regressions_vs_baseline": regressed,
            "n_xpass_strict": len(xpass),
            "n_assertion_failures": len(fails),
            "n_regressions": len(regressed),
        }
        print("== %-10s  totals=%s" % (label, r["shapes"]["suite"]["totals"]))
        print("   targets passing (suite/solo): %d/5  %d/5"
              % (r["target_passes_in_suite"], r["target_passes_solo"]))
        print("   XPASS(strict) — pre-registered specs now passing: %d" % len(xpass))
        for n in xpass:
            print("      + " + n.split("::")[-1])
        print("   assertion failures: %d   (regressions vs baseline: %d)"
              % (len(fails), len(regressed)))
        for n in fails:
            mark = "REGRESSION" if n in regressed else "already-failing"
            print("      ! %-70s %s" % (n.split("::")[-1][:70], mark))
        print()
    with open(os.path.join(BASE, "summary.json"), "w") as fh:
        json.dump(out, fh, indent=2, sort_keys=True)


if __name__ == "__main__":
    main()
