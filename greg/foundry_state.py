"""Bounded snapshots and atomic commit for the reviewed Foundry worker store.

Only regular files/directories are imported. This guards state publication;
it does not turn the worker's Python hooks into an OS filesystem sandbox.
"""
from __future__ import annotations

import ctypes
import hashlib
import os
from pathlib import Path
import shutil
import stat

from greg.capabilities import CapabilityError

MAX_FILES = 4096
MAX_BYTES = 64 * 1024 * 1024


def fingerprint(root: Path) -> str:
    root = Path(root)
    if not root.exists():
        return "absent"
    if root.is_symlink() or not root.is_dir():
        raise CapabilityError("Foundry store must be an owned directory")
    result, size, count = hashlib.sha256(), 0, 0
    for path in sorted(root.rglob("*")):
        info = path.lstat()
        count += 1
        if count > MAX_FILES:
            raise CapabilityError("Foundry state quota exceeded")
        if stat.S_ISDIR(info.st_mode):
            result.update(b"dir:" + str(path.relative_to(root)).encode() + b"\0")
            continue
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise CapabilityError("linked or special Foundry state refused")
        size += info.st_size
        if count > MAX_FILES or size > MAX_BYTES:
            raise CapabilityError("Foundry state quota exceeded")
        result.update(str(path.relative_to(root)).encode() + b"\0")
        with path.open("rb") as stream:
            for part in iter(lambda: stream.read(65536), b""):
                result.update(part)
        result.update(b"\0")
    return "sha256:" + result.hexdigest()


def stage(root: Path, target: Path) -> str:
    before = fingerprint(root)
    if before == "absent":
        target.mkdir()
    else:
        shutil.copytree(root, target)
    if fingerprint(root) != before:
        raise CapabilityError("Foundry state changed while taking snapshot")
    return before


def commit(staged: Path, target: Path, before: str) -> str:
    after = fingerprint(staged)
    if fingerprint(target) != before:
        raise CapabilityError("Foundry state changed during worker execution; commit refused")
    # Flush complete staged bytes before publishing the new directory.
    for path in staged.rglob("*"):
        if path.is_file():
            with path.open("rb") as stream:
                os.fsync(stream.fileno())
    if before == "absent":
        os.rename(staged, target)
    else:
        libc = ctypes.CDLL(None, use_errno=True)
        exchange = getattr(libc, "renameat2", None)
        if exchange is None:
            raise CapabilityError("atomic directory exchange unavailable; commit refused")
        exchange.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        exchange.restype = ctypes.c_int
        if exchange(-100, os.fsencode(staged), -100, os.fsencode(target), 2):
            raise CapabilityError(f"atomic directory exchange refused: errno {ctypes.get_errno()}")
    directory = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return after
