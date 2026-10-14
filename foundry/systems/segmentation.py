"""#26 Network segmentation without privilege: per-identity egress through one governed relay.

The earlier plan (network namespace plus a proxy on a UNIX socket) needs privileges this body does not have and the
founder has not granted. This mechanism needs none:

  kernel     each confined component runs under the Kernel's reviewed seccomp filter (``tools/offline_test.py``):
             socket, socketcall, connect, bind, listen, accept, io_uring_*, pidfd_getfd, ptrace, bpf and setns all
             fail with EPERM, inherited across exec. It cannot open any socket of any family, so it cannot reach any
             host directly. This is a kernel filter, not a Python check.
  one door   the parent hands it exactly one end of a socketpair (``pass_fds``; every other descriptor is closed).
             On that control channel the component may only ask ``CONNECT <host> <port>``.
  relay      the parent checks the request against the identity's allowlist (exact host and port; no wildcard,
             no DNS chosen by the component). Allowed: the parent opens the upstream connection, creates a fresh
             socketpair for the data and passes the component its end with SCM_RIGHTS, then relays bytes.
             Denied: nothing is connected and the component reads DENIED.
  evidence   every decision (identity, host, port, verdict, bytes each way) is appended to a hash-chained journal;
             editing or dropping an entry breaks the chain.

Inter-organ traffic is the same thing: an organ's allowlist names the loopback endpoints of the organs it may call.

Limits, stated: only components launched through ``run_confined`` are covered; capabilities that run inside the body
process itself (``github.pulls``, ``http.get``, the browser) are not yet routed through the relay. External upstream
connections are refused unless the policy marks the identity ``external: true``: the relay opens them from the body
process, and in an environment whose egress must traverse a mandated proxy the relay must chain to it first (the
2026-09-30 negative evidence: a direct connection bypassed the configured proxy). The filter needs Linux and
libseccomp; without them a launch is refused (fail closed). Nothing here is evidence about arbitrary untrusted code
beyond the syscalls the filter names.
"""
from __future__ import annotations

import array
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[2]
GENESIS = "sha256:" + "0" * 64
MAX_LINE = 512


class SegmentationError(RuntimeError):
    pass


# -- policy ------------------------------------------------------------------------------------------------------

def normalize_policy(policy: dict) -> dict:
    """{identity: {"allow": [[host, port], ...], "external": bool}} with exact, bounded entries."""
    out = {}
    if not isinstance(policy, dict) or len(policy) > 256:
        raise SegmentationError("policy maps at most 256 identities")
    for identity, spec in policy.items():
        if not isinstance(identity, str) or not identity or len(identity) > 128:
            raise SegmentationError("identity must be a short string")
        allow = []
        for entry in (spec or {}).get("allow", []):
            host, port = entry
            if not isinstance(host, str) or not host or len(host) > 253 or "*" in host:
                raise SegmentationError("allowlist hosts are exact names or addresses, never wildcards")
            if type(port) is not int or not 1 <= port <= 65535:
                raise SegmentationError("allowlist ports are integers 1..65535")
            allow.append([host.lower(), port])
        out[identity] = {"allow": sorted(allow), "external": bool((spec or {}).get("external", False))}
    return out


def policy_from_manifests() -> dict:
    """GREG's own capability manifests, read as per-identity egress policy (HTTPS port 443 for declared hosts)."""
    from greg.capabilities import BUILTINS
    policy = {}
    for cid, (manifest, _) in BUILTINS.items():
        hosts = [h for h in (manifest.egress_allowlist or ()) if h]
        if manifest.network == "egress-allowlist" and hosts:
            policy[cid] = {"allow": [[h, 443] for h in hosts if not _loopback(h)] +
                                   [[h, 11434] for h in hosts if _loopback(h)], "external": True}
    return normalize_policy(policy)


def _loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


# -- evidence ----------------------------------------------------------------------------------------------------

class Journal:
    """Append-only, hash-chained relay decisions in one JSONL file."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.lock = threading.Lock()

    def append(self, entry: dict) -> dict:
        with self.lock:
            rows = self.read()
            prev = rows[-1]["hash"] if rows else GENESIS
            body = {**entry, "seq": len(rows), "prev": prev}
            body["hash"] = "sha256:" + hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a") as fh:
                fh.write(json.dumps(body, sort_keys=True) + "\n")
            return body

    def read(self) -> list[dict]:
        if not self.path.is_file():
            return []
        return [json.loads(line) for line in self.path.read_text().splitlines() if line.strip()]

    def verify(self) -> dict:
        prev = GENESIS
        for i, row in enumerate(self.read()):
            body = {k: v for k, v in row.items() if k != "hash"}
            digest = "sha256:" + hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
            if row.get("seq") != i or row.get("prev") != prev or row.get("hash") != digest:
                return {"intact": False, "broken_at": i}
            prev = row["hash"]
        return {"intact": True, "entries": len(self.read()), "head": prev}


# -- relay -------------------------------------------------------------------------------------------------------

class Relay:
    def __init__(self, policy: dict, journal: Journal, *, connect=socket.create_connection):
        self.policy = normalize_policy(policy)
        self.journal = journal
        self.connect = connect             # injectable only so tests can prove a denied request never connects
        self.pumps: list[threading.Thread] = []

    def drain(self, timeout: float = 10.0):
        """Wait until every relayed stream has closed and been journaled."""
        for thread in list(self.pumps):
            thread.join(timeout=timeout)

    def decide(self, identity: str, host: str, port: int) -> str | None:
        spec = self.policy.get(identity)
        if spec is None:
            return "identity has no egress policy"
        if [host.lower(), port] not in spec["allow"]:
            return "host and port are not on this identity's allowlist"
        if not _loopback(host) and not spec["external"]:
            return "external upstream not declared for this identity"
        return None

    MAX_REQUESTS = 64          # per control channel: a compromised component cannot exhaust the relay

    def serve(self, identity: str, control: socket.socket):
        """One component's control channel, until it closes."""
        with control:
            buf, requests = b"", 0
            while True:
                try:
                    chunk = control.recv(MAX_LINE)
                except OSError:
                    return
                if not chunk:
                    return
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    requests += 1
                    if requests > self.MAX_REQUESTS:
                        self.journal.append({"identity": identity, "verdict": "DENIED", "why": "request limit"})
                        return
                    self._request(identity, control, line)
                if len(buf) > MAX_LINE:
                    self.journal.append({"identity": identity, "verdict": "DENIED", "why": "oversized request"})
                    return

    def _request(self, identity, control, line: bytes):
        parts = line.decode("utf-8", "replace").split()
        if len(parts) != 3 or parts[0] != "CONNECT" or not parts[2].isdigit():
            self.journal.append({"identity": identity, "verdict": "DENIED", "why": "malformed request",
                                 "request": line[:120].decode("utf-8", "replace")})
            control.sendall(b"DENIED malformed\n")
            return
        host, port = parts[1], int(parts[2])
        why = self.decide(identity, host, port)
        if why:
            self.journal.append({"identity": identity, "host": host, "port": port, "verdict": "DENIED", "why": why})
            control.sendall(b"DENIED " + why.encode() + b"\n")
            return
        try:
            upstream = self.connect((host, port), timeout=10)
        except OSError as exc:
            self.journal.append({"identity": identity, "host": host, "port": port, "verdict": "UPSTREAM_FAILED",
                                 "why": type(exc).__name__})
            control.sendall(b"FAILED upstream\n")
            return
        mine, theirs = socket.socketpair()
        socket.send_fds(control, [b"OK\n"], [theirs.fileno()])
        theirs.close()
        entry = {"identity": identity, "host": host, "port": port, "verdict": "ALLOWED"}
        pump = threading.Thread(target=self._pump, args=(entry, mine, upstream), daemon=True)
        self.pumps.append(pump)
        pump.start()

    def _pump(self, entry, inner: socket.socket, upstream: socket.socket):
        counts = {"sent": 0, "received": 0}

        def copy(src, dst, key):
            try:
                while True:
                    data = src.recv(65536)
                    if not data:
                        break
                    dst.sendall(data)
                    counts[key] += len(data)
            except OSError:
                pass
            finally:
                try:
                    dst.shutdown(socket.SHUT_WR)
                except OSError:
                    pass
        t = threading.Thread(target=copy, args=(inner, upstream, "sent"), daemon=True)
        t.start()
        copy(upstream, inner, "received")
        t.join(timeout=10)
        inner.close()
        upstream.close()
        self.journal.append({**entry, "bytes_sent": counts["sent"], "bytes_received": counts["received"]})


def _confine():
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        from offline_test import install_filter
        install_filter()
    except Exception:
        os._exit(97)           # fail closed: a component never runs unconfined


def run_confined(argv: list, *, identity: str, relay: Relay, cwd: Path, timeout: int = 30,
                 env: dict | None = None) -> subprocess.CompletedProcess:
    """Run one component with no socket of its own and one governed door, the relay."""
    if sys.platform != "linux":
        raise SegmentationError("kernel socket confinement requires Linux; launch refused")
    control, child = socket.socketpair()
    worker = threading.Thread(target=relay.serve, args=(identity, control), daemon=True)
    worker.start()
    try:
        proc = subprocess.run(argv, cwd=cwd, capture_output=True, timeout=timeout, preexec_fn=_confine,
                              pass_fds=(child.fileno(),), close_fds=True,
                              env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "PYTHONPATH": str(ROOT),
                                   "PYTHONDONTWRITEBYTECODE": "1", "GREG_EGRESS_FD": str(child.fileno()),
                                   **(env or {})})
    finally:
        child.close()
    worker.join(timeout=5)
    if proc.returncode == 97:
        raise SegmentationError("seccomp confinement unavailable; launch refused")
    return proc


# -- the component side ------------------------------------------------------------------------------------------

def egress_connect(host: str, port: int) -> socket.socket:
    """Inside a confined component: ask the relay for one connection. Raises PermissionError when denied."""
    control = socket.socket(fileno=int(os.environ["GREG_EGRESS_FD"]))
    try:
        control.sendall(f"CONNECT {host} {port}\n".encode())
        msg, fds, _, _ = socket.recv_fds(control, 512, 1)
    finally:
        control.detach()                  # the control channel stays open for further requests
    if not msg.startswith(b"OK"):
        raise PermissionError(msg.decode().strip())
    return socket.socket(fileno=fds[0])


# -- Foundry contract --------------------------------------------------------------------------------------------

PROBE = r'''
import ctypes, errno, json, os, socket, sys
from foundry.systems.segmentation import egress_connect
out = {}
libc = ctypes.CDLL(None, use_errno=True)
fd = libc.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
out["direct_socket"] = "EPERM" if fd < 0 and ctypes.get_errno() == errno.EPERM else "OPENED"
fd = libc.socket(socket.AF_UNIX, socket.SOCK_STREAM, 0)
out["unix_socket"] = "EPERM" if fd < 0 and ctypes.get_errno() == errno.EPERM else "OPENED"
for name, (host, port) in json.loads(sys.argv[1]).items():
    try:
        conn = egress_connect(host, port)
        conn.sendall(b"GET / HTTP/1.0\r\nHost: x\r\n\r\n")
        data = b""
        while True:
            chunk = conn.recv(65536)
            if not chunk:
                break
            data += chunk
        out[name] = "OK " + data.split(b"\r\n\r\n", 1)[-1].decode()
    except PermissionError as exc:
        out[name] = "DENIED"
print(json.dumps(out))
'''


def exercise(root) -> dict:
    """Loopback-only, controlled: one allowed organ endpoint, one undeclared TEST-NET host, one foreign identity."""
    import http.server
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = b"organ-reply"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    attempted = []

    def connect(address, timeout=10):
        attempted.append(list(address))
        return socket.create_connection(address, timeout=timeout)
    journal = Journal(root / "egress-journal.jsonl")
    relay = Relay({"organ.reader": {"allow": [["127.0.0.1", port]]}, "organ.other": {"allow": []}}, journal,
                  connect=connect)
    targets = {"allowed": ["127.0.0.1", port], "undeclared_testnet": ["192.0.2.1", 443],
               "undeclared_port": ["127.0.0.1", port + 1 if port < 65535 else port - 1]}
    try:
        reader = run_confined([sys.executable, "-s", "-c", PROBE, json.dumps(targets)], identity="organ.reader",
                              relay=relay, cwd=root)
        other = run_confined([sys.executable, "-s", "-c", PROBE, json.dumps({"allowed": ["127.0.0.1", port]})],
                             identity="organ.other", relay=relay, cwd=root)
    finally:
        server.shutdown()
        server.server_close()
    relay.drain()                         # every relayed stream closed and journaled
    a, b = json.loads(reader.stdout), json.loads(other.stdout)
    return {"reader": a, "other_identity": b,
            "upstream_connections": len(attempted), "upstream_hosts": sorted({t[0] for t in attempted}),
            "decisions": sorted(f"{r['identity']}:{r['verdict']}" for r in journal.read()),
            "journal_chain": journal.verify()["intact"],
            "never_connected_to_denied": all(t[0] != "192.0.2.1" for t in attempted) and len(attempted) == 1}


QUERY_OPS = {"policy": lambda a, r: {"policy": policy_from_manifests()},
             "journal": lambda a, r: {"entries": Journal(Path(r) / "egress-journal.jsonl").read()[-int(a.get("limit", 50)):],
                                      "chain": Journal(Path(r) / "egress-journal.jsonl").verify()}}
APPLY_OPS: dict = {}       # launching a component is the body's act, never a free Foundry op
