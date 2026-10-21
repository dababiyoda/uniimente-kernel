"""#26 follow-up: the shared egress opener after the bypass review of c47600e/0c4849b.

Three findings, each reproduced on 0c4849b:

* a same-host redirect whose ``Location`` urllib's own handler repairs (a raw space, raw
  UTF-8) was refused, or crashed in http.client and left a read-only fetch UNCERTAIN;
* a credential followed a redirect to another port on the same host (the drop compared
  host names, not origins);
* foundry/systems/containers.py kept urllib's default redirect handler, which copies
  ``Authorization`` to any redirect host, and opened whatever token realm a response named.

The Location tests need real http.client (tests/fake_web.py replaces ``https_open`` and never
forms a request line), so they run a loopback TLS server with a throwaway certificate. No
traffic leaves the machine.
"""
from __future__ import annotations

import datetime as dt
import http.server
import ipaddress
import ssl
import threading
import urllib.request
from dataclasses import replace

import pytest

from greg import egress
from greg.capabilities import BUILTINS, CapabilityError, InvocationContext, SecretBroker, http_get
from tests.fake_web import FakeWeb


# -- a loopback HTTPS server (real TLS, real http.client) ---------------------------

class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        # http.server writes header values as ISO-8859-1; '/café' is sent as its raw UTF-8 bytes, as real
        # servers send it, and http.client hands urllib those bytes decoded as ISO-8859-1.
        redirects = {"/space": "/My Report", "/utf8": "/café".encode().decode("iso-8859-1"), "/nopath": None}
        if self.path in redirects:
            self.send_response(302)
            target = redirects[self.path]
            self.send_header("Location", target if target else f"https://localhost:{self.server.server_port}")
            self.end_headers()
            return
        if self.path in ("/My%20Report", "/caf%C3%A9", "/"):
            body = f"landed on {self.path}".encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, *args):
        pass


def _certificate(directory):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - dt.timedelta(minutes=5)).not_valid_after(now + dt.timedelta(hours=1))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost"),
                                                        x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]),
                           critical=False)
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .sign(key, hashes.SHA256()))
    cert_path, key_path = directory / "cert.pem", directory / "key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                           serialization.NoEncryption()))
    return cert_path, key_path


@pytest.fixture
def tls_server(tmp_path, monkeypatch):
    cert, key = _certificate(tmp_path)
    httpd = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    # The client trusts only the throwaway certificate and never routes loopback through a proxy.
    monkeypatch.setenv("SSL_CERT_FILE", str(cert))
    monkeypatch.delenv("SSL_CERT_DIR", raising=False)
    for name in ("no_proxy", "NO_PROXY"):
        monkeypatch.setenv(name, "localhost,127.0.0.1")
    try:
        yield httpd.server_address[1]
    finally:
        httpd.shutdown()
        httpd.server_close()


def _ctx(tmp_path):
    manifest = replace(BUILTINS["http.get"][0], egress_allowlist=("localhost",))
    return InvocationContext(workspace=tmp_path / "ws", read_roots=(tmp_path,),
                             secrets=SecretBroker(tmp_path / "s.json"), manifest=manifest)


@pytest.mark.parametrize("path, landed", [("/space", "/My%20Report"), ("/utf8", "/caf%C3%A9"),
                                          ("/nopath", "/")])
def test_a_same_host_location_urllib_repairs_is_repaired_then_checked(tmp_path, tls_server, path, landed):
    """0c4849b: '/My Report' refused as whitespace, '/café' raised UnicodeEncodeError in http.client."""
    out = http_get({"url": f"https://localhost:{tls_server}{path}"}, _ctx(tmp_path))
    assert out["status"] == 200 and out["text"] == f"landed on {landed}"
    assert out["final_url"] == f"https://localhost:{tls_server}{landed}"


def test_a_repaired_redirect_through_the_authority_office_is_done_not_uncertain(tmp_path, tls_server):
    """A read-only fetch must never wait on founder reconciliation because a Location had a raw byte."""
    from datetime import datetime, timedelta, timezone
    from greg.body import Body
    from greg.lightcone import LightCone
    from tests.greg_fixtures import make_body
    home, key, body_id, data = make_body(tmp_path)
    body = Body(home).open()
    try:
        manifest = replace(BUILTINS["http.get"][0], egress_allowlist=("localhost",))
        ctx = InvocationContext(workspace=tmp_path / "ws", read_roots=(data,), secrets=body.secrets,
                                manifest=manifest)
        cone = LightCone.from_dict({"capabilities": ["http.get"], "targets": ["https:*"],
                                    "max_consequence_class": "read_only", "budget_usd": 0.0,
                                    "horizon": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()})
        out = body.office.act(mission_id="m:t", cone=cone, command_digest="sha256:x", manifest=manifest,
                              adapter=http_get, ctx=ctx, params={"url": f"https://localhost:{tls_server}/utf8"},
                              target="https:localhost", cost_usd=0.0, expected_outcome="page read",
                              evidence_refs=[], attempt=0, spent_usd=0.0, approved_scopes=set())
        assert out.status == "DONE", (out.status, out.reasons)
    finally:
        body.close()


def test_a_request_http_client_cannot_form_is_a_definite_refusal(tmp_path, tls_server):
    """A non-ASCII path fails in http.client before a byte is sent: a CapabilityError, not an
    UnicodeEncodeError that the authority office would record as an unknown outcome."""
    with pytest.raises(CapabilityError, match="cannot be formed"):
        http_get({"url": f"https://localhost:{tls_server}/café"}, _ctx(tmp_path))


def test_repair_matches_urllibs_own_redirect_handler():
    import string
    import urllib.parse
    for raw in ("/My Report", "/café", "/a%20b?q=1 2", "https://a.example", "/x\ty"):
        parts = urllib.parse.urlparse(raw)
        if not parts.path and parts.netloc:
            parts = parts._replace(path="/")
        expected = urllib.parse.quote(urllib.parse.urlunparse(parts), encoding="iso-8859-1",
                                      safe=string.punctuation)
        assert egress.repair_location(raw) == expected
    with pytest.raises(egress.EgressRefused, match="cannot be encoded"):
        egress.repair_location("/caf€")                 # outside ISO-8859-1: http.client never yields it


# -- credentials are scoped to an origin, not a host name ---------------------------

def test_a_credential_does_not_follow_a_same_host_redirect_to_another_port(monkeypatch):
    web = FakeWeb({"https://api.github.com/user": (302, "https://api.github.com:8443/collect", b""),
                   "https://api.github.com:8443/collect": (302, "https://api.github.com/after", b""),
                   "https://api.github.com/after": (200, None, b"{}")}).install(monkeypatch)
    request = urllib.request.Request("https://api.github.com/user",
                                     headers={"Authorization": "Bearer ghp_secret", "Cookie": "s=1"})
    with egress.open_checked(request, allowlist=("api.github.com",), timeout=5) as response:
        response.read()
    sent = [(r["url"], r["headers"].get("authorization"), r["headers"].get("cookie")) for r in web.seen]
    assert sent == [("https://api.github.com/user", "Bearer ghp_secret", "s=1"),
                    ("https://api.github.com:8443/collect", None, None),
                    ("https://api.github.com/after", None, None)]          # dropped, never restored


def test_an_explicit_default_port_is_the_same_origin(monkeypatch):
    web = FakeWeb({"https://a.example/x": (302, "https://a.example:443/y", b""),
                   "https://a.example:443/y": (200, None, b"ok")}).install(monkeypatch)
    request = urllib.request.Request("https://a.example/x", headers={"Authorization": "Bearer t"})
    with egress.open_checked(request, allowlist=("a.example",), timeout=5) as response:
        assert response.read() == b"ok"
    assert [r["headers"].get("authorization") for r in web.seen] == ["Bearer t", "Bearer t"]
    assert egress.origin("https://a.example:443/y") == egress.origin("https://A.example/z") \
        == ("https", "a.example", 443)
    assert egress.origin("https://a.example:0/") != egress.origin("https://a.example/")


# -- the http.get manifest declares what http_get returns ------------------------------

def test_http_get_manifest_declares_every_output_it_returns(tmp_path, monkeypatch):
    FakeWeb({"https://example.com/a": (200, None, b"page")}).install(monkeypatch)
    secrets = SecretBroker(tmp_path / "s.json")
    manifest = BUILTINS["http.get"][0]
    out = http_get({"url": "https://example.com/a"},
                   InvocationContext(workspace=tmp_path / "ws", read_roots=(tmp_path,), secrets=secrets,
                                     manifest=manifest))
    assert set(out) == set(manifest.outputs) and manifest.outputs["final_url"] == "str"


# -- the OCI registry client goes through the same opener --------------------------------

BLOB = "https://mirror.gcr.io/v2/library/python/blobs/sha256:" + "0" * 64
CHALLENGE = 'Bearer realm="https://mirror.gcr.io/token",service="x",scope="y"'


class _Registry(FakeWeb):
    """FakeWeb with response headers: a 401 challenge, and a redirect only for the authenticated retry."""

    def __init__(self, routes, *, challenge=CHALLENGE, retry_location=None):
        super().__init__(routes)
        self.challenge, self.retry_location = challenge, retry_location

    def _open(self, handler, request):
        import email.message
        import io
        import urllib.response
        if request.full_url == BLOB:
            headers = {name.lower(): value for name, value in request.header_items()}
            self.seen.append({"url": request.full_url, "method": request.get_method(), "headers": headers})
            message = email.message.Message()
            if "authorization" not in headers:
                status = 401
                message["WWW-Authenticate"] = self.challenge
            elif self.retry_location:
                status = 307
                message["Location"] = self.retry_location
            else:
                status = 200
            response = urllib.response.addinfourl(io.BytesIO(b"blob-bytes" if status == 200 else b""),
                                                  message, request.full_url, status)
            response.msg = "fake"
            return response
        return super()._open(handler, request)


def test_the_registry_token_never_leaves_the_registry_for_a_redirect_host(monkeypatch):
    """0c4849b: urllib's default handler sent 'Authorization: Bearer registry-token-123' to the collector."""
    from foundry.systems import containers
    web = _Registry({"https://mirror.gcr.io/token?service=x&scope=y": (200, None, {"token": "registry-token-123"}),
                     "https://collector.attacker.example/blob": (200, None, b"blob-bytes")},
                    retry_location="https://collector.attacker.example/blob").install(monkeypatch)
    with pytest.raises(egress.EgressRefused, match="not in allowlist"):
        containers._fetch(BLOB)
    assert "collector.attacker.example" not in web.hosts()


def test_a_blob_redirected_to_its_cdn_is_read_without_the_token(monkeypatch):
    from foundry.systems import containers
    cdn = "https://production.cloudfront.docker.com/registry-v2/blob"
    web = _Registry({"https://mirror.gcr.io/token?service=x&scope=y": (200, None, {"token": "registry-token-123"}),
                     cdn: (200, None, b"blob-bytes")}, retry_location=cdn).install(monkeypatch)
    assert containers._fetch(BLOB) == b"blob-bytes"
    assert [r["headers"].get("authorization") for r in web.received("production.cloudfront.docker.com")] == [None]
    assert [r["headers"].get("authorization") for r in web.received("mirror.gcr.io")] == \
        [None, None, "Bearer registry-token-123"]                 # challenge, token, authenticated retry


@pytest.mark.parametrize("realm", ["http://mirror.gcr.io/token", "https://collector.attacker.example/token",
                                   "https://user:pw@mirror.gcr.io/token", "file:///etc/passwd"])
def test_a_token_realm_named_by_a_response_is_checked_before_it_is_opened(monkeypatch, realm):
    from foundry.systems import containers
    web = _Registry({}, challenge=f'Bearer realm="{realm}",service="x",scope="y"').install(monkeypatch)
    with pytest.raises(egress.EgressRefused):
        containers._fetch(BLOB)
    assert web.hosts() == ["mirror.gcr.io"]                         # only the challenged request was sent


def test_a_refused_mirror_falls_through_to_the_next_one(tmp_path, monkeypatch):
    import hashlib
    from foundry.systems import containers
    data = b"layer"
    digest = "sha256:" + hashlib.sha256(data).hexdigest()
    first, second = (f"{registry}/v2/{repo}/blobs/{digest}" for registry, repo in containers.MIRRORS[:2])
    web = FakeWeb({first: (302, "https://elsewhere.example/layer", b""), second: (200, None, data)})
    web.install(monkeypatch)
    assert containers.fetch_blob(digest, store=tmp_path / "cas") == data
    assert "elsewhere.example" not in web.hosts()
