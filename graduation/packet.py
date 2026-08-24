"""The External Reality Graduation Packet: preregistered, sealed, unexecuted.

FOUNDER-RULING-2026-08-22, ruling 8:

> Build an External Reality Graduation Packet now: identify the smallest,
> cheapest, reversible, lawful and most informative first canary; preregister
> the prediction and success/failure criteria; specify exact capability,
> authority, consequence class, budget/exposure, identity, kill switch,
> reconciliation method, external verification method and rollback; connect the
> complete Bridge C → D → learning path; and prove it end-to-end against a
> consequence-inert rehearsal.
>
> Do not execute that real canary yet.

## Why preregistration is the whole mechanism

The failure this guards against is not lying. It is the ordinary human motion of
looking at a result and remembering that it is roughly what you expected. An
institution whose first external act is evaluated against criteria written after
the result arrived has learned nothing it can trust, and has done it in the one
place where trust matters most.

So `PREREGISTRATION_SHA256` seals the prediction, the success criteria, the
failure criteria and the kill conditions. It is computed over those fields only
— deliberately not over the whole packet, so operational details (a channel
name, a rollback contact) can be corrected without disturbing the seal, while
any edit to what counts as success moves it and fails a test.

## This packet is not an authorization

Constructing it, sealing it, and rehearsing it produce no permission to run it.
`authorized_by` is `None` and there is no code path that sets it — the founder
grants that separately and explicitly, per the standing constraint that the
canary is not to be executed. `EXECUTION_STATUS` says so in the module.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field

from graduation.candidates import selected

#: Stated in the module so no reader has to infer it from the absence of a run.
EXECUTION_STATUS = (
    "NOT EXECUTED AND NOT AUTHORIZED. This packet is a proposal. The founder's "
    "standing constraints forbid external publication and any real-world "
    "consequence, and ruling 8 says explicitly: do not execute that real canary "
    "yet. Building the packet, sealing it and rehearsing it confer nothing."
)


@dataclass(frozen=True)
class Preregistration:
    """What we predict, and what would falsify it. Sealed before any run.

    Every field here is written before the act. `predicted_confidence` is the
    number Bridge D will later join against the observed result — the first
    entry in a calibration record that currently has none, and the reason
    witness contract v2 had to exist first.
    """

    prediction: str
    predicted_confidence: float
    success_criteria: tuple[str, ...]
    failure_criteria: tuple[str, ...]
    kill_conditions: tuple[str, ...]

    def canonical(self) -> bytes:
        return json.dumps(asdict(self), sort_keys=True,
                          separators=(",", ":")).encode()

    def seal(self) -> str:
        return hashlib.sha256(self.canonical()).hexdigest()


@dataclass(frozen=True)
class GraduationPacket:
    """One proposed first external act, fully specified and unexecuted."""

    canary_id: str
    summary: str
    preregistration: Preregistration

    # -- exactly what the ruling required be specified ----------------------
    capability: str
    authority_required: str
    consequence_class: str
    budget_usd: float
    exposure_ceiling_usd: float
    identity: str
    kill_switch: str
    reconciliation_method: str
    external_verification_method: str
    rollback: str

    #: The Bridge C -> D -> learning path this run traverses, in order.
    bridge_path: tuple[str, ...]

    #: "How strong is the evidence that taking this bounded action is
    #: justified?" — the quantity the Gate's floor governs, and a DIFFERENT
    #: question from `preregistration.predicted_confidence`, which asks how
    #: likely the run is to succeed.
    #:
    #: Deliberately outside `Preregistration`: the founder ruled the sealed
    #: preregistration must be preserved, so the seal does not move. This is not
    #: a prediction and nothing calibrates against it.
    #:
    #: Set to 0.0 by default so a packet that omits its justification is refused
    #: by the floor rather than admitted by a convenient default.
    evidence_confidence: float = 0.0

    #: Why that number, itemised. Each entry is a fact a reviewer can check
    #: against the repository, not an adjective. The value above is a judgement,
    #: and this is the argument it has to survive.
    evidence_basis: tuple[str, ...] = field(default_factory=tuple)

    #: Never set by code. The founder grants authorization separately.
    authorized_by: None = None
    authorization_ref: None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def sealed(self) -> str:
        return self.preregistration.seal()

    @property
    def is_authorized(self) -> bool:
        """Always False. There is no code path that makes it True."""
        return self.authorized_by is not None


#: The packet. Every value below is a decision, and each is argued in
#: `docs/deliberations/EXTERNAL-REALITY-GRADUATION-PACKET.md`.
PACKET = GraduationPacket(
    canary_id="CANARY-0001",
    summary=(
        "Publish one narrowly bounded item to a DALEOBANKS-owned channel, "
        "observe it from outside the institution, and reconcile the observation "
        "against the receipt."
    ),
    preregistration=Preregistration(
        prediction=(
            "The governed path will execute end to end and the item will be "
            "externally observable within 15 minutes. The institution will "
            "correctly reconcile the external observation against the receipt, "
            "and clean_verified_outcomes will move from 0 to 1."
        ),
        # Deliberately not 0.9. The chain has never run against reality once,
        # and the honest prior for a first integration with an external
        # platform is closer to a coin flip than to confidence. A high number
        # here would be the first thing miscalibrated.
        predicted_confidence=0.55,
        success_criteria=(
            "the Consequence Gate reaches `committed` and emits a receipt",
            "the published item is retrievable by an observer outside this "
            "process, by its own identifier",
            "the retrieved content digest equals the digest recorded in the "
            "witness payload_hash",
            "an OutcomeRecord is written with validation_status "
            "externally_verified and an observer identity distinct from the "
            "acting identity",
            "clean_verified_outcomes(ledger) == 1",
        ),
        failure_criteria=(
            "the item is not retrievable within 15 minutes",
            "the retrieved digest differs from the witness payload_hash",
            "the platform returns success but no item exists (a claimed effect "
            "with no consequence — the exact failure this canary exists to "
            "detect)",
            "the only party attesting the outcome is the actor that performed "
            "it (self-attestation is refused by Bridge D and is a FAILURE of "
            "the run, not a retry condition)",
            "reconciliation cannot distinguish 'executed' from 'consequence "
            "exists'",
        ),
        kill_conditions=(
            "any effect outside the single declared target",
            "any spend, at all — the budget is zero and a non-zero charge means "
            "the exposure model is wrong",
            "the item cannot be deleted on demand",
            "any second publication without a second authorization",
            "the acting identity differs from the declared identity",
        ),
    ),
    capability="daleobanks.publish.single_item",
    authority_required=(
        "a single-use capability grant naming this exact target, issued under a "
        "founder authorization that does not yet exist"
    ),
    consequence_class="external_contact",
    budget_usd=0.0,
    exposure_ceiling_usd=0.0,
    identity="spiffe://uniimente.internal/organ/daleobanks/bridge",
    kill_switch=(
        "Revoke the single-use grant. The grant is single-use with a 15-minute "
        "TTL, so the window closes by itself; revocation closes it immediately. "
        "Constitutional shutdown remains available and supersedes."
    ),
    reconciliation_method=(
        "Fetch the published item by its identifier from outside this process "
        "and compare its content digest against the witness `payload_hash`. "
        "Digest equality, not 'the request returned 200' — a platform "
        "acknowledging a write is not evidence the write exists."
    ),
    external_verification_method=(
        "An observer identity distinct from the acting identity records the "
        "OutcomeRecord. Bridge D refuses self-attestation, so a run the actor "
        "verifies alone cannot raise clean_verified_outcomes however green it "
        "looks."
    ),
    rollback=(
        "Delete the published item. Incomplete by nature and stated as such: a "
        "reader may have seen it and a cache may retain it. This is the residue "
        "that makes the content bound part of the design rather than a "
        "formality — the item must be something whose persistence is harmless."
    ),
    # -- CONTRADICTION-0003 Option A, ratified 2026-08-23 --------------------
    # The two numbers this packet now carries, and why they differ:
    #
    #   predicted_confidence  0.55  (sealed, unchanged) — will it work?
    #   evidence_confidence   0.85  (here)              — are we right to try?
    #
    # 0.55 was never a measure of how well-evidenced the decision was; it was
    # the only field available, so it carried both. The argument for running
    # CANARY-0001 is strong *because* the outcome is uncertain — the
    # uncertainty is the reason the experiment exists.
    #
    # 0.85 rather than higher: the residual is real and named in `rollback`.
    # Deletion is incomplete, a reader may have seen the item, a cache may
    # retain it. An institution claiming 0.95 for its first external act would
    # be making the same error in the other field.
    evidence_confidence=0.85,
    evidence_basis=(
        "selected by score over five candidates with written arguments "
        "(graduation/candidates.py): CAN-A 24, CAN-C 22 — not suggested, "
        "compared",
        "budget_usd is 0.0 and exposure_ceiling_usd is 0.0: nothing is spent "
        "and nothing can be",
        "single-use grant with a 15-minute TTL: the window closes by itself "
        "even if revocation is never issued",
        "reconciliation is a digest comparison, not a status code, so the "
        "run can be shown WRONG rather than merely finished",
        "external verification requires an observer identity distinct from "
        "the acting identity; Bridge D refuses self-attestation",
        "the content bound makes the acknowledged rollback residue harmless, "
        "which is why the residue is a design parameter and not a defect",
        "the institution cannot calibrate any prediction without one external "
        "outcome, so the information value is structural rather than nice to "
        "have",
    ),
    bridge_path=(
        "Bridge B: ExperimentSpec with an approval requirement (granted=False)",
        "founder authorization (ABSENT — the blocker)",
        "Bridge C: compile -> Consequence Gate -> witness -> execute -> receipt",
        "external observation by a distinct identity",
        "Bridge D: ValidationResult -> DecisionEpisode -> causal memory",
        "calibration: predicted 0.55 joined against the realised outcome",
        "Capability Genome update via Bridge G",
    ),
    notes=(
        "Selected by comparison in graduation/candidates.py, not because it was "
        "suggested. CAN-C (signed artifact) scores higher on verification "
        "objectivity and lower on system relevance, and is the recommended "
        "second canary.",
        "Witness contract v2 must be EMITTED before this runs, or the "
        "predicted_confidence above cannot be joined to the outcome and the "
        "calibration half of the run yields nothing. That is blocked on "
        "CONTRADICTION-0002.",
        "This packet is a proposal. It is not an authorization and confers "
        "nothing.",
    ),
)

#: The seal over the preregistration only. Pinned so an edit to what counts as
#: success fails the build instead of quietly redefining the experiment.
PREREGISTRATION_SHA256 = PACKET.preregistration.seal()


def blockers() -> tuple[str, ...]:
    """Exactly what stands between this packet and a real run.

    Reported rather than implied. Each is a thing no build session can supply,
    which is the founder's own blocker discipline applied to this packet.
    """
    from governance import gap_audit

    from policy.engine import EVIDENCE_THRESHOLDS

    found = ["founder authorization to execute an external consequence "
             "(explicitly withheld by ruling 8)",
             "a live DALEOBANKS platform credential",
             "a public network surface, which is founder-gated (#31 transport "
             "half is absent by design)"]

    # CONTRADICTION-0003, resolved 2026-08-23 (FOUNDER-RULING-2026-08-23,
    # Options A+B). The Gate used to refuse this packet because one field
    # carried two quantities: a preregistered success prediction of 0.55 was
    # being measured against an admission floor of 0.70.
    #
    # The check is kept and now asks the RIGHT question — is the decision to act
    # sufficiently evidenced — rather than being deleted. If a future edit drops
    # `evidence_confidence` below the floor, this blocker returns, and the fix
    # then is more evidence, never a larger number.
    floor = EVIDENCE_THRESHOLDS.get(PACKET.consequence_class, 0.0)
    if PACKET.evidence_confidence < floor:
        found.append(
            f"the Consequence Gate refuses this packet: evidence confidence "
            f"{PACKET.evidence_confidence} is below the {floor} floor for "
            f"{PACKET.consequence_class}. The remedy is stronger evidence in "
            f"`evidence_basis`, never a larger number.")

    still_open, detail = gap_audit._witness_v2_is_not_emitted()
    if still_open:
        found.append(f"witness contract v2 is not emitted: {detail}")
    return tuple(found)


def resolved_blockers() -> tuple[str, ...]:
    """What used to be on the list above, and what took it off.

    Kept because a blocker list that silently shortens is indistinguishable
    from one nobody is maintaining. A reader comparing this packet against the
    2026-08-22 version must be able to see which walls came down and why —
    especially since neither of these was removed by relaxing anything.
    """
    return (
        "the Consequence Gate refused the packet on a 0.55 predicted "
        "confidence against a 0.70 floor — RESOLVED by CONTRADICTION-0003 "
        "Options A+B: the two quantities are separate fields now. The floor is "
        "unchanged at 0.70, the sealed prediction is unchanged at 0.55, and "
        "admission is judged on evidence_confidence with its itemised basis. "
        "Option B additionally REQUIRES containment to be declared, so the "
        "packet must clear more than it did before, not less.",
        "witness contract v2 was built but not emitted — RESOLVED by "
        "CONTRADICTION-0002 Option A, which unblocked "
        "policy/consequence_gate.py by freezing the historical continuity "
        "corpus. The Gate now emits all four v2 facts.",
    )


def render() -> str:
    """The one-screen graduation decision the ruling asked to be brought back."""
    p = PACKET
    pre = p.preregistration
    lines = [
        "=" * 74,
        "EXTERNAL REALITY GRADUATION PACKET — CANARY-0001",
        "=" * 74,
        f"  {p.summary}",
        "",
        f"  preregistration seal : {p.sealed[:32]}…",
        f"  authorized           : {p.is_authorized}  (founder-gated)",
        "",
        "PREREGISTERED PREDICTION",
        f"  {pre.prediction}",
        f"  confidence: {pre.predicted_confidence}",
        "",
        "SUCCEEDS ONLY IF ALL OF:",
    ]
    lines += [f"  - {c}" for c in pre.success_criteria]
    lines += ["", "FAILS IF ANY OF:"]
    lines += [f"  - {c}" for c in pre.failure_criteria]
    lines += ["", "KILL IMMEDIATELY IF ANY OF:"]
    lines += [f"  - {c}" for c in pre.kill_conditions]
    lines += [
        "",
        "ENVELOPE",
        f"  capability        {p.capability}",
        f"  consequence class {p.consequence_class}",
        f"  budget / ceiling  ${p.budget_usd:.2f} / ${p.exposure_ceiling_usd:.2f}",
        f"  identity          {p.identity}",
        f"  kill switch       {p.kill_switch}",
        f"  rollback          {p.rollback}",
        "",
        "BRIDGE PATH",
    ]
    lines += [f"  {i + 1}. {step}" for i, step in enumerate(p.bridge_path)]
    lines += ["", "BLOCKERS — none of these can be cleared by a build session:"]
    lines += [f"  - {b}" for b in blockers()]
    lines += ["", EXECUTION_STATUS, ""]
    lines.append(f"Candidate comparison: {selected().candidate_id} selected of "
                 f"5 considered (python -m graduation.candidates).")
    return "\n".join(lines)


if __name__ == "__main__":  # pragma: no cover - operator entry point
    print(render())
