"""Mission G: settlement and delivery honour only grants the governing Consequence Gate issued.

Constitution: only the Gate issues grants, and nothing may honour a grant the Gate did not issue. Before
(19bbdcb), ``payments.Rail.charge`` and ``agent_commerce.Storefront.redeem`` checked a grant's shape only (a
``grant_id`` and a matching ``objective``): a forged dict settled a 5000-cent test charge (scratch probe
missiong/probe.py). Now a rail or storefront honours a grant only if its own Gate holds it, unaltered, unrevoked,
unused, unexpired and bound to exactly this case and amount, and the act itself runs through that Gate, which
consumes the grant. Test-mode money on the loopback Stripe emulator; nothing reaches a real network.
"""
from __future__ import annotations

import pytest

from foundry.systems import agent_commerce, marketplace, payments
from foundry.systems.kernel_stack import gate_stack

RECEIPT = "sha256:" + "1" * 64


@pytest.fixture
def emulator():
    server, emu = payments.start_emulator()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", emu
    finally:
        server.shutdown()
        server.server_close()


def test_a_forged_grant_moves_no_money(tmp_path, emulator):
    base, emu = emulator
    forged = {"grant_id": "forged-not-issued-by-any-gate", "objective": "charge:case-x"}
    # The probe's exact call: a rail constructed without a governing Gate honours no grant at all.
    ungoverned = payments.Rail(tmp_path / "ungoverned", api_key="sk_test_emulator", base=base)
    with pytest.raises(payments.PaymentError, match="grant not honoured"):
        ungoverned.charge(case_id="case-x", customer="anyone", amount_cents=5000, delivery_receipt=RECEIPT, grant=forged)
    assert emu.intents == {}, "a refused charge never reaches the processor"

    gate, _, ledger = gate_stack()
    rail = payments.Rail(tmp_path / "rail", api_key="sk_test_emulator", base=base, gate=gate)
    genuine = payments.charge_grant("case-x", 5000, gate=gate)
    attempts = {
        "forged": forged,
        "issued by another gate": payments.charge_grant("case-x", 5000, gate=gate_stack()[0]),
        "altered after issue": {**payments.charge_grant("case-x", 5000, gate=gate), "spending_limit_usd": 1e9},
        "bound to a smaller amount": payments.charge_grant("case-x", 100, gate=gate),
    }
    for label, grant in attempts.items():
        with pytest.raises(payments.PaymentError, match="grant not honoured"):
            rail.charge(case_id="case-x", customer="anyone", amount_cents=5000, delivery_receipt=RECEIPT, grant=grant)
    revoked = payments.charge_grant("case-x", 5000, gate=gate)
    gate.grants.revoke(revoked["grant_id"], reason="test", revoker="test")
    with pytest.raises(payments.PaymentError, match="revoked"):
        rail.charge(case_id="case-x", customer="anyone", amount_cents=5000, delivery_receipt=RECEIPT,
                    grant=gate.grants.get(revoked["grant_id"]))
    assert emu.intents == {}

    settled = rail.charge(case_id="case-x", customer="anyone", amount_cents=5000, delivery_receipt=RECEIPT, grant=genuine)
    assert settled["status"] == "settled" and len(emu.intents) == 1
    assert gate.grants.get_meta(genuine["grant_id"])["used"], "the Gate consumed the grant"
    receipts = [r.payload for r in ledger.by_type("receipt")]
    assert [r["grant_id"] for r in receipts] == [genuine["grant_id"]]
    assert rail._state()["charges"]["case-x"]["gate_receipt"]
    # single use is the Gate's, not the rail file's: fresh books under the same Gate cannot spend it again
    replay = payments.Rail(tmp_path / "replay", api_key="sk_test_emulator", base=base, gate=gate)
    with pytest.raises(payments.PaymentError, match="already used"):
        replay.charge(case_id="case-x", customer="anyone", amount_cents=5000, delivery_receipt=RECEIPT, grant=genuine)
    assert len(emu.intents) == 1


def _shop(root, base, **gate):
    rail = payments.Rail(root / "rail", api_key="sk_test_emulator", base=base, **gate)
    shop = agent_commerce.Storefront(root / "shop", seller_id="organ:test-shop", key_seed=bytes(32 * [7]), rail=rail,
                                     **gate)
    shop.handlers["audit"] = lambda inputs: b"audited"
    shop.publish_card(name="t", description="t", version="1", skills=agent_commerce.demo_skills(),
                      now="2026-10-13T12:00:00Z")
    challenge = shop.challenge(skill_id="audit", buyer="agent:b", inputs={"units": 1, "customer_tier": 1},
                               now="2026-10-13T12:01:00Z")
    paid = agent_commerce.Storefront.pay(challenge["payment_required"], payer=payments.client("sk_test_b", base))
    return shop, challenge["payment_required"]["order_id"], paid


def test_a_storefront_delivers_only_under_its_own_gates_grant(tmp_path, emulator):
    base, emu = emulator
    # The probe's pattern: a storefront without a governing Gate, handed a forged dict, delivers nothing.
    shop, order, paid = _shop(tmp_path / "ungoverned", base)
    with pytest.raises(agent_commerce.CommerceError, match="grant not honoured"):
        shop.redeem(paid, grant={"grant_id": "forged", "objective": f"deliver:{order}"}, now="2026-10-13T12:02:00Z")
    assert shop._state()["redeemed"] == {} and not (tmp_path / "ungoverned" / "shop" / "deliveries").exists()

    gate, _, ledger = gate_stack()
    shop, order, paid = _shop(tmp_path / "governed", base, gate=gate)
    for grant in ({"grant_id": "forged", "objective": f"deliver:{order}"},
                  agent_commerce.deliver_grant(order, gate=gate_stack()[0])):
        with pytest.raises(agent_commerce.CommerceError, match="grant not honoured"):
            shop.redeem(paid, grant=grant, now="2026-10-13T12:02:00Z")
    assert shop._state()["redeemed"] == {} and shop._state()["booked_cents"] == 0, "nothing booked or delivered"
    grant = agent_commerce.deliver_grant(order, gate=gate)
    served = shop.redeem(paid, grant=grant, now="2026-10-13T12:02:00Z")
    assert served["status"] == 200 and gate.grants.get_meta(grant["grant_id"])["used"]
    assert [r.payload["grant_id"] for r in ledger.by_type("receipt")] == [grant["grant_id"]]


def test_marketplace_settlement_refuses_a_forged_grant(tmp_path):
    result = marketplace.exercise(tmp_path)
    assert "grant not honoured" in result["refusals"]["settle_forged_grant"]
    assert result["settlement"]["status"] == "settled"
