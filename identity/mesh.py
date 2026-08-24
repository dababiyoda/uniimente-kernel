"""The internal identity mesh — where `identity/pki/` stops being beside the
institution and starts being used by it.

Created 2026-08-23 under FOUNDER-RULING-2026-08-23: *"cryptographically isolated
workload identities actually adopted in the live internal bridges, not merely
implemented beside them."*

## What was missing

`identity/pki/` was built, tested and deliberately left unadopted — the PR that
shipped it said so plainly, and `governance.gap_audit` was rewritten to measure
*adoption* rather than the presence of an asymmetric primitive, precisely so
that building it could not be mistaken for using it.

Two things were absent between "the mechanism exists" and "the institution uses
it":

1. **Nobody issued the identities.** `CertificateAuthority.issue` mints one
   workload identity at a time from a SPIFFE string. No component held a CA,
   and no component knew which SPIFFE strings the institution actually declares.
2. **Nobody connected them.** `mutual_tls` authenticates two `WorkloadIdentity`
   objects. Nothing produced the pair.

This module is both halves, and nothing more.

## The registry is the source of names

Service identities are declared in `identity/service-identities.yaml` — a
constitutional artifact, watched by `governance.integrity`. This module reads
it. It does not carry its own list, and it refuses a service the registry does
not name.

That direction matters. A mesh with its own hardcoded identity list would be a
second identity authority, and the first divergence between it and the registry
would be invisible: certificates would keep verifying, against names the
institution never declared.

## Identity is still not authority

The same wall the PKI package enforces, enforced again here because this module
is the one an application-side caller will reach for:

- no import of `policy`, `authority`, `capabilities` or `capital`;
- `connect()` returns `PeerIdentity` objects, which have no capability field;
- a verified handshake answers *who* and says nothing about *may*.

`tests/unit/test_identity_mesh.py` asserts the import wall structurally.

## What this is not

Not a network. `mutual_tls` runs over `ssl.MemoryBIO` — a real TLS 1.3 handshake
with real chain validation and no socket, because the standing constraints
forbid a network surface. Adoption here means the live in-process bridge
authenticates its peer with an isolated key instead of asserting a string. It
does not mean anything left the process, and `identity_isolated` travelling as
`"true"` is a claim about the key model, never about reachability.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from identity.pki.ca import CertificateAuthority
from identity.pki.handshake import PeerIdentity, mutual_tls
from identity.pki.revocation import RevocationList
from identity.pki.workload import WorkloadIdentity

KERNEL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY_PATH = os.path.join(KERNEL_ROOT, "identity", "service-identities.yaml")


class MeshError(PermissionError):
    """A service was asked for that the institution does not declare.

    A `PermissionError` rather than a `KeyError`: asking for an identity the
    registry does not name is a refusal, not a lookup miss, and the difference
    matters at the call site — a caller catching `KeyError` around a dict access
    would swallow it.
    """


def load_registry(path: str = REGISTRY_PATH) -> dict[str, str]:
    """`{service_name: spiffe_id}` exactly as the institution declares them."""
    import yaml

    with open(path, encoding="utf-8") as handle:
        document = yaml.safe_load(handle)

    services = document.get("services") or {}
    return {name: spec["id"] for name, spec in services.items() if "id" in spec}


@dataclass
class InternalMesh:
    """One CA, one identity per declared service, issued on demand.

    Deliberately not a singleton and deliberately not process-global. Each mesh
    anchors its own trust: two meshes do not trust each other, which is what
    makes a test that builds its own mesh a genuine negative control rather than
    a run against the same anchor with a different variable name.
    """

    ca: CertificateAuthority = field(default_factory=CertificateAuthority)
    revocations: RevocationList = field(default_factory=RevocationList)
    registry: dict[str, str] = field(default_factory=load_registry)
    _issued: dict[str, WorkloadIdentity] = field(default_factory=dict, repr=False)

    def spiffe_id(self, service: str) -> str:
        """The declared SPIFFE ID for a service name. Refuses undeclared ones."""
        try:
            return self.registry[service]
        except KeyError:
            raise MeshError(
                f"{service!r} is not a declared service identity. The mesh "
                f"issues only for names in identity/service-identities.yaml; "
                f"known: {sorted(self.registry)}"
            ) from None

    def identity_for(self, service: str) -> WorkloadIdentity:
        """This service's private identity material, minted once per mesh.

        Cached because re-issuing per call would hand the same service a new
        serial on every connection, making revocation meaningless: revoking the
        serial you saw would not revoke the one it uses next.
        """
        if service not in self._issued:
            workload, _issued = self.ca.issue(self.spiffe_id(service))
            self._issued[service] = workload
        return self._issued[service]

    def connect(self, client: str, server: str
                ) -> tuple[PeerIdentity, PeerIdentity]:
        """Authenticate two declared services to each other.

        Returns `(server_as_seen_by_client, client_as_seen_by_server)` — the two
        independent verifications kept separate, exactly as `mutual_tls` returns
        them. Merging them would hide a handshake where only one direction
        actually authenticated.

        Raises `IdentityError` on any failure. There is no partial success and
        no fallback to the shared-secret path: a caller that wants the legacy
        path must ask for it by name.
        """
        return mutual_tls(self.identity_for(client), self.identity_for(server),
                          revocations=self.revocations)

    def revoke(self, service: str, *, reason: str) -> int:
        """Revoke a service's current certificate. Returns the dead serial.

        The identity is dropped from the cache, so the next `identity_for` mints
        a fresh one — revocation removes a credential, it does not remove a
        service from the institution.
        """
        workload = self.identity_for(service)
        self.revocations.revoke(workload.serial, reason=reason)
        del self._issued[service]
        return workload.serial
