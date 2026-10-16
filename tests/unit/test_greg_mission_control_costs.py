"""Mission Control keeps money in distinct columns: budget, booked, provider-measured, unknown at cap, fixture."""
from greg.mission_control import cost_rows


def mission(mid, budget):
    return {"mission_id": mid, "cone": {"budget_usd": budget}}


def test_measured_unknown_and_fixture_amounts_are_never_netted():
    actions = [
        {"mission_id": "m:a", "status": "DONE", "cost_usd": 0.12, "spend_basis": "provider_reported",
         "provider_reported_usd": 0.12},
        {"mission_id": "m:a", "status": "DONE", "cost_usd": 0.5, "spend_basis": "signed_cap: provider spend not reported",
         "provider_reported_usd": None},
        {"mission_id": "m:a", "status": "DONE", "cost_usd": 0.5, "spend_basis": "signed_cap: provider report outside [0, cap]",
         "provider_reported_usd": 9.0},                                   # an over-cap report is booked at the cap
        {"mission_id": "m:a", "status": "FAILED", "cost_usd": 3.0, "spend_basis": "provider_reported",
         "provider_reported_usd": 3.0},                                   # not DONE: never booked here
        {"mission_id": "m:elsewhere", "status": "DONE", "cost_usd": 7.0},  # no such mission: ignored, not invented
    ]
    rows = {r["mission_id"]: r for r in cost_rows(actions, [mission("m:a", 2.0), mission("m:b", 0)],
                                                   [{"mission_id": "m:b", "totals": {"revenue": 1200}}])}
    a, b = rows["m:a"], rows["m:b"]
    assert a == {"mission_id": "m:a", "budget_usd": 2.0, "booked_usd": 1.12, "measured_usd": 0.12,
                 "unknown_at_cap_usd": 1.0, "fixture_cents": 0, "money_moved": False}
    assert b["fixture_cents"] == 1200 and b["booked_usd"] == 0.0 and b["money_moved"] is False
    assert set(rows) == {"m:a", "m:b"}


def test_free_capabilities_book_zero_without_claiming_a_measurement():
    rows = cost_rows([{"mission_id": "m:a", "status": "DONE", "cost_usd": 0.0, "spend_basis": "signed_cap",
                       "provider_reported_usd": None}], [mission("m:a", 0)], [])
    assert rows[0]["booked_usd"] == 0.0 and rows[0]["measured_usd"] == 0.0 and rows[0]["unknown_at_cap_usd"] == 0.0
