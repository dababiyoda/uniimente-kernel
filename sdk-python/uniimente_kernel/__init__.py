"""UNIIMENTE Kernel Python SDK.

Organ integration surface: shared governance modules extracted from organ
repositories (starting with DALEOBANKS) and generalized behind stable,
organ-agnostic APIs. Organs import these; they do not own governance locally.
"""

from uniimente_kernel.capability import (
    CapabilityError,
    CapabilityService,
    GrantRecord,
    GrantStore,
    InMemoryGrantStore,
)
from uniimente_kernel.ledger import (
    DecisionLedger,
    KillSwitch,
    RateGovernor,
    default_ledger_path,
)
from uniimente_kernel.raw_vault import RawVault

__all__ = [
    "CapabilityError",
    "CapabilityService",
    "DecisionLedger",
    "GrantRecord",
    "GrantStore",
    "InMemoryGrantStore",
    "KillSwitch",
    "RateGovernor",
    "RawVault",
    "default_ledger_path",
]

__version__ = "0.2.0"
