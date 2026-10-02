"""#15 Workflow engine: the Kernel's DurableWorkflow (events/spine.py).

Checkpointed state machines with approvals, retries, compensation and
recovery: a workflow killed mid-flight resumes from its ledger checkpoints
without re-running finished steps; an approval gate stops until approved; a
step that exhausts retries triggers compensation of completed steps in
reverse; a step whose outcome is uncertain is never blindly retried.
"""
from __future__ import annotations

from pathlib import Path


def exercise(root) -> dict:
    from events.spine import DurableWorkflow, EventSpine, WorkflowFailed, WorkflowKilled, WorkflowStep
    from provenance.ledger import EvidenceLedger
    path = Path(root) / "ledger.jsonl"
    runs = {"research": 0, "draft": 0, "deliver": 0}
    undone = []

    def step(name, fail_times=0):
        def run(state):
            runs[name] += 1
            if runs[name] <= fail_times:
                raise RuntimeError(f"{name} transient failure")
            return {name: "done"}
        return run

    def steps(fail_deliver=0):
        return [WorkflowStep("research", step("research"), compensate=lambda s: undone.append("research"), retry_safe=True),
                WorkflowStep("draft", step("draft"), compensate=lambda s: undone.append("draft"), retry_safe=True),
                WorkflowStep("deliver", step("deliver", fail_deliver), max_retries=1, retry_safe=True)]

    spine = EventSpine(EvidenceLedger("sha256:" + "0" * 64, str(path)))
    wf = DurableWorkflow(spine, "wf-brief", steps(), actor="greg", legal_principal="alfonso_lopez")
    try:
        wf.execute(kill_at_step="deliver")
        killed = False
    except WorkflowKilled:
        killed = True
    spine.ledger.close()                                                         # the process dies
    reopened = EventSpine(EvidenceLedger("sha256:" + "0" * 64, str(path)))     # a new process takes over
    resumed = DurableWorkflow.resume(reopened, "wf-brief", steps()).execute()
    exactly_once = runs == {"research": 1, "draft": 1, "deliver": 1}

    gated = DurableWorkflow(reopened, "wf-gated", [WorkflowStep("publish", lambda s: {"p": 1}, approval_wait=True)],
                            actor="greg", legal_principal="alfonso_lopez")
    try:
        gated.execute(approver=lambda s: False)
        approval_blocked = False
    except WorkflowKilled:
        approval_blocked = True

    runs.update({"research": 0, "draft": 0, "deliver": 0})
    failing = DurableWorkflow(reopened, "wf-fail", steps(fail_deliver=5), actor="greg", legal_principal="alfonso_lopez")
    try:
        failing.execute()
        compensated = False
    except WorkflowFailed:
        compensated = True
    reopened.ledger.close()
    return {"killed_mid_flight": killed, "resumed_status": resumed.status, "no_step_repeated": exactly_once,
            "approval_blocks_without_approver": approval_blocked, "failure_compensated": compensated,
            "compensation_order": undone, "deliver_attempts": runs["deliver"]}


def run_composed(args: dict, root) -> dict:
    """A durable workflow whose steps are other Foundry system ops (the Swiss Army knife composing itself).

    args: {workflow_id, steps: [{name, system, op, args, write: bool}]}. A workflow
    already on this store's ledger resumes instead of starting over.
    """
    from events.spine import DurableWorkflow, EventError, EventSpine, WorkflowStep
    from foundry.systems import module
    from provenance.ledger import EvidenceLedger
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)

    def make(spec):
        system = module(int(spec["system"]))
        table = system.APPLY_OPS if spec.get("write") else system.QUERY_OPS
        if spec["op"] not in table:
            raise EventError(f"system {spec['system']} has no {'apply' if spec.get('write') else 'query'} op {spec['op']!r}")
        store = root.parent / f"system-{int(spec['system']):02d}"
        return WorkflowStep(spec["name"], lambda state, f=table[spec["op"]], a=spec.get("args", {}): {spec["name"]: f(a, store)},
                            retry_safe=not spec.get("write"))

    steps = [make(s) for s in args["steps"]]
    spine = EventSpine(EvidenceLedger("sha256:" + "0" * 64, str(root / "workflows.jsonl")))
    try:
        known = any(r.payload.get("workflow_id") == args["workflow_id"] for r in spine.ledger.by_type("workflow"))
        wf = (DurableWorkflow.resume(spine, args["workflow_id"], steps) if known else
              DurableWorkflow(spine, args["workflow_id"], steps, actor="greg", legal_principal="alfonso_lopez"))
        wf.execute()
        return {"status": wf.status, "outputs": wf.state}
    finally:
        spine.ledger.close()


QUERY_OPS = {"demonstrate": lambda a, r: exercise(r)}
APPLY_OPS = {"run": run_composed}
