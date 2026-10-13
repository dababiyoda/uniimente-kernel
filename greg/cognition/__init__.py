"""GREG's bounded competency compiler; the existing registry and Gate remain owners.

Package-level ``solve``/``status``/``settle``/``evaluate_problem`` are the schema-routed compatibility
entry (from #156/#159): a ``cognition/1`` problem goes to the legacy seed path, anything else to the
cortex bridge. The registered capabilities stay distinct (``cognition.solve`` = cortex bridge,
``cognition.seed.solve`` = seed path, from #155/#158); this dispatcher adds no registration.
"""

from .contracts import (AbstentionClass, CognitiveCapabilityProfile, CognitiveReceipt,
                        ConsequenceVector, ProblemGeometry, EpistemicClass, ProofClass)

__all__ = ["AbstentionClass", "CognitiveCapabilityProfile", "CognitiveReceipt", "ConsequenceVector",
           "ProblemGeometry", "EpistemicClass", "ProofClass"]


def solve(params, ctx):
    if isinstance(params, dict) and isinstance(params.get("problem"), dict) and params["problem"].get("schema_version") == "cognition/1":
        from .seed_path import solve as implementation
    else:
        from .cortex import solve as implementation
    return implementation(params, ctx)


def status(params, ctx):
    from .seed_path import status as implementation
    return implementation(params, ctx)


def settle(params, ctx):
    from .seed_path import settle as implementation
    return implementation(params, ctx)


def evaluate_problem(*args, **kwargs):
    from .seed_path import evaluate_problem as implementation
    return implementation(*args, **kwargs)
