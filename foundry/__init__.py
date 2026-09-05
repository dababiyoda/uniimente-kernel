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
# The pipeline depends on OMNIMORPH, whose engine consumes Foundry primitives.
# Resolve only these facade exports on demand so a fresh import of the pure
# organization compiler does not enter a partially initialized package cycle.
# Canonical source/owner: foundry.pipeline. Remove this lazy facade only if that
# dependency cycle is removed while the public exports remain compatible.
def __getattr__(name):
    if name in {"FoundryPipeline", "PipelineRun", "PipelineStatus"}:
        from . import pipeline
        value = getattr(pipeline, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

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
