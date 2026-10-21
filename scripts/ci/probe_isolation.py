"""Read-only host facility inventory; no sandbox completion claim.

Kernel reference: https://docs.kernel.org/userspace-api/landlock.html
This probes this actual runner, not the disconnected Codex execution host.
"""
import ctypes
import json
import platform
import shutil
import subprocess

report = {"kernel": platform.release(), "machine": platform.machine(),
          "scope": "actual CI host; facilities are not escape-test or capability completion evidence"}
if platform.system() == "Linux" and platform.machine() in {"x86_64", "aarch64"}:
    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long
    ctypes.set_errno(0)
    abi = libc.syscall(444, None, 0, 1)
    report["landlock"] = {"abi": abi if abi >= 0 else None, "errno": ctypes.get_errno() if abi < 0 else None}
else:
    report["landlock"] = {"abi": None, "reason": "unprobed architecture"}
report["tools"] = {tool: bool(shutil.which(tool)) for tool in ("docker", "podman", "runsc", "bwrap", "unshare")}
if report["tools"]["docker"]:
    try:
        result = subprocess.run(["docker", "version", "--format", "{{json .Server.Version}}"],
                                text=True, capture_output=True, timeout=5, check=False)
        report["docker_server"] = {"exit": result.returncode, "version": result.stdout.strip()[:128]}
    except subprocess.TimeoutExpired:
        report["docker_server"] = {"reason": "5 second probe timeout"}
print(json.dumps(report, sort_keys=True))
