"""Which first external act teaches the most for the least exposure.

FOUNDER-RULING-2026-08-22, ruling 8:

> A likely candidate may be one narrowly bounded DALEOBANKS publication because
> it can test sensing → decision → authorization → public action → external
> observation → reconciliation → causal learning without financial custody. But
> do not choose it just because I mentioned it — compare it against the
> strongest alternatives and select based on information value, reversibility
> and relevance to the complete system.

So the comparison is real, the founder's suggestion competes on the same terms
as everything else, and the scoring is recorded whether or not it agrees.

## The question a first canary has to answer

Not "can we reach the internet". The wall this institution has built is about
**consequences**, and the specific thing nobody knows is whether the governed
path survives contact with reality — most precisely, whether **reconciliation
can distinguish "we did it" from "it worked"**.

That reframing does most of the selection work. A canary whose external
observation cannot disagree with the internal record teaches nothing about the
mechanism that matters, however cheap it is.

## Scoring

Each candidate is scored on the three axes the founder named plus the two the
constraints impose. Scores are 0–5, hand-assigned, and the reasoning is written
out per candidate rather than compressed into the number — a table of numbers
with no argument is how a predetermined answer gets dressed as an analysis.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    """One possible first external act, scored and argued."""

    candidate_id: str
    summary: str
    #: Can the outside world's answer CONTRADICT our internal record? This is
    #: the axis that matters most and the one most easily overlooked.
    information_value: int
    #: How completely can it be undone, and how fast?
    reversibility: int
    #: Does it exercise the institution we are actually building, or a corner?
    system_relevance: int
    #: Money, legal exposure, counterparty obligation.
    cost_and_exposure: int
    #: Can it be done lawfully with what the founder already controls?
    lawfulness: int
    argument: str
    disqualifier: str = ""

    @property
    def total(self) -> int:
        return (self.information_value + self.reversibility
                + self.system_relevance + self.cost_and_exposure
                + self.lawfulness)

    @property
    def eligible(self) -> bool:
        return not self.disqualifier


CANDIDATES: tuple[Candidate, ...] = (
    Candidate(
        candidate_id="CAN-A-publication",
        summary=("Publish one narrowly bounded item to a DALEOBANKS-owned "
                 "channel, then observe it externally and reconcile."),
        information_value=5,
        reversibility=4,
        system_relevance=5,
        cost_and_exposure=5,
        lawfulness=5,
        argument=(
            "The external observation can genuinely disagree with the internal "
            "record, in more than one way: the item can fail to appear, appear "
            "mangled, appear and be removed, or appear with a different "
            "identifier than the receipt claims. Each is a distinct "
            "reconciliation outcome, so a single run distinguishes 'the action "
            "executed' from 'the intended consequence exists' — which is the "
            "one thing no internal test can establish. It exercises the organ "
            "the architecture designates for distribution, so what it proves "
            "transfers to Bridge F rather than to a corner of the system. "
            "Reversible by deletion, though not perfectly: a reader may have "
            "seen it, and a cached copy may persist. That residue is real and "
            "is the reason for content bounds rather than a reason to reject."
        ),
    ),
    Candidate(
        candidate_id="CAN-B-readonly-fetch",
        summary="Fetch one public document and record it as evidence.",
        information_value=1,
        reversibility=5,
        system_relevance=2,
        cost_and_exposure=5,
        lawfulness=5,
        argument=(
            "The cheapest and most reversible option by a wide margin — nothing "
            "outside changes, so there is nothing to undo. And that is exactly "
            "why it is the wrong first canary: with no external consequence "
            "there is nothing for reconciliation to reconcile, and the "
            "Consequence Gate is never actually tested. It would raise CVO by "
            "zero and answer none of the open question. Genuinely useful "
            "later, as the sensing half of Bridge A; not a graduation."
        ),
    ),
    Candidate(
        candidate_id="CAN-C-signed-artifact",
        summary=("Publish a content-addressed signed artifact to a public "
                 "repository, verify by fetching and comparing its digest."),
        information_value=4,
        reversibility=5,
        system_relevance=3,
        cost_and_exposure=5,
        lawfulness=5,
        argument=(
            "The strongest genuine rival, and better than CAN-A on the axis "
            "that usually decides these things: external verification is a "
            "digest comparison, so 'did the intended thing exist' has an exact "
            "answer with no judgement in it. Fully reversible by deletion, and "
            "cheap. It loses on system relevance — publishing a blob to a code "
            "host exercises a path the architecture does not otherwise use, so "
            "what it proves about the Gate transfers, and what it proves about "
            "distribution does not. Recommended as the SECOND canary, where its "
            "objectivity is worth more once the first has shown the chain runs "
            "at all."
        ),
    ),
    Candidate(
        candidate_id="CAN-D-counterparty-email",
        summary="Send one message to a consenting external counterparty.",
        information_value=4,
        reversibility=1,
        system_relevance=4,
        cost_and_exposure=3,
        lawfulness=3,
        argument=(
            "Tests the full chain and adds a real counterparty, which is where "
            "Bridge F ultimately has to go. But a sent message cannot be "
            "unsent, so the reversibility that makes a first canary safe is "
            "absent, and it requires a consenting human whose time is a real "
            "cost. The right third step, not the first."
        ),
    ),
    Candidate(
        candidate_id="CAN-E-micropayment",
        summary="Execute one minimal real payment and reconcile against a balance.",
        information_value=5,
        reversibility=1,
        system_relevance=4,
        cost_and_exposure=1,
        lawfulness=2,
        argument=(
            "Maximally informative, and it is worth being precise about why "
            "rather than waving at it. Money is the least forgiving "
            "reconciliation there is: a balance is an external fact held by a "
            "third party who has no interest in agreeing with us, so 'we think "
            "we paid' and 'the money moved' cannot blur. Nothing else on this "
            "list has an adversarial verifier. Technologies #38, #39 and #55 "
            "all wait on it, so it would unblock more of the ladder than every "
            "other candidate combined. It is also irreversible in the way that "
            "matters — a sent payment is a completed transfer, and the recourse "
            "is a request to a counterparty rather than a delete. And it is the "
            "single thing the founder's standing constraints most explicitly "
            "forbid. Scored and kept on the list precisely because it is the "
            "strongest option: dropping it would hide the fact that the "
            "institution is deliberately not running its most decisive "
            "experiment."
        ),
        disqualifier=(
            "Requires money movement and fund custody, both excluded by the "
            "standing authorization boundary. Not eligible at any score."
        ),
    ),
)


def ranked() -> tuple[Candidate, ...]:
    """Eligible candidates, strongest first. Ineligible ones are not scored away.

    A disqualified candidate keeps its scores and its argument: recording that
    the most informative option is also the forbidden one is more useful than
    quietly dropping it, and it is the honest answer to "why not just do the
    decisive experiment".
    """
    return tuple(sorted((c for c in CANDIDATES if c.eligible),
                        key=lambda c: (-c.total, c.candidate_id)))


def selected() -> Candidate:
    """The recommended first canary. Selected by score, not by suggestion."""
    return ranked()[0]


def render() -> str:
    lines = ["FIRST-CANARY CANDIDATE COMPARISON", "=" * 74, ""]
    header = f"{'candidate':<26}{'info':>5}{'rev':>5}{'rel':>5}{'cost':>5}{'law':>5}{'total':>7}"
    lines.append(header)
    lines.append("-" * 74)
    for candidate in sorted(CANDIDATES, key=lambda c: (-c.total, c.candidate_id)):
        mark = "" if candidate.eligible else "  INELIGIBLE"
        lines.append(
            f"{candidate.candidate_id:<26}{candidate.information_value:>5}"
            f"{candidate.reversibility:>5}{candidate.system_relevance:>5}"
            f"{candidate.cost_and_exposure:>5}{candidate.lawfulness:>5}"
            f"{candidate.total:>7}{mark}")
    lines += ["", f"SELECTED: {selected().candidate_id}", "",
              selected().argument, ""]
    for candidate in CANDIDATES:
        if candidate.disqualifier:
            lines.append(f"INELIGIBLE {candidate.candidate_id}: "
                         f"{candidate.disqualifier}")
    return "\n".join(lines)


if __name__ == "__main__":  # pragma: no cover - operator entry point
    print(render())
