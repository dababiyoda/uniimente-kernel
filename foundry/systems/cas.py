"""#36 Content-addressed storage: artifacts identified by their SHA-256 content hash.

Objects live at ``objects/<2 hex>/<62 hex>``. Writes are atomic and idempotent;
every read re-hashes the bytes, so a corrupted or substituted object is refused,
never returned. Adopted mechanism: the git/IPFS object-store layout.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

PREFIX = "sha256:"


class IntegrityError(RuntimeError):
    """Stored bytes no longer hash to their address."""


def digest(data: bytes) -> str:
    return PREFIX + hashlib.sha256(data).hexdigest()


def _path(root: Path, address: str) -> Path:
    if not address.startswith(PREFIX) or len(address) != len(PREFIX) + 64:
        raise ValueError(f"not a sha256 address: {address!r}")
    hexd = address[len(PREFIX):]
    if any(c not in "0123456789abcdef" for c in hexd):
        raise ValueError(f"not a sha256 address: {address!r}")
    return Path(root) / "objects" / hexd[:2] / hexd[2:]


def put(root: Path, data: bytes) -> str:
    address = digest(data)
    target = _path(root, address)
    if target.exists():
        get(root, address)  # an existing object must still be intact
        return address
    _write(target, data)
    return address


def _write(target: Path, data: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    with open(temporary, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, target)


def repair(root: Path, data: bytes) -> str:
    """Rewrite the stored object of ``data`` atomically. ``data`` hashes to the address, so this restores an object
    whose stored bytes no longer do; the caller records the repair (nothing here repairs silently)."""
    address = digest(data)
    _write(_path(root, address), data)
    return address


def intact(root: Path, address: str) -> bool:
    """Whether the object is stored and still hashes to its address, re-hashed in chunks (never read whole)."""
    hasher = hashlib.sha256()
    try:
        with open(_path(root, address), "rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                hasher.update(chunk)
    except OSError:
        return False
    return PREFIX + hasher.hexdigest() == address


def get(root: Path, address: str) -> bytes:
    path = _path(root, address)
    if not path.is_file():
        raise KeyError(address)
    data = path.read_bytes()
    if digest(data) != address:
        raise IntegrityError(f"{address} is corrupted or substituted")
    return data


def has(root: Path, address: str) -> bool:
    return _path(root, address).is_file()


def verify_all(root: Path) -> dict:
    """Re-hash every stored object; report the corrupt ones (never repairs silently)."""
    objects = Path(root) / "objects"
    total, corrupt = 0, []
    for path in sorted(objects.glob("??/*")) if objects.is_dir() else []:
        if path.name.startswith("."):
            continue
        total += 1
        address = PREFIX + path.parent.name + path.name
        if digest(path.read_bytes()) != address:
            corrupt.append(address)
    return {"objects": total, "corrupt": corrupt, "intact": not corrupt}


# -- Foundry interface ------------------------------------------------------------------

def op_put(args: dict, root: Path) -> dict:
    return {"address": put(root, str(args["text"]).encode("utf-8"))}


def op_get(args: dict, root: Path) -> dict:
    return {"text": get(root, args["address"]).decode("utf-8")}


def op_verify(args: dict, root: Path) -> dict:
    return verify_all(root)


QUERY_OPS = {"get": op_get, "verify": op_verify}
APPLY_OPS = {"put": op_put}


def exercise(root: Path) -> dict:
    a = put(root, b"evidence: buyer interview 1")
    b = put(root, b"evidence: buyer interview 1")        # identical content -> same address
    c = put(root, b"evidence: counterexample")
    before = verify_all(root)
    _path(root, c).write_bytes(b"evidence: counterexample (edited)")
    try:
        get(root, c)
        refused = False
    except IntegrityError:
        refused = True
    after = verify_all(root)
    return {"dedup": a == b, "objects_before": before["objects"], "intact_before": before["intact"],
            "tampered_read_refused": refused, "detected": after["corrupt"] == [c],
            "untouched_readable": get(root, a) == b"evidence: buyer interview 1", "address_a": a}
