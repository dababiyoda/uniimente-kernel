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
GLIBC_RUNTIME = ("libc", "libm", "librt", "libdl", "libpthread", "libutil")


def _trusted_shared_object(path: Path) -> bool:
    """A regular, root-owned, non-group/world-writable, world-readable ELF file (never a directory)."""
    try:
        resolved = path.resolve(strict=True)
        metadata = resolved.stat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != 0 or metadata.st_mode & 0o022 \
                or not metadata.st_mode & 0o004:
            return False
        with resolved.open("rb") as stream:
            return stream.read(4) == b"\x7fELF"
    except OSError:
        return False
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
    # A child started from a virtual environment reads <venv>/pyvenv.cfg first; without it startup falls
    # back to the base prefix and every confined Python child dies in ``site``. GREG's installers
    # (greg/chromebook/install.sh, the Mac runbook) always create one, unlike CI's toolcache Python.
    # One grant: the exact public config file, read-only (both lineages fixed this; #168's resolve()
    # comparison also covers a symlinked prefix).
    if Path(sys.prefix).resolve() != Path(sys.base_prefix).resolve():
        venv_config = Path(sys.prefix).resolve() / "pyvenv.cfg"
        if venv_config.is_file():
            grants[venv_config] = READ_FILE
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
            # Core glibc runtime libraries a later extension import may dlopen (librt.so.1 is the one
            # MCP needed on GitHub runners): public loader-adjacent files, read-only, never directories.
            # Each candidate must be a root-owned, non-writable, world-readable ELF object (#156/#159).
            for arch in ("", "x86_64-linux-gnu/", "aarch64-linux-gnu/"):
                for name in GLIBC_RUNTIME:
                    for path in base.glob(f"{arch}{name}.so.*"):
                        if _trusted_shared_object(path):
                            grants[path.resolve()] = grants.get(path.resolve(), 0) | READ_FILE
    # The interpreter's own site-packages (Debian installs them outside sys.prefix/lib, e.g.
    # /usr/local/lib/python3.X/dist-packages). Installed runtime code only: user-site and arbitrary
    # sys.path entries stay excluded.
    import site
    for directory in getattr(site, "getsitepackages", lambda: [])():
        directory = Path(directory)
        if directory.is_dir():
            grants[directory.resolve()] = grants.get(directory.resolve(), 0) | READ_FILE | READ_DIR
    restrict(grants, libc)
    return {"filesystem": "landlock", "abi": abi, "arbitrary_source": "refused",
            "scope": "published source/runtime read-only; staged store read/write"}


def restrict(grants, libc=None):
    """Irreversibly apply a Landlock ruleset of ``{path: access}`` grants to this process.

    Only syscalls: safe to call in a ``preexec_fn`` after fork when ``libc`` was loaded in the parent.
    Every access the ruleset handles and no rule grants is denied, including truncation (ABI >= 3).
    """
    libc = libc or _libc()
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


# A commissioned frontier worker (greg/workers.py) is a full tool-using agent: it needs the host's installed
# runtime (its own binary, shells, git, interpreters, certificates) and its provider's network, so its policy is
# broader than ``confine``'s. What it must never reach is everything else on the body: the Body home (ledger,
# witness key, device key, inbox), other missions' workspaces, other work orders, the source checkout and the
# founder's files. Landlock grants are allow-only, so those are denied by not being granted, and a runtime root
# that would contain the worker's own workspace (and with it the Body home above it) is refused outright.
WORKER_RUNTIME = ("/usr", "/bin", "/sbin", "/lib", "/lib32", "/lib64", "/libx32", "/etc", "/opt")
WORKER_DEVICES = ("/dev/null", "/dev/zero", "/dev/full", "/dev/random", "/dev/urandom", "/dev/tty")
# Kernel information only. Never all of /proc: Landlock's ptrace scoping blocks another process's mem, fd, cwd
# and root, but not its environ, so a /proc grant would hand the worker the Body's environment (probe, 2026-10-15).
# ``/proc/self`` is opened by ``restrict`` inside the confined child, so it names the worker's own pid directory.
WORKER_KERNEL_VIEWS = ("/sys", "/proc/sys")
WORKER_KERNEL_FILES = ("/proc/cpuinfo", "/proc/meminfo", "/proc/stat", "/proc/loadavg", "/proc/uptime",
                       "/proc/version", "/proc/filesystems", "/proc/self")


def worker_grants(workdir, *, binaries=(), read_files=()):
    """The Landlock grants for one commissioned worker: its work directory read/write, the runtime read/execute.

    ``binaries`` are the provider executables (their install trees are granted read/execute); ``read_files`` are
    single files the worker must read (its prompt file). Raises when any granted root would contain ``workdir``.
    """
    workdir = Path(workdir).resolve(strict=True)
    runtime = READ_FILE | READ_DIR | EXECUTE
    roots = {Path(p) for p in WORKER_RUNTIME}
    roots |= {Path(sys.prefix).resolve(), Path(sys.base_prefix).resolve(), Path(sys.executable).resolve().parent}
    optional = set()
    for binary in binaries:
        if binary:
            given, real = Path(binary).absolute(), Path(binary).resolve()
            roots |= {given.parent, real.parent}
            optional.add(real.parent.parent)      # the install tree (a venv, a node prefix), only where it is safe
    grants = {}
    for root in sorted(roots | optional):
        if not root.exists():
            continue
        root = root.resolve()
        if root == workdir or root in workdir.parents:
            if root in {r.resolve() for r in optional} - {r.resolve() for r in roots if r.exists()}:
                continue
            raise IsolationError(f"runtime root {root} contains the worker workspace; the body home would be "
                                 "readable, so the worker is refused")
        grants[root] = grants.get(root, 0) | runtime
    for name in WORKER_DEVICES:
        if Path(name).exists():
            grants[Path(name)] = READ_FILE | WRITE_FILE
    for name in WORKER_KERNEL_VIEWS:
        if Path(name).is_dir():
            grants[Path(name)] = READ_FILE | READ_DIR
    for name in WORKER_KERNEL_FILES:
        if Path(name).exists():
            grants[Path(name)] = READ_FILE | (READ_DIR if name == "/proc/self" else 0)
    for file in read_files:
        file = Path(file).resolve(strict=True)
        if not file.is_file():
            raise IsolationError(f"worker read grant {file} is not a regular file")
        grants[file] = grants.get(file, 0) | READ_FILE
    grants[workdir] = ALL_FS
    return grants
