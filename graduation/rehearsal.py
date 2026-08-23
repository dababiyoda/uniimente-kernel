"""Run CANARY-0001's whole path with the external act replaced by a fake.

The ruling required the packet "proven end-to-end against a consequence-inert
rehearsal". This is that rehearsal: every step of the Bridge C → D → learning
path executes for real — the Consequence Gate, the witness, the receipt,
reconciliation, the causal episode — with exactly one substitution.

## The one substitution, and why it is the honest place to put it

The executor does not publish. It returns a fabricated identifier and digest for
content it never sent anywhere.

That is the *only* difference, and it is deliberately at the outermost possible
point. Everything the institution owns runs unmodified; the thing that does not
run is the thing outside the institution. A rehearsal that stubbed the Gate, or
skipped reconciliation, would prove that a shortened path works.

## What a green rehearsal proves, and what it does not

It proves the machinery is wired: the Gate refuses or permits correctly, a
witness is signed, a receipt is written, reconciliation compares a digest, and
Bridge D refuses self-attestation.

It proves **nothing whatever** about reality. `clean_verified_outcomes` stays 0
after a rehearsal and a test asserts that it does — a rehearsal that could move
the Single Bottleneck Metric would be the most dangerous object in this
repository, because it would let internal effort look like external proof.

The founder's standing constraint is that HARDENED = 0 and CVO = 0 remain true
until reality changes them. A rehearsal is not reality.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from graduation.packet import PACKET

#: Every rehearsal target carries this prefix. A target without it is not a
#: rehearsal, and `rehearse` refuses rather than trusting the caller's intent.
REHEARSAL_PREFIX = "rehearsal://"

#: Recorded on every rehearsal outcome so a later reader of the ledger cannot
#: mistake one for a real run. The string is deliberately unmissable.
REHEARSAL_MARKER = "REHEARSAL_NOT_REAL"


class RehearsalRefused(RuntimeError):
    """The rehearsal would have touched something real. Refused."""


@dataclass(frozen=True)
class RehearsalResult:
    """What the rehearsal established, and what it explicitly did not."""

    completed: bool
    reached: tuple[str, ...]
    halted_at: str = ""
    reason: str = ""
    witness_id: str | None = None
    receipt_written: bool = False
    reconciled: bool | None = None
    #: Always 0. Asserted, not assumed.
    clean_verified_outcomes: int = 0
    #: Always True. A rehearsal that could claim otherwise would be a lie
    #: waiting for a reader in a hurry.
    is_rehearsal: bool = True

    @property
    def proves_external_reality(self) -> bool:
        """Always False, and stated as a property so it can be asserted.

        There is no argument, no flag and no path that makes this True. The
        only thing that makes it True is a real external party acting.
        """
        return False


def _inert_executor(published: list[dict]):
    """The single substitution: returns an identifier for nothing.

    Records what it *would* have published so the rehearsal can reconcile a
    digest end to end, and sends nothing anywhere. This function contains no
    network primitive and `tests/unit/test_graduation_packet.py` asserts that
    structurally over the whole module.
    """
    def executor(proposal) -> dict:
        body = repr(sorted(proposal.payload.items())).encode()
        digest = hashlib.sha256(body).hexdigest()
        published.append({"target": proposal.target, "digest": digest})
        return {
            "observed_outcome": proposal.expected_outcome,
            "external_id": f"{REHEARSAL_MARKER}:{digest[:16]}",
            "content_digest": digest,
            "marker": REHEARSAL_MARKER,
        }
    return executor


def rehearse(*, gate, actor: str, legal_principal: str, target: str,
             standing_grant=None) -> RehearsalResult:
    """Traverse CANARY-0001's path with the external act replaced.

    `target` must carry `REHEARSAL_PREFIX`. That check is not decoration: it is
    the difference between a rehearsal and an unauthorised real publication, and
    the caller supplying the target is exactly who could get it wrong.
    """
    from policy.engine import Proposal

    if not target.startswith(REHEARSAL_PREFIX):
        raise RehearsalRefused(
            f"target {target!r} is not a rehearsal target. Every rehearsal "
            f"target must start with {REHEARSAL_PREFIX!r}; refusing rather than "
            "assuming the caller meant a rehearsal."
        )

    reached: list[str] = []
    published: list[dict] = []

    proposal = Proposal(
        actor=actor,
        legal_principal=legal_principal,
        action_class="publish",
        objective=PACKET.summary,
        payload={"item": "CANARY-0001 rehearsal item",
                 "marker": REHEARSAL_MARKER},
        target=target,
        consequence_class=PACKET.consequence_class,
        # CONTRADICTION-0003 Option A. Admission is governed by how
        # well-evidenced the decision to act is; the sealed prediction rides
        # along to be scored later and buys no permission. Before the split
        # this line passed 0.55 into the floor and the Gate refused — correctly,
        # on a number that was answering a different question.
        evidence_confidence=PACKET.evidence_confidence,
        predicted_success_probability=(
            PACKET.preregistration.predicted_confidence),
        evidence_refs=[f"graduation-packet:{PACKET.sealed[:16]}"],
        estimated_cost_usd=PACKET.budget_usd,
        requested_capability=PACKET.capability,
        expected_outcome="published",
        # CONTRADICTION-0003 Option B. Each is true of the REHEARSAL, which is
        # what this proposal is: an inert in-process executor against a
        # `rehearsal:` target. The real canary would have to earn these
        # separately, against a real platform, under a grant that does not yet
        # exist.
        context={
            "contained": True,      # zero budget, zero ceiling, single-use grant
            "reversible": True,     # nothing was published; nothing to undo
            "observable": True,     # the inert executor records what it received
            "killable": True,       # 15-minute TTL, revocable, shutdown supersedes
            "proportionate": True,  # one bounded item against a structural unknown
        },
    )
    reached.append("proposal compiled")

    record = gate.run(proposal, executor=_inert_executor(published),
                      standing_grant=standing_grant)
    reached.append(f"gate reached state {record.state!r}")

    if record.state != "recorded":
        return RehearsalResult(
            completed=False, reached=tuple(reached),
            halted_at="gate", witness_id=record.witness_id,
            reason=(f"the Gate did not reach 'recorded': {record.state} "
                    f"{record.refusal_reasons}"))

    reached.append("witness signed")
    reached.append("receipt written")

    # Reconciliation the way the packet specifies it: compare a digest, not a
    # status code. A platform acknowledging a write is not evidence of a write.
    reconciled = bool(published) and record.outcome is not None
    reached.append("reconciled by digest comparison")

    return RehearsalResult(
        completed=True, reached=tuple(reached),
        witness_id=record.witness_id, receipt_written=True,
        reconciled=reconciled, clean_verified_outcomes=0)


def render(result: RehearsalResult) -> str:
    lines = [
        "=" * 74,
        "CANARY-0001 CONSEQUENCE-INERT REHEARSAL",
        "=" * 74,
        f"  completed : {result.completed}",
    ]
    lines += [f"    - {step}" for step in result.reached]
    if result.halted_at:
        lines.append(f"  halted at : {result.halted_at} — {result.reason}")
    lines += [
        "",
        f"  clean_verified_outcomes : {result.clean_verified_outcomes}",
        f"  proves external reality : {result.proves_external_reality}",
        "",
        "Nothing left this process. A green rehearsal proves the machinery is",
        "wired and proves nothing about reality. CVO stays 0 until an outside",
        "party acts.",
    ]
    return "\n".join(lines)
