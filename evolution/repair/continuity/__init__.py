"""Frozen continuity history for the Package 3 subjects. Read-only, content-addressed.

CONTRADICTION-0002 Option A (FOUNDER-RULING-2026-08-23, preserved verbatim in
``docs/deliberations/FOUNDER-RULING-2026-08-23-infinite-goal-chase.md``)
separates two questions the sealed experiment used to answer with one reading of
the live tree:

* *Does a historical run reproduce?* Answered here, from byte-identical copies
  of the twelve continuity artifacts each subject binding pins.
* *Has a constitutional or authority artifact changed without authorisation?*
  Answered by ``governance.integrity`` against the live tree. Never here.

``objects/<sha256>`` holds exactly the bytes whose sha256 is the file name. A
subject binding names a digest per artifact path, so the copy a binding reads is
fixed by the binding itself; nothing in this module chooses or learns a digest.
Every copy was materialised from git at its binding's source commit and checked
against the pinned digest before it was written (``MANIFEST.json`` records the
commands, ``tests/unit/test_repair_continuity_history.py`` re-proves them).

There is no writer. A copy that no longer hashes to its own name is reported as
tampered and the binding that reads it stops reproducing; it is never repaired
from the live tree, and no pinned digest is ever re-measured.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

STORE = Path(__file__).resolve().parent
OBJECTS = STORE / "objects"
_DIGEST = re.compile(r"[0-9a-f]{64}")


class FrozenHistoryError(ValueError):
    """A frozen copy is missing, malformed or does not hash to its own name."""


def object_path(digest: str) -> Path:
    if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
        raise FrozenHistoryError(f"not a sha256 digest: {digest!r}")
    return OBJECTS / digest


def read_raw(digest: str) -> bytes:
    """The stored bytes for ``digest``, unverified. Missing history raises."""
    path = object_path(digest)
    try:
        return path.read_bytes()
    except FileNotFoundError as exc:
        raise FrozenHistoryError(f"no frozen copy for {digest}") from exc


def read_frozen(digest: str) -> bytes:
    """The stored bytes for ``digest``, refused unless they hash to ``digest``."""
    raw = read_raw(digest)
    if hashlib.sha256(raw).hexdigest() != digest:
        raise FrozenHistoryError(f"frozen copy {digest} was altered")
    return raw


def materialize(artifacts, destination) -> Path:
    """Write ``(path, digest)`` pairs as a tree under ``destination``.

    For tests and offline review only: it writes nowhere but the caller's
    directory, and only verified bytes.
    """
    destination = Path(destination)
    for relative, digest in artifacts:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(read_frozen(digest))
    return destination
