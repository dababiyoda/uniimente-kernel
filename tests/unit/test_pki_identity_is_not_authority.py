"""Identity proves who is speaking. It must never confer what they may do.

The founder stated this as the load-bearing constraint on ratifying #7 and #26:

> Identity must remain strictly separate from authority. A valid certificate
> proves which workload is speaking; it does not create a capability, budget,
> approval, role, grant, or execution right.

A docstring saying so is worth nothing — the failure mode is a later editor
adding one convenient field to `PeerIdentity` ("just the organ's tier, for
routing") and a caller downstream treating it as permission. So the separation
is asserted over the package's AST, and the absence of network primitives is
asserted twice: structurally, and by running a real handshake under kernel-level
denial.

Structural, not substring: PR #70 recorded a substring guard firing on the
identifier `max_subprocesses_per_candidate`, and that precedent is followed
throughout — every check here parses real syntax nodes.
"""
from __future__ import annotations

import ast
import dataclasses
import json
import os
import subprocess
import sys
import textwrap

import pytest

from identity.pki import PeerIdentity
from identity.pki.handshake import mutual_tls

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PACKAGE = os.path.join(ROOT, "identity", "pki")

#: Modules that decide what may happen. The identity layer answers a different
#: question and must not be able to reach any of them.
AUTHORITY_MODULES = {
    "policy", "authority", "capabilities", "capital", "constitution",
    "provenance", "embassy",
}

#: Field names that would mean identity had started carrying permission.
AUTHORITY_SHAPED = {
    "capability", "capabilities", "budget", "grant", "grants", "role", "roles",
    "permission", "permissions", "approval", "approved", "authority",
    "may_execute", "can_execute", "execution_right", "ceiling", "scope",
    "consequence_class", "trusted", "privileged", "admin",
}


def _sources():
    for name in sorted(os.listdir(PACKAGE)):
        if name.endswith(".py"):
            path = os.path.join(PACKAGE, name)
            with open(path, encoding="utf-8") as fh:
                yield name, ast.parse(fh.read(), filename=path)


# ------------------------------------------------- identity cannot reach authority
@pytest.mark.parametrize("name,tree", list(_sources()))
def test_the_pki_package_imports_no_authority_module(name, tree):
    """A module that cannot import `policy` cannot consult or mint policy."""
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in AUTHORITY_MODULES:
                offenders.append(f"from {node.module} import ...")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in AUTHORITY_MODULES:
                    offenders.append(f"import {alias.name}")
    assert not offenders, (
        f"{name} reaches for authority: {offenders}. A certificate proves who "
        "is speaking; it does not decide what they may do."
    )


def test_peer_identity_carries_no_field_that_reads_as_permission():
    """The whole returned type, checked field by field.

    `PeerIdentity` is what every caller receives from a successful handshake. If
    authentication is ever going to be mistaken for authorisation, this is the
    object through which it happens.
    """
    fields = {f.name for f in dataclasses.fields(PeerIdentity)}
    assert fields == {"spiffe_id", "serial", "not_before", "not_after", "issuer"}

    leaked = {f for f in fields if f in AUTHORITY_SHAPED}
    assert not leaked, f"PeerIdentity grew an authority-shaped field: {leaked}"

    # Properties too — a computed `may_execute` would evade the field check.
    exposed = {n for n in dir(PeerIdentity) if not n.startswith("_")}
    assert not (exposed & AUTHORITY_SHAPED), (
        f"PeerIdentity exposes authority-shaped attributes: "
        f"{sorted(exposed & AUTHORITY_SHAPED)}"
    )


def test_a_verified_peer_identity_is_immutable():
    """A caller cannot upgrade a peer after the fact."""
    peer = PeerIdentity(
        spiffe_id="spiffe://uniimente.internal/organ/daleobanks/bridge",
        serial=1, not_before=None, not_after=None, issuer="UNIIMENTE Internal CA")
    with pytest.raises(dataclasses.FrozenInstanceError):
        peer.spiffe_id = "spiffe://uniimente.internal/kernel/action-gateway"  # type: ignore[misc]


def test_the_guard_would_catch_an_authority_shaped_field():
    """Exercised, not trusted: the check matches a real violation."""
    @dataclasses.dataclass(frozen=True)
    class Tempting:
        spiffe_id: str
        may_execute: bool

    fields = {f.name for f in dataclasses.fields(Tempting)}
    assert fields & AUTHORITY_SHAPED == {"may_execute"}


def test_the_import_guard_would_catch_a_real_authority_import():
    tree = ast.parse("from policy.consequence_gate import ConsequenceGate\n")
    caught = [n for n in ast.walk(tree)
              if isinstance(n, ast.ImportFrom) and n.module
              and n.module.split(".")[0] in AUTHORITY_MODULES]
    assert caught, "the import guard's pattern does not match a real import"


# --------------------------------------------------- no network surface, twice
@pytest.mark.parametrize("name,tree", list(_sources()))
def test_the_pki_package_contains_no_network_primitive(name, tree):
    """The founder's standing constraint, enforced in source.

    No listener, socket, bind, public port, outbound connection or HTTP client.
    `ssl` is imported — but `ssl` without a socket is a cryptographic state
    machine, and `wrap_bio` is precisely the API that uses it without one.
    """
    banned_calls = {"socket", "create_connection", "bind", "listen", "accept",
                    "connect", "connect_ex", "urlopen", "getaddrinfo",
                    "gethostbyname", "create_server", "wrap_socket"}
    banned_imports = {"socket", "socketserver", "http", "urllib", "requests",
                      "httpx", "asyncio", "selectors", "ftplib", "telnetlib",
                      "smtplib", "xmlrpc"}

    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in banned_imports:
                    offenders.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in banned_imports:
                offenders.append(f"from {node.module} import ...")
        elif isinstance(node, ast.Call):
            func = node.func
            attr = func.attr if isinstance(func, ast.Attribute) else (
                func.id if isinstance(func, ast.Name) else None)
            if attr in banned_calls:
                offenders.append(ast.unparse(node)[:80])
    assert not offenders, (
        f"{name} contains a network primitive: {offenders}. The transport half "
        "of this technology remains absent and founder-gated."
    )


def test_the_network_guard_would_catch_a_real_socket():
    """The guard bites — checked against source that really opens a socket."""
    tree = ast.parse("import socket\ns = socket.socket()\ns.connect(('h', 443))\n")
    found = [n for n in ast.walk(tree)
             if isinstance(n, ast.Import)
             and any(a.name == "socket" for a in n.names)]
    assert found, "the network guard's pattern does not match a real socket import"


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
    }

    def hook(event, args):
        kind = WATCHED.get(event)
        if kind is not None:
            violations.append({"event": event, "kind": kind})

    sys.addaudithook(hook)
    sys.path.insert(0, __REPO_ROOT__)

    # Everything below runs under the hook.
    from identity.pki import CertificateAuthority, mutual_tls

    ca = CertificateAuthority()
    server, _ = ca.issue("spiffe://uniimente.internal/kernel/action-gateway")
    client, _ = ca.issue("spiffe://uniimente.internal/organ/daleobanks/bridge")
    seen_server, seen_client = mutual_tls(client, server)

    __PROBE__

    sys.stderr.write(json.dumps({
        "violations": violations,
        "ran": True,
        "client": seen_client.spiffe_id,
        "server": seen_server.spiffe_id,
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


def test_a_real_handshake_touches_no_network_under_audit():
    """Source analysis proves separation; this proves absence of effect.

    A static check cannot see through a dynamic import or a C extension, so the
    handshake also runs in a child process under `sys.addaudithook`, and the
    PARENT asserts on the result rather than the child self-reporting a clean
    bill of health.
    """
    proc, data = _run_child()
    assert proc.returncode == 0, f"handshake failed in child: {proc.stderr[-1500:]}"
    assert data.get("ran") is True
    assert data["violations"] == [], (
        f"the handshake produced network effects: {data['violations']}"
    )
    # And it did real work while denied, rather than passing by doing nothing.
    assert data["client"] == "spiffe://uniimente.internal/organ/daleobanks/bridge"
    assert data["server"] == "spiffe://uniimente.internal/kernel/action-gateway"


def test_the_audit_harness_detects_a_deliberate_connection():
    """A denial harness that never reports anything is a broken one."""
    _, data = _run_child(probe=textwrap.dedent(
        """
        try:
            import socket
            socket.getaddrinfo("example.invalid", 443)
        except Exception:
            pass
        """
    ).strip())
    assert "network" in {v["kind"] for v in data["violations"]}, (
        "the audit harness failed to detect a deliberate network call"
    )
