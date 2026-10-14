"""Competency characterization harness (directive section 5): measured behavioral profiles per family.

Each family gets a native workload: a generator of instances whose correct answer is known by
construction. The harness measures what applies to a stateless bounded solver behind GREG's verifier:

* responsiveness: end-to-end latency through `reason()` (the canonical cognition entry), as percentiles;
* error_correction: the share of corrupted answers the independent verifier refutes. A corruption
  changes the answer's primary field and mirrors the change into the proof artifact wherever the same
  key appears, so the lie is self-consistent and checks that only compare the answer with its artifact
  cannot see it;
* problem_space: the largest rung of a size ladder answered correctly within the default latency limit;
* generalization: whether answers stay the same when names are changed and the order of constraints or
  edges is reversed, which leaves the meaning untouched.

Rates carry Wilson 95% intervals. Correlated-failure evidence is read from the family's own receipts: the
verifier's independence statement and its cross-checks. Memory depth, persistence, prediction horizon,
adaptability, cooperation and higher-scale coherence are reported as not applicable, with the reason and
where the evidence lives instead. These are behavioral profiles on synthetic workloads, not consciousness
scores and not claims about real-world inputs.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from fractions import Fraction
import json
import math
import statistics
import time

from .verification import verify

VERSION = "greg-characterization/1"
NOT_APPLICABLE = {
    "memory_depth": "stateless per call; retained history is the body's journal (restart and replay are tested separately)",
    "persistence": "the body's property, not the solver's; see the kill -9 and restart integration tests",
    "prediction_horizon": "no forecast is produced by these families",
    "adaptability": "no online update inside a family; routing adapts from settled outcomes (learned_routing)",
    "cooperation": "measured for compositions, not single families; see the P6 composition-lift evidence",
    "higher_scale_coherence": "unmeasured for single families; the P6 VPL measurement is the relevant evidence",
}


def _rename(name: str) -> str:
    return "v_" + name


def _linear(n):
    return {"variables": {f"x{i}": [0, 10] for i in range(n)},
            "constraints": [{"coefficients": {f"x{i}": 1 for i in range(n)}, "op": ">=", "rhs": 5}]}


def _renamed_linear(data):
    out = {"variables": {_rename(k): v for k, v in data["variables"].items()},
           "constraints": [{**c, "coefficients": {_rename(k): v for k, v in c["coefficients"].items()}}
                           for c in reversed(data["constraints"])]}
    if "objective" in data:
        out["objective"] = {**data["objective"],
                            "coefficients": {_rename(k): v for k, v in data["objective"]["coefficients"].items()}}
    return out


def _chain(n):
    edges = [[f"a{i}", f"a{i + 1}", 1] for i in range(n)] + [["a0", f"a{n}", n + 1]]
    return {"edges": edges, "start": "a0", "goal": f"a{n}"}


def _renamed_chain(data):
    return {"edges": [[_rename(a), _rename(b), w] for a, b, w in reversed(data["edges"])],
            "start": _rename(data["start"]), "goal": _rename(data["goal"])}


# family -> (operation, generator(n) -> (data, truth), primary output field, rename/reorder transform, ladder)
WORKLOADS = {
    "exact": ("calculate",
              lambda n: ({"expression": " + ".join(f"{i}/{i + 1}" for i in range(1, n + 1))},
                         str(sum(Fraction(i, i + 1) for i in range(1, n + 1)))),
              "exact", lambda d: {"expression": " + ".join(reversed(d["expression"].split(" + ")))},
              (1, 4, 16, 64)),
    "estimation": ("estimate",
                   lambda n: ({"factors": [{"name": f"f{i}", "low": 1, "central": 2, "high": 3} for i in range(n)]}, 2 ** n),
                   "central", lambda d: {"factors": [{**f, "name": _rename(f["name"])} for f in reversed(d["factors"])]},
                   (1, 4, 8, 16)),
    "formal": ("constraints", lambda n: (_linear(n), "SAT"), "solver_status", _renamed_linear, (1, 4, 16, 64)),
    "optimization": ("optimize",
                     lambda n: ({**_linear(n), "objective": {"coefficients": {f"x{i}": i + 1 for i in range(n)},
                                                             "sense": "min"}}, 5),
                     "objective_value", _renamed_linear, (1, 4, 16, 64)),
    "graph": ("shortest_path", lambda n: (_chain(n), n), "cost", _renamed_chain, (1, 8, 64, 256)),
    "causal": ("treatment_effect",
               lambda n: ({"design": "randomized", "treated": [4, 6] * n, "control": [1, 3] * n, "dag": [["X", "Y"]]}, 3),
               "effect", lambda d: {**d, "treated": list(reversed(d["treated"])), "control": list(reversed(d["control"]))},
               (1, 8, 64, 256)),
}


def wilson(successes: int, n: int, z: float = 1.959963984540054):
    if n == 0:
        return None
    p = successes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]


def _same(value, truth) -> bool:
    if isinstance(truth, (int, float)) and isinstance(value, (int, float)):
        return math.isclose(float(value), float(truth), rel_tol=1e-9, abs_tol=1e-9)
    return value == truth


def _wrong(value):
    if isinstance(value, bool) or value is None:
        return "corrupted"
    if isinstance(value, (int, float)):
        return value + 1
    if isinstance(value, str):
        return {"SAT": "UNSAT", "UNSAT": "SAT"}.get(value, value + "1")
    return "corrupted"


def _mirror(obj, field, value):
    """Replace `field` wherever it appears in a nested artifact, keeping the lie self-consistent."""
    if isinstance(obj, dict):
        return {k: (value if k == field else _mirror(v, field, value)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_mirror(v, field, value) for v in obj]
    return obj


def _call(reason, registry, family, operation, data):
    started = time.monotonic()
    receipt = reason({"problem_id": f"characterize:{family}", "operation": operation, "data": deepcopy(data)},
                     registry=registry)
    return receipt, time.monotonic() - started


def _environment() -> dict:
    import platform
    from importlib import metadata
    versions = {}
    for package in ("ortools", "z3-solver", "networkx", "sympy", "scipy"):
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = None
    return {"python": platform.python_version(), "platform": platform.platform(), "packages": versions}


def characterize(families=None, *, repeats: int = 5, quick: bool = False) -> dict:
    from .cortex import reason, registry_view
    registry = registry_view()
    report = {"version": VERSION, "families": {}, "not_applicable": NOT_APPLICABLE, "environment": _environment(),
              "limits": "synthetic native workloads with answers known by construction; one machine; latency is "
                        "environment-dependent; corruptions are a declared model, not every possible lie",
              "authority_created": False}
    for family in families or WORKLOADS:
        operation, generate, field, transform, ladder = WORKLOADS[family]
        ladder = ladder[:2] if quick else ladder
        latencies, ladder_rows, corrections, invariant, receipts = [], [], [], [], []
        for n in ladder:
            data, truth = generate(n)
            receipt, wall = _call(reason, registry, family, operation, data)
            answered = receipt["abstention_state"] == "NONE"
            correct = answered and _same((receipt["output"] or {}).get(field), truth)
            ladder_rows.append({"size": n, "answered": answered, "correct": correct, "wall_seconds": round(wall, 4),
                                "state": receipt["abstention_state"]})
            receipts.append(receipt)
            if not correct:
                continue
            twin, _ = _call(reason, registry, family, operation, transform(data))
            invariant.append(twin["abstention_state"] == "NONE" and _same((twin["output"] or {}).get(field), truth))
            lie_value = _wrong(receipt["output"][field])
            lie = {"output": {**receipt["output"], field: lie_value},
                   "proof": _mirror(receipt["proof_artifact"], field, lie_value),
                   "status": "ANSWER", "formal_validity": receipt["formal_validity"]}
            try:
                verdict = verify(family, data, lie, receipt["proof_type"])["verdict"]
            except Exception as exc:  # a verifier that crashes on a lie has not refuted it
                verdict = f"ERROR:{type(exc).__name__}"
            corrections.append(verdict == "REFUTED")
        base, _ = generate(ladder[0])
        for _ in range(1 if quick else repeats):
            receipt, wall = _call(reason, registry, family, operation, base)
            latencies.append(wall)
        largest = max((r["size"] for r in ladder_rows if r["correct"]), default=None)
        independence = {r["evaluator_result"].get("independence") for r in receipts if r.get("evaluator_result")}
        cross = sorted({k for r in receipts for k in (r.get("evaluator_result") or {}).get("cross_checks", {})})
        unavailable = all(r["state"] == "CAPABILITY_DEFICIT" for r in ladder_rows)
        report["families"][family] = {
            "operation": operation,
            "available": not unavailable,
            "responsiveness": {"n": len(latencies), "p50_seconds": round(statistics.median(latencies), 4),
                               "max_seconds": round(max(latencies), 4)},
            "error_correction": {"refuted": sum(corrections), "n": len(corrections),
                                 "rate_wilson95": wilson(sum(corrections), len(corrections)),
                                 "corruption_model": f"primary field `{field}` changed and mirrored into the artifact"},
            "problem_space": {"ladder": ladder_rows, "largest_correct_size": largest},
            "generalization": {"invariant": sum(invariant), "n": len(invariant),
                               "rate_wilson95": wilson(sum(invariant), len(invariant)),
                               "transform": "renamed identifiers and reversed order"},
            "correlated_failure_evidence": {"verifier_independence": sorted(i for i in independence if i),
                                            "cross_checks": cross},
        }
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--family", action="append")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    report = characterize(args.family, quick=args.quick)
    text = json.dumps(report, indent=1)
    if args.out:
        with open(args.out, "w") as handle:
            handle.write(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
