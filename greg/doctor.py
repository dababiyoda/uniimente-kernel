"""Read-only prerequisite probe for a Chromebook Linux first body.

This checks the Linux environment that is actually running. It cannot determine
whether the ChromeOS host owns that environment, whether the VM survives sleep,
or whether the person at the keyboard is Alfonso. It creates no body or key.
"""
from __future__ import annotations

import importlib.util
import importlib.metadata
from pathlib import Path
import platform
import shutil
import subprocess
import sys

# Present inside ChromeOS's Linux (Crostini) container; informational, never an identity claim.
CROSTINI_MARKERS = ("/dev/.cros_milestone", "/opt/google/cros-containers")


def is_crostini(markers=CROSTINI_MARKERS) -> bool:
    return any(Path(marker).exists() for marker in markers)


ENGINE_MODULES = {"z3-solver": "z3", "ortools": "ortools", "protobuf": "google",
                  "networkx": "networkx", "sympy": "sympy", "scipy": "scipy", "mpmath": "mpmath"}


def _reviewed_pins():
    root = Path(__file__).resolve().parents[1]
    pins = {}
    for name in ("requirements-cognition.txt", "requirements-cognition-expanded.txt"):
        path = root / name
        if not path.is_file():
            continue
        for line in path.read_text().splitlines():
            line = line.split("#", 1)[0].strip()
            if "==" in line and not line.startswith("-"):
                package, version = line.split("==", 1)
                pins[package.strip().lower()] = {"version": version.strip(), "recipe": name}
    return pins


def _body_registry(home):
    """Read retained canonical state without creating a body, lock, key or event."""
    if home is None:
        return None, {"inspected": False, "reason": "no body home supplied"}
    from greg.body import Layout, observe
    from greg.cognition.cortex import registry_view
    layout = Layout(home)
    if not layout.config.is_file() or not layout.ledger.is_file():
        return None, {"inspected": False, "reason": "no retained body registry history", "body_exists": layout.config.is_file()}
    try:
        with observe(home, actor="spiffe://uniimente.internal/greg/doctor-reader") as journal:
            ok, why = journal.ledger.verify_chain()
            if not ok:
                return None, {"inspected": False, "reason": "retained history failed integrity verification"}
            return registry_view(journal), {"inspected": True, "ledger_head": journal.ledger.head,
                                           "unacknowledged_tail_present": bool(journal.ledger.unacknowledged_tail),
                                           "meaning": "retained registry state; no mission or grant eligibility inferred"}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return None, {"inspected": False, "reason": "body registry unavailable: " + str(exc)[:200]}


def engines(home=None) -> dict:
    """Metadata/path and retained attachment probe; never imports or runs an engine."""
    from greg.cognition.catalog import FAMILIES
    pins = _reviewed_pins()
    registry, body_state = _body_registry(home)
    rows = []
    for name, module in ENGINE_MODULES.items():
        metadata_error = None
        try:
            dist = importlib.metadata.distribution(name)
        except importlib.metadata.PackageNotFoundError:
            dist = None
        except (OSError, ValueError) as exc:
            dist, metadata_error = None, "installed metadata unreadable: " + str(exc)[:200]
        try:
            module_present = importlib.util.find_spec(module) is not None
            if name == "protobuf" and dist is not None:
                module_present = module_present and Path(dist.locate_file("google/protobuf/__init__.py")).is_file()
        except (ImportError, ValueError, AttributeError):
            module_present = False
        reviewed = pins.get(name)
        version = dist.version if dist else None
        version_matches = version == reviewed["version"] if version is not None and reviewed else None
        dependency_available = bool(dist and module_present and version_matches is True)
        license_text = (dist.metadata.get("License-Expression") or dist.metadata.get("License")) if dist else None
        uses = []
        for family, (_, operations, classes, proof, dependency) in FAMILIES.items():
            if dependency != name:
                continue
            cid = "cognition." + family
            state = registry.state.get(cid) if registry is not None else None
            adapter_available = registry.manifests[cid].available()[0] if registry is not None and cid in registry.manifests else None
            dependent_operations = ["polynomial"] if family == "exact" else list(operations)
            uses.append({"capability": cid, "operations": dependent_operations, "lifecycle_state": state,
                         "attached": state == "ATTACHED" if state is not None else None,
                         "available": dependency_available and adapter_available if adapter_available is not None else None,
                         "availability_scope": "package metadata/path and declared adapter only; native execution not probed",
                         "qualified_for_task": None, "authorized_for_task": None,
                         "dependency_scope": "polynomial needs SymPy; Fraction arithmetic does not" if family == "exact" else "declared family dependency"})
        rows.append({"distribution": name, "package_present": dist is not None, "installed": dist is not None,
                     "version": version, "reviewed_version": reviewed["version"] if reviewed else None,
                     "reviewed_recipe": reviewed["recipe"] if reviewed else None,
                     "version_matches_reviewed_pin": version_matches, "module_path_present": module_present,
                     "metadata_error": metadata_error,
                     "dependency_available": dependency_available, "native_execution_verified": None,
                     "license_metadata": license_text[:512] if license_text else None,
                     "license_metadata_truncated": bool(license_text and len(license_text) > 512),
                     "license_verification": "metadata only; consult the exact license/dependency evidence before use",
                     "capabilities": uses})
    missing = [r["distribution"] for r in rows if not r["package_present"]]
    mismatched = [r["distribution"] for r in rows if r["version_matches_reviewed_pin"] is False]
    return {"present": len(rows) - len(missing), "total": len(rows), "missing": missing,
            "version_mismatches": mismatched, "engines": rows, "body_registry": body_state,
            "authority_created": False,
            "note": "Package presence, declared adapter availability, attachment, task qualification and authorization are separate. "
                    "This read-only doctor runs no solver/model, downloads nothing and makes no body/device acceptance claim. "
                    "Optional installation is human-invoked with --with-engines or --with-expanded-engines."}


def chromebook(home=None) -> dict:
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
            "engines": engines(home),
            **({"fix": {"python_venv_available": "sudo apt install python3-venv"}}
               if "python_venv_available" in missing else {}),
            "not_verified": ["ChromeOS host identity and ownership", "VM restart at login", "sleep continuity",
                             "founder identity", "real mission outcome"],
            "next": ("follow greg/CHROMEBOOK_FIRST_MISSION.md on the actual Chromebook" if not missing else
                     "resolve missing prerequisites on the Chromebook before creating a key or body")}
