"""Pending construction feedback is visible and reportable through the signed CLI.

Fixture receipts are synthetic; the final test executes a real constructed
portfolio on a temporary body. Its reported outcome is synthetic, not a buyer
or founder-device result and not evidence of a positive learning dividend.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from greg import cli
from greg.cognition import settlement
from greg.cognition.contracts import digest
from tests.greg_fixtures import make_body
from tests.unit.test_greg_outcome_calibration import Journal

CID = "composed.selection.closure.fixture"


def pending(*, function="selection.closure", result=None, **changes):
    journal = Journal()
    journal.events.append(SimpleNamespace(type="greg.capability.registered", payload={
        "manifest": {"capability_id": CID, "provider": "composed:fixture", "version": "1.0.0"},
        "origin": {"kind": "composed", "function": function},
    }))
    value = {
        "schema": "greg-competency-compilation/0.2", "state": "ANSWERED",
        "authority_created": False, "selected_receipt": None,
        "method_or_composition_selected": CID, "confidence_type": "certified construction",
        "problem_id": "pending-fixture", "result": {"profit": 2} if result is None else result,
        **changes,
    }
    value["receipt_id"] = digest(value)
    return journal, journal.ledger.add(value)


def test_a_pending_construction_names_the_promised_objective_and_does_not_write():
    journal, receipt = pending()
    before = repr((journal.events, journal.ledger.records))
    [row] = settlement.awaiting_realization(journal)
    assert row["receipt"] == receipt
    assert (row["kind"], row["objective"], row["sense"], row["promised"]) == ("objective", "profit", "max", 2)
    assert row["method"] == CID and row["method_version"] == "1.0.0"
    assert row["tolerance"] == .1 and row["authority_created"] is False
    assert "--objective-value" in row["report_with"] and "--key" in row["report_with"]
    assert "not independently verified" in row["evidence_limit"]
    assert repr((journal.events, journal.ledger.records)) == before


@pytest.mark.parametrize("changes", [
    {"state": "ABSTAIN"}, {"state": "WORLD_UNVERIFIED"}, {"authority_created": True},
    {"confidence_type": "model claim"}, {"selected_receipt": {}},
    {"method_or_composition_selected": "unregistered"},
    {"result": {"profit": True}}, {"result": {"profit": "2"}},
    {"result": {"profit": 2, "feasible": False}}, {"result": {}},
])
def test_unaccepted_or_objectiveless_records_are_not_offered_for_feedback(changes):
    journal, _ = pending(**changes)
    assert settlement.awaiting_realization(journal) == []


def test_tampering_unregistered_functions_and_bound_results_are_not_pending():
    journal, receipt = pending()
    journal.ledger.find(receipt).payload["result"]["output"]["result"]["profit"] = 3
    assert settlement.awaiting_realization(journal) == []
    journal, _ = pending(function="unknown.function")
    assert settlement.awaiting_realization(journal) == []
    journal, receipt = pending()
    journal.record("cognition.realization", {"receipt": receipt, "kind": "objective", "realized": 1})
    assert settlement.awaiting_realization(journal) == []
    assert settlement.awaiting_realization(None) == []


@pytest.mark.parametrize("function,result,objective,sense", [
    ("selection.budgeted", {"profit": -2}, "profit", "max"),
    ("assignment.staffing", {"staffed": 0}, "staffed", "max"),
    ("assignment.matching", {"size": 3}, "size", "max"),
    ("project.crash", {"cost": 10}, "cost", "min"),
])
def test_existing_objective_shapes_remain_visible(function, result, objective, sense):
    journal, receipt = pending(function=function, result=result)
    [row] = settlement.awaiting_realization(journal)
    assert row["receipt"] == receipt
    assert (row["objective"], row["sense"], row["promised"]) == (objective, sense, result[objective])


def test_cli_keeps_a_single_step_forecast_as_a_list(tmp_path, capsys):
    home, *_ = make_body(tmp_path)
    assert cli.main(["--home", str(home), "realize", "sha256:fixture", "--value", "3",
                     "--key", str(tmp_path / "founder.pem"), "--no-passphrase"]) == 0
    envelope = json.loads(Path(capsys.readouterr().out.strip()).read_text())
    assert envelope["body"]["realized"] == [3.0]


def test_cli_emits_a_signed_scalar_without_changing_forecast_shape(tmp_path, capsys):
    home, *_ = make_body(tmp_path)
    assert cli.main(["--home", str(home), "realize", "sha256:fixture", "--objective-value", "3",
                     "--key", str(tmp_path / "founder.pem"), "--no-passphrase"]) == 0
    envelope = json.loads(Path(capsys.readouterr().out.strip()).read_text())
    assert envelope["kind"] == "REALIZATION" and envelope["body"]["realized"] == 3.0


def test_cli_scalar_and_forecast_forms_cannot_be_combined(tmp_path):
    home, *_ = make_body(tmp_path)
    with pytest.raises(SystemExit) as error:
        cli.main(["--home", str(home), "realize", "sha256:fixture",
                  "--value", "3", "--objective-value", "3"])
    assert error.value.code == 2
    assert list((home / "inbox").glob("*.json")) == []


@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_nonfinite_objectives_are_refused_before_signing(tmp_path, value):
    home, *_ = make_body(tmp_path)
    assert cli.main(["--home", str(home), "realize", "sha256:fixture",
                     "--objective-value=" + value, "--key", str(tmp_path / "founder.pem"),
                     "--no-passphrase"]) == 2
    assert list((home / "inbox").glob("*.json")) == []


def test_scalar_reporting_still_requires_the_founder_key(tmp_path):
    home, *_ = make_body(tmp_path)
    assert cli.main(["--home", str(home), "realize", "sha256:fixture", "--objective-value", "0"]) == 2
    assert list((home / "inbox").glob("*.json")) == []


def test_real_construction_is_listed_reported_by_signed_cli_and_no_longer_pending(tmp_path, capsys):
    pytest.importorskip("networkx")
    pytest.importorskip("scipy")
    from tests.unit.test_greg_construction_realization import PORTFOLIO, Run
    with Run(tmp_path) as run:
        record = run.ask("pending-cli-portfolio", PORTFOLIO)
        before = len(run.body.journal.replay())
        capsys.readouterr()
        assert cli.main(["--home", str(run.home), "cognition", "calibration"]) == 0
        view = json.loads(capsys.readouterr().out)
        row = next(r for r in view["awaiting_realization"] if r["receipt"] == record.hash)
        assert row["promised"] == 2 and row["objective"] == "profit"
        assert view["authority_created"] is False
        assert len(run.body.journal.replay()) == before
        assert cli.main(["--home", str(run.home), "realize", record.hash, "--objective-value", "1",
                         "--key", str(tmp_path / "founder.pem"), "--no-passphrase"]) == 0
        capsys.readouterr()
        run.body.tick()
        [fact] = list(run.body.journal.replay("cognition.realization"))
        assert fact.payload["kind"] == "objective" and fact.payload["realized"] == 1.0
        assert fact.payload["command_digest"] and fact.payload["authority_created"] is False
        assert not any(r["receipt"] == record.hash for r in settlement.awaiting_realization(run.body.journal))
        assert run.outcome(record)["correct"] is False
        assert run.outcome(record)["certificate_correct"] is True
