"""Unknown completion through the canonical Body, MissionEngine, AuthorityOffice and ConsequenceGate.

Mission H (directive section 33): "no unbounded retry loop, no duplicate irreversible consequence, and truthful
handling of unknown completion". A dispatch whose completion is unknown (UNCERTAIN) is reconciled by a signed
founder answer, never blindly retried; one answer settles exactly one dispatch; and the dispatch's worst case
(its signed cap) counts against the signed budget until it is settled.

Before (19bbdcb): the RECONCILIATION request id was derived from mission, kind and exact scope only, so after
one signed ``reconcile_not_executed`` every later UNCERTAIN dispatch of the same scope found the old answer and
was redispatched on every tick with no new ask (9 dispatches of a $0.40 action under a $1.00 budget), and
UNCERTAIN spend was booked as $0.00, so the budget never bounded it.

In-process Body with a test clock and a per-test Ed25519 key (not Alfonso's): SANDBOX_VERIFIED.
"""
from __future__ import annotations

from greg.body import Body
from greg.capabilities import CapabilityManifest
from tests.greg_fixtures import Clock, drop, make_body, mission, signed, workspace


def _capability(body, effects: list, *, retry_safe: bool):
    """A capability that performs its effect and then loses power before the Gate's receipt."""
    manifest = CapabilityManifest(
        capability_id="test.flaky", version="1.0.0", provider="test", function="test.flaky",
        description="writes, then dies before its receipt", route="api",
        consequence_class="read_only" if retry_safe else "internal_write", inputs={"x": "str"},
        outputs={"ok": "bool"}, strengthens=("proof",), target_prefix="probe:", retry_safe=retry_safe)

    def adapter(params, ctx):
        effects.append(ctx.grant_id)
        raise RuntimeError("power lost mid-effect")
    body.registry.register(manifest, adapter, state="ATTACHED")


def _spec(data, *, retry_safe: bool, cost: float, budget: float):
    ceiling = "read_only" if retry_safe else "internal_write"
    return mission("m:unknown", checks=[{
        "check_id": "c", "description": "never true", "sensor": {
            "capability": "fs.read", "params": {"path": str(data / "never.txt")}, "target": "fs:never.txt"},
        "predicate": {"op": "contains", "field": "text", "value": "x"}}],
        strategies=[{"action_id": "act", "capability": "test.flaky", "params": {}, "target": "probe:x",
                     "advances": ["c"], "rationale": "test", "cost_usd": cost}],
        capabilities=["fs.read", "test.flaky"], targets=("fs:*", "probe:*"), ceiling=ceiling, budget=budget)


def _open(home, clock, effects, *, retry_safe):
    body = Body(home, clock=clock).open()
    _capability(body, effects, retry_safe=retry_safe)
    body.boot()
    return body


def _ticks(body, clock, n, seconds=60):
    states = []
    for _ in range(n):
        clock.advance(seconds)
        states.append(body.tick()["missions"][0]["state"])
    return states


def _requests(body, kind="RECONCILIATION"):
    return [e.payload for e in body.journal.replay("decision.requested") if e.payload["kind"] == kind]


def _actions(body):
    return [(e.payload["status"], e.payload["attempt"]) for e in body.journal.replay("mission.action")]


def test_one_reconciliation_answer_settles_exactly_one_dispatch(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _spec(data, retry_safe=False, cost=0.4, budget=1.0)))
    clock, effects = Clock(), []
    body = _open(home, clock, effects, retry_safe=False)
    try:
        assert _ticks(body, clock, 6) == ["BLOCKED"] + ["WAITING"] * 5
        assert len(effects) == 1 and _actions(body) == [("UNCERTAIN", 0)]
        first = _requests(body)
        assert len(first) == 1
        # The ask states what each answer books: an unmetered dispatch's "not executed" releases its reservation.
        assert first[0]["evidence"]["booked_usd_by_answer"] == {"reconcile_executed": 0.4,
                                                                "reconcile_not_executed": 0.0}
        assert "metered" not in first[0]["recommendation"]
        reserved_before = body.engine.book.missions["m:unknown"].__dict__.get("reserved")

        drop(home, signed(key, body_id, "DECISION", {"request_id": first[0]["request_id"],
                                                     "answer": "reconcile_not_executed", "reason": "test"}))
        states = _ticks(body, clock, 11)
        # The answer settles attempt 0 only: exactly one redispatch, which is UNCERTAIN again and opens its own
        # reconciliation, bound to attempt 1 and its own grant. Nothing else is dispatched while it waits.
        assert len(effects) == 2, (states, _actions(body))
        assert first[0]["authority_requested"]["attempt"] == 0
        assert reserved_before == {("act", 0): 0.4}                                  # unknown spend, not zero
        assert _actions(body) == [("UNCERTAIN", 0), ("RECONCILED_NOT_EXECUTED", 0), ("UNCERTAIN", 1)]
        second = _requests(body)
        assert len(second) == 2 and second[1]["request_id"] != first[0]["request_id"]
        assert second[1]["authority_requested"]["attempt"] == 1
        assert second[1]["authority_requested"]["grant_id"] == effects[1] != effects[0]
        assert states[0] == "BLOCKED" and set(states[1:]) == {"WAITING"}
        m = body.engine.book.missions["m:unknown"]
        assert m.blocker["type"] == "reconciliation" and m.blocker["request_id"] == second[1]["request_id"]
        assert (m.spent_usd, m.reserved_usd) == (0.0, 0.4)                          # attempt 0 released
    finally:
        body.close()

    # A restart rebuilds the same truth from the ledger: still one open reconciliation, still no dispatch.
    body = _open(home, clock, effects, retry_safe=False)
    try:
        assert set(_ticks(body, clock, 5)) == {"WAITING"} and len(effects) == 2
        assert body.engine.book.missions["m:unknown"].reserved_usd == 0.4
        drop(home, signed(key, body_id, "DECISION", {"request_id": second[1]["request_id"],
                                                     "answer": "reconcile_executed", "reason": "test"}))
        _ticks(body, clock, 6)
        m = body.engine.book.missions["m:unknown"]
        done = [e.payload for e in body.journal.replay("mission.action") if e.payload["status"] == "DONE"]
        assert len(done) == 1 and done[0]["attempt"] == 1 and done[0]["reconciles"]["grant_id"] == effects[1]
        # It executed and its spend was never measured: the signed cap is booked, not zero.
        assert done[0]["cost_usd"] == 0.4 and done[0]["spend_basis"].startswith("signed_cap")
        assert (m.spent_usd, m.reserved_usd) == (0.4, 0.0)
        assert len(effects) == 2                     # an executed dispatch is never dispatched again
        assert len(_requests(body)) == 2
        assert body.ledger.verify_chain()[0]
    finally:
        body.close()


def test_unknown_spend_is_reserved_at_its_worst_case_and_bounds_dispatch(tmp_path):
    """A retry-safe dispatch is re-attempted, but each unknown outcome may have spent its cap: two reserved
    $0.40 dispatches leave $0.20 of a signed $1.00, so a third is not dispatched; the mission asks instead."""
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _spec(data, retry_safe=True, cost=0.4, budget=1.0)))
    clock, effects = Clock(), []
    body = _open(home, clock, effects, retry_safe=True)
    try:
        _ticks(body, clock, 8, seconds=120)
        m = body.engine.book.missions["m:unknown"]
        assert len(effects) == 2, _actions(body)
        assert _actions(body) == [("UNCERTAIN", 0), ("UNCERTAIN", 1)]
        assert (m.spent_usd, m.reserved_usd) == (0.0, 0.8)
        asks = _requests(body, "APPROVAL")
        assert len(asks) == 1 and any("exceeds budget" in r for r in asks[0]["evidence"]["policy"])
        assert asks[0]["evidence"]["budget"] == {"spent_usd": 0.0, "budget_usd": 1.0, "reserved_usd": 0.8}
        uncertain = [e.payload for e in body.journal.replay("mission.action")]
        assert all(a["cost_usd"] == 0.0 and a["reserved_usd"] == 0.4 for a in uncertain)
    finally:
        body.close()
    body = _open(home, clock, effects, retry_safe=True)
    try:
        _ticks(body, clock, 4, seconds=120)
        assert len(effects) == 2 and body.engine.book.missions["m:unknown"].committed_usd == 0.8
    finally:
        body.close()


class _InterruptedOnceWorker:
    """A worker provider double (not a frontier worker): its first run loses its process mid-work, after a partial
    edit and with its spend unreported; a later run finishes the edit. With ``interrupt=False`` every run finishes."""
    name = "interrupted-once-test-double"

    def __init__(self, *, interrupt: bool = True):
        self.runs = []
        self.interrupt = interrupt

    def available(self):
        return True, ""

    def run(self, order, cwd):
        from greg import workers
        self.runs.append(order.grant_id)
        (cwd / "pkg" / "calc.py").write_text("def add(a, b):\n    return a + b\n\n\ndef sub(a, b):\n    return a - b\n")
        if self.interrupt and len(self.runs) == 1:
            raise RuntimeError("worker process lost mid-run")
        return workers.WorkerReport(self.name, self.name, 0, 0.1, None)


def _work_repo(tmp_path):
    """A project whose frozen acceptance test fails until ``sub`` exists."""
    import subprocess
    data = tmp_path / "data"
    data.mkdir()
    repo = data / "proj"
    (repo / "pkg").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "pkg" / "__init__.py").write_text("")
    (repo / "pkg" / "calc.py").write_text("def add(a, b):\n    return a + b\n")
    (repo / "tests" / "test_calc.py").write_text("from pkg.calc import sub\n\n\ndef test_sub():\n    assert sub(3, 1) == 2\n")
    for argv in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "base"]):
        subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *argv], check=True,
                       capture_output=True)
    return data, repo


def _paid_mission(repo, provider: str, *, budget: float):
    """One $0.50 WorkOrder, closed only by the independent worker.appraise verdict ACCEPTED."""
    return mission("m:paid", checks=[{
        "check_id": "accepted", "description": "independently accepted",
        "sensor": {"capability": "worker.appraise", "params": {"order": "add-sub"}, "target": "work:add-sub"},
        "predicate": {"op": "equals", "field": "verdict", "value": "ACCEPTED"}}],
        strategies=[{"action_id": "commission", "capability": "worker.commission", "target": "work:add-sub",
                     "params": {"order": "add-sub", "mode": "repository", "repo": str(repo), "objective": "add sub()",
                                "acceptance": {"tests": [["python", "-m", "pytest", "-q", "-p", "no:cacheprovider",
                                                          "tests/test_calc.py"]]},
                                "allowed_paths": ["pkg/*"], "provider": provider, "max_budget_usd": 0.5,
                                "timeout_seconds": 60},
                     "cost_usd": 0.5, "advances": ["accepted"], "rationale": "one paid worker"}],
        capabilities=["worker.commission", "worker.appraise"], targets=("work:*",), budget=budget)


def test_an_interrupted_paid_worker_reconciled_not_executed_books_its_cap_and_the_budget_bounds_a_rerun(
        tmp_path, monkeypatch):
    """A metered worker spends while its provider runs, whether or not GREG collected its result: "not executed"
    settles the effect, not the money. Before H.G4 the settlement booked $0.00 and released the reservation, so a
    signed $0.50 budget re-commissioned a second $0.50 run after an interrupted one that may have spent $0.50."""
    from greg import resilience, routing, workers
    data, repo = _work_repo(tmp_path)
    worker = _InterruptedOnceWorker()
    monkeypatch.setitem(workers.PROVIDERS, "interrupted-once", worker)
    home, key, body_id, _ = make_body(tmp_path, read_roots=[data])
    drop(home, signed(key, body_id, "MISSION", _paid_mission(repo, "interrupted-once", budget=0.5)))
    clock = Clock()
    body = Body(home, clock=clock).open()
    body.boot()
    try:
        assert _ticks(body, clock, 3) == ["BLOCKED", "WAITING", "WAITING"]
        assert _actions(body) == [("UNCERTAIN", 0)] and len(worker.runs) == 1
        [request] = _requests(body)
        # The founder is told before answering that "not executed" still books the metered run's signed cap.
        assert request["evidence"]["booked_usd_by_answer"] == {"reconcile_executed": 0.5,
                                                               "reconcile_not_executed": 0.5}
        assert "either answer books $0.50" in request["recommendation"]
        drop(home, signed(key, body_id, "DECISION", {"request_id": request["request_id"],
                                                     "answer": "reconcile_not_executed", "reason": "test"}))
        _ticks(body, clock, 4)
        settled = [e.payload for e in body.journal.replay("mission.action")][1]
        assert settled["status"] == "RECONCILED_NOT_EXECUTED"
        assert settled["cost_usd"] == 0.5 and settled["spend_basis"].startswith("signed_cap")
        # The basis states what is known: the run may never have started (the body can stop while cloning).
        assert "whether its metered provider ran" in settled["spend_basis"]
        m = body.engine.book.missions["m:paid"]
        assert (m.spent_usd, m.reserved_usd) == (0.5, 0.0)
        # The signed budget is spent at its worst case: a second run needs the founder, it is not re-commissioned.
        assert len(worker.runs) == 1, _actions(body)
        [ask] = _requests(body, "APPROVAL")
        assert any("exceeds budget" in r for r in ask["evidence"]["policy"])
        # One interruption is one failure of the capability: the settlement carries the capability for its spend
        # record, and is not counted as a second failure by routing or resilience.
        assert routing.track_record(body.journal)["worker.commission"]["failed"] == 1
        assert resilience.after_failure(body.journal)["worker.commission"]["failures"] == 1
    finally:
        body.close()
    body = Body(home, clock=clock).open()               # the booking is retained truth, rebuilt from the ledger
    try:
        assert body.engine.book.missions["m:paid"].spent_usd == 0.5
    finally:
        body.close()


def _lost_after_evidence(tmp_path, monkeypatch):
    """A Body whose first commission writes the WorkOrder's evidence.json and is then lost before the Gate's receipt
    (the real commission, then an exception: the Gate records reconciliation_required), left at its RECONCILIATION."""
    import json
    from greg import workers
    data, repo = _work_repo(tmp_path)
    worker = _InterruptedOnceWorker(interrupt=False)
    monkeypatch.setitem(workers.PROVIDERS, "finishing", worker)
    collected = []
    real_commission = workers.commission

    def stops_after_evidence(params, ctx):
        collected.append(real_commission(params, ctx))
        if len(collected) == 1:
            raise RuntimeError("body lost after the work order evidence, before the receipt")
        return collected[-1]
    monkeypatch.setattr(workers, "commission", stops_after_evidence)
    home, key, body_id, _ = make_body(tmp_path, read_roots=[data])
    drop(home, signed(key, body_id, "MISSION", _paid_mission(repo, "finishing", budget=1.0)))
    evidence_path = workspace(home, "m:paid") / "work-orders" / "add-sub" / "evidence.json"
    clock = Clock()
    body = Body(home, clock=clock).open()
    body.boot()
    assert _ticks(body, clock, 3) == ["BLOCKED", "WAITING", "WAITING"]
    assert _actions(body) == [("UNCERTAIN", 0)] and len(worker.runs) == 1
    assert json.loads(evidence_path.read_text())["summary"]["grant_id"] == worker.runs[0]   # completed, unreceipted
    [request] = _requests(body)
    return body, clock, worker, evidence_path, lambda answer: drop(home, signed(key, body_id, "DECISION", {
        "request_id": request["request_id"], "answer": answer, "reason": "test"}))


def test_a_body_lost_after_the_work_order_evidence_but_before_its_receipt_is_recommissioned_not_closed(
        tmp_path, monkeypatch):
    """H.G11: the Body stops after the WorkOrder's evidence.json is written but before the Gate's receipt.

    Before: after a signed reconcile_not_executed the engine's own worker.appraise sensor accepted that evidence
    without binding it to a commission receipt, so the mission closed ACHIEVED with no receipted DONE action (one
    worker run; actions UNCERTAIN, RECONCILED_NOT_EXECUTED) while the separate-process appraisal, which binds it,
    gave REFUTED. And a re-commission would have returned that evidence as the new grant's result ("reused")
    instead of running a worker, which the binding rejects. Now the engine's sensor binds the evidence to its
    canonical receipt like the appraiser, and every grant runs its own worker in a fresh clone."""
    import json
    body, clock, worker, evidence_path, answer = _lost_after_evidence(tmp_path, monkeypatch)
    try:
        [killed] = worker.runs
        answer("reconcile_not_executed")
        _ticks(body, clock, 6)
        # Exactly one re-commission, under a new grant, by a new worker run: nothing is reused.
        assert len(worker.runs) == 2 and worker.runs[1] != killed, _actions(body)
        assert _actions(body) == [("UNCERTAIN", 0), ("RECONCILED_NOT_EXECUTED", 0), ("DONE", 1)]
        done = [e.payload for e in body.journal.replay("mission.action")][2]
        output = body.ledger.find(done["receipt"]).payload["result"]["output"]
        assert output["grant_id"] == worker.runs[1] and "reused" not in output
        assert json.loads(evidence_path.read_text())["summary"]["grant_id"] == worker.runs[1]
        # The engine's own sensor refused the unreceipted evidence; the closure came only after the receipted run.
        observed = [e.payload for e in body.journal.replay("mission.observed")]
        assert [o["passed"] for o in observed] == [False, False, True], observed
        assert "REJECTED" in observed[1]["detail"]
        [achieved] = [e.payload for e in body.journal.replay("mission.achieved")]
        assert achieved["actions_done"] == 1
        assert [e.payload["verdict"] for e in body.journal.replay("mission.appraised")] == ["VERIFIED"]
        m = body.engine.book.missions["m:paid"]
        assert (m.spent_usd, m.reserved_usd) == (1.0, 0.0)          # the unreceipted run's cap, then the rerun's
    finally:
        body.close()


def test_unreceipted_work_order_evidence_never_closes_the_mission_even_when_reconciled_as_executed(
        tmp_path, monkeypatch):
    """The stated limit of H.G11: evidence whose grant has no receipt cannot be accepted, whatever the founder
    answers. Answered "executed", the dispatch is booked at its cap and the mission asks once instead of closing
    (before the fix it closed ACHIEVED on the unbound sensor, and the separate appraisal could only refute it)."""
    body, clock, worker, _, answer = _lost_after_evidence(tmp_path, monkeypatch)
    try:
        answer("reconcile_executed")
        states = _ticks(body, clock, 8)
        assert "ACHIEVED" not in states and states[-3:] == ["WAITING"] * 3, states
        assert _actions(body) == [("UNCERTAIN", 0), ("DONE", 0)] and len(worker.runs) == 1
        assert not list(body.journal.replay("mission.achieved"))
        observed = [e.payload for e in body.journal.replay("mission.observed")]
        assert not any(o["passed"] for o in observed) and "REJECTED" in observed[-1]["detail"]
        assert [e.payload["kind"] for e in body.journal.replay("decision.requested")] == ["RECONCILIATION",
                                                                                         "NO_STRATEGY"]
        m = body.engine.book.missions["m:paid"]
        assert (m.spent_usd, m.reserved_usd) == (0.5, 0.0) and m.blocker["type"] == "decision"
    finally:
        body.close()
