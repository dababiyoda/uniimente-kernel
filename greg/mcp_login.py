"""``greg mcp login``: the founder authorizes GREG at a remote MCP server (OAuth 2.1, the SDK's own client).

The founder runs it in a terminal, as with ``greg secret set``. GREG prints the authorization link; the founder
opens it, signs in at the service and approves; the service redirects to a one-shot page on 127.0.0.1 that this
command serves; the tokens go into the body's secret broker under ``mcp:<name>``. The flow itself (metadata
discovery, dynamic client registration, PKCE, code exchange) is the official MCP SDK's ``OAuthClientProvider``. GREG
adds only the storage, the loopback page and a record of where the token may be renewed.

Using the login is a separate decision: an ``mcp.act`` naming the handle as ``bearer`` runs only after the founder
approves that call. When the access token has expired, GREG's confined client renews it once at the token endpoint
recorded here (RFC 6749 section 6), and only if that host is the server's own or is named in the approved hosts.
"""
from __future__ import annotations

import asyncio
import json
import time
from urllib.parse import parse_qs, urlsplit

from greg.capabilities import CapabilityError

KIND = "oauth-login/1"


def record(broker, handle: str) -> dict | None:
    """The stored login for ``handle``, or None when the handle holds a plain bearer token (or nothing)."""
    try:
        value = broker.resolve(handle, declared=(handle,))
    except CapabilityError:
        return None
    try:
        parsed = json.loads(value)
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) and parsed.get("kind") == KIND else None


def public(login: dict) -> dict:
    """What may be shown: never a token or a client secret."""
    return {"server": login["server"], "renews_at": urlsplit(login["token_endpoint"]).hostname,
            "scope": login.get("scope"), "expires_at": login.get("expires_at")}


def expired(login: dict, *, now: float | None = None, margin: float = 60.0) -> bool:
    at = login.get("expires_at")
    return at is not None and (now if now is not None else time.time()) + margin >= float(at)


def store_renewal(broker, handle: str, login: dict, tokens: dict) -> None:
    """Keep a renewed token response (rotating the refresh token when the service sent a new one)."""
    fresh = {**login["tokens"], **{k: v for k, v in tokens.items() if v is not None}}
    expires_in = tokens.get("expires_in")
    broker.put(handle, json.dumps({**login, "tokens": fresh, "scope": tokens.get("scope", login.get("scope")),
                                   "expires_at": time.time() + float(expires_in) if expires_in else None}))


class _Storage:
    """The SDK's TokenStorage, kept in one JSON record that is written to the broker once the flow succeeds."""

    def __init__(self, server: str):
        self.data = {"kind": KIND, "server": server}

    async def get_tokens(self):
        from mcp.shared.auth import OAuthToken
        return OAuthToken(**self.data["tokens"]) if "tokens" in self.data else None

    async def set_tokens(self, tokens) -> None:
        self.data["tokens"] = tokens.model_dump(mode="json", exclude_none=True)
        self.data["scope"] = tokens.scope
        self.data["expires_at"] = time.time() + tokens.expires_in if tokens.expires_in else None

    async def get_client_info(self):
        from mcp.shared.auth import OAuthClientInformationFull
        return OAuthClientInformationFull(**self.data["client"]) if "client" in self.data else None

    async def set_client_info(self, client_info) -> None:
        self.data["client"] = client_info.model_dump(mode="json", exclude_none=True)


async def _callback_server():
    """A one-shot page on 127.0.0.1 receiving the authorization redirect: (redirect_uri, waiter, server)."""
    from mcp.shared.auth import AuthorizationCodeResult
    got: asyncio.Future = asyncio.get_running_loop().create_future()

    async def handle(reader, writer):
        line = (await reader.readline()).decode("latin-1").split()
        while (await reader.readline()) not in (b"\r\n", b"\n", b""):
            pass
        target = line[1] if len(line) > 1 else ""
        query = parse_qs(urlsplit(target).query)
        ok = urlsplit(target).path == "/callback" and "code" in query and not got.done()
        body = (b"GREG received your authorization. You can close this page." if ok
                else b"This page only receives one authorization for GREG.")
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nConnection: close\r\nContent-Length: "
                     + str(len(body)).encode() + b"\r\n\r\n" + body)
        await writer.drain()
        writer.close()
        if ok:
            got.set_result(AuthorizationCodeResult(code=query["code"][0], state=(query.get("state") or [None])[0],
                                                   iss=(query.get("iss") or [None])[0]))
    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    return f"http://127.0.0.1:{port}/callback", got, server


async def login(name: str, url: str, broker, *, open_url, cafile: str | None = None, timeout: float = 300.0) -> dict:
    """Run the SDK's OAuth flow against ``url`` and store the result under ``mcp:<name>``. ``open_url`` shows the
    founder the authorization link (the CLI prints it). Returns the public record."""
    import ssl
    import httpx2
    from mcp import Client
    from mcp.client.auth import OAuthClientProvider
    from mcp.client.streamable_http import streamable_http_client
    from mcp.shared.auth import OAuthClientMetadata
    from greg.mcp_tools import HANDLE, remote_url
    handle = f"mcp:{name}"
    if not HANDLE.fullmatch(handle):
        raise CapabilityError("the login's name is a lowercase name (it becomes the handle mcp:<name>)")
    remote_url(url)
    redirect_uri, got, server = await _callback_server()
    storage = _Storage(url)

    async def redirect(authorization_url: str) -> None:
        await asyncio.to_thread(open_url, authorization_url)

    async def callback():
        return await asyncio.wait_for(got, timeout)
    provider = OAuthClientProvider(
        server_url=url, storage=storage, redirect_handler=redirect, callback_handler=callback,
        client_metadata=OAuthClientMetadata(client_name="GREG", redirect_uris=[redirect_uri],
                                            grant_types=["authorization_code", "refresh_token"],
                                            response_types=["code"], token_endpoint_auth_method="none"))
    verify = ssl.create_default_context(cafile=cafile) if cafile else True
    try:
        async with httpx2.AsyncClient(auth=provider, verify=verify, trust_env=True,
                                      timeout=httpx2.Timeout(30.0, read=60.0)) as http:
            async with Client(streamable_http_client(url, http_client=http), read_timeout_seconds=60) as client:
                tools = len((await client.list_tools()).tools)
    finally:
        server.close()
    if "tokens" not in storage.data:
        raise CapabilityError("the service returned no token; nothing was stored")
    metadata = provider.context.oauth_metadata
    endpoint = str(metadata.token_endpoint) if metadata and metadata.token_endpoint else \
        f"{urlsplit(url).scheme}://{urlsplit(url).netloc}/token"
    try:
        remote_url(endpoint)              # renewal crosses the relay on 443 only: an endpoint elsewhere is refused now
    except CapabilityError:
        raise CapabilityError(f"the service's token endpoint {endpoint} is not https on 443; nothing was stored") from None
    storage.data["token_endpoint"] = endpoint
    broker.put(handle, json.dumps(storage.data))
    return {**public(storage.data), "handle": handle, "tools_offered": tools}
