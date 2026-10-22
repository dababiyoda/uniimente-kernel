"""P6 joined v1: re-measure the recipe lifts on the JOINED integration tree (claude/greg-full-machine-completion).

Why: on the joined tree every recipe verdict is stale. ``greg.cognition.compiler.recipe_stale`` names a changed recipe
closure for all seven recipes, because the joined ``cortex.reason`` (grant-window guard) and the composition and stage
solvers changed under the code P6 converged v1 measured at ``53d39d76``. Live VPL on this tree is therefore 0. The
founder's rule: bind verification to the actual integrated code, do not transfer old claims, preserve NO_LIFT.

This runner is deliberately thin. It imports ``run_converged_v1`` and reuses its generators, payloads, truths, arms,
scoring, sign test, verdict, summary, recipe bindings, dirty-tree check and frozen-input comparison unchanged. It
overrides only the experiment identity (this runner, ``prereg-joined-v1.json``, ``freeze-joined-v1.json``), the
evidence path and the held-out seeds, and its report adds the environment and the limits block v1 omitted.

Seeds (fresh, inside 4000-4999 as assigned to this lane): F1 4717-4756, F2R 4640-4703, F3 4809-4848, F4 4863-4902.
The check that chose them is disclosed in ``prereg-joined-v1.json`` (``seed_hygiene``).

Procedure (pre-registered): commit this runner and the pre-registration; in a clean tree ``--freeze`` writes
``freeze-joined-v1.json`` (file digests, the four recipes' complete code bindings, seeds, rule); commit it; run once
from a clean detached worktree at the freeze commit under ``python -I`` pinned to one core. The run refuses a dirty
tree, a missing freeze, any changed input, or a non-isolated interpreter.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
if str(ROOT) not in sys.path:               # python -I does not prepend the script directory
    sys.path.insert(0, str(ROOT))

import importlib.util  # noqa: E402

# A private instance of the v1 module: its code is executed unchanged, and only this instance's identity globals are
# overridden below, so importing this runner never changes ``run_converged_v1`` for anyone else.
_SPEC = importlib.util.spec_from_file_location("_p6_joined_v1_procedure", HERE / "run_converged_v1.py")
C = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(C)

MANIFEST = HERE / "freeze-joined-v1.json"
PREREG = HERE / "prereg-joined-v1.json"
EVIDENCE = ROOT / "docs/evidence/greg-composition-lift/2026-10-22-joined"
SEEDS = {"F1": range(4717, 4757), "F2R": range(4640, 4704), "F3": range(4809, 4849), "F4": range(4863, 4903)}
FROZEN_FILES = ["cortex/evaluation/composition_lift/run_joined_v1.py",
                "cortex/evaluation/composition_lift/prereg-joined-v1.json",
                *C.FROZEN_FILES]                 # v1's runner, its pre-registration and every code file it froze
LIMITS = [
    "F1, F2R, F3 and F4 are constructed to need two intelligences; they test the machinery on the joined code, "
    "not whether natural tasks need composition",
    "F1 truth assumes the stated intervals are calibrated lognormal 90% intervals",
    "the natural families (F5 M4, F6 bank calls, F7 SNDlib, F8 Uber) are not re-measured: their held-out data were "
    "already looked at",
    "one container, one pinned core; latency is this machine's under the contention recorded in environment; the "
    "compiled arm measured the compiler at the freeze commit",
]

# The identity overrides: every v1 function reads these globals of its (private) module instance.
C.MANIFEST, C.PREREG, C.SEEDS, C.FROZEN_FILES = MANIFEST, PREREG, SEEDS, FROZEN_FILES
CONSTITUENTS, RECIPE, RULE, EVAL_ATTACH = C.CONSTITUENTS, C.RECIPE, C.RULE, C.EVAL_ATTACH
generate, arms_for, inputs, bindings, dirty, measure = C.generate, C.arms_for, C.inputs, C.bindings, C.dirty, C.measure


def environment() -> dict:
    def read(path):
        try:
            return Path(path).read_text().strip()
        except OSError:
            return None
    cpu = next((line.split(":", 1)[1].strip() for line in (read("/proc/cpuinfo") or "").splitlines()
                if line.startswith("model name")), None)
    return {"python": platform.python_version(), "implementation": platform.python_implementation(),
            "executable": sys.executable, "isolated": bool(sys.flags.isolated), "platform": platform.platform(),
            "cpu_model": cpu, "cpu_count": os.cpu_count(),
            "affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
            "loadavg": read("/proc/loadavg"), "taskset": os.environ.get("P6_TASKSET"),
            "contention_note": os.environ.get("P6_CONTENTION")}


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
    if not sys.flags.isolated:
        raise SystemExit("NOT_ISOLATED: run under python -I")
    if args.out is None:
        raise SystemExit("--out is required for the run")
    env_start = environment()
    started = datetime.now(timezone.utc).isoformat()
    measured = measure(log=lambda line: print(line, flush=True))
    report = {"schema": "greg-composition-lift-joined/1",
              "manifest_sha256": "sha256:" + hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
              "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
              "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "environment": {**env_start, "loadavg_end": environment()["loadavg"]},
              "limits": LIMITS, "recipe_bindings": bindings(), **measured}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({f: {k: v for k, v in s.items() if k in ("lift", "best_constituent", "routed_wins",
                                                              "routed_losses", "sign_test_p_one_sided")}
                      for f, s in report["summary"].items() if f in SEEDS}, indent=1))


if __name__ == "__main__":
    main()
