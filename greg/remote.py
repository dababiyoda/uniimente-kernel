"""GREG remote channel: the phone reaches the body without becoming a second authority.

    iPhone (Safari, non-extractable Ed25519 device key)
        -> HTTPS on the tailnet (Tailscale Serve terminates TLS on the Mac)
        -> greg serve on 127.0.0.1 (this module)
        -> signed envelope dropped into the body inbox
        -> the body re-verifies, applies, records

What this server is allowed to do, and nothing else:

* serve the static phone client;
* answer reads (status, decisions, VEPMC) from the ledger opened READ-ONLY, and
  only for a request signed by the founder key or a delegated, unexpired device key;
* accept a signed command envelope, pre-verify it (so unauthenticated traffic
  cannot flood the inbox), and drop it atomically into the inbox.

It never opens the ledger for writing, never holds a private key, never issues a
grant and never decides anything. The body verifies every command again. It binds
to loopback only: the supported off-machine route is an authenticated TLS proxy
on the same machine (``tailscale serve --bg --https=443 http://127.0.0.1:8765``),
because WebCrypto requires a secure context and the tailnet admits only
Alfonso's enrolled devices.
"""
from __future__ import annotations

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
from pathlib import Path
import secrets

from events.spine import EventSpine
from greg.body import Layout, device_delegations, status
from greg.founder import FounderAuthError, FounderVerifier
from greg.journal import Journal
from provenance.ledger import EvidenceLedger

PHONE = Path(__file__).resolve().parent / "phone"
ASSETS = {"/": ("index.html", "text/html; charset=utf-8"),
          "/app.js": ("app.js", "text/javascript; charset=utf-8"),
          "/core.js": ("core.js", "text/javascript; charset=utf-8")}
MAX_COMMAND_BYTES = 64 * 1024
MAX_PENDING = 100
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; script-src 'self'; connect-src 'self'; style-src 'self' "
                               "'unsafe-inline'; img-src 'self' data:; base-uri 'none'; form-action 'none'; "
                               "frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", "Cache-Control": "no-store",
    "Cross-Origin-Opener-Policy": "same-origin", "Cross-Origin-Resource-Policy": "same-origin",
}


class RemoteError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


class _Reader:
    """A read-only view of the body's ledger for one request (revocation is immediate)."""

    def __init__(self, home: Path):
        self.layout = Layout(home)
        self.config = json.loads(self.layout.config.read_text())

    def __enter__(self):
        self.ledger = EvidenceLedger(self.config["constitution_hash"], str(self.layout.ledger), read_only=True)
        self.journal = Journal(EventSpine(self.ledger), actor="spiffe://uniimente.internal/greg/remote-reader")
        founder = {}
        for event in self.journal.replay("founder."):
            if event.type == "greg.founder.enrolled":
                founder[event.payload["key_id"]] = event.payload["public_key"]
            elif event.type == "greg.founder.key_rotated":
                founder.pop(event.payload["old_key_id"], None)
                founder[event.payload["new_key_id"]] = event.payload["new_public_key"]
        nonces = {e.payload["nonce"] for e in self.journal.replay("command.accepted")}
        self.verifier = FounderVerifier(body_id=self.config["body_id"], enrolled=founder,
                                        seen_nonce=nonces.__contains__, devices=device_delegations(self.journal))
        return self

    def __exit__(self, *exc):
        self.ledger.close()


def handle(home: Path, method: str, path: str, headers, body: bytes, *, now: datetime | None = None):
    """Pure request handler (tested without sockets). Returns (status, content_type, bytes)."""
    now = now or datetime.now(timezone.utc)
    layout = Layout(home)
    if method == "GET" and path in ASSETS:
        name, ctype = ASSETS[path]
        return 200, ctype, (PHONE / name).read_bytes()
    if method == "GET" and path == "/api/hello":
        config = json.loads(layout.config.read_text())
        return _json(200, {"protocol": "greg-remote-v1", "body_id": config["body_id"],
                           "server_time": now.isoformat().replace("+00:00", "Z")})
    if method == "GET" and path in ("/api/status", "/api/decisions", "/api/vepmc", "/api/commands"):
        with _Reader(home) as reader:
            try:
                principal = reader.verifier.verify_read(headers, method=method, path=path, now=now)
            except (FounderAuthError, ValueError) as exc:
                raise RemoteError(401, str(exc))
            if path == "/api/vepmc":
                from greg import metrics
                return _json(200, {"principal": principal, **metrics.vepmc(reader.journal)})
            if path == "/api/commands":
                recent = [{"kind": e.payload["kind"], "nonce": e.payload["nonce"], "signer": e.payload.get("signer"),
                           "status": "APPLIED"} for e in reader.journal.replay("command.accepted")][-20:]
                return _json(200, {"principal": principal, "recent": recent,
                                   "rejected": [{"file": e.payload["file"], "reason": e.payload["reason"]}
                                                for e in reader.journal.replay("command.rejected")][-10:]})
        full = status(home)
        data = full["decisions_required"] if path == "/api/decisions" else full
        return _json(200, {"principal": principal, "data": data})
    if method == "POST" and path == "/api/command":
        if len(body) > MAX_COMMAND_BYTES:
            raise RemoteError(413, "command too large")
        try:
            envelope = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise RemoteError(400, "command must be JSON")
        with _Reader(home) as reader:
            try:  # pre-verification only; the body verifies again before anything happens
                reader.verifier.verify(envelope, now=now)
                principal = reader.verifier.principal(envelope, now=now)
            except (FounderAuthError, ValueError, KeyError, TypeError) as exc:
                raise RemoteError(403, str(exc))
        if len(list(layout.inbox.glob("*.json"))) >= MAX_PENDING:
            raise RemoteError(429, "inbox full; the body is not keeping up")
        name = f"{envelope['issued_at'].replace(':', '')}-remote-{envelope['kind'].lower()}-{envelope['nonce'][:8]}"
        target = layout.inbox / f"{name}-{secrets.token_hex(4)}.json"
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(envelope))
        tmp.replace(target)
        return _json(202, {"delivered_to_inbox": target.name, "signer": principal, "nonce": envelope["nonce"],
                           "note": "the body verifies and applies it; check /api/commands"})
    raise RemoteError(404, "not found")


def _json(status_code: int, data) -> tuple[int, str, bytes]:
    return status_code, "application/json", json.dumps(data, default=str).encode("utf-8")


def make_server(home: str | Path, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    if not ipaddress.ip_address(host).is_loopback:
        raise ValueError("greg serve binds to loopback only; expose it through an authenticated TLS proxy "
                         "such as `tailscale serve`")
    home = Path(home).expanduser().resolve()

    class Handler(BaseHTTPRequestHandler):
        server_version = "greg-remote/1"
        sys_version = ""

        def _reply(self, code, ctype, payload):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(payload)))
            for k, v in SECURITY_HEADERS.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(payload)

        def _run(self, method):
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_COMMAND_BYTES:
                return self._reply(*_json(413, {"error": "command too large"}))
            body = self.rfile.read(length) if length else b""
            try:
                self._reply(*handle(home, method, self.path.split("?")[0], self.headers, body))
            except RemoteError as exc:
                self._reply(*_json(exc.status, {"error": str(exc)}))

        def do_GET(self):
            self._run("GET")

        def do_POST(self):
            self._run("POST")

        def log_message(self, fmt, *args):  # no request logging of signatures or bodies
            pass

    return ThreadingHTTPServer((host, port), Handler)


def serve(home: str | Path, host: str = "127.0.0.1", port: int = 8765) -> int:
    server = make_server(home, host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
