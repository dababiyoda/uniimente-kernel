"""P8 candidate sandbox: run one candidate configuration on problem INPUTS only, then exit.

The parent (``greg/cognition/evolution.py``) builds every request itself; a candidate is a validated
configuration (data), never code. This process parses the request, imports the one reviewed method its
target names from the TARGETS allow-list, then irreversibly confines itself with Landlock before it runs
anything on the problems, so nothing it runs can open repository files - in particular the evaluator's real
outcomes, which never enter this process at all. Output: outputs per problem id, with {"confined": ...}
recorded so the parent can refuse unconfined runs where confinement is required.
"""
from __future__ import annotations

import json
from pathlib import Path
import resource
import sys
import tempfile

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import importlib  # noqa: E402
from greg.cognition.genomes.contract import GenomeError  # noqa: E402
from greg import isolation  # noqa: E402

# The only code a cycle can run: reviewed modules and functions, named by the trusted parent's target.
TARGETS = {"forecast_quantile": ("greg.cognition.genomes.forecasting", "solve_with"),
           "immune_detect": ("greg.cognition.genomes.collective", "immune_solve_with")}


def main():
    request = json.loads(sys.stdin.read(64 * 1024 * 1024))
    if request.get("target") not in TARGETS:
        print(json.dumps({"confined": None, "error": "UNKNOWN_TARGET"}))
        return
    module, function = TARGETS[request["target"]]
    method = getattr(importlib.import_module(module), function)      # imported BEFORE confinement
    resource.setrlimit(resource.RLIMIT_CPU, (120, 121))
    scratch = tempfile.mkdtemp(prefix="greg-p8-")
    confined = None
    if request.get("confine", True):
        try:
            confined = isolation.confine(scratch, [])
        except isolation.IsolationError as exc:
            print(json.dumps({"confined": None, "error": f"CONFINEMENT_UNAVAILABLE: {exc}"}))
            return
    probe = request.get("probe_read")            # test-only: report whether a path is readable, never its bytes
    probe_result = None
    if probe:
        try:
            with open(probe, "rb") as fh:
                fh.read(1)
            probe_result = "READ"
        except OSError as exc:
            probe_result = f"DENIED:{type(exc).__name__}"
    outputs = {}
    for problem in request["problems"]:
        try:
            out = method(request["config"], problem["data"])
            outputs[problem["id"]] = {"output": out["output"], "certificate": out["certificate"]}
        except (GenomeError, ValueError, ZeroDivisionError, OverflowError) as exc:
            outputs[problem["id"]] = {"error": f"{type(exc).__name__}: {str(exc)[:160]}"}
    print(json.dumps({"confined": confined, "probe": probe_result, "outputs": outputs}))


if __name__ == "__main__":
    main()
