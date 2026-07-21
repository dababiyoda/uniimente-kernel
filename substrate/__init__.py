"""UNIIMENTE digital developmental substrate.

This package does not reproduce tutorial products. It extracts mechanism-level
patterns, mutates their institutional meaning, and recombines them into bounded,
non-executing developmental plans governed by the Kernel.
"""

from .anatomy import (
    AnatomyError,
    BuildDecision,
    MechanismPrimitive,
    MechanismRegistry,
    MutationSpec,
)
from .catalog import default_mutations, default_primitives, default_registry
from .development import (
    CandidateOrganManifest,
    DevelopmentError,
    DevelopmentLedger,
    DevelopmentRequest,
    DevelopmentalSubstrate,
    ReconfigurationProposal,
)

__all__ = [
    "AnatomyError",
    "BuildDecision",
    "MechanismPrimitive",
    "MechanismRegistry",
    "MutationSpec",
    "default_mutations",
    "default_primitives",
    "default_registry",
    "CandidateOrganManifest",
    "DevelopmentError",
    "DevelopmentLedger",
    "DevelopmentRequest",
    "DevelopmentalSubstrate",
    "ReconfigurationProposal",
]
