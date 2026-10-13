"""Reproducible evidence for RECOMBINE (greg/recombine.py): stress and reuse measurement.

1. Stress: every reduction's frozen oracle for seeds 0..N-1, solved through every installed engine
   candidate in one isolated batch each, decoded and certified by GREG; counts mismatches.
2. Reuse: the cost of qualifying an engine (package Mechanism Card + frozen oracle + scale probe)
   versus constructing a new function over an engine that is already qualified and attached.

Usage: python scripts/qualify_recombine.py [out.json] [seeds]
Nothing is installed, downloaded, attached or sent; engines run in GREG's no-network runner.
"""
from __future__ import annotations

import importlib.metadata
import json
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from greg import genesis, mechanisms, recombine  # noqa: E402
from greg.capabilities import CapabilityRegistry  # noqa: E402


def candidates(function):
    for c in genesis.CATALOG[function]["candidates"]:
        dist = mechanisms.installed(c.distribution)
        yield c, dist


def stress(seeds: int) -> list[dict]:
    rows = []
    for function, reduction in recombine.REDUCTIONS.items():
        found = recombine.chain(function, genesis.CATALOG)
        path, engine = found
        if len(path) > 1:
            continue                     # chained functions are exercised end to end in the tests
        cases = [c for seed in range(seeds) for c in reduction.oracle(seed)]
        problems = [reduction.normalize(c["input"]) for c in cases]
        todo = [(c, p) for c, p in zip(cases, problems) if not (reduction.direct and reduction.direct(p))]
        spec = genesis.CATALOG[engine]
        for candidate, dist in candidates(engine):
            row = {"function": function, "engine": engine, "distribution": candidate.distribution,
                   "cases": len(cases), "proved_without_engine": len(cases) - len(todo)}
            if dist is None:
                rows.append({**row, "status": "not installed (GREG installs nothing)"})
                continue
            card = mechanisms.card(candidate, engine, dist)
            requests = [spec["normalize"](reduction.encode(p)) for _, p in todo]
            started = time.perf_counter()
            claims = mechanisms.run(candidate, spec["runners"][candidate.runner], requests,
                                    location=card["location"], version=card["version"], cpu_seconds=300)
            wall = time.perf_counter() - started
            wrong, refused = 0, 0
            for (case, problem), request, claim in zip(todo, requests, claims):
                try:
                    answer = reduction.certify(problem, reduction.decode(problem, spec["certify"](request, claim["result"])))
                    wrong += not reduction.judge(answer, case["expected"])
                except Exception:            # a refusal is counted, never hidden
                    refused += 1
            rows.append({**row, "status": "run", "version": card["version"], "engine_cases": len(todo),
                         "wrong": wrong, "refused": refused, "batch_seconds": round(wall, 2)})
    return rows


def reuse(seed: int = 11) -> dict:
    candidate, dist = next((c, d) for c, d in candidates("graph.max_flow") if d is not None)
    card = mechanisms.card(candidate, "graph.max_flow", dist)
    started = time.perf_counter()
    passed, report = genesis.qualify_package("graph.max_flow", candidate, card, seed)
    engine_seconds = time.perf_counter() - started
    g = genesis.Genesis.__new__(genesis.Genesis)
    manifest = g._package_manifest("graph.max_flow", candidate, card, "deficit-evidence", report)
    registry = CapabilityRegistry()
    registry.register(manifest, genesis.package_adapter("graph.max_flow", candidate), state="ATTACHED")
    out = {"engine": {"capability_id": manifest.capability_id, "qualified": passed,
                      "seconds": round(engine_seconds, 2), "oracle_cases": report["cases"],
                      "scale_probe": report["scale_probe"]}, "constructions": []}
    for function in ("assignment.staffing", "assignment.matching"):
        path, _ = recombine.chain(function, genesis.CATALOG)
        composed = g._composed_manifest(function, path, manifest, "deficit-evidence")
        adapter = recombine.composed_adapter(path, registry)
        started = time.perf_counter()
        ok, rep = recombine.qualify(path, adapter, composed, seed)
        out["constructions"].append({"function": function, "chain": rep["chain"], "qualified": ok,
                                     "seconds": round(time.perf_counter() - started, 2), "oracle_cases": rep["cases"],
                                     "engine_calls": rep["engine_calls"], "engine_requalified": False,
                                     "new_solver_code_lines": 0})
    return out


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs/evidence/greg-recombine/2026-10-13/results.json"
    seeds = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    versions = {}
    for name in ("networkx", "scipy", "numpy", "ortools"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    result = {"generated_by": "scripts/qualify_recombine.py", "seeds": seeds,
              "environment": {"python": platform.python_version(), "platform": sys.platform, "packages": versions},
              "reductions": {r.reduction_id: recombine.source_digest(r) for r in recombine.REDUCTIONS.values()},
              "stress": stress(seeds), "reuse": reuse(),
              "limits": ["timings are one run on a shared CI-class container, indicative only",
                         "chained functions (matching) are covered end to end by tests, not by the batch stress"]}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"stress": result["stress"], "reuse": result["reuse"]}, indent=1))


if __name__ == "__main__":
    main()
