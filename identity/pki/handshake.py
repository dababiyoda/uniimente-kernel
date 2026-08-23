"""A complete mutual TLS handshake with no network primitive anywhere.

## Why in-memory, and what that costs

The founder's standing constraints forbid opening a public network surface,
listener, bind or outbound connection. `ssl.SSLContext.wrap_bio` runs the TLS
state machine over `MemoryBIO` buffers, so this is a genuine TLS 1.3 exchange —
real chain validation, real mutual authentication, real expiry enforcement —
with the transport removed. Not a mock of TLS: TLS, with no socket.

What it does not prove is equally important and is stated rather than implied:
no real peer has spoken this, no network path exists, and certificate
distribution and key custody are unsolved. This earns the mechanism, not the
deployment.

## Identity comes from the certificate, never from the claim

`_spiffe_id_from()` reads the URI SAN of the peer certificate **after** OpenSSL
has validated the chain. Nothing a peer *says* about itself reaches the returned
`PeerIdentity`. This is the concrete difference from the HMAC transport, where
`X-Service-Identity` was a header the sender chose and the signature only proved
that *somebody with the shared key* had chosen it.

## Fail closed, and never downgrade

Both sides set `CERT_REQUIRED`. A peer that presents no certificate fails the
handshake rather than continuing unauthenticated, and there is no parameter to
relax that — the way an optional-mTLS flag becomes a permanent downgrade path is
by existing.
"""
from __future__ import annotations

import datetime
import ssl
from dataclasses import dataclass

from identity.pki.errors import (
    CertificateExpired,
    CertificateRevoked,
    HandshakeRefused,
    UntrustedIssuer,
)
from identity.pki.revocation import RevocationList
from identity.pki.workload import WorkloadIdentity

#: Bound on handshake pumping rounds. TLS 1.3 completes in far fewer; this only
#: stops a malformed exchange from spinning. Not a timeout — there is no clock
#: here and no I/O to wait on.
_MAX_ROUNDS = 16


@dataclass(frozen=True)
class PeerIdentity:
    """Who the peer is. Deliberately, that is all.

    There is no `capabilities`, no `budget`, no `role`, no `grant`, no
    `may_execute`. Not omitted for brevity — absent because the question "what
    may this peer do?" has no answer at the identity layer, and a field here
    would invite a caller to treat authentication as authorisation.

    `test_pki_identity_is_not_authority.py` asserts the absence structurally,
    so adding such a field fails the build.
    """

    spiffe_id: str
    serial: int
    not_before: datetime.datetime
    not_after: datetime.datetime
    issuer: str

    @property
    def organ(self) -> str:
        """Which organ this workload belongs to, for routing and logging.

        The live namespace in `identity/service-identities.yaml` has two path
        shapes, and this must honour both rather than the tidier one:

            spiffe://uniimente.internal/kernel/action-gateway
            spiffe://uniimente.internal/organ/daleobanks/bridge

        Kernel services sit directly under the trust domain; organ workloads sit
        under an `organ/` segment. Reading position 1 unconditionally — the
        first version of this — returned the literal `"organ"` for every organ
        workload, which is a routing label that looks plausible and is wrong for
        every non-kernel caller. Both shapes are pinned by test.

        Naming convenience only. Two workloads in the same organ are distinct
        identities and nothing here merges them.
        """
        parts = self.spiffe_id.removeprefix("spiffe://").split("/")
        if len(parts) < 2:
            return ""
        if parts[1] == "organ":
            return parts[2] if len(parts) > 2 else ""
        return parts[1]


def _spiffe_id_from(peer_cert: dict) -> str:
    """The URI SAN of a chain-validated certificate.

    Reads `subjectAltName` only. Falls back to nothing: a certificate without a
    URI SAN has no identity this institution recognises, and guessing one from
    the Common Name would resurrect exactly the free-text identity the SAN
    exists to replace.
    """
    for kind, value in peer_cert.get("subjectAltName", ()):
        if kind == "URI" and value.startswith("spiffe://"):
            return value
    raise HandshakeRefused(
        "peer certificate carries no SPIFFE URI SAN; identity is taken from the "
        "validated certificate and never inferred from the subject"
    )


def _serial_from(peer_cert: dict) -> int:
    raw = peer_cert.get("serialNumber")
    if not raw:
        raise HandshakeRefused("peer certificate has no serial number")
    return int(raw, 16)


def _issuer_from(peer_cert: dict) -> str:
    for rdn in peer_cert.get("issuer", ()):
        for key, value in rdn:
            if key == "commonName":
                return value
    return ""


def _to_peer(peer_cert: dict) -> PeerIdentity:
    return PeerIdentity(
        spiffe_id=_spiffe_id_from(peer_cert),
        serial=_serial_from(peer_cert),
        not_before=_parse_time(peer_cert["notBefore"]),
        not_after=_parse_time(peer_cert["notAfter"]),
        issuer=_issuer_from(peer_cert),
    )


def _parse_time(raw: str) -> datetime.datetime:
    return datetime.datetime.strptime(
        raw, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=datetime.timezone.utc)


def _classify(exc: ssl.SSLError) -> Exception:
    """Turn OpenSSL's verification message into the institution's vocabulary.

    Kept narrow on purpose. Anything unrecognised becomes `HandshakeRefused`
    rather than a guess, because mislabelling a failure is worse than labelling
    it generically — an operator who reads "expired" for a chain-of-trust
    failure looks in the wrong place.
    """
    message = str(exc)
    if "KEY_VALUES_MISMATCH" in message or "key values mismatch" in message:
        # Proof of possession failed before a byte was exchanged: the presented
        # certificate does not match the private key held. This is what a
        # replayed certificate looks like — certificates travel in the clear, so
        # an attacker has one, but pairing it with their own key is detected
        # here rather than in the handshake loop.
        return HandshakeRefused(
            "certificate does not match the private key presented with it: "
            f"{message}")
    if "expired" in message:
        return CertificateExpired(message)
    if any(marker in message for marker in (
            "unknown ca", "self signed", "self-signed", "unable to get local "
            "issuer", "certificate verify failed: unable")):
        return UntrustedIssuer(message)
    return HandshakeRefused(message)


def mutual_tls(
    client: WorkloadIdentity,
    server: WorkloadIdentity,
    *,
    revocations: RevocationList | None = None,
) -> tuple[PeerIdentity, PeerIdentity]:
    """Run a real mutual TLS handshake in memory.

    Returns `(server_as_seen_by_client, client_as_seen_by_server)` — each side's
    view of the other, derived from the certificate that side validated. The
    two are returned separately rather than merged because they are two
    independent verifications, and collapsing them would hide the case where
    only one direction actually authenticated.

    Raises on any failure. There is no partial success.
    """
    revocations = revocations or RevocationList()

    with client.materialise() as (client_chain, client_trust), \
            server.materialise() as (server_chain, server_trust):

        # Context construction is inside the same classification as the
        # handshake itself. Loading a chain verifies that the certificate and
        # the private key belong together, so a replayed certificate paired with
        # an attacker's key is refused *here* — and it must surface as an
        # IdentityError like every other refusal. Leaving OpenSSL's raw
        # SSLError to escape would mean a caller catching IdentityError saw an
        # unexpected crash instead of a clean denial, which is how a refusal
        # quietly becomes an outage.
        try:
            client_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            client_ctx.load_cert_chain(client_chain)
            client_ctx.load_verify_locations(client_trust)
            client_ctx.verify_mode = ssl.CERT_REQUIRED
            # Identity is the SPIFFE URI SAN, not a DNS name. There is no
            # hostname to check and no DNS in this trust model; leaving hostname
            # checking on would fail every handshake for the wrong reason.
            client_ctx.check_hostname = False

            server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            server_ctx.load_cert_chain(server_chain)
            server_ctx.load_verify_locations(server_trust)
            # The mutual half. Without this the server would accept any client
            # and this would be ordinary one-way TLS wearing the name.
            server_ctx.verify_mode = ssl.CERT_REQUIRED
        except ssl.SSLError as exc:
            raise _classify(exc) from exc

        client_in, client_out = ssl.MemoryBIO(), ssl.MemoryBIO()
        server_in, server_out = ssl.MemoryBIO(), ssl.MemoryBIO()
        client_obj = client_ctx.wrap_bio(client_in, client_out,
                                         server_side=False)
        server_obj = server_ctx.wrap_bio(server_in, server_out,
                                         server_side=True)

        client_done = server_done = False
        for _ in range(_MAX_ROUNDS):
            for obj, outgoing, peer_inbox, finished in (
                    (client_obj, client_out, server_in, "client"),
                    (server_obj, server_out, client_in, "server")):
                try:
                    obj.do_handshake()
                    if finished == "client":
                        client_done = True
                    else:
                        server_done = True
                except ssl.SSLWantReadError:
                    pass
                except ssl.SSLError as exc:
                    raise _classify(exc) from exc
                payload = outgoing.read()
                if payload:
                    peer_inbox.write(payload)
            if client_done and server_done:
                break
        else:
            raise HandshakeRefused(
                "handshake did not complete within the round budget")

        server_seen_by_client = client_obj.getpeercert()
        client_seen_by_server = server_obj.getpeercert()

        # A server that requested a client certificate and received none can
        # still finish a handshake. Refusing here is what makes this mutual.
        if not client_seen_by_server:
            raise HandshakeRefused(
                "peer completed the handshake without presenting a client "
                "certificate; one-way TLS is not mutual authentication")
        if not server_seen_by_client:
            raise HandshakeRefused("server presented no certificate")

        peer_server = _to_peer(server_seen_by_client)
        peer_client = _to_peer(client_seen_by_server)

    # Revocation is checked after chain validation, so an untrusted *and*
    # revoked certificate reports the more fundamental failure. Both directions
    # are checked: a revoked server is as dangerous as a revoked client.
    for peer, side in ((peer_client, "client"), (peer_server, "server")):
        if revocations.is_revoked(peer.serial):
            raise CertificateRevoked(
                f"{side} {peer.spiffe_id} presented revoked serial "
                f"{peer.serial:x}: {revocations.reason(peer.serial) or 'no reason recorded'}"
            )

    return peer_server, peer_client
