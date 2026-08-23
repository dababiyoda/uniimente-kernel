"""Capability Router (Foundry technology #25, FBO §4.14).

Where several implementations satisfy the same contract, something has to choose.
That choice is a recommendation with a recorded rationale — never an execution
and never a permission.

    Routing decisions are recorded and later compared with outcomes.
                                                      — Final Build Order §4.14

The comparison half is not yet possible: no live traffic has routed through this
router and the institution has zero verified external outcomes. The selection
weights are therefore *declared*, not learned, and the router says so in every
decision it returns.
"""
from routing.decision_router import (
    Candidate,
    RouterError,
    RoutingCriteria,
    RoutingDecision,
    DecisionRouter,
)

__all__ = [
    "Candidate", "RouterError", "RoutingCriteria", "RoutingDecision",
    "DecisionRouter",
]
