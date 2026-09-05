"""Temporary organ and organization design under explicit human/Gate authority."""

from .engine import (
    ActivationProposal,
    CapabilityBinding,
    GateActivationReceipt,
    OmnimorphEngine,
    OrganManifest,
    RatificationRecord,
    RetirementRecord,
    SimulationReport,
)
from .mission_compiler import (
    MissionCompilationError,
    MissionCompilationResult,
    MissionCompiler,
)
from .organization_compiler import (
    COMPILER_VERSION,
    CompilationResult,
    OrganizationCompilationError,
    OrganizationCompiler,
    content_digest,
)

__all__ = [
    "ActivationProposal", "CapabilityBinding", "GateActivationReceipt",
    "OmnimorphEngine", "OrganManifest", "RatificationRecord",
    "RetirementRecord", "SimulationReport", "COMPILER_VERSION",
    "CompilationResult", "OrganizationCompilationError",
    "OrganizationCompiler", "content_digest",
    "MissionCompilationError", "MissionCompilationResult", "MissionCompiler",
]