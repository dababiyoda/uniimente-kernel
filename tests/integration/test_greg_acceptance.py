"""The founder-device acceptance report reads only this body's ledger and never over-claims."""
from greg.acceptance import report
from greg.body import Body
from tests.greg_fixtures import drop, signed
from tests.integration.test_greg_first_mission import run_until_settled, setup


def status_of(result):
    return {p["property"]: p["status"] for p in result["properties"]}


def test_report_tracks_founder_acts_and_never_claims_a_device_it_cannot_show(tmp_path):
    home, key, body_id, _, spec = setup(tmp_path)
    before = status_of(report(home))
    assert before["first_mission_verified"] == "NOT_YET" and before["pause_and_resume_exercised"] == "NOT_YET"
    run_until_settled(home)
    for kind, body in (("BODY_PAUSE", {}), ("BODY_RESUME", {})):
        drop(home, signed(key, body_id, kind, body), f"{kind}.json")
    with Body(home) as b:
        b.boot()
        b.tick()
    result = report(home)
    after = status_of(result)
    for prop in ("ledger_chain_verified", "founder_key_enrolled", "engine_attached_by_founder", "first_mission_verified",
                 "foundry_private_page", "lesson_retained", "pause_and_resume_exercised"):
        assert after[prop] == "PASS", (prop, result)
    assert after["first_body_designated"] == "NOT_YET" and after["interruption_survived"] == "NOT_YET"
    assert result["reality"].startswith("LOCAL") and result["vepmc"] == 0 and result["authority_created"] is False
