"""Deterministic local CLI worker for the one-machine test. A TEST DOUBLE, never a frontier worker.

GREG runs it exactly like any headless agent CLI (``greg.workers.CliAgentWorker``): the WorkOrder
prompt arrives on stdin, the process runs in a private clone with a scrubbed environment and
dies with the body (PR_SET_PDEATHSIG). What it writes is a claim; GREG collects the diff, runs the
acceptance with no network, and ``worker.appraise`` re-checks it in a fresh clone.

It does real, inspectable work from the bound context: it records the certified assignment and a
test that re-checks it against ``problem.json`` from first principles, including an exhaustive
search that no feasible assignment staffs more. It does not import GREG.

Test control: a file next to this script, outside any clone, read only.
  HOLD      present -> stay in progress until killed (the test finds this process in /proc)
The worker writes nothing outside its clone: where Landlock confines workers it could not, and the
test observes it from outside instead (its process, and GREG's own dispatch records).
"""
import json
import os
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
MARK = "CERTIFIED_PLAN_JSON:\n"

TEST = '''"""Re-check the recorded plan against problem.json from first principles (no GREG import)."""
import itertools
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBLEM = json.loads((ROOT / "problem.json").read_text())
PLAN = json.loads((ROOT / "plan" / "plan.json").read_text())
WORKERS = {w["id"]: w for w in PROBLEM["workers"]}
ORDERS = {o["id"]: o for o in PROBLEM["orders"]}


def test_every_assignment_is_feasible():
    used, served = {}, {}
    for worker, order, units in PLAN["assignment"]:
        assert units > 0 and ORDERS[order]["skill"] in WORKERS[worker]["skills"]
        used[worker] = used.get(worker, 0) + units
        served[order] = served.get(order, 0) + units
    assert all(used[w] <= WORKERS[w]["capacity"] for w in used)
    assert all(served[o] <= ORDERS[o]["demand"] for o in served)
    assert sum(served.values()) == PLAN["staffed"]


def test_no_feasible_assignment_staffs_more():
    pairs = [(w, o) for w in WORKERS for o in ORDERS if ORDERS[o]["skill"] in WORKERS[w]["skills"]]
    ranges = [range(min(WORKERS[w]["capacity"], ORDERS[o]["demand"]) + 1) for w, o in pairs]
    best = 0
    for units in itertools.product(*ranges):
        used, served = {}, {}
        for (w, o), u in zip(pairs, units):
            used[w] = used.get(w, 0) + u
            served[o] = served.get(o, 0) + u
        if all(used[w] <= WORKERS[w]["capacity"] for w in used) and \\
                all(served[o] <= ORDERS[o]["demand"] for o in served):
            best = max(best, sum(units))
    assert PLAN["staffed"] == best
'''


def main() -> int:
    prompt = sys.stdin.read()
    if (HERE / "HOLD").exists():
        time.sleep(600)                      # in progress until the body (and so this process) is killed
        return 3
    if MARK not in prompt:
        print("no certified plan in the order context; refusing to invent one")
        return 2
    raw = prompt.split(MARK, 1)[1].split("\n\nWhen finished", 1)[0]
    result = json.loads(raw)
    Path("plan").mkdir(exist_ok=True)
    Path("plan/plan.json").write_text(json.dumps({"assignment": result["assignment"], "staffed": result["staffed"],
                                                  "certificate": result["certificate"]["kind"],
                                                  "source": "bound from GREG's competency compiler receipt"},
                                                 indent=1) + "\n")
    Path("tests").mkdir(exist_ok=True)
    Path("tests/test_plan.py").write_text(TEST)
    print('WORK_REPORT: {"changed": ["plan/plan.json", "tests/test_plan.py"], "tests_run": [], '
          '"unresolved": [], "confidence": 0.9}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
