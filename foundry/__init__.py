"""Evidence-governed media, strategy, composition, and validation Foundry."""

from .company import (
    CompanyFoundry,
    FoundryError,
    MediaCompany,
    MediaCompanyCharter,
    REQUIRED_EDITORIAL_RULES,
)
from .distribution import DistributionLoop, DistributionWindow, USEFUL_ACTIONS
from .territory import ContentNode, TerritoryError, TerritoryGraph
from .arsenal import ARSENAL, TechnologySpec, by_surface, technology
from .composition import (
    AttachmentStep,
    CompositionPlan,
    CompositionRefused,
    CompositionRequest,
    EvidenceExperiment,
    FoundryComposer,
)
from .evidence_rank import (
    TechnologyEvidence,
    UnknownTechnology,
    evidence_table,
    selection_rank,
)
from .advantage import (
    AdvantageArchitecture,
    AdvantageFoundry,
    AdvantageRefused,
    CapabilityNeed,
    ClosureState,
    ExternalOutcome,
    OpportunitySpec,
    SealedAdvantageGenome,
    StrategyBranch,
    STRATEGY_ROUTES,
)
from .tribunal import (
    CONTROL_SUPER_NODES,
    TRIBUNAL_LENSES,
    SpiderWebTribunal,
    TribunalFinding,
    TribunalJudgment,
    TribunalReport,
    TribunalVerdict,
)
from .intake import FoundryIntakeSupplement, opportunity_from_canonical
from .outcome_bridge import ReconciliationPacket, external_outcome_from_case
from .pipeline import FoundryPipeline, PipelineRun, PipelineStatus

__all__ = [
    "CompanyFoundry", "FoundryError", "MediaCompany", "MediaCompanyCharter",
    "REQUIRED_EDITORIAL_RULES", "DistributionLoop", "DistributionWindow",
    "USEFUL_ACTIONS", "ContentNode", "TerritoryError", "TerritoryGraph",
    "ARSENAL", "TechnologySpec", "by_surface", "technology",
    "AttachmentStep", "CompositionPlan", "CompositionRefused",
    "CompositionRequest", "EvidenceExperiment", "FoundryComposer",
    "TechnologyEvidence", "UnknownTechnology", "evidence_table", "selection_rank",
    "AdvantageArchitecture", "AdvantageFoundry", "AdvantageRefused",
    "CapabilityNeed", "ClosureState", "ExternalOutcome", "OpportunitySpec",
    "SealedAdvantageGenome", "StrategyBranch", "STRATEGY_ROUTES",
    "CONTROL_SUPER_NODES", "TRIBUNAL_LENSES", "SpiderWebTribunal",
    "TribunalFinding", "TribunalJudgment", "TribunalReport", "TribunalVerdict",
    "FoundryIntakeSupplement", "opportunity_from_canonical",
    "ReconciliationPacket", "external_outcome_from_case",
    "FoundryPipeline", "PipelineRun", "PipelineStatus",
]
