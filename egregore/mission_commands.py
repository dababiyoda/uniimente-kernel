"""Reserved command boundary: CMC-002 does not authorize runtime execution.

Manual direction records belong to governance evidence, not to this boundary.
There is deliberately no accepted command path, claimed-signature verifier,
operator-name shortcut, authority issuer or flag that enables execution.
"""
from events.task_fabric import AuthorityViolation


def refuse_runtime_command(command: object) -> None:
    """Fail closed even if a caller supplies a valid record or claims a signature."""
    raise AuthorityViolation(
        "NEEDS_FOUNDER_DECISION: runtime commands are not admitted; manual chat "
        "direction is artifact-only and is not cryptographic authentication"
    )
