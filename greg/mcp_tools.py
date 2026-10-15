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


SKIP_DIRS = {".git", "node_modules", "__pycache__", ".cache", "lib", "lib64", "include", "share", "site-packages"}


def _launch(directory: Path) -> dict:
    """What the founder wrote in ``greg-mcp.json`` beside a server: arguments its command needs (the filesystem server
    takes the directories it may serve) and the paths it may read. Optional; every path is still checked against the
    read roots when a mission runs, and the founder signs the mission that carries them."""
    config = directory / "greg-mcp.json"
    if not config.is_file():
        return {}
    try:
        value = json.loads(config.read_text())
    except (OSError, ValueError):
        return {"config_error": f"{config.name} is not valid JSON"}
    args, readable = value.get("args", []), value.get("readable", [])
    if not (isinstance(args, list) and isinstance(readable, list) and all(isinstance(a, str) for a in args + readable)):
        return {"config_error": f"{config.name}: args and readable must be lists of strings"}
    return {"args": args, "readable": readable}


def installed_servers(read_roots, *, max_depth: int = 4) -> dict:
    """The MCP servers the founder installed under the body's read roots: ``name -> {"root", "command"}``.

    A server is an installation directory whose ``bin`` holds an executable named ``mcp-server-<name>`` (what
    ``python -m venv <dir> && <dir>/bin/pip install mcp-server-<name>`` produces), or whose ``node_modules/.bin`` does
    (what ``npm install --prefix <dir> @modelcontextprotocol/server-<name>`` produces). Nothing is started: this only
    reads the directory tree, a few levels deep, skipping library and cache trees."""
    found: dict = {}
    for read_root in read_roots:
        base = Path(read_root).expanduser()
        if not base.is_dir():
            continue
        stack = [(base, 0)]
        while stack:
            directory, depth = stack.pop()
            try:
                entries = sorted(directory.iterdir())
            except OSError:
                continue
            for entry in entries:
                bins = (entry if entry.name == "bin" and entry.is_dir() else
                        entry / ".bin" if entry.name == "node_modules" and (entry / ".bin").is_dir() else None)
                if bins is not None:
                    for executable in sorted(bins.glob("mcp-server-*")):
                        name = executable.name[len("mcp-server-"):].lower()
                        if (NAME.fullmatch(name) and executable.is_file() and name not in found
                                and executable.stat().st_mode & 0o111):
                            found[name] = {"root": str(directory.resolve()), "command": [str(executable)],
                                           **_launch(directory)}
                elif (entry.is_dir() and not entry.is_symlink() and depth < max_depth
                      and entry.name not in SKIP_DIRS and not entry.name.startswith(".")):
                    stack.append((entry, depth + 1))
    return dict(sorted(found.items()))


def server_tools(server: dict, *, scratch_parent: Path) -> list[dict]:
    """The tools one installed server offers, each with its input schema and its own read-only claim. The server runs
    exactly as ``mcp.call`` runs it: confined, no network, read-only, discarded scratch. Read-only discovery."""
    from foundry.systems.mcp_gateway import list_tools
    from greg.worker_isolation import WorkerIsolationError, _backend
    try:
        _backend(require_bubblewrap=True)
    except WorkerIsolationError as exc:
        raise CapabilityError(f"an MCP server runs only in a bubblewrap namespace, unavailable here: {exc}") from None
    Path(scratch_parent).mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="mcp-list-", dir=scratch_parent))
    try:
        return list_tools({"name": Path(server["command"][0]).name,
                           "command": [*server["command"], *server.get("args", [])], "root": server["root"],
                           "readable": server.get("readable", []), "scratch": str(scratch)})
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


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
