"""Candidate B0-restore — re-enable the original. The conventional repair.

This is the strongest conventional repair option and the permanent benchmark. It
introduces no new algorithm: it imports the preserved original and translates its
report into the shared output shape. If nothing beats this, this wins, and that
is a legitimate result rather than a disappointing one.

B0 can never satisfy the "materially different from the original" success gate —
it *is* the original — so it is scored on function and excluded from the
structural-replacement verdict. `spec.EXPECTED_RESULTS` freezes both facts.

The import is deliberately inside `resolve`, not at module scope. That is what
makes this candidate an honest test of the runtime disable: while the component
is disabled this candidate fails exactly the way production code would, and once
the disable is lifted it works again with no other change. A module-scope import
would bind at first import and hide the removal.
"""
from __future__ import annotations

from evolution.repair.candidate import FunctionOutput

#: One operation returns the institution to this path: lift the runtime disable.
#: Nothing was deleted, so there is nothing to restore from backup.
ROLLBACK_STEPS = 1


class BaselineRestore:
    """Re-enables and adapts the preserved original implementation."""

    candidate_id = "B0-restore"
    mechanism = "original nested scan over manifests, branching per contract"

    def resolve(self, manifests: list, contracts_dir: str) -> FunctionOutput:
        from linker.linker import InstitutionalLinker

        report = InstitutionalLinker(manifests, contracts_dir=contracts_dir).link()
        return FunctionOutput.normalize(
            edges=[(e.producer, e.contract, e.consumer) for e in report.edges],
            untyped=report.untyped,
            unconsumed=report.unconsumed,
            unproduced=report.unproduced,
            unresolved=report.unresolved,
            overlapping_authority=report.overlapping_authority,
            diagnostics=("original implementation, unmodified",),
        )


def factory() -> BaselineRestore:
    return BaselineRestore()
