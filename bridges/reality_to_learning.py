"""Bridge D — Reality-to-Learning, executed end to end.

External observation -> ValidationResult -> decision episode -> Causal Memory ->
calibration update -> proposed Capability Genome evidence.

Composition only. `CausalMemory`, `EvidenceLedger` and `GenomeRegistry` existed
and were tested before this file. What was missing is the leg that lets anything
the institution learns come from outside it.

This is the bridge with the sharpest failure mode, and it is worth naming before
the code: **every outcome the institution has ever recorded is
`internally_observed`.** The gate writes that status itself. `VALIDATION_WEIGHT`
scores it 0.6 against 1.0 for `externally_verified`, so the only way any claim
reaches full weight is for something outside the institution to say so. A bridge
that let a component upgrade its own outcome would convert the entire evidence
ladder into self-report wearing a stronger word.

Four properties this pathway keeps:

**Nothing verifies itself.** An observation is admitted only when its observer is
attributed and distinct from the actor whose outcome it judges. Self-attestation
is refused by identity comparison, before the status is read — so an actor cannot
reach `externally_verified` about its own action no matter what it claims.

**Calibration compares a prediction to a result, not a result to itself** — and
building that join is what exposed GAP-BRIDGE-D-001. The Commit Witness has no
field for the confidence the policy engine decided on, so the prediction is
discarded at the durability boundary and no such pair can be reconstructed. The
join is written anyway, against the field the witness would have to carry, and
reports nothing rather than something convenient. Widening a signed structure is
a contract change; it was not made here.

**A capability genome is not promoted here.** Bridge D emits a proposed evidence
update carrying the observation's attribution and validation status. It never
writes to the registry: raising a genome's standing is a governed act, and a
learning loop that promoted its own components would be a component authorizing
its own promotion under a different name.

**The Single Bottleneck Metric becomes measured.** Clean Verified Outcome Count
has been asserted as 0 all along. `clean_verified_outcomes()` computes it from
the ledger: outcomes that are externally verified, positive, and reconciled
against what was predicted. With no external observer in the loop it returns 0 —
but now that 0 is a reading rather than a claim, and it will move the moment a
real counterparty says something, and not one moment before.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from events.spine import Event, EventSpine
from memory.causal import VALIDATION_WEIGHT, CausalMemory
from provenance import witness_v2
from provenance.ledger import EvidenceLedger

KERNEL = "spiffe://uniimente.internal/organ/constitutional-controller"

SIMULATED = "SIMULATED"

#: The only status that carries full evidential weight, and the only one an
#: outside party can confer. Named here so a reader sees the stake immediately.
EXTERNALLY_VERIFIED = "externally_verified"
INTERNALLY_OBSERVED = "internally_observed"
SELF_REPORTED = "self_reported"

#: `contracts/outcome.schema.json` enumerates exactly these three.
VALIDATION_STATUSES = (EXTERNALLY_VERIFIED, INTERNALLY_OBSERVED, SELF_REPORTED)

POSITIVE = ("positive",)


class Halt(Enum):
    """Why a run stopped short. Every value is a refusal the institution wanted."""

    OBSERVER_NOT_ATTRIBUTED = "observer_not_attributed"
    SELF_ATTESTATION = "self_attestation"
    UNKNOWN_VALIDATION_STATUS = "unknown_validation_status"
    NO_SUCH_ACTION = "no_such_action"


@dataclass(frozen=True)
class ValidationResult:
    """One outside party's statement about one action. Attributed or refused."""

    action_id: str
    observer: str
    #: What the observer says happened, in their words, not the actor's.
    external_observation: str
    result_class: str
    validation_status: str
    #: The actor whose outcome this judges, carried so the record is readable
    #: without re-joining the ledger.
    actor: str

    @property
    def weight(self) -> float:
        """The evidential weight `memory.causal` will give this."""
        return VALIDATION_WEIGHT.get(self.validation_status, 0.3)


@dataclass(frozen=True)
class LearningRun:
    """What one traversal actually did. Derived; nothing here is supplied."""

    completed: bool
    halted_at: Halt | None = None
    reason: str = ""
    reality: str = SIMULATED
    validation: ValidationResult | None = None
    #: The calibration report over every (predicted, realized) pair the ledger
    #: holds. `None` today for a structural reason, not an incidental one:
    #: see `CALIBRATION_GAP`.
    calibration: dict | None = None
    #: Set whenever calibration could not be computed, carrying why.
    calibration_blocked_by: str | None = None
    #: What Bridge D would propose about a capability's standing. Never applied.
    proposed_genome_evidence: dict | None = None
    #: The Single Bottleneck Metric, read rather than asserted.
    clean_verified_outcomes: int = 0
    event_ids: tuple[str, ...] = ()


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


def _ingest_external_fact(spine: EventSpine, *, observer: str, payload: dict,
                          causal_parent: str | None) -> str:
    """An outside party's assertion. `ingest`, never `emit`.

    `emit` would make the kernel the source of a claim it merely received — the
    authority inflation section 8 forbids, in the one place it would be
    invisible, and the exact mistake that would turn an external verification
    into an internal one.
    """
    event = Event(
        type="bridge.external_observation_received",
        source=observer,
        actor=observer,
        payload=payload,
        legal_principal="Alfonso Lopez",
        causal_parent=causal_parent,
    )
    spine.ingest(event)
    return event.event_id


def clean_verified_outcomes(ledger: EvidenceLedger) -> int:
    """The Single Bottleneck Metric, computed from the ledger.

    An outcome counts only when all three hold: an outside party verified it,
    the result was positive, and what was observed reconciled with what was
    predicted before the action ran. Any two of the three is not a clean
    verified outcome, which is the whole reason the metric has stayed at zero.
    """
    count = 0
    for record in ledger.by_type("outcome"):
        outcome = record.payload
        if outcome.get("validation_status") != EXTERNALLY_VERIFIED:
            continue
        if outcome.get("result_class") not in POSITIVE:
            continue
        if "reconciled=True" not in str(outcome.get("expected_vs_actual", "")):
            continue
        count += 1
    return count


#: GAP-BRIDGE-D-001, found by building this leg rather than by reading doctrine.
#:
#: The institution cannot calibrate itself from its own ledger, because the
#: prediction it would be graded on is never durably recorded. `Proposal`
#: carries `evidence_confidence`; `policy.engine.evaluate` decides on it; and
#: `provenance.commit_witness.CommitWitness` — the signed record written at the
#: durability boundary — has no field for it. Nothing else on the ledger holds
#: it either: the receipt carries a result, and the action-state transitions
#: carry only actor and action class.
#:
#: So `CausalMemory.calibrate` is reachable but unfeedable. It is exercised
#: today only by hand-built pairs in tests and closure probes, which is why the
#: gap stayed invisible: the function works perfectly on data the institution
#: never produces.
#:
#: This bridge does NOT close the gap. Adding a field to `CommitWitness` changes
#: a signed structure — every existing signature is computed over the current
#: field set — so it is a contract change requiring a version and a founder
#: decision, not a repair to slip into a bridge. Recorded as an unresolved field
#: in the sense section 4.1 means: named, not invented around.
#: AMENDED 2026-08-22 under FOUNDER-RULING-2026-08-22, which approved the
#: coordinated contract migration. The contract now exists — `provenance/
#: witness_v2.py` carries evidence_confidence, consequence_class and the
#: effective exposure ceiling, all covered by the signature. What remains is
#: adoption, and the gap is rewritten to say so rather than closed: a contract
#: nothing writes produces no pairs, exactly as before.
CALIBRATION_GAP = (
    "Witness contract v2 records evidence_confidence, but no v2 witness has "
    "been written: policy/consequence_gate.py is a sealed continuity artifact "
    "(pinned in evolution/repair/spec.CONTINUITY_ARTIFACT_SHA256) and still "
    "calls the v1 constructor, dropping the consequence_class and "
    "evidence_confidence its own Proposal already carries. Every historical "
    "record is v1 and reads as UNRECORDED, never as zero. See "
    "docs/deliberations/CONTRADICTION-0002-continuity-baseline.md."
)


def predicted_versus_realized(ledger: EvidenceLedger) -> list[tuple[float, bool]]:
    """Join the confidence written in the witness to what was later observed.

    Returns empty today, and the emptiness is the finding — see
    `CALIBRATION_GAP`. The join is written against the field the witness would
    have to carry, so it starts working the moment that contract change is
    ratified, and reports nothing rather than something convenient until then.

    Deliberately reads confidence off the *witness* and not the outcome. The
    witness is written before execution; the outcome after. Sourcing it from the
    outcome would compare a result to itself and report perfect calibration
    forever, which is the shape this whole bridge exists to refuse.
    """
    witnesses = {w.payload["witness_id"]: w.payload for w in ledger.by_type("witness")}
    receipts = {r.payload["action_id"]: r.payload for r in ledger.by_type("receipt")}
    pairs: list[tuple[float, bool]] = []
    for record in ledger.by_type("outcome"):
        outcome = record.payload
        receipt = receipts.get(outcome.get("action_ref"))
        witness = witnesses.get(receipt["witness_id"]) if receipt else None
        if witness is None:
            continue
        # Read through the versioned contract rather than reaching for the raw
        # key. A v1 record yields UNRECORDED and `calibratable` is False, so it
        # is skipped as *absent* rather than coerced into a number — the
        # distinction the ruling insisted on, and the reason this join stays
        # empty over a historical ledger instead of reporting a flattering curve.
        reading = witness_v2.read(witness)
        if not reading.calibratable:
            continue
        pairs.append((float(reading.evidence_confidence),
                      outcome.get("result_class") in POSITIVE))
    return pairs


def run(observation: dict, *, ledger: EvidenceLedger,
        capability: str | None = None) -> LearningRun:
    """Traverse Bridge D once.

    `observation` is what an outside party says about one action:
    `{action_id, observer, external_observation, result_class, validation_status}`.
    The observer is an identity, not a label, and it is compared against the
    actor recorded in the action's own witness.
    """
    spine = EventSpine(ledger)
    events: list[str] = []

    observer = (observation.get("observer") or "").strip()
    if not observer:
        return LearningRun(completed=False, halted_at=Halt.OBSERVER_NOT_ATTRIBUTED,
                           reason="an observation with no attributed observer is a rumour")

    status = observation.get("validation_status")
    if status not in VALIDATION_STATUSES:
        return LearningRun(
            completed=False, halted_at=Halt.UNKNOWN_VALIDATION_STATUS,
            reason=f"validation_status {status!r} is not one of {list(VALIDATION_STATUSES)}")

    # --- who acted? read from the witness, never from the observation --------
    action_id = observation.get("action_id")
    receipts = {r.payload["action_id"]: r.payload for r in ledger.by_type("receipt")}
    witnesses = {w.payload["witness_id"]: w.payload for w in ledger.by_type("witness")}
    receipt = receipts.get(action_id)
    witness = witnesses.get(receipt["witness_id"]) if receipt else None
    if witness is None:
        return LearningRun(
            completed=False, halted_at=Halt.NO_SUCH_ACTION,
            reason=f"no witnessed action {action_id!r}; an observation about nothing "
                   f"is not evidence")

    actor = witness.get("actor")
    if observer == actor:
        return LearningRun(
            completed=False, halted_at=Halt.SELF_ATTESTATION,
            reason=(f"{observer} cannot verify its own action; external verification "
                    f"requires an observer distinct from the actor"))

    validation = ValidationResult(
        action_id=action_id, observer=observer,
        external_observation=observation.get("external_observation", ""),
        result_class=observation.get("result_class", "inconclusive"),
        validation_status=status, actor=actor)

    # --- the observation enters as someone else's fact ----------------------
    events.append(_ingest_external_fact(
        spine, observer=observer,
        payload={"action_id": action_id, "validation_status": status,
                 "result_class": validation.result_class},
        causal_parent=None))

    # --- the kernel's own reading, recorded as an outcome -------------------
    ledger.append("outcome", {
        "outcome_id": f"{action_id}:{observer}",
        "action_ref": action_id,
        "recorded_at": witness.get("created_at") or "",
        "recorded_by": observer,
        "external_observation": validation.external_observation,
        "result_class": validation.result_class,
        "expected_vs_actual": (
            f"expected={witness.get('expected_outcome')!r} "
            f"actual={validation.external_observation!r} "
            f"reconciled={validation.external_observation == witness.get('expected_outcome')}"),
        "validation_status": status,
        "feeds": ["causal_memory", "calibration"],
    })

    events.append(_emit_kernel_fact(
        spine, event_type="bridge.validation_recorded",
        payload={"action_id": action_id, "observer": observer,
                 "validation_status": status, "weight": validation.weight},
        causal_parent=events[-1]))

    # --- calibration: prediction written first, result joined after ---------
    pairs = predicted_versus_realized(ledger)
    calibration = CausalMemory.calibrate(pairs) if pairs else None
    blocked = None if pairs else CALIBRATION_GAP

    # --- what would be proposed about a capability's standing ---------------
    proposed = None
    if capability is not None:
        proposed = {
            "capability": capability,
            "observed_by": observer,
            "validation_status": status,
            "evidential_weight": validation.weight,
            "applied": False,
            "why_not_applied": ("raising a genome's standing is a governed act; a "
                                "learning loop that promoted its own components "
                                "would be authorizing its own promotion"),
        }

    sbm = clean_verified_outcomes(ledger)

    events.append(_emit_kernel_fact(
        spine, event_type="bridge.learning_recorded",
        payload={"action_id": action_id,
                 "calibration_verdict": (calibration or {}).get("verdict"),
                 "clean_verified_outcomes": sbm,
                 "genome_update_applied": False,
                 "reality": SIMULATED},
        causal_parent=events[-1]))

    return LearningRun(
        completed=True, validation=validation, calibration=calibration,
        calibration_blocked_by=blocked, proposed_genome_evidence=proposed,
        clean_verified_outcomes=sbm, event_ids=tuple(events))
