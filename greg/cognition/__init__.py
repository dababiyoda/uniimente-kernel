"""GREG's bounded competency compiler; the existing registry and Gate remain owners."""

from .contracts import (AbstentionClass, CognitiveCapabilityProfile, CognitiveReceipt,
                        ConsequenceVector, ProblemGeometry, EpistemicClass, ProofClass)

__all__ = ["AbstentionClass", "CognitiveCapabilityProfile", "CognitiveReceipt", "ConsequenceVector",
           "ProblemGeometry", "EpistemicClass", "ProofClass"]


def solve(params, ctx):
    if isinstance(params, dict) and isinstance(params.get("problem"), dict) and params["problem"].get("schema_version") == "cognition/1":
        from .seed_compat import solve as implementation
    else:
        from .cortex import solve as implementation
    return implementation(params, ctx)


def status(params, ctx):
    from .seed_compat import status as implementation
    return implementation(params, ctx)


def settle(params, ctx):
    from .seed_compat import settle as implementation
    return implementation(params, ctx)


def evaluate_problem(*args, **kwargs):
    from .seed_compat import evaluate_problem as implementation
    return implementation(*args, **kwargs)
