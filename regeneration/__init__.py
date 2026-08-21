"""Governed functional regeneration.

Function identity that outlives organs, obligations that survive replacement,
and authority that never does.
"""
from .function import (FunctionContract, FunctionRegistry, Obligation,
                       ObligationState, OrganIncarnation, RegenerationError)
from .succession import (CandidateFormer, CandidateForm, CapabilityPool,
                         Deficit, SuccessionOutcome, succeed)

__all__ = ["FunctionContract", "FunctionRegistry", "Obligation",
           "ObligationState", "OrganIncarnation", "RegenerationError",
           "CandidateFormer", "CandidateForm", "CapabilityPool", "Deficit",
           "SuccessionOutcome", "succeed"]
