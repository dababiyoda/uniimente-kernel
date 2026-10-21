"""Fail a release that would carry uncleared third-party data (review of #179, M19; round-2 review, N3).

``docs/collaboration/RELEASE-EXCLUSIONS.json`` lists every tracked file holding third-party-derived values
whose redistribution terms are not cleared, each with its sha256. Those files stay in git as frozen evidence;
this check keeps them out of what is released.

    python scripts/check_release_exclusions.py                    # the Python package's declared contents
    python scripts/check_release_exclusions.py --archive A.tar    # a release artifact (tar, tar.gz, zip, whl)

A file is blocked when any of these holds, at any depth of nested archives:
* its content digest equals a listed file's sha256, before or after gzip, xz or bz2 decompression (a renamed or
  recompressed copy);
* it parses as JSON whose canonical form (sorted keys, compact) equals a listed file's parsed content (a minified or
  reformatted copy, under any extension);
* its path ends with a listed path (any prefix, any depth);
* its text, under any extension and after decompression, carries a listed data marker.

Out of scope, stated rather than hidden (round-3 review of #179, finding 3): values re-encoded into another
format (a Python literal, a CSV re-export, a subset of rows). Those need human review of what a release contains.

Exit 1 names every finding. It never edits, moves or deletes a file.
"""
from __future__ import annotations

import argparse
import bz2
import gzip
import lzma
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


def _decompressed(data: bytes) -> list[bytes]:
    """``data`` and every layer of gzip, xz or bz2 decompression beneath it (at most four layers)."""
    out, current = [data], data
    for _ in range(4):
        nxt = None
        if current[:2] == b"\x1f\x8b":
            nxt = _gunzip(current)
        elif current[:6] == b"\xfd7zXZ\x00":
            try:
                nxt = lzma.decompress(current)
            except lzma.LZMAError:
                nxt = None
        elif current[:3] == b"BZh":
            try:
                nxt = bz2.decompress(current)
            except (OSError, ValueError):
                nxt = None
        if nxt is None:
            break
        out.append(nxt)
        current = nxt
    return out


def _canonical(data: bytes) -> str | None:
    """Digest of the parsed JSON's canonical form, or None when ``data`` is not one JSON document."""
    if not data or data.lstrip()[:1] not in (b"{", b"["):
        return None
    try:
        value = json.loads(data)
    except (ValueError, UnicodeDecodeError, RecursionError):
        return None
    return "json:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


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
    variants = _decompressed(data)
    for variant in variants:
        for key in (_digest(variant), _canonical(variant)):
            if key is not None and key in digests:
                found.append(f"{path}: content of {digests[key]}")
                break
        else:
            continue
        break
    leaf = path.split("!")[-1]
    for listed_path in paths:
        if leaf == listed_path or leaf.endswith("/" + listed_path):
            found.append(f"{path}: path {listed_path}")
    hits = sorted({m for m in markers for v in variants if m.encode() in v})
    if hits:
        found.append(f"{path}: data markers {', '.join(hits)}")
    return found


def _listed() -> dict:
    record = _list()
    digests = {e["sha256"]: e["path"] for e in record["paths"] if e.get("sha256")}
    for e in record["paths"]:              # decompressed and canonical-JSON forms of a listed file are the same data
        file = ROOT / e["path"]
        if not file.exists():
            continue
        for variant in _decompressed(file.read_bytes()):
            digests.setdefault(_digest(variant), e["path"])
            if (canonical := _canonical(variant)) is not None:
                digests.setdefault(canonical, e["path"])
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
