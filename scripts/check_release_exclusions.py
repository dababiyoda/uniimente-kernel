"""Fail a release that would carry uncleared third-party data (review of #179, M19; round-2 review, N3).

``docs/collaboration/RELEASE-EXCLUSIONS.json`` lists every tracked file holding third-party-derived values
whose redistribution terms are not cleared, each with its sha256. Those files stay in git as frozen evidence;
this check keeps them out of what is released.

    python scripts/check_release_exclusions.py                    # the Python package's declared contents
    python scripts/check_release_exclusions.py --archive A.tar    # a release artifact (tar, tar.gz, zip, whl)

A file is blocked when any of these holds, at any depth of nested archives:
* its content digest equals a listed file's sha256, before or after gzip decompression (a renamed copy);
* its path ends with a listed path (any prefix, any depth);
* its text (JSON, JSONL, log, CSV or plain text, gzip-decompressed when needed) carries a listed data marker.

Exit 1 names every finding. It never edits, moves or deletes a file.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
LIST = ROOT / "docs/collaboration/RELEASE-EXCLUSIONS.json"
TEXT = (".json", ".jsonl", ".log", ".csv", ".txt", ".tsv")
MAX_DEPTH = 8


def _list() -> dict:
    return json.loads(LIST.read_text())


def excluded() -> set[str]:
    return {entry["path"] for entry in _list()["paths"]}


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _gunzip(data: bytes) -> bytes | None:
    if data[:2] != b"\x1f\x8b":
        return None
    try:
        return gzip.decompress(data)
    except (OSError, EOFError):
        return None


def packaged() -> set[str]:
    """Tracked paths under the packages pyproject.toml declares (setuptools packages and package data)."""
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    packages = config.get("tool", {}).get("setuptools", {}).get("packages", [])
    out = set()
    for package in packages:
        base = ROOT / package.replace(".", "/")
        out |= {str(p.relative_to(ROOT)) for p in base.rglob("*") if p.is_file()}
    return out


def _entries(name: str, data: bytes, depth: int = 0):
    """(path, bytes) for every regular file in ``data``, recursing into nested tar, tar.gz, zip and whl."""
    if depth > MAX_DEPTH:
        yield name, data
        return
    nested = None
    if zipfile.is_zipfile(io.BytesIO(data)):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            nested = [(m, z.read(m)) for m in z.namelist() if not m.endswith("/")]
    else:
        try:
            with tarfile.open(fileobj=io.BytesIO(data)) as t:
                nested = [(m.name, t.extractfile(m).read()) for m in t.getmembers() if m.isfile()]
        except (tarfile.TarError, EOFError, OSError):
            nested = None
    if nested is None:
        yield name, data
        return
    for inner, content in nested:
        yield from _entries(f"{name}!{inner}" if name else inner, content, depth + 1)


def members(archive: Path) -> set[str]:
    """Every regular file's path in an archive (nested archives as ``outer!inner``); kept for callers."""
    return {path for path, _ in _entries("", archive.read_bytes())}


def _findings(path: str, data: bytes, listed: dict) -> list[str]:
    digests, paths, markers = listed["digests"], listed["paths"], listed["markers"]
    found = []
    for variant in (data, _gunzip(data)):
        if variant is not None and _digest(variant) in digests:
            found.append(f"{path}: content of {digests[_digest(variant)]}")
            break
    leaf = path.split("!")[-1]
    for listed_path in paths:
        if leaf == listed_path or leaf.endswith("/" + listed_path):
            found.append(f"{path}: path {listed_path}")
    text_like = leaf.lower().endswith(TEXT) or leaf.lower().endswith(tuple(t + ".gz" for t in TEXT))
    if text_like:
        text = (_gunzip(data) or data).decode("utf-8", "replace")
        hits = sorted({m for m in markers if m in text})
        if hits:
            found.append(f"{path}: data markers {', '.join(hits)}")
    return found


def _listed() -> dict:
    record = _list()
    digests = {e["sha256"]: e["path"] for e in record["paths"] if e.get("sha256")}
    for e in record["paths"]:              # the decompressed content of a listed .gz is the same data
        if e["path"].endswith(".gz"):
            raw = _gunzip((ROOT / e["path"]).read_bytes()) if (ROOT / e["path"]).exists() else None
            if raw is not None:
                digests[_digest(raw)] = e["path"]
    markers = {m for ms in record.get("markers", {}).values() for m in ms}
    return {"digests": digests, "paths": sorted(excluded()), "markers": markers}


def scan_archive(archive: Path) -> list[str]:
    listed = _listed()
    return sorted({f for path, data in _entries("", archive.read_bytes()) for f in _findings(path, data, listed)})


def scan_paths(paths: set[str]) -> list[str]:
    listed = _listed()
    out = set()
    for rel in paths:
        file = ROOT / rel
        if file.is_file():
            out |= set(_findings(rel, file.read_bytes(), listed))
    return sorted(out)


def check(paths: set[str]) -> list[str]:
    """Listed paths among ``paths`` (path rule only); see scan_paths and scan_archive for the full rule."""
    return sorted(excluded() & paths)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", type=Path, help="a release artifact to inspect")
    args = ap.parse_args(argv)
    found = scan_archive(args.archive) if args.archive else scan_paths(packaged())
    if found:
        print("RELEASE_BLOCKED: uncleared third-party data would ship:\n  " + "\n  ".join(found))
        return 1
    print(f"release exclusions: none of {len(excluded())} uncleared files would ship (digest, path and marker rules)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
