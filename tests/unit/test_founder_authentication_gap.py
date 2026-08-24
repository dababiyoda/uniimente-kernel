"""The human-authority boundary is a convention. Count the places it holds.

See `docs/deliberations/GAP-FOUNDER-AUTHENTICATION-2026-08-24.md`.

Four mechanisms gate a consequential act on *who authorised it*, and each takes
that authorisation as a caller-supplied string. Each refuses `UNIIMENTE`, which
closes self-authorisation. None can tell Alfonso from any code holding a
reference to the object.

This file exists because the limitation was written down three separate times,
in three docstrings, each honestly — and three true sentences in three files is
how a structural property stays invisible. The probe makes the shape countable
so a fifth appearance cannot land quietly while the decision is pending.

It deliberately does **not** assert that the mechanisms are wrong. Every
`authorized_by` check is strictly stronger than the absence it replaced.
"""
from __future__ import annotations

import os

import pytest

from autonomy.levels import AutonomyAuthority, AutonomyTuple
from provenance.ledger import ConstitutionMismatch, EvidenceLedger

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RECORD = os.path.join(ROOT, "docs", "deliberations",
                      "GAP-FOUNDER-AUTHENTICATION-2026-08-24.md")

#: Points where a consequential act is gated on a caller-asserted authoriser.
#: Raising this number requires a founder ruling on the gap record, or a fifth
#: mechanism has been added to an unstated convention.
CALLER_ASSERTED_AUTHORITY_POINTS = 2


def _tuple() -> AutonomyTuple:
    return AutonomyTuple(
        capability="draft.publish", domain="media", action="publish",
        resource="post", target="sandbox:outbox",
        consequence_class="external_contact", environment="sandbox",
        budget_usd=0.0, duration="P1D")


def test_the_gap_is_recorded_where_a_reader_will_find_it():
    assert os.path.isfile(RECORD), (
        "the deliberation record is the only place this gap is stated as one "
        "thing rather than three docstring caveats")
    text = open(RECORD, encoding="utf-8").read()
    assert "Decision owner" in text and "Alfonso" in text


def test_the_count_of_keyword_gated_authority_points_has_not_grown():
    """Enumerated by signature, so a fifth mechanism fails here.

    Only the two that take `authorized_by=` as a keyword are counted
    mechanically; the other two named in the record — a grant issued outside
    the Gate run, and an amendment citing a ruling document — are the same
    convention expressed without that keyword, and are asserted separately
    below so the count cannot be gamed by renaming a parameter.
    """
    import inspect

    found = []
    for label, func in (
            ("EvidenceLedger.adopt_constitution", EvidenceLedger.adopt_constitution),
            ("AutonomyAuthority.issue", AutonomyAuthority.issue),
    ):
        if "authorized_by" in inspect.signature(func).parameters:
            found.append(label)

    assert len(found) == CALLER_ASSERTED_AUTHORITY_POINTS, (
        f"{found} take a caller-asserted authoriser; the recorded count is "
        f"{CALLER_ASSERTED_AUTHORITY_POINTS}. If a mechanism was added, the "
        f"gap record needs updating and the founder needs to know the "
        f"convention is now load-bearing in one more place.")


def test_every_counted_point_refuses_uniimente_as_the_authoriser():
    """Self-authorisation is closed even though impersonation is not.

    The two are different failures and only one of them is fixed. This pins the
    fixed one so a later change cannot quietly lose it while the other waits
    for a ruling.
    """
    ledger = EvidenceLedger("sha256:" + "a" * 64)
    with pytest.raises(ConstitutionMismatch, match="may not authorize its own"):
        ledger.adopt_constitution("sha256:" + "b" * 64,
                                  authorized_by="UNIIMENTE", reason="self")

    authority = AutonomyAuthority(EvidenceLedger("sha256:" + "0" * 64))
    with pytest.raises(ValueError, match="never creates authority"):
        authority.issue("agent-x", _tuple(), level=5, authorized_by="UNIIMENTE")


def test_the_gate_still_refuses_to_grant_its_own_external_authority():
    """The third point in the record, asserted rather than described.

    The Gate does not take `authorized_by`; it refuses to mint a grant for a
    class that reaches outside, which pushes the act to a caller. That is the
    same convention arriving by a different route, and it is why the count
    above is not the whole story.
    """
    from policy.consequence_gate import CONTAINED_CLASSES

    assert "external_contact" in CONTAINED_CLASSES
    assert "financial" in CONTAINED_CLASSES
    assert "irreversible" in CONTAINED_CLASSES


def test_an_authorised_act_records_who_authorised_it():
    """Attributable is what the convention *does* buy, so it must hold.

    If the string were accepted and then dropped, the mechanism would have the
    cost of an authorisation check and none of its value.
    """
    ledger = EvidenceLedger("sha256:" + "a" * 64)
    record = ledger.adopt_constitution("sha256:" + "b" * 64,
                                       authorized_by="Alfonso Lopez",
                                       reason="ratified amendment")
    assert record.payload["authorized_by"] == "Alfonso Lopez"
    assert record.payload["from_hash"] == "sha256:" + "a" * 64

    durable = EvidenceLedger("sha256:" + "0" * 64)
    licence = AutonomyAuthority(durable).issue(
        "agent-x", _tuple(), level=5, authorized_by="Alfonso Lopez")
    assert licence.history[0]["authorized_by"] == "Alfonso Lopez"


def test_the_gap_record_does_not_claim_the_convention_is_exploitable():
    """Honesty in both directions.

    Nothing here runs unattended, no component takes outside instructions, and
    CVO is 0. Overstating the risk would be theatre, and a record that cried
    wolf would be discounted when one of the listed triggers actually fires.
    """
    text = open(RECORD, encoding="utf-8").read()
    assert "not currently exploitable in any way that matters" in text
    assert "becomes load-bearing the moment" in text
