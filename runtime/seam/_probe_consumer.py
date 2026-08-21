"""A synthetic consumer used only by the seam's own unit tests.

Deliberately trivial and deliberately NOT a stand-in for a real one. It exists
so ``tests/unit/test_seam_router.py`` can measure routing mechanics — refusal,
fail-closed, Geometry B dispatch, the execution witness — without depending on
whether the DALEOBANKS and WealthMachineIntelligence checkouts are present.

It must never appear in a closure episode. The frozen contract's disqualifying
outcomes name "restoration verified only by test fixture, never by a routed
request", and ``runtime/seam/bindings_p3.py`` binds real organ code precisely
so this file stays where it belongs: in the unit tests.
"""
from __future__ import annotations


class Consumer:
    """Echoes the payload back so the witness has something to observe."""

    def receive(self, body: dict) -> dict:
        return {"received": dict(body)}
