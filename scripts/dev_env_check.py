#!/usr/bin/env python3
"""Environment doctor: say, before you run tests, what will fail for reasons that
are about this machine rather than the code.

    python scripts/dev_env_check.py            # report; exit 0
    python scripts/dev_env_check.py --strict   # exit 1 if anything required is missing
    python scripts/dev_env_check.py --json

Why it exists (docs/collaboration/CONTRIBUTOR-PAIN-POINTS-2026-11-05.md, P-8 and P-14):
sessions repeatedly lost time to failures that came from the machine, not the code.
A shallow clone breaks frozen-history tests. Missing optional modules (rfc3161_client,
scipy, networkx, Python Playwright) fail or skip whole test files. A tmpfs `/tmp` makes
greg/backup.py refuse its stores (20 test failures on one CI runner). Missing bubblewrap
or pdftotext skips or fails confined-worker and PDF tests.

Read-only: it reads package metadata, /proc/mounts and git, and installs and writes
nothing. A clean report is not evidence that tests pass. It only removes known
environmental causes.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Which requirement files each test area needs (as CI installs them).
REQUIREMENT_FILES = {
    "requirements-dev.txt": "every test job (Canonical CI job 1 and most others)",
    "requirements-cognition.txt": "cognition, Mind and exposure-ledger tests (directive-completion, job 1)",
    "requirements-cortex.txt": "cortex seed experiment (job 6)",
    "requirements-research-line.txt": "open-source research line (job 5)",
}
# Executables and Python packages CI installs outside the requirement files.
EXTRA_TOOLS = {
    "bwrap": "bubblewrap: confined-worker and one-machine tests (job 1, job 8 install it)",
    "pdftotext": "poppler: PDF reader tests (job 6 installs it)",
    "git": "everything; frozen-history tests need full history",
}
EXTRA_MODULES = {
    "playwright": "Python Playwright 1.63.0 and its Chromium (python -m playwright install chromium): browser.session, "
                  "Mission Control and phone-page tests (Canonical CI job 11 installs both and sets "
                  "GREG_REQUIRE_BROWSER=1; directive-completion installs 1.63.0)",
}
VOLATILE_FS = ("tmpfs", "ramfs")  # the same rule greg/backup.py applies (VOLATILE)


def _requirements(path: Path, seen: set | None = None) -> list[str]:
    seen = seen if seen is not None else set()
    if path in seen or not path.is_file():
        return []
    seen.add(path)
    out = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("-r "):
            out += _requirements(path.parent / line[3:].strip(), seen)
        elif not line.startswith("-"):
            out.append(line)
    return out


def _check_requirement(spec: str) -> dict:
    name = re.split(r"[<>=!~;\[ ]", spec, maxsplit=1)[0]
    try:
        installed = metadata.version(name)
    except metadata.PackageNotFoundError:
        return {"requirement": spec, "installed": None, "ok": False}
    ok = True
    try:
        from packaging.requirements import Requirement
        req = Requirement(spec)
        ok = req.specifier.contains(installed, prereleases=True) if req.specifier else True
    except Exception:  # packaging absent or unparsable spec: presence only
        pass
    return {"requirement": spec, "installed": installed, "ok": ok}


def _fs_type(path: str, mounts_text: str | None = None) -> str | None:
    """Filesystem type of the mount holding `path`, from /proc/mounts (Linux only)."""
    if mounts_text is None:
        try:
            mounts_text = Path("/proc/mounts").read_text()
        except OSError:
            return None
    mounts = mounts_text.splitlines()
    real = os.path.realpath(path)
    best, kind = "", None
    for line in mounts:
        parts = line.split()
        if len(parts) >= 3 and (real == parts[1] or real.startswith(parts[1].rstrip("/") + "/")):
            if len(parts[1]) >= len(best):
                best, kind = parts[1], parts[2]
    return kind


def _shallow() -> bool | None:
    try:
        out = subprocess.run(["git", "rev-parse", "--is-shallow-repository"], cwd=ROOT,
                             capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() == "true" if out.returncode == 0 else None


def build_report() -> dict:
    report = {"schema": "uniimente.dev_env_check/1", "python": sys.version.split()[0],
              "python_ok": sys.version_info >= (3, 11), "requirements": {}, "tools": {},
              "modules": {}, "advice": []}
    for name, needed_for in REQUIREMENT_FILES.items():
        rows = [_check_requirement(s) for s in _requirements(ROOT / name)]
        missing = [r for r in rows if not r["ok"]]
        report["requirements"][name] = {"needed_for": needed_for, "total": len(rows),
                                        "missing_or_wrong_version": missing}
        if missing:
            report["advice"].append(f"pip install -r {name}   # {len(missing)} missing: "
                                    + ", ".join(r["requirement"] for r in missing[:5]))
    for tool, why in EXTRA_TOOLS.items():
        found = shutil.which(tool)
        report["tools"][tool] = {"found": bool(found), "needed_for": why}
        if not found:
            report["advice"].append(f"install {tool}: {why}")
    for mod, why in EXTRA_MODULES.items():
        try:
            metadata.version(mod)
            present = True
        except metadata.PackageNotFoundError:
            present = False
        report["modules"][mod] = {"found": present, "needed_for": why}
        if not present:
            report["advice"].append(f"pip install {mod}: {why}")
    tmp = tempfile.gettempdir()
    kind = _fs_type(tmp)
    report["tempdir"] = {"path": tmp, "fs_type": kind, "volatile": kind in VOLATILE_FS}
    if kind in VOLATILE_FS:
        report["advice"].append(f"TMPDIR={tmp} is {kind}; greg/backup.py refuses stores there. "
                                "Point TMPDIR at a disk directory before running tests.")
    shallow = _shallow()
    report["git"] = {"shallow": shallow}
    if shallow:
        report["advice"].append("git fetch --unshallow   # frozen-history tests need full history")
    if not report["python_ok"]:
        report["advice"].append("Python >= 3.11 is required (pyproject.toml)")
    report["required_ok"] = (report["python_ok"] and not shallow and not report["tempdir"]["volatile"]
                             and not report["requirements"]["requirements-dev.txt"]["missing_or_wrong_version"])
    return report


def to_text(report: dict) -> str:
    lines = [f"Python {report['python']} ({'ok' if report['python_ok'] else 'TOO OLD'})"]
    for name, row in report["requirements"].items():
        miss = row["missing_or_wrong_version"]
        lines.append(f"{name}: {row['total'] - len(miss)}/{row['total']} satisfied"
                     + (f"; missing {', '.join(m['requirement'] for m in miss)}" if miss else ""))
    for name, row in {**report["tools"], **report["modules"]}.items():
        lines.append(f"{name}: {'found' if row['found'] else 'MISSING'} ({row['needed_for']})")
    t = report["tempdir"]
    lines.append(f"tempdir {t['path']}: {t['fs_type'] or 'unknown fs'}"
                 + (" (VOLATILE: backup tests will be refused)" if t["volatile"] else ""))
    lines.append(f"git shallow: {report['git']['shallow']}")
    lines.append("")
    lines += ["To fix:"] + [f"  {a}" for a in report["advice"]] if report["advice"] else \
        ["No known environmental cause of test failure found."]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 when Python, git history, tempdir or requirements-dev.txt would break tests")
    args = ap.parse_args(argv)
    report = build_report()
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else to_text(report))
    return 1 if args.strict and not report["required_ok"] else 0


if __name__ == "__main__":
    sys.exit(main())
