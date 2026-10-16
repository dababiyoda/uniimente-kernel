"""GREG's client for one remote (Streamable HTTP) MCP server, run inside the door namespace.

``python -m greg.mcp_remote list|call <url> [tool]``: the arguments arrive as JSON on stdin, the answer leaves as
JSON on stdout. The process sees no founder home, no body home, no ``.git``, and has no network of its own: its
only way out is the door to a relay that allows exactly the server's host on 443 (``greg/mcp_tools.py`` builds
both). The bearer token arrives by environment from a credential handle, never in argv, and is removed from
``os.environ`` before anything else runs, so libraries and child processes do not see it.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from urllib.parse import urlsplit


def renew(login: dict, url: str, cafile: str | None) -> dict:
    """One refresh of an expired OAuth login (RFC 6749 section 6), at the token endpoint recorded when the founder
    logged in, through the same door. Returns the new token response."""
    import ssl
    import httpx2
    form = {"grant_type": "refresh_token", "refresh_token": login["refresh_token"], "client_id": login["client_id"],
            "resource": url}                                   # RFC 8707: the token is for this server
    auth = (login["client_id"], login["client_secret"]) if login.get("client_secret") else None
    if auth:
        form.pop("client_id")
    verify = ssl.create_default_context(cafile=cafile) if cafile else True
    with httpx2.Client(verify=verify, trust_env=True, timeout=30.0) as http:
        reply = http.post(login["token_endpoint"], data=form, auth=auth, headers={"Accept": "application/json"})
    if reply.status_code != 200:
        raise PermissionError(f"renewing the login failed with HTTP {reply.status_code}; the founder can run "
                              "greg mcp login again")
    tokens = reply.json()
    if not isinstance(tokens, dict) or not tokens.get("access_token"):
        raise PermissionError("the token endpoint answered without an access token")
    return tokens


def main(argv: list[str]) -> int:
    from foundry.systems.mcp_gateway import _call, list_tools, root_cause
    op, url = argv[0], argv[1]
    cafile = os.environ.get("GREG_EGRESS_CAFILE")
    provider = {"name": urlsplit(url).hostname or "remote", "url": url,
                "bearer": os.environ.pop("GREG_MCP_BEARER", ""), "cafile": cafile}
    pending = os.environ.pop("GREG_MCP_RENEW", "")
    renewed = None
    try:
        if pending:
            renewed = renew(json.loads(pending), url, cafile)
            provider["bearer"] = renewed["access_token"]
        if op == "list":
            out = list_tools(provider)
        elif op == "call" and len(argv) == 3:
            out = asyncio.run(_call(provider, argv[2], json.loads(sys.stdin.read() or "{}")))
        else:
            raise ValueError("usage: list|call <url> [tool]")
    except Exception as exc:          # one line the caller can show; the token is not in the environment any more
        cause = root_cause(exc)
        print(json.dumps({"error": " ".join(f"{type(cause).__name__}: {cause}".split())[:600],
                          **({"renewed": renewed} if renewed else {})}))       # a renewal is kept even if the call failed
        return 1
    print(json.dumps({"ok": out, **({"renewed": renewed} if renewed else {})}, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
