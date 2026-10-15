"""#26: the relay's door for programs that need ordinary sockets (a browser, a provider CLI) but must not have a network.

``run_confined`` covers components that can live without sockets: its seccomp filter denies every socket call and
the component asks the relay for each connection over one inherited control channel. A browser or a coding agent's
provider client cannot run that way. This door gives them the same single way out without that filter:

  namespace  the program runs in a bubblewrap network namespace (``--unshare-net``, no privilege): only its own
             loopback exists, so no address outside it, including the body's loopback, is reachable directly.
  door       inside the namespace, before the program starts, a small front listens on the namespace's loopback as an
             HTTP proxy (CONNECT for TLS; absolute-form requests for plain-http loopback pages). Each request becomes
             one ``CONNECT <host> <port>`` line on the inherited control channel.
  relay      the body's ``Relay`` decides against the identity's exact allowlist, journals the decision in its hash
             chain, opens the upstream (through the mandated proxy when there is one) and passes back a data socket.
  program    started with HTTPS_PROXY/HTTP_PROXY naming the door, and any ``{door}`` in its argv replaced by the door's
             address (``--proxy-server={door}`` for Chromium).

The control channel is an inherited descriptor when the body starts the namespace itself. When another launcher
starts the program (Playwright's driver starts Chromium, so no descriptor of the body's survives the way there), the
door instead connects once to a Unix socket in a private directory; the body accepts exactly one connection from its
own user and stops listening. Descriptors the launcher hands the program (Playwright's pipe on 3 and 4) are kept with
``keep_fds``; nothing else of the door's, the control channel included, reaches the program.

Limits, stated: the namespace needs bubblewrap with unprivileged user namespaces; without it nothing is launched
(fail closed). The door trusts nothing the program sends beyond one request line per connection; a program that
ignores the proxy settings simply has no network. Name resolution happens at the relay, never inside the namespace.
"""
from __future__ import annotations

import os
from pathlib import Path
import socket
import threading
import time

# Runs inside the namespace as ``python -I -c DOOR <control fd> -- <argv...>``; standard library only.
DOOR = r'''
import os, socket, subprocess, sys, threading
if sys.argv[1].startswith("unix:"):
    control = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    control.connect(sys.argv[1][5:])
else:
    control = socket.socket(fileno=int(sys.argv[1]))
rest, keep = sys.argv[2:], ()
while rest and rest[0] != "--":
    option = rest.pop(0)
    if option.startswith("--keep="):
        keep = tuple(int(x) for x in option[7:].split(",") if x)
argv = rest[1:]
lock = threading.Lock()
listener = socket.socket()
listener.bind(("127.0.0.1", 0))
listener.listen(64)
door = "http://127.0.0.1:%d" % listener.getsockname()[1]

def pump(a, b):
    def copy(src, dst):
        try:
            while True:
                data = src.recv(65536)
                if not data:
                    break
                dst.sendall(data)
        except OSError:
            pass
        finally:
            try:
                dst.shutdown(socket.SHUT_WR)
            except OSError:
                pass
    t = threading.Thread(target=copy, args=(a, b), daemon=True)
    t.start()
    copy(b, a)
    t.join(10)
    a.close()
    b.close()

def ask(host, port):
    with lock:
        control.sendall(("CONNECT %s %d\n" % (host, port)).encode())
        msg, fds, _, _ = socket.recv_fds(control, 512, 1)
    if msg.startswith(b"OK") and fds:
        return socket.socket(fileno=fds[0]), ""
    for fd in fds:
        os.close(fd)
    return None, msg.decode("utf-8", "replace").strip()[:200] or "relay closed"

def handle(client):
    try:
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = client.recv(4096)
            if not chunk or len(head) > 16384:
                client.close()
                return
            head += chunk
        header, _, rest = head.partition(b"\r\n\r\n")
        lines = header.split(b"\r\n")
        parts = lines[0].decode("latin-1").split()
        if len(parts) != 3:
            raise ValueError("malformed request line")
        method, target, version = parts
        if method == "CONNECT":
            host, _, port = target.rpartition(":")
            upstream, why = ask(host.strip("[]"), int(port))
            if upstream is None:
                client.sendall(("HTTP/1.1 403 Forbidden\r\nX-Relay: %s\r\nContent-Length: 0\r\n\r\n" % why).encode())
                client.close()
                return
            client.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
            if rest:
                upstream.sendall(rest)
        elif target.startswith("http://"):
            hostport, slash, path = target[len("http://"):].partition("/")
            host, _, port = hostport.rpartition(":") if ":" in hostport.rsplit("]", 1)[-1] else (hostport, "", "80")
            upstream, why = ask(host.strip("[]"), int(port or 80))
            if upstream is None:
                client.sendall(("HTTP/1.1 403 Forbidden\r\nX-Relay: %s\r\nContent-Length: 0\r\n\r\n" % why).encode())
                client.close()
                return
            kept = [l for l in lines[1:] if not l.lower().startswith((b"proxy-", b"connection:", b"keep-alive:"))]
            request = ("%s /%s %s" % (method, path, version)).encode()
            upstream.sendall(b"\r\n".join([request, *kept, b"Connection: close"]) + b"\r\n\r\n" + rest)
        else:
            client.sendall(b"HTTP/1.1 405 Method Not Allowed\r\nContent-Length: 0\r\n\r\n")
            client.close()
            return
        pump(client, upstream)
    except (OSError, ValueError):
        try:
            client.close()
        except OSError:
            pass

def serve():
    while True:
        client, _ = listener.accept()
        threading.Thread(target=handle, args=(client,), daemon=True).start()

threading.Thread(target=serve, daemon=True).start()
env = {**os.environ, "HTTPS_PROXY": door, "HTTP_PROXY": door, "https_proxy": door, "http_proxy": door,
       "ALL_PROXY": door, "NO_PROXY": "", "no_proxy": ""}
sys.exit(subprocess.call([a.replace("{door}", door) for a in argv], env=env, pass_fds=keep))
'''


def namespace_argv(*, writable=(), readonly=(), chdir: str, tmp_roots=("/tmp",)) -> list[str]:
    """The one bubblewrap network namespace every door program runs in (no privilege): its own user, pid, ipc, uts
    and network namespaces, the read-only root, private /dev/shm and scratch roots, then the program's own writable
    directories and read-only files (re-exposed when a private scratch root hid them). Callers check that bubblewrap
    namespaces work first and refuse without them (fail closed)."""
    import shutil
    bwrap = shutil.which("bwrap")
    if not bwrap:
        raise FileNotFoundError("bubblewrap (bwrap) is not installed")
    roots = sorted({str(r) for r in tmp_roots})
    return [bwrap, "--unshare-user", "--unshare-pid", "--unshare-ipc", "--unshare-uts", "--unshare-net",
            "--die-with-parent", "--new-session", "--ro-bind", "/", "/", "--proc", "/proc", "--dev", "/dev",
            "--tmpfs", "/dev/shm", *[a for r in roots for a in ("--tmpfs", r)],
            *[a for w in writable if w for a in ("--bind", str(w), str(w))],
            *[a for r in readonly if r and Path(r).exists() for a in ("--ro-bind", str(r), str(r))],
            "--chdir", str(chdir), "--"]


def door_argv(python: str, control, argv: list[str], *, keep_fds=()) -> list[str]:
    """The command that runs inside the namespace: the door first, then the program behind it.

    ``control`` is an inherited descriptor (int) or ``Door.control`` (``"unix:<path>"``); ``keep_fds`` are descriptors
    above stderr the program itself must receive from its launcher."""
    if not argv or not all(isinstance(a, str) for a in argv):
        raise ValueError("door needs a program argv of strings")
    control = control if isinstance(control, str) and control.startswith("unix:") else str(int(control))
    keep = [int(fd) for fd in keep_fds]
    if any(fd <= 2 for fd in keep):
        raise ValueError("keep_fds names descriptors above stderr only")
    return [python, "-I", "-c", DOOR, control, *([f"--keep={','.join(map(str, keep))}"] if keep else []), "--", *argv]


class Door:
    """The body's half: one control channel, served by the relay for one identity, for one confined program.

    By default the channel is a socket pair whose child end is passed to the namespace (``fd``). With ``path`` the body
    listens on a Unix socket there instead (``control``) and serves the first connection from its own user only."""

    def __init__(self, relay, identity: str, *, max_requests: int = 512, path: Path | None = None,
                 accept_seconds: float = 60.0):
        self.relay, self.identity, self.path = relay, identity, path
        self._parent = self._child = self._listener = None
        self._stop = threading.Event()
        if path is None:
            self._parent, self._child = socket.socketpair()
            target, args = relay.serve, (identity, self._parent)
        else:
            if not Path(path).parent.is_dir() or Path(path).parent.stat().st_mode & 0o077:
                raise ValueError("a door socket lives in an existing directory private to the body's user")
            self._listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._listener.bind(str(path))
            os.chmod(path, 0o600)
            self._listener.listen(1)
            self._listener.settimeout(0.2)
            target, args = self._accept_once, (accept_seconds,)
        self._thread = threading.Thread(target=target, args=args, kwargs={"max_requests": max_requests}, daemon=True)
        self._thread.start()

    def _accept_once(self, accept_seconds: float, *, max_requests: int):
        deadline = time.monotonic() + accept_seconds
        try:
            while not self._stop.is_set() and time.monotonic() < deadline:
                try:
                    conn, _ = self._listener.accept()
                except socket.timeout:
                    continue
                uid = int.from_bytes(conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)[4:8], "little")
                if uid != os.getuid():          # only the body's own user; anyone else is turned away, still waiting
                    conn.close()
                    continue
                self._parent = conn
                break
        finally:
            self._listener.close()
            Path(self.path).unlink(missing_ok=True)
        if self._parent is not None and not self._stop.is_set():
            self.relay.serve(self.identity, self._parent, max_requests=max_requests)

    @property
    def fd(self) -> int:
        """Pass this descriptor (``pass_fds``) to the namespace; nothing else of the body's goes with it."""
        if self._child is None:
            raise ValueError("this door listens on a path; pass ``control`` instead")
        return self._child.fileno()

    @property
    def control(self):
        """What ``door_argv`` takes: the descriptor, or ``unix:<path>`` for a door that listens."""
        return f"unix:{self.path}" if self.path is not None else self.fd

    def close(self, timeout: float = 10.0):
        """After the program exits: release the channel and wait until every relayed stream is journaled."""
        self._stop.set()
        if self._child is not None:
            self._child.close()
        if self._parent is not None:
            try:
                self._parent.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        self._thread.join(timeout)
        if self._parent is not None:
            self._parent.close()
        self.relay.drain(timeout)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
