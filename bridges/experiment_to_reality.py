"""Bridge C — Experiment-to-Reality, executed end to end.

ExperimentSpec -> compiler -> authority narrowing -> Proposal -> Consequence
Gate -> Commit Witness -> executor -> receipt -> reconciliation -> resolution.

Composition only. The gate already owns witness, receipt and reconciliation
(`ConsequenceGate.run` steps 9-14); this file does not reimplement any of them.
The wire that was missing is narrower and more dangerous than it looks: nothing
in the institution turned a compiled experiment into a gate proposal.

That edge is where authority inflation would happen. An `ExperimentSpec` names
its own `required_capabilities`, `budget_usd` and `authority_requirements`. Read
naively, those fields are a component writing its own permissions — the thing
the Constitution forbids, in the one place it would look like plumbing.

Four properties this pathway keeps:

**An experiment cannot widen its own authority.** The spec's capability list and
budget are *requests*. They are checked against the acting passport, and the
effective budget is `min(requested, ceiling)` — never the larger, never the
spec's number alone. An experiment asking for more than its actor holds is
refused before a proposal is built, so the gate is never asked to bless it.

**Reconciliation decides the experiment; the executor does not.** The gate
reconciles expected against observed outcome, which is a statement about the
action. Whether the *decisive unknown* was resolved is a separate question,
answered by `spec.resolves(measured)` against the threshold that was fixed
before the run. An executor reporting the expected outcome while the metric sits
below threshold produces `resolved=False`. Self-declared success is not a result.

**A refused gate produces no experiment result at all.** Not a failed result —
`resolved is None`. A refusal is the absence of evidence, and recording it as a
negative finding would be inventing a measurement that never happened.

**It claims nothing about the outside world.** `assurance.side_effects` measured
this institution at zero network-egress sites, so no experiment run from here can
touch anything external. The target must be sandboxed and `reality` says
SIMULATED. The Single Bottleneck Metric — Clean Verified Outcome Count — is
untouched by construction, and stays 0.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from evolution.experiment import ExperimentCompiler, ExperimentSpec
from events.spine import Event, EventSpine
from policy.engine import Proposal
from provenance.ledger import EvidenceLedger

KERNEL = "spiffe://uniimente.internal/organ/constitutional-controller"

#: The reality axis of `blueprint.ladder`. A constant so no caller can quietly
#: upgrade what a fixture run means.
SIMULATED = "SIMULATED"

#: Targets an experiment may name. The institution holds no network capability
#: at all (0 egress sites, measured at call and import level), so a target
#: outside this set could not be reached even if policy allowed it. Enforcing
#: the prefix keeps the record honest rather than merely lucky.
SANDBOX_PREFIX = "sandbox:"

#: Gate states that mean the action reached durability. Everything else is a
#: refusal, and a refusal yields no measurement.
COMMITTED_STATES = ("committed", "recorded")


class Halt(Enum):
    """Why a run stopped short. Every value is a refusal the institution wanted."""

    SPEC_DOES_NOT_COMPILE = "spec_does_not_compile"
    UNKNOWN_ACTOR = "unknown_actor"
    CAPABILITY_EXCEEDS_PASSPORT = "capability_exceeds_passport"
    BUDGET_EXCEEDS_PASSPORT = "budget_exceeds_passport"
    TARGET_NOT_SANDBOXED = "target_not_sandboxed"
    GATE_REFUSED = "gate_refused"


@dataclass(frozen=True)
class ExperimentRun:
    """What one traversal actually did. Derived; nothing here is supplied."""

    completed: bool
    #: Did the measurement resolve the decisive unknown? `None` means the run
    #: never reached a measurement — which is not the same as `False`.
    resolved: bool | None = None
    halted_at: Halt | None = None
    reason: str = ""
    reality: str = SIMULATED
    #: The gate's own record, so a caller can audit the action independently.
    action_id: str | None = None
    witness_id: str | None = None
    receipt_hash: str | None = None
    gate_state: str | None = None
    #: What the metric actually read, and what it had to beat.
    measured: float | None = None
    threshold: float | None = None
    #: Requested versus granted. Divergence here is the authority narrowing
    #: doing its job, and is worth being able to read back.
    requested_budget_usd: float | None = None
    granted_budget_usd: float | None = None
    kill_condition_fired: bool = False
    experiment_id: str | None = None
    event_ids: tuple[str, ...] = ()

    @property
    def produced_a_measurement(self) -> bool:
        """True only when the gate committed and the metric was read."""
        return self.measured is not None


def _emit_kernel_fact(spine: EventSpine, *, event_type: str, payload: dict,
                      causal_parent: str | None) -> str:
    """The kernel's own reading. Emitted, because the kernel is its source."""
    event = Event(
        type=event_type,
        source=KERNEL,
        actor=KERNEL,
        payload=payload,
        legal_principal="Alfonso Lopez",
        causal_parent=causal_parent,
    )
    spine.emit(event)
    return event.event_id


def run(spec: ExperimentSpec, *, gate, passports, actor: str,
        measure, ledger: EvidenceLedger | None = None,
        legal_principal: str = "alfonso_lopez",
        target: str | None = None,
        approver=None,
        standing_grant: dict | None = None,
        kill_check=None) -> ExperimentRun:
    """Traverse Bridge C once.

    `measure` is the caller's instrument: it runs inside the gate's executor
    slot and returns the float the metric reads. It is deliberately not allowed
    to declare the experiment resolved — that verdict is computed here from the
    threshold fixed before the run.

    `target` is the caller's, defaulting to a sandbox path derived from the
    workflow. A caller naming anything outside `sandbox:` is refused: the
    institution holds no egress capability, so any other target would be a
    claim about the world that this code could not keep.

    `standing_grant` is a budget authorization issued elsewhere. This bridge
    never mints one: an experiment that funded itself would be the precise
    authority inflation the narrowing above exists to prevent. Without a grant,
    the policy engine denies any non-zero cost — so a budgeted experiment simply
    does not run until someone with the authority to fund it has done so.

    `kill_check` receives the measured value and answers whether the spec's kill
    condition fired. A fired kill condition does not un-commit the action (the
    gate already made it durable); it is recorded alongside the result, because
    an experiment that succeeded and tripped its own kill condition is a fact
    the institution needs to see rather than a contradiction to hide.
    """
    ledger = ledger if ledger is not None else EvidenceLedger("bridge-c")
    spine = EventSpine(ledger)
    events: list[str] = []

    # --- leg 1: the spec must compile ---------------------------------------
    # `ExperimentCompiler` refuses hopes: irreversible, unfalsifiable, or
    # unbudgeted experiments never become proposals.
    try:
        compiled = ExperimentCompiler().compile(spec)
    except ValueError as exc:
        return ExperimentRun(completed=False, halted_at=Halt.SPEC_DOES_NOT_COMPILE,
                             reason=str(exc), experiment_id=spec.experiment_id)

    events.append(_emit_kernel_fact(
        spine, event_type="bridge.experiment_compiled",
        payload={"experiment_id": compiled.experiment_id,
                 "decisive_unknown": compiled.decisive_unknown,
                 "metric": compiled.metric, "threshold": compiled.threshold},
        causal_parent=None))

    # --- leg 2: authority narrowing -----------------------------------------
    # The spec asked. The passport decides. Nothing below may exceed what the
    # acting identity already held before this experiment was written.
    try:
        passport = passports.to_dict(actor)
    except Exception as exc:  # unknown identity, however the registry says it
        return ExperimentRun(completed=False, halted_at=Halt.UNKNOWN_ACTOR,
                             reason=f"actor not in registry: {exc}",
                             experiment_id=compiled.experiment_id,
                             event_ids=tuple(events))

    held = set(passport.get("declared_capabilities") or ())
    overreach = sorted(set(compiled.required_capabilities) - held)
    if overreach:
        return ExperimentRun(
            completed=False, halted_at=Halt.CAPABILITY_EXCEEDS_PASSPORT,
            reason=f"experiment requests capabilities its actor does not hold: {overreach}",
            experiment_id=compiled.experiment_id, event_ids=tuple(events))

    ceiling = float(passport.get("budget_ceiling_usd") or 0.0)
    if compiled.budget_usd > ceiling:
        return ExperimentRun(
            completed=False, halted_at=Halt.BUDGET_EXCEEDS_PASSPORT,
            reason=(f"experiment budgets {compiled.budget_usd} against a passport "
                    f"ceiling of {ceiling}"),
            experiment_id=compiled.experiment_id,
            requested_budget_usd=compiled.budget_usd,
            event_ids=tuple(events))

    # min, not max, and not the spec's number on its own.
    granted = min(compiled.budget_usd, ceiling)

    # --- leg 3: the target must be one the institution can honestly reach ----
    # The caller names the target. Constructing it here and then checking our
    # own construction would assert nothing; the check exists to refuse a
    # caller who names something the institution cannot reach.
    target = target if target is not None else f"{SANDBOX_PREFIX}{compiled.workflow}"
    if not target.startswith(SANDBOX_PREFIX):
        return ExperimentRun(completed=False, halted_at=Halt.TARGET_NOT_SANDBOXED,
                             reason=(f"target {target!r} is not sandboxed; this institution "
                                     f"holds no egress capability, so no other target is honest"),
                             experiment_id=compiled.experiment_id,
                             event_ids=tuple(events))

    # --- leg 4: the proposal, built from the narrowed authority --------------
    proposal = Proposal(
        actor=actor,
        legal_principal=legal_principal,
        action_class=compiled.workflow,
        objective=compiled.decisive_unknown,
        payload={"experiment_id": compiled.experiment_id,
                 "hypothesis": compiled.hypothesis,
                 "prediction": compiled.prediction},
        target=target,
        consequence_class=passport.get("consequence_class") or "internal_write",
        evidence_confidence=0.9,
        evidence_refs=[f"experiment:{compiled.experiment_id}"],
        estimated_cost_usd=granted,
        requested_capability=compiled.required_capabilities[0],
        expected_outcome=compiled.prediction,
    )

    events.append(_emit_kernel_fact(
        spine, event_type="bridge.experiment_proposed",
        payload={"experiment_id": compiled.experiment_id,
                 "requested_budget_usd": compiled.budget_usd,
                 "granted_budget_usd": granted,
                 "target": target},
        causal_parent=events[-1]))

    # --- leg 5: the gate. Witness, receipt and reconciliation are its. -------
    readings: list[float] = []

    def _executor(p: Proposal) -> dict:
        value = float(measure(compiled))
        readings.append(value)
        return {"observed_outcome": compiled.prediction,
                "result_class": "measured",
                "metrics": {compiled.metric: value},
                "validation_status": "internally_observed"}

    record = gate.run(proposal, executor=_executor, approver=approver,
                      standing_grant=standing_grant)

    if record.state not in COMMITTED_STATES:
        # A refusal is the absence of evidence. `resolved` stays None.
        events.append(_emit_kernel_fact(
            spine, event_type="bridge.experiment_refused",
            payload={"experiment_id": compiled.experiment_id,
                     "gate_state": record.state},
            causal_parent=events[-1]))
        return ExperimentRun(
            completed=False, halted_at=Halt.GATE_REFUSED,
            reason=f"consequence gate returned {record.state!r}",
            experiment_id=compiled.experiment_id, action_id=record.action_id,
            gate_state=record.state, threshold=compiled.threshold,
            requested_budget_usd=compiled.budget_usd, granted_budget_usd=granted,
            event_ids=tuple(events))

    # --- leg 6: resolution, decided by the threshold and not by the executor -
    measured = readings[0] if readings else None
    resolved = compiled.resolves(measured) if measured is not None else None
    fired = bool(kill_check(measured)) if (kill_check and measured is not None) else False

    events.append(_emit_kernel_fact(
        spine, event_type="bridge.experiment_resolved",
        payload={"experiment_id": compiled.experiment_id,
                 "measured": measured, "threshold": compiled.threshold,
                 "resolved": resolved, "kill_condition_fired": fired,
                 "reality": SIMULATED},
        causal_parent=events[-1]))

    return ExperimentRun(
        completed=True, resolved=resolved, action_id=record.action_id,
        witness_id=record.witness_id, receipt_hash=record.receipt_hash,
        gate_state=record.state, measured=measured, threshold=compiled.threshold,
        requested_budget_usd=compiled.budget_usd, granted_budget_usd=granted,
        kill_condition_fired=fired, experiment_id=compiled.experiment_id,
        event_ids=tuple(events))
