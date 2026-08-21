"""Signing providers. ISSUER DISTRIBUTION ONLY.

This module ships in `uniimente-aperture-issuer` and NOT in
`uniimente-aperture-client`. An organ that installs verification support does
not receive the ability to sign, because these bytes are not in its wheel.

That is the point of the two-distribution geometry: authority leakage is
prevented by the package boundary, not by a runtime check that could be
bypassed or a naming convention that could be ignored.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding, NoEncryption, PrivateFormat, PublicFormat)

from aperture.certificate import CertificateError
from aperture.verification import (EnvironmentRefusal, EPHEMERAL_ALLOWED,
                                   PRODUCTION, TEST, current_environment)


class SigningUnavailable(CertificateError):
    """No usable signing key. Fails closed - never degrades to unsigned."""


# Signing side - held by the canonical issuer alone
# --------------------------------------------------------------------------

class SigningProvider(ABC):
    """Interface for whatever holds a private key. The Kernel never sees bytes."""

    @property
    @abstractmethod
    def key_id(self) -> str: ...

    @property
    @abstractmethod
    def algorithm(self) -> str: ...

    @abstractmethod
    def sign(self, message: bytes) -> str: ...

    @abstractmethod
    def public_key_hex(self) -> str: ...


class Ed25519SigningProvider(SigningProvider):
    """In-process Ed25519 signer.

    Suitable for tests and for deployments where in-process custody is an
    accepted risk. Production custody belongs behind an HSM or KMS
    implementation of the same interface.
    """

    def __init__(self, private_key: Ed25519PrivateKey, key_id: str,
                 environment: str = TEST):
        if environment == PRODUCTION:
            raise EnvironmentRefusal(
                "PRODUCTION key custody is disabled in this pass. It requires "
                "separate founder authorization plus custody, rotation, "
                "revocation, backup, recovery and compromise procedures. See "
                "docs/authority/KEY_CUSTODY_READINESS.md.",
                code="production_custody_disabled")
        self._sk = private_key
        self._key_id = key_id
        self.environment = environment

    @classmethod
    def generate(cls, key_id: str, environment: str = TEST
                 ) -> "Ed25519SigningProvider":
        """Ephemeral in-process key. Permitted only in TEST and DEVELOPMENT.

        SHADOW deliberately refuses: a shadow run must use an auditable key
        identifier so its signatures can be traced afterwards. An ephemeral key
        that vanishes when the process exits cannot be audited.
        """
        if environment not in EPHEMERAL_ALLOWED:
            raise EnvironmentRefusal(
                f"ephemeral generated keys are not permitted in {environment}; "
                f"allowed only in {sorted(EPHEMERAL_ALLOWED)}. Load an "
                "auditable key via from_env() instead.",
                code="ephemeral_key_refused")
        return cls(Ed25519PrivateKey.generate(), key_id, environment)

    @classmethod
    def from_env(cls, var: str = "UNIIMENTE_APERTURE_SIGNING_KEY_HEX",
                 key_id_var: str = "UNIIMENTE_APERTURE_KEY_ID") -> "Ed25519SigningProvider":
        """Load from the environment. Absent key is a hard refusal.

        There is deliberately no development fallback key. A build that cannot
        find a signing key must not be able to authorize anything.
        """
        env = current_environment()
        if env == PRODUCTION:
            raise EnvironmentRefusal(
                "PRODUCTION key custody is disabled in this pass; see "
                "docs/authority/KEY_CUSTODY_READINESS.md.",
                code="production_custody_disabled")
        raw = os.environ.get(var)
        if not raw:
            raise SigningUnavailable(
                f"{var} is not set; the aperture refuses to sign. There is no "
                "development fallback key by design.", code="signing_unavailable")
        key_id = os.environ.get(key_id_var)
        if not key_id:
            raise SigningUnavailable(
                f"{key_id_var} is required so that receipts name the key that "
                "signed them.", code="signing_unavailable")
        # A key marked as a test key must never load outside TEST. Otherwise a
        # deterministic fixture key could silently become a shadow signer.
        if key_id.startswith("test-") and env != TEST:
            raise EnvironmentRefusal(
                f"key_id {key_id!r} is a test key and cannot load in {env}",
                code="test_key_outside_test")
        try:
            sk = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(raw))
        except (ValueError, TypeError) as e:
            raise SigningUnavailable(f"unusable signing key: {e}",
                                     code="signing_unavailable") from None
        return cls(sk, key_id, env)

    @property
    def key_id(self) -> str:
        return self._key_id

    @property
    def algorithm(self) -> str:
        return "ed25519"

    def sign(self, message: bytes) -> str:
        return self._sk.sign(message).hex()

    def public_key_hex(self) -> str:
        return self._sk.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw).hex()

    def private_key_hex(self) -> str:
        """Test and provisioning use only. Never logged, never serialized into
        a certificate, never written to the repository."""
        return self._sk.private_bytes(
            Encoding.Raw, PrivateFormat.Raw, NoEncryption()).hex()


