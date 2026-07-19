"""UCL Constitutional Compiler (WP-02).

Turns the five real ``constitution/*.ucl`` files from dead text into the
gate's ``policy_fn``: parse UCL (lexer + recursive-descent parser, no
third-party parser libraries), build the semantic Constitution model, and
compile a callable compatible with ``kernel.gate.pipeline.Gate(policy_fn=...)``.

Governing clauses enforced by this package (see module docstrings for the
full citations): the kernel_invariant (refuse_and_escalate on any violation —
fail closed), permanent_prohibitions.non_delegable (self-amendment
protection), participant_rights hard_refusal rights (rank 1), the
safety_states ladder (shutdown is an authorized state transition), and
doctrine.humans_authorize (C0/C1 PERMIT, C2-C4 REQUIRE_HUMAN, C5 DENY).
"""
from .ast import Block
from .compiler import compile_policy_fn
from .lexer import Token, UCLError, lex
from .model import Constitution
from .parser import Document, Parser, parse, parse_file
from .version import (
    canonical_file_set,
    constitution_version,
    constitution_version_from_dir,
    policy_version,
)

__all__ = [
    "Block",
    "Constitution",
    "Document",
    "Parser",
    "Token",
    "UCLError",
    "canonical_file_set",
    "compile_policy_fn",
    "constitution_version",
    "constitution_version_from_dir",
    "lex",
    "parse",
    "parse_file",
    "policy_version",
]
