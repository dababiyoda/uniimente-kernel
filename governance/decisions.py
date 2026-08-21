"""What is waiting on the founder, and what happens while it waits.

The institution accumulated four deliberation records before anything could
report them. Every operator surface could say what the ladder claimed, which
organs were connected, and how many cycles had unlocked nothing — and none of
them could say that three constitutional questions were sitting unanswered in
`docs/deliberations/`. A decision nobody can see is not escalated; it is
mislaid.

Three properties this reader enforces, because the records cannot enforce them
on themselves:

**A record does not approve itself.** `approval_status: "approved"` counts only
when the record also names `authorized_by` and `authorization_ref`. A record
claiming approval without both is reported as UNAUTHORIZED_CLAIM — a *louder*
state than pending, not a quieter one, because a record asserting an approval it
cannot substantiate is worse than one honestly waiting. This is the same rule
`tests/unit/test_governance_records.py` asserts; reader and guard agree by
construction rather than by coincidence.

**A pending decision must say what happens if nobody decides.** Not deciding is
itself a choice, and it is the choice that is in force right now. A record whose
`do_nothing_option.expected_outcome` is missing or empty cannot tell the founder
the cost of silence, so it is reported as incomplete rather than merely open.

**Nothing is aggregated away.** The report lists every decision by id, title and
question. A count is a summary of an escalation, never a substitute for one.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import Enum

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DELIBERATIONS = os.path.join(ROOT, "docs", "deliberations")

#: A decision verdict that, by itself, does not settle the record — the record
#: says in terms that a human has to answer.
_DEFERS_TO_HUMAN = "NEEDS_FOUNDER_DECISION"


class State(Enum):
    """The state of a deliberation record with respect to human authorization."""

    #: A human must answer and has not. The `do_nothing` option is in force.
    AWAITING_FOUNDER = "AWAITING_FOUNDER"
    #: A human answered, and the record carries who and where.
    AUTHORIZED = "AUTHORIZED"
    #: Settled without needing a human — no authority, money, identity or
    #: external effect at stake.
    SETTLED = "SETTLED"
    #: The record claims approval it cannot substantiate. Refused.
    UNAUTHORIZED_CLAIM = "UNAUTHORIZED_CLAIM"
    #: The record is missing a field this reader needs to classify it at all.
    MALFORMED = "MALFORMED"


#: States an operator must act on. Everything else is history.
OPEN_STATES = (State.AWAITING_FOUNDER, State.UNAUTHORIZED_CLAIM, State.MALFORMED)


@dataclass(frozen=True)
class OpenDecision:
    """One deliberation record, classified, with its unanswered question intact."""

    decision_id: str
    title: str
    state: State
    level: str
    decision: str
    owner: str
    #: What is in force right now because the decision has not been made. Empty
    #: when the record failed to say, which is itself reported.
    default_in_force: str
    #: Why the record is not simply open — the substantiation defect, if any.
    defect: str = ""

    @property
    def is_open(self) -> bool:
        return self.state in OPEN_STATES

    def headline(self) -> str:
        if self.state is State.AWAITING_FOUNDER:
            return f"{self.decision_id} ({self.level}) — {self.title}"
        return f"{self.decision_id} ({self.state.value}) — {self.title}"


def _classify(record: dict) -> tuple[State, str]:
    """Classify one record. Returns the state and any substantiation defect.

    Order matters. An unsubstantiated approval is checked *before* the pending
    branch, so a record cannot escape scrutiny by claiming approval: claiming it
    without backing is a worse state than not claiming it.
    """
    impact = record.get("authority_impact")
    if not isinstance(impact, dict) or "decision" not in record:
        return State.MALFORMED, "no authority_impact block or no decision field"

    status = impact.get("approval_status")
    requires_human = bool(impact.get("requires_authorized_human"))

    if status == "approved":
        by = (impact.get("authorized_by") or "").strip()
        ref = (impact.get("authorization_ref") or "").strip()
        if not by or not ref:
            missing = [n for n, v in (("authorized_by", by),
                                      ("authorization_ref", ref)) if not v]
            return (State.UNAUTHORIZED_CLAIM,
                    "claims approved without " + " and ".join(missing))
        return State.AUTHORIZED, ""

    if record.get("decision") == _DEFERS_TO_HUMAN or requires_human:
        return State.AWAITING_FOUNDER, ""

    return State.SETTLED, ""


def _default_in_force(record: dict) -> str:
    """What the record says happens if nobody decides. Never invented."""
    do_nothing = record.get("do_nothing_option")
    if not isinstance(do_nothing, dict):
        return ""
    return (do_nothing.get("expected_outcome") or "").strip()


def load_all(directory: str = DELIBERATIONS) -> tuple[OpenDecision, ...]:
    """Read and classify every deliberation record, in id order.

    A file that is not valid JSON is surfaced as MALFORMED rather than skipped.
    A reader that quietly drops the records it cannot parse reports a cleaner
    institution than the one that exists.
    """
    out: list[OpenDecision] = []
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(directory, name)
        try:
            with open(path, encoding="utf-8") as fh:
                record = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            out.append(OpenDecision(
                decision_id=name, title=name, state=State.MALFORMED,
                level="unknown", decision="unknown", owner="unknown",
                default_in_force="", defect=f"unreadable: {exc}",
            ))
            continue
        if not isinstance(record, dict):
            out.append(OpenDecision(
                decision_id=name, title=name, state=State.MALFORMED,
                level="unknown", decision="unknown", owner="unknown",
                default_in_force="", defect="record is not an object",
            ))
            continue

        state, defect = _classify(record)
        impact = record.get("authority_impact")
        level = (impact or {}).get("level", "unknown") if isinstance(impact, dict) \
            else "unknown"
        default = _default_in_force(record)
        if state is State.AWAITING_FOUNDER and not default:
            defect = "open, and does not state what is in force while it waits"

        out.append(OpenDecision(
            decision_id=record.get("decision_id", name),
            title=record.get("title", name),
            state=state,
            level=level,
            decision=record.get("decision", "unknown"),
            owner=record.get("decision_owner", "unassigned"),
            default_in_force=default,
            defect=defect,
        ))
    return tuple(sorted(out, key=lambda d: d.decision_id))


def open_decisions(records: tuple[OpenDecision, ...] | None = None
                   ) -> tuple[OpenDecision, ...]:
    """Only the records an operator must act on."""
    return tuple(d for d in (records if records is not None else load_all())
                 if d.is_open)


def by_state(records: tuple[OpenDecision, ...] | None = None) -> dict[State, int]:
    """Every state, including the ones at zero.

    States at zero are reported because their absence is the claim worth
    checking: a run with no UNAUTHORIZED_CLAIM rows says something, and a table
    that omits empty rows cannot say it.
    """
    found = records if records is not None else load_all()
    counts = {state: 0 for state in State}
    for record in found:
        counts[record.state] += 1
    return counts


def render() -> str:
    """The operator's view. Every open decision, with its unanswered question."""
    records = load_all()
    counts = by_state(records)
    lines = [
        f"deliberation records : {len(records)}",
        "  " + "  ".join(f"{s.value}={counts[s]}" for s in State),
        "",
    ]
    still_open = open_decisions(records)
    if not still_open:
        lines.append("no decision is waiting on a human")
        return "\n".join(lines)

    lines.append(f"{len(still_open)} decision(s) waiting:")
    for record in still_open:
        lines.append(f"  {record.headline()}")
        lines.append(f"    owner   : {record.owner}")
        if record.default_in_force:
            lines.append(f"    in force: {record.default_in_force}")
        if record.defect:
            lines.append(f"    DEFECT  : {record.defect}")
    return "\n".join(lines)


if __name__ == "__main__":  # pragma: no cover - operator entry point
    print(render())
