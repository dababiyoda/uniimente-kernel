"""Governed mechanical-organism primitives for UNIIMENTE.

The package makes persistence, daily cognition, and bounded replication explicit
without treating the institution as conscious or allowing it to self-authorize.
"""

from organism.daily import (
    ActionProposal,
    DailyBrief,
    DailyOrganismPlanner,
    OutcomeObservation,
    Signal,
    daily_organism_pattern,
)
from organism.media import (
    AccountCreationIntent,
    ContentIntent,
    ContentRegistry,
    MediaPropertyCharter,
    MediaPropertyFactory,
    MediaPropertyStatus,
    ReplicationEvidence,
)

__all__ = [
    "AccountCreationIntent",
    "ActionProposal",
    "ContentIntent",
    "ContentRegistry",
    "DailyBrief",
    "DailyOrganismPlanner",
    "MediaPropertyCharter",
    "MediaPropertyFactory",
    "MediaPropertyStatus",
    "OutcomeObservation",
    "ReplicationEvidence",
    "Signal",
    "daily_organism_pattern",
]
