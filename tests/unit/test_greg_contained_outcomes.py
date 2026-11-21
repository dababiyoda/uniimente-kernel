"""Settlement withholds competence that rests on an impugned measurement (S45-A's ``contained_receipts``, #270).

The agreed hook: an outcome whose observation receipt a recorded correction impugns (REPLICATION_FAILED,
APPRAISAL_REFUTED, FOUNDER_REJECTED, not requalified) leaves ``measured_outcomes``; ``reconcile`` closes its
settlement once, naming the cause, as withheld rather than wrong; other outcomes of the same method still count; a
requalified receipt settles again; a body without ``greg.corrections`` is unchanged. The stand-in module below stands
for #270's; the last test uses #270's own module when this tree carries it. Values are synthetic test inputs.
"""
from __future__ import annotations

import sys
from types import ModuleType

import pytest

from greg.cognition import settlement
from tests.unit.test_greg_outcome_resolution import signed_commands  # noqa: F401  (autouse fixture)
from tests.unit.test_greg_pending_construction_realization import Journal, answer, appraise, observe, pending


@pytest.fixture(autouse=True)
def reconcilable(monkeypatch):
    """The fixture journal, able to take reconcile's keyed, causally linked records."""
    def record(self, kind, payload, key=None, sensitivity=None, causal_parent=None):
        from types import SimpleNamespace
        if key is not None and any(e.key == repr(key) for e in self.events if hasattr(e, "key")):
            return None
        event = SimpleNamespace(type="greg." + kind, payload=payload, key=repr(key), event_id=f"e:{len(self.events)}")
        self.events.append(event)
        return event
    monkeypatch.setattr(Journal, "record", record)


def two_answers():
    """Two certified answers of one method, each observed and appraised VERIFIED."""
    journal, first = pending()
    second = answer(journal, result={"profit": 3})
    observe(journal, second)
    appraise(journal, "VERIFIED")
    return journal, first, second


@pytest.fixture
def corrections(monkeypatch):
    """A stand-in for #270's greg.corrections whose contained set the test controls."""
    module = ModuleType("greg.corrections")
    module.contained = {}
    module.contained_receipts = lambda journal: dict(module.contained)
    monkeypatch.setitem(sys.modules, "greg.corrections", module)
    return module


def receipts(journal):
    return {o["receipt"] for o in settlement.measured_outcomes(journal)}


def counts(journal):
    rows = settlement.competence(journal).values()
    return sum(r["count"] for r in rows), sum(r["correct"] for r in rows)


def test_an_impugned_receipt_is_withheld_once_and_the_other_answer_still_counts(corrections):
    journal, first, second = two_answers()
    settlement.reconcile(journal)
    assert receipts(journal) == {first, second} and counts(journal) == (2, 2)

    corrections.contained = {first: {"cause": "REPLICATION_FAILED", "cause_id": "c:1", "event": "e:corr",
                                     "path": ["receipt", "claim"]}}
    assert receipts(journal) == {second} and counts(journal) == (1, 1)      # neither credited nor counted wrong
    settlement.reconcile(journal)
    closed = [e.payload for e in journal.replay("cognition.settled")
              if e.payload.get("receipt") == first and e.payload.get("invalidated")]
    assert len(closed) == 1 and closed[0]["reason"].startswith("withheld: the evidence it rests on was invalidated")
    assert closed[0]["contained_by"] == {"cause": "REPLICATION_FAILED", "cause_id": "c:1", "event": "e:corr"}
    before = len(journal.replay("cognition.settled"))
    settlement.reconcile(journal)
    assert len(journal.replay("cognition.settled")) == before               # idempotent


def test_a_requalified_receipt_settles_again(corrections):
    journal, first, _ = two_answers()
    corrections.contained = {first: {"cause": "APPRAISAL_REFUTED", "cause_id": "c:2", "event": "e:x", "path": []}}
    settlement.reconcile(journal)
    corrections.contained = {}                                              # evidence requalified it
    settlement.reconcile(journal)
    assert first in receipts(journal) and counts(journal) == (2, 2)
    latest = [e.payload for e in journal.replay("cognition.settled") if e.payload.get("receipt") == first][-1]
    assert not latest.get("invalidated")


def test_without_the_corrections_module_nothing_is_contained(monkeypatch):
    monkeypatch.setitem(sys.modules, "greg.corrections", None)            # import raises ImportError
    journal, first, second = two_answers()
    assert settlement.contained_receipts(journal) == {} and receipts(journal) == {first, second}


def test_with_the_real_corrections_module_a_body_without_corrections_contains_nothing():
    pytest.importorskip("greg.corrections")
    journal, first, second = two_answers()
    assert settlement.contained_receipts(journal) == {} and receipts(journal) == {first, second}


def reobserved():
    """One certified answer observed through two ledger receipts (the same claim identity), appraised VERIFIED."""
    journal, first = pending()
    again = answer(journal, rerun=1)                 # a new receipt of the same answer
    observe(journal, again)
    appraise(journal, "VERIFIED")
    assert first != again and counts(journal) == (1, 1)
    return journal, first, again


@pytest.mark.parametrize("which", ["latest", "earliest"])
def test_containing_any_receipt_of_an_answer_withholds_the_answer(corrections, which):
    """Skeptic P2 on #221 (...foabg): the outcome is per answer, not per receipt; containing the latest receipt
    used to fall back to an earlier receipt of the same answer, so nothing was withheld."""
    journal, first, again = reobserved()
    settlement.reconcile(journal)
    target = again if which == "latest" else first
    corrections.contained = {target: {"cause": "FOUNDER_REJECTED", "cause_id": "c:3", "event": "e:y", "path": []}}
    assert receipts(journal) == set() and counts(journal) == (0, 0)
    [(identity, cause)] = settlement.impugned_identities(journal).items()
    assert cause["cause"] == "FOUNDER_REJECTED"
    corrections.contained = {}
    assert counts(journal) == (1, 1)                 # requalified: counted once again, never twice


def test_withholding_names_the_cause_when_the_contained_receipt_is_not_the_settled_head(corrections):
    """Skeptic P3 on #221: reconcile looked up only the settled row's receipt, so containing another receipt of
    the answer closed it with the generic reason and no contained_by."""
    journal, first, again = reobserved()
    settlement.reconcile(journal)
    head = [e.payload for e in journal.replay("cognition.settled")][-1]["receipt"]
    other = first if head == again else again
    corrections.contained = {other: {"cause": "APPRAISAL_REFUTED", "cause_id": "c:4", "event": "e:z", "path": []}}
    settlement.reconcile(journal)
    closed = [e.payload for e in journal.replay("cognition.settled") if e.payload.get("invalidated")]
    assert len(closed) == 1 and closed[0]["reason"].startswith("withheld: the evidence it rests on was invalidated")
    assert closed[0]["contained_by"] == {"cause": "APPRAISAL_REFUTED", "cause_id": "c:4", "event": "e:z"}
