"""Round 3 of the review of #221 (session_01Kucyfoabgsg6W8H8xj4qea, #221 comment 6499707581).

Decision-value cases run on injected settled counts through the compiler's own rules, as the review's probes did;
the reconcile, inbox and text cases run on a real body with a per-test founder key or on the fixture journal.
Values are synthetic test inputs.
"""
from __future__ import annotations

import json
from datetime import timedelta
from functools import lru_cache
from types import SimpleNamespace

import pytest

pytest.importorskip("networkx")
pytest.importorskip("scipy")

from greg.cognition import compiler, settlement  # noqa: E402
from greg.cognition.contracts import digest  # noqa: E402
from tests.greg_fixtures import signed  # noqa: E402
from tests.unit.test_greg_construction_realization import PROMISED, Run  # noqa: E402
from tests.unit.test_greg_pending_construction_realization import appraise, pending  # noqa: E402
from tests.unit.test_greg_recombine import PORTFOLIO  # noqa: E402


def weigh(monkeypatch, counts, disputes):
    monkeypatch.setattr(compiler, "_settled_counts", lambda journal: counts)
    rows = [{"method": m, "mission_id": "m", "check_passed": True} for m, d in disputes.items() for _ in range(d)]
    settlement._weigh_investigations(object(), rows, settling={"m": object()})
    return {r["method"]: r for r in rows}


# --- the decision value ----------------------------------------------------------------------------------------


def test_f2r_1_another_disputed_method_is_walked_over_every_count_it_can_reach(monkeypatch):
    """X (36, 29) with 1 dispute, Z (17, 16) with 2, C (30, 12) first: with Z at 17 of 19 the pick goes X, Z, X."""
    row = weigh(monkeypatch, {"construction.X": (36, 29), "construction.Z": (17, 16), "fit.C": (30, 12)},
                {"construction.X": 1, "construction.Z": 2})["construction.X"]
    assert row["priority"] == "investigate"
    assert any("with construction.Z at" in r for r in row["decision_impact"]["could_change"])


def test_f2r_6_the_joint_preference_walk_alone_finds_the_change(monkeypatch):
    """X (36, 24) with 4 disputes, Y (31, 28) with 2: only Y's joint state (33, 28) makes X's resolution matter."""
    counts = {"construction.X": (36, 24), "construction.Y": (31, 28)}
    row = weigh(monkeypatch, counts, {"construction.X": 4, "construction.Y": 2})["construction.X"]
    assert row["priority"] == "investigate"
    assert any("with construction.Y at" in r for r in row["decision_impact"]["could_change"])
    held, _ = settlement._preference_changes("construction.X", settlement._resolution_states(36, 24, 4), counts, {},
                                             lru_cache(maxsize=None)(compiler._settled_inhibition))
    assert held == []                                                   # with Y held, nothing changes


def test_f2r_2_a_gap_between_another_methods_reachable_values_is_not_a_tie(monkeypatch):
    """X (30, 16) with 1 dispute reaches {0.515, 0.531, 0.545}; none of Y (5, 2) with 3's values lies there."""
    rows = weigh(monkeypatch, {"construction.X": (30, 16), "construction.Y": (5, 2)},
                 {"construction.X": 1, "construction.Y": 3})
    assert rows["construction.X"]["priority"] == "hold"


def test_f2r_3_a_cut_short_walk_reads_investigate_without_claiming_a_change(monkeypatch):
    counts = {"construction.A": (30, 30), **{f"fit.f{i}": (20, 10) for i in range(9)}}   # undemoted, never preferred
    row = weigh(monkeypatch, counts, {"construction.A": 1})["construction.A"]
    assert row["decision_impact"]["could_change"] == [] and row["decision_impact"]["walk_limits"]
    assert row["priority"] == "investigate"
    assert row["priority_why"].startswith("the walk could not be completed")


def test_jointly_more_than_three_other_disputed_methods_is_a_stated_limit(monkeypatch):
    counts = {f"construction.M{i}": (20 + i, 10 + i) for i in range(5)}
    rows = weigh(monkeypatch, counts, {m: 1 for m in counts})
    for row in rows.values():
        assert row["priority"] == "investigate"
        assert any("exceed the joint method limit" in w for w in row["decision_impact"]["walk_limits"])


def test_f2r_4_the_inhibition_rule_is_computed_once_per_count(monkeypatch):
    calls = []
    real = compiler._settled_inhibition
    monkeypatch.setattr(compiler, "_settled_inhibition", lambda n, k: calls.append((n, k)) or real(n, k))
    counts = {f"construction.M{i}": (20 + i, 10 + i) for i in range(3)}
    weigh(monkeypatch, counts, {m: 3 for m in counts})
    assert len(calls) == len(set(calls))


# --- reconcile and links ---------------------------------------------------------------------------------------


def _live(journal):
    settled = journal.replay("cognition.settled")
    superseded = {e.payload.get("supersedes") for e in settled}
    return [e for e in settled if e.payload.get("compile_receipt") and e.event_id not in superseded
            and not e.payload.get("invalidated") and not e.payload.get("merged_into")]


def test_f1_r3_1_a_body_reconciled_by_8e91315c_converges_in_one_pass(tmp_path, monkeypatch):
    """8e91315c wrote the new-version row N, then invalidated the old head: the identity's latest row is the
    invalidation and N is a second live head."""
    with Run(tmp_path) as run:
        journal = run.body.journal
        current_rule = settlement._answer_version
        with monkeypatch.context() as old:
            old.setattr(settlement, "_answer_version", lambda built: digest(["engine-1", built.get("result")]))
            record = run.ask("pf-r3-1", PORTFOLIO)
            run.realize(record, PROMISED, source="external_record")
            settlement.reconcile(journal)
        old_head = [e for e in journal.replay("cognition.settled") if e.payload.get("compile_receipt")][-1]
        new = journal.record("cognition.settled", {**old_head.payload, "supersedes": None, "answer_version":
                             current_rule(record.payload["result"]["output"])}, key=["base", "new-row"])
        journal.record("cognition.settled", {**old_head.payload, "invalidated": True, "supersedes": old_head.event_id,
                       "reason": "current appraisal no longer supports competence; history retained"},
                       key=["base", "invalidate"])
        settlement.reconcile(journal)
        [live] = _live(journal)
        merged = [e for e in journal.replay("cognition.settled") if e.payload.get("merged_into")]
        assert [e.payload["supersedes"] for e in merged] == [new.event_id]
        assert merged[0].payload["merged_into"] == live.event_id                     # this pass's final row (F1-r3-2)
        once = len(journal.replay("cognition.settled"))
        settlement.reconcile(journal)
        assert len(journal.replay("cognition.settled")) == once


def test_r3_n33_a_merged_chains_own_receipt_links_the_claims_current_settlement():
    def event(event_id, **payload):
        return SimpleNamespace(event_id=event_id, payload=payload)
    events = [event("a", compile_receipt="c1", correct=True, supersedes=None),
              event("b", compile_receipt="c2", correct=True, supersedes=None),
              event("b-merged", compile_receipt="c2", correct=True, supersedes="b", merged_into="a", invalidated=True),
              event("a-invalid", compile_receipt="c1", correct=True, supersedes="a", invalidated=True)]
    links = settlement.receipt_links(SimpleNamespace(replay=lambda kind: events))
    assert links["c1"]["outcome_link"] == links["c2"]["outcome_link"] == "a-invalid"
    assert links["c2"]["invalidated"] is True


# --- G4-a through both real writers --------------------------------------------------------------------------------


def _ordered_pair(run, pid):
    record = run.ask(pid, PORTFOLIO)
    run.realize(record, PROMISED - 1, source="founder_reported")
    run.realize(record, PROMISED, source="external_record")
    run.realize(record, PROMISED - 1, source="sensor_observation")
    ids = {e.payload["source"]: e.event_id for e in run.body.journal.replay("cognition.realization")
           if e.payload.get("kind") == "objective" and e.payload["receipt"] == record.hash}
    r1 = {"receipt": record.hash, "resolves": [ids["external_record"], ids["sensor_observation"]],
          "accept": ids["sensor_observation"], "note": "R1"}
    r2 = {"receipt": record.hash, "resolves": [ids["founder_reported"], ids["sensor_observation"]],
          "accept": ids["sensor_observation"], "note": "R2"}
    return record, r1, r2


def test_g4f7_1_send_signed_keeps_signing_order_in_the_inbox(tmp_path, monkeypatch):
    from greg import founder
    from greg.body import send_signed
    with Run(tmp_path) as run:
        record, r1, r2 = _ordered_pair(run, "pf-send")
        t1 = run.clock().replace(microsecond=0)
        real = founder.sign_command
        for body, at in ((r2, t1 + timedelta(milliseconds=500)), (r1, t1)):
            monkeypatch.setattr(founder, "sign_command", lambda *a, _at=at, **kw: real(*a, **{**kw, "now": _at}))
            send_signed(run.home, run.key, "REALIZATION", body)
        monkeypatch.setattr(founder, "sign_command", real)
        run.body.ingest_inbox()
        assert [e.payload["note"] for e in settlement._resolutions(run.body.journal)] == ["R1", "R2"]


def test_g4f7_1_the_remote_command_endpoint_keeps_signing_order_in_the_inbox(tmp_path):
    from greg import remote
    from greg.body import Body
    with Run(tmp_path) as run:
        record, r1, r2 = _ordered_pair(run, "pf-remote")
        t1 = run.clock().replace(microsecond=0)
        envelopes = [signed(run.key, run.body_id, "REALIZATION", r2, now=t1 + timedelta(milliseconds=500)),
                     signed(run.key, run.body_id, "REALIZATION", r1, now=t1)]
        home, clock = run.home, run.clock
    for envelope in envelopes:
        code, _, _ = remote.handle(home, "POST", "/api/command", {}, json.dumps(envelope).encode(), now=clock())
        assert code == 202
    with Body(home, clock=clock) as body:
        body.ingest_inbox()
        assert [e.payload["note"] for e in settlement._resolutions(body.journal)] == ["R1", "R2"]


# --- F7-a: pending, final and none -----------------------------------------------------------------------------------


def test_g4f7_3_the_unsettled_texts_follow_closures_awaiting_appraisal():
    assert settlement._unsettled_why(None, False).startswith("pending: the mission has no closure yet")
    assert settlement._unsettled_why(None, True).startswith("final: the mission ended (abandoned or superseded) without an appraisal")
    assert settlement._unsettled_why("REFUTED", True).startswith("final: the mission is closed")
    assert settlement._unsettled_why("REFUTED", False).startswith("none: the mission's latest appraisal (REFUTED)")
    assert settlement._unsettled_why("REFUTED", True, True).startswith("pending: a closure of this mission awaits")


@pytest.mark.parametrize("case", ["no closure", "achieved, appraisal pending", "achieved, refuted"])
def test_g4f7_2_the_row_text_follows_the_missions_closures(case, monkeypatch):
    from tests.unit.test_greg_outcome_resolution import report
    monkeypatch.setattr(settlement, "_signed_realizations", lambda journal: getattr(journal, "signed", {}))
    journal, receipt = pending()
    if case != "no closure":
        journal.record("mission.achieved", {"mission_id": "m:pending-fixture"})
    if case == "achieved, refuted":
        appraise(journal, "REFUTED")
    report(journal, receipt, 1, "founder_reported")
    report(journal, receipt, 2, "external_record")
    [row] = settlement.awaiting_realization(journal)
    expected = {"no closure": "pending: the mission has no closure yet",
                "achieved, appraisal pending": "pending: a closure of this mission awaits appraisal",
                "achieved, refuted": "final: the mission is closed and its latest appraisal (REFUTED)"}[case]
    assert row["competence_claim"].startswith(expected) and row["scored_as"] == f"nothing: {row['competence_claim']}"
    assert row["priority"] == "hold" and row["priority_why"].startswith("no resolution changes competence now")


def test_g4f7_6_the_evidence_request_lists_only_rejected_independent_signed_reports(monkeypatch):
    from tests.unit.test_greg_outcome_resolution import facts, report, resolve
    monkeypatch.setattr(settlement, "_signed_realizations", lambda journal: getattr(journal, "signed", {}))
    journal, receipt = pending()
    appraise(journal, "VERIFIED")
    report(journal, receipt, 1, "founder_reported")
    report(journal, receipt, 2, "external_record")
    ids = facts(journal)
    resolve(journal, receipt, list(ids.values()), None, note="both mis-keyed")    # invalidates both
    report(journal, receipt, 1, "founder_reported")
    report(journal, receipt, 2, "founder_reported")
    [row] = [r for r in settlement.awaiting_realization(journal) if r.get("kind") == "objective_conflict"]
    why = row["evidence_request"]["why"]
    assert ids["external_record:2"] in why and ids["founder_reported:1"] not in why
