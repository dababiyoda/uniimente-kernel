"""Append-only hash-chained institutional spine — Hard Rule 4.

The spine exposes append(), get(), verify_chain() and iter() ONLY. There is no
update or delete API: history cannot be rewritten, and any tampering with the
segment file is detected by verify_chain().
"""
from .log import GENESIS_HASH, SEGMENT_NAME, Spine, SpineError
from .merkle import merkle_root, seal_day

__all__ = ["GENESIS_HASH", "SEGMENT_NAME", "Spine", "SpineError", "merkle_root", "seal_day"]
