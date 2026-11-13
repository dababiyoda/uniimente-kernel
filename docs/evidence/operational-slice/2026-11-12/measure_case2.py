"""Case 2, pre-registered measure 3: ``case.assess`` on every withheld case, graded against LABELS.json.

SYNTHETIC — not a real party. Read-only; no body, network or payment:

    PYTHONPATH=. python docs/evidence/operational-slice/2026-11-12/measure_case2.py [--json]
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from tests.unit.request_case_2_grading import CASES, grade, read_case  # noqa: E402


def main():
    rows = []
    with tempfile.TemporaryDirectory(prefix="greg-case2-") as tmp:
        for case in sorted(p.name for p in CASES.iterdir()):
            rows.append(grade(case, read_case(case, Path(tmp))))
    if "--json" in sys.argv:
        print(json.dumps(rows, indent=1))
        return
    for r in rows:
        m = r["match"]
        mark = lambda ok: "ok" if ok else "XX"  # noqa: E731
        print(f"{r['case']:12s} elig {r['eligibility']:12s}/{r['expected_eligibility']:12s} {mark(m['eligibility'])} "
              f"route {r['route']:36s}{mark(m['route'])} deciding {','.join(r['deciding']) or '-':26s}"
              f"/{','.join(r['expected_deciding']) or '-':26s}{mark(m['deciding'])} "
              f"missing {len(r['missing'])}/{len(r['expected_missing'])} {mark(m['missing'])} "
              f"pay {r['payment_strict']}/{r['expected_payment']} strict {mark(m['payment_strict'])} "
              f"gated {mark(m['payment_gated'])}")
        if r["missing_extra"] or r["missing_absent"]:
            print(f"{'':12s} missing facts reported beyond the label: {r['missing_extra']}; "
                  f"label facts not reported: {r['missing_absent']}")
        if r["unknown_reported_decided"] or r["decided_reported_unknown"]:
            print(f"{'':12s} label unknown reported pass/fail: {r['unknown_reported_decided']}; "
                  f"label pass/fail reported unknown: {r['decided_reported_unknown']}")
        differ = {k: (v, r["expected_rule_outcomes"][k]) for k, v in r["rule_outcomes"].items()
                  if v != r["expected_rule_outcomes"][k]}
        if differ:
            print(f"{'':12s} rule outcomes that differ (reading, label): {differ}")
    n = len(rows)
    for field in ("eligibility", "route", "deciding", "missing", "payment_strict", "payment_gated"):
        print(f"{field}: {sum(r['match'][field] for r in rows)}/{n}")
    print("label unknown reported as pass or fail:", sum(len(r["unknown_reported_decided"]) for r in rows))
    print("label pass or fail reported unknown:", sum(len(r["decided_reported_unknown"]) for r in rows))


if __name__ == "__main__":
    main()
