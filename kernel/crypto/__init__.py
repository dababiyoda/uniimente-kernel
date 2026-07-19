"""Crypto primitives — Ed25519 signatures and canonical-JSON hashing.

Backs Hard Rules 1, 2 and 5: every signature verification fails closed
(returns False on any error) and every hash is computed over canonical JSON
(sorted keys, no whitespace) for byte-identical determinism.
"""
from .hashing import canonical_json, content_hash, sha256_hex
from .keys import (
    generate_private_key,
    private_key_from_hex,
    private_key_to_hex,
    public_key_from_hex,
    public_key_to_hex,
    sign,
    verify,
)

__all__ = [
    "canonical_json",
    "content_hash",
    "sha256_hex",
    "generate_private_key",
    "private_key_from_hex",
    "private_key_to_hex",
    "public_key_from_hex",
    "public_key_to_hex",
    "sign",
    "verify",
]
