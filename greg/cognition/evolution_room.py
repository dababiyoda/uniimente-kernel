"""The entry of a recorded P8 cycle's clean room, run by path (never imported as part of the package).

``evolution.run_recorded`` starts this file inside a fresh detached checkout. Before the interpreter imports any
repository module it installs a source-only loader: repository source is hashed from the exact bytes compiled, and
no bytecode is read at all (with the room's fresh prefix and -B every .pyc a read could find would have been placed
there by someone else), so the import system compiles everything from source. Then it runs
``greg.cognition.evolution`` as __main__. A recorded cycle refuses to run without this loader and compares the
digests it recorded with the freeze; a stdlib-only file keeps that true from the first repository import on.
"""
from __future__ import annotations

import hashlib
import importlib.machinery
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
_READ = importlib.machinery.SourceFileLoader.get_data


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def get_data(loader, path):
    resolved = Path(path).resolve()
    if resolved.suffix == ".pyc":
        raise OSError("the clean room compiles from source and never reads bytecode")
    data = _READ(loader, path)
    if ROOT in resolved.parents and resolved.suffix == ".py":
        get_data.executed[resolved.relative_to(ROOT).as_posix()] = _sha(data)
    return data


get_data.executed = {Path(__file__).resolve().relative_to(ROOT).as_posix(): _sha(Path(__file__).read_bytes())}


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    importlib.machinery.SourceFileLoader.get_data = get_data
    # Started with -P (as the launcher does) the script's directory is not on the path, so nothing in greg/cognition
    # can stand in for a standard module this file imports; otherwise that directory is sys.path[0]: replace it.
    if sys.path and Path(sys.path[0] or ".").resolve() == Path(__file__).resolve().parent:
        sys.path[0] = str(ROOT)
    else:
        sys.path.insert(0, str(ROOT))
    sys.argv = [str(ROOT / "greg" / "cognition" / "evolution.py"), *sys.argv[1:]]
    runpy.run_module("greg.cognition.evolution", run_name="__main__", alter_sys=True)
