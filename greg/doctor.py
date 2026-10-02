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


FRONTIER_WORKERS = ("claude", "codex", "aider")


def frontier_workers(names=FRONTIER_WORKERS, which=None) -> dict:
    """Which temporary frontier worker CLIs are installed. Looks them up on PATH; never runs them."""
    which = which or shutil.which
    return {name: which(name) is not None for name in names}


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
            # informational only: not a readiness check, and presence grants no authority
            "frontier_workers_installed": frontier_workers(),
            **({"fix": {"python_venv_available": "sudo apt install python3-venv"}}
               if "python_venv_available" in missing else {}),
            "not_verified": ["ChromeOS host identity and ownership", "VM restart at login", "sleep continuity",
                             "founder identity", "real mission outcome"],
            "next": ("follow greg/CHROMEBOOK_FIRST_MISSION.md on the actual Chromebook" if not missing else
                     "resolve missing prerequisites on the Chromebook before creating a key or body")}
