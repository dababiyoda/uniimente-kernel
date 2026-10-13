"""Read-only prerequisite probe for a Chromebook Linux first body.

This checks the Linux environment that is actually running. It cannot determine
whether the ChromeOS host owns that environment, whether the VM survives sleep,
or whether the person at the keyboard is Alfonso. It creates no body or key.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import platform
import shutil
import subprocess
import sys

# Present inside ChromeOS's Linux (Crostini) container; informational, never an identity claim.
CROSTINI_MARKERS = ("/dev/.cros_milestone", "/opt/google/cros-containers")


def is_crostini(markers=CROSTINI_MARKERS) -> bool:
    return any(Path(marker).exists() for marker in markers)


# Engines are not prerequisites for N1: a missing one makes its functions abstain and GREG asks.
ENGINE_USES = {
    "z3-solver": ["cognition.solve: cortex formal engine and schedules", "#140 formal operations"],
    "ortools": ["cognition.solve: cortex CP-SAT engine and schedules", "lp.optimize (GLOP)", "assignment.optimize", "flow.min_cost"],
    "scipy": ["graph.shortest_path", "graph.max_flow", "graph.spanning_tree", "lp.optimize (HiGHS)", "assignment.optimize",
              "#140 game and evolutionary"],
    "networkx": ["graph.shortest_path", "graph.max_flow", "graph.spanning_tree", "flow.min_cost", "#140 graph operations"],
    "sympy": ["#140 exact arithmetic and polynomials"],
}


# What a worker imports. Workers run ``python -I``, which ignores user site-packages, so an engine the
# metadata calls installed can still be unusable to them (seen in a container whose pandas found
# ``dateutil`` only in ~/.local). The probe imports exactly these modules the same way.
ENGINE_MODULES = {
    "z3-solver": ("z3",),
    "ortools": ("ortools.sat.python.cp_model", "ortools.linear_solver.pywraplp"),
    "scipy": ("scipy.optimize", "scipy.sparse.csgraph"),
    "networkx": ("networkx",),
    "sympy": ("sympy",),
}
IMPORT_PROBE = ("import importlib, json, sys\n"
                "out = {}\n"
                "for name in json.loads(sys.argv[1]):\n"
                "    try:\n"
                "        importlib.import_module(name)\n"
                "        out[name] = None\n"
                "    except Exception as exc:\n"
                "        out[name] = (type(exc).__name__ + ': ' + str(exc))[:200]\n"
                "print(json.dumps(out))\n")


def importable(modules) -> dict:
    """Import each module in an isolated interpreter, as workers do; None means it imported."""
    import json
    modules = list(modules)
    try:
        proc = subprocess.run([sys.executable, "-I", "-c", IMPORT_PROBE, json.dumps(modules)],
                              capture_output=True, text=True, timeout=180)
        found = json.loads(proc.stdout.strip().splitlines()[-1])
        return {m: found.get(m, "not reported by the probe") for m in modules}
    except Exception as exc:  # the report must not crash the doctor
        return {m: f"probe failed: {type(exc).__name__}" for m in modules}


def engines() -> dict:
    """Which open-source reasoning engines this body carries and its isolated workers can import."""
    from greg import mechanisms
    dists = {name: mechanisms.installed(name) for name in ENGINE_USES}
    probed = importable(m for name, dist in dists.items() if dist for m in ENGINE_MODULES[name])
    rows = []
    for name, uses in ENGINE_USES.items():
        dist = dists[name]
        errors = [f"{m}: {probed[m]}" for m in ENGINE_MODULES[name] if dist and probed.get(m)]
        rows.append({"distribution": name, "installed": dist is not None, "version": dist.version if dist else None,
                     "license": mechanisms.license_of(dist) if dist else None, "serves": uses,
                     "importable": dist is not None and not errors, "import_error": errors[0] if errors else None})
    missing = [r["distribution"] for r in rows if not r["installed"]]
    unusable = [r["distribution"] for r in rows if r["installed"] and not r["importable"]]
    return {"present": sum(r["importable"] for r in rows), "total": len(rows), "missing": missing,
            "unusable": unusable, "engines": rows,
            "note": "not prerequisites: a missing engine makes its functions abstain and GREG asks; GREG never "
                    "installs one (the founder-run installer does, unless --no-engines). Present means the "
                    "isolated interpreter GREG's workers use imports it; installed but unusable is reported "
                    "with the import error."}


def chromebook() -> dict:
    checks = {
        "python_3_11": sys.version_info >= (3, 11),
        # Debian in Crostini ships python3 without python3-venv; `python3 -m venv` then fails.
        "python_venv_available": importlib.util.find_spec("ensurepip") is not None,
        "linux_runtime": platform.system() == "Linux",
        "git_available": shutil.which("git") is not None,
        "systemctl_available": shutil.which("systemctl") is not None,
    }
    checks["user_service_available"] = False
    if checks["linux_runtime"] and checks["systemctl_available"]:
        try:
            result = subprocess.run(["systemctl", "--user", "show-environment"],
                                    capture_output=True, timeout=5, check=False)
            checks["user_service_available"] = result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            pass
    missing = [name for name, passed in checks.items() if not passed]
    return {"route": "Linux user-service prerequisites for the Chromebook candidate",
            "ready_for_linux_service": not missing,
            "checks": checks, "missing": missing,
            "crostini_detected": is_crostini(),
            "engines": engines(),
            **({"fix": {"python_venv_available": "sudo apt install python3-venv"}}
               if "python_venv_available" in missing else {}),
            "not_verified": ["ChromeOS host identity and ownership", "VM restart at login", "sleep continuity",
                             "founder identity", "real mission outcome"],
            "next": ("follow greg/CHROMEBOOK_FIRST_MISSION.md on the actual Chromebook" if not missing else
                     "resolve missing prerequisites on the Chromebook before creating a key or body")}
