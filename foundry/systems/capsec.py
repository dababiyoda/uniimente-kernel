"""#8 Operating-system capability security: one grant, one proposal, nothing else.

Exercised on the Kernel's Consequence Gate (see foundry/systems/gate.py): a
grant issued for one action cannot be presented for another target, a larger
cost, a second use or after revocation. GREG's own light cones apply the same
rule to missions (tests/unit/test_foundry_systems.py covers both).
"""
from foundry.systems.gate import capability_security

QUERY_OPS = {"demonstrate": lambda a, r: capability_security()}
APPLY_OPS: dict = {}


def exercise(root) -> dict:
    return capability_security()
