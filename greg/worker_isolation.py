"""OS-enforced containment for disposable workers, never an authority boundary owner.

Linux Landlock ABI 3+ confines filesystem access. When Landlock is unavailable,
commodity bubblewrap provides an empty filesystem with explicit runtime mounts.
Neither backend denies provider network access: a remote worker needs that access
to think. Unsupported hosts refuse dispatch instead of silently running unconfined.
"""
from __future__ import annotations

import ctypes
import math
import os
from pathlib import Path
import platform
import re
import resource
import shutil
import signal
import subprocess
import sys

from greg.capabilities import CapabilityError


class WorkerIsolationError(CapabilityError):
    """Pre-dispatch refusal; evidence contains the actual unavailable mechanism."""

    def __init__(self, message: str, *, evidence: dict | None = None):
        super().__init__(message)
        self.evidence = evidence or {"status": "refused", "reason": message}


_READ = (1 << 0) | (1 << 2) | (1 << 3)  # execute, read file, read directory
_HANDLED = (1 << 15) - 1               # ABI 3 includes REFER and TRUNCATE
_WRITE = _HANDLED & ~((1 << 6) | (1 << 11))  # never create device nodes
_PROVIDER_ENV = {
    "claude-code": ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN"),
    "codex": ("OPENAI_API_KEY", "CODEX_API_KEY"),
    "aider": ("OPENAI_API_KEY", "ANTHROPIC_API_KEY"),
}
_AUTH_FILES = {"claude-code": ".claude/.credentials.json", "codex": ".codex/auth.json"}
_TRANSPORT_ENV = (
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "http_proxy", "https_proxy",
    "all_proxy", "no_proxy", "SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE",
    "CURL_CA_BUNDLE", "NODE_EXTRA_CA_CERTS",
)
_CERT_ENV = ("SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE", "NODE_EXTRA_CA_CERTS")
_CERT_ROOTS = (Path("/etc/ssl"), Path("/etc/pki"), Path("/usr/share/ca-certificates"),
               Path("/usr/local/share/ca-certificates"))
_MEMORY_LIMIT = 16 * 1024 ** 3  # address space, not a claim of per-worker RSS accounting


def _landlock_abi() -> int:
    if sys.platform != "linux" or platform.machine() not in ("x86_64", "aarch64"):
        raise WorkerIsolationError("Landlock requires supported Linux x86_64/aarch64")
    libc = ctypes.CDLL(None, use_errno=True)
    abi = libc.syscall(444, 0, 0, 1)  # landlock_create_ruleset(..., VERSION)
    if abi < 3:
        reason = os.strerror(ctypes.get_errno()) if abi < 0 else f"ABI {abi} lacks truncate confinement"
        raise WorkerIsolationError(f"Landlock ABI >= 3 unavailable: {reason}")
    return int(abi)


def _runtime_paths(executable: Path) -> list[Path]:
    """Read-only code, libraries and transport support; never a home/workspace root."""
    paths = [Path(p) for p in ("/usr/bin", "/bin", "/usr/lib", "/usr/lib64", "/lib", "/lib64",
                               "/usr/local/bin", "/usr/local/lib", "/usr/share/zoneinfo",
                               "/etc/ld.so.cache", "/etc/ssl/certs", "/etc/resolv.conf",
                               "/etc/nsswitch.conf", "/etc/hosts")]
    for prefix in dict.fromkeys((sys.prefix, sys.base_prefix)):
        paths.extend((Path(prefix) / "bin", Path(prefix) / "lib", Path(prefix) / "pyvenv.cfg"))
    paths.extend((executable, executable.resolve()))
    if executable.parent.name == "bin" and (executable.parent.parent / "pyvenv.cfg").is_file():
        paths.extend((executable.parent, executable.parent.parent / "lib",
                      executable.parent.parent / "pyvenv.cfg"))
    # Node/Python installed outside /usr use their own bin/lib directories. The
    # executable itself is granted exactly; a home installation does not grant HOME.
    for binary_name in ("python", "python3", "node"):
        binary = shutil.which(binary_name)
        if binary:
            resolved = Path(binary).resolve()
            if resolved.parent.name == "bin":
                paths.extend((resolved, resolved.parent.parent / "lib"))
    for parent in list(executable.parents)[:4]:
        if "node_modules" in parent.parts and (parent / "package.json").is_file():
            paths.append(parent)
            break
    existing = list(dict.fromkeys(p.absolute() for p in paths if p.exists()))
    return [p for p in existing if not any(p != root and p.is_relative_to(root)
                                          for root in existing if root.is_dir())]


def _bubblewrap_argv(binary: str, read_paths: list[Path], cwd: Path | None = None,
                    runtime: Path | None = None, *, network: bool = True) -> list[str]:
    argv = [binary, "--unshare-user", "--unshare-pid", "--unshare-uts", "--unshare-ipc",
            "--disable-userns", "--die-with-parent", "--new-session", "--cap-drop", "ALL"]
    if not network:
        argv.append("--unshare-net")
    for path in read_paths:
        argv += ["--ro-bind", str(path), str(path)]
    argv += ["--proc", "/proc", "--dev", "/dev"]
    if cwd is not None and runtime is not None:
        argv += ["--bind", str(runtime / "tmp"), "/tmp", "--tmpfs", str(cwd.parent),
                 "--bind", str(cwd), str(cwd),
                 "--bind", str(runtime), str(runtime), "--chdir", str(cwd)]
        metadata = cwd / ".git"
        if metadata.is_dir() and not metadata.is_symlink():
            argv += ["--ro-bind", str(metadata), str(metadata)]
        argv += ["--remount-ro", str(cwd.parent)]
    argv += ["--remount-ro", "/"]
    return argv


def _backend(*, require_bubblewrap: bool = False) -> tuple[str, int | None, str | None, list[str]]:
    reasons = []
    try:
        abi = _landlock_abi()
        if not require_bubblewrap:
            return "landlock", abi, None, reasons
        reasons.append("Landlock alone does not isolate untrusted acceptance processes/network")
    except WorkerIsolationError as exc:
        reasons.append(str(exc))
    binary = shutil.which("bwrap") if sys.platform == "linux" else None
    if binary:
        true = Path("/usr/bin/true")
        try:
            probe = subprocess.run(_bubblewrap_argv(binary, _runtime_paths(true),
                                                   network=not require_bubblewrap) + ["--", str(true)],
                                   env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
                                   stdin=subprocess.DEVNULL, capture_output=True, timeout=5)
            if probe.returncode == 0:
                return "bubblewrap", None, binary, reasons
            reasons.append("bubblewrap namespace probe failed: " + probe.stderr.decode(errors="replace")[-300:])
        except (OSError, subprocess.TimeoutExpired) as exc:
            reasons.append(f"bubblewrap namespace probe failed: {exc}")
    else:
        reasons.append("bubblewrap is unavailable on this host")
    message = "; ".join(reasons)
    raise WorkerIsolationError("worker OS filesystem isolation unavailable: " + message,
                               evidence={"status": "unsupported", "reason": message,
                                         "network": "provider-network-required"})


def _private_directory(path: Path) -> None:
    if path.absolute() != path.resolve():
        raise WorkerIsolationError(f"private runtime path has a symlink parent: {path}")
    try:
        path.mkdir(mode=0o700)
    except FileExistsError:
        if path.is_symlink() or not path.is_dir():
            raise WorkerIsolationError(f"private runtime path is not a real directory: {path}")
    path.chmod(0o700)


def _install_landlock(read_paths: list[Path], write_paths: list[Path]) -> None:
    class Ruleset(ctypes.Structure):
        _fields_ = [("handled_access_fs", ctypes.c_uint64)]

    class PathRule(ctypes.Structure):
        _pack_ = 1
        _fields_ = [("allowed_access", ctypes.c_uint64), ("parent_fd", ctypes.c_int32)]

    libc = ctypes.CDLL(None, use_errno=True)
    attrs = Ruleset(_HANDLED)
    ruleset = libc.syscall(444, ctypes.byref(attrs), ctypes.sizeof(attrs), 0)
    if ruleset < 0:
        raise OSError(ctypes.get_errno(), "Landlock ruleset creation failed")
    try:
        rules = [(p, _READ) for p in read_paths] + [(p, _WRITE) for p in write_paths]
        # Only these device files are granted, never /dev or /proc as a read root.
        rules += [(Path("/dev/null"), (1 << 1) | (1 << 2)),
                  (Path("/dev/urandom"), 1 << 2), (Path("/dev/random"), 1 << 2)]
        for path, rights in rules:
            fd = os.open(path, os.O_PATH | os.O_CLOEXEC)
            try:
                if not path.is_dir():
                    rights &= (1 << 0) | (1 << 1) | (1 << 2) | (1 << 14)
                rule = PathRule(rights, fd)
                if libc.syscall(445, ruleset, 1, ctypes.byref(rule), 0) != 0:
                    raise OSError(ctypes.get_errno(), f"Landlock path rule failed: {path}")
            finally:
                os.close(fd)
        if libc.syscall(446, ruleset, 0) != 0:
            raise OSError(ctypes.get_errno(), "Landlock restrict_self failed")
    finally:
        os.close(ruleset)


def prepare_worker(argv, cwd, timeout_seconds, provider, reviewed=False, config_files=None,
                   *, source_env=None, network=True, file_bytes=512 * 1024 ** 2) -> dict:
    """Prepare a confined argv/env/preexec envelope; callers must execute returned argv.

    ``config_files`` maps the provider's one supported HOME-relative credential
    destination to its exact current HOME source. Missing optional files are ignored.
    No full HOME, configuration directory, source checkout or body is mounted/copied.
    ``network=False`` is for independent acceptance, requires full bubblewrap
    process/network/filesystem isolation, and carries no provider authentication.
    """
    if reviewed is not True:
        raise WorkerIsolationError("unreviewed worker provider refused before dispatch")
    if not isinstance(argv, (list, tuple)) or not argv or not all(isinstance(a, str) for a in argv):
        raise WorkerIsolationError("worker argv must contain strings")
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,60}", str(provider)):
        raise WorkerIsolationError("invalid worker provider runtime name")
    try:
        timeout = float(timeout_seconds)
    except (TypeError, ValueError, OverflowError) as exc:
        raise WorkerIsolationError("worker timeout must be finite and positive") from exc
    if isinstance(timeout_seconds, bool) or not math.isfinite(timeout) or not 0 < timeout <= 3600:
        raise WorkerIsolationError("worker timeout must be finite and in (0, 3600]")
    if isinstance(file_bytes, bool) or not isinstance(file_bytes, int) or not 0 < file_bytes <= 512 * 1024 ** 2:
        raise WorkerIsolationError("worker file_bytes must be a positive integer <= 512 MiB")
    requested_cwd = Path(cwd).absolute()
    cwd = requested_cwd.resolve(strict=True)
    if requested_cwd != cwd:
        raise WorkerIsolationError("worker workspace must not use a symlink directory or parent")
    if not cwd.is_dir() or cwd == Path("/") or cwd == Path.home().resolve():
        raise WorkerIsolationError("worker cwd must be a private workspace directory")
    binary = shutil.which(argv[0]) if not Path(argv[0]).is_absolute() else argv[0]
    if not binary or not Path(binary).is_file() or not os.access(binary, os.X_OK):
        raise WorkerIsolationError("worker executable is unavailable")
    executable = Path(binary).absolute()
    # Reviewed CLI code still has native syscalls. Filesystem-only Landlock cannot
    # deny same-UID ptrace/signals to the body, so every worker needs PID/user isolation.
    backend, abi, bwrap, unavailable = _backend(require_bubblewrap=True)

    runtime_parent = cwd.parent / ".worker-runtime"
    _private_directory(runtime_parent)
    runtime = runtime_parent / provider
    _private_directory(runtime)
    home, temporary = runtime / "home", runtime / "tmp"
    for path in (home, temporary):
        _private_directory(path)
    for path in (home / ".config", home / ".cache", home / ".local", home / ".local" / "share"):
        _private_directory(path)

    read_paths = _runtime_paths(executable)
    runtime_bins = [str(Path(binary).resolve().parent) for name in ("node", "python", "python3")
                    if (binary := shutil.which(name))]
    env = {"PATH": ":".join(dict.fromkeys((str(executable.parent), str(Path(sys.prefix) / "bin"),
                                           *runtime_bins, "/usr/local/bin", "/usr/bin", "/bin"))),
           "HOME": str(home), "TMPDIR": str(temporary), "TMP": str(temporary), "TEMP": str(temporary),
           "LANG": "C.UTF-8", "XDG_CONFIG_HOME": str(home / ".config"),
           "XDG_CACHE_HOME": str(home / ".cache"), "XDG_DATA_HOME": str(home / ".local" / "share"),
           "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"}
    inherited = os.environ if source_env is None else source_env
    for name in (*_TRANSPORT_ENV, *_PROVIDER_ENV.get(provider, ())) if network else ():
        if name in inherited:
            env[name] = inherited[name]
    for name in _CERT_ENV:
        if name in env:
            certificate = Path(env[name]).resolve()
            if not certificate.exists() or not any(certificate.is_relative_to(root.resolve()) for root in _CERT_ROOTS):
                raise WorkerIsolationError(f"transport certificate path outside supported certificate roots: {name}")
            read_paths.append(certificate)
    if provider == "codex":
        env["CODEX_HOME"] = str(home / ".codex")

    supported = _AUTH_FILES.get(provider) if network else None
    configs = ({supported: Path.home() / supported} if supported else {}) if config_files is None else config_files
    copied = []
    for relative, source in configs.items():
        if relative != supported or Path(source).absolute() != (Path.home() / relative).absolute():
            raise WorkerIsolationError("worker configuration copy must name the provider's exact credential file")
        source = Path(source)
        if not source.exists():
            continue
        if source.is_symlink() or not source.is_file() or source.stat().st_nlink != 1:
            raise WorkerIsolationError("worker credential source must be a regular non-symlink file")
        if source.stat().st_size > 1024 * 1024:
            raise WorkerIsolationError("worker credential source exceeds the 1 MiB limit")
        destination = home / relative
        _private_directory(destination.parent)
        if destination.exists() and (destination.is_symlink() or destination.stat().st_nlink != 1):
            raise WorkerIsolationError("worker credential destination must be a private regular file")
        fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        source_fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "wb") as output, os.fdopen(source_fd, "rb") as original:
            output.write(original.read(1024 * 1024 + 1))
        destination.chmod(0o600)
        copied.append(relative)

    parent_pid = os.getpid()
    cpu_limit = max(1, math.ceil(timeout))
    uid_tasks = 0
    for status in Path("/proc").glob("[0-9]*/status"):
        try:
            fields = dict(line.split(":", 1) for line in status.read_text().splitlines() if ":" in line)
            if int(fields["Uid"].split()[0]) == os.getuid():
                uid_tasks += int(fields.get("Threads", "1").strip())
        except (OSError, KeyError, ValueError):
            continue
    process_limit = max(1024, uid_tasks + 128)
    if process_limit > 4096:
        raise WorkerIsolationError("shared UID task count leaves no bounded worker process margin")

    def preexec():
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:  # PR_SET_PDEATHSIG
            raise OSError(ctypes.get_errno(), "worker parent-death signal failed")
        if os.getppid() != parent_pid:
            os.kill(os.getpid(), signal.SIGKILL)
        if libc.prctl(38, 1, 0, 0, 0) != 0:  # PR_SET_NO_NEW_PRIVS
            raise OSError(ctypes.get_errno(), "worker no-new-privileges failed")
        for limit, value in ((resource.RLIMIT_CPU, cpu_limit), (resource.RLIMIT_AS, _MEMORY_LIMIT),
                             (resource.RLIMIT_NPROC, process_limit), (resource.RLIMIT_NOFILE, 256),
                             (resource.RLIMIT_FSIZE, file_bytes), (resource.RLIMIT_CORE, 0)):
            _, hard = resource.getrlimit(limit)
            bounded = value if hard == resource.RLIM_INFINITY else min(value, hard)
            resource.setrlimit(limit, (bounded, bounded))
        if backend == "landlock":
            _install_landlock(read_paths, [cwd, runtime])

    confined_argv = [str(executable), *argv[1:]]
    if backend == "bubblewrap":
        confined_argv = _bubblewrap_argv(bwrap, list(dict.fromkeys(read_paths)), cwd, runtime,
                                        network=network) + ["--", *confined_argv]
    evidence = {"status": "prepared", "filesystem": "os-confined", "mechanism": backend,
                "landlock_abi": abi, "unavailable_mechanisms": unavailable,
                "network": "provider-network-required" if network else "isolated-network-namespace",
                "network_isolated": not network,
                "network_reason": ("provider thinking requires network; filesystem isolation does not authorize network actions"
                                   if network else "untrusted acceptance has no provider network or inherited authentication"),
                "read_roots": [str(p) for p in dict.fromkeys(read_paths)],
                "write_roots": [str(cwd), str(runtime)], "private_home": str(home),
                "copied_config_files": copied, "environment_names": sorted(env),
                "limits": {"cpu_seconds": cpu_limit, "address_space_bytes": _MEMORY_LIMIT,
                           "processes_per_uid": process_limit, "shared_uid_task_baseline": uid_tasks,
                           "process_limit_scope": "per real UID, includes other host processes and threads",
                           "open_files": 256, "file_bytes": file_bytes,
                           "wall_timeout_seconds": timeout},
                "parent_death": "SIGKILL", "no_new_privileges": True}
    evidence["process_isolation"] = "private-pid-user-ipc-uts-namespaces" if backend == "bubblewrap" else "not-isolated"
    evidence["descendant_cleanup"] = ("bubblewrap namespace dies with parent" if backend == "bubblewrap"
                                      else "caller process-group cleanup required; parent-death signal covers direct child")
    return {"argv": confined_argv, "env": env, "preexec_fn": preexec,
            "evidence": evidence, "runtime_root": runtime}
