"""Reality Compiler primitives for governed proof-to-consequence workflows."""

from .ivio import (
    CANONICALIZATION_PROFILE,
    CompileError,
    bind_integrity,
    canonical_json_bytes,
    compile_instruction,
    content_digest,
    verify_integrity,
)

__all__ = [
    "CANONICALIZATION_PROFILE",
    "CompileError",
    "bind_integrity",
    "canonical_json_bytes",
    "compile_instruction",
    "content_digest",
    "verify_integrity",
]
