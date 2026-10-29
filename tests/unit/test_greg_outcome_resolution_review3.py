"""Cross-session review of #221 (session_01Kucyfoabgsg6W8H8xj4qea, #221 comment 6491739752).

The decision-value counterexamples (F2-a to F2-d, T-a, the weighed hold) run on injected settled counts through the
compiler's own rules, as the review's probes did. The rest run on a real body with a per-test founder key, or on the
fixture journal for the row texts. Values are synthetic test inputs.
"""
from __future__ import annotations

from datetime import timedelta

import pytest

pytest.importorskip("networkx")
pytest.importorskip("scipy")

from greg.cognition import compiler, settlement  # noqa: E402
from tests.greg_fixtures import signed  # noqa: E402
from tests.unit.test_greg_construction_realization import PROMISED, Run  # noqa: E402
from tests.unit.test_greg_pending_construction_realization import appraise, pending  # noqa: E402
from tests.unit.test_greg_recombine import PORTFOLIO  # noqa: E402


def weigh(monkeypatch, counts, disputes):
    """Rows for ``disputes`` (method -> open disputes), weighed against ``counts``; method -> (priority, reasons)."""
    monkeypatch.setattr(compiler, "_settled_counts", lambda journal: counts)
    rows = [{"method": m, "mission_id": "m", "check_passed": True} for m, d in disputes.items() for _ in range(d)]
    settlement._weigh_investigations(object(), rows, settling={"m": object()})
    return {r["method"]: (r["priority"], r["decision_impact"]["could_change"], r["priority_why"]) for r in rows}


# --- the decision value ----------------------------------------------------------------------------------------


def test_f2_a_above_the_subset_limit_the_row_is_never_a_clean_hold(monkeypatch):
    """The review's three-way case plus G (30, 30) and seven fillers: ten co-eligible fits exceed the subset limit,
    and the A, B, C family in between changes the pick."""
    counts = {"fit.A": (20, 10), "construction.B": (10, 10), "fit.C": (12, 6), "fit.G": (30, 30),
              **{f"fit.f{i}": (10 + i, 3) for i in range(7)}}
    priority, reasons, _ = weigh(monkeypatch, counts, {"construction.B": 1})["construction.B"]
    assert priority == "investigate"
    assert any("pairs and the whole family only" in r for r in reasons)


def test_f2_b_a_non_monotone_pick_between_the_extremes_is_investigated(monkeypatch):
    """X (38, 16) with 4 open disputes first; B (24, 23), C (30, 28), D (13, 13): B at 0 and at 4 kept, C at 1."""
    counts = {"construction.X": (38, 16), "fit.B": (24, 23), "fit.C": (30, 28), "fit.D": (13, 13)}
    priority, reasons, _ = weigh(monkeypatch, counts, {"construction.X": 4})["construction.X"]
    assert priority == "investigate"
    assert any("selects differently as the disputes resolve" in r for r in reasons)


def test_f2_c_joint_disputes_of_two_methods_are_weighed_together(monkeypatch):
    """X (17, 6) with 1 dispute, Y (22, 9) with 2: X kept and both of Y's failed puts X ahead (0.400 > 0.385)."""
    rows = weigh(monkeypatch, {"construction.X": (17, 6), "construction.Y": (22, 9)},
                 {"construction.X": 1, "construction.Y": 2})
    for method, other in (("construction.X", "construction.Y"), ("construction.Y", "construction.X")):
        priority, reasons, _ = rows[method]
        assert priority == "investigate"
        assert any(f"Laplace rank against {other}" in r and "as its own disputes resolve" in r for r in reasons)


def test_f2_d_a_demoted_fit_is_never_tested_as_the_first_fit(monkeypatch):
    """X (11, 7) with 2 disputes; A (18, 4) is demoted. compiler.run never ranks a demoted fit first."""
    priority, reasons, _ = weigh(monkeypatch, {"construction.X": (11, 7), "fit.A": (18, 4)},
                                 {"construction.X": 2})["construction.X"]
    assert priority == "hold" and reasons == []


def test_f2_f_the_reason_names_the_selected_fit_never_none(monkeypatch):
    counts = {"fit.A": (20, 10), "construction.B": (10, 10), "fit.C": (12, 6)}
    _, reasons, _ = weigh(monkeypatch, counts, {"construction.B": 1})["construction.B"]
    assert reasons and not any("None" in r for r in reasons)


def test_a_weighed_hold_stays_a_hold(monkeypatch):
    """The review's G2-F3-a case: A (4, 4) with one dispute and B (3, 2) can change nothing."""
    priority, reasons, why = weigh(monkeypatch, {"construction.A": (4, 4), "fit.B": (3, 2)},
                                   {"construction.A": 1})["construction.A"]
    assert (priority, reasons) == ("hold", []) and "no resolution changes a selection rule" in why


@pytest.mark.parametrize("counts", [
    {"construction.B": (10, 10), "fit.C": (11, 10)},      # C's 11/13 equals B's lower bound
    {"construction.B": (2, 2), "fit.C": (3, 3)},          # C's 4/5 equals B's upper bound
])
def test_t_a_a_tie_at_a_bound_is_investigated_on_the_tie_alone(monkeypatch, counts):
    """1/2 lies outside B's bounds here, so only the inclusive comparison with C flags the row."""
    priority, reasons, _ = weigh(monkeypatch, counts, {"construction.B": 1})["construction.B"]
    assert priority == "investigate"
    assert [r for r in reasons if "Laplace rank against fit.C" in r] and not [r for r in reasons if "unsettled" in r]


# --- F1-a: chains an earlier rule kept apart are merged, and none outlasts the claim ---------------------------


def test_f1_a_two_old_rule_chains_of_one_answer_leave_one_live_head_and_none_after_a_withdrawal(tmp_path, monkeypatch):
    with Run(tmp_path) as run:
        journal = run.body.journal
        from greg.cognition.contracts import digest
        with monkeypatch.context() as old:
            old.setattr(settlement, "_answer_version", lambda built: digest(["engine-1", built.get("result")]))
            record = run.ask("pf-f1a", PORTFOLIO)
            run.realize(record, PROMISED, source="external_record")
            settlement.reconcile(journal)
        first = [e for e in journal.replay("cognition.settled") if e.payload.get("compile_receipt")][-1]
        # the same answer settled under another engine label: a second chain, as 917404cf left it
        journal.record("cognition.settled", {**first.payload, "answer_version": digest(["engine-2", "x"]),
                                             "supersedes": None}, key=["old-rule", "engine-2"])

        def live():
            settled = journal.replay("cognition.settled")
            superseded = {e.payload.get("supersedes") for e in settled}
            return [e for e in settled if e.payload.get("compile_receipt") and e.event_id not in superseded
                    and not e.payload.get("invalidated") and not e.payload.get("merged_into")]

        settlement.reconcile(journal)
        assert len(live()) == 1
        merged = [e for e in journal.replay("cognition.settled") if e.payload.get("merged_into")]
        assert len(merged) == 1 and merged[0].payload["reason"].startswith("merged:")
        once = len(journal.replay("cognition.settled"))
        settlement.reconcile(journal)
        assert len(journal.replay("cognition.settled")) == once                    # idempotent
        mission = next(e.payload["mission_id"] for e in journal.replay("mission.observed")
                       if e.payload["receipt"] == record.hash)
        appraise(journal, "UNAVAILABLE", mission_id=mission)                        # the settling appraisal is withdrawn
        settlement.reconcile(journal)
        assert live() == []
        compile_receipt = record.payload["result"]["output"]["receipt_id"]
        assert settlement.receipt_links(journal)[compile_receipt]["invalidated"] is True


# --- G4: inbox order, an equal stamp, disjoint facts --------------------------------------------------------------


def _three_reports(run, pid):
    record = run.ask(pid, PORTFOLIO)
    run.realize(record, PROMISED - 1, source="founder_reported")                   # f1: 1, unmet
    run.realize(record, PROMISED, source="external_record")                        # f2: 2, met
    ids = {e.payload["source"]: e.event_id for e in run.body.journal.replay("cognition.realization")
           if e.payload.get("kind") == "objective" and e.payload["receipt"] == record.hash}
    return record, ids


def test_g4_a_the_inbox_reads_a_whole_second_command_before_one_signed_half_a_second_later(tmp_path):
    from greg.body import inbox_stamp
    import json
    with Run(tmp_path) as run:
        record, ids = _three_reports(run, "pf-g4a")
        run.realize(record, PROMISED - 1, source="sensor_observation")             # f3: 1, unmet, independent
        f3 = next(e.event_id for e in run.body.journal.replay("cognition.realization")
                  if e.payload.get("source") == "sensor_observation")
        t1 = run.clock().replace(microsecond=0)
        r1 = signed(run.key, run.body_id, "REALIZATION", {"receipt": record.hash, "resolves": [
                    ids["external_record"], f3], "accept": f3, "note": "R1"}, now=t1)
        # R2 is valid only after R1: before it, f2 (2) still disagrees with f3 (1) and R2 does not name it
        r2 = signed(run.key, run.body_id, "REALIZATION", {"receipt": record.hash, "resolves": [
                    ids["founder_reported"], f3], "accept": f3, "note": "R2"}, now=t1 + timedelta(milliseconds=500))
        raw = sorted([r1["issued_at"].replace(":", ""), r2["issued_at"].replace(":", "")])
        assert raw[0] == r2["issued_at"].replace(":", "")                          # the old names misorder them
        for env, kind in ((r2, "b"), (r1, "a")):
            (run.home / "inbox" / f"{inbox_stamp(env['issued_at'])}-realization-{kind}.json").write_text(
                json.dumps(env))
        run.body.ingest_inbox()
        assert [e.payload["note"] for e in settlement._resolutions(run.body.journal)] == ["R1", "R2"]
        outcome = run.outcome(record)
        assert outcome["world"]["state"] == "adjudicated" and outcome["correct"] is False


def test_g4_d_an_equal_stamp_is_accepted_and_takes_effect(tmp_path):
    with Run(tmp_path) as run:
        record, ids = _three_reports(run, "pf-g4d")
        at = run.clock()
        named = [ids["founder_reported"], ids["external_record"]]
        run.body.apply(signed(run.key, run.body_id, "REALIZATION", {"receipt": record.hash, "resolves": named,
                                                                    "accept": ids["external_record"], "note": "R1"},
                              now=at))
        run.body.apply(signed(run.key, run.body_id, "REALIZATION", {"receipt": record.hash, "resolves": named,
                                                                    "accept": None, "note": "R2, same stamp"}, now=at))
        assert [e.payload["note"] for e in settlement._resolutions(run.body.journal)] == ["R1", "R2, same stamp"]
        assert run.outcome(record)["world"]["state"] == "invalidated"


def test_g4_f_an_older_signed_resolution_on_disjoint_facts_is_applied(tmp_path):
    with Run(tmp_path) as run:
        record, ids = _three_reports(run, "pf-g4f")
        run.realize(record, PROMISED, source="sensor_observation")                 # f3: 2, met, independent
        f3 = next(e.event_id for e in run.body.journal.replay("cognition.realization")
                  if e.payload.get("source") == "sensor_observation")
        at = run.clock()
        run.body.apply(signed(run.key, run.body_id, "REALIZATION", {
            "receipt": record.hash, "resolves": [ids["founder_reported"], ids["external_record"]],
            "accept": ids["external_record"], "note": "newer"}, now=at))
        run.body.apply(signed(run.key, run.body_id, "REALIZATION", {
            "receipt": record.hash, "resolves": [f3], "accept": f3, "note": "older, disjoint"},
            now=at - timedelta(minutes=2)))
        assert sorted(e.payload["note"] for e in settlement._resolutions(run.body.journal)) == ["newer",
                                                                                               "older, disjoint"]
        outcome = run.outcome(record)
        assert outcome["world"]["state"] == "adjudicated" and outcome["correct"] is True


def test_g4_b_the_refusal_leads_with_the_instruction(tmp_path):
    with Run(tmp_path) as run:
        record, ids = _three_reports(run, "pf-g4b")
        named = [ids["founder_reported"], ids["external_record"]]
        at = run.clock()
        run.body.apply(signed(run.key, run.body_id, "REALIZATION", {"receipt": record.hash, "resolves": named,
                                                                    "accept": ids["external_record"], "note": "new"},
                              now=at))
        with pytest.raises(ValueError) as refused:
            run.body.apply(signed(run.key, run.body_id, "REALIZATION", {"receipt": record.hash, "resolves": named,
                                                                        "accept": None, "note": "old"},
                                  now=at - timedelta(minutes=1)))
        assert str(refused.value)[:300].startswith("sign a new resolution if still wanted")


# --- F7: the row says why nothing is scored ------------------------------------------------------------------------


@pytest.mark.parametrize("passed", [True, False])
def test_t_b_a_mission_whose_appraisal_settles_nothing_says_so_whatever_the_check(passed, monkeypatch):
    from tests.unit.test_greg_outcome_resolution import report
    monkeypatch.setattr(settlement, "_signed_realizations", lambda journal: getattr(journal, "signed", {}))
    journal, receipt = pending()
    for event in journal.events:
        if getattr(event, "type", "") == "greg.mission.observed":
            event.payload["passed"] = passed
    appraise(journal, "REFUTED")
    report(journal, receipt, 1, "founder_reported")
    report(journal, receipt, 2, "external_record")
    [row] = settlement.awaiting_realization(journal)
    assert row["scored_as"].startswith("nothing: none: the mission's latest appraisal (REFUTED) settles nothing")
    assert row["competence_claim"].startswith("none: the mission's latest appraisal (REFUTED) settles nothing")
    assert row["priority"] == "hold" and "REFUTED" in row["priority_why"]


# --- F8-a: the memo reruns the founder pass only when a founder record lands --------------------------------------


def test_f8_a_the_signed_realization_memo_reruns_only_on_a_founder_record(tmp_path, monkeypatch):
    from greg import goal_gravity
    with Run(tmp_path) as run:
        journal = run.body.journal
        record = run.ask("pf-f8a", PORTFOLIO)
        run.realize(record, PROMISED, source="external_record")
        calls = []
        real = goal_gravity.founder_facts
        monkeypatch.setattr(goal_gravity, "founder_facts", lambda ledger, **kw: calls.append(1) or real(ledger, **kw))
        settlement._SIGNED.clear()
        first = settlement._signed_realizations(journal)
        assert settlement._signed_realizations(journal) == first and len(calls) == 1          # a repeated read
        settlement.record_realization(journal, receipt=record.hash, realized=PROMISED - 1, source="founder_reported")
        assert settlement._signed_realizations(journal) == first and len(calls) == 1          # an in-process fact
        run.realize(record, PROMISED - 2, source="sensor_observation")
        after = settlement._signed_realizations(journal)
        assert len(after) == len(first) + 1 and len(calls) >= 2                               # a REALIZATION
        seen = len(calls)
        assert settlement._signed_realizations(journal) == after and len(calls) == seen       # cached again
        settlement._SIGNED.clear()
        assert settlement._signed_realizations(journal) == after                              # equals a fresh pass
