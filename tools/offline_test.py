"""Fail-closed Linux no-network test launcher, independent of application mocks.

Blocks socket creation, including localhost TCP. Anonymous AF_UNIX socketpairs
remain available for asyncio. Filters survive fork/exec; no credentials, proxy,
Python startup hooks or inherited descriptor > 2 are passed to the child.
This is network containment, not a container or filesystem sandbox. Only use
reviewed source with synthetic fixtures. Never use it to claim packaged HTTP.
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import errno
import json
import os
from pathlib import Path
import resource
import subprocess


def install_filter():
    library = ctypes.util.find_library("seccomp")
    if not library:
        raise RuntimeError("libseccomp unavailable; execution blocked")
    seccomp = ctypes.CDLL(library, use_errno=True)
    seccomp.seccomp_init.argtypes = [ctypes.c_uint32]
    seccomp.seccomp_init.restype = ctypes.c_void_p
    seccomp.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    seccomp.seccomp_syscall_resolve_name.restype = ctypes.c_int
    seccomp.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32,
                                        ctypes.c_int, ctypes.c_uint]
    seccomp.seccomp_load.argtypes = [ctypes.c_void_p]
    seccomp.seccomp_release.argtypes = [ctypes.c_void_p]
    context = seccomp.seccomp_init(0x7FFF0000)  # SCMP_ACT_ALLOW
    if not context:
        raise RuntimeError("seccomp initialization failed")
    try:
        # No alternate socket, inherited-fd, async-I/O or process-injection path.
        for name in ("socket", "socketcall", "connect", "bind", "listen",
                     "accept", "accept4", "io_uring_setup", "io_uring_enter",
                     "io_uring_register", "ptrace", "process_vm_readv",
                     "process_vm_writev", "pidfd_getfd", "bpf", "setns"):
            number = seccomp.seccomp_syscall_resolve_name(name.encode())
            if number >= 0:
                result = seccomp.seccomp_rule_add(
                    context, 0x00050000 | errno.EPERM, number, 0)
                if result:
                    raise RuntimeError(f"seccomp rule failed: {name}: {result}")
        result = seccomp.seccomp_load(context)
        if result:
            raise RuntimeError(f"seccomp load failed: {result}; execution blocked")
    finally:
        seccomp.seccomp_release(context)


PROBE = r'''
import ctypes, errno, json, os, socket
libc = ctypes.CDLL(None, use_errno=True)
denied = []
for family in (socket.AF_INET, socket.AF_INET6, socket.AF_UNIX):
    for kind in (socket.SOCK_STREAM, socket.SOCK_DGRAM):
        fd = libc.socket(family, kind, 0)
        if fd >= 0:
            os.close(fd)
            raise RuntimeError('socket creation escaped OS isolation')
        if ctypes.get_errno() != errno.EPERM:
            raise RuntimeError('unexpected socket refusal')
        denied.append([family, kind])
left, right = socket.socketpair()
left.send(b'fixture')
assert right.recv(7) == b'fixture'
left.close(); right.close()
assert not any(k in os.environ for k in (
    'TWITTER_BEARER_TOKEN', 'OPENAI_API_KEY', 'AWS_ACCESS_KEY_ID',
    'WEALTHMACHINE_SIGNING_KEY', 'JWT_SECRET_KEY', 'HTTP_PROXY', 'HTTPS_PROXY'))
print(json.dumps({'direct_libc_socket_denials': denied,
                  'anonymous_local_socketpair': 'passed',
                  'credential_environment': 'clean'}))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", required=True)
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--tmp", required=True)
    parser.add_argument("--pythonpath", action="append", default=[])
    parser.add_argument("--producer")
    parser.add_argument("--probe-only", action="store_true")
    parser.add_argument("args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    python = str(Path(args.python).absolute())
    temporary = Path(args.tmp).resolve()
    temporary.mkdir(parents=True, exist_ok=True)
    env = {"PATH": str(Path(python).parent) + ":/usr/local/bin:/usr/bin:/bin",
           "LANG": "C.UTF-8", "TMPDIR": str(temporary),
           "PYTHONDONTWRITEBYTECODE": "1", "PIP_NO_INDEX": "1"}
    if args.pythonpath:
        env["PYTHONPATH"] = os.pathsep.join(str(Path(p).resolve()) for p in args.pythonpath)
    if args.producer:
        env["DALEOBANKS_SOURCE"] = str(Path(args.producer).resolve())
    os.environ.clear()
    os.environ.update(env)
    os.closerange(3, resource.getrlimit(resource.RLIMIT_NOFILE)[0])
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (180, 180))
    install_filter()
    # Native syscall probes run in a separate exec, before project imports.
    probe = subprocess.run([python, "-I", "-c", PROBE], env=env,
                           capture_output=True, text=True, timeout=10)
    if probe.returncode:
        raise RuntimeError("inherited isolation probe failed: " + probe.stderr)
    print("OFFLINE_PREFLIGHT=" + probe.stdout.strip(), flush=True)
    if args.probe_only:
        return
    command = args.args
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        parser.error("provide Python arguments after --")
    print("OFFLINE_COMMAND=" + json.dumps([python, *command]), flush=True)
    os.chdir(args.cwd)
    os.execve(python, [python, *command], env)


if __name__ == "__main__":
    main()
