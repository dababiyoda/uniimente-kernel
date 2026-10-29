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


@pytest.fixture(autouse=True)
def signed_commands(monkeypatch):
    """Fixture journals have no founder ledger. Settlement reads verified REALIZATION envelopes through
    ``_signed_realizations``; here a journal's ``signed`` map stands in for what ``goal_gravity.signed_commands``
    would verify. Real envelopes are exercised in test_greg_outcome_resolution_signed.py."""
    monkeypatch.setattr(settlement, "_signed_realizations", lambda journal: getattr(journal, "signed", {}),
                        raising=False)


def sign(journal, digest, body, issued_at=None):
    """Register one verified founder-signed REALIZATION envelope (its digest, signed body and signing time)."""
    signed = journal.__dict__.setdefault("signed", {})
    signed[digest] = {"body": body, "principal": "founder",
                      "issued_at": issued_at or f"2026-10-28T12:{len(signed):02d}:00Z"}
    # the bare record a body also writes; it authenticates nothing (S1), and lets the pre-review code under test
    # honour the same legitimate commands, so a fail-before run shows the defect and not a fixture artefact
    journal.record("command.accepted", {"kind": "REALIZATION", "digest": digest})


def report(journal, receipt, realized, source, note=""):
    """A founder-signed REALIZATION report: the fact plus its verified envelope."""
    digest = f"sha256:report-{len(journal.events)}"
    payload = settlement.record_realization(journal, receipt=receipt, realized=realized, source=source, note=note,
                                            command_digest=digest)
    sign(journal, digest, {"receipt": receipt, "realized": realized, "source": source, "note": note})
    return payload


def resolve(journal, receipt, resolves, accept, note="time-clock export, 2026-10-28", digest="sha256:r1",
            issued_at=None):
    payload = settlement.record_resolution(journal, receipt=receipt, resolves=resolves, accept=accept, note=note,
                                           command_digest=digest)
    sign(journal, digest, {"receipt": receipt, "resolves": resolves, "accept": accept, "note": note}, issued_at)
    return payload


def facts(journal):
    return {e.payload["source"] + ":" + repr(e.payload["realized"]): e.event_id
            for e in journal.replay("cognition.realization") if e.payload.get("kind") == "objective"}


def disputed():
    """promise 2 (tolerance 0.1): a founder report of 1 (unmet) and an external record of 2 (met)."""
    journal, receipt = pending()
    appraise(journal, "VERIFIED")
    report(journal, receipt, 1, "founder_reported")
    report(journal, receipt, 2, "external_record")
    return journal, receipt


def counts(journal):
    return [(r["count"], r["correct"]) for r in settlement.competence(journal).values()]


def test_a_dispute_is_investigable_work_with_a_prepared_resolution_and_scores_nothing():
    journal, receipt = disputed()
    [row] = settlement.awaiting_realization(journal)
    assert row["kind"] == "objective_conflict" and row["world_state"] == "disputed"
    assert {(r["declared_source"], r["met"]) for r in row["reports"]} == {("founder_reported", False), ("external_record", True)}
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
    report(journal, receipt, 1, "founder_reported")
    report(journal, receipt, 2, "founder_reported")
    [row] = settlement.awaiting_realization(journal)
    assert row["resolvable_now"] is False and "prepared_resolution" not in row
    request = row["evidence_request"]
    assert request["why"] == "no signed report declared as an independent source is recorded" and "--source external_record" in request["how"]
    with pytest.raises(ValueError, match="accepts only a report declared as an independent source"):
        resolve(journal, receipt, list(facts(journal).values()), facts(journal)["founder_reported:2"])


def test_an_authorized_resolution_accepts_the_independent_record_keeps_every_fact_and_corrects_competence():
    journal, receipt = disputed()
    before = list(facts(journal).values())
    resolve(journal, receipt, before, facts(journal)["external_record:2"])
    [outcome] = settlement.measured_outcomes(journal)
    world = outcome["world"]
    assert world["state"] == "adjudicated" and world["realized"] == 2 and outcome["correct"] is True
    assert world["rejected_events"] == [facts(journal)["founder_reported:1"]] and world["resolution_event"]
    assert "declared by the reporter, not verified" in outcome["evidence_tier"]
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
    report(journal, first, 2, "external_record")
    report(journal, later, 1, "founder_reported")
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
    report(journal, other, 1.5, "sensor_observation")
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
    report(journal, receipt, 2, "founder_reported")
    report(journal, receipt, 1.95, "founder_reported")
    [outcome] = settlement.measured_outcomes(journal)
    assert outcome["world"]["state"] == "verdict_concordant" and outcome["world"]["realized"] is None
    assert outcome["world"]["realized_values"] == [1.95, 2] and outcome["correct"] is True
    assert settlement.awaiting_realization(journal) == []


def test_an_answer_no_signed_check_observed_has_nothing_to_resolve():
    journal, receipt = pending(observed=False)
    report(journal, receipt, 2, "external_record")
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
    sign(journal, "sha256:direct", {"receipt": receipt, "resolves": list(ids.values()),
                                    "accept": ids["founder_reported:1"], "note": "around the check"})
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


def test_a_founder_report_labelled_external_record_is_eligible_but_shown_as_declared_never_verified():
    """Integrator finding (#196 review of 67184991): ``source`` is whatever the REALIZATION command declared, so a
    founder can file a value as external_record and then accept it. That stays possible (GREG cannot verify the
    label); what it must never do is present the label as verification."""
    journal, receipt = pending()
    appraise(journal, "VERIFIED")
    report(journal, receipt, 1, "founder_reported")
    report(journal, receipt, 2, "external_record")                     # the founder's own key, labelled external
    [row] = settlement.awaiting_realization(journal)
    labelled = next(r for r in row["reports"] if r["declared_source"] == "external_record")
    assert labelled["independence"] == "declared by the reporter, not verified by GREG"
    assert labelled["eligible_to_accept"] is True and "independent" not in labelled and "verified" not in labelled
    assert row["source_independence"] == labelled["independence"]
    resolve(journal, receipt, list(facts(journal).values()), facts(journal)["external_record:2"])
    [outcome] = settlement.measured_outcomes(journal)
    assert outcome["world"]["source"] == "external_record"
    assert "declared by the reporter, not verified" in outcome["evidence_tier"]
    assert "verified independent" not in outcome["evidence_tier"]


# --- review of #210 (#196 comment 6481186880): S1-S11 ------------------------------------------------------------


def test_s1_a_resolution_carrying_another_signed_commands_digest_resolves_nothing():
    """S1: a resolution journaled with the digest of the founder's ordinary signed report (a body with no resolves)
    must not adjudicate; nor may two resolutions share one signed command."""
    journal, receipt = disputed()
    ids = facts(journal)
    report_digest = next(d for d, c in journal.signed.items() if "realized" in c["body"])
    journal.record("cognition.realization", {"receipt": receipt, "kind": "resolution", "resolves": list(ids.values()),
                                             "accept": ids["external_record:2"], "note": "borrowed signature",
                                             "command_digest": report_digest, "authority_created": False})
    [row] = settlement.awaiting_realization(journal)
    assert row["world_state"] == "disputed" and counts(journal) == []
    resolve(journal, receipt, list(ids.values()), ids["external_record:2"], digest="sha256:once")
    journal.record("cognition.realization", {"receipt": receipt, "kind": "resolution", "resolves": list(ids.values()),
                                             "accept": None, "note": "replayed digest",
                                             "command_digest": "sha256:once", "authority_created": False})
    [outcome] = settlement.measured_outcomes(journal)
    assert outcome["world"]["state"] == "adjudicated"          # the second use of one signed command is ignored


def test_s2_an_invalidation_must_name_every_live_report_and_never_adjudicates_the_founders_own():
    journal, receipt = pending()
    appraise(journal, "VERIFIED")
    report(journal, receipt, 2, "founder_reported")
    report(journal, receipt, 0, "external_record")
    with pytest.raises(ValueError, match="names every live report"):
        resolve(journal, receipt, [facts(journal)["external_record:0"]], None)
    # written around record time and signed: the founder report left standing is reported, never adjudicated
    ids = facts(journal)
    journal.record("cognition.realization", {"receipt": receipt, "kind": "resolution",
                                             "resolves": [ids["external_record:0"]], "accept": None, "note": "x",
                                             "command_digest": "sha256:partial", "authority_created": False})
    sign(journal, "sha256:partial", {"receipt": receipt, "resolves": [ids["external_record:0"]], "accept": None,
                                     "note": "x"})
    [outcome] = settlement.measured_outcomes(journal)
    assert outcome["world"]["state"] == "reported" and "accepted" not in outcome["evidence_tier"]


def test_s3_an_independent_report_matching_a_conflicting_value_is_recorded_and_makes_the_dispute_resolvable():
    journal, receipt = pending()
    appraise(journal, "VERIFIED")
    report(journal, receipt, 1, "founder_reported")
    report(journal, receipt, 2, "founder_reported")
    report(journal, receipt, 2, "external_record")             # what the evidence request asks for
    assert "external_record:2" in facts(journal)
    [row] = settlement.awaiting_realization(journal)
    assert row["resolvable_now"] is True


def test_s3_a_re_report_after_an_invalidation_is_a_new_fact_not_a_duplicate_of_a_rejected_one():
    journal, receipt = disputed()
    resolve(journal, receipt, list(facts(journal).values()), None, note="both read the wrong roster")
    before = len(journal.replay("cognition.realization"))
    report(journal, receipt, 2, "external_record")
    assert len(journal.replay("cognition.realization")) == before + 1
    [outcome] = settlement.measured_outcomes(journal)
    assert outcome["world"]["state"] == "reported" and outcome["world"]["realized"] == 2


def test_s4_an_older_signed_resolution_delivered_later_never_overrides_a_newer_one():
    journal, receipt = pending()
    appraise(journal, "VERIFIED")
    report(journal, receipt, 1, "sensor_observation")
    report(journal, receipt, 2, "external_record")
    ids = facts(journal)
    resolve(journal, receipt, list(ids.values()), ids["external_record:2"], digest="sha256:new",
            issued_at="2026-10-28T15:00:00Z")
    resolve(journal, receipt, list(ids.values()), ids["sensor_observation:1"], digest="sha256:old",
            issued_at="2026-10-28T09:00:00Z")                  # signed earlier, delivered later
    [outcome] = settlement.measured_outcomes(journal)
    assert outcome["world"]["realized"] == 2


def test_s6_a_dispute_on_an_answer_whose_check_failed_is_scored_wrong_and_has_no_decision_value():
    journal, receipt = pending(observed=False)
    observe(journal, receipt)
    journal.events[-1].payload["passed"] = False                # the signed check failed
    appraise(journal, "VERIFIED_UNMET")
    report(journal, receipt, 1, "founder_reported")
    report(journal, receipt, 2, "external_record")
    [outcome] = settlement.measured_outcomes(journal)
    assert outcome["correct"] is False and outcome["world"]["state"] == "disputed"
    [row] = settlement.awaiting_realization(journal)
    assert row["priority"] == "hold" and row["decision_impact"] is None and "check failed" in row["priority_why"]


def test_s7_a_dispute_whose_mission_cannot_settle_is_held_and_names_the_appraisal():
    journal, receipt = pending()
    appraise(journal, "REFUTED")
    report(journal, receipt, 1, "founder_reported")
    report(journal, receipt, 2, "external_record")
    [row] = settlement.awaiting_realization(journal)
    assert row["priority"] == "hold" and row["decision_impact"] is None and "REFUTED" in row["priority_why"]


def test_s9_an_unsigned_report_is_never_eligible_to_be_accepted():
    journal, receipt = pending()
    appraise(journal, "VERIFIED")
    report(journal, receipt, 1, "founder_reported")
    settlement.record_realization(journal, receipt=receipt, realized=2, source="external_record")   # no command
    [row] = settlement.awaiting_realization(journal)
    unsigned = next(r for r in row["reports"] if r["declared_source"] == "external_record")
    assert unsigned["eligible_to_accept"] is False and unsigned["signed_command"] is None
    assert row["resolvable_now"] is False
    with pytest.raises(ValueError, match="verified founder-signed"):
        resolve(journal, receipt, list(facts(journal).values()), facts(journal)["external_record:2"])


def test_s10_the_answer_version_ignores_the_engine_label():
    journal, first = pending(result={"profit": 2, "engine": "networkx 3.6.1"})
    later = answer(journal, result={"profit": 2, "engine": "networkx 3.7.0"}, again=True)
    observe(journal, later)
    appraise(journal, "VERIFIED")
    assert len(settlement.measured_outcomes(journal)) == 1


def test_s5_reconcile_supersedes_a_legacy_settlement_once_and_never_invalidates_it_later(monkeypatch):
    journal, receipt = pending()
    appraise(journal, "VERIFIED")
    original_record = journal.record
    monkeypatch.setattr(journal, "record", lambda kind, payload, key=None, sensitivity=None, causal_parent=None:
                        original_record(kind, payload, key=key, sensitivity=sensitivity), raising=False)
    built = settlement._constructed_outcome
    monkeypatch.setattr(settlement, "_constructed_outcome",                       # a module before answer versions
                        lambda *a, **k: {key: v for key, v in (built(*a, **k) or {}).items() if key != "answer_version"}
                        or None)
    settlement.reconcile(journal)
    monkeypatch.setattr(settlement, "_constructed_outcome", built)
    settlement.reconcile(journal)
    after_first = len(journal.replay("cognition.settled"))
    settlement.reconcile(journal)
    settled = journal.replay("cognition.settled")
    assert len(settled) == after_first, "a second pass wrote again"
    assert not any(e.payload.get("invalidated") for e in settled), "the superseded legacy row was invalidated"
    assert settled[-1].payload.get("answer_version") and settled[-1].payload["supersedes"] == settled[0].event_id


def weigh(monkeypatch, counts, rows):
    from greg.cognition import compiler
    monkeypatch.setattr(compiler, "_settled_counts", lambda journal: counts)
    settlement._weigh_investigations(object(), rows, settling={"m": object()})
    return rows


def test_s8_a_laplace_rank_flip_between_the_two_resolutions_is_investigated(monkeypatch):
    rows = weigh(monkeypatch, {"B": (1, 1)}, [{"method": "A", "mission_id": "m", "check_passed": True} for _ in range(2)])
    assert rows[0]["priority"] == "investigate"
    assert any("Laplace rank against B" in r for r in rows[0]["decision_impact"]["could_change"])


def test_s11_the_preference_bound_is_the_compilers_own_holm_rule(monkeypatch):
    from greg.cognition import compiler
    calls = []
    real = compiler._settled_preference
    monkeypatch.setattr(compiler, "_settled_preference", lambda eligible, settled: calls.append(
        [r["method"] for r in eligible]) or real(eligible, settled))
    weigh(monkeypatch, {"B": (12, 12)}, [{"method": "A", "mission_id": "m", "check_passed": True} for _ in range(10)])
    assert ["A", "B"] in calls and ["B", "A"] in calls


def test_s9_settlement_itself_refuses_a_signed_resolution_accepting_an_unsigned_report():
    """record_resolution refuses it; written around that check under a verified envelope, it still resolves nothing."""
    journal, receipt = pending()
    appraise(journal, "VERIFIED")
    report(journal, receipt, 1, "founder_reported")
    settlement.record_realization(journal, receipt=receipt, realized=2, source="external_record")   # no command
    ids = facts(journal)
    body = {"receipt": receipt, "resolves": list(ids.values()), "accept": ids["external_record:2"], "note": "around"}
    journal.record("cognition.realization", {**body, "kind": "resolution", "command_digest": "sha256:around",
                                             "authority_created": False})
    sign(journal, "sha256:around", body)
    [row] = settlement.awaiting_realization(journal)
    assert row["world_state"] == "disputed" and counts(journal) == []
