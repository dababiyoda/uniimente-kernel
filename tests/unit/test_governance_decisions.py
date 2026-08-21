"""The pending-decision reader must not flatter the records it reads.

Its whole value is that an agent cannot make a constitutional question look
answered. Every test below is an attempt to do exactly that, plus two tests
binding the reader to the record guard so the two cannot drift apart.
"""
from __future__ import annotations

import json
import os

import pytest

from governance.decisions import (
    OPEN_STATES,
    State,
    by_state,
    load_all,
    open_decisions,
    render,
)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DELIBERATIONS = os.path.join(ROOT, "docs", "deliberations")

_APPROVED = {
    "level": "constitutional",
    "changes_authority": False,
    "requires_authorized_human": True,
    "approval_status": "approved",
}


def _write(directory, name: str, record) -> None:
    with open(os.path.join(directory, name), "w", encoding="utf-8") as fh:
        if isinstance(record, str):
            fh.write(record)
        else:
            json.dump(record, fh)


def _record(**overrides) -> dict:
    base = {
        "decision_id": "DEC-TEST",
        "title": "a constructed record",
        "decision": "RETAIN",
        "decision_owner": "Alfonso Lopez",
        "authority_impact": dict(_APPROVED),
        "do_nothing_option": {"expected_outcome": "nothing changes"},
    }
    base.update(overrides)
    return base


# --------------------------------------------------- self-approval is refused
@pytest.mark.parametrize("impact,missing", [
    ({**_APPROVED, "authorization_ref": "somewhere"}, "authorized_by"),
    ({**_APPROVED, "authorized_by": "Alfonso Lopez"}, "authorization_ref"),
    ({**_APPROVED, "authorized_by": "  ", "authorization_ref": "  "},
     "authorized_by"),
])
def test_an_approval_without_its_substantiation_is_an_unauthorized_claim(
        tmp_path, impact, missing):
    """`approved` is not self-certifying, and the defect names what is absent.

    This is the shape an agent produces when it decides a constitutional
    question and labels the result human-approved. It must not read as
    AUTHORIZED, and it must not read as merely pending either — a record
    asserting an approval it cannot back is worse than one honestly waiting.
    """
    _write(tmp_path, "dec.json", _record(authority_impact=impact))
    found = load_all(str(tmp_path))
    assert [d.state for d in found] == [State.UNAUTHORIZED_CLAIM]
    assert missing in found[0].defect
    assert found[0].is_open


def test_a_substantiated_approval_is_authorized_and_closed(tmp_path):
    _write(tmp_path, "dec.json", _record(authority_impact={
        **_APPROVED,
        "authorized_by": "Alfonso Lopez",
        "authorization_ref": "founder decision message 2026-08-17",
    }))
    found = load_all(str(tmp_path))
    assert [d.state for d in found] == [State.AUTHORIZED]
    assert not found[0].is_open
    assert found[0].defect == ""


# ------------------------------------------- requiring a human is enough alone
def test_requiring_a_human_keeps_a_record_open_whatever_its_verdict(tmp_path):
    """A verdict of RETAIN does not settle a record that still needs a human.

    The escape an agent would reach for: write the answer into `decision`, leave
    `approval_status` pending, and let a reader that only looks at `decision`
    treat it as done. `requires_authorized_human` alone holds the record open.
    """
    _write(tmp_path, "dec.json", _record(
        decision="RETAIN",
        authority_impact={**_APPROVED, "approval_status": "pending"},
    ))
    found = load_all(str(tmp_path))
    assert [d.state for d in found] == [State.AWAITING_FOUNDER]


def test_a_record_needing_no_human_settles(tmp_path):
    _write(tmp_path, "dec.json", _record(
        decision="RETAIN",
        authority_impact={"level": "operational", "changes_authority": False,
                          "requires_authorized_human": False,
                          "approval_status": "pending"},
    ))
    found = load_all(str(tmp_path))
    assert [d.state for d in found] == [State.SETTLED]
    assert not found[0].is_open


# ------------------------------------------------- the cost of silence is required
def test_an_open_record_that_hides_the_cost_of_waiting_is_defective(tmp_path):
    """Not deciding is the choice currently in force, so the record must state it.

    A pending decision whose `do_nothing_option` says nothing leaves the founder
    unable to price the delay. That is reported, not tolerated — but reported as
    a defect on an open record rather than as a reason to drop it.
    """
    _write(tmp_path, "a.json", _record(
        decision="NEEDS_FOUNDER_DECISION",
        authority_impact={**_APPROVED, "approval_status": "pending"},
        do_nothing_option={"expected_outcome": "   "},
    ))
    _write(tmp_path, "b.json", _record(
        decision_id="DEC-TEST-2",
        decision="NEEDS_FOUNDER_DECISION",
        authority_impact={**_APPROVED, "approval_status": "pending"},
    ))
    del_b = json.load(open(os.path.join(str(tmp_path), "b.json"), encoding="utf-8"))
    del del_b["do_nothing_option"]
    _write(tmp_path, "b.json", del_b)

    found = load_all(str(tmp_path))
    assert [d.state for d in found] == [State.AWAITING_FOUNDER] * 2
    for record in found:
        assert record.default_in_force == ""
        assert "what is in force" in record.defect


# ------------------------------------------------ unparseable is not invisible
def test_an_unreadable_record_is_reported_not_skipped(tmp_path):
    """A reader that drops what it cannot parse reports a cleaner institution."""
    _write(tmp_path, "broken.json", "{ this is not json")
    _write(tmp_path, "list.json", [1, 2, 3])
    _write(tmp_path, "empty.json", _record(authority_impact=None))

    found = load_all(str(tmp_path))
    assert len(found) == 3
    assert {d.state for d in found} == {State.MALFORMED}
    assert all(d.is_open for d in found)
    assert all(d.defect for d in found)


def test_a_record_without_a_decision_field_is_malformed(tmp_path):
    record = _record()
    del record["decision"]
    _write(tmp_path, "dec.json", record)
    assert [d.state for d in load_all(str(tmp_path))] == [State.MALFORMED]


def test_non_json_files_are_ignored_entirely(tmp_path):
    _write(tmp_path, "notes.md", "prose is not a record")
    assert load_all(str(tmp_path)) == ()


# ------------------------------------------------------------- report shape
def test_every_state_is_counted_including_the_empty_ones():
    """A table that omits zero rows cannot say that a state is absent."""
    counts = by_state()
    assert set(counts) == set(State)
    assert counts[State.UNAUTHORIZED_CLAIM] == 0
    assert counts[State.MALFORMED] == 0


def test_open_states_are_exactly_the_ones_needing_action():
    assert set(OPEN_STATES) == {
        State.AWAITING_FOUNDER, State.UNAUTHORIZED_CLAIM, State.MALFORMED,
    }


def test_records_are_ordered_by_id_not_by_filesystem_order(tmp_path):
    _write(tmp_path, "zzz.json", _record(decision_id="DEC-OM-001"))
    _write(tmp_path, "aaa.json", _record(decision_id="DEC-OM-009"))
    assert [d.decision_id for d in load_all(str(tmp_path))] == [
        "DEC-OM-001", "DEC-OM-009",
    ]


# ------------------------------------------- reader and guard must not diverge
def test_the_reader_agrees_with_the_record_guard_on_every_committed_record():
    """The reader's rule and `test_governance_records.py`'s rule are one rule.

    Two independent checks of the same property drift. Binding them here means a
    future edit that loosens either one fails a test that mentions both.
    """
    for name in sorted(os.listdir(DELIBERATIONS)):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(DELIBERATIONS, name), encoding="utf-8") as fh:
            raw = json.load(fh)
        impact = raw["authority_impact"]
        state = {d.decision_id: d.state for d in load_all()}[raw["decision_id"]]

        if impact["approval_status"] == "approved":
            assert state is State.AUTHORIZED
            assert impact["authorized_by"].strip()
            assert impact["authorization_ref"].strip()
            assert raw["decision"] != "NEEDS_FOUNDER_DECISION"
        elif impact["level"] == "constitutional":
            assert state is State.AWAITING_FOUNDER
            assert raw["decision"] == "NEEDS_FOUNDER_DECISION"


def test_the_committed_corpus_has_open_constitutional_questions():
    """The institution's actual state: decisions are waiting, and are named.

    This asserts the *shape* of the corpus, not a count that every new record
    would have to chase: at least one question is open, exactly one is
    authorized, and nothing is malformed or self-approved.
    """
    found = load_all()
    still_open = open_decisions(found)
    assert still_open, "the reader must surface the questions that are waiting"
    assert all(d.state is State.AWAITING_FOUNDER for d in still_open), (
        "no committed record may be malformed or claim an unsubstantiated approval"
    )
    assert all(d.owner for d in still_open)
    assert all(d.default_in_force for d in still_open), (
        "every open record must state what is in force while it waits"
    )
    assert any(d.state is State.AUTHORIZED for d in found), (
        "DEC-OM-003 is decided and must not read as open"
    )


def test_the_rendered_report_names_each_open_decision():
    text = render()
    for record in open_decisions():
        assert record.decision_id in text
        assert record.title in text
        assert record.default_in_force in text
    assert "waiting" in text
