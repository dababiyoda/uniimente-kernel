"""UNIIMENTE developmental substrate: bounded-local digital cells.

Generates candidate forms. Cannot authorize them. Cannot ratify itself.
"""
from .cell import Cell, CellView, Interface, Signal, Tri, signature
from .tissue import Tissue, TissueStats

__all__ = ["Cell", "CellView", "Interface", "Signal", "Tri", "signature",
           "Tissue", "TissueStats"]
from .causal import (CausalMotif, CausalRejectionCertificate, FailureSignature,
                     causal_escape, certificate_for, local_inhibition_from,
                     signature_from_failure, FAILURE_CLASSES)
__all__ += ["CausalMotif", "CausalRejectionCertificate", "FailureSignature",
            "causal_escape", "certificate_for", "local_inhibition_from",
            "signature_from_failure", "FAILURE_CLASSES"]
