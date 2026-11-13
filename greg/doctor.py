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


def device_class(markers=CROSTINI_MARKERS) -> str:
    """The observed kind of device, recorded beside ``platform``. Informational and forgeable (a marker
    path or a patched interpreter changes it): never an identity, ownership or VEPMC condition."""
    system = platform.system()
    if system == "Darwin":
        return "macos"
    if system == "Linux":
        return "chromeos_linux" if is_crostini(markers) else "linux_other"
    return "other"


# Engines are not prerequisites for N1: a missing one makes its functions abstain and GREG asks.
ENGINE_USES = {
    "z3-solver": ["cognition.solve: cortex formal engine and schedules", "#140 formal operations"],
    "ortools": ["cognition.solve: cortex CP-SAT engine and schedules", "lp.optimize (GLOP)"],
    "scipy": ["graph.shortest_path", "graph.max_flow", "lp.optimize (HiGHS)", "#140 game and evolutionary"],
    "networkx": ["graph.shortest_path", "graph.max_flow", "#140 graph operations"],
    "sympy": ["#140 exact arithmetic and polynomials"],
}


# Where the pinned engine's only Linux wheel for a CPU needs a newer glibc than Debian 12's 2.36 (ChromeOS Linux's
# base), read from the files PyPI lists for the pinned release (requirements-cortex.txt z3-solver==5.1.0.0:
# manylinux_2_27_x86_64 and manylinux_2_38_aarch64; checked 2026-10-28). The installer never compiles an engine, so
# such a machine has no wheel to install. Explains a missing engine; never a reason to install another version.
WHEEL_GLIBC_FLOOR = {("z3-solver", "aarch64"): (2, 38)}


def _glibc() -> tuple[int, ...] | None:
    lib, version = platform.libc_ver()
    try:
        return tuple(int(part) for part in version.split(".")[:2]) if lib == "glibc" and version else None
    except ValueError:
        return None


def engines() -> dict:
    """Which open-source reasoning engines this interpreter carries, read from installed metadata only."""
    from greg import mechanisms
    machine, glibc = platform.machine().lower(), _glibc()
    machine = {"arm64": "aarch64"}.get(machine, machine)
    rows = []
    for name, uses in ENGINE_USES.items():
        dist = mechanisms.installed(name)
        row = {"distribution": name, "installed": dist is not None, "version": dist.version if dist else None,
               "license": mechanisms.license_of(dist) if dist else None, "serves": uses}
        floor = WHEEL_GLIBC_FLOOR.get((name, machine))
        if dist is None and floor and glibc is not None and glibc < floor:
            row["why_missing"] = (f"no binary wheel for this machine: the pinned {name}'s Linux {machine} wheel needs "
                                  f"glibc {'.'.join(map(str, floor))}, this system has {'.'.join(map(str, glibc))}; "
                                  f"its functions abstain and GREG asks before one is needed")
        rows.append(row)
    missing = [r["distribution"] for r in rows if not r["installed"]]
    return {"present": len(rows) - len(missing), "total": len(rows), "missing": missing, "engines": rows,
            "platform": {"machine": machine, "glibc": ".".join(map(str, glibc)) if glibc else None},
            "note": "not prerequisites: a missing engine makes its functions abstain and GREG asks; GREG never "
                    "installs one (the founder-run installer does, unless --no-engines)"}


def worker_isolation() -> dict:
    """Whether this host can confine coding workers and their acceptance tests (bubblewrap namespaces).

    Not a prerequisite for the body: without it, ``worker.commission`` refuses to dispatch rather than run a
    worker or its tests with GREG's own reach. Probing runs ``/usr/bin/true`` in a namespace; nothing else."""
    from greg import worker_isolation as isolation
    fix = "sudo apt install -y bubblewrap (worker.commission refuses to dispatch until this probe passes)"
    if platform.system() != "Linux":
        return {"workers_can_run_confined": False, "why": "the worker envelope is Linux-only on this path", "fix": fix}
    try:
        mechanism = isolation._backend(require_bubblewrap=True)[0]
        return {"workers_can_run_confined": True, "mechanism": mechanism}
    except Exception as exc:          # a probe failure is reported, never raised: the doctor is read-only
        return {"workers_can_run_confined": False, "why": f"{type(exc).__name__}: {str(exc)[:280]}", "fix": fix}


def confined_egress() -> dict:
    """Whether this host can run GREG's network capabilities confined behind the #26 egress relay: the Kernel seccomp
    filter (components with no socket of their own) and bubblewrap network namespaces (programs behind the door).

    Not a prerequisite for the body, but the installer turns it on whenever this probe passes. Probing installs the
    filter in a throwaway child and runs ``/usr/bin/true`` in a namespace; nothing else."""
    from greg import worker_isolation as isolation
    from greg.capabilities import KERNEL_ROOT
    fix = "sudo apt install -y bubblewrap libseccomp2"
    if platform.system() != "Linux":
        return {"available": False, "why": "confined egress is Linux-only on this path", "fix": fix}
    problems = []
    try:
        probe = subprocess.run([sys.executable, "-I", "-c", "import sys; sys.path.insert(0, sys.argv[1]); "
                                "from offline_test import install_filter; install_filter()",
                                str(KERNEL_ROOT / "tools")], capture_output=True, text=True, timeout=20)
        if probe.returncode:
            problems.append("kernel filter: " + ((getattr(probe, "stderr", "") or "").strip().splitlines()
                                                 or ["refused"])[-1][:200])
    except (OSError, subprocess.TimeoutExpired) as exc:
        problems.append(f"kernel filter: {type(exc).__name__}")
    try:
        isolation._backend(require_bubblewrap=True)
    except Exception as exc:          # a probe failure is reported, never raised: the doctor is read-only
        problems.append(f"network namespaces: {type(exc).__name__}: {str(exc)[:200]}")
    return ({"available": True, "mechanism": "seccomp filter + bubblewrap network namespaces behind the relay"}
            if not problems else {"available": False, "why": "; ".join(problems), "fix": fix})


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
            "worker_isolation": worker_isolation(),
            "confined_egress": confined_egress(),
            **({"fix": {"python_venv_available": "sudo apt install python3-venv"}}
               if "python_venv_available" in missing else {}),
            "not_verified": ["ChromeOS host identity and ownership", "VM restart at login", "sleep continuity",
                             "founder identity", "real mission outcome"],
            "next": ("follow greg/CHROMEBOOK_FIRST_MISSION.md on the actual Chromebook" if not missing else
                     "resolve missing prerequisites on the Chromebook before creating a key or body")}
