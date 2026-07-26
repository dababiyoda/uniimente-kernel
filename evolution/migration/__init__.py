"""Package 4 — governed stateful replacement through the canonical runtime.

Package 3 replaced a STATELESS component inside a private experiment registry.
Its own record says installation "does NOT rewrite the kernel's live import
path". Package 4 closes exactly that gap: a stateful component, replaced at the
real construction sites that verifier V3 exercises.

Thin adapters only, around machinery that already exists:

    spec.py       the frozen experiment (first commit, no candidates)
    schema.py     declared state schemas + validation
    migrate.py    cursor:int <-> completed_steps/next_step, and its refusals
    compat.py     compatibility checking before activation
    export.py     state export / import
    harness.py    the governed loop

The seam itself lives in `events/engine.py` because it is part of the canonical
runtime, not part of the experiment. This package supplies the validator the
seam enforces; it does not own the seam.

WHAT THIS IS NOT. Not autonomous regeneration, not open-ended self-repair. Every
candidate is authored in one session by one author, activation is scoped and
temporary, and the original is the default after every process restart.
"""
