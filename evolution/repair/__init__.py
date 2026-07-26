"""Package 3 — governed functional replacement of a specialist component.

This package holds FOUR thin integration/testing adapters around machinery
that already exists on the canonical line, plus the candidate
implementations they compare:

    disable.py    runtime component disable
    detector.py   blind function-loss detector
    candidate.py  replacement-candidate interface
    cost.py       repair-cost meter

It deliberately contains NO new Foundry, morphogenesis engine, recovery
framework, authority system, memory system, or governance layer. Ranking is
`evolution.comparison.Comparison`; the experiment is
`evolution.experiment.ExperimentSpec`; the decision is
`evolution.capsule.RetainRegressKillDecision`; evidence is the existing
provenance ledger; authority is the one canonical control plane.

WHAT THIS IS. A governed functional-replacement experiment: a working
specialist function is removed at runtime, the loss is detected without
telling the detector what broke, materially different replacements are
ranked by a frozen comparison, and one is installed while institutional
continuity is proved to hold.

WHAT THIS IS NOT. It is not autonomous regeneration, not unscripted
morphogenesis, and not open-ended self-repair. Every candidate was authored
in the same development session by the same author, and the replaced
component is stateless. Those limitations are structural to the result and
are recorded, not dressed up. See `spec.DECLARED_LIMITATIONS`.
"""
