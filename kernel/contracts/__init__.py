"""Contract registry — all 31 frozen constitutional contracts + 2 sub-records.

Every contract derives from KernelModel (frozen, extra-forbid) so that unknown
or ambiguous data can never silently pass through the kernel
(Hard Rule 4: fail closed on any ambiguity).

WP-05 added the eight Phase 2 evolution contracts (``evolution.py``) plus the
AuditFinding sub-record (a finding type, not a standalone contract).
WP-06 added the three Phase 3 fast-evolution contracts (ComparisonReport,
FailureAnalysis, ImprovementProposal) plus the ComparisonEntry sub-record.
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
from .evolution import (
    AuditFinding,
    ClosureLoop,
    ComparisonEntry,
    ComparisonReport,
    EvolutionCapsule,
    ExperimentSpec,
    FailureAnalysis,
    ImprovementProposal,
    RetainRegressKillDecision,
    SpiderWebAudit,
    StrategyBranch,
    StrategyTree,
    VerifierRecord,
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
    StrategyBranch,
    StrategyTree,
    SpiderWebAudit,
    ExperimentSpec,
    VerifierRecord,
    RetainRegressKillDecision,
    ClosureLoop,
    EvolutionCapsule,
    ComparisonReport,
    FailureAnalysis,
    ImprovementProposal,
]

CONTRACTS: dict[str, type[KernelModel]] = {cls.__name__: cls for cls in _CONTRACT_CLASSES}

__all__ = ["KernelModel", "CONTRACTS", "AuditFinding", "ComparisonEntry"] + [
    cls.__name__ for cls in _CONTRACT_CLASSES
]
