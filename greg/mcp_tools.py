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

``mcp.act`` is the same call for a tool that changes something: the founder approves its exact scope (the paths it
may write, the hosts it may reach through the body's relay, the credential handles it receives) before it runs.

Limits, stated: bubblewrap namespaces are required (refused without them); namespaces share the kernel, so this is
not gVisor-class isolation of arbitrary code (Foundry #10). Credentials reach a server as environment variables only,
and remote (HTTP) transport is not built.
"""
from __future__ import annotations

import asyncio
import contextlib
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


HOST = re.compile(r"[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+")
ENV_NAME = re.compile(r"[A-Z_][A-Z0-9_]{0,63}")
HANDLE = re.compile(r"mcp:[a-z0-9][a-z0-9._-]{0,60}")     # the founder's own credential handles for MCP servers


def _common(params: dict, ctx: InvocationContext) -> dict:
    """What every MCP invocation checks: the signed target names the server; the installation, its command and every
    named path are inside the read roots; the arguments are an object; namespaces exist (else nothing starts)."""
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
    return {"server": server, "tool": tool, "root": root, "command": command, "readable": readable,
            "arguments": arguments}


def _invoke(c: dict, ctx: InvocationContext, *, writable=(), hosts=(), env=None) -> dict:
    """Start the server confined (behind a door to a relay allowing exactly ``hosts`` when there are any), call the
    tool once, discard the scratch directory, and report the answer as untrusted data."""
    from foundry.systems.mcp_gateway import GatewayError, _call, root_cause
    ctx.workspace.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix=f"mcp-{c['server']}-", dir=ctx.workspace))
    provider = {"name": c["server"], "command": c["command"], "root": str(c["root"]), "readable": c["readable"],
                "writable": list(writable), "env": dict(env or {}), "scratch": str(scratch)}
    try:
        with contextlib.ExitStack() as stack:
            if hosts:
                from foundry.systems.relay_door import Door
                from foundry.systems.segmentation import Relay
                scoped = Relay({"mcp.act": {"allow": [[h, 443] for h in hosts], "external": True}},
                               ctx.egress.journal, connect=ctx.egress.connect, proxy=ctx.egress.proxy)
                # The SDK starts the server, so the door listens on a socket the namespace is shown read-only, in a
                # short private directory: a socket path in a deep workspace would exceed the 108-byte limit.
                sockets = Path(tempfile.mkdtemp(prefix="greg-door-"))
                stack.callback(shutil.rmtree, sockets, True)
                door = stack.enter_context(Door(scoped, "mcp.act", path=sockets / "door.sock"))
                provider["door"], provider["readable"] = door.control, [*provider["readable"], str(sockets)]
            out = asyncio.run(_call(provider, c["tool"], c["arguments"]))
    except Exception as exc:              # a refusal, a crash, a protocol break: say what actually failed
        cause = root_cause(exc)
        log = scratch / "server-stderr.log"
        tail = log.read_text(errors="replace")[-300:].strip() if log.exists() else ""
        what = " ".join((str(cause) if isinstance(cause, GatewayError) else f"{type(cause).__name__}: {cause}").split())
        tail = " ".join(tail.split())[-200:]
        raise CapabilityError(f"MCP server {c['server']}: {what}"[:700] + (f" | stderr: {tail}" if tail else "")) from None
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    value = out["value"]
    text = value if isinstance(value, str) else json.dumps(value, sort_keys=True, default=str)
    if len(text.encode()) > MAX_RESULT_BYTES:
        raise CapabilityError("the server's answer exceeds the read ceiling")
    return {"server": c["server"], "tool": c["tool"], "result": value, "text": text,
            "result_sha256": "sha256:" + hashlib.sha256(text.encode()).hexdigest(),
            "trust": "untrusted-external-data", "server_claims_read_only": out["provider_claims_read_only"]}


def call(params: dict, ctx: InvocationContext) -> dict:
    """``mcp.call``: read-only by construction (no network, nothing writable but a discarded scratch directory)."""
    if "url" in params:
        raise CapabilityError("a remote server's tools run on someone else's machine, so GREG cannot make a call "
                              "read-only; each call is an mcp.act the founder approves")
    c = _common(params, ctx)
    out = _invoke(c, ctx)
    out["confinement"] = {"network": "none", "filesystem": "read-only except a discarded scratch directory",
                          "shown": [str(c["root"]), *c["readable"]]}
    return out


def act(params: dict, ctx: InvocationContext) -> dict:
    """``mcp.act``: one tool that may change something, inside exactly what the founder signed for this use.

    - ``writable``: paths under the read roots the server may write (nothing else is writable);
    - ``hosts``: exact host names it may reach on port 443, through the body's relay (confined bodies only);
    - ``secrets``: environment variables for the server, each naming a credential handle in the ``mcp:`` namespace
      (``greg secret set mcp:<name>``); values reach the server's environment only, never the ledger.

    With ``url`` instead of an installation, the server is remote (Streamable HTTP): GREG's own client runs confined,
    reaching only that URL's host through the relay, with the token from ``bearer`` (an ``mcp:`` handle).

    The capability's class is ``external_contact``, so outside a signed standing mandate every use stops for the
    founder's decision on its exact scope, and an uncertain outcome is never retried blindly."""
    if "url" in params:
        return _remote_act(params, ctx)
    c = _common(params, ctx)
    writable = []
    for path in params.get("writable") or []:
        resolved = _inside(Path(path), ctx.read_roots)
        if not resolved.exists():
            raise CapabilityError(f"{resolved} does not exist; a mission names existing paths to write")
        writable.append(str(resolved))
    c["readable"] = [r for r in c["readable"] if r not in writable]     # a path named both ways is writable
    hosts = [str(h).lower() for h in params.get("hosts") or []]
    bad = [h for h in hosts if not HOST.fullmatch(h)]
    if bad:
        raise CapabilityError(f"hosts must be exact host names (no scheme, port or wildcard): {bad}")
    if hosts and ctx.egress is None:
        raise CapabilityError("a server that reaches the network runs only on a body with confined egress "
                              "(its connections cross the relay); this body has none")
    secrets = params.get("secrets") or {}
    if not isinstance(secrets, dict):
        raise CapabilityError("secrets must map environment names to credential handles")
    env = {}
    for name, handle in secrets.items():
        if not ENV_NAME.fullmatch(str(name)) or not HANDLE.fullmatch(str(handle)):
            raise CapabilityError("each secret maps an UPPER_CASE environment name to an mcp:<name> credential handle")
        env[name] = ctx.secrets.resolve(str(handle), declared=(str(handle),))
    if not writable and not hosts:
        raise CapabilityError("nothing to act on: name writable paths or hosts, or use mcp.call for a read-only call")
    out = _invoke(c, ctx, writable=writable, hosts=hosts, env=env)
    out["confinement"] = {"network": f"only {', '.join(hosts)} through the relay" if hosts else "none",
                          "writable": writable, "shown": [str(c["root"]), *c["readable"]],
                          "secrets": sorted(secrets)}
    return out


def remote_url(url) -> str:
    """The host of an https URL GREG may connect to: https only, no credentials, no port but 443."""
    from urllib.parse import urlsplit
    parts = urlsplit(str(url))
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or parts.username or parts.password or parts.port not in (None, 443) \
            or not HOST.fullmatch(host):
        raise CapabilityError("url must be https://<exact host>/<path>, without credentials or a port other than 443")
    return host


def _remote_act(params: dict, ctx: InvocationContext) -> dict:
    """``mcp.act`` against a remote server: one tool call from GREG's confined client, through the relay."""
    import os
    import subprocess
    import sys
    from foundry.systems.relay_door import ROOT, Door, door_argv, namespace_argv
    from foundry.systems.segmentation import Relay
    from greg.worker_isolation import WorkerIsolationError, _backend
    server, tool = params.get("server", ""), params.get("tool", "")
    if not NAME.fullmatch(str(server)) or not TOOL.fullmatch(str(tool)):
        raise CapabilityError("server must be a lowercase name and tool a plain identifier")
    if ctx.target != f"mcp:{server}":
        raise CapabilityError(f"the signed target {ctx.target!r} does not name server {server!r}")
    host = remote_url(params["url"])
    if [str(h).lower() for h in params.get("hosts") or [host]] != [host]:
        raise CapabilityError(f"a remote server reaches exactly its own host ({host})")
    if params.get("writable") or params.get("readable") or params.get("secrets"):
        raise CapabilityError("a remote server is given no local paths and no environment; its credential is bearer")
    arguments = params.get("arguments") or {}
    if not isinstance(arguments, dict):
        raise CapabilityError("arguments must be an object")
    bearer = params.get("bearer")
    if bearer is not None and not HANDLE.fullmatch(str(bearer)):
        raise CapabilityError("bearer names an mcp:<name> credential handle")
    if ctx.egress is None:
        raise CapabilityError("a remote server is reached only from a body with confined egress (its connections "
                              "cross the relay); this body has none")
    token = ctx.secrets.resolve(str(bearer), declared=(str(bearer),)) if bearer else ""
    try:
        _backend(require_bubblewrap=True)
    except WorkerIsolationError as exc:
        raise CapabilityError(f"GREG's MCP client runs only in a bubblewrap namespace, unavailable here: {exc}") from None
    ctx.workspace.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix=f"mcp-{server}-", dir=ctx.workspace))
    sockets = Path(tempfile.mkdtemp(prefix="greg-door-"))
    cafile = os.environ.get("GREG_EGRESS_CAFILE")
    scoped = Relay({"mcp.act": {"allow": [[host, 443]], "external": True}}, ctx.egress.journal,
                   connect=ctx.egress.connect, proxy=ctx.egress.proxy)
    try:
        with Door(scoped, "mcp.act", path=sockets / "door.sock") as door:
            (scratch / "home").mkdir()
            argv = namespace_argv(writable=[str(scratch)], readonly=[str(sockets), *([cafile] if cafile else [])],
                                  chdir=str(ROOT))
            argv += door_argv(sys.executable, door.control,
                              [sys.executable, "-m", "greg.mcp_remote", "call", str(params["url"]), tool])
            env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(scratch / "home"), "TMPDIR": str(scratch),
                   "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1", "GREG_MCP_BEARER": token,
                   **({"GREG_EGRESS_CAFILE": cafile} if cafile else {})}
            done = subprocess.run(argv, input=json.dumps(arguments), capture_output=True, text=True, env=env,
                                  timeout=180)
    except subprocess.TimeoutExpired:
        raise CapabilityError(f"MCP server {server}: no answer within 180 s") from None
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
        shutil.rmtree(sockets, ignore_errors=True)
    try:
        answer = json.loads(done.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        tail = " ".join(done.stderr.split())[-300:].replace(token, "[credential]") if token else done.stderr[-300:]
        raise CapabilityError(f"MCP server {server}: GREG's client failed (exit {done.returncode}): {tail}") from None
    if "error" in answer:
        raise CapabilityError(f"MCP server {server}: {answer['error']}"[:700])
    value = answer["ok"]["value"]
    text = value if isinstance(value, str) else json.dumps(value, sort_keys=True, default=str)
    if len(text.encode()) > MAX_RESULT_BYTES:
        raise CapabilityError("the server's answer exceeds the read ceiling")
    return {"server": server, "tool": tool, "result": value, "text": text,
            "result_sha256": "sha256:" + hashlib.sha256(text.encode()).hexdigest(),
            "trust": "untrusted-external-data", "server_claims_read_only": answer["ok"]["provider_claims_read_only"],
            "confinement": {"network": f"only {host} through the relay", "writable": [], "shown": [],
                            "secrets": [str(bearer)] if bearer else [], "remote": str(params["url"])}}
