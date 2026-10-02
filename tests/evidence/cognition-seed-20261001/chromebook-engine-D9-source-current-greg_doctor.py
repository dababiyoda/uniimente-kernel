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
    "ortools": ["cognition.solve: cortex CP-SAT engine and schedules", "lp.optimize (GLOP)"],
    "scipy": ["graph.shortest_path", "graph.max_flow", "lp.optimize (HiGHS)", "#140 game and evolutionary"],
    "networkx": ["graph.shortest_path", "graph.max_flow", "#140 graph operations"],
    "sympy": ["#140 exact arithmetic and polynomials"],
}


def engines() -> dict:
    """Which open-source reasoning engines this interpreter carries, read from installed metadata only."""
    from greg import mechanisms
    rows = []
    for name, uses in ENGINE_USES.items():
        dist = mechanisms.installed(name)
        rows.append({"distribution": name, "installed": dist is not None, "version": dist.version if dist else None,
                     "license": mechanisms.license_of(dist) if dist else None, "serves": uses})
    missing = [r["distribution"] for r in rows if not r["installed"]]
    return {"present": len(rows) - len(missing), "total": len(rows), "missing": missing, "engines": rows,
            "note": "not prerequisites: a missing engine makes its functions abstain and GREG asks; GREG never "
                    "installs one (the founder-run installer does, unless --no-engines)"}


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
