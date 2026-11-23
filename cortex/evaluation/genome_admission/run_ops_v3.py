"""Operation-family admission v3: a live re-admission harness for PR #155's operation families (review of #179, M17).

Why: #155's frozen runners (``run.py``, ``run_v2.py``, ``pr155_crowd_sparse/run.py``) refuse to report on the
converged tree (``FROZEN_INPUT_CHANGED``), as their freezes intend, and #158's admission harness enumerates genome
executables only. Without a harness, a positive operation verdict whose code closure drifts can never be restored,
only demoted. This runner re-measures the same native benchmarks on the current tree, on fresh seeds, under a
freeze that binds the exact solver closures it measures.

What is reused unchanged (imported, not copied): every benchmark generator, arm, metric and per-module solver
geometry from v1 (``run.BENCHMARKS``), v2 (``run_v2.BENCHMARKS``) and the sparse-crowd test
(``pr155_crowd_sparse.run.bench``), and v1's frozen status rule (``run.status``). Nothing is tuned; the only
declared changes are the seeds (5001-5040, never generated before by any suite in this repository) and the
binding of each family's solver closure (``greg.cognition.code_binding``) into the freeze.

Known limitation, declared before the run: v1's ``collective`` baseline uses the generator's hidden observer
accuracies and is not deployable (review of #179, M3). It is replicated unchanged; the index's erratum on a
REJECTED reading continues to apply.

Procedure (pre-registered in ``prereg-ops-v3.json``): commit this runner and the pre-registration; in a clean
tree, ``--freeze`` writes ``freeze-ops-v3.json`` (refuses to overwrite); commit it; run once from a clean tree at
the freeze commit; the run refuses when the tree is dirty or any frozen input (file digest, solver closure, seed
range, family list, rule) differs.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from cortex.evaluation.genome_admission import run as V1  # noqa: E402
from cortex.evaluation.genome_admission import run_v2 as V2  # noqa: E402
from cortex.evaluation.pr155_crowd_sparse import run as SPARSE  # noqa: E402

SEEDS = range(5001, 5041)
MANIFEST = HERE / "freeze-ops-v3.json"
PREREG = HERE / "prereg-ops-v3.json"
FROZEN_FILES = ["cortex/evaluation/genome_admission/run_ops_v3.py", "cortex/evaluation/genome_admission/run.py",
                "cortex/evaluation/genome_admission/run_v2.py", "cortex/evaluation/pr155_crowd_sparse/run.py",
                "cortex/evaluation/genome_admission/prereg-ops-v3.json", "greg/cognition/repertoire.py",
                "greg/cognition/solvers.py"]
# family -> (benchmark, source module label); v2's crowd geometry is the family row, the sparse geometry is a second
# row for the same family, reported apart (``crowd_sparse``) exactly as #155's lineage ran it.
BENCHMARKS = {**{f: (b, "v1") for f, b in V1.BENCHMARKS.items()}, **{f: (b, "v2") for f, b in V2.BENCHMARKS.items()}}
SPARSE_NAMES = ("Dawid-Skene (crowd)", "majority vote", "one-step agreement-weighted vote", "oracle Bayes posterior")
DEPENDENCIES = ("numpy", "scipy", "networkx", "ortools", "z3-solver")


def closures() -> dict:
    """Each benchmarked family's solver as it is dispatched now, with its static dependency closure digest."""
    from greg.cognition.compiler import solver_code
    out = {}
    for family in sorted(BENCHMARKS):
        code = solver_code(family)
        out[family] = None if code is None else {"path": code["path"], "function": code["function"],
                                                 "closure_sha256": code["closure_sha256"]}
    return out


def inputs() -> dict:
    return {"files": {p: "sha256:" + hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in FROZEN_FILES},
            "solver_closures": closures(), "seeds": [SEEDS.start, SEEDS.stop - 1],
            "families": sorted(BENCHMARKS), "subgeometries": ["crowd_sparse"],
            "structural": {k: v[0] for k, v in V1.STRUCTURAL.items()}, "rule": "run.status (v1, frozen)"}


def dirty() -> list[str]:
    out = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, capture_output=True,
                         text=True, check=True).stdout
    return [line for line in out.splitlines() if line.strip()]


def _versions() -> dict:
    found = {}
    for name in DEPENDENCIES:
        try:
            found[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            found[name] = None
    return {"python": platform.python_version(), **found}


def _row(rows: list[dict], names: tuple) -> dict:
    scored = [{k: r.get(k) for k in ("candidate", "baseline", "competitor")} for r in rows]
    finite = lambda k: [r[k] for r in rows if r.get(k) is not None and math.isfinite(r[k])]  # noqa: E731
    reference = None
    if len(names) > 3 and names[3] and all(r.get("reference") is not None for r in rows):
        w = sum(1 for r in rows if r["candidate"] < r["reference"] - 1e-9)
        l = sum(1 for r in rows if r["reference"] < r["candidate"] - 1e-9)
        reference = {"name": names[3], "wins": w, "losses": l, "mean": round(statistics.fmean(
            r["reference"] for r in rows), 6)}
    return {"candidate": names[0], "baseline": names[1], "competitor": names[2], "n": len(rows),
            **V1.status(scored), "reference_not_in_rule": reference,
            "mean_metric": {k: (round(statistics.fmean(finite(k)), 6) if finite(k) else None)
                            for k in ("candidate", "baseline", "competitor")},
            "median_seconds": (round(statistics.median(r["seconds"] for r in rows), 5)
                               if all("seconds" in r for r in rows) else None),
            "per_item": [{k: (round(v, 9) if isinstance(v, float) else v) for k, v in r.items()
                          if k not in ("names", "kinds")} for r in rows]}


def measure(seeds=SEEDS) -> dict:
    """Every benchmarked family and the sparse-crowd geometry on ``seeds``; v1's status rule per row."""
    families = {}
    for family, (bench, origin) in BENCHMARKS.items():
        rows = [bench(seed) for seed in seeds]
        families[family] = {"benchmark": origin, **_row(rows, rows[0]["names"])}
    for family, (verdict, why) in V1.STRUCTURAL.items():
        families.setdefault(family, {"status": verdict, "reason": why})
    sparse_rows = []
    for seed in seeds:
        started = time.perf_counter()
        row = SPARSE.bench(seed)
        sparse_rows.append({**row, "seconds": time.perf_counter() - started})
    return {"families": families, "crowd_sparse": {"benchmark": "pr155_crowd_sparse", **_row(sparse_rows,
                                                                                             SPARSE_NAMES)}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    if dirty():
        raise SystemExit("DIRTY_TREE: commit or discard tracked changes first\n" + "\n".join(dirty()))
    if args.freeze:
        if MANIFEST.exists():
            raise SystemExit("refusing to overwrite an existing freeze; create a new version")
        MANIFEST.write_text(json.dumps({"frozen_at": datetime.now(timezone.utc).isoformat(), "inputs": inputs()},
                                       indent=2) + "\n")
        return
    if not MANIFEST.exists():
        raise SystemExit("NOT_FROZEN: run --freeze and commit the manifest first")
    if json.loads(MANIFEST.read_text())["inputs"] != inputs():
        raise SystemExit("FROZEN_INPUT_CHANGED: results cannot be reported")
    started = datetime.now(timezone.utc).isoformat()
    measured = measure()
    report = {"schema": "greg-operation-admission/3", "lineage": "PR #155 operation families, re-admitted on the "
              "converged tree", "manifest_sha256": "sha256:" + hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
              "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
              "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "seeds": [SEEDS.start, SEEDS.stop - 1], "environment": _versions(),
              "solver_closures": closures(), **measured}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({f: (v["status"], v.get("vs_baseline"), v.get("vs_competitor"))
                      for f, v in {**report["families"], "crowd_sparse": report["crowd_sparse"]}.items()}, indent=1))


if __name__ == "__main__":
    main()
