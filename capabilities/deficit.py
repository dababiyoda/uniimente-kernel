"""A CapabilityDeficit, and what makes one *verified*.

Founder clarification 2026-09-09: `morphogenesis` canonically means
**resourceful functional capability formation or reconfiguration after a
VERIFIED CapabilityDeficit**. The word "verified" is the load-bearing part. A
system that reconfigures itself whenever something merely looks absent is not
resourceful, it is twitchy — and the cheapest way to fake developmental
behavior is to declare a deficit that was never real.

So a deficit is verified only when three independent facts hold, each with
evidence attached:

1. **Required** — something actually depends on the capability. A capability
   nothing needs cannot be missing in any sense that matters; that was exactly
   the defect that disqualified Route A, where a health probe's unhappiness was
   mistaken for a lost function.
2. **Failed** — a concrete invocation was attempted and did not succeed. Not
   "the registry looks empty": something tried and could not.
3. **Unserviceable** — no registered implementation can currently serve it.
   Checked against the router, so a deficit cannot be declared while a healthy
   implementation is sitting there unused.

Missing any one of the three leaves the deficit ``UNVERIFIED``, and
``morphogenesis_authorized()`` is False. There is no override.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

#: The search order the founder made binding on 2026-09-09:
#: "Preserve the intended effect. Do not literalize the metaphor. Search
#: reality before inventing architecture." Cheapest and most-proven first;
#: new architecture last, never first.
RESOLUTION_LADDER = (
    "EXISTING_CAPABILITY",      # already registered and healthy
    "CONVENTIONAL_WORKFLOW",    # the boring durable-runtime answer
    "COMMODITY_OR_EXTERNAL",    # open source, API, CLI tool, computer use
    "MECHANISM_RECOMBINATION",  # compose from registered Capability Genomes
    "NEW_ARCHITECTURE",         # build something that does not exist yet
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class CapabilityDeficit:
    """A claim that a capability is missing, and the evidence for it."""

    capability: str
    #: What depends on it. A mission id, workflow id, or consumer name — never
    #: a bare assertion that it "should" exist.
    required_by: str = ""
    #: The invocation that actually failed, and how.
    failed_invocation: str = ""
    failure_error: str = ""
    #: Implementations the router examined, and why each could not serve.
    examined: tuple[str, ...] = ()
    unserviceable_reason: str = ""
    at: str = field(default_factory=_now)

    # -- verification -------------------------------------------------------
    def missing_evidence(self) -> list[str]:
        gaps = []
        if not self.required_by:
            gaps.append("no dependent named: nothing is shown to require this capability")
        if not (self.failed_invocation and self.failure_error):
            gaps.append("no failed invocation: absence was inferred, not attempted")
        if not self.unserviceable_reason:
            gaps.append("no unserviceability finding from the router")
        return gaps

    @property
    def status(self) -> str:
        return "VERIFIED" if not self.missing_evidence() else "UNVERIFIED"

    def morphogenesis_authorized(self) -> bool:
        """Whether capability formation or reconfiguration may proceed.

        The founder's precondition, executable. No override argument exists on
        purpose: a caller that could pass ``force=True`` would make the
        verification decorative.
        """
        return self.status == "VERIFIED"

    def describe(self) -> dict:
        return {
            "capability": self.capability,
            "status": self.status,
            "required_by": self.required_by,
            "failed_invocation": self.failed_invocation,
            "failure_error": self.failure_error,
            "examined": list(self.examined),
            "unserviceable_reason": self.unserviceable_reason,
            "missing_evidence": self.missing_evidence(),
            "morphogenesis_authorized": self.morphogenesis_authorized(),
            "at": self.at,
        }


def verify_against_router(capability: str, *, required_by: str,
                          failed_invocation: str, failure_error: str,
                          router) -> CapabilityDeficit:
    """Build a deficit whose third fact is measured, not asserted.

    Asks the router directly. If it can still serve the capability, the deficit
    comes back UNVERIFIED with the reason left empty — which is the correct
    outcome: the function is not missing, something else went wrong, and
    reconfiguring would be treating a symptom.
    """
    from capabilities.router import NoImplementationAvailable

    examined = tuple(i.implementation_id for i in router.implementations(capability))
    reason = ""
    try:
        router.select(capability)
    except NoImplementationAvailable as exc:
        reason = str(exc)
    return CapabilityDeficit(
        capability=capability, required_by=required_by,
        failed_invocation=failed_invocation, failure_error=failure_error,
        examined=examined, unserviceable_reason=reason,
    )
