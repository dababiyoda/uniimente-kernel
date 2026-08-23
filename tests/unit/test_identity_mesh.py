"""The internal identity mesh, attacked — and the adoption it exists to make real.

`identity/pki/` was built a day before this and deliberately left unadopted.
This file covers the module that adopts it, so most of it is about the two
things adoption can get wrong: inventing identities the institution never
declared, and letting authentication quietly become authorisation.
"""
from __future__ import annotations

import ast
import os

import pytest

from identity.mesh import InternalMesh, MeshError, load_registry
from identity.pki.ca import CertificateAuthority
from identity.pki.errors import CertificateRevoked, IdentityError, UntrustedIssuer

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# -- the registry is the source of names ------------------------------------

def test_the_mesh_issues_only_for_declared_service_identities():
    """A mesh that minted its own names would be a second identity authority.

    The first divergence between it and `identity/service-identities.yaml`
    would be invisible: certificates would keep verifying, against names the
    institution never declared.
    """
    mesh = InternalMesh()

    with pytest.raises(MeshError, match="not a declared service identity"):
        mesh.identity_for("bridge_that_does_not_exist")


def test_every_declared_service_can_be_issued_an_identity():
    """The registry and the CA agree about the trust domain.

    A declared service the CA refuses to issue for would be a service that can
    never authenticate — an identity on paper only, which is the state this
    module exists to end.
    """
    mesh = InternalMesh()
    assert mesh.registry, "the registry parsed to nothing"

    for service in mesh.registry:
        workload = mesh.identity_for(service)
        assert workload.spiffe_id == mesh.registry[service]


def test_the_registry_is_read_not_restated():
    """The mesh holds no identity list of its own."""
    from identity import mesh as mesh_module

    with open(mesh_module.__file__, encoding="utf-8") as handle:
        source = handle.read()

    for spiffe_id in load_registry().values():
        assert spiffe_id not in source, (
            f"{spiffe_id} is hardcoded in identity/mesh.py; the registry must "
            "be the only place service identities are named")


# -- the handshake is real --------------------------------------------------

def test_two_declared_services_authenticate_each_other():
    mesh = InternalMesh()

    server_seen, client_seen = mesh.connect("bridge_daleobanks", "kernel_gateway")

    assert client_seen.spiffe_id == \
        "spiffe://uniimente.internal/organ/daleobanks/bridge"
    assert server_seen.spiffe_id == \
        "spiffe://uniimente.internal/kernel/action-gateway"
    # Both namespace shapes resolve to a usable organ label.
    assert client_seen.organ == "daleobanks"
    assert server_seen.organ == "kernel"


def test_an_identity_is_stable_across_connections():
    """Re-issuing per call would make revocation meaningless: revoking the
    serial you saw would not revoke the one the service uses next."""
    mesh = InternalMesh()

    first = mesh.identity_for("bridge_daleobanks").serial
    mesh.connect("bridge_daleobanks", "kernel_gateway")
    second = mesh.identity_for("bridge_daleobanks").serial

    assert first == second


def test_a_revoked_workload_cannot_authenticate():
    mesh = InternalMesh()
    workload = mesh.identity_for("bridge_daleobanks")
    mesh.revocations.revoke(workload.serial, reason="test")

    with pytest.raises(CertificateRevoked):
        mesh.connect("bridge_daleobanks", "kernel_gateway")


def test_revocation_removes_a_credential_not_a_service():
    """The service keeps existing; the certificate stops being trusted."""
    mesh = InternalMesh()

    dead = mesh.revoke("bridge_daleobanks", reason="rotation drill")
    fresh = mesh.identity_for("bridge_daleobanks")

    assert fresh.serial != dead
    assert fresh.spiffe_id == mesh.spiffe_id("bridge_daleobanks")
    # And the replacement authenticates, so revocation is not a one-way door.
    mesh.connect("bridge_daleobanks", "kernel_gateway")


def test_two_meshes_do_not_trust_each_other():
    """Each mesh anchors its own trust.

    This is what makes a test that builds its own mesh a real negative control
    rather than a run against the same anchor under a different name.
    """
    mesh = InternalMesh()
    foreign = CertificateAuthority(common_name="Foreign CA")
    forged, _ = foreign.issue(
        "spiffe://uniimente.internal/organ/daleobanks/bridge")

    from identity.pki.handshake import mutual_tls

    with pytest.raises(UntrustedIssuer):
        mutual_tls(forged, mesh.identity_for("kernel_gateway"))


# -- identity is not authority ----------------------------------------------

def test_the_mesh_cannot_reach_authority_modules():
    """The same wall `identity/pki/` enforces, enforced at the adoption layer.

    This module is the one an application-side caller reaches for, so it is the
    likeliest place for a convenience import to turn a verified identity into a
    permission check.
    """
    from identity import mesh as mesh_module

    with open(mesh_module.__file__, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())

    forbidden = {"policy", "authority", "capabilities", "capital"}
    for node in ast.walk(tree):
        modules: list[str] = []
        if isinstance(node, ast.Import):
            modules = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules = [node.module]
        for module in modules:
            assert module.split(".")[0] not in forbidden, (
                f"identity/mesh.py imports {module}; a verified identity must "
                "not be able to answer 'what may this peer do?'")


def test_a_verified_peer_carries_no_capability():
    mesh = InternalMesh()
    _server, client = mesh.connect("bridge_daleobanks", "kernel_gateway")

    for attribute in ("capabilities", "budget", "role", "grant", "may_execute",
                      "authority"):
        assert not hasattr(client, attribute), (
            f"PeerIdentity grew {attribute!r}; authentication would start "
            "reading as authorisation")


# -- the adoption itself ------------------------------------------------------

def test_bridge_a_authenticates_its_peer_instead_of_asserting_it():
    """The founder's condition: adopted in the live bridge, not beside it.

    Bridge A used to build HMAC headers with `identity="daleobanks"` and then
    verify them against a shared secret every participant holds — the kernel
    signing as DALEOBANKS and confirming DALEOBANKS had signed. The organ label
    now comes off a chain-validated certificate.
    """
    with open(os.path.join(ROOT, "bridges", "signal_to_venture.py"),
              encoding="utf-8") as handle:
        source = handle.read()

    assert "verify_mutual_identity" in source
    assert 'transport_identity="daleobanks"' not in source, (
        "the bridge asserts its peer's identity from a literal again")


def test_the_adoption_probe_agrees_that_adoption_happened():
    """Measured by the institution's own audit, not by this file's opinion."""
    from governance import gap_audit

    still_open, detail = gap_audit._asymmetric_identity_is_not_adopted()

    assert still_open is False
    assert "bridges/signal_to_venture.py" in detail


def test_adoption_is_reported_as_one_edge_deep_and_not_as_finished():
    """The honest remaining gap.

    One bridge authenticating is not an authenticated institution, and a green
    row here would be the proxy failure the gap audit was rewritten to avoid.
    """
    from governance import gap_audit

    still_open, detail = gap_audit._asymmetric_identity_is_only_one_edge_deep()

    assert still_open is True
    assert "declared trust edges authenticate their peer" in detail
    assert "bridges/signal_to_venture.py" not in detail.split("still unauthenticated")[1]


def test_every_declared_trust_edge_exists():
    """A typo in the edge list would count as an unauthenticated edge forever,
    inflating the gap with a file that was never there."""
    from governance.gap_audit import _TRUST_EDGES

    for relative in _TRUST_EDGES:
        assert os.path.isfile(os.path.join(ROOT, relative)), relative
