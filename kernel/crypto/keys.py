"""Ed25519 key management and signatures (via the ``cryptography`` library).

Backs Hard Rule 1 (witness verification) and the approval / grant / witness /
receipt signature chain. ``verify`` NEVER raises: any error (bad signature,
malformed hex, wrong key) returns False — verification fails closed
(Hard Rule 4).
"""
from __future__ import annotations

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)


def generate_private_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


def private_key_to_hex(sk: Ed25519PrivateKey) -> str:
    return sk.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()).hex()


def public_key_to_hex(pk: Ed25519PublicKey) -> str:
    return pk.public_bytes(Encoding.Raw, PublicFormat.Raw).hex()


def private_key_from_hex(h: str) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(h))


def public_key_from_hex(h: str) -> Ed25519PublicKey:
    return Ed25519PublicKey.from_public_bytes(bytes.fromhex(h))


def sign(sk: Ed25519PrivateKey, message: bytes) -> str:
    """Return the hex-encoded Ed25519 signature over ``message``."""
    return sk.sign(message).hex()


def verify(pk: Ed25519PublicKey, message: bytes, signature_hex: str) -> bool:
    """Fail-closed verification: returns False on ANY error, never raises."""
    try:
        pk.verify(bytes.fromhex(signature_hex), message)
        return True
    except (InvalidSignature, ValueError):
        return False
