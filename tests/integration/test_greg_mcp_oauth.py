"""OAuth for a remote MCP server: the founder logs GREG in once; approved calls use the login; an expired login
renews inside the approved call, through the relay, and the tokens stay in the secret broker.

The hosted "notes" service is the official SDK's ``MCPServer`` with an OAuth authorization server (an in-memory
provider that approves at once, standing in for the founder's sign-in) on ``https://service.test``. ``greg mcp
login``'s flow is the SDK's own client: metadata discovery, dynamic client registration, PKCE, code exchange. The
founder's browser is simulated by following the authorization redirect to GREG's loopback page.

Loopback only, behind the fake CONNECT proxy; nothing leaves the machine.
"""
from __future__ import annotations

import asyncio
from dataclasses import replace
import json
from pathlib import Path
import secrets
import socket
import threading
import time

import pytest

from greg import mcp_login
from greg.body import Body
from greg.capabilities import BUILTINS, SecretBroker
from tests.greg_fixtures import drop, signed
from tests.integration.test_greg_confined_egress import body_with_confined_egress, certificate, fake_proxy
from tests.integration.test_greg_mcp_remote_mission import remote_mission, tick_until
from tests.unit.test_greg_mcp_planner import needs_namespaces

pytest.importorskip("uvicorn")


class Provider:
    """An OAuth authorization server that approves every request at once (the founder's sign-in, simulated)."""

    def __init__(self):
        self.clients, self.codes, self.access, self.refresh, self.refreshed = {}, {}, {}, {}, 0

    async def get_client(self, client_id):
        return self.clients.get(client_id)

    async def register_client(self, client_info):
        self.clients[client_info.client_id] = client_info

    async def authorize(self, client, params):
        from mcp.server.auth.provider import AuthorizationCode, construct_redirect_uri
        code = "code-" + secrets.token_urlsafe(12)
        self.codes[code] = AuthorizationCode(
            code=code, scopes=params.scopes or ["notes"], expires_at=time.time() + 300, client_id=client.client_id,
            code_challenge=params.code_challenge, redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly, resource=params.resource)
        return construct_redirect_uri(str(params.redirect_uri), code=code, state=params.state)

    async def load_authorization_code(self, client, authorization_code):
        return self.codes.get(authorization_code)

    def _issue(self, client_id, scopes, resource):
        from mcp.server.auth.provider import AccessToken, RefreshToken
        from mcp.shared.auth import OAuthToken
        access, refresh = "at-" + secrets.token_urlsafe(16), "rt-" + secrets.token_urlsafe(16)
        self.access[access] = AccessToken(token=access, client_id=client_id, scopes=scopes,
                                          expires_at=int(time.time()) + 3600, resource=resource)
        self.refresh[refresh] = RefreshToken(token=refresh, client_id=client_id, scopes=scopes, resource=resource)
        return OAuthToken(access_token=access, token_type="Bearer", expires_in=3600, refresh_token=refresh,
                          scope=" ".join(scopes))

    async def exchange_authorization_code(self, client, authorization_code):
        self.codes.pop(authorization_code.code, None)
        return self._issue(client.client_id, authorization_code.scopes, authorization_code.resource)

    async def load_refresh_token(self, client, refresh_token):
        return self.refresh.get(refresh_token)

    async def exchange_refresh_token(self, client, refresh_token, scopes):
        self.refresh.pop(refresh_token.token, None)
        self.refreshed += 1
        return self._issue(client.client_id, scopes or refresh_token.scopes, refresh_token.resource)

    async def load_access_token(self, token):
        return self.access.get(token)

    async def revoke_token(self, token):
        self.access.pop(getattr(token, "token", ""), None)


def oauth_service(cert, key, provider):
    import uvicorn
    from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
    from mcp.server.mcpserver import MCPServer
    from mcp.server.transport_security import TransportSecuritySettings
    notes, seen = [], []
    server = MCPServer("notes", auth_server_provider=provider, auth=AuthSettings(
        issuer_url="https://service.test", resource_server_url="https://service.test/mcp", required_scopes=["notes"],
        validate_token_resource=True,                   # a token is accepted only for this server (RFC 8707)
        client_registration_options=ClientRegistrationOptions(enabled=True, valid_scopes=["notes"],
                                                              default_scopes=["notes"])))

    @server.tool()
    def add_note(text: str) -> str:
        """Add a note to the shared notes."""
        notes.append(text)
        return f"{len(notes)} notes"

    app = server.streamable_http_app(transport_security=TransportSecuritySettings(
        allowed_hosts=["service.test", "service.test:443"], allowed_origins=["https://service.test"]))

    async def listing(request):                         # what GREG's own check reads (no token needed)
        from starlette.responses import JSONResponse
        return JSONResponse(notes)
    app.add_route("/notes", listing)

    async def recording(scope, receive, send):
        if scope["type"] == "http":
            seen.append((scope["path"], dict(scope["headers"]).get(b"authorization", b"").decode()))
        await app(scope, receive, send)
    sock = socket.create_server(("127.0.0.1", 0))
    service = uvicorn.Server(uvicorn.Config(recording, ssl_certfile=str(cert), ssl_keyfile=str(key),
                                            log_level="error", lifespan="on"))
    threading.Thread(target=service.run, kwargs={"sockets": [sock]}, daemon=True).start()
    for _ in range(100):
        if service.started:
            break
        time.sleep(0.05)
    return service, sock.getsockname()[1], notes, seen


@pytest.fixture
def hosted(tmp_path, monkeypatch):
    cert, key = certificate(tmp_path)
    provider = Provider()
    service, port, notes, seen = oauth_service(cert, key, provider)
    proxy, heads = fake_proxy(port)
    for name in ("HTTPS_PROXY", "https_proxy"):            # the founder's terminal: whichever spelling it has
        monkeypatch.setenv(name, f"http://fixture-user:fixture-secret@127.0.0.1:{proxy.getsockname()[1]}")
    monkeypatch.setenv("GREG_EGRESS_CAFILE", str(cert))
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    manifest, adapter = BUILTINS["http.get"]
    monkeypatch.setitem(BUILTINS, "http.get", (replace(manifest, egress_allowlist=("service.test",)), adapter))
    yield {"provider": provider, "notes": notes, "seen": seen, "cert": cert}
    service.should_exit = True
    proxy.close()


def browser(cert):
    """The founder's browser: open the link, sign in (the provider approves at once), follow the redirect home."""
    import ssl
    import httpx2

    def open_url(link):
        with httpx2.Client(verify=ssl.create_default_context(cafile=str(cert)), trust_env=True) as http:
            redirect = http.get(link)
            assert redirect.status_code in (302, 303, 307), redirect.status_code
            location = redirect.headers["location"]
            assert location.startswith("http://127.0.0.1:"), location        # only GREG's own loopback page
        with httpx2.Client(trust_env=False) as local:
            assert "GREG received your authorization" in local.get(location).text
    return open_url


@needs_namespaces
def test_the_founder_logs_greg_in_and_an_approved_call_uses_and_renews_the_login(tmp_path, hosted):
    home, key, body_id = body_with_confined_egress(tmp_path)
    broker = SecretBroker(home / "secrets.json")
    out = asyncio.run(mcp_login.login("notes", "https://service.test/mcp", broker, open_url=browser(hosted["cert"]),
                                      cafile=str(hosted["cert"])))
    assert out["handle"] == "mcp:notes" and out["renews_at"] == "service.test" and out["tools_offered"] == 1
    login = mcp_login.record(broker, "mcp:notes")
    first = login["tokens"]["access_token"]
    assert first in hosted["provider"].access and "access_token" not in json.dumps(out)

    drop(home, signed(key, body_id, "MISSION", remote_mission("m:oauth-note", bearer="mcp:notes")))
    with Body(home) as body:
        body.boot()
        tick_until(body, "WAITING")
        [ask] = [e.payload for e in body.journal.replay("decision.requested")]
    assert ask["authority_requested"]["credentials"] == ["mcp:notes"] and first not in json.dumps(ask)
    drop(home, signed(key, body_id, "DECISION", {"request_id": ask["request_id"], "answer": "approve"}))
    with Body(home) as body:
        body.boot()
        out = tick_until(body, "ACHIEVED")
        assert out["state"] == "ACHIEVED", out
    assert hosted["notes"] == ["ship the wedge"] and ("/mcp", f"Bearer {first}") in hosted["seen"]
    assert hosted["provider"].refreshed == 0                         # a valid login is used as it is

    # The access token expires; the service forgets it. An approved call renews it once, inside the call.
    stale = {**login, "expires_at": time.time() - 30}
    broker.put("mcp:notes", json.dumps(stale))
    hosted["provider"].access.clear()
    drop(home, signed(key, body_id, "MISSION", remote_mission("m:oauth-renewed", text="renewed", bearer="mcp:notes")))
    with Body(home) as body:
        body.boot()
        tick_until(body, "WAITING")
        [ask] = [e.payload for e in body.journal.replay("decision.requested") if e.payload["mission_id"] == "m:oauth-renewed"]
    drop(home, signed(key, body_id, "DECISION", {"request_id": ask["request_id"], "answer": "approve"}))
    with Body(home) as body:
        body.boot()
        out = tick_until(body, "ACHIEVED")
        receipts = [r.payload["result"].get("output") for r in body.ledger.by_type("receipt")]
        chain_ok, _ = body.ledger.verify_chain()
    assert out["state"] == "ACHIEVED" and chain_ok, out
    assert hosted["notes"] == ["ship the wedge", "renewed"] and hosted["provider"].refreshed == 1
    renewed = mcp_login.record(broker, "mcp:notes")
    assert renewed["tokens"]["access_token"] != first and not mcp_login.expired(renewed)
    assert renewed["tokens"]["refresh_token"] != login["tokens"]["refresh_token"]       # rotated and kept
    [acted] = [r for r in receipts if isinstance(r, dict) and r.get("result") == "2 notes"]
    assert acted["confinement"]["login_renewed"] is True and "renewed" not in acted
    tokens = {first, login["tokens"]["refresh_token"], renewed["tokens"]["access_token"],
              renewed["tokens"]["refresh_token"]}
    leaked = [p for p in home.rglob("*") if p.is_file() and p.name != "secrets.json"
              and any(t.encode() in p.read_bytes() for t in tokens)]
    assert not leaked, leaked                       # neither token is in the ledger, the journals or the workspace
