"""Acceptance G.G4: a buyer's quality-control rejection is honoured everywhere the loop counts.

Mission G (business operating loop): "fulfillment, proof, quality control, settlement state, and learning".
The owned-company loop (Foundry systems 49 and 54) was proven on its accept path only. Here a signed buyer
REJECTS a delivered fixture order: it is not counted as accepted, no revenue reaches the fixture books, no purchase
journey is recorded, the offer's rating moves down rather than up (the same order accepted is the contrast), and a
later "accept" cannot overwrite the retained rejection. Fixture mode throughout: no money moves.
"""
from __future__ import annotations

import pytest

from foundry.systems import journeys, media_company, offers
from tests.unit.test_greg_owned_company import acceptance, order, spec


def loop(tmp_path, verdict):
    root = tmp_path / "system-49"
    media_company.assemble(root, spec())
    market = tmp_path / "system-54"
    delivery = offers.fulfill(market, order(market))
    assert offers.accept(market, acceptance(delivery, verdict))["verdict"] == verdict
    rating = offers.rated(market, "2026-10-01T12:04:00Z")["subjects"][0]
    return root, market, delivery, rating


def test_a_rejected_delivery_is_never_accepted_booked_journeyed_or_rated_up(tmp_path):
    root, market, delivery, rejected = loop(tmp_path / "rejected", "reject")
    assert offers.inspect(market) == {"intact": True, "delivered": 1, "accepted": 0, "mode": "fixture", "paid": False}
    reconciled = media_company.reconcile(root)
    assert reconciled["newly_reconciled"] == [] and reconciled["book"]["totals"]["revenue"] == 0
    assert media_company.observed(root)["fixture_finance"]["totals"]["revenue"] == 0
    assert journeys.report(tmp_path / "rejected" / "system-34", "fixture")["events"] == 0
    with pytest.raises(ValueError, match="already retained"):
        offers.accept(market, acceptance(delivery, "accept"))          # a rejection cannot be flipped later
    assert offers.inspect(market)["accepted"] == 0

    root2, market2, _, accepted = loop(tmp_path / "accepted", "accept")  # the contrast: the same order accepted
    assert offers.inspect(market2)["accepted"] == 1
    assert media_company.reconcile(root2)["newly_reconciled"] == ["order-1"]
    assert rejected["subject"] == accepted["subject"] == "offer"
    assert rejected["mean"] < 0.5 < accepted["mean"], (rejected, accepted)
