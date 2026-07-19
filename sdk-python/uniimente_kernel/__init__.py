"""UNIIMENTE Kernel Python SDK.

Organ integration surface: shared governance modules extracted from organ
repositories (starting with DALEOBANKS) and generalized behind stable,
organ-agnostic APIs. Organs import these; they do not own governance locally.
"""

from uniimente_kernel.approval_queue import (
    ApprovalQueue,
    ApprovalRecord,
    ApprovalStore,
    InMemoryApprovalStore,
)
from uniimente_kernel.capability import (
    CapabilityError,
    CapabilityService,
    GrantRecord,
    GrantStore,
    InMemoryGrantStore,
)
from uniimente_kernel.commit_witness import (
    CommitReceipt,
    CommitWitness,
    PostconditionResult,
    action_fingerprint,
)
from uniimente_kernel.constitution_check import (
    DEFAULT_CONSTITUTION_PATHS,
    ConstitutionGuard,
)
from uniimente_kernel import contracts
from uniimente_kernel.context_packet import (
    ContextPacketData,
    build_packet,
)
from uniimente_kernel.evolution import (
    BRANCH_ARCHETYPES,
    CLOSURE_STATES,
    ClosureController,
    EvolutionCapsule,
    EvolutionError,
    ExperimentSpec,
    RetainRegressKillDecision,
    SpiderWebAudit,
    StrategyBranch,
    StrategyTree,
    VerifierRecord,
)
from uniimente_kernel.events import (
    Event,
    EventSpine,
    EventValidationError,
    validate_event_dict,
)
from uniimente_kernel.evolution_loop import (
    BranchCandidate,
    BranchGenerator,
    EvolutionLoop,
    FAILURE_CLASSES,
    FailureAnalyzer,
    FailureRecord,
    ImprovementProposal,
    IsolatedResult,
    IsolatedRunner,
    OutcomeComparator,
)
from uniimente_kernel.gate import (
    VALIDATION_STATUSES,
    ConsequenceGate,
    GateError,
    GateResult,
)
from uniimente_kernel.heartbeat import Heartbeat
from uniimente_kernel.ledger import (
    DecisionLedger,
    KillSwitch,
    RateGovernor,
    default_ledger_path,
)
from uniimente_kernel.prompt_firewall import PromptFirewall
from uniimente_kernel.raw_vault import RawVault

__all__ = [
    "ApprovalQueue",
    "ApprovalRecord",
    "ApprovalStore",
    "BranchCandidate",
    "BranchGenerator",
    "CapabilityError",
    "CommitReceipt",
    "CommitWitness",
    "CapabilityService",
    "ConsequenceGate",
    "ConstitutionGuard",
    "ContextPacketData",
    "DEFAULT_CONSTITUTION_PATHS",
    "DecisionLedger",
    "BRANCH_ARCHETYPES",
    "CLOSURE_STATES",
    "ClosureController",
    "Event",
    "EventSpine",
    "EventValidationError",
    "EvolutionCapsule",
    "EvolutionError",
    "EvolutionLoop",
    "ExperimentSpec",
    "FAILURE_CLASSES",
    "FailureAnalyzer",
    "FailureRecord",
    "GateError",
    "GateResult",
    "GrantRecord",
    "GrantStore",
    "Heartbeat",
    "ImprovementProposal",
    "InMemoryApprovalStore",
    "InMemoryGrantStore",
    "IsolatedResult",
    "IsolatedRunner",
    "KillSwitch",
    "OutcomeComparator",
    "PostconditionResult",
    "PromptFirewall",
    "VALIDATION_STATUSES",
    "VerifierRecord",
    "RateGovernor",
    "RetainRegressKillDecision",
    "RawVault",
    "SpiderWebAudit",
    "StrategyBranch",
    "StrategyTree",
    "action_fingerprint",
    "build_packet",
    "contracts",
    "default_ledger_path",
    "validate_event_dict",
]

__version__ = "0.10.0"
