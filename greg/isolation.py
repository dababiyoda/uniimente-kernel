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
RUNTIME_LIBRARIES = ("libc.so*", "libm.so*", "librt.so*", "libdl.so*", "libpthread.so*", "libutil.so*",
                     "libgcc_s.so*", "libstdc++.so*", "libz.so*", "libffi.so*")


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
    # (this superset with the ancestor guard above). Each candidate must be a root-owned, non-writable,
    # world-readable ELF object (#156/#159), so a planted or linker-script file is never granted.
    for base in (Path("/lib"), Path("/lib64"), Path("/usr/lib"), Path("/usr/lib64")):
        for sub in ("", "x86_64-linux-gnu/", "aarch64-linux-gnu/"):
            for name in RUNTIME_LIBRARIES:
                for path in base.glob(sub + name):
                    if _trusted_shared_object(path):
                        grants[path.resolve()] = grants.get(path.resolve(), 0) | READ_FILE
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
    scoped = abi >= 6
    restrict(grants, libc, scope=SCOPE_ABSTRACT_UNIX_SOCKET | SCOPE_SIGNAL if scoped else 0)
    return {"filesystem": "landlock", "abi": abi, "arbitrary_source": "refused",
            "scope": "published source/runtime read-only; staged store read/write",
            "repository_listing": "allowed" if list_code else "denied",
            "signals": "scoped to the domain" if scoped else "unscoped (Landlock ABI < 6)"}


def signal_scope(abi) -> int:
    """``SCOPE_SIGNAL`` where the kernel has it (Landlock ABI >= 6), else 0.

    A process GREG confines on a worker's behalf (the worker itself, or its patch's tests in GREG's acceptance run)
    has the body's UID and, in supervised mode, no PID namespace: unscoped, it could SIGSTOP or SIGKILL the body
    and freeze its timeout, founder STOP and budget handling. Scoped, it can signal only processes in its own
    Landlock domain (its own children), never the body that supervises it (#173 scoping, merge review of e410977)."""
    return SCOPE_SIGNAL if isinstance(abi, int) and abi >= 6 else 0


def signals_record(scope: int) -> str:
    return "scoped to the domain" if scope & SCOPE_SIGNAL else "unscoped (Landlock ABI < 6)"


def restrict(grants, libc=None, *, scope: int = 0):
    """Irreversibly apply a Landlock ruleset of ``{path: access}`` grants to this process.

    Only syscalls: safe to call in a ``preexec_fn`` after fork when ``libc`` was loaded in the parent.
    Every access the ruleset handles and no rule grants is denied, including truncation (ABI >= 3).
    ``scope`` (ABI >= 6 only) adds IPC scoping.
    """
    libc = libc or _libc()
    attr = _ScopedRules(ALL_FS, 0, scope) if scope else _Rules(ALL_FS)
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


FILE_RIGHTS = EXECUTE | WRITE_FILE | READ_FILE | TRUNCATE


def confine_paths(*, read=(), read_exec=(), write=()) -> int:
    """Irreversibly confine this process (a forked child about to exec) to explicit paths.

    ``read`` trees are read-only, ``read_exec`` trees read-only and executable, ``write`` trees
    read/write. Every other path is neither readable nor writable, which is what keeps one
    organ's process away from another organ's code, the Kernel's sources and the body's home.
    Missing paths are skipped; installation failure raises."""
    libc = _libc()
    abi = libc.syscall(444, None, 0, 1)
    if abi < 3:
        raise IsolationError("Landlock ABI >=3 required")
    grants = {}
    for paths, access in ((read, READ_FILE | READ_DIR), (read_exec, READ_FILE | READ_DIR | EXECUTE),
                          (write, ALL_FS)):
        for path in paths:
            path = Path(path)
            if not path.exists():
                continue
            path = path.resolve()
            access_now = grants.get(path, 0) | access
            grants[path] = access_now if path.is_dir() else access_now & FILE_RIGHTS
    restrict(grants, libc)
    return abi


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


def _install_tree(tree: Path) -> set:
    """The install tree above a provider's ``bin`` directory, unless granting it would expose the founder's files.

    A tree that is the user's home or contains it (``~/bin/agent``) is never granted. A tree directly in the home
    is granted whole only when it is a virtual environment; otherwise (``~/.local``, whose ``share`` and ``state``
    hold other programs' data and credentials) only its ``lib`` directory is."""
    home = Path.home().resolve()
    tree = tree.resolve()
    if tree == home or tree in home.parents:
        return set()
    if tree.parent == home and not (tree / "pyvenv.cfg").is_file():
        return {tree / "lib"}
    return {tree}


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
            optional |= _install_tree(real.parent.parent)   # a venv or node prefix, only where it is safe
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
