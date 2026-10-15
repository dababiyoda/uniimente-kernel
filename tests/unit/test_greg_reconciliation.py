"""Founder reconciliation of an UNCERTAIN dispatch, on a real body.

An executor exception between the Gate's dispatch and its receipt makes the action UNCERTAIN;
the founder then states whether it executed. The reconciliation record is a new fact about
that same attempt: it names the capability the dispatch used, books the signed spend cap when
the founder says it executed, counts once in routing, and is never a receipted execution that
routing can blame or a consumer can bind from. The founder key is a per-test key, not Alfonso's.
"""
from types import SimpleNamespace

import pytest

from foundry.systems import reputation
from greg import resilience, routing
from greg.body import Body
from greg.missions import Unbound
from greg.tribunal import morning_report
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy


def explode_once(body, capability="fs.write"):
    """The first dispatch dies mid-effect (power loss), so the Gate records no receipt."""
    real, calls = body.registry.adapters[capability], []

    def adapter(params, ctx):
        calls.append(params)
        if len(calls) == 1:
            raise RuntimeError("power lost mid-effect")
        return real(params, ctx)
    body.registry.adapters[capability] = adapter
    return calls


def tick(body, clock, n):
    for _ in range(n):
        body.tick()
        clock.advance(1)


def reconcile(body, key, body_id, clock, answer, *, after=6):
    [request] = [r for r in body.engine.book.open_requests() if r["kind"] == "RECONCILIATION"]
    drop(body.layout.home, signed(key, body_id, "DECISION", {
        "request_id": request["request_id"], "answer": answer, "reason": "inspected the retained evidence"}))
    tick(body, clock, after)
    return request


def actions(body, mission_id=None):
    return [e.payload for e in body.journal.replay("mission.action")
            if mission_id is None or e.payload["mission_id"] == mission_id]


@pytest.mark.parametrize("answer", ["reconcile_executed", "reconcile_not_executed"])
def test_reconciling_a_function_named_strategy_names_the_dispatched_capability(tmp_path, answer):
    home, key, body_id, _ = make_body(tmp_path)
    note = workspace(home, "m:reconcile-fn") / "c.txt"
    drop(home, signed(key, body_id, "MISSION", mission(
        "m:reconcile-fn", checks=[note_check("c", note, "ok")],
        strategies=[{"action_id": "w", "function": "filesystem.write", "target": "workspace:c.txt",
                     "params": {"relative_path": "c.txt", "content": "ok"}, "advances": ["c"],
                     "rationale": "write through whichever capability serves the function"}],
        capabilities=["fs.read", "fs.write"])))
    clock = Clock()
    with Body(home, clock=clock) as body:
        explode_once(body)
        tick(body, clock, 3)
        assert [a["status"] for a in actions(body)] == ["UNCERTAIN"]
        reconcile(body, key, body_id, clock, answer)
        # every reader of mission.action renders the reconciled ledger
        report = resilience.summary(body.journal)
        morning = morning_report(body.journal, body.engine)
        assert set(report["after_failure"]) == {"fs.write"}
        assert {r["capability"] for r in morning["routing_knowledge"]} >= {"fs.write"}
        reconciled = [a for a in actions(body) if a.get("route") == "founder_reconciliation"]
        assert len(reconciled) == 1
        assert reconciled[0]["capability"] == "fs.write" and reconciled[0]["attempt"] == 0
        assert reconciled[0]["receipt"] is None and reconciled[0]["dispatch_route"] == "api"
        # a founder reconciliation is not a receipted execution for routing to blame
        assert not [o for o in body.journal.replay("routing.outcome") if not o.payload.get("receipt")]


@pytest.mark.parametrize("answer, sequence, counts", [
    ("reconcile_not_executed", [("w", 0, "UNCERTAIN"), ("w", 0, "RECONCILED_NOT_EXECUTED"), ("w", 1, "DONE")],
     {"done": 1, "failed": 1, "founder_reconciled": 0, "ineffective": 0}),
    ("reconcile_executed", [("w", 0, "UNCERTAIN"), ("w", 0, "DONE"), ("w2", 0, "DONE")],
     {"done": 1, "failed": 0, "founder_reconciled": 1, "ineffective": 0}),
])
def test_routing_counts_one_outcome_per_attempt_and_a_reconciliation_is_no_receipted_success(
        tmp_path, answer, sequence, counts):
    home, key, body_id, _ = make_body(tmp_path)
    note = workspace(home, "m:reconcile-routing") / "c.txt"
    drop(home, signed(key, body_id, "MISSION", mission(
        "m:reconcile-routing", checks=[note_check("c", note, "ok")],
        strategies=[write_strategy("w", "c.txt", "ok", ["c"]),
                    write_strategy("w2", "c.txt", "ok, by the alternative", ["c"])],
        capabilities=["fs.read", "fs.write"])))
    clock = Clock()
    with Body(home, clock=clock) as body:
        explode_once(body)
        tick(body, clock, 3)
        reconcile(body, key, body_id, clock, answer)
        assert [(a["action_id"], a["attempt"], a["status"]) for a in actions(body)] == sequence
        assert body.engine.book.missions["m:reconcile-routing"].status == "ACHIEVED"
        record = routing.track_record(body.journal)["fs.write"]
    assert {k: record.get(k, 0) for k in counts} == counts
    assert routing.reliability(record) == routing.reliability({**record, "founder_reconciled": 0})


def test_a_paid_action_reconciled_as_executed_books_its_signed_cap_against_the_budget(tmp_path):
    """The founder says the paid dispatch ran, but no provider measured it: the signed cap is spent."""
    home, key, body_id, _ = make_body(tmp_path)
    note = workspace(home, "m:reconcile-paid") / "c.txt"
    spec = mission("m:reconcile-paid", checks=[note_check("c", note, "ok")],
                   strategies=[write_strategy("a", "c.txt", "ok", ["c"], cost_usd=0.6),
                               write_strategy("b", "c.txt", "ok, paid again", ["c"], cost_usd=0.6)],
                   capabilities=["fs.read", "fs.write"], budget=1.0)
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        explode_once(body)
        tick(body, clock, 3)
        reconcile(body, key, body_id, clock, "reconcile_executed")
        # a second 0.6 would pass the signed 1.0 budget: it is not run, it is asked for
        assert not [a for a in actions(body) if a["action_id"] == "b"]
        [ask] = body.engine.book.open_requests()
        assert ask["kind"] == "APPROVAL" and ask["action_id"] == "b"
        m = body.engine.book.missions["m:reconcile-paid"]
        assert m.spent_usd == pytest.approx(0.6) and m.status == "ACTIVE" and not note.exists()
        [reconciled] = [a for a in actions(body) if a.get("route") == "founder_reconciliation"]
        assert reconciled["cost_usd"] == reconciled["cost_cap_usd"] == 0.6
        assert reconciled["spend_basis"] == "signed_cap: founder reconciled executed; provider spend unknown"
        from greg.mission_control import cost_rows
        [row] = cost_rows(actions(body), [{"mission_id": "m:reconcile-paid", "cone": spec["light_cone"]}], [])
        assert row["booked_usd"] == row["unknown_at_cap_usd"] == 0.6 and row["measured_usd"] == 0.0


def reconciled_done(mission_id, action_id, attempt, capability):
    """Exactly the record the engine writes when the founder answers reconcile_executed."""
    return {"mission_id": mission_id, "action_id": action_id, "attempt": attempt, "status": "DONE",
            "capability": capability, "route": "founder_reconciliation", "dispatch_route": "api", "receipt": None,
            "at": "2026-10-14T12:00:00Z", "reasons": ["founder reconciliation: reconcile_executed"], "cost_usd": 0.0}


def test_a_signed_binding_never_falls_back_past_a_reconciled_execution(tmp_path):
    from tests.unit.test_greg_bindings import composed, run as run_composed
    home, key, body_id, _ = make_body(tmp_path)
    spec, _ = composed(home)
    drop(home, signed(key, body_id, "MISSION", spec))
    assert run_composed(home)[0][-1] == "ACHIEVED"
    with Body(home) as body:
        consumer = next(s for s in spec["strategies"] if s["action_id"] == "write-b")
        assert body.engine._bind(body.engine.book.missions["m:composed"], consumer)[2]   # bound from a receipt
        # write-a ran again; that run died mid-dispatch and the founder said it executed: its output is unknown
        body.journal.record("mission.action", reconciled_done("m:composed", "write-a", 1, "fs.write"),
                            key=["m:composed", "write-a", "reconciled", "test"])
        body.engine.book.rebuild()
        with pytest.raises(Unbound, match="write-a's latest execution was reconciled without a retained receipt"):
            body.engine._bind(body.engine.book.missions["m:composed"], consumer)


def test_a_pipeline_input_never_falls_back_past_a_reconciled_execution(tmp_path):
    from greg.pipeline import BindingError, resolve
    from tests.integration.test_greg_pipeline import binding, build_mission
    home, key, body_id, data = make_body(tmp_path)
    (data / "source.txt").write_text("Evidence 42\n")
    drop(home, signed(key, body_id, "MISSION", build_mission(home, data / "source.txt")))
    clock = Clock()
    with Body(home, clock=clock) as body:
        tick(body, clock, 1)
        assert [a["status"] for a in actions(body)] == ["DONE"]
        assert resolve({"content": binding()}, body.journal, "m:pipeline")[0] == {"content": "Evidence 42\n"}
        body.journal.record("mission.action", reconciled_done("m:pipeline", "read", 1, "fs.read"),
                            key=["m:pipeline", "read", "reconciled", "test"])
        with pytest.raises(BindingError, match="read's latest execution was reconciled without a retained receipt"):
            resolve({"content": binding()}, body.journal, "m:pipeline")


def test_the_morning_report_renders_a_reconciliation_retained_before_it_carried_a_time(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    note = workspace(home, "m:reconcile-legacy") / "c.txt"
    drop(home, signed(key, body_id, "MISSION", mission(
        "m:reconcile-legacy", checks=[note_check("c", note, "ok")],
        strategies=[write_strategy("w", "c.txt", "ok", ["c"])], capabilities=["fs.read", "fs.write"])))
    clock = Clock()
    with Body(home, clock=clock) as body:
        tick(body, clock, 3)
        # the shape written before 2026-10-14: no capability, route, receipt or at
        body.journal.record("mission.action", {"mission_id": "m:reconcile-legacy", "action_id": "w", "attempt": 0,
                                               "status": "DONE", "cost_usd": 0.0,
                                               "reasons": ["founder reconciliation: reconcile_executed"]},
                            key=["m:reconcile-legacy", "w", "reconciled", "legacy"])
        report = morning_report(body.journal, body.engine)
    assert report["report_digest"] and len(report["q7_surprises"]) <= 1   # only the timed action is judged
    assert [a["at"] is None for a in report["q3_what_i_did"]] == [False, True]


def test_a_reconciled_brief_cannot_be_labelled_because_it_retained_no_inputs(tmp_path):
    from greg import improvement, tribunal
    home, key, body_id, _ = make_body(tmp_path)
    with Body(home) as body:
        body.journal.record("mission.action", reconciled_done("m:brief", "deliver", 0, improvement.CAPABILITY),
                            key=["m:brief", "reconciled"])
        target = body.journal.replay("mission.action")[-1]
        for evidence in ({"attention": {"missed": [], "noise": ["acme/kernel#1"]}},
                         {"failure_claim": {"missed_failing": ["acme/kernel#2"]}}):
            with pytest.raises(tribunal.CritiqueError, match="reconciled brief has no retained inputs to label"):
                tribunal.critique(body.journal, body.engine, {"target_event_id": target.event_id, "verdict": "reject",
                                                              "evidence_type": "founder_judgment", "text": "noisy",
                                                              **evidence}, "sha256:" + "c" * 64)
        assert not body.journal.replay("critique.recorded")


def test_sop_extraction_excludes_founder_reconciled_steps_consistently(tmp_path):
    from greg import sop
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    for n, reconciled in ((1, True), (2, False), (3, False)):
        mid = f"m:reconcile-sop-{n}"
        drop(home, signed(key, body_id, "MISSION", mission(
            mid, checks=[note_check("c", workspace(home, mid) / "c.txt", "ok")],
            strategies=[write_strategy("w", "c.txt", "ok", ["c"]),
                        write_strategy("w2", "c.txt", "ok, by the alternative", ["c"])],
            capabilities=["fs.read", "fs.write"])))
        with Body(home, clock=clock) as body:
            if reconciled:
                explode_once(body)
                tick(body, clock, 3)
                reconcile(body, key, body_id, clock, "reconcile_executed")
            else:
                tick(body, clock, 4)
            assert body.engine.book.missions[mid].status == "ACHIEVED"
    with Body(home, clock=clock) as body:
        procedures = sop.closed_procedures(body.journal)
        proposed = [e.payload for e in body.journal.replay("sop.proposed")]
    # the appraiser verified only receipted steps; the reconciled one is not part of the procedure
    assert procedures == {f"m:reconcile-sop-{n}": ["fs.write"] for n in (1, 2, 3)}
    assert len(proposed) == 1 and proposed[0]["occurrences"] == 3
    assert "founder-reconciled steps" in proposed[0]["evidence_level"]


def _verifier():
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / "scripts" / "verify_one_machine.py"
    spec = importlib.util.spec_from_file_location("verify_one_machine", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Ledger:
    def __init__(self, *hashes):
        self.records = {h: SimpleNamespace(record_type="receipt", payload={"result": {"output": {"patch": h}}})
                        for h in hashes}

    def find(self, record_hash):
        return self.records.get(record_hash)


def test_the_one_machine_verifier_counts_only_receipted_commissions_and_either_reconciliation():
    outcomes = _verifier().commission_outcomes
    uncertain = {"mission_id": "m", "action_id": "commission", "attempt": 0, "status": "UNCERTAIN", "receipt": None}
    executed = reconciled_done("m", "commission", 0, "worker.commission")
    legacy = {"mission_id": "m", "action_id": "commission", "attempt": 0, "status": "DONE", "cost_usd": 0.0,
              "reasons": ["founder reconciliation: reconcile_executed"]}
    not_executed = {**executed, "status": "RECONCILED_NOT_EXECUTED",
                    "reasons": ["founder reconciliation: reconcile_not_executed"]}
    rerun = {**uncertain, "attempt": 1, "status": "DONE", "receipt": "sha256:rerun"}
    ledger = Ledger("sha256:rerun")
    retried = outcomes([uncertain, not_executed, rerun], ledger)
    assert retried["done"] == [rerun] and retried["reconciled"] == [not_executed]
    assert retried["reconciled_executed"] == []
    for said_executed in (executed, legacy):     # no receipt: reported, never counted or dereferenced
        judged = outcomes([uncertain, said_executed], ledger)
        assert judged["done"] == [] and judged["reconciled"] == judged["reconciled_executed"] == [said_executed]
    forged = {**rerun, "receipt": "sha256:not-on-the-ledger"}
    assert outcomes([forged], ledger)["done"] == []


class Journal:
    """A retained journal as readers see it: append-only payloads, some written before 2026-10-14."""

    def __init__(self):
        self.events = []

    def add(self, kind, payload, at="2026-10-13T08:00:00+00:00"):
        self.events.append(SimpleNamespace(type="greg." + kind, payload=payload, occurred_at=at,
                                           event_id=f"ev-{len(self.events)}"))
        return self

    def replay(self, prefix=""):
        return [e for e in self.events if e.type.startswith("greg." + prefix)]


def test_readers_tolerate_legacy_and_unnamed_reconciliation_records():
    uncertain = {"mission_id": "m1", "action_id": "w", "attempt": 0, "status": "UNCERTAIN", "capability": "fs.write",
                 "route": "api", "receipt": None, "cost_usd": 0.0, "at": "2026-10-13T08:00:00+00:00"}
    legacy = {"mission_id": "m1", "action_id": "w", "attempt": 0, "status": "DONE", "cost_usd": 0.0,
              "reasons": ["founder reconciliation: reconcile_executed"]}   # no capability, route, receipt or at
    unnamed = {"mission_id": "m2", "action_id": "f", "attempt": 0, "status": "RECONCILED_NOT_EXECUTED",
               "capability": None, "route": "founder_reconciliation", "receipt": None, "cost_usd": 0.0,
               "reasons": ["founder reconciliation: reconcile_not_executed"], "at": "2026-10-13T09:00:00+00:00"}
    j = Journal().add("mission.action", uncertain).add("mission.action", legacy).add("mission.action", unnamed)
    j.add("mission.action", {**uncertain, "mission_id": "m2", "action_id": "g", "status": "UNAVAILABLE"})
    j.add("routing.outcome", {"mission_id": "m2", "action_id": "f", "capability": None, "verdict": "ineffective",
                              "receipt": None, "reason": "retained before the reconciliation named its capability"})
    j.add("mission.appraised", {"mission_id": "m1", "verdict": "VERIFIED", "checks": {}})
    record = routing.track_record(j)
    # the legacy reconciliation replaces its attempt's UNCERTAIN and inherits the capability it reconciles
    assert record["fs.write"] == {"done": 0, "failed": 1, "ineffective": 0, "refuted": 0, "verified": 0,
                                  "founder_reconciled": 1}
    assert [r["capability"] for r in routing.routing_knowledge(j)] == ["?", "fs.write"]
    summary = resilience.summary(j)
    assert set(summary["after_failure"]) == {"?", "fs.write"}
    assert [c["capability"] for c in summary["common_cause_candidates"]] == ["fs.write"]
    events = [{"type": e.type, "event_id": e.event_id, "payload": e.payload, "at": e.occurred_at} for e in j.events]
    assert [r["subject"] for r in reputation.from_greg(events)] == ["?"]


def test_a_second_uncertain_dispatch_of_one_action_gets_its_own_founder_question(tmp_path):
    """Second review (measurement 4, pre-existing): the RECONCILIATION request was keyed on the action's
    scope alone, so a re-run that went UNCERTAIN again reused the answered request; the old answer was
    applied to the new attempt and every later tick raised EventError (same fact key, other content)."""
    home, key, body_id, _ = make_body(tmp_path)
    note = workspace(home, "m:twice") / "c.txt"
    drop(home, signed(key, body_id, "MISSION", mission(
        "m:twice", checks=[note_check("c", note, "ok")],
        strategies=[{"action_id": "w", "capability": "fs.write", "target": "workspace:c.txt",
                     "params": {"relative_path": "c.txt", "content": "ok"}, "advances": ["c"], "rationale": "w"}],
        capabilities=["fs.read", "fs.write"])))
    clock = Clock()
    with Body(home, clock=clock) as body:
        real, calls = body.registry.adapters["fs.write"], []

        def adapter(params, ctx):
            calls.append(1)
            if len(calls) <= 2:
                raise RuntimeError("power lost mid-effect")
            return real(params, ctx)
        body.registry.adapters["fs.write"] = adapter
        tick(body, clock, 3)
        first = reconcile(body, key, body_id, clock, "reconcile_not_executed")      # raised EventError before
        [second] = [r for r in body.engine.book.open_requests() if r["kind"] == "RECONCILIATION"]
        assert second["request_id"] != first["request_id"]
        reconcile(body, key, body_id, clock, "reconcile_not_executed")
        assert [(a["attempt"], a["status"]) for a in actions(body)][:4] == [
            (0, "UNCERTAIN"), (0, "RECONCILED_NOT_EXECUTED"), (1, "UNCERTAIN"), (1, "RECONCILED_NOT_EXECUTED")]
        assert body.engine.book.missions["m:twice"].status == "ACHIEVED"


def test_a_pipeline_consumer_of_a_reconciled_producer_is_held_and_the_alternative_runs(tmp_path):
    """Second review (spend 2): a ``$from_action`` consumer whose producer was reconciled without a
    receipt blocked the mission with a self-clearing no_strategy every tick: the alternative never ran
    and the founder was never asked. The consumer is now held at selection, like a signed bind edge."""
    home, key, body_id, _ = make_body(tmp_path)
    out = workspace(home, "m:pipe") / "b.txt"
    drop(home, signed(key, body_id, "MISSION", mission(
        "m:pipe", checks=[note_check("copied", out, "ok")],
        strategies=[write_strategy("produce", "a.txt", "ok", ["copied"]),
                    {"action_id": "copy", "capability": "fs.write", "target": "workspace:b.txt",
                     "params": {"relative_path": "b.txt",
                                "content": {"$from_action": {"action_id": "produce", "field": "path",
                                                             "type": "string"}}},
                     "advances": ["copied"], "rationale": "consume the producer's output"},
                    write_strategy("alt", "b.txt", "ok", ["copied"])],
        capabilities=["fs.read", "fs.write"])))
    clock = Clock()
    with Body(home, clock=clock) as body:
        explode_once(body)
        tick(body, clock, 3)
        reconcile(body, key, body_id, clock, "reconcile_executed", after=0)
        for _ in range(12):
            body.tick()
            clock.advance(60)
        ran = [a["action_id"] for a in actions(body, "m:pipe")]
        assert "alt" in ran and "copy" not in ran
        assert body.engine.book.missions["m:pipe"].status == "ACHIEVED"
        assert not [e for e in body.journal.replay("mission.blocked") if e.payload["blocker"]["type"] == "no_strategy"]
