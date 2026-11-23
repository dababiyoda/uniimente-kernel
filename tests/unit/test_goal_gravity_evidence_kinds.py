"""Integration conditions on #219's EVIDENCE_KINDS in ``greg/goal_gravity.py`` (#196 intake).

Verifying REALIZATION envelopes lets settlement bind a resolution to what the founder signed. It must stay evidence:
no goal, mission or decision fact may change, the other readers of verified commands see what they saw before, and a
report the verifier does not count is still recorded and scored as it was. Values are synthetic test inputs.
"""
from __future__ import annotations

import pytest

pytest.importorskip("networkx")
pytest.importorskip("scipy")

from greg import goal_gravity  # noqa: E402
from greg.cognition import settlement  # noqa: E402
from tests.unit.test_greg_construction_realization import PROMISED, Run  # noqa: E402
from tests.unit.test_greg_recombine import PORTFOLIO  # noqa: E402

GOAL_FIELDS = ("admitted", "specs", "closed", "closed_intents", "stop", "narrowing", "floor", "controlled_at",
               "authorizations", "revoked", "enrolled_at")


def _facts(journal, monkeypatch, evidence):
    monkeypatch.setattr(goal_gravity, "EVIDENCE_KINDS", evidence)
    return goal_gravity.founder_facts(journal.ledger)


def test_a_verified_realization_changes_no_goal_mission_or_decision_fact(tmp_path, monkeypatch):
    with Run(tmp_path) as run:
        journal = run.body.journal
        record = run.ask("pf-evidence", PORTFOLIO)
        run.realize(record, PROMISED)
        with_evidence = _facts(journal, monkeypatch, ("REALIZATION",))
        without = _facts(journal, monkeypatch, ())
    reports = {d for d, c in with_evidence.signed.items() if c["kind"] == "REALIZATION"}
    assert reports, "the founder's signed REALIZATION verifies"
    assert not any(c["kind"] == "REALIZATION" for c in without.signed.values())
    assert {d: c for d, c in with_evidence.signed.items() if d not in reports} == without.signed
    for name in GOAL_FIELDS:
        assert getattr(with_evidence, name) == getattr(without, name), name
    assert {d: r for d, r in with_evidence.refused.items() if d not in reports} == without.refused
    assert with_evidence.book.requests.keys() == without.book.requests.keys()


def test_every_other_reader_of_verified_commands_sees_what_it_saw_before(tmp_path, monkeypatch):
    with Run(tmp_path) as run:
        journal = run.body.journal
        record = run.ask("pf-readers", PORTFOLIO)
        run.realize(record, PROMISED)
        monkeypatch.setattr(goal_gravity, "EVIDENCE_KINDS", ("REALIZATION",))
        now = goal_gravity.signed_commands(journal, *goal_gravity.VERIFIED_KINDS)
        monkeypatch.setattr(goal_gravity, "EVIDENCE_KINDS", ())
        before = goal_gravity.signed_commands(journal, *goal_gravity.VERIFIED_KINDS)
    assert now == before and now
    assert all(c["kind"] in goal_gravity.VERIFIED_KINDS for c in now.values())


def test_a_report_the_verifier_does_not_count_is_still_recorded_and_scored(tmp_path):
    """An in-process report (no signed envelope) cannot ground a resolution, but it still records its value and
    settles an undisputed claim exactly as before #219."""
    with Run(tmp_path) as run:
        journal = run.body.journal
        record = run.ask("pf-unsigned", PORTFOLIO)
        settlement.record_realization(journal, receipt=record.hash, realized=PROMISED, source="external_record")
        facts = [e.payload for e in journal.replay("cognition.realization") if e.payload.get("kind") == "objective"]
        assert len(facts) == 1 and facts[0]["realized"] == PROMISED
        assert not goal_gravity.signed_commands(journal, "REALIZATION")
        assert run.outcome(record)["correct"] is True
