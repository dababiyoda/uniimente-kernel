"""OS filesystem confinement for Linux reviewed Foundry workers.

Reference: https://docs.kernel.org/userspace-api/landlock.html
ABI >=3 is required so truncation is denied as well as opening files. Rules
grant read-only access to explicit published source/runtime inputs and writes
only to the staged store. This is additional filesystem confinement, not a
microVM or permission to execute arbitrary providers/caller source.
"""
from __future__ import annotations
import ctypes
import os
from pathlib import Path
import platform
import stat
import sys

READ_FILE, READ_DIR = 1 << 2, 1 << 3
WRITE_FILE, EXECUTE, TRUNCATE = 1 << 1, 1, 1 << 14
ALL_FS = (1 << 15) - 1


class IsolationError(RuntimeError):
    pass


class _Rules(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64)]


class _Path(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("allowed_access", ctypes.c_uint64), ("parent_fd", ctypes.c_int32)]


def _libc():
    if sys.platform != "linux" or platform.machine() not in {"x86_64", "aarch64"}:
        raise IsolationError("Landlock requires a supported Linux architecture")
    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long
    return libc


def available():
    try:
        libc = _libc()
        abi = libc.syscall(444, None, 0, 1)
        return {"available": abi >= 3, "abi": abi if abi >= 0 else None,
                "errno": ctypes.get_errno() if abi < 0 else None}
    except IsolationError as exc:
        return {"available": False, "abi": None, "reason": str(exc)}


def confine(root, public_files):
    """Irreversibly confine this disposable process. Installation failure raises."""
    libc = _libc()
    abi = libc.syscall(444, None, 0, 1)
    if abi < 3:
        raise IsolationError("Landlock ABI >=3 required; caller/provider execution remains refused")
    root = Path(root).resolve(strict=True)
    code = Path(__file__).resolve().parents[1]
    grants = {root: ALL_FS, code: READ_DIR}
    for file in public_files:
        file = Path(file)
        if file.resolve(strict=True) != file or file.stat().st_nlink != 1 or not file.is_file():
            raise IsolationError("public source path must be a real unlinked file")
        grants[file] = READ_FILE
    # Interpreter-owned library trees contain runtime code/data. Exclude
    # arbitrary sys.path entries, repository roots and user-site directories.
    prefix = Path(sys.base_prefix).resolve()
    for directory in (prefix / "lib", Path(sys.prefix).resolve() / "lib"):
        if directory.is_dir():
            grants[directory] = READ_FILE | READ_DIR
    # Already-loaded ELF dependencies are explicit public runtime files.
    # No /proc hierarchy is granted; this read happens before confinement.
    for line in Path("/proc/self/maps").read_text().splitlines():
        parts = line.split(maxsplit=5)
        if len(parts) == 6 and parts[5].startswith("/") and "(deleted)" not in parts[5]:
            path = Path(parts[5]).resolve()
            if path.is_file() and path.suffix != ".pem" and ("/lib" in str(path) or path == Path(sys.executable).resolve()):
                grants[path] = grants.get(path, 0) | READ_FILE
    interpreter = Path(sys.executable).resolve(strict=True)
    grants[interpreter] = READ_FILE | EXECUTE
    for name in ("/etc/ld.so.cache", "/dev/null", "/etc/ssl/certs/ca-certificates.crt"):
        path = Path(name)
        if path.exists():
            grants[path] = READ_FILE | (WRITE_FILE if name == "/dev/null" else 0)
    for name in ("/usr/lib/locale/C.utf8", "/usr/share/zoneinfo"):
        path = Path(name)
        if path.is_dir():
            grants[path] = READ_FILE | READ_DIR
    # Future imported extension modules use the public loader/library files,
    # not broad host /usr or /etc grants.
    for base in (Path("/lib"), Path("/lib64"), Path("/usr/lib")):
        if base.is_dir():
            for pattern in ("ld-linux*.so*", "x86_64-linux-gnu/ld-linux*.so*",
                            "aarch64-linux-gnu/ld-linux*.so*"):
                for path in base.glob(pattern):
                    grants[path.resolve()] = READ_FILE | EXECUTE
    # Reviewed extension modules load glibc compatibility libraries lazily.
    # Include these named runtime dependencies without granting host directories
    # or every shared library installed on the host.
    triplet = {"x86_64": "x86_64-linux-gnu", "aarch64": "aarch64-linux-gnu"}[platform.machine()]
    for base in (Path("/lib") / triplet, Path("/usr/lib") / triplet):
        if not base.is_dir():
            continue
        for candidate in (base / name for name in (
                "librt.so.1", "libdl.so.2", "libpthread.so.0", "libutil.so.1")):
            if not candidate.exists():
                continue
            path = candidate.resolve(strict=True)
            metadata = path.stat()
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != 0 or \
                    metadata.st_mode & 0o022 or not metadata.st_mode & 0o004:
                continue
            with path.open("rb") as stream:
                if stream.read(4) == b"\x7fELF":
                    grants[path] = grants.get(path, 0) | READ_FILE
    attr = _Rules(ALL_FS)
    fd = libc.syscall(444, ctypes.byref(attr), ctypes.sizeof(attr), 0)
    if fd < 0:
        raise IsolationError(f"Landlock ruleset creation failed errno={ctypes.get_errno()}")
    try:
        for path, access in grants.items():
            pfd = os.open(path, os.O_PATH | os.O_CLOEXEC)
            try:
                rule = _Path(access, pfd)
                if libc.syscall(445, fd, 1, ctypes.byref(rule), 0) != 0:
                    raise IsolationError(f"Landlock path rule failed errno={ctypes.get_errno()}")
            finally:
                os.close(pfd)
        if libc.prctl(38, 1, 0, 0, 0) != 0:
            raise IsolationError("Landlock no_new_privs installation failed")
        if libc.syscall(446, fd, 0) != 0:
            raise IsolationError(f"Landlock restriction failed errno={ctypes.get_errno()}")
    finally:
        os.close(fd)
    return {"filesystem": "landlock", "abi": abi, "arbitrary_source": "refused",
            "scope": "published source/runtime read-only; staged store read/write"}
