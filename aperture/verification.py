"""Trust root: the verification-only registry. CLIENT DISTRIBUTION.

The single most important property of this module is a separation that the
previous HMAC design could not express:

    verification capability != signing capability

Under HMAC-SHA256 the verifier recomputes the MAC with the same secret used to
produce it. Anyone able to check a witness is able to forge one. An institution
whose claim is *attributable* autonomy cannot rest attribution on a shared
secret, so the aperture uses asymmetric signatures and hands out public keys
only.

`VerificationRegistry` physically cannot sign: it stores public key bytes and
exposes no signing method. `SigningProvider` is an interface so that the private
key can live in an HSM, a KMS, or a test fixture without the rest of the system
knowing which.

Missing or invalid signing infrastructure fails closed. There is no development
fallback that silently signs with a hardcoded literal - that was a defect in the
previous design and is deliberately not reproduced.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .certificate import CertificateError

SUPPORTED_ALGORITHMS = frozenset({"ed25519"})

# Key custody environments. PRODUCTION is deliberately unreachable in this pass.
TEST = "TEST"
DEVELOPMENT = "DEVELOPMENT"
SHADOW = "SHADOW"
PRODUCTION = "PRODUCTION"
ENVIRONMENTS = (TEST, DEVELOPMENT, SHADOW, PRODUCTION)

ENV_VAR = "UNIIMENTE_APERTURE_ENV"

# Keys generated in-process are ephemeral and institutionally worthless. They
# are permitted only where nothing institutional is at stake.
EPHEMERAL_ALLOWED = frozenset({TEST, DEVELOPMENT})


class EnvironmentRefusal(CertificateError):
    """The requested key does not belong in the requested environment."""


def current_environment() -> str:
    env = os.environ.get(ENV_VAR, TEST)
    if env not in ENVIRONMENTS:
        raise EnvironmentRefusal(
            f"{ENV_VAR}={env!r} is not one of {ENVIRONMENTS}; refusing rather "
            "than guessing which custody rules apply", code="unknown_environment")
    return env


class SigningUnavailable(CertificateError):
    """No usable signing key. Fails closed - never degrades to unsigned."""


class KeyRevoked(CertificateError):
    pass


class UnknownKey(CertificateError):
    pass


class AlgorithmRefused(CertificateError):
    pass


# Verification side - distributable to every organ, effector and auditor
# --------------------------------------------------------------------------

@dataclass
class RegisteredKey:
    key_id: str
    algorithm: str
    public_key_hex: str
    not_before: Optional[str] = None
    revoked_at: Optional[str] = None
    revocation_reason: str = ""
    supersedes: Optional[str] = None


class VerificationRegistry:
    """Public keys only. This class cannot sign and has no method that could.

    Safe to hand to a DALEOBANKS effector, a PumpStation contract deployer, an
    IoT device, or an external auditor. Possession confers the ability to check
    attribution and nothing else.
    """

    def __init__(self) -> None:
        self._keys: dict[str, RegisteredKey] = {}

    def register(self, key_id: str, public_key_hex: str, *,
                 algorithm: str = "ed25519",
                 supersedes: Optional[str] = None) -> RegisteredKey:
        if algorithm not in SUPPORTED_ALGORITHMS:
            raise AlgorithmRefused(f"unsupported algorithm {algorithm!r}",
                                   code="algorithm_refused")
        try:
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
        except (ValueError, TypeError) as e:
            raise UnknownKey(f"unusable public key for {key_id}: {e}",
                             code="unusable_public_key") from None
        rk = RegisteredKey(key_id=key_id, algorithm=algorithm,
                           public_key_hex=public_key_hex, supersedes=supersedes)
        self._keys[key_id] = rk
        return rk

    def revoke(self, key_id: str, *, reason: str) -> None:
        k = self._keys.get(key_id)
        if k is None:
            raise UnknownKey(f"cannot revoke unknown key {key_id!r}",
                             code="unknown_key")
        k.revoked_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        k.revocation_reason = reason

    def get(self, key_id: str) -> RegisteredKey:
        k = self._keys.get(key_id)
        if k is None:
            raise UnknownKey(f"key {key_id!r} is not registered; refusing",
                             code="unknown_key")
        return k

    def verify(self, key_id: str, message: bytes, signature_hex: str,
               *, algorithm: str) -> bool:
        """Fail-closed verification.

        Returns False on any error and never raises for a bad signature. It DOES
        raise for a revoked or unknown key, because those are institutional
        conditions the caller must not confuse with 'the bytes did not match'.
        """
        k = self.get(key_id)
        if k.revoked_at is not None:
            raise KeyRevoked(
                f"key {key_id!r} was revoked at {k.revoked_at} ({k.revocation_reason}); "
                "certificates signed by it cannot authorize a new effect",
                code="key_revoked")
        if algorithm != k.algorithm or algorithm not in SUPPORTED_ALGORITHMS:
            raise AlgorithmRefused(
                f"certificate claims {algorithm!r}, key {key_id!r} is {k.algorithm!r}",
                code="algorithm_mismatch")
        try:
            pk = Ed25519PublicKey.from_public_bytes(bytes.fromhex(k.public_key_hex))
            pk.verify(bytes.fromhex(signature_hex), message)
            return True
        except (InvalidSignature, ValueError, TypeError):
            return False


class SigningUnavailable(CertificateError):
    """Retained for import compatibility. The client cannot sign at all."""
