"""The attacks the founder named, run against the real handshake.

FOUNDER-RULING-2026-08-22 ratified technologies #7 and #26 with an explicit test
list: *"Test impersonation, wrong-cert identity, expired certs, revoked certs,
replay, rotation, downgrade attempts, and cross-organ authentication."* Each is
below, and each fails closed.

Two disciplines carried from earlier work in this repository:

**No mocked clock.** The expiry tests issue certificates whose validity window
genuinely lies in the past, via `CertificateAuthority.issue(not_before=...)`.
Monkeypatching `datetime` would prove the monkeypatch works; issuing a real
expired certificate proves OpenSSL's validation works.

**Every guard is shown to bite.** A refusal test that passes because the setup
was broken is indistinguishable from one that passes because the guard fired, so
each negative case is paired with the positive control that would otherwise have
succeeded.
"""
from __future__ import annotations

import datetime

import pytest

from identity.pki import (
    CertificateAuthority,
    CertificateExpired,
    CertificateRevoked,
    HandshakeRefused,
    IdentityError,
    RevocationList,
    UntrustedIssuer,
    mutual_tls,
)

KERNEL = "spiffe://uniimente.internal/kernel/action-gateway"
DALEOBANKS = "spiffe://uniimente.internal/organ/daleobanks/bridge"
WEALTHMACHINE = "spiffe://uniimente.internal/organ/wealthmachine/bridge"


@pytest.fixture
def ca() -> CertificateAuthority:
    return CertificateAuthority()


# --------------------------------------------------------- the positive control
def test_two_workloads_of_the_same_ca_authenticate_each_other(ca):
    """The baseline. Every refusal below is measured against this succeeding."""
    server, _ = ca.issue(KERNEL)
    client, issued = ca.issue(DALEOBANKS)

    seen_server, seen_client = mutual_tls(client, server)

    assert seen_client.spiffe_id == DALEOBANKS
    assert seen_server.spiffe_id == KERNEL
    assert seen_client.serial == issued.serial
    assert seen_client.issuer == "UNIIMENTE Internal CA"


def test_identity_comes_from_the_certificate_not_from_any_claim(ca):
    """The concrete improvement over the shared HMAC key.

    Under HMAC, `X-Service-Identity` was a header the sender chose; the
    signature only proved that *somebody holding the shared secret* chose it.
    Here the returned identity is read out of the chain-validated certificate,
    so there is no channel through which a peer can assert a different one.
    """
    server, _ = ca.issue(KERNEL)
    client, _ = ca.issue(DALEOBANKS)

    _, seen_client = mutual_tls(client, server)

    # The identity equals the SAN the CA bound, and the workload had no input.
    assert seen_client.spiffe_id == client.spiffe_id
    assert seen_client.spiffe_id == DALEOBANKS


# -------------------------------------------------------------- impersonation
def test_a_foreign_ca_cannot_mint_a_kernel_identity(ca):
    """Impersonation, the attack the shared key could not stop.

    An attacker stands up their own CA and issues themselves the kernel's exact
    SPIFFE ID. Under HMAC this succeeded outright, because holding the verifying
    secret *was* holding the signing secret. Here the SAN says `kernel` and the
    chain says nothing the verifier anchors, so it is refused.
    """
    attacker_ca = CertificateAuthority(common_name="Attacker CA")
    forged, _ = attacker_ca.issue(KERNEL)          # same SPIFFE ID
    honest_server, _ = ca.issue(KERNEL)

    assert forged.spiffe_id == honest_server.spiffe_id, (
        "fixture must forge the *same* identity or it tests nothing"
    )
    with pytest.raises(UntrustedIssuer):
        mutual_tls(forged, honest_server)


def test_a_workload_cannot_reissue_itself_under_another_identity(ca):
    """Self-assigned identity, refused at the point of issuance.

    The frozen `WorkloadIdentity` is half the answer; the other half is that
    only the CA can bind a SPIFFE ID to a key at all.
    """
    client, _ = ca.issue(DALEOBANKS)
    with pytest.raises(AttributeError):
        client.spiffe_id = KERNEL  # type: ignore[misc]


def test_the_ca_refuses_identities_outside_its_trust_domain(ca):
    with pytest.raises(ValueError, match="outside the trust domain"):
        ca.issue("spiffe://someone-elses-domain/kernel/action-gateway")


# ------------------------------------------------------------------- expiry
def test_an_expired_certificate_is_refused(ca):
    """Issued with a genuinely past validity window — no clock is mocked."""
    long_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)
    stale, _ = ca.issue(DALEOBANKS, not_before=long_ago,
                        lifetime=datetime.timedelta(hours=1))
    server, _ = ca.issue(KERNEL)

    with pytest.raises(CertificateExpired):
        mutual_tls(stale, server)


def test_the_expiry_guard_is_not_refusing_everything(ca):
    """The control for the test above: same code path, unexpired certificate."""
    recent = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5)
    fresh, _ = ca.issue(DALEOBANKS, not_before=recent,
                        lifetime=datetime.timedelta(hours=1))
    server, _ = ca.issue(KERNEL)

    _, seen = mutual_tls(fresh, server)
    assert seen.spiffe_id == DALEOBANKS


def test_an_expired_server_is_refused_too(ca):
    """Both directions. A stale server is as dangerous as a stale client."""
    long_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)
    stale_server, _ = ca.issue(KERNEL, not_before=long_ago,
                               lifetime=datetime.timedelta(hours=1))
    client, _ = ca.issue(DALEOBANKS)

    with pytest.raises(IdentityError):
        mutual_tls(client, stale_server)


# --------------------------------------------------------------- revocation
def test_a_revoked_client_is_refused_although_its_certificate_still_validates(ca):
    """The case expiry cannot cover: a live certificate whose key is burned."""
    server, _ = ca.issue(KERNEL)
    client, issued = ca.issue(DALEOBANKS)

    crl = RevocationList()
    # Control: it authenticates before revocation, so the refusal below is
    # attributable to the revocation and nothing else.
    mutual_tls(client, server, revocations=crl)

    crl.revoke(issued.serial, reason="key believed compromised")
    with pytest.raises(CertificateRevoked, match="key believed compromised"):
        mutual_tls(client, server, revocations=crl)


def test_a_revoked_server_is_refused(ca):
    server, issued = ca.issue(KERNEL)
    client, _ = ca.issue(DALEOBANKS)

    crl = RevocationList()
    crl.revoke(issued.serial, reason="organ detached")
    with pytest.raises(CertificateRevoked, match="organ detached"):
        mutual_tls(client, server, revocations=crl)


def test_revoking_twice_keeps_the_first_reason(ca):
    """A later blanket sweep must not erase why trust was actually withdrawn."""
    _, issued = ca.issue(DALEOBANKS)
    crl = RevocationList()
    crl.revoke(issued.serial, reason="key believed compromised")
    crl.revoke(issued.serial, reason="routine cleanup")
    assert crl.reason(issued.serial) == "key believed compromised"


def test_revocation_is_permanent_by_construction(ca):
    """There is no unrevoke, and that is the design, not an omission."""
    crl = RevocationList()
    assert not hasattr(crl, "unrevoke")
    assert not hasattr(crl, "restore")


# ----------------------------------------------------------------- rotation
def test_rotation_issues_an_independent_key_and_the_old_serial_can_be_retired(ca):
    """Rotation must not preserve the key, or it does not recover from anything.

    The whole point of rotating after a suspected compromise is that the
    compromised private key stops working. A 'renew' that kept the key would
    leave the attacker exactly where they were.
    """
    server, _ = ca.issue(KERNEL)
    old, old_issued = ca.issue(DALEOBANKS)
    new, new_issued = ca.issue(DALEOBANKS)

    assert old.private_key_pem != new.private_key_pem, "rotation reused a key"
    assert old_issued.serial != new_issued.serial

    crl = RevocationList()
    crl.revoke(old_issued.serial, reason="rotated")

    # The new certificate works; the retired one does not. Same identity.
    _, seen = mutual_tls(new, server, revocations=crl)
    assert seen.spiffe_id == DALEOBANKS
    with pytest.raises(CertificateRevoked):
        mutual_tls(old, server, revocations=crl)


def test_every_issued_workload_gets_an_independent_keypair(ca):
    """Cryptographic isolation, asserted across the whole registry shape.

    'One identity per service' is worth nothing if two services share key
    material — that would be the shared secret again with more ceremony.
    """
    identities = [ca.issue(spiffe)[0] for spiffe in
                  (KERNEL, DALEOBANKS, WEALTHMACHINE,
                   "spiffe://uniimente.internal/kernel/policy-engine",
                   "spiffe://uniimente.internal/organ/railscout/evidence-browser")]
    keys = {identity.private_key_pem for identity in identities}
    assert len(keys) == len(identities), "two workloads share private key material"

    certs = {identity.certificate_pem for identity in identities}
    assert len(certs) == len(identities)


# ------------------------------------------------------- cross-organ handshake
@pytest.mark.parametrize("initiator,responder", [
    (DALEOBANKS, KERNEL),
    (WEALTHMACHINE, KERNEL),
    (DALEOBANKS, WEALTHMACHINE),
    (KERNEL, DALEOBANKS),
])
def test_cross_organ_authentication_names_both_parties(ca, initiator, responder):
    """Every pairing the bridges actually use, in both directions."""
    client, _ = ca.issue(initiator)
    server, _ = ca.issue(responder)

    seen_server, seen_client = mutual_tls(client, server)
    assert seen_client.spiffe_id == initiator
    assert seen_server.spiffe_id == responder


def test_the_organ_label_handles_both_namespace_shapes(ca):
    """Pins the bug this module shipped with, in both shapes.

    The first implementation read path position 1 unconditionally and returned
    the literal `"organ"` for every organ workload — a routing label that looks
    plausible and is wrong for every non-kernel caller.
    """
    server, _ = ca.issue(KERNEL)
    client, _ = ca.issue(DALEOBANKS)
    seen_server, seen_client = mutual_tls(client, server)

    assert seen_client.organ == "daleobanks"
    assert seen_server.organ == "kernel"


# ----------------------------------------------------------------- downgrade
def test_a_client_presenting_no_certificate_cannot_complete_the_handshake(ca):
    """One-way TLS is not mutual TLS, and must not be accepted as it.

    This is the downgrade that matters: an anonymous client finishing a
    handshake and being treated as authenticated. The server demands a
    certificate and the exchange fails rather than yielding an unnamed peer.
    """
    import ssl

    server, _ = ca.issue(KERNEL)
    with server.materialise() as (server_chain, server_trust):
        server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_ctx.load_cert_chain(server_chain)
        server_ctx.load_verify_locations(server_trust)
        server_ctx.verify_mode = ssl.CERT_REQUIRED

        # A client with a trust bundle but NO certificate of its own.
        anon_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        anon_ctx.load_verify_locations(server_trust)
        anon_ctx.check_hostname = False
        anon_ctx.verify_mode = ssl.CERT_REQUIRED

        c_in, c_out = ssl.MemoryBIO(), ssl.MemoryBIO()
        s_in, s_out = ssl.MemoryBIO(), ssl.MemoryBIO()
        cobj = anon_ctx.wrap_bio(c_in, c_out, server_side=False)
        sobj = server_ctx.wrap_bio(s_in, s_out, server_side=True)

        failed = False
        for _ in range(16):
            for obj, out, inbox in ((cobj, c_out, s_in), (sobj, s_out, c_in)):
                try:
                    obj.do_handshake()
                except ssl.SSLWantReadError:
                    pass
                except ssl.SSLError:
                    failed = True
                data = out.read()
                if data:
                    inbox.write(data)
            if failed:
                break

        assert failed or not sobj.getpeercert(), (
            "an anonymous client was accepted; mutual authentication is not "
            "being enforced"
        )


def test_mutual_tls_exposes_no_switch_that_relaxes_verification():
    """There is no `verify=False`, and its absence is the point.

    An optional-mTLS parameter becomes a permanent downgrade path by existing:
    one caller sets it during an incident, and it is never unset. The signature
    offers no way to ask for less.
    """
    import inspect

    params = set(inspect.signature(mutual_tls).parameters)
    assert params == {"client", "server", "revocations"}
    forbidden = {"verify", "insecure", "allow_unverified", "optional",
                 "check_hostname", "verify_mode", "fallback", "downgrade"}
    assert not (params & forbidden)


# -------------------------------------------------------------------- replay
def test_a_captured_certificate_alone_does_not_impersonate_its_holder(ca):
    """Replay, at the identity layer.

    Certificates travel in the clear on every handshake, so an attacker
    trivially obtains one. What they cannot obtain is the private key, and TLS
    requires proving possession of it. Replaying the certificate without the key
    fails — which is precisely what capturing a signed HMAC header did *not*
    guarantee.
    """
    from identity.pki import WorkloadIdentity

    server, _ = ca.issue(KERNEL)
    victim, _ = ca.issue(DALEOBANKS)
    attacker_ca = CertificateAuthority(common_name="Attacker CA")
    attacker, _ = attacker_ca.issue(DALEOBANKS)

    # The attacker replays the victim's public certificate, but can only pair it
    # with a key they actually hold.
    replayed = WorkloadIdentity(
        spiffe_id=victim.spiffe_id,
        certificate_pem=victim.certificate_pem,
        private_key_pem=attacker.private_key_pem,
        trust_bundle_pem=victim.trust_bundle_pem,
        serial=victim.serial,
    )
    with pytest.raises(IdentityError):
        mutual_tls(replayed, server)
