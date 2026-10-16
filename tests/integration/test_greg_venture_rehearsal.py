"""The First Mission's dossier carried through GREG's governed commerce loop as a FIXTURE, on the same body."""
import json

import pytest

from greg.body import Body
from greg.venture_rehearsal import FIXTURE, books, latest_canon, venture_rehearsal
from tests.greg_fixtures import drop, signed
from tests.integration.test_greg_first_mission import run_until_settled, setup


def test_dossier_to_fixture_sale_delivery_acceptance_and_books(tmp_path):
    home, key, body_id, _, first = setup(tmp_path)
    out, _ = run_until_settled(home)
    assert out["missions"][0]["state"] == "ACHIEVED"
    canon, source = latest_canon(home / "deliveries")
    assert canon["source_refs"][0].startswith("dossier sha256:") and source.endswith(".json")
    spec = venture_rehearsal(canon=canon, price_cents=1200)
    assert FIXTURE in spec["founder_expression"] and spec["light_cone"]["budget_usd"] == 0
    drop(home, signed(key, body_id, "MISSION", spec), "v.json")
    with Body(home) as body:
        body.boot()
        for _ in range(12):
            states = {m["mission_id"]: m["state"] for m in body.tick()["missions"]}
            if states.get(spec["mission_id"]) == "ACHIEVED":
                break
        assert states.get(spec["mission_id"]) == "ACHIEVED", states
        assert body.appraise(spec["mission_id"])["verdict"] == "VERIFIED"
    ledger = books(home, spec["mission_id"])
    assert ledger["mode"] == FIXTURE and ledger["money_moved"] is False and ledger["totals"]["revenue"] == 1200
    journal = home / "workspace" / spec["mission_id"].replace(":", "_") / "foundry" / "system-49" / "fixture-books" / "journal.jsonl"
    journal.write_text(journal.read_text().replace("1200", "999"))          # an edited book
    with Body(home) as body:
        assert body.appraise(spec["mission_id"])["verdict"] == "REFUTED"


def test_no_dossier_means_no_rehearsal(tmp_path):
    with pytest.raises(FileNotFoundError, match="First Mission"):
        latest_canon(tmp_path)
    with pytest.raises(ValueError, match="fixture price"):
        from greg.venture_rehearsal import company_spec
        company_spec({"canon_id": "x-1", "title": "t", "body": "b", "source_refs": ["s"], "rights": "r"}, price_cents=0)
