"""Append-only hash-chained institutional spine — Hard Rule 4.

The spine exposes append(), get(), verify_chain() and iter() ONLY. There is no
update or delete API: history cannot be rewritten, and any tampering with the
segment file is detected by verify_chain().
"""
from .log import GENESIS_HASH, SEGMENT_NAME, Spine, SpineError
from .merkle import merkle_root, seal_day


def __getattr__(name: str):
    # Lazy guard (SPEC-WP04 3.3): `from kernel.spine import PostgresSpine`
    # works without psycopg installed; missing driver fails only on
    # PostgresSpine instantiation, not on import.
    if name == "PostgresSpine":
        from .pg import PostgresSpine

        return PostgresSpine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "GENESIS_HASH",
    "SEGMENT_NAME",
    "PostgresSpine",
    "Spine",
    "SpineError",
    "merkle_root",
    "seal_day",
]
