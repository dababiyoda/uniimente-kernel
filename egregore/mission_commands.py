"""Reserved command boundary: CMC-002 does not authorize runtime execution.

Manual direction records belong to governance evidence, not to this boundary.
There is deliberately no accepted command path, claimed-signature verifier,
operator-name shortcut, authority issuer or flag that enables execution.
"""
from events.task_fabric import AuthorityViolation


def refuse_runtime_command(command: object) -> None:
    """Fail closed even if a caller supplies a valid record or claims a signature."""
    # Compatibility source/owner: egregore.cathedral_runtime.FounderCommandSurface.
    # Expiry: CMC-EXP-001 migrates. Removal: no remaining legacy callers.
    # No second policy decision; preserve the historical exception type only.
    from egregore.cathedral_runtime import FounderCommandSurface, FounderAuthenticationRequired
    try:
        FounderCommandSurface().submit(command)
    except FounderAuthenticationRequired as exc:
        raise AuthorityViolation("NEEDS_FOUNDER_DECISION: " + str(exc)) from exc
