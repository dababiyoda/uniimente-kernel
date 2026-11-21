"""Probe for #217: does a certifier call a suboptimal on-time plan the cheapest when an engine hands it back
with the optimum's real prices?

For random small projects whose durations sit at 10**scale (the spans stay small, so exhaustive enumeration
is cheap), SciPy's HiGHS solves the time-cost LP once through GREG's own runner. Its certified prices are
kept, and every other on-time integer plan is offered in place of the engine's plan, as an engine that
drifts to another vertex would. Each certifier is asked whether that plan is the cheapest:

    before  greg/recombine.py at #196's 917404cf: plan cost against the LP objective at the engine's point,
            after GREG's LP certificate with its relative 1e-7 gap tolerance;
    after   this tree: plan cost against the exact deadline-flow bound.

Usage: python docs/evidence/greg-crash-certificate/2026-10-28/false_optimum_probe.py BEFORE_RECOMBINE_PY [out.json]
BEFORE_RECOMBINE_PY is `git show 917404cf:greg/recombine.py` saved to a file. Nothing is sent or installed.
"""
from __future__ import annotations

import importlib.util
import itertools
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from greg import recombine as after  # noqa: E402
from greg.cognition import linear  # noqa: E402


def load_before(path: str):
    spec = importlib.util.spec_from_file_location("recombine_before", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["recombine_before"] = module            # dataclasses resolves annotations through it
    spec.loader.exec_module(module)
    return module


def project(rng, scale):
    n = rng.randint(1, 4)
    tasks = []
    for k in range(n):
        d = rng.randint(1, 4)
        tasks.append({"id": f"T{k}", "duration": d + 10 ** scale, "min_duration": d - rng.randint(0, d) + 10 ** scale,
                      "cost_per_unit": rng.randint(1, 9)})
    precedences = [[f"T{a}", f"T{b}"] for a in range(n) for b in range(a + 1, n) if rng.random() < 0.5]
    normal = after._longest({"order": [t["id"] for t in tasks], "precedences": precedences},
                            {t["id"]: t["duration"] for t in tasks})[0]
    return {"tasks": tasks, "precedences": precedences, "deadline": max(0, normal - rng.randint(0, 6))}


def on_time_plans(p):
    """Every integer shortening that meets the deadline, as an earliest-start schedule, with its cost."""
    preds = {t[0]: [a for a, b in p["precedences"] if b == t[0]] for t in p["tasks"]}
    for crash in itertools.product(*[range(d - s + 1) for _, d, s, _ in p["tasks"]]):
        durations = {t[0]: t[1] - x for t, x in zip(p["tasks"], crash)}
        finish = {}
        for t in p["order"]:
            finish[t] = max((finish[a] for a in preds[t]), default=0) + durations[t]
        if max(finish.values()) <= p["deadline"]:
            yield ({t: (finish[t] - durations[t], finish[t]) for t in finish},
                   sum(t[3] * x for t, x in zip(p["tasks"], crash)))


def main():
    before = load_before(sys.argv[1])
    namespace = {"MODULE": importlib.import_module("scipy.optimize")}
    exec(linear.RUNNERS["scipy.lp"], namespace)
    solve = namespace["solve"]
    rows = []
    for scale in (0, 4, 6, 7, 8):
        rng = random.Random(21700 + scale)
        tally = {"duration_offset": 10 ** scale, "projects": 0, "plans_offered": 0, "suboptimal_offered": 0,
                 "before_called_cheapest_when_not": 0, "after_called_cheapest_when_not": 0,
                 "before_refused_the_optimum": 0, "after_refused_the_optimum": 0}
        while tally["projects"] < 40:
            params = project(rng, scale)
            p_after, p_before = after.normalize_crash(params), before.normalize_crash(params)
            if after.direct_crash(p_after) is not None:
                continue
            tally["projects"] += 1
            best = after.crash_brute_force(p_after)
            req_a = linear.normalize_lp(after.encode_crash(p_after))
            req_b = linear.normalize_lp(before.encode_crash(p_before))
            claim_a, claim_b = solve(req_a), solve(req_b)
            position = {t[0]: i for i, t in enumerate(p_after["tasks"])}
            for timing, cost in on_time_plans(p_after):
                x = [0.0] * (2 * len(timing))
                for t, (s, f) in timing.items():
                    x[2 * position[t]], x[2 * position[t] + 1] = float(s), float(f)
                tally["plans_offered"] += 1
                tally["suboptimal_offered"] += cost != best
                for name, module, p, req, claim in (("before", before, p_before, req_b, claim_b),
                                                    ("after", after, p_after, req_a, claim_a)):
                    try:
                        lp = linear.certify_lp(req, {**claim, "x": x})
                        called = module.certify_crash(p, module.decode_crash(p, lp))["cost"] == cost
                    except (linear.CertificateError, module.ReductionError):
                        called = False
                    if called and cost != best:
                        tally[f"{name}_called_cheapest_when_not"] += 1
                    if not called and cost == best:
                        tally[f"{name}_refused_the_optimum"] += 1
        rows.append(tally)
        print(json.dumps(tally))
    out = {"generated_by": "docs/evidence/greg-crash-certificate/2026-10-28/false_optimum_probe.py",
           "engine": "scipy.lp (HiGHS) through GREG's runner, in-process", "rows": rows}
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(json.dumps(out, indent=1) + "\n")


if __name__ == "__main__":
    main()
