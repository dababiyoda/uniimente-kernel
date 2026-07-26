"""IVIO-NEMT — a preserved Venture Cell. INACTIVE AND UNATTACHED BY DEFAULT.

UNIIMENTE may create and govern ventures. No venture may define UNIIMENTE.

This package is a Venture Cell, not core. It is preserved as a potentially
connectable venture — not archived as dead history. Nothing here is attached,
activated, or granted authority by import.

BOUNDARY RULES (enforced by tests/unit/test_core_venture_boundary.py):
  - core modules may not import from ventures/
  - this package may import approved core interfaces only
  - it may not define or override Constitution, founder authority, identity
    authority, legal-principal rules, shutdown, the Consequence Gate, core
    memory, or developmental acceptance criteria

ATTACHMENT STATE: unattached. Attaching a Venture Cell requires a bounded
capability grant through the Consequence Gate and is out of scope here.
"""

ACTIVE = False
ATTACHED = False
VENTURE_CELL_ID = "ivio_nemt"          # resolvable in identity/organ-registry.yaml
LEGAL_PRINCIPAL = "IVIO_NEMT_LLC"      # status: proving_ground, jurisdiction unconfirmed

__all__ = ["ACTIVE", "ATTACHED", "VENTURE_CELL_ID", "LEGAL_PRINCIPAL"]
