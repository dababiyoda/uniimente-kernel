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


def main(argv: list[str]) -> int:
    from foundry.systems.mcp_gateway import _call, list_tools, root_cause
    op, url = argv[0], argv[1]
    provider = {"name": urlsplit(url).hostname or "remote", "url": url,
                "bearer": os.environ.pop("GREG_MCP_BEARER", ""), "cafile": os.environ.get("GREG_EGRESS_CAFILE")}
    try:
        if op == "list":
            out = list_tools(provider)
        elif op == "call" and len(argv) == 3:
            out = asyncio.run(_call(provider, argv[2], json.loads(sys.stdin.read() or "{}")))
        else:
            raise ValueError("usage: list|call <url> [tool]")
    except Exception as exc:          # one line the caller can show; the token is not in the environment any more
        cause = root_cause(exc)
        print(json.dumps({"error": " ".join(f"{type(cause).__name__}: {cause}".split())[:600]}))
        return 1
    print(json.dumps({"ok": out}, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
