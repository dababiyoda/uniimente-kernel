"""A disputed world outcome becomes investigable work and can be corrected, without losing the evidence.

Founder directive, 2026-10-28 (on #210): contradiction -> investigation -> evidence -> authorized resolution ->
corrected competence. A construction answer's world outcome has an explicit state (``settlement.WORLD_STATES``).
A resolution is a founder-signed REALIZATION that accepts one independent observation already recorded, or
invalidates the named reports; a signed report proves who reported it, not that it is true. Every fact stays on
the record. Fixture receipts and values are synthetic.
"""
from __future__ import annotations

import pytest

from greg.cognition import settlement
from tests.unit.test_greg_pending_construction_realization import answer, appraise, observe, pending


def signed(journal, digest):
    """What the body records after it applied a founder-signed REALIZATION command."""
    journal.record("command.accepted", {"kind": "REALIZATION", "digest": digest})


def resolve(journal, receipt, resolves, accept, note="time-clock export, 2026-10-28", digest="sha256:r1"):
    payload = settlement.record_resolution(journal, receipt=receipt, resolves=resolves, accept=accept, note=note,
                                           command_digest=digest)
    signed(journal, digest)
    return payload


def facts(journal):
    return {e.payload["source"] + ":" + repr(e.payload["realized"]): e.event_id
            for e in journal.replay("cognition.realization") if e.payload.get("kind") == "objective"}


def disputed():
    """promise 2 (tolerance 0.1): a founder report of 1 (unmet) and an external record of 2 (met)."""
    journal, receipt = pending()
    appraise(journal, "VERIFIED")
    settlement.record_realization(journal, receipt=receipt, realized=1, source="founder_reported")
    settlement.record_realization(journal, receipt=receipt, realized=2, source="external_record")
    return journal, receipt


def counts(journal):
    return [(r["count"], r["correct"]) for r in settlement.competence(journal).values()]


def test_a_dispute_is_investigable_work_with_a_prepared_resolution_and_scores_nothing():
    journal, receipt = disputed()
    [row] = settlement.awaiting_realization(journal)
    assert row["kind"] == "objective_conflict" and row["world_state"] == "disputed"
    assert {(r["source"], r["met"]) for r in row["reports"]} == {("founder_reported", False), ("external_record", True)}
    assert "at or above 1.9" in row["distinguishing_observation"]
    assert row["competence_claim"].startswith("withheld") and counts(journal) == []
    assert row["resolvable_now"] is True
    body = row["prepared_resolution"]["body"]
    assert body["accept"] == facts(journal)["external_record:2"] and sorted(body["resolves"]) == sorted(facts(journal).values())
    assert row["priority"] in ("investigate", "hold") and row["decision_impact"]["open_disputes"] == 1
    assert row["authority_created"] is False


def test_with_no_independent_observation_it_asks_for_one_instead_of_resolving():
    journal, receipt = pending()
    appraise(journal, "VERIFIED")
    settlement.record_realization(journal, receipt=receipt, realized=1, source="founder_reported")
    settlement.record_realization(journal, receipt=receipt, realized=2, source="founder_reported")
    [row] = settlement.awaiting_realization(journal)
    assert row["resolvable_now"] is False and "prepared_resolution" not in row
    request = row["evidence_request"]
    assert request["why"] == "no independent observation is recorded" and "--source external_record" in request["how"]
    with pytest.raises(ValueError, match="accepts only an independent observation"):
        resolve(journal, receipt, list(facts(journal).values()), facts(journal)["founder_reported:2"])


def test_an_authorized_resolution_accepts_the_independent_record_keeps_every_fact_and_corrects_competence():
    journal, receipt = disputed()
    before = list(facts(journal).values())
    resolve(journal, receipt, before, facts(journal)["external_record:2"])
    [outcome] = settlement.measured_outcomes(journal)
    world = outcome["world"]
    assert world["state"] == "adjudicated" and world["realized"] == 2 and outcome["correct"] is True
    assert world["rejected_events"] == [facts(journal)["founder_reported:1"]] and world["resolution_event"]
    assert "independent observation" in outcome["evidence_tier"]
    assert sorted(facts(journal).values()) == sorted(before)              # nothing deleted
    assert counts(journal) == [(1, 1)] and settlement.awaiting_realization(journal) == []


def test_a_resolution_no_founder_command_accepted_resolves_nothing():
    journal, receipt = disputed()
    settlement.record_resolution(journal, receipt=receipt, resolves=list(facts(journal).values()),
                                 accept=facts(journal)["external_record:2"], note="forged",
                                 command_digest="sha256:never-accepted")
    [row] = settlement.awaiting_realization(journal)
    assert row["world_state"] == "disputed" and counts(journal) == []
    with pytest.raises(ValueError, match="founder-signed"):
        settlement.record_resolution(journal, receipt=receipt, resolves=list(facts(journal).values()),
                                     accept=None, note="x", command_digest=None)


@pytest.mark.parametrize("case", ["no basis", "unknown event", "accept not named", "partial"])
def test_malformed_or_partial_resolutions_are_refused(case):
    journal, receipt = disputed()
    ids = facts(journal)
    external, founder = ids["external_record:2"], ids["founder_reported:1"]
    args = {"no basis": ([founder, external], external, " "), "unknown event": ([founder, "e:999"], None, "n"),
            "accept not named": ([founder], external, "n"), "partial": ([external], external, "n")}[case]
    with pytest.raises(ValueError):
        resolve(journal, receipt, args[0], args[1], note=args[2])


def test_a_resolution_on_one_answer_cannot_name_another_answers_report():
    journal, first = pending()
    later = answer(journal, result={"profit": 4})
    observe(journal, later)
    appraise(journal, "VERIFIED")
    settlement.record_realization(journal, receipt=first, realized=2, source="external_record")
    settlement.record_realization(journal, receipt=later, realized=1, source="founder_reported")
    with pytest.raises(ValueError, match="only realization facts recorded about this answer"):
        resolve(journal, later, list(facts(journal).values()), facts(journal)["external_record:2"])


def test_invalidating_every_report_returns_the_answer_to_awaiting_a_new_one():
    journal, receipt = disputed()
    resolve(journal, receipt, list(facts(journal).values()), None, note="both reports read the wrong roster")
    [outcome] = settlement.measured_outcomes(journal)
    assert outcome["world"]["state"] == "invalidated" and outcome["correct"] is True      # certificate only
    [row] = settlement.awaiting_realization(journal)
    assert row["receipt"] == receipt and row["world_state"] == "invalidated"
    assert sorted(row["invalidated_events"]) == sorted(facts(journal).values())


def test_a_new_disagreeing_report_after_a_resolution_reopens_the_dispute_and_a_later_resolution_governs():
    journal, receipt = disputed()
    resolve(journal, receipt, list(facts(journal).values()), facts(journal)["external_record:2"])
    other = answer(journal, recorded="again")                        # the same answer on a later receipt
    observe(journal, other)
    settlement.record_realization(journal, receipt=other, realized=1.5, source="sensor_observation")
    [row] = settlement.awaiting_realization(journal)
    assert row["world_state"] == "disputed" and row["resolvable_now"] is False      # two independent values
    live = [r["event"] for r in row["reports"]]
    resolve(journal, other, live, facts(journal)["sensor_observation:1.5"], note="sensor recalibrated",
            digest="sha256:r2")
    [outcome] = settlement.measured_outcomes(journal)
    assert outcome["world"]["state"] == "adjudicated" and outcome["world"]["realized"] == 1.5
    assert outcome["correct"] is False and counts(journal) == [(1, 0)]


def test_values_that_differ_but_agree_on_the_verdict_settle_without_investigation():
    journal, receipt = pending()
    appraise(journal, "VERIFIED")
    settlement.record_realization(journal, receipt=receipt, realized=2, source="founder_reported")
    settlement.record_realization(journal, receipt=receipt, realized=1.95, source="founder_reported")
    [outcome] = settlement.measured_outcomes(journal)
    assert outcome["world"]["state"] == "verdict_concordant" and outcome["world"]["realized"] is None
    assert outcome["world"]["realized_values"] == [1.95, 2] and outcome["correct"] is True
    assert settlement.awaiting_realization(journal) == []


def test_an_answer_no_signed_check_observed_has_nothing_to_resolve():
    journal, receipt = pending(observed=False)
    settlement.record_realization(journal, receipt=receipt, realized=2, source="external_record")
    with pytest.raises(ValueError, match="no signed check observed"):
        resolve(journal, receipt, list(facts(journal).values()), None)


def test_settlement_itself_refuses_a_signed_resolution_that_accepts_a_founder_report():
    """record_resolution refuses it; a payload written around that check, even under an accepted command, still
    resolves nothing: settlement re-applies the independent-source rule on replay."""
    journal, receipt = disputed()
    ids = facts(journal)
    journal.record("cognition.realization", {"receipt": receipt, "kind": "resolution", "resolves": list(ids.values()),
                                             "accept": ids["founder_reported:1"], "note": "around the check",
                                             "command_digest": "sha256:direct", "authority_created": False})
    signed(journal, "sha256:direct")
    [row] = settlement.awaiting_realization(journal)
    assert row["world_state"] == "disputed" and counts(journal) == []


def test_a_resolution_never_relabels_a_reports_source():
    """Integrator intake condition 2 (#196, 6476642680): a founder signature is attestation, never independent
    measurement. Every fact keeps the source it was reported with; the settled outcome names the accepted fact's own
    source; the resolution itself carries no source and cannot turn a founder report into an observation."""
    journal, receipt = disputed()
    before = {e.event_id: e.payload["source"] for e in journal.replay("cognition.realization")}
    resolution = resolve(journal, receipt, list(facts(journal).values()), facts(journal)["external_record:2"])
    assert "source" not in resolution and "realized" not in resolution
    after = {e.event_id: e.payload.get("source") for e in journal.replay("cognition.realization")
             if e.payload.get("kind") == "objective"}
    assert after == before
    [outcome] = settlement.measured_outcomes(journal)
    assert outcome["world"]["source"] == "external_record" and outcome["world"]["state"] == "adjudicated"
    assert "founder_reported" not in outcome["evidence_tier"]          # the rejected report lends no label
