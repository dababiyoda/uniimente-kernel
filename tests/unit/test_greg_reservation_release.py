"""A reconciliation settles the signed cap an interrupted action held as unknown spend, exactly once.

Found on 2026-10-15 by #178's whole-machine test on the merged trunk: a priced commission interrupted by SIGKILL
held its $0.05 cap (#169's rule for unknown spend), the founder reconciled "not executed", and the retry was then
refused for exceeding the $0.05 budget, so the mission waited for an approval the founder had no reason to give.
The mirror case booked the cap twice: once as the reservation and again when "executed" was reconciled.
"""
from __future__ import annotations

from greg.missions import MissionBook
from tests.greg_fixtures import mission


class _NoHistory:
    def replay(self, *args, **kwargs):
        return []


def _book(cap: float) -> tuple[MissionBook, str]:
    spec = mission("m:priced", checks=[], strategies=[{"action_id": "commission", "capability": "worker.commission",
                                                       "target": "workspace:*", "params": {}, "cost_usd": cap,
                                                       "advances": []}],
                   capabilities=["worker.commission"], budget=cap)
    book = MissionBook(_NoHistory())
    book.fold("mission.registered", {"mission_id": spec["mission_id"], "spec": spec, "command_digest": "sha256:x"})
    return book, spec["mission_id"]


def _uncertain(cap):
    return {"mission_id": "m:priced", "action_id": "commission", "attempt": 0, "status": "UNCERTAIN",
            "reasons": ["dispatch claimed without receipt; outcome unknown"], "cost_usd": cap, "cost_cap_usd": cap,
            "cost_reserved": True, "capability": "worker.commission"}


def test_an_interrupted_priced_action_holds_its_cap_until_reconciled():
    book, mid = _book(0.05)
    book.fold("mission.action", _uncertain(0.05))
    m = book.missions[mid]
    assert m.spent_usd == 0.0 and m.committed_usd == 0.05          # held against the budget, not booked as spent


def test_reconciled_not_executed_releases_the_cap_so_the_one_retry_fits_the_signed_budget():
    book, mid = _book(0.05)
    book.fold("mission.action", _uncertain(0.05))
    book.fold("mission.action", {"mission_id": mid, "action_id": "commission", "attempt": 0,
                                 "status": "RECONCILED_NOT_EXECUTED", "route": "founder_reconciliation",
                                 "reasons": ["founder reconciliation: reconcile_not_executed"], "cost_usd": 0.0})
    m = book.missions[mid]
    assert m.committed_usd == 0.0 and m.attempts["commission"] == 1
    assert m.committed_usd + 0.05 <= m.cone.budget_usd


def test_reconciled_executed_books_the_cap_once_not_twice():
    book, mid = _book(0.05)
    book.fold("mission.action", _uncertain(0.05))
    book.fold("mission.action", {"mission_id": mid, "action_id": "commission", "attempt": 0, "status": "DONE",
                                 "route": "founder_reconciliation", "receipt": None,
                                 "reasons": ["founder reconciliation: reconcile_executed"], "cost_usd": 0.05,
                                 "cost_cap_usd": 0.05, "spend_basis": "signed_cap: founder reconciled executed"})
    m = book.missions[mid]
    assert round(m.spent_usd, 6) == round(m.committed_usd, 6) == 0.05


def test_a_later_attempts_reservation_is_independent_of_an_earlier_settled_one():
    book, mid = _book(0.10)
    book.fold("mission.action", _uncertain(0.05))
    book.fold("mission.action", {"mission_id": mid, "action_id": "commission", "attempt": 0,
                                 "status": "RECONCILED_NOT_EXECUTED", "reasons": [], "cost_usd": 0.0})
    book.fold("mission.action", {**_uncertain(0.05), "attempt": 1})
    m = book.missions[mid]       # the legacy record's own held figure (0.05), not the spec's current cost (0.10)
    assert m.spent_usd == 0.0 and m.committed_usd == 0.05
