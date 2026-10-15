"""``mcp.call``: one tool on a founder-installed MCP server, read-only because the operating system makes it so.

The Model Context Protocol has become the common way tools are offered to models: filesystems, git, databases,
calendars, search, domain calculators. Rather than rebuild each one, GREG uses the server the founder installs.

The founder installs a stdio MCP server (any language) into a directory inside the body's read roots, and signs a
mission naming that directory, the command that starts the server, the tool, its arguments, and any further paths
the server may read. GREG starts the server in the door namespace (``relay_door.namespace_argv``) with no network
at all:

  - the founder's home, the body's home and GREG's ``.git`` are hidden;
  - the filesystem is read-only except a private scratch directory that is discarded;
  - only the server's own installation and the paths the mission names are shown.

So the call is read-only by construction, whatever the server does. A tool that writes, deletes or sends finds
nothing writable and no network. The server's own claim about its tools (``readOnlyHint``) is recorded as a claim
and never used. Its answer is untrusted external data, and the mission's predicate decides what it means.

Limits, stated: bubblewrap namespaces are required (refused without them); namespaces share the kernel, so this is
not gVisor-class isolation of arbitrary code (Foundry #10). A server that needs the network is refused here; that
needs signed hosts behind the relay, which is not built.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile

from greg.capabilities import CapabilityError, InvocationContext, _inside

NAME = re.compile(r"[a-z0-9][a-z0-9._-]{0,60}")
TOOL = re.compile(r"[A-Za-z0-9_.-]{1,64}")
MAX_RESULT_BYTES = 256 * 1024


def _command(params: dict, root: Path) -> list[str]:
    command = params.get("command")
    if not isinstance(command, list) or not command or not all(isinstance(a, str) for a in command):
        raise CapabilityError("command must be a non-empty list of strings")
    executable = Path(command[0])
    if not executable.is_absolute():
        raise CapabilityError("the server's executable must be an absolute path inside its installation directory")
    try:
        executable.resolve().relative_to(root)
    except ValueError:
        raise CapabilityError(f"{command[0]} is outside the server's installation directory {root}") from None
    return command


def call(params: dict, ctx: InvocationContext) -> dict:
    from foundry.systems.mcp_gateway import GatewayError, _call, root_cause
    from greg.worker_isolation import WorkerIsolationError, _backend
    server, tool = params.get("server", ""), params.get("tool", "")
    if not NAME.fullmatch(str(server)) or not TOOL.fullmatch(str(tool)):
        raise CapabilityError("server must be a lowercase name and tool a plain identifier")
    if ctx.target != f"mcp:{server}":
        raise CapabilityError(f"the signed target {ctx.target!r} does not name server {server!r}")
    root = _inside(Path(params["root"]), ctx.read_roots)
    command = _command(params, root)
    readable = [str(_inside(Path(p), ctx.read_roots)) for p in params.get("readable") or []]
    arguments = params.get("arguments") or {}
    if not isinstance(arguments, dict):
        raise CapabilityError("arguments must be an object")
    try:
        _backend(require_bubblewrap=True)
    except WorkerIsolationError as exc:
        raise CapabilityError(f"an MCP server runs only in a bubblewrap namespace, unavailable here: {exc}") from None
    ctx.workspace.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix=f"mcp-{server}-", dir=ctx.workspace))
    provider = {"name": server, "command": command, "root": str(root), "readable": readable, "scratch": str(scratch)}
    try:
        out = asyncio.run(_call(provider, tool, arguments))
    except Exception as exc:              # a refusal, a crash, a protocol break: say what actually failed
        cause = root_cause(exc)
        log = scratch / "server-stderr.log"
        tail = log.read_text(errors="replace")[-300:].strip() if log.exists() else ""
        what = " ".join((str(cause) if isinstance(cause, GatewayError) else f"{type(cause).__name__}: {cause}").split())
        tail = " ".join(tail.split())[-200:]
        raise CapabilityError(f"MCP server {server}: {what}"[:700] + (f" | stderr: {tail}" if tail else "")) from None
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    value = out["value"]
    text = value if isinstance(value, str) else json.dumps(value, sort_keys=True, default=str)
    if len(text.encode()) > MAX_RESULT_BYTES:
        raise CapabilityError("the server's answer exceeds the read ceiling")
    return {"server": server, "tool": tool, "result": value, "text": text,
            "result_sha256": "sha256:" + hashlib.sha256(text.encode()).hexdigest(),
            "trust": "untrusted-external-data", "server_claims_read_only": out["provider_claims_read_only"],
            "confinement": {"network": "none", "filesystem": "read-only except a discarded scratch directory",
                            "shown": [str(root), *readable]}}
