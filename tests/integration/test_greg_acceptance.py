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


def test_confinement_passes_only_on_a_confined_body_whose_relay_journal_verifies(tmp_path):
    """#26 on the device report: PASS needs a confined body, an intact relay chain, and decisions actually made."""
    import json
    from foundry.systems.segmentation import Journal
    from tests.integration.test_greg_confined_egress import body_with_confined_egress
    home, _, _ = body_with_confined_egress(tmp_path)
    assert {status_of(report(home))[p] for p in ("network_confined", "undeclared_destination_denied")} == {"NOT_YET"}
    journal = Journal(home / "egress-journal.jsonl")
    journal.append({"identity": "http.get", "host": "service.test", "port": 443, "verdict": "ALLOWED"})
    assert status_of(report(home))["network_confined"] == "PASS"
    assert status_of(report(home))["undeclared_destination_denied"] == "NOT_YET"
    journal.append({"identity": "browser.render", "host": "beacon.example.com", "port": 443, "verdict": "DENIED"})
    result = report(home)
    assert status_of(result)["undeclared_destination_denied"] == "PASS"
    assert result["egress"]["identities"] == ["browser.render", "http.get"]
    rows = (home / "egress-journal.jsonl").read_text().splitlines()       # an edited record breaks the chain
    first = json.loads(rows[0])
    first["port"] = 8443                                                    # same verdicts, edited record
    (home / "egress-journal.jsonl").write_text("\n".join([json.dumps(first)] + rows[1:]) + "\n")
    tampered = status_of(report(home))
    assert tampered["network_confined"] == "NOT_YET" and tampered["undeclared_destination_denied"] == "NOT_YET"


def test_an_unconfined_body_never_reports_confinement(tmp_path):
    from foundry.systems.segmentation import Journal
    home, *_ = setup(tmp_path)
    Journal(home / "egress-journal.jsonl").append({"identity": "http.get", "host": "x", "port": 443,
                                                   "verdict": "ALLOWED"})    # a stray file is not a confined body
    after = status_of(report(home))
    assert after["network_confined"] == "NOT_YET" and after["undeclared_destination_denied"] == "NOT_YET"
