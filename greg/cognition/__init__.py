"""GREG's bounded competency compiler; the existing registry and Gate remain owners.

One Mind surface, two layers that answer different questions:

- the competency cells and organs in this package (``greg.cognition.cortex`` and
  siblings) — how a problem is compiled, routed, solved and receipted;
- the deterministic selector in ``greg.cognition.selector`` — which declared
  competency is eligible for a signed invocation. It is the original
  ``greg/cognition.py`` module of the execution-fabric line, moved into this
  package byte-for-byte, so historical imports
  (``from greg.cognition import evaluate_problem, solve, settle``) keep working.

Neither layer creates authority; every receipt still carries authority_created=false.
"""

from .contracts import (AbstentionClass, CognitiveCapabilityProfile, CognitiveReceipt,
                        ConsequenceVector, ProblemGeometry, EpistemicClass, ProofClass)
from .selector import POLICY, _worker, eligible, evaluate_problem, profile, settle, solve, status

__all__ = ["AbstentionClass", "CognitiveCapabilityProfile", "CognitiveReceipt", "ConsequenceVector",
           "ProblemGeometry", "EpistemicClass", "ProofClass",
           "POLICY", "eligible", "evaluate_problem", "profile", "settle", "solve", "status"]
