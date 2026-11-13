"""Fail a release that would carry uncleared third-party data (review of #179, M19).

``docs/collaboration/RELEASE-EXCLUSIONS.json`` lists every tracked file holding third-party-derived values
whose redistribution terms are not cleared. Those files stay in git as frozen evidence; this check keeps them
out of what is released.

    python scripts/check_release_exclusions.py                    # the Python package's declared contents
    python scripts/check_release_exclusions.py --archive A.tar    # a release artifact (tar, tar.gz, zip, whl)

Exit 1 names every excluded path found. It never edits, moves or deletes a file.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tarfile
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
LIST = ROOT / "docs/collaboration/RELEASE-EXCLUSIONS.json"


def excluded() -> set[str]:
    return {entry["path"] for entry in json.loads(LIST.read_text())["paths"]}


def packaged() -> set[str]:
    """Tracked paths under the packages pyproject.toml declares (setuptools packages and package data)."""
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    packages = config.get("tool", {}).get("setuptools", {}).get("packages", [])
    out = set()
    for package in packages:
        base = ROOT / package.replace(".", "/")
        out |= {str(p.relative_to(ROOT)) for p in base.rglob("*") if p.is_file()}
    return out


def members(archive: Path) -> set[str]:
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as z:
            names = z.namelist()
    else:
        with tarfile.open(archive) as t:
            names = t.getnames()
    # an archive may prefix every member with one top-level directory (git archive --prefix, sdists)
    return {n for name in names for n in (name, name.split("/", 1)[-1])}


def check(paths: set[str]) -> list[str]:
    return sorted(excluded() & paths)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", type=Path, help="a release artifact to inspect")
    args = ap.parse_args(argv)
    found = check(members(args.archive) if args.archive else packaged())
    if found:
        print("RELEASE_BLOCKED: uncleared third-party data would ship:\n  " + "\n  ".join(found))
        return 1
    print(f"release exclusions: none of {len(excluded())} uncleared paths would ship")
    return 0


if __name__ == "__main__":
    sys.exit(main())
