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
import sys

READ_FILE, READ_DIR = 1 << 2, 1 << 3
WRITE_FILE, EXECUTE, TRUNCATE = 1 << 1, 1, 1 << 14
ALL_FS = (1 << 15) - 1
RUNTIME_LIBRARIES = ("libc.so*", "libm.so*", "librt.so*", "libdl.so*", "libpthread.so*", "libutil.so*",
                     "libgcc_s.so*", "libstdc++.so*", "libz.so*", "libffi.so*")


class IsolationError(RuntimeError):
    pass


class _Rules(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64)]


class _ScopedRules(ctypes.Structure):
    """The ruleset attribute from ABI 6: network access left unhandled (unchanged), IPC scoped to the domain."""
    _fields_ = [("handled_access_fs", ctypes.c_uint64), ("handled_access_net", ctypes.c_uint64),
                ("scoped", ctypes.c_uint64)]


# ABI >= 6: a confined process may neither signal a process outside its Landlock domain (the parent, PID 1, any
# host process) nor connect to an abstract UNIX socket created outside it. (#158 af258bf, review of #179 L5)
SCOPE_ABSTRACT_UNIX_SOCKET, SCOPE_SIGNAL = 1, 2


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


def confine(root, public_files, *, list_code: bool = True):
    """Irreversibly confine this disposable process. Installation failure raises. ``list_code=False`` withholds
    even directory listing of the repository (the P8 sandbox imports everything it runs before confinement)."""
    libc = _libc()
    abi = libc.syscall(444, None, 0, 1)
    if abi < 3:
        raise IsolationError("Landlock ABI >=3 required; caller/provider execution remains refused")
    root = Path(root).resolve(strict=True)
    code = Path(__file__).resolve().parents[1]
    grants = {root: ALL_FS, **({code: READ_DIR} if list_code else {})}
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
    # The interpreter's own installed-package trees can sit outside <prefix>/lib (Debian's
    # /usr/local/lib/pythonX.Y/dist-packages). User-site, the repository and the store stay excluded.
    import site
    import sysconfig
    user_site = Path(site.getusersitepackages()).resolve()
    for directory in {*site.getsitepackages(), sysconfig.get_paths()["purelib"], sysconfig.get_paths()["platlib"]}:
        directory = Path(directory).resolve()
        if directory.is_dir() and not any(directory == p or p in directory.parents or directory in p.parents
                                          for p in (user_site, code, root)):
            grants[directory] = grants.get(directory, 0) | READ_FILE | READ_DIR
    # C runtime libraries an extension module imported after confinement may link against (CI:
    # librt.so.1). Exact public library files, never a whole host library directory. One grant path:
    # the 2026-10-14 Mind-lineage convergence unified #158's 1ea2209 (glibc family) and #155's bfb9c04
    # (this superset with the ancestor guard above).
    for base in (Path("/lib"), Path("/lib64"), Path("/usr/lib"), Path("/usr/lib64")):
        for sub in ("", "x86_64-linux-gnu/", "aarch64-linux-gnu/"):
            for name in RUNTIME_LIBRARIES:
                for path in base.glob(sub + name):
                    if path.is_file():
                        grants[path.resolve()] = grants.get(path.resolve(), 0) | READ_FILE
    # A virtual environment's interpreter reads pyvenv.cfg at startup: a confined worker's child interpreter needs it.
    venv_config = Path(sys.prefix).resolve() / "pyvenv.cfg"
    if sys.prefix != sys.base_prefix and venv_config.is_file():
        grants[venv_config] = READ_FILE
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
    # landlock_restrict_self confines the calling thread (and what it later creates) only: a thread that already
    # exists would keep unconfined access, so a multi-threaded caller is refused rather than half-confined.
    threads = len(os.listdir("/proc/self/task"))
    if threads != 1:
        raise IsolationError(f"Landlock confines the calling thread only; {threads} threads exist (start numeric "
                             f"libraries single-threaded, e.g. OPENBLAS_NUM_THREADS=1, before confining)")
    scoped = abi >= 6
    attr = _ScopedRules(ALL_FS, 0, SCOPE_ABSTRACT_UNIX_SOCKET | SCOPE_SIGNAL) if scoped else _Rules(ALL_FS)
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
            "scope": "published source/runtime read-only; staged store read/write",
            "repository_listing": "allowed" if list_code else "denied",
            "signals": "scoped to the domain" if scoped else "unscoped (Landlock ABI < 6)",
            "ipc_scopes": ["abstract_unix_socket", "signal"] if scoped else [], "threads": threads}
