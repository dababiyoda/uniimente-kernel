"""Track B — the morphogenetic runtime.

Separate from the institutional capability track by construction. Nothing in
this package may import from the Kernel's policy, authority, capital, or
provenance modules, and nothing here may produce an external effect. Track B
is permitted to be ungoverned precisely because it is inert.

See docs/DEVELOPMENTAL_TRACK.md for the two-track architecture and the
convergence gate.
"""

from . import cell, grn, substrate

__all__ = ["cell", "grn", "substrate"]
