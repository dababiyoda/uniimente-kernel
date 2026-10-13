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
from .parts import PartSpec, PartsBoard
from .model_parts import local_draft_part
from .genesis import CapabilityDeficit, CapabilityGenesis, CaseState, DeficitDetector, LADDER, diagnose
from .failures import CapabilityMissing, DoctrinalRefusal

__all__ = [
    "Assessment",
    "CandidateProposal",
    "CapabilityDeficit",
    "CapabilityMissing",
    "CapabilityGenesis",
    "CaseState",
    "ChangeProposal",
    "CognitionCycle",
    "ContractError",
    "CycleStatus",
    "DeficitDetector",
    "DoctrinalRefusal",
    "IntegrityConflict",
    "LADDER",
    "PartSpec",
    "PartsBoard",
    "ResourceExhausted",
    "ResourceGovernor",
    "ResourceMode",
    "SignalEnvelope",
    "StandingCognitionRuntime",
    "diagnose",
    "local_draft_part",
]
