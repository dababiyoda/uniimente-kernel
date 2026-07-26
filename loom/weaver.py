"""Phase 4 — the Weaver: compiles ratified patterns into durable workflows.

A pattern is data; the weaver gives it legs. Every StepSpec becomes a
durable WorkflowStep on the Layer 4 spine: checkpointed, retry-bounded,
approval-gated, compensated in reverse on failure.

Fail closed: unratified patterns never weave. Unknown operations never
weave. The weaver grants nothing — steps consume capabilities the
pattern declared, and execution authority still comes from the
Consequence Gate for any external effect (the loom orchestrates; the
gate authorizes).
"""
from __future__ import annotations

from dataclasses import dataclass

from events.spine import DurableWorkflow, WorkflowStep, durable_workflow
from loom.ratify import Ratifier


class LoomRefused(ValueError):
    """The loom refuses to weave: unratified, invalid, or unknown operation."""


@dataclass
class Operation:
    """A named unit of work the loom may weave. Compensation operations
    are named separately in the pattern and run through the same registry —
    undo is work, not metadata."""
    run: callable                    # (state, params) -> state delta dict


class Weaver:
    def __init__(self, spine, ratifier: Ratifier, operations: dict[str, Operation]):
        self.spine = spine
        self.ratifier = ratifier
        self.operations = operations

    def weave(self, pattern, *, workflow_id: str) -> DurableWorkflow:
        problems = pattern.validate()
        if problems:
            raise LoomRefused(f"invalid pattern: {problems}")
        if not self.ratifier.is_ratified(pattern.hash()):
            raise LoomRefused(
                f"pattern {pattern.hash()[:20]}... is not ratified; "
                "the machine authors, only the human ratifies")
        steps = []
        for spec in pattern.steps:
            op = self.operations.get(spec.action)
            if op is None:
                raise LoomRefused(f"unknown operation: {spec.action!r}")
            comp_op = self.operations.get(spec.compensation) if spec.compensation else None
            if spec.compensation and comp_op is None:
                raise LoomRefused(f"unknown compensation operation: {spec.compensation!r}")
            steps.append(WorkflowStep(
                name=spec.name,
                run=lambda state, _op=op, _p=spec.params: _op.run(state, _p),
                compensate=(lambda state, _c=comp_op, _p=spec.params: _c.run(state, _p))
                if comp_op else None,
                max_retries=spec.max_retries,
                approval_wait=spec.approval_required))
        wf = durable_workflow(self.spine, workflow_id, steps,
                             actor=pattern.authored_by,
                             legal_principal=pattern.legal_principal)
        self.spine.ledger.append("event", {"type": "loom.pattern_woven",
                                           "pattern_hash": pattern.hash(),
                                           "workflow_id": workflow_id,
                                           "steps": [s.name for s in pattern.steps]})
        return wf
