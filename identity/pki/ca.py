"""One internal root, issuing one independent keypair per workload.

The CA's only job is to bind a SPIFFE ID to a public key for a bounded time.
It does not know what any workload is allowed to do, and it has no way to
express that — there is no extension here for capability, budget or role, by
design rather than by omission.

## Why the SPIFFE ID lives in a URI SAN

The identity has to be somewhere a TLS peer will actually validate. Putting it
in the Common Name would be the easy mistake: CN is free text, browsers stopped
trusting it for identity a decade ago, and nothing in the chain validation path
constrains it. A `UniformResourceIdentifier` SAN is validated as part of the
certificate and is where SPIFFE specifies workload identity belongs, so
`identity/service-identities.yaml` maps onto it unchanged.

## Rotation

`issue()` always generates a fresh keypair. Rotating is therefore just issuing
again for the same SPIFFE ID and revoking the old serial; there is no "renew"
that preserves a key, because a rotation that keeps the private key does not
recover from the compromise that motivated it.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

#: The namespace declared in `identity/service-identities.yaml`. Preserved
#: exactly, per the ruling: the existing SPIFFE-style namespace stays useful.
TRUST_DOMAIN = "spiffe://uniimente.internal"

#: Deliberately short. A certificate is a statement about the present, and a
#: long-lived one is the shared bearer token this work exists to retire —
#: `service-identities.yaml` already says `rotation: short_lived_documents`.
DEFAULT_LIFETIME = datetime.timedelta(hours=24)

#: Small backdate so a workload whose clock trails the CA's by a second does not
#: reject a certificate issued moments ago. Bounded tightly: this is a clock-skew
#: allowance, not a grace period, and widening it would weaken expiry itself.
_CLOCK_SKEW = datetime.timedelta(minutes=1)


@dataclass(frozen=True)
class IssuedIdentity:
    """A certificate the CA has issued, with the serial needed to revoke it."""

    spiffe_id: str
    serial: int
    not_before: datetime.datetime
    not_after: datetime.datetime


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class CertificateAuthority:
    """A self-signed root that issues per-workload leaf certificates.

    One root, no intermediates. An intermediate exists to limit blast radius
    when a signing key is delegated to a separate operator, and this CA is not
    delegated to anyone — adding the layer would add ceremony without adding a
    boundary.
    """

    def __init__(self, *, common_name: str = "UNIIMENTE Internal CA",
                 lifetime: datetime.timedelta = datetime.timedelta(days=365)):
        self._key = ec.generate_private_key(ec.SECP256R1())
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
        now = _now()
        self._cert = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(self._key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - _CLOCK_SKEW)
            .not_valid_after(now + lifetime)
            # path_length=0: this root may sign leaves and may not mint another
            # CA. A workload certificate that could issue certificates would be
            # a workload that can manufacture peers.
            .add_extension(x509.BasicConstraints(ca=True, path_length=0),
                           critical=True)
            .add_extension(x509.KeyUsage(
                digital_signature=True, content_commitment=False,
                key_encipherment=False, data_encipherment=False,
                key_agreement=False, key_cert_sign=True, crl_sign=True,
                encipher_only=False, decipher_only=False), critical=True)
            .sign(self._key, hashes.SHA256())
        )

    @property
    def trust_bundle(self) -> bytes:
        """The PEM a peer needs to verify certificates from this CA.

        Public material only. Handing someone the trust bundle lets them
        *verify*; it never lets them *sign*. That asymmetry is the entire
        improvement over the shared HMAC key, where verifying and signing were
        the same capability.
        """
        return self._cert.public_bytes(serialization.Encoding.PEM)

    def issue(self, spiffe_id: str, *,
              lifetime: datetime.timedelta = DEFAULT_LIFETIME,
              not_before: datetime.datetime | None = None,
              ) -> tuple["WorkloadIdentity", IssuedIdentity]:  # noqa: F821
        """Mint a fresh keypair and a certificate binding it to `spiffe_id`.

        `not_before` is exposed so tests can construct an already-expired
        certificate honestly, by issuing one whose window is in the past, rather
        than by monkeypatching a clock. A test that fakes time proves the fake
        works; this one proves the validation does.
        """
        from identity.pki.workload import WorkloadIdentity

        if not spiffe_id.startswith(TRUST_DOMAIN + "/"):
            raise ValueError(
                f"{spiffe_id!r} is outside the trust domain {TRUST_DOMAIN}. The "
                "CA does not issue for namespaces it does not anchor."
            )

        key = ec.generate_private_key(ec.SECP256R1())
        start = (not_before or _now()) - _CLOCK_SKEW
        end = start + _CLOCK_SKEW + lifetime
        serial = x509.random_serial_number()

        cert = (
            x509.CertificateBuilder()
            .subject_name(x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME,
                                   spiffe_id.rsplit("/", 1)[-1])]))
            .issuer_name(self._cert.subject)
            .public_key(key.public_key())
            .serial_number(serial)
            .not_valid_before(start)
            .not_valid_after(end)
            # The identity itself. Critical, so a validator that does not
            # understand SANs must reject rather than ignore it.
            .add_extension(x509.SubjectAlternativeName(
                [x509.UniformResourceIdentifier(spiffe_id)]), critical=True)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None),
                           critical=True)
            # Both roles: in a mutual handshake each workload is a server on one
            # side and a client on the other, and an organ is not intrinsically
            # one or the other.
            .add_extension(x509.ExtendedKeyUsage([
                ExtendedKeyUsageOID.SERVER_AUTH,
                ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
            .sign(self._key, hashes.SHA256())
        )

        identity = WorkloadIdentity(
            spiffe_id=spiffe_id,
            certificate_pem=cert.public_bytes(serialization.Encoding.PEM),
            private_key_pem=key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption()),
            trust_bundle_pem=self.trust_bundle,
            serial=serial,
        )
        return identity, IssuedIdentity(
            spiffe_id=spiffe_id, serial=serial,
            not_before=cert.not_valid_before_utc,
            not_after=cert.not_valid_after_utc)
