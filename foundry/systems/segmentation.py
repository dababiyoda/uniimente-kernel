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

Limits, stated: only components launched through ``run_confined``, or behind ``relay_door`` in a network namespace,
are covered. On a body with confined egress that is ``http.get``, ``github.pulls`` and ``brief.engineering`` (here) and
``browser.render`` and coding workers (the door). Still outside: ``browser.session`` (Playwright), the paid model
routes called from the body process, anchoring, and the DALEOBANKS bridge. External upstream
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
import re
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

# The relay's refusals of a destination, as journaled. Its other DENIED rows (a request limit, an oversized or
# malformed request) refuse a request without consulting any allowlist, so they are not destination decisions.
NO_POLICY = "identity has no egress policy"
NOT_ALLOWED = "host and port are not on this identity's allowlist"
NOT_EXTERNAL = "external upstream not declared for this identity"
DESTINATION_REFUSALS = frozenset({NO_POLICY, NOT_ALLOWED, NOT_EXTERNAL})
QUARANTINED = "TORN_TAIL_QUARANTINED"   # a chained record that a torn final line was moved to a sidecar


class Journal:
    """Append-only, hash-chained relay decisions in one JSONL file.

    Past ``max_records`` the oldest lines move to a sealed segment and the hot
    file is rewritten as a ``COMPACTED`` checkpoint plus the newest
    ``keep_records`` rows, re-chained so ``verify`` still holds. Segment files
    together stay within ``max_segment_bytes``; past that they are deleted and
    their bytes are folded into ``digested_head``. The hot chain stays checkable.
    The folded payloads are then attested by that head, not stored.
    """

    def __init__(self, path: Path, *, max_records: int = 8192, keep_records: int = 1024,
                 max_segment_bytes: int = 1_048_576):
        if keep_records < 1 or max_records <= keep_records or max_segment_bytes < 1:
            raise ValueError("journal retention bounds must leave a hot tail under a positive segment cap")
        self.path = Path(path)
        self.lock = threading.Lock()
        self.max_records = max_records
        self.keep_records = keep_records
        self.max_segment_bytes = max_segment_bytes

    def append(self, entry: dict) -> dict:
        # One chain, possibly several writers (the body and its console both decide egress): the read of the head and
        # the append are one step under an exclusive file lock, not only a thread lock.
        import fcntl
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path.with_name(self.path.name + ".lock"), "a") as guard:
                fcntl.flock(guard, fcntl.LOCK_EX)
                try:
                    moved = self._repair_tail()
                    rows = self.read()                     # damage in a committed row raises: never append onto it
                    if moved:
                        rows.append(self._chain(rows, {"verdict": QUARANTINED, **moved}))
                    if len(rows) >= self.max_records:
                        rows = self._compact(rows)
                    return self._chain(rows, entry)
                finally:
                    fcntl.flock(guard, fcntl.LOCK_UN)

    def _compact(self, rows: list[dict]) -> list[dict]:
        """Seal the oldest rows and leave a checkpoint plus a re-chained hot tail."""
        prefix, keep = rows[:-self.keep_records], rows[-self.keep_records:]
        raw = self.path.read_bytes()
        lines = [line for line in raw.split(b"\n") if line.strip()]
        if len(lines) < len(prefix):
            raise SegmentationError("journal compact could not find the rows it is sealing")
        segment = b"\n".join(lines[:len(prefix)]) + b"\n"
        digest = "sha256:" + hashlib.sha256(segment).hexdigest()
        side = self.path.with_name(f"{self.path.name}.segment-{digest[7:23]}")
        if side.exists() and side.read_bytes() != segment:
            raise SegmentationError(f"{side.name} exists with other bytes")
        if not side.exists():
            temporary = side.with_name(side.name + ".tmp")
            temporary.write_bytes(segment)
            os.replace(temporary, side)
        checkpoint = {
            "verdict": "COMPACTED",
            "folded": len(prefix),
            "folded_head": prefix[-1]["hash"],
            "segment": side.name,
            "segment_sha256": digest,
            "segment_retained": True,
            "seq": 0,
            "prev": GENESIS,
        }
        self._collapse_segments(checkpoint)
        checkpoint["hash"] = "sha256:" + hashlib.sha256(
            json.dumps(checkpoint, sort_keys=True).encode()).hexdigest()
        chained = [checkpoint]
        for entry in keep:
            payload = {k: v for k, v in entry.items() if k not in ("seq", "prev", "hash")}
            chained.append(self._link(chained, payload))
        text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in chained)
        tmp = self.path.with_name(self.path.name + ".compact-tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self.path)
        return chained

    def _collapse_segments(self, checkpoint: dict) -> None:
        segments = sorted(self.path.parent.glob(self.path.name + ".segment-*"))
        total = sum(path.stat().st_size for path in segments)
        if total <= self.max_segment_bytes:
            return
        head = checkpoint.get("digested_head", GENESIS)
        count = int(checkpoint.get("digested_count") or 0)
        for path in segments:
            raw = path.read_bytes()
            head = "sha256:" + hashlib.sha256(head.encode() + raw).hexdigest()
            count += raw.count(b"\n")
            path.unlink()
        checkpoint["digested_head"] = head
        checkpoint["digested_count"] = count
        checkpoint["segment_retained"] = False
        checkpoint.pop("segment", None)
        checkpoint.pop("segment_sha256", None)

    def _link(self, rows: list[dict], entry: dict) -> dict:
        """The next chained row, not yet written. ``_chain`` writes it."""
        prev = rows[-1]["hash"] if rows else GENESIS
        body = {**entry, "seq": len(rows), "prev": prev}
        body["hash"] = "sha256:" + hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
        return body

    def _chain(self, rows: list[dict], entry: dict) -> dict:
        body = self._link(rows, entry)
        with open(self.path, "a") as fh:
            fh.write(json.dumps(body, sort_keys=True) + "\n")
        return body

    def _rows(self) -> tuple[list[dict], bytes, int | None]:
        """The complete rows; a final line cut short by a crash mid-append (no newline, not JSON); and the index of
        the first committed row that does not parse, if any (damage, not an interrupted append)."""
        if not self.path.is_file():
            return [], b"", None
        *lines, tail = self.path.read_bytes().split(b"\n")
        rows = []
        for line in lines:
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                return rows, b"", len(rows)
        if tail.strip():
            try:
                rows.append(json.loads(tail))
            except ValueError:
                return rows, tail, None
        return rows, b"", None

    def _repair_tail(self) -> dict | None:
        """Before an append (under the file lock): a torn final line moves to a sidecar named by its digest, created
        exclusively and synced before the journal is cut back, so a later crash never overwrites an earlier one; the
        move is then chained as its own row. A complete final row that lost its newline gets one, so the next row is
        never glued onto it."""
        if not self.path.is_file():
            return None
        raw = self.path.read_bytes()
        if not raw or raw.endswith(b"\n"):
            return None
        cut = raw.rfind(b"\n") + 1
        tail = raw[cut:]
        try:
            json.loads(tail)
        except ValueError:
            digest = hashlib.sha256(tail).hexdigest()
            side = self.path.with_name(f"{self.path.name}.torn-{cut}-{digest[:16]}")
            try:
                fd = os.open(side, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                if hashlib.sha256(side.read_bytes()).hexdigest() != digest:
                    raise SegmentationError(f"{side.name} exists with other bytes") from None
            else:
                with os.fdopen(fd, "wb") as fh:
                    fh.write(tail)
                    fh.flush()
                    os.fsync(fh.fileno())
            folder = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(folder)
            finally:
                os.close(folder)
            os.truncate(self.path, cut)
            return {"offset": cut, "bytes": len(tail), "sha256": "sha256:" + digest, "sidecar": side.name}
        with open(self.path, "ab") as fh:
            fh.write(b"\n")
        return None

    def read(self) -> list[dict]:
        rows, _, damaged = self._rows()
        if damaged is not None:
            raise ValueError(f"the relay journal does not parse at entry {damaged}")
        return rows

    def verify(self) -> dict:
        """The chain's state, as a result, never an exception: damage that does not parse is reported where it is."""
        prev = GENESIS
        rows, torn, damaged = self._rows()
        for i, row in enumerate(rows):
            body = {k: v for k, v in row.items() if k != "hash"}
            digest = "sha256:" + hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
            if row.get("seq") != i or row.get("prev") != prev or row.get("hash") != digest:
                return {"intact": False, "broken_at": i}
            prev = row["hash"]
        if damaged is not None:
            return {"intact": False, "broken_at": damaged, "malformed": True}
        out = {"intact": True, "entries": len(rows), "head": prev}
        if torn:
            # An append a crash cut short. A torn ALLOWED row can be the record of a connection that already ran (the
            # relay journals it when the connection ends), so it counts as no verdict and is shown, never dropped:
            # the next append moves it to a sidecar and chains the move.
            out["torn_tail_bytes"] = len(torn)
        quarantined = sum(1 for r in rows if r.get("verdict") == QUARANTINED)
        if quarantined:
            out["quarantined_tails"] = quarantined
        return out


# -- relay -------------------------------------------------------------------------------------------------------

def proxy_from_environment(environ=None) -> dict | None:
    """The mandated egress proxy, if this environment declares one (HTTPS_PROXY / https_proxy).

    Returned as {host, port, authorization}; the authorization header value is never journaled."""
    import base64
    from urllib.parse import unquote, urlsplit
    environ = os.environ if environ is None else environ
    raw = environ.get("HTTPS_PROXY") or environ.get("https_proxy")
    if not raw:
        return None
    parts = urlsplit(raw if "://" in raw else "http://" + raw)
    if parts.scheme != "http" or not parts.hostname:
        raise SegmentationError("only an http:// CONNECT proxy can be chained")
    auth = None
    if parts.username is not None:
        token = f"{unquote(parts.username)}:{unquote(parts.password or '')}".encode()
        auth = "Basic " + base64.b64encode(token).decode()
    return {"host": parts.hostname, "port": parts.port or 80, "authorization": auth}


def _via_proxy(proxy: dict, host: str, port: int, connect) -> socket.socket:
    """Open a tunnel to host:port through the mandated proxy with HTTP CONNECT (RFC 9110 section 9.3.6)."""
    sock = connect((proxy["host"], proxy["port"]), timeout=10)
    request = f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n"
    if proxy.get("authorization"):
        request += f"Proxy-Authorization: {proxy['authorization']}\r\n"
    sock.sendall((request + "\r\n").encode())
    head = b""
    while b"\r\n\r\n" not in head:
        chunk = sock.recv(1)
        if not chunk or len(head) > 8192:
            sock.close()
            raise OSError("proxy closed or sent an oversized CONNECT response")
        head += chunk
    status = head.split(b"\r\n", 1)[0].split()
    if len(status) < 2 or status[1] != b"200":
        sock.close()
        raise OSError("proxy refused the tunnel: " + head.split(b"\r\n", 1)[0].decode("latin-1")[:120])
    return sock


class Relay:
    def __init__(self, policy: dict, journal: Journal, *, connect=socket.create_connection, proxy: dict | None = None):
        self.policy = normalize_policy(policy)
        self.journal = journal
        self.connect = connect             # injectable only so tests can prove a denied request never connects
        self.proxy = proxy                 # external upstreams go through it; loopback never does
        self.pumps: list[threading.Thread] = []

    def drain(self, timeout: float = 10.0):
        """Wait until every relayed stream has closed and been journaled."""
        for thread in list(self.pumps):
            thread.join(timeout=timeout)

    def decide(self, identity: str, host: str, port: int) -> str | None:
        spec = self.policy.get(identity)
        if spec is None:
            return NO_POLICY
        if [host.lower(), port] not in spec["allow"]:
            return NOT_ALLOWED
        if not _loopback(host) and not spec["external"]:
            return NOT_EXTERNAL
        return None

    MAX_REQUESTS = 64          # per control channel: a compromised component cannot exhaust the relay

    def serve(self, identity: str, control: socket.socket, *, max_requests: int | None = None):
        """One component's control channel, until it closes. A browser or provider client opens many connections, so
        its door may raise the per-channel limit; it stays a bound."""
        limit = self.MAX_REQUESTS if max_requests is None else max_requests
        if type(limit) is not int or not 1 <= limit <= 4096:
            raise SegmentationError("max_requests is an integer from 1 to 4096")
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
                    if requests > limit:
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
        via = "direct"
        try:
            if self.proxy and not _loopback(host):
                via = f"proxy {self.proxy['host']}:{self.proxy['port']}"
                upstream = _via_proxy(self.proxy, host, port, self.connect)
            else:
                upstream = self.connect((host, port), timeout=10)
        except OSError as exc:
            self.journal.append({"identity": identity, "host": host, "port": port, "verdict": "UPSTREAM_FAILED",
                                 "via": via, "why": f"{type(exc).__name__}: {exc}"[:200]})
            control.sendall(b"FAILED upstream\n")
            return
        mine, theirs = socket.socketpair()
        socket.send_fds(control, [b"OK\n"], [theirs.fileno()])
        theirs.close()
        entry = {"identity": identity, "host": host, "port": port, "verdict": "ALLOWED", "via": via}
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


def _load_filter():
    """The seccomp filter, loaded once into this (parent) process. A child that imported it from disk
    at fork time could be handed a replaced tools/offline_test.py by any earlier writer."""
    try:
        module = sys.modules.get("offline_test")
        if module is None:
            sys.path.insert(0, str(ROOT / "tools"))
            import offline_test as module  # type: ignore
        return module.install_filter
    except Exception:
        return None


_INSTALL_FILTER = _load_filter() if sys.platform == "linux" else None


def _confiner(refused_fd: int):
    """preexec: install the in-memory filter or fail closed. A failure is written to a close-on-exec pipe only
    the parent holds, then raised, so the component never runs and its own exit status never reads as a
    refusal (nor a refusal as a component that ran)."""
    def confine():
        try:
            _INSTALL_FILTER()      # in memory since import; the child imports nothing
        except Exception:
            os.write(refused_fd, b"N")
            raise
    return confine


def run_confined(argv: list, *, identity: str, relay: Relay, cwd: Path, timeout: int = 30,
                 env: dict | None = None, input_bytes: bytes | None = None) -> subprocess.CompletedProcess:
    """Run one component with no socket of its own and one governed door, the relay."""
    if sys.platform != "linux":
        raise SegmentationError("kernel socket confinement requires Linux; launch refused")
    control, child = socket.socketpair()
    worker = threading.Thread(target=relay.serve, args=(identity, control), daemon=True)
    worker.start()
    refused_r, refused_w = os.pipe()
    try:
        stdin = {"stdin": subprocess.DEVNULL} if input_bytes is None else {"input": input_bytes}
        proc = subprocess.run(argv, cwd=cwd, capture_output=True, timeout=timeout, preexec_fn=_confiner(refused_w),
                              **stdin,
                              pass_fds=(child.fileno(),), close_fds=True,
                              env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "PYTHONPATH": str(ROOT),
                                   "PYTHONDONTWRITEBYTECODE": "1", "GREG_EGRESS_FD": str(child.fileno()),
                                   **(env or {})})
    except subprocess.SubprocessError as exc:
        if isinstance(exc, subprocess.TimeoutExpired):
            raise
        os.set_blocking(refused_r, False)
        try:
            refused = os.read(refused_r, 1) == b"N"
        except BlockingIOError:
            refused = False
        if not refused:
            raise
        raise SegmentationError("seccomp confinement unavailable; launch refused") from None
    finally:
        child.close()
        os.close(refused_r)
        os.close(refused_w)
    worker.join(timeout=5)
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


FETCH = r'''
import base64, json, os, ssl, sys
from foundry.systems.segmentation import egress_connect
host, port, path, limit = sys.argv[1], int(sys.argv[2]), sys.argv[3], int(sys.argv[4])
flags = sys.argv[5:]
# Extra request headers (e.g. a credential) and a request body arrive on stdin, never in argv or the environment.
method, extra, payload = "GET", {}, b""
if "--headers-stdin" in flags:
    extra = json.loads(sys.stdin.read() or "{}")
elif "--request-stdin" in flags:
    spec = json.loads(sys.stdin.read())
    method, extra, payload = spec["method"], spec.get("headers", {}), base64.b64decode(spec.get("body_b64", ""))
try:
    raw = egress_connect(host, port)
except PermissionError as exc:
    print(json.dumps({"denied": str(exc)}))
    sys.exit(0)
headers = {"Host": host, "User-Agent": "uniimente-greg/0.1", **extra,
           **({"Content-Length": str(len(payload))} if payload or method != "GET" else {}), "Connection": "close"}
request = (f"{method} {path} HTTP/1.1\r\n" + "".join(f"{k}: {v}\r\n" for k, v in headers.items()) + "\r\n").encode()
if "--plain" in flags:                      # loopback only; the parent refuses plain http anywhere else
    stream = raw
else:
    context = ssl.create_default_context(cafile=os.environ.get("GREG_EGRESS_CAFILE") or None)
    stream = context.wrap_socket(raw, server_hostname=host)
with stream:
    stream.sendall(request + payload)
    data = b""
    while len(data) <= limit + 65536:
        chunk = stream.recv(65536)
        if not chunk:
            break
        data += chunk
head, _, body = data.partition(b"\r\n\r\n")
lines = head.split(b"\r\n")
status = int(lines[0].split()[1])
if any(l.lower().replace(b" ", b"") == b"transfer-encoding:chunked" for l in lines[1:]):
    decoded, rest = b"", body
    while rest:
        size_line, _, rest = rest.partition(b"\r\n")
        size = int(size_line.split(b";")[0] or b"0", 16)
        if size == 0:
            break
        decoded, rest = decoded + rest[:size], rest[size + 2:]
    body = decoded
print(json.dumps({"status": status, "body": base64.b64encode(body[:limit + 1]).decode(),
                  "peer_verified": "--plain" not in flags}))
'''


HEADER_NAME = re.compile(r"^[A-Za-z0-9-]{1,64}$")


def confined_fetch(url: str, *, identity: str, relay: Relay, cwd: Path, max_bytes: int, timeout: int = 30,
                   headers: dict | None = None) -> dict:
    """HTTPS GET performed by a component that holds no socket of its own: TLS (and certificate verification)
    happens inside the confined child, the bytes cross only the relay, and the relay journals the decision.
    ``headers`` reach the child on stdin only, so a credential never appears in argv, the environment or the
    egress journal."""
    return confined_request(url, identity=identity, relay=relay, cwd=cwd, max_bytes=max_bytes, timeout=timeout,
                            headers=headers)


def confined_request(url: str, *, identity: str, relay: Relay, cwd: Path, max_bytes: int, timeout: int = 30,
                     headers: dict | None = None, method: str = "GET", body: bytes | None = None) -> dict:
    """``confined_fetch`` for any of GET or POST with a body (an RFC 3161 query, say). HTTPS; plain http only to a
    loopback host. Headers and body reach the child on stdin only."""
    from urllib.parse import urlsplit
    parts = urlsplit(url)
    plain = parts.scheme == "http" and _loopback(parts.hostname or "")
    if not parts.hostname or not (parts.scheme == "https" or plain):
        raise SegmentationError("confined fetch is HTTPS only (plain http only to loopback)")
    if method not in ("GET", "POST") or (body is not None and method != "POST"):
        raise SegmentationError("confined requests are GET, or POST with a body")
    path = (parts.path or "/") + (("?" + parts.query) if parts.query else "")
    for name, value in (headers or {}).items():
        if not HEADER_NAME.match(str(name)) or any(c in str(value) for c in "\r\n\x00") or \
                name.lower() in ("host", "connection", "transfer-encoding", "content-length"):
            raise SegmentationError(f"request header {name!r} refused")
    env = {}
    if os.environ.get("GREG_EGRESS_CAFILE"):
        env["GREG_EGRESS_CAFILE"] = os.environ["GREG_EGRESS_CAFILE"]
    # -P: neither the working directory nor the script's is put on sys.path, so nothing written into a mission
    # workspace can be imported ahead of the standard library; the component also runs from an empty
    # directory of its own. Only PYTHONPATH (the Kernel) and the interpreter's own paths are searched.
    argv = [sys.executable, "-P", "-s", "-c", FETCH, parts.hostname, str(parts.port or (80 if plain else 443)), path,
            str(max_bytes)]
    import base64
    if method == "GET":
        flags, stdin = (["--headers-stdin"] if headers else []), (json.dumps(headers).encode() if headers else None)
    else:
        flags = ["--request-stdin"]
        stdin = json.dumps({"method": method, "headers": headers or {},
                            "body_b64": base64.b64encode(body or b"").decode()}).encode()
    with tempfile.TemporaryDirectory(prefix="greg-fetch-") as empty:
        proc = run_confined(argv + flags + (["--plain"] if plain else []), identity=identity, relay=relay,
                            cwd=Path(empty), timeout=timeout, env=env, input_bytes=stdin)
    relay.drain()
    if proc.returncode != 0:
        raise SegmentationError("confined fetch failed: " + proc.stderr.decode("utf-8", "replace")[-300:])
    out = json.loads(proc.stdout)
    if "denied" in out:
        raise PermissionError(out["denied"])
    return {"status": out["status"], "body": base64.b64decode(out["body"])}


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
