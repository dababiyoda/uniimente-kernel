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

Limits, stated: the namespace needs bubblewrap with unprivileged user namespaces; without it nothing is launched
(fail closed). The door trusts nothing the program sends beyond one request line per connection; a program that
ignores the proxy settings simply has no network. Name resolution happens at the relay, never inside the namespace.
"""
from __future__ import annotations

import socket
import threading

# Runs inside the namespace as ``python -I -c DOOR <control fd> -- <argv...>``; standard library only.
DOOR = r'''
import os, socket, subprocess, sys, threading
control = socket.socket(fileno=int(sys.argv[1]))
argv = sys.argv[3:]
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
sys.exit(subprocess.call([a.replace("{door}", door) for a in argv], env=env))
'''


def door_argv(python: str, control_fd: int, argv: list[str]) -> list[str]:
    """The command that runs inside the namespace: the door first, then the program behind it."""
    if not argv or not all(isinstance(a, str) for a in argv):
        raise ValueError("door needs a program argv of strings")
    return [python, "-I", "-c", DOOR, str(int(control_fd)), "--", *argv]


class Door:
    """The body's half: one control channel, served by the relay for one identity, for one confined program."""

    def __init__(self, relay, identity: str, *, max_requests: int = 512):
        self.relay, self.identity = relay, identity
        self._parent, self._child = socket.socketpair()
        self._thread = threading.Thread(target=relay.serve, args=(identity, self._parent),
                                        kwargs={"max_requests": max_requests}, daemon=True)
        self._thread.start()

    @property
    def fd(self) -> int:
        """Pass this descriptor (``pass_fds``) to the namespace; nothing else of the body's goes with it."""
        return self._child.fileno()

    def close(self, timeout: float = 10.0):
        """After the program exits: release the channel and wait until every relayed stream is journaled."""
        self._child.close()
        try:
            self._parent.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self._thread.join(timeout)
        self.relay.drain(timeout)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
