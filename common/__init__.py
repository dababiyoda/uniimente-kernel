"""Small shared primitives used by non-boundary Kernel modules.

This package exists so that one definition answers "what is the canonical
hash of this value?" and "what time is it, in UTC?" instead of a dozen local
copies drifting apart. It holds mechanics only: no policy, no authority, no
state. See ``common/README.md`` for what deliberately does *not* use it.
"""

from .canonical import canonical_json, is_sha256_ref, sha256_ref
from .clock import utc_now, utc_now_iso

__all__ = ["canonical_json", "is_sha256_ref", "sha256_ref", "utc_now", "utc_now_iso"]
