"""#31 Owned web server: canonical pages and portals whose every byte is provably the institution's.

Mechanism recombination (not a re-implementation of a web server — Python's
ThreadingHTTPServer is the commodity part):

  content     every page version is stored by content (#36) and committed as a
              versioned record with reason and evidence (#3)
  proof       the current site is a Merkle tree over ``path=content-address``
              leaves (#6); its root is signed with the site's Ed25519 key (#7),
              so anyone holding the public key can check that a page they were
              served is exactly what the institution published at that root
  serving     responses carry ETag = content hash, the version number and a
              ``rel=provenance`` link; conditional GET answers 304; a page whose
              stored bytes no longer match their hash is refused, not served
  portal      /portal/<customer>/... needs a short-lived bearer token signed by
              the site key and scoped to that customer
  exposure    the server binds loopback only; binding any other interface is a
              publication and is refused without a Consequence Gate grant

Owned destination, portable proof: a platform can send traffic, but the page,
its history and the customer's portal live here.
"""
from __future__ import annotations

import base64
import hashlib
import http.server
import ipaddress
import json
import posixpath
import threading
import time
import urllib.parse
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from foundry.systems import cas, versions

CONTENT_TYPES = {".html": "text/html; charset=utf-8", ".json": "application/json", ".txt": "text/plain; charset=utf-8",
                 ".svg": "image/svg+xml", ".css": "text/css", ".xml": "application/xml"}


class SiteError(RuntimeError):
    pass


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _canon(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def normalize(path: str) -> str:
    """One canonical form per page; anything that climbs out of the site is refused."""
    raw = urllib.parse.unquote(path.split("?", 1)[0])
    if "\x00" in raw or "\\" in raw or any(part == ".." for part in raw.split("/")):
        raise SiteError(f"refused path {path!r}")
    norm = posixpath.normpath("/" + raw.lstrip("/"))
    return "/" if norm in ("/", "/.") else norm


def _record_name(path: str) -> str:
    """Version-store name for a page (slashes are not names); the path itself is in the record."""
    return "page-" + hashlib.sha256(path.encode()).hexdigest()[:24]


class Site:
    def __init__(self, root: Path, *, key_seed: bytes | None = None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        key_path = self.root / "site_ed25519.key"
        if not key_path.exists():
            key = Ed25519PrivateKey.from_private_bytes(key_seed) if key_seed else Ed25519PrivateKey.generate()
            key_path.write_bytes(key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                                                   serialization.NoEncryption()))
            key_path.chmod(0o600)
        self._key = Ed25519PrivateKey.from_private_bytes(key_path.read_bytes())
        self.public_key = self._key.public_key().public_bytes(serialization.Encoding.Raw,
                                                              serialization.PublicFormat.Raw).hex()

    # -- state ------------------------------------------------------------------------
    def _state(self) -> dict:
        p = self.root / "site.json"
        return json.loads(p.read_text()) if p.exists() else {"pages": {}, "generation": 0}

    def _save(self, state: dict) -> None:
        tmp = self.root / "site.tmp"
        tmp.write_text(json.dumps(state, sort_keys=True, indent=1))
        tmp.replace(self.root / "site.json")

    # -- publishing (internal: loopback serving only) ---------------------------------------
    def publish(self, path: str, content: bytes | str, *, reason: str, evidence: list[str],
                content_type: str | None = None) -> dict:
        path = normalize(path)
        if not reason or not evidence:
            raise SiteError("a page version needs a reason and evidence")
        data = content.encode() if isinstance(content, str) else content
        address = cas.put(self.root / "cas", data)
        ctype = content_type or CONTENT_TYPES.get(Path(path).suffix, "text/html; charset=utf-8")
        record = versions.commit(self.root / "versions", _record_name(path), {"path": path, "address": address,
                                                                                    "content_type": ctype},
                                 reason=reason, evidence=evidence)
        state = self._state()
        state["pages"][path] = {"address": address, "content_type": ctype, "version": record["n"]}
        state["generation"] += 1
        self._save(state)
        return {"path": path, "version": record["n"], "address": address, "site_root": self.site_root()["root"]}

    def _leaves(self, state: dict) -> list[str]:
        return [f"{p}={state['pages'][p]['address']}" for p in sorted(state["pages"])]

    def site_root(self) -> dict:
        from provenance.proof import MerkleTree
        state = self._state()
        if not state["pages"]:
            raise SiteError("nothing published")
        body = {"root": MerkleTree(self._leaves(state)).root, "pages": len(state["pages"]),
                "generation": state["generation"]}
        return {**body, "public_key": self.public_key, "signature": self._key.sign(_canon(body)).hex()}

    def provenance(self, path: str) -> dict:
        from provenance.proof import MerkleTree
        path = normalize(path)
        state = self._state()
        if path not in state["pages"]:
            raise SiteError(f"no page {path}")
        tree = MerkleTree(self._leaves(state))
        proof = tree.prove(f"{path}={state['pages'][path]['address']}")
        history = [{"n": v["n"], "reason": v["reason"], "evidence": v["evidence"], "record": v["address"]}
                   for v in versions.history(self.root / "versions", _record_name(path))]
        return {"path": path, "current": state["pages"][path], "history": history,
                "inclusion": {"leaf": proof.leaf_record_hash, "index": proof.leaf_index, "tree_size": proof.tree_size,
                              "steps": [{"sibling": s.sibling, "side": s.side} for s in proof.steps], "root": proof.root}}

    # -- portal tokens -----------------------------------------------------------------------
    def issue_token(self, customer: str, *, now: float, ttl_s: int = 900) -> str:
        if not customer or "/" in customer:
            raise SiteError("customer id must be a single path segment")
        claims = {"sub": customer, "exp": int(now) + int(ttl_s), "scope": f"/portal/{customer}/"}
        payload = _canon(claims)
        return f"{_b64(payload)}.{_b64(self._key.sign(payload))}"

    def check_token(self, token: str, path: str, *, now: float) -> str:
        try:
            payload_b64, sig_b64 = token.split(".")
            payload = _unb64(payload_b64)
            self._key.public_key().verify(_unb64(sig_b64), payload)
            claims = json.loads(payload)
        except (ValueError, InvalidSignature):
            raise SiteError("invalid token") from None
        if now >= claims["exp"]:
            raise SiteError("token expired")
        if not (path + "/").startswith(claims["scope"]) and not path.startswith(claims["scope"]):
            raise SiteError("token does not cover this portal")
        return claims["sub"]

    # -- rendering (the server's single code path; also used directly by GREG ops) ----------------
    def render(self, raw_path: str, headers: dict, *, now: float) -> tuple[int, dict, bytes]:
        try:
            path = normalize(raw_path)
        except SiteError as exc:
            return 400, {"Content-Type": "text/plain"}, str(exc).encode()
        if path == "/.well-known/site-root":
            try:
                return 200, {"Content-Type": "application/json"}, _canon(self.site_root())
            except SiteError as exc:
                return 404, {"Content-Type": "text/plain"}, str(exc).encode()
        if path == "/.well-known/provenance":
            target = urllib.parse.parse_qs(urllib.parse.urlsplit(raw_path).query).get("path", ["/"])[0]
            try:
                return 200, {"Content-Type": "application/json"}, _canon(self.provenance(target))
            except SiteError as exc:
                return 404, {"Content-Type": "text/plain"}, str(exc).encode()
        if path.startswith("/portal/"):
            auth = headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                return 401, {"Content-Type": "text/plain", "WWW-Authenticate": "Bearer"}, b"portal requires a token"
            try:
                self.check_token(auth[7:], path, now=now)
            except SiteError as exc:
                return 403, {"Content-Type": "text/plain"}, str(exc).encode()
        page = self._state()["pages"].get(path)
        if page is None:
            return 404, {"Content-Type": "text/plain"}, b"not found"
        try:
            body = cas.get(self.root / "cas", page["address"])
        except Exception as exc:  # integrity failure: never serve bytes that do not match their address
            return 500, {"Content-Type": "text/plain"}, f"integrity failure; refusing to serve ({type(exc).__name__})".encode()
        out = {"Content-Type": page["content_type"], "ETag": f'"{page["address"]}"', "Cache-Control": "no-cache",
               "X-Content-Version": str(page["version"]),
               "Link": f'</.well-known/provenance?path={urllib.parse.quote(path)}>; rel="provenance"'}
        if headers.get("If-None-Match", "").strip() == out["ETag"]:
            return 304, out, b""
        return 200, out, body


def verify_served(public_key_hex: str, site_root: dict, provenance: dict, body: bytes) -> dict:
    """What any third party can check with only the site's public key."""
    from provenance.proof import InclusionProof, ProofStep, verify_inclusion
    signed = {k: site_root[k] for k in ("root", "pages", "generation")}
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex)).verify(bytes.fromhex(site_root["signature"]),
                                                                                 _canon(signed))
        signature_ok = True
    except InvalidSignature:
        signature_ok = False
    inc = provenance["inclusion"]
    proof = InclusionProof(leaf_record_hash=inc["leaf"], leaf_index=inc["index"], tree_size=inc["tree_size"],
                           steps=[ProofStep(**s) for s in inc["steps"]], root=inc["root"])
    address = "sha256:" + hashlib.sha256(body).hexdigest()
    return {"signature_ok": signature_ok, "inclusion_ok": verify_inclusion(proof),
            "root_matches_signed_root": inc["root"] == site_root["root"],
            "body_matches_leaf": inc["leaf"] == f"{provenance['path']}={address}"}


class _Handler(http.server.BaseHTTPRequestHandler):
    site: Site = None  # set per server
    clock = staticmethod(time.time)

    def _respond(self, head_only: bool) -> None:
        status, headers, body = self.site.render(self.path, dict(self.headers), now=self.clock())
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not head_only and status != 304:
            self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        self._respond(False)

    def do_HEAD(self):  # noqa: N802
        self._respond(True)

    def log_message(self, *args):  # the journal is the site's history, not stderr
        pass


def serve(site: Site, *, host: str = "127.0.0.1", port: int = 0, public_grant: dict | None = None,
          clock=time.time) -> http.server.ThreadingHTTPServer:
    """Serve on loopback. Any other interface is publication and needs a gate grant first."""
    if not ipaddress.ip_address(host).is_loopback and not (public_grant and public_grant.get("state") == "recorded"):
        raise SiteError(f"binding {host} publishes the site; it needs a Consequence Gate grant")
    handler = type("SiteHandler", (_Handler,), {"site": site, "clock": staticmethod(clock)})
    server = http.server.ThreadingHTTPServer((host, port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


QUERY_OPS = {"site_root": lambda a, r: Site(r).site_root(),
             "provenance": lambda a, r: Site(r).provenance(a["path"]),
             "render": lambda a, r: (lambda s, h, b: {"status": s, "headers": h, "body": b.decode(errors="replace")})(
                 *Site(r).render(a["path"], a.get("headers", {}), now=float(a.get("now", time.time()))))}
APPLY_OPS = {"publish": lambda a, r: Site(r).publish(a["path"], a["content"], reason=a["reason"], evidence=a["evidence"],
                                                     content_type=a.get("content_type")),
             "issue_portal_token": lambda a, r: {"token": Site(r).issue_token(a["customer"], now=float(a["now"]),
                                                                              ttl_s=int(a.get("ttl_s", 900)))}}


def exercise(root) -> dict:
    import urllib.error
    import urllib.request
    root = Path(root)
    now = 1_790_000_000.0
    site = Site(root / "site", key_seed=bytes(32 * [21]))
    site.publish("/index.html", "<h1>Proof rail</h1><p>v1</p>", reason="launch", evidence=["decision:launch"])
    site.publish("/index.html", "<h1>Proof rail</h1><p>v2: audited suppliers paid faster</p>", reason="add outcome",
                 evidence=["outcome:pilot-1"])
    site.publish("/guide/start.html", "<h2>Start here</h2>", reason="knowledge hub", evidence=["territory:entry"])
    site.publish("/portal/acme/receipts.json", json.dumps({"receipts": ["r-1"]}), reason="customer receipts",
                 evidence=["receipt:r-1"])
    server = serve(site, clock=lambda: now)
    base = f"http://127.0.0.1:{server.server_address[1]}"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # loopback only, never via a proxy

    def get(path, headers=None):
        try:
            with opener.open(urllib.request.Request(base + path, headers=headers or {}), timeout=10) as r:
                return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as exc:
            return exc.code, dict(exc.headers), exc.read()
    try:
        status, headers, body = get("/index.html")
        root_doc = json.loads(get("/.well-known/site-root")[2])
        prov = json.loads(get("/.well-known/provenance?path=/index.html")[2])
        checked = verify_served(site.public_key, root_doc, prov, body)
        not_modified = get("/index.html", {"If-None-Match": headers["ETag"]})[0]
        traversal = get("/../site_ed25519.key")[0]
        token = site.issue_token("acme", now=now)
        portal_ok = get("/portal/acme/receipts.json", {"Authorization": f"Bearer {token}"})[0]
        other_token = site.issue_token("globex", now=now)
        portal_wrong = get("/portal/acme/receipts.json", {"Authorization": f"Bearer {other_token}"})[0]
        portal_none = get("/portal/acme/receipts.json")[0]
        expired = site.issue_token("acme", now=now - 3600, ttl_s=60)
        portal_expired = get("/portal/acme/receipts.json", {"Authorization": f"Bearer {expired}"})[0]
        forged = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
        portal_forged = get("/portal/acme/receipts.json", {"Authorization": f"Bearer {forged}"})[0]
        # tamper with stored bytes: the server refuses rather than serve unproven content
        stored = site.root / "cas" / "objects"
        victim = next(p for p in stored.rglob("*") if p.is_file() and b"Start here" in p.read_bytes())
        victim.write_bytes(b"<h2>Defaced</h2>")
        tampered = get("/guide/start.html")[0]
    finally:
        server.shutdown()
        server.server_close()
    public_refused = None
    try:
        serve(site, host="0.0.0.0")
    except SiteError as exc:
        public_refused = str(exc)
    forged_body = verify_served(site.public_key, root_doc, prov, b"<h1>Proof rail</h1><p>forged</p>")
    return {"served": status, "version": headers["X-Content-Version"], "etag_is_content_hash":
            headers["ETag"].strip('"') == "sha256:" + hashlib.sha256(body).hexdigest(),
            "third_party_verification": checked, "forged_body_verification": forged_body,
            "history": [h["reason"] for h in prov["history"]], "not_modified": not_modified,
            "traversal": traversal, "portal": {"own": portal_ok, "other_customer": portal_wrong, "no_token": portal_none,
                                               "expired": portal_expired, "forged": portal_forged},
            "tampered_page": tampered, "public_bind_refused": public_refused is not None,
            "site_root_pages": root_doc["pages"]}
