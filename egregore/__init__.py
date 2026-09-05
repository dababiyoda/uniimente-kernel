"""Bounded standing cognition and mission metabolism for the UNIIMENTE kernel.

The package owns mission-level reasoning and durable coordination records. It
does not own an executor, wallet, publisher, credential issuer, or legal
identity. The kernel's Consequence Gate remains the only path from a proposal
to an external effect.
"""

from .cathedral_runtime import (
    CathedralMetabolismRuntime,
    DEFAULT_EVALUATOR_IDENTITY,
    FounderAuthenticationRequired,
    FounderCommandSurface,
    MissionAdmission,
    MissionRuntimeError,
    MissionSnapshot,
    SIMULATION_WORKER_PREFIX,
    SOURCE_IDENTITY,
)
from .contracts import (
    Assessment,
    CandidateProposal,
    ChangeProposal,
    ContractError,
    IntegrityConflict,
    SignalEnvelope,
)
from .mission_resolution import (
    MissionResolution,
    MissionResolutionError,
    MissionResolutionRouter,
    ResolutionCandidate,
    ResolutionClass,
)
from .resources import ResourceExhausted, ResourceGovernor, ResourceMode
from .runtime import CognitionCycle, CycleStatus, StandingCognitionRuntime

__all__ = [
    "Assessment",
    "CandidateProposal",
    "CathedralMetabolismRuntime",
    "ChangeProposal",
    "CognitionCycle",
    "ContractError",
    "CycleStatus",
    "DEFAULT_EVALUATOR_IDENTITY",
    "FounderAuthenticationRequired",
    "FounderCommandSurface",
    "IntegrityConflict",
    "MissionAdmission",
    "MissionResolution",
    "MissionResolutionError",
    "MissionResolutionRouter",
    "MissionRuntimeError",
    "MissionSnapshot",
    "ResolutionCandidate",
    "ResolutionClass",
    "ResourceExhausted",
    "ResourceGovernor",
    "ResourceMode",
    "SIMULATION_WORKER_PREFIX",
    "SignalEnvelope",
    "SOURCE_IDENTITY",
    "StandingCognitionRuntime",
]