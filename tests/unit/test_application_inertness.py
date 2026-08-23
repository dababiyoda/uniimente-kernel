"""The kill criterion for #31, enforced two ways.

FOUNDER-RULING-2026-08-22, ruling 5 (DEC-OM-004), named three non-negotiables:
structural/AST inertness enforcement, explicit gap text saying the
transport/listener half remains absent and founder-gated, and a kill criterion
that turns any unauthorized network primitive into a stop-the-line failure. All
three are asserted here.

**This is a stop-the-line test, not a lint.** If it fails, the correct response
is not to delete the offending line and carry on — its presence means the
boundary was not being maintained, and a founder decision governs whether the
transport half exists at all.

The failure mode it exists for is entirely ordinary: a contributor adds a
`serve()` helper "just for local testing", it works, and the institution
acquires a listener nobody decided to build.

Structural, not substring: PR #70 recorded a substring guard firing on the
identifier `max_subprocesses_per_candidate`, so every check below parses real
syntax nodes.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import textwrap

import pytest

import application
from application import KILL_CRITERION, TRANSPORT_HALF_STATUS

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PACKAGE = os.path.join(ROOT, "application")

#: Importing any of these is a stop-the-line failure.
BANNED_IMPORTS = {
    "socket", "socketserver", "http", "urllib", "requests", "httpx", "asyncio",
    "selectors", "ssl", "ftplib", "smtplib", "telnetlib", "xmlrpc",
    "subprocess", "multiprocessing", "webbrowser",
}

#: Calling any of these is a stop-the-line failure.
BANNED_CALLS = {
    "socket", "create_connection", "create_server", "bind", "listen", "accept",
    "connect", "connect_ex", "urlopen", "getaddrinfo", "gethostbyname",
    "serve_forever", "run_forever", "wrap_socket", "sendall", "recv",
    "Popen", "system", "fork", "spawn",
}


def _modules():
    for name in sorted(os.listdir(PACKAGE)):
        if name.endswith(".py"):
            path = os.path.join(PACKAGE, name)
            with open(path, encoding="utf-8") as fh:
                yield name, ast.parse(fh.read(), filename=path)


MODULES = list(_modules())


# ------------------------------------------- non-negotiable 1: AST inertness
@pytest.mark.parametrize("name,tree", MODULES)
def test_no_module_imports_a_network_or_process_primitive(name, tree):
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in BANNED_IMPORTS:
                    offenders.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in BANNED_IMPORTS:
                offenders.append(f"from {node.module} import ...")
    assert not offenders, (
        f"STOP THE LINE — {name} imports a network or process primitive: "
        f"{offenders}.\n{KILL_CRITERION}"
    )


@pytest.mark.parametrize("name,tree", MODULES)
def test_no_module_calls_a_network_or_process_primitive(name, tree):
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        attr = func.attr if isinstance(func, ast.Attribute) else (
            func.id if isinstance(func, ast.Name) else None)
        if attr in BANNED_CALLS:
            offenders.append(ast.unparse(node)[:80])
    assert not offenders, (
        f"STOP THE LINE — {name} calls a network or process primitive: "
        f"{offenders}.\n{KILL_CRITERION}"
    )


@pytest.mark.parametrize("name,tree", MODULES)
def test_no_module_opens_a_file_or_reads_a_stream(name, tree):
    """Inert means inert. No I/O of any kind, not merely no network.

    A package that reads configuration from disk at import time has a behaviour
    that depends on its environment, and the whole claim here is that given the
    same bytes it produces the same bytes.
    """
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == "open":
            offenders.append(ast.unparse(node)[:80])
        if isinstance(node, ast.Attribute) and node.attr in (
                "read", "readline", "readlines", "write", "makefile"):
            # `bytes.split`-style attribute access is fine; a stream read is not.
            # Reported for review rather than silently allowed.
            value = getattr(node.value, "id", "")
            if value in ("sys", "stdin", "stdout", "stderr", "f", "fh", "file"):
                offenders.append(ast.unparse(node)[:80])
    assert not offenders, f"STOP THE LINE — {name} performs I/O: {offenders}"


def test_no_module_defines_anything_that_serves():
    """A `serve`/`listen`/`run` entry point is the transport half by another name."""
    offenders = []
    for name, tree in MODULES:
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name in ("serve", "serve_forever", "listen", "run",
                                 "start", "main", "bind", "accept"):
                    offenders.append(f"{name}:{node.name}")
    assert not offenders, (
        f"STOP THE LINE — a serving entry point exists: {offenders}.\n"
        f"{KILL_CRITERION}"
    )


def test_the_package_has_no_async_surface():
    """No coroutines. An async application half implies an event loop."""
    offenders = [f"{name}:{node.name}"
                 for name, tree in MODULES
                 for node in ast.walk(tree)
                 if isinstance(node, ast.AsyncFunctionDef)]
    assert not offenders, f"STOP THE LINE — async surface: {offenders}"


# ------------------------------------- the guards are shown to actually bite
@pytest.mark.parametrize("source,description", [
    ("import socket\n", "a socket import"),
    ("from http.server import HTTPServer\n", "an http.server import"),
    ("import asyncio\n", "an asyncio import"),
])
def test_the_import_guard_catches_real_violations(source, description):
    tree = ast.parse(source)
    caught = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            caught += [a.name for a in node.names
                       if a.name.split(".")[0] in BANNED_IMPORTS]
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in BANNED_IMPORTS:
                caught.append(node.module)
    assert caught, f"the import guard does not catch {description}"


def test_the_call_guard_catches_a_real_bind():
    tree = ast.parse("s.bind(('0.0.0.0', 8080))\ns.listen(5)\n")
    caught = [n for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
              and n.func.attr in BANNED_CALLS]
    assert len(caught) == 2, "the call guard does not catch bind/listen"


def test_the_serving_entry_point_guard_catches_a_real_one():
    tree = ast.parse("def serve(app):\n    pass\n")
    caught = [n.name for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "serve"]
    assert caught, "the entry-point guard does not catch a serve() definition"


# ----------------------------- non-negotiable 2: the gap text is explicit
def test_the_package_states_that_the_transport_half_is_absent_and_gated():
    assert "ABSENT AND FOUNDER-GATED" in TRANSPORT_HALF_STATUS
    assert "cannot serve a request" in TRANSPORT_HALF_STATUS
    assert "separate explicit founder authorization" in TRANSPORT_HALF_STATUS


def test_the_blueprint_says_the_same_thing_in_the_same_words():
    """The register and the package must not drift into two stories.

    A package that says "founder-gated" while the ladder says "in progress" lets
    a reader pick whichever is convenient.
    """
    from blueprint.registry import BINDINGS

    gaps = " ".join(BINDINGS[31].gaps)
    assert "ABSENT AND FOUNDER-GATED" in gaps
    assert "cannot serve a request" in gaps


def test_the_blueprint_does_not_claim_a_web_server():
    """The ruling's exact caution: not that we possess a real web server."""
    from blueprint.registry import BINDINGS

    binding = BINDINGS[31]
    gaps = " ".join(binding.gaps).lower()
    assert "no listener" in gaps
    # And the rung is not inflated past what the evidence supports.
    from blueprint.ladder import Rung, rung_index
    assert rung_index(binding.claimed_rung) <= rung_index(Rung.BUILT), (
        "the application half has no closure module and serves no traffic; "
        "claiming EXERCISED or above would be gaming the ladder"
    )


# --------------------- non-negotiable 3: enforced at runtime, not just source
CHILD = textwrap.dedent(
    """
    import json, sys

    violations = []
    WATCHED = {
        "socket.connect": "network", "socket.bind": "network",
        "socket.listen": "network", "socket.accept": "network",
        "socket.getaddrinfo": "network", "socket.gethostbyname": "network",
        "socket.__new__": "network", "urllib.Request": "network",
        "subprocess.Popen": "subprocess", "os.system": "subprocess",
        "os.fork": "subprocess", "os.exec": "subprocess",
    }

    def hook(event, args):
        kind = WATCHED.get(event)
        if kind is not None:
            violations.append({"event": event, "kind": kind})
        if event == "open":
            violations.append({"event": "open", "kind": "file"})

    sys.path.insert(0, __REPO_ROOT__)

    # Imported BEFORE the hook so module import machinery does not register as
    # file I/O; everything measured below is the request path itself.
    from application.router import ApplicationRouter, handle
    from application.response import Response

    router = ApplicationRouter()
    router.add("GET", "/health/{organ}",
               lambda r: Response(200, {"content-type": "text/plain"},
                                  r.params["organ"].encode()))

    sys.addaudithook(hook)

    raw = b"GET /health/kernel HTTP/1.1\\r\\nhost: internal\\r\\n\\r\\n"
    out = handle(raw, router)

    __PROBE__

    sys.stderr.write(json.dumps({
        "violations": violations,
        "ran": True,
        "response": out.decode("latin-1"),
    }))
    """
)


def _run_child(probe: str = ""):
    script = (CHILD.replace("__REPO_ROOT__", repr(ROOT))
                   .replace("__PROBE__", probe))
    proc = subprocess.run([sys.executable, "-c", script],
                          capture_output=True, text=True, timeout=300)
    line = proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else "{}"
    return proc, json.loads(line)


def test_the_whole_request_path_produces_zero_external_effects():
    """Source analysis proves separation; this proves absence of effect.

    A static check cannot see through a dynamic import or a C extension, so the
    full bytes-in/bytes-out path runs under `sys.addaudithook` in a child
    process and the PARENT asserts, rather than the child reporting itself
    clean.
    """
    proc, data = _run_child()
    assert proc.returncode == 0, f"request path failed: {proc.stderr[-1500:]}"
    assert data.get("ran") is True
    assert data["violations"] == [], (
        f"STOP THE LINE — the request path produced external effects: "
        f"{data['violations']}.\n{KILL_CRITERION}"
    )
    # And it did real work while watched, rather than passing by doing nothing.
    assert data["response"].startswith("HTTP/1.1 200 OK")
    assert data["response"].endswith("kernel")


def test_the_audit_harness_detects_a_deliberate_connection():
    """A denial harness that never reports anything is a broken one."""
    _, data = _run_child(probe=textwrap.dedent(
        """
        try:
            import socket
            socket.getaddrinfo("example.invalid", 80)
        except Exception:
            pass
        """
    ).strip())
    assert "network" in {v["kind"] for v in data["violations"]}


def test_the_kill_criterion_is_stated_in_the_package_not_only_in_this_test():
    """A rule that lives only in a test is a rule the next reader will not find."""
    assert "stop" in KILL_CRITERION.lower() or "kill" in KILL_CRITERION.lower() \
        or "fails" in KILL_CRITERION.lower()
    for primitive in ("socket", "bind", "listen", "HTTP client"):
        assert primitive in KILL_CRITERION
    assert hasattr(application, "KILL_CRITERION")
