"""Second cross-session review of #219 (session_01Kucyfoabgsg6W8H8xj4qea, #196 comment 6485774890): F1-F8 and the
N2 guard. Each test is built from that review's probe, on a real body with a per-test founder key where the probe
used one. Values are synthetic test inputs.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("networkx")
pytest.importorskip("scipy")

from greg import gravity  # noqa: E402
from greg.cognition import compiler, settlement  # noqa: E402
from greg.cognition.contracts import digest  # noqa: E402
from greg.cognition.genomes.flow import maxflow_instance  # noqa: E402
from provenance.ledger import sha256_json  # noqa: E402
from tests.greg_fixtures import signed  # noqa: E402
from tests.unit.test_greg_construction_realization import PROMISED, Run, construction_id  # noqa: E402
from tests.unit.test_greg_recombine import CRASH, PORTFOLIO  # noqa: E402

FLOW = "cognition.flow_maxflow"


def facts(journal, receipt=None):
    return {e.payload["source"] + ":" + repr(e.payload["realized"]): e.event_id
            for e in journal.replay("cognition.realization")
            if e.payload.get("kind") == "objective" and (receipt is None or e.payload["receipt"] == receipt)}


def disputes(journal):
    return [r for r in settlement.awaiting_realization(journal) if r.get("kind") == "objective_conflict"]


def send(run, body, *, at):
    return run.body.apply(signed(run.key, run.body_id, "REALIZATION", body, now=at))


# --- F1: a body upgraded from the previous answer-version rule keeps its settlements --------------------------------


def test_f1_rows_written_under_the_old_answer_version_rule_are_revised_never_invalidated(tmp_path, monkeypatch):
    """917404cf hashed the provenance fields into ``answer_version``; reconcile on the current rule invalidated every
    such row on its first pass. Re-deriving the version from the retained receipt makes each the prior of its
    successor."""
    with Run(tmp_path) as run:
        journal = run.body.journal
        current_rule = settlement._answer_version
        with monkeypatch.context() as old:
            old.setattr(settlement, "_answer_version", lambda built: digest(built.get("result")))
            record = run.ask("pf-f1", PORTFOLIO)
            run.realize(record, PROMISED, source="external_record")
            settlement.reconcile(journal)
            legacy = [e for e in journal.replay("cognition.settled") if e.payload.get("compile_receipt")]
            assert legacy and all(e.payload["answer_version"] != current_rule(
                record.payload["result"]["output"]) for e in legacy)      # the two rules really differ here
        before = len(journal.replay("cognition.settled"))
        settlement.reconcile(journal)
        new = journal.replay("cognition.settled")[before:]
        assert new and not any(e.payload.get("invalidated") for e in new)
        assert all(e.payload["supersedes"] in {x.event_id for x in legacy} for e in new)
        assert not any(link["invalidated"] for link in settlement.receipt_links(journal).values())
        once = len(journal.replay("cognition.settled"))
        settlement.reconcile(journal)
        assert len(journal.replay("cognition.settled")) == once


# --- F2: the preference bound uses the whole Holm family ----------------------------------------------------------


def test_f2_a_change_only_the_three_way_holm_family_shows_is_investigated(monkeypatch):
    """The review's counterexample: A (20, 10) ranked first, B (10, 10) with one open dispute, C (12, 6). A pair is a
    Holm family of one; the compiler's three-way family prefers A if B's promise failed and B if it was kept."""
    counts = {"fit.A": (20, 10), "construction.B": (10, 10), "fit.C": (12, 6)}
    monkeypatch.setattr(compiler, "_settled_counts", lambda journal: counts)
    rows = [{"method": "construction.B", "mission_id": "m", "check_passed": True}]
    settlement._weigh_investigations(object(), rows, settling={"m": object()})
    assert rows[0]["priority"] == "investigate"
    assert any("fit.A ranked first among ['construction.B', 'fit.A', 'fit.C']" in r
               for r in rows[0]["decision_impact"]["could_change"]), rows[0]["decision_impact"]


# --- F3: an unsettled co-eligible fit and a tie at a bound ------------------------------------------------------------


def _gap_case(tmp_path, case, kept):
    """From the review's q3 probe: (a) the crash construction is disputed too, so it has no settled outcome and
    _rank reads it at 1/2; (b) the crash construction settled (1, 0), Laplace 1/3, equal to a bound."""
    with Run(tmp_path) as run:
        crash = run.ask("crash-a", CRASH)
        cost = crash.payload["result"]["output"]["result"]["cost"]
        if case == "a":
            run.realize(crash, cost + 10, source="founder_reported")
            run.realize(crash, cost, source="external_record")
        else:
            run.realize(crash, cost + 10, source="external_record")
        pf = run.ask("pf-b", PORTFOLIO)
        run.realize(pf, PROMISED - 2 if kept else PROMISED, source="founder_reported")
        run.realize(pf, PROMISED if kept else PROMISED - 2, source="external_record")
        [row] = [r for r in disputes(run.body.journal) if "selection" in r["method"]]
        seen = row["priority"]
        run.command("REALIZATION", {**row["prepared_resolution"]["body"], "note": "fixture outside record"})
        later = compiler.run({"problem_id": "later", "compile": {"geometry": {"geometry": "optimization"},
                                                                 "data": {**PORTFOLIO, **CRASH}, "execute": False}},
                             registry=run.body.registry, journal=run.body.journal)
        return seen, later["method_or_composition_selected"]


@pytest.mark.parametrize("case", ["a", "b"])
def test_f3_a_row_whose_resolution_flips_the_compile_is_investigated(tmp_path, case):
    (tmp_path / "k").mkdir(), (tmp_path / "f").mkdir()
    seen_k, selected_k = _gap_case(tmp_path / "k", case, kept=True)
    seen_f, selected_f = _gap_case(tmp_path / "f", case, kept=False)
    assert selected_k != selected_f                      # ground truth: the two resolutions select different fits
    assert seen_k == seen_f == "investigate"


def test_f3_on_the_public_path_a_laplace_rank_flip_is_investigated(tmp_path):
    """From the review's q3 public-path probe (S8): flow_maxflow (1, 1) against the construction (1, 1) plus one
    disputed answer; the two extreme resolutions straddle 2/3."""
    with Run(tmp_path) as run:
        run.command("CAPABILITY_ATTACH", {"capability_id": FLOW})
        run.ask("net-0", maxflow_instance(3)[0], allow=False)
        run.ask("pf-a", PORTFOLIO)
        disputed = run.ask("pf-b", PORTFOLIO)
        run.realize(disputed, PROMISED - 2, source="founder_reported")
        run.realize(disputed, PROMISED, source="external_record")
        cid = construction_id(run.body)
        assert compiler._settled_counts(run.body.journal) == {FLOW: (1, 1), cid: (1, 1)}
        [row] = disputes(run.body.journal)
        assert row["priority"] == "investigate"
        assert any(f"Laplace rank against {FLOW}" in r for r in row["decision_impact"]["could_change"])


# --- F4: resolutions order by signing instant; an older-signed one is refused with a reason ---------------------------


def _accepted_and_external(run, pid):
    record = run.ask(pid, PORTFOLIO)
    run.realize(record, PROMISED - 2, source="founder_reported")
    run.realize(record, PROMISED, source="external_record")
    ids = list(facts(run.body.journal, record.hash).values())
    return record, ids


def test_f4_a_later_resolution_signed_half_a_second_after_a_whole_second_takes_effect(tmp_path):
    """'...:00Z' sorted after '...:00.500000Z' as strings; instants order them correctly."""
    with Run(tmp_path) as run:
        record, (f1, f2) = _accepted_and_external(run, "pf-f4-string")
        t1 = datetime.now(timezone.utc).replace(microsecond=0)
        send(run, {"receipt": record.hash, "resolves": [f1, f2], "accept": f2, "note": "R1"}, at=t1)
        run.realize(record, PROMISED - 2, source="sensor_observation")
        f3 = next(x for x in facts(run.body.journal, record.hash).values() if x not in (f1, f2))
        send(run, {"receipt": record.hash, "resolves": [f2, f3], "accept": f3, "note": "R2"},
             at=t1 + timedelta(milliseconds=500))
        assert [e.payload["note"] for e in settlement._resolutions(run.body.journal)] == ["R1", "R2"]
        outcome = run.outcome(record)
        assert outcome["world"]["state"] == "adjudicated" and outcome["correct"] is False
        assert disputes(run.body.journal) == []


def test_f4_a_resolution_signed_before_one_already_ruling_on_its_facts_is_refused_with_the_reason(tmp_path):
    """Clock skew and a held-back envelope: an older-signed resolution delivered later was APPLIED and ignored, and
    out-of-order deliveries could leave two accepted facts disputing again."""
    with Run(tmp_path) as run:
        record, (f1, f2) = _accepted_and_external(run, "pf-f4-held")
        now = datetime.now(timezone.utc)
        send(run, {"receipt": record.hash, "resolves": [f1, f2], "accept": f2, "note": "newer"}, at=now)
        with pytest.raises(ValueError, match="already rules on"):
            send(run, {"receipt": record.hash, "resolves": [f1, f2], "accept": None, "note": "older, held back"},
                 at=now - timedelta(minutes=10))
        outcome = run.outcome(record)
        assert outcome["world"]["state"] == "adjudicated" and outcome["correct"] is True
        # P (t0), Q (t2) delivered, then R (t1): R is refused, so replay leaves the state Q left
        other, (x, y) = _accepted_and_external(run, "pf-f4-pqr")
        send(run, {"receipt": other.hash, "resolves": [x, y], "accept": y, "note": "P"}, at=now - timedelta(minutes=20))
        send(run, {"receipt": other.hash, "resolves": [y], "accept": y, "note": "Q"}, at=now)
        with pytest.raises(ValueError, match="already rules on"):
            send(run, {"receipt": other.hash, "resolves": [x, y], "accept": x, "note": "R"},
                 at=now - timedelta(minutes=10))
        assert run.outcome(other)["world"]["state"] == "adjudicated" and disputes(run.body.journal) == []


def test_f4_a_fast_clock_earlier_resolution_refuses_a_later_one_until_re_signed_after_its_time(tmp_path):
    """The independent check of #220's case: R1 signed on a clock 4 minutes fast, R2 a minute later on a correct
    clock, naming a fact recorded after R1 was applied. R2 is refused with the reason, never applied as a no-op;
    signed after R1's time, it takes effect."""
    with Run(tmp_path) as run:
        record, (f1, f2) = _accepted_and_external(run, "pf-f4-skew")
        now = datetime.now(timezone.utc)
        send(run, {"receipt": record.hash, "resolves": [f1, f2], "accept": f2, "note": "R1"},
             at=now + timedelta(minutes=4))
        run.realize(record, PROMISED - 2, source="sensor_observation")
        f3 = next(x for x in facts(run.body.journal, record.hash).values() if x not in (f1, f2))
        body = {"receipt": record.hash, "resolves": [f2, f3], "accept": f3, "note": "R2"}
        with pytest.raises(ValueError, match="fast clock"):
            send(run, body, at=now + timedelta(minutes=1))
        assert [e.payload["note"] for e in settlement._resolutions(run.body.journal)] == ["R1"]
        send(run, {**body, "note": "R2, re-signed"}, at=now + timedelta(minutes=4, seconds=30))
        outcome = run.outcome(record)
        assert outcome["world"]["state"] == "adjudicated" and outcome["correct"] is False


# --- F5: a signed report is not absorbed by an unsigned fact --------------------------------------------------------


def test_f5_a_signed_report_matching_an_unsigned_fact_is_kept_and_can_be_accepted(tmp_path):
    with Run(tmp_path) as run:
        journal = run.body.journal
        record = run.ask("pf-f5", PORTFOLIO)
        run.realize(record, PROMISED - 2, source="founder_reported")
        settlement.record_realization(journal, receipt=record.hash, realized=PROMISED, source="external_record")
        [row] = disputes(journal)
        assert row["resolvable_now"] is False
        assert row["evidence_request"]["why"] == "no signed report declared as an independent source is recorded"
        run.realize(record, PROMISED, source="external_record")          # the founder signs the same report
        [row] = disputes(journal)
        assert row["resolvable_now"] is True
        run.command("REALIZATION", {**row["prepared_resolution"]["body"], "note": "billing export"})
        assert run.outcome(record)["world"]["state"] == "adjudicated"
        run.realize(record, PROMISED, source="external_record")          # a signed repeat stays idempotent
        assert len([e for e in journal.replay("cognition.realization") if e.payload.get("kind") == "objective"
                    and e.payload["source"] == "external_record"]) == 2


def test_f5_a_crash_before_acceptance_then_a_fresh_signature_records_a_signed_fact(tmp_path):
    with Run(tmp_path) as run:
        journal = run.body.journal
        record = run.ask("pf-f5-crash", PORTFOLIO)
        run.realize(record, PROMISED - 2, source="founder_reported")
        env = signed(run.key, run.body_id, "REALIZATION", {"receipt": record.hash, "realized": PROMISED,
                                                           "source": "external_record"}, now=run.clock(),
                     ttl=timedelta(hours=1))
        real_record = journal.record

        def crash(kind, payload, **kw):
            if kind == "command.accepted" and payload.get("digest") == sha256_json(env):
                raise SystemExit("power loss")
            return real_record(kind, payload, **kw)

        journal.record = crash
        with pytest.raises(SystemExit):
            run.body.apply(env)
        journal.record = real_record
        run.clock.advance(2 * 3600)                                     # down past the envelope's validity
        run.realize(record, PROMISED, source="external_record")
        [row] = disputes(journal)
        assert row["resolvable_now"] is True


# --- F6: only the founder's own signature resolves ----------------------------------------------------------------


def test_f6_a_verified_realization_a_device_signed_is_not_founder_evidence(tmp_path, monkeypatch):
    from greg import goal_gravity
    with Run(tmp_path) as run:
        journal = run.body.journal
        record = run.ask("pf-f6", PORTFOLIO)
        run.realize(record, PROMISED, source="external_record")
        real = goal_gravity.founder_facts

        def as_device(ledger, **kw):
            result = real(ledger, **kw)
            for command in result.signed.values():
                if command["kind"] == "REALIZATION":
                    command["principal"] = "device:phone"
            return result

        settlement._SIGNED.clear()
        monkeypatch.setattr(goal_gravity, "founder_facts", as_device)
        assert settlement._signed_realizations(journal) == {}
        settlement._SIGNED.clear()
        monkeypatch.undo()
        assert len(settlement._signed_realizations(journal)) == 1


# --- F7: row texts ------------------------------------------------------------------------------------------------


def test_f7_a_signed_report_without_a_source_is_shown_as_signed(tmp_path):
    with Run(tmp_path) as run:
        record = run.ask("pf-f7", PORTFOLIO)
        run.command("REALIZATION", {"receipt": record.hash, "realized": PROMISED - 2})   # source defaults
        run.realize(record, PROMISED, source="external_record")
        [row] = disputes(run.body.journal)
        founder = next(r for r in row["reports"] if r["declared_source"] == "founder_reported")
        assert founder["signed_command"]


# --- F8: the realization order is computed once per resolution -----------------------------------------------------


def test_f8_record_resolution_reads_the_realization_order_once(tmp_path, monkeypatch):
    with Run(tmp_path) as run:
        record, ids = _accepted_and_external(run, "pf-f8")
        for value in range(3, 8):
            run.realize(record, value, source="sensor_observation")
        calls = []
        real = settlement._realization_order
        monkeypatch.setattr(settlement, "_realization_order", lambda j: calls.append(1) or real(j))
        live = list(facts(run.body.journal, record.hash).values())
        run.command("REALIZATION", {"receipt": record.hash, "resolves": live, "accept": None, "note": "mis-keyed"})
        assert len(calls) == 1


# --- N2: the once-per-signed-command guard is load-bearing ---------------------------------------------------------


def test_n2_a_verbatim_copy_of_a_signed_resolution_changes_nothing(tmp_path):
    with Run(tmp_path) as run:
        journal = run.body.journal
        record = run.ask("pf-n2", PORTFOLIO)
        run.realize(record, PROMISED - 2, source="founder_reported")
        run.realize(record, PROMISED, source="external_record")
        [row] = disputes(journal)
        run.command("REALIZATION", {**row["prepared_resolution"]["body"], "note": "time-clock export"})
        [first] = [e for e in journal.replay("cognition.realization") if e.payload.get("kind") == "resolution"]
        settlement.reconcile(journal)
        run.ask("pf-n2-later", PORTFOLIO)
        settled = len(journal.replay("cognition.settled"))
        before = (settlement.decisions_to_recheck(journal), gravity._measured_trust(journal)["decisions_to_recheck"],
                  run.outcome(record)["world"])
        journal.record("cognition.realization", dict(first.payload), key=["replayed", first.event_id])
        assert (settlement.decisions_to_recheck(journal), gravity._measured_trust(journal)["decisions_to_recheck"],
                run.outcome(record)["world"]) == before
        settlement.reconcile(journal)
        assert len(journal.replay("cognition.settled")) == settled
        assert [e.event_id for e in settlement._resolutions(journal)] == [first.event_id]
        assert json.dumps(before[0])                                     # the projection stays serializable
