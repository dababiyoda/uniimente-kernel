"""Fail a release that would carry uncleared third-party data (review of #179, M19; round-2 review, N3).

``docs/collaboration/RELEASE-EXCLUSIONS.json`` lists every tracked file holding third-party-derived values
whose redistribution terms are not cleared, each with its sha256. Those files stay in git as frozen evidence;
this check keeps them out of what is released.

    python scripts/check_release_exclusions.py                    # the Python package's declared contents
    python scripts/check_release_exclusions.py --archive A.tar    # a release artifact (tar, tar.gz, zip, whl)

A file is blocked when any of these holds, at any depth of nested archives:
* its content digest equals a listed file's sha256, before or after decoding (gzip, xz, lzma-alone, bz2, zlib,
  base64, UTF-16) - a renamed, recompressed or re-encoded copy;
* it parses as JSON whose canonical form (sorted keys, compact) equals a listed file's parsed content (a minified or
  reformatted copy, under any extension);
* its path ends with a listed path (any prefix, any depth);
* its text, after decoding, carries a listed data marker - except a ``.py`` member byte-identical to a tracked Python
  source file (a ``.py`` name, or parsing as Python, is not enough: JSON parses as Python, so an edited data copy
  renamed ``x.py`` is still scanned; round-5 review, N1), and except the exclusion list itself, byte for byte,
  which carries the markers it defines (N2), and except a record the list declares ``provenance_only`` (the
  data-exposure ledger cites instance names), byte-identical to its tracked file. Edited copies are scanned, which
  fails closed.

Out of scope, stated rather than hidden (round-3, round-4 and round-5 reviews of #179): values re-encoded into
another format (a Python literal, a CSV re-export, a subset of rows); encodings not decoded above (UTF-16-BE or
UTF-32 without a byte-order mark, raw deflate or zlib with other window sizes, raw lzma, hex, base32, base85,
base64 with stray bytes, a compressed stream with a leading byte); and more than six nested decoding layers. Those
need human review of what a release contains.

Exit 1 names every finding. It never edits, moves or deletes a file.
"""
from __future__ import annotations

import argparse
import base64
import functools
import binascii
import bz2
import gzip
import lzma
import zlib
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


def _decode_once(data: bytes) -> bytes | None:
    """One decoding layer: gzip, xz or lzma-alone, bz2, zlib, base64 or UTF-16; None when none applies."""
    if data[:2] == b"\x1f\x8b":
        return _gunzip(data)
    if data[:6] == b"\xfd7zXZ\x00" or data[:1] == b"\x5d":
        try:
            return lzma.decompress(data)                  # FORMAT_AUTO reads xz and lzma-alone
        except lzma.LZMAError:
            pass
    if data[:3] == b"BZh":
        try:
            return bz2.decompress(data)
        except (OSError, ValueError):
            return None
    if data[:1] == b"\x78" and len(data) > 2 and (data[0] * 256 + data[1]) % 31 == 0:
        try:
            return zlib.decompress(data)
        except zlib.error:
            pass
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        try:
            return data.decode("utf-16").encode("utf-8")
        except UnicodeDecodeError:
            return None
    compact = b"".join(data.split())
    alphabet = set(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=-_")
    if len(compact) >= 16 and len(compact) % 4 == 0 and set(compact) <= alphabet:
        try:
            urlsafe = b"-" in compact or b"_" in compact
            decoded = (base64.urlsafe_b64decode(compact) if urlsafe else base64.b64decode(compact, validate=True))
            if decoded:
                return decoded
        except (binascii.Error, ValueError):
            pass
    return None


def _decompressed(data: bytes) -> list[bytes]:
    """``data`` and every decoding layer beneath it (at most six layers)."""
    out, current = [data], data
    for _ in range(6):
        nxt = _decode_once(current)
        if nxt is None or nxt == current:
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


@functools.lru_cache(maxsize=None)
def _tracked_source() -> frozenset:
    """Digests of the repository's tracked Python source files. Parsing as Python is not enough: a JSON document
    is a valid Python expression, so an edited data copy renamed ``x.py`` parses (round-5 review of #179, N1)."""
    import subprocess
    names = subprocess.run(["git", "ls-files", "-z", "*.py"], cwd=ROOT, capture_output=True, check=True).stdout
    return frozenset(_digest((ROOT / n).read_bytes()) for n in names.decode().split("\0") if n and (ROOT / n).is_file())


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
    exempt = (_digest(data) in listed["provenance_digests"]
              or (leaf.endswith(".py") and _digest(data) in _tracked_source()))
    hits = [] if exempt else sorted({m for m in markers for v in variants if m.encode() in v})
    if hits:
        found.append(f"{path}: data markers {', '.join(hits)}")
    return found


@functools.lru_cache(maxsize=None)
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
    # the list itself and its declared provenance-only records, byte for byte, carry markers they cite, not data
    provenance = {_digest(LIST.read_bytes())} | {
        _digest((ROOT / p).read_bytes()) for p in (record.get("provenance_only") or {}).get("paths", [])
        if (ROOT / p).is_file()}
    return {"digests": digests, "paths": sorted(excluded()), "markers": markers, "provenance_digests": provenance}


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
