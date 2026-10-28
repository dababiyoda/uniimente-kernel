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
from tests.unit.test_greg_outcome_calibration import Journal as _Journal


class Journal(_Journal):
    """The calibration fixture plus what record_realization needs from a body journal: event ids and keyed
    idempotency (``retained``)."""

    def record(self, kind, payload, key=None, sensitivity=None):
        self.events.append(SimpleNamespace(type="greg." + kind, payload=payload, key=repr(key),
                                           event_id=f"e:{len(self.events)}"))

    def retained(self, kind, key):
        return next((e for e in self.replay(kind) if e.key == repr(key)), None)

CID = "composed.selection.closure.fixture"
PARAMS = {"problem_id": "pending-fixture", "compile": {"geometry": {"geometry": "optimization"}, "data": {}}}
CHECK = {"check_id": "answered", "description": "fixture", "predicate": {"op": "equals", "field": "state",
                                                                         "value": "ANSWERED"},
         "sensor": {"capability": "cognition.solve", "target": "cognition:pending-fixture", "params": PARAMS}}


def observe(journal, receipt, *, mission_id="m:pending-fixture", check=CHECK, producer="cognition.solve"):
    """What a body records when a signed check observes a receipt: the witness, the registration, the observation."""
    witness = f"w:{receipt}"
    journal.ledger.find(receipt).payload["witness_id"] = witness
    journal.ledger.records[witness] = SimpleNamespace(record_type="witness", hash=witness, ts_utc="t",
                                                      payload={"witness_id": witness, "capability": producer})
    if not journal.replay("mission.registered"):
        journal.record("mission.registered", {"mission_id": mission_id, "command_digest": "sha256:" + "c" * 64,
                                              "spec": {"success_checks": [check]}})
    journal.events.append(SimpleNamespace(type="greg.mission.observed", event_id=f"e:{len(journal.events)}",
                                          payload={"mission_id": mission_id, "check_id": check["check_id"],
                                                   "receipt": receipt, "passed": True}))


def answer(journal, *, result=None, **changes):
    value = {
        "schema": "greg-competency-compilation/0.2", "state": "ANSWERED",
        "authority_created": False, "selected_receipt": None,
        "method_or_composition_selected": CID, "confidence_type": "certified construction",
        "problem_id": "pending-fixture", "inputs_digest": digest(PARAMS),
        "result": {"profit": 2} if result is None else result, **changes,
    }
    value["receipt_id"] = digest(value)
    return journal.ledger.add(value)


def pending(*, function="selection.closure", result=None, observed=True, **changes):
    journal = Journal()
    journal.events.append(SimpleNamespace(type="greg.capability.registered", payload={
        "manifest": {"capability_id": CID, "provider": "composed:fixture", "version": "1.0.0"},
        "origin": {"kind": "composed", "function": function},
    }))
    receipt = answer(journal, result=result, **changes)
    if observed:
        observe(journal, receipt)
    return journal, receipt


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
    settlement.record_realization(journal, receipt=receipt, realized=1, source="external_record")
    assert settlement.awaiting_realization(journal) == []
    assert settlement.awaiting_realization(None) == []


def test_an_answer_no_signed_check_observed_is_not_offered_because_its_report_would_never_settle():
    """Settlement credits a construction only through a signed check's observation of its receipt. A receipt no
    check observed (or one a check does not bind: another sensor, producer or input) is in no claim, so the view
    does not invite a report the body would record and then never count."""
    journal, receipt = pending(observed=False)
    assert settlement.awaiting_realization(journal) == []
    for change in ({"producer": "fs.read"},
                   {"check": {**CHECK, "sensor": {**CHECK["sensor"], "params": {**PARAMS, "problem_id": "other"}}}}):
        journal, receipt = pending(observed=False)
        observe(journal, receipt, **change)
        assert settlement.awaiting_realization(journal) == []


def test_one_claim_reobserved_on_many_receipts_is_offered_once_and_leaves_once_any_receipt_is_reported():
    journal, first = pending()
    later = [answer(journal, recorded="again", n=n) for n in range(2)]   # one claim: same mission, check, input
    for receipt in later:
        observe(journal, receipt)
    [row] = settlement.awaiting_realization(journal)
    assert row["receipt"] == later[-1] and row["receipts_for_claim"] == 3
    assert row["claim"].startswith("sha256:") and row["mission_appraisal"] is None
    assert row["settles"].startswith("only once the mission's latest appraisal is an eligible settling appraisal")
    settlement.record_realization(journal, receipt=first, realized=2, source="founder_reported")   # an older one
    assert settlement.awaiting_realization(journal) == []


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


def test_a_persistent_mission_reobserving_one_answer_asks_once_and_one_signed_report_settles_it_once(
        tmp_path, capsys):
    """An infinite-closure mission re-verifies its answer every cadence, leaving one receipt per observation of
    one signed claim. Before: every receipt was listed as awaiting a report (13 on this run), the claim stayed
    listed after it was reported, and a second, rounded report on a sibling receipt erased the outcome as a
    conflict. Now the claim is offered once, the signed scalar report settles it once, and it leaves the list.
    The realized value is synthetic, not a real-world outcome."""
    pytest.importorskip("networkx")
    pytest.importorskip("scipy")
    from greg.templates import compiled_question
    from tests.greg_fixtures import drop, signed
    from tests.unit.test_greg_construction_realization import PORTFOLIO, Run
    with Run(tmp_path) as run:
        spec = compiled_question(problem_id="pending-persistent", data=PORTFOLIO, allow_construction=True,
                                 objective="which to take")
        spec["closure"] = {"kind": "infinite", "cadence_seconds": 60}
        drop(run.home, signed(run.key, run.body_id, "MISSION", spec))
        for _ in range(8):
            run.body.tick()
            run.clock.advance(61)
        answered = [o.payload["receipt"] for o in run.body.journal.replay("mission.observed")
                    if o.payload["passed"] and o.payload["mission_id"] == spec["mission_id"]]
        assert len(answered) >= 3, "the mission did not re-observe its answer"
        capsys.readouterr()
        assert cli.main(["--home", str(run.home), "cognition", "calibration"]) == 0
        rows = json.loads(capsys.readouterr().out)["awaiting_realization"]
        assert len(rows) == 1, f"one signed claim offered as {len(rows)} pending reports"
        [row] = rows
        assert row["receipts_for_claim"] == len(answered) and row["receipt"] == answered[-1]
        assert row["promised"] == 2
        assert cli.main(["--home", str(run.home), "realize", row["receipt"], "--objective-value", "1",
                         "--key", str(tmp_path / "founder.pem"), "--no-passphrase"]) == 0
        capsys.readouterr()
        for _ in range(3):                                   # it keeps re-observing after the report
            run.body.tick()
            run.clock.advance(61)
        assert settlement.awaiting_realization(run.body.journal) == []
        [outcome] = [o for o in settlement.measured_outcomes(run.body.journal) if o["method"] == row["method"]]
        assert outcome["correct"] is False and outcome["certificate_correct"] is True
        assert outcome["world"]["realized"] == 1.0 and outcome["world"]["met"] is False
        [(count, correct)] = [(r["count"], r["correct"]) for (m, _, _), r in
                              settlement.competence(run.body.journal).items() if m == row["method"]]
        assert (count, correct) == (1, 0), "one claim settles once, however many receipts it left"


def appraise(journal, verdict, mission_id="m:pending-fixture"):
    from greg.sop import REQUIRED_CHECKS
    journal.record("mission.appraised", {"mission_id": mission_id, "verdict": verdict,
                                         "checks": {k: verdict.startswith("VERIFIED") for k in REQUIRED_CHECKS}})


def test_the_row_says_when_a_report_will_settle_following_the_missions_latest_appraisal():
    """Review finding 2 on #210 (...foabg): a claim whose mission's latest appraisal is not VERIFIED was offered
    with an unconditional "settles once"; a report on it is recorded and scores nothing until it is."""
    journal, receipt = pending()
    appraise(journal, "VERIFIED")
    [row] = settlement.awaiting_realization(journal)
    assert row["mission_appraisal"] == "VERIFIED" and row["settles"].startswith("once for the claim")
    appraise(journal, "REFUTED")
    [row] = settlement.awaiting_realization(journal)
    assert row["mission_appraisal"] == "REFUTED"
    assert row["settles"].startswith("only once the mission's latest appraisal is an eligible settling appraisal")



def test_a_verified_failure_closure_settles_like_a_verified_success_and_a_later_refutation_withdraws_it():
    """Directive on #210 (2026-10-28): the shared rule admits VERIFIED and VERIFIED_UNMET (a verified failure
    closure, never promoted to success); the row must say so, and a later REFUTED withdraws eligibility."""
    journal, receipt = pending()
    appraise(journal, "VERIFIED_UNMET")
    [row] = settlement.awaiting_realization(journal)
    assert row["mission_appraisal"] == "VERIFIED_UNMET" and row["settles"].startswith("once for the claim")
    appraise(journal, "REFUTED")
    [row] = settlement.awaiting_realization(journal)
    assert row["settles"].startswith("only once") and "VERIFIED_UNMET" in row["settles"]


@pytest.mark.xfail(strict=True, reason="answer-version alias (directive on #210, 2026-10-28), reproduced: the claim "
                                       "identity binds mission/check/input/method/version, not the answer, so a "
                                       "report on one certified answer settles a later, different answer of the "
                                       "same claim. Unreachable for today's certified optima (the promised value "
                                       "is unique per input and version); the fix is settlement semantics, owned "
                                       "by the #196 integrator. Strict: this flips to a failure once fixed.")
def test_a_report_on_one_answer_never_settles_a_different_later_answer_of_the_same_claim():
    journal, first = pending()                                  # promises profit 2
    later = answer(journal, result={"profit": 4})               # same claim key, a different certified answer
    observe(journal, later)
    appraise(journal, "VERIFIED")
    settlement.record_realization(journal, receipt=first, realized=1, source="founder_reported")
    credited = [o for o in settlement.measured_outcomes(journal) if o.get("world")]
    assert all(o["world"]["promised"] == 4 for o in credited), "the later answer inherited the first answer's report"
    assert any(r.get("promised") == 4 for r in settlement.awaiting_realization(journal)), \
        "the later answer's world outcome is no longer asked for"

def test_a_corrected_report_is_shown_as_a_conflict_scored_as_neither_never_silently_dropped():
    """Review finding 1 on #210 (...foabg): a second, different value, even on the same receipt, makes settlement
    score the claim as neither; the view dropped it from every surface. It is now its own row."""
    journal, receipt = pending()
    appraise(journal, "VERIFIED")
    settlement.record_realization(journal, receipt=receipt, realized=1, source="founder_reported")
    assert settlement.awaiting_realization(journal) == []                 # settled: nothing to ask
    settlement.record_realization(journal, receipt=receipt, realized=2, source="founder_reported")
    [row] = settlement.awaiting_realization(journal)
    assert row["kind"] == "objective_conflict" and row["realized_values"] == [1, 2]
    assert len(row["realization_events"]) == 2 and row["promised"] == 2 and row["objective"] == "profit"
    assert "neither" in row["scored_as"] and row["authority_created"] is False
    assert "receipt" not in row and "report_with" not in row               # no further report resolves it
    settlement.record_realization(journal, receipt=receipt, realized=1, source="founder_reported")   # idempotent
    [again] = settlement.awaiting_realization(journal)
    assert again["realized_values"] == [1, 2] and len(again["realization_events"]) == 2
