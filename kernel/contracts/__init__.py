"""Contract registry — all 20 frozen constitutional contracts.

Every contract derives from KernelModel (frozen, extra-forbid) so that unknown
or ambiguous data can never silently pass through the kernel
(Hard Rule 4: fail closed on any ambiguity).
"""
from .base import KernelModel
from .institutional import ContextPacket, EvidencePacket, InstitutionalEvent
from .venture import OpportunityPacket, VentureAssessment
from .action import (
    ActionIntent,
    ApprovalRecord,
    AutonomyLicense,
    CapabilityGrant,
    PolicyDecision,
)
from .execution import (
    CommitWitness,
    DecisionEpisode,
    ExecutionReceipt,
    OutcomeRecord,
    ReconciliationRecord,
)
from .governance import (
    BusinessGenome,
    IncidentRecord,
    OrganCharter,
    RegenerativeImpactRecord,
    SwarmContract,
)

_CONTRACT_CLASSES = [
    InstitutionalEvent,
    EvidencePacket,
    ContextPacket,
    OpportunityPacket,
    VentureAssessment,
    ActionIntent,
    PolicyDecision,
    ApprovalRecord,
    CapabilityGrant,
    AutonomyLicense,
    CommitWitness,
    ExecutionReceipt,
    ReconciliationRecord,
    OutcomeRecord,
    DecisionEpisode,
    RegenerativeImpactRecord,
    IncidentRecord,
    OrganCharter,
    BusinessGenome,
    SwarmContract,
]

CONTRACTS: dict[str, type[KernelModel]] = {cls.__name__: cls for cls in _CONTRACT_CLASSES}

__all__ = ["KernelModel", "CONTRACTS"] + [cls.__name__ for cls in _CONTRACT_CLASSES]
