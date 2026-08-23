"""Refusals, named separately so a caller cannot catch them by accident.

Every one of these is a *closed* failure: the handshake produced no peer
identity and the caller has nothing to proceed with. There is deliberately no
"degraded" or "unverified" outcome — a peer is identified or it is not, and an
intermediate state is the thing that turns into an accidental downgrade path six
months later.
"""
from __future__ import annotations


class IdentityError(PermissionError):
    """Base: identity could not be established. Nothing may proceed on it.

    Subclasses `PermissionError` so a caller that blanket-catches permission
    failures cannot mistake an unverified peer for a verified one.
    """


class UntrustedIssuer(IdentityError):
    """The peer presented a certificate this trust bundle does not anchor.

    Covers self-signed certificates and certificates from a different CA — the
    two most obvious impersonation attempts.
    """


class CertificateExpired(IdentityError):
    """The peer's certificate is outside its validity window.

    Expiry is the mechanism that makes rotation meaningful. A PKI that issued
    certificates without it would be distributing bearer tokens with extra
    steps.
    """


class CertificateRevoked(IdentityError):
    """The certificate is anchored and unexpired, but its serial is revoked.

    The case expiry alone cannot handle: a key believed compromised before its
    natural end. Checked *after* chain validation, so a revoked-and-untrusted
    certificate reports the more fundamental failure.
    """


class HandshakeRefused(IdentityError):
    """The TLS exchange failed, or a party declined to present a certificate.

    Notably raised when a peer completes a handshake without offering a client
    certificate: one-way TLS is not mutual TLS, and accepting it would silently
    return the institution to "whoever is talking says who they are".
    """
