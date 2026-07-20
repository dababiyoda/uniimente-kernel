"""Asymmetric Advantage Foundry.

The Foundry compiles a market failure into a bounded Advantage Genome. It plans;
it does not execute infrastructure or create external effects. Any execution must
still pass through the Kernel Consequence Gate.
"""

from .arsenal import ARSENAL, TechnologySpec, technology
from .composer import FoundryComposer, FoundryRefused
from .genome import (
    AdvantageGenome,
    AdvantageRequest,
    AttachmentStep,
    EvidenceExperiment,
)

__all__ = [
    "ARSENAL",
    "TechnologySpec",
    "technology",
    "FoundryComposer",
    "FoundryRefused",
    "AdvantageGenome",
    "AdvantageRequest",
    "AttachmentStep",
    "EvidenceExperiment",
]
