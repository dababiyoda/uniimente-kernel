"""Bounded standing cognition for the UNIIMENTE kernel.

The package deliberately owns no executor, wallet, publisher, credential, or
legal identity.  It turns evidence into proposals; the kernel's Consequence
Gate remains the only path from a proposal to an external effect.
"""

from .contracts import (
    Assessment,
    CandidateProposal,
    ChangeProposal,
    ContractError,
    IntegrityConflict,
    SignalEnvelope,
)
from .resources import ResourceExhausted, ResourceGovernor, ResourceMode
from .runtime import CognitionCycle, CycleStatus, StandingCognitionRuntime

__all__ = [
    "Assessment",
    "CandidateProposal",
    "ChangeProposal",
    "CognitionCycle",
    "ContractError",
    "CycleStatus",
    "IntegrityConflict",
    "ResourceExhausted",
    "ResourceGovernor",
    "ResourceMode",
    "SignalEnvelope",
    "StandingCognitionRuntime",
]
