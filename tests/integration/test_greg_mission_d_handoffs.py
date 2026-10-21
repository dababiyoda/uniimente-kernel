"""Mission D (multi-worker execution): typed handoffs between workers on the canonical Body path.

Directive section 33, Mission D. Three defects found by the out-of-tree probe (scratch missiond_probe/probe.py)
and reproduced here through the canonical Body, MissionEngine, AuthorityOffice and ConsequenceGate:

  D1  a ``bind`` edge could set a worker's provider budget (max_budget_usd) above the strategy's signed cost,
      and the extra spend was not booked: worker-b's budget was bound to $20, it reported $15, the mission
      booked the $0.50 cap, independent appraisal ACCEPTED and the mission was ACHIEVED inside a $1 cone.
  D2  a consumer consumed a producer output that independent appraisal (worker.appraise) REJECTED.
  D3  an inline ``$from_action`` consumer listed before its producer stalled silently: BLOCKED on every tick,
      the producer never ran, and the founder was never asked.

In-process Body with a test clock, a per-test Ed25519 key (not Alfonso's) and a scripted worker double:
SANDBOX_VERIFIED. No model, network or real provider.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from greg import workers
from greg.body import Body
from greg.missions import MissionError, validate_mission
from provenance.ledger import sha256_json
from tests.greg_fixtures import Clock, drop, horizon, make_body, signed


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _repo(root: Path) -> Path:
    repo = root / "proj"
    (repo / "pkg").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "pkg" / "__init__.py").write_text("")
    (repo / "pkg" / "calc.py").write_text("def add(a, b):\n    return a + b\n")
    _git(repo.parent, "init", "-q", str(repo))
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base")
    return repo


class Double:
    """A scripted worker: 'a' adds sub() and its test (good or bad), 'b' writes a release note."""
    name = "scripted-test-double"

    def __init__(self, *, a_test="assert sub(3, 1) == 2", b_cost=0.3):
        self.calls, self.a_test, self.b_cost = [], a_test, b_cost

    def available(self):
        return True, ""

    def run(self, order, cwd):
        self.calls.append({"order": order.order, "context": order.context, "max_budget_usd": order.max_budget_usd})
        if order.order == "a":
            (cwd / "pkg" / "calc.py").write_text("def add(a, b):\n    return a + b\n\n\ndef sub(a, b):\n    return a - b\n")
            (cwd / "tests").mkdir(exist_ok=True)
            (cwd / "tests" / "test_calc.py").write_text(f"from pkg.calc import sub\n\n\ndef test_sub():\n    {self.a_test}\n")
            cost = 0.4
        else:
            (cwd / "note.md").write_text("Release note for " + order.context + "\n")
            cost = self.b_cost
        return workers.WorkerReport(self.name, self.name, 0, 0.1, cost, claim={"confidence": 1.0}, summary="WORK_REPORT: {}")


def _spec(repo, *, budget=2.0, cost_b=0.5, b_budget=0.5, handoff="bind", requires=False, consumer_first=False):
    a = {"action_id": "worker-a", "capability": "worker.commission", "target": "work:a",
         "params": {"order": "a", "mode": "repository", "repo": str(repo), "objective": "add sub()",
                    "acceptance": {"run_changed_tests": True, "max_changed_files": 4},
                    "allowed_paths": ["pkg/*", "tests/*"], "provider": "scripted", "max_budget_usd": 0.5,
                    "timeout_seconds": 60}, "cost_usd": 0.5, "advances": ["a_accepted"], "rationale": "a"}
    bparams = {"order": "b", "mode": "document", "objective": "write a release note", "inputs": [],
               "acceptance": {"output": "note.md"}, "allowed_paths": ["note.md"], "provider": "scripted",
               "max_budget_usd": b_budget, "timeout_seconds": 60}
    b = {"action_id": "worker-b", "capability": "worker.commission", "target": "work:b", "params": bparams,
         "cost_usd": cost_b, "advances": ["b_accepted"], "rationale": "b"}
    if requires:
        b["requires"] = ["a_accepted"]
    if handoff == "bind":
        b["bind"] = [{"param": "context", "from": {"action_id": "worker-a", "field": "commit"}, "type": "string",
                      "template": "commit {value}"}]
    elif handoff == "inline":
        bparams["context"] = {"$from_action": {"action_id": "worker-a", "field": "commit", "type": "string"}}
    checks = [{"check_id": f"{o}_accepted", "description": o, "sensor": {
        "capability": "worker.appraise", "params": {"order": o}, "target": f"work:{o}"},
        "predicate": {"op": "equals", "field": "verdict", "value": "ACCEPTED"}} for o in ("a", "b")]
    return {"mission_id": "m:two-workers", "founder_expression": "two workers", "intended_effect": "chained",
            "priority": 50, "closure": {"kind": "bounded"}, "success_checks": checks,
            "strategies": [b, a] if consumer_first else [a, b],
            "light_cone": {"capabilities": ["worker.commission", "worker.appraise"], "targets": ["work:*"],
                           "max_consequence_class": "internal_write", "budget_usd": budget, "horizon": horizon()}}


def _run(tmp_path, monkeypatch, spec_kw=None, *, double=None, ticks=8, seconds=60, register=None):
    data = tmp_path / "data"
    data.mkdir()
    repo = _repo(data)
    home, key, bid, _ = make_body(tmp_path, read_roots=[data])
    double = double or Double()
    monkeypatch.setitem(workers.PROVIDERS, "scripted", double)
    spec = _spec(repo, **(spec_kw or {}))
    if register is None:
        drop(home, signed(key, bid, "MISSION", spec))
    clock, states = Clock(), []
    with Body(home, clock=clock) as body:
        if register is not None:
            register(body, spec)
        for _ in range(ticks):
            states.append(body.tick()["missions"][0]["state"])
            clock.advance(seconds)
        out = {"states": states, "double": double, "m": body.engine.book.missions["m:two-workers"],
               "actions": [e.payload for e in body.journal.replay("mission.action")],
               "asks": [e.payload for e in body.journal.replay("decision.requested")],
               "observed": [e.payload for e in body.journal.replay("mission.observed")],
               "chain": body.ledger.verify_chain()[0]}
        out["receipts"] = {a["receipt"]: body.ledger.find(a["receipt"]).payload
                           for a in out["actions"] if a.get("receipt")}
    return out


# -- D1 -------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("param", ["max_budget_usd", "allowed_paths", "provider", "acceptance", "repo",
                                   "acceptance.output"])
def test_a_bind_edge_onto_an_authority_or_budget_param_is_refused_at_registration(tmp_path, param):
    spec = _spec(_repo(tmp_path), handoff=None)
    params = spec["strategies"][1]["params"]
    params.pop(param.split(".")[0], None)
    spec["strategies"][1]["bind"] = [{"param": param, "from": {"action_id": "worker-a", "field": "commit"},
                                      "type": "string"}]
    with pytest.raises(MissionError, match="protected"):
        validate_mission(spec)


def test_a_worker_budget_is_capped_at_the_signed_cost_and_actual_spend_is_booked(tmp_path, monkeypatch):
    # worker-b's own provider budget was signed at $20 against a strategy cost of $0.50; it spends $15. (The cone
    # is wide enough that the overspend leaves room to observe; a narrower one blocks the sensor on budget.)
    run = _run(tmp_path, monkeypatch, {"b_budget": 20.0, "requires": True, "budget": 20.0},
               double=Double(b_cost=15.0), ticks=10)
    budgets = {c["order"]: c["max_budget_usd"] for c in run["double"].calls}
    assert budgets == {"a": 0.5, "b": 0.5}, "a worker never gets a provider budget above its signed cost"
    b = next(a for a in run["actions"] if a["action_id"] == "worker-b" and a["status"] == "DONE")
    assert b["cost_usd"] == 15.0 and b["provider_reported_usd"] == 15.0 and b["cost_cap_usd"] == 0.5
    assert b["budget_capped"] == {"signed_cost_usd": 0.5, "requested_usd": 20.0}
    assert run["m"].spent_usd == pytest.approx(15.4), "actual spend is booked, never the cap in its place"
    assert run["m"].status != "ACHIEVED"
    last_b = [o for o in run["observed"] if o["check_id"] == "b_accepted"][-1]
    assert not last_b["passed"] and "REJECTED" in last_b["detail"]
    assert run["chain"]


def test_a_legacy_protected_bind_is_never_honoured_at_dispatch(tmp_path, monkeypatch):
    """A mission registered before registration refused protected binds (its retained spec still binds the
    worker's budget from a producer receipt) never dispatches the consumer with a bound budget."""
    def legacy(body, spec):
        b = spec["strategies"][1]
        b["params"].pop("max_budget_usd")
        b["requires"] = ["a_accepted"]
        b["bind"] = [{"param": "max_budget_usd", "from": {"action_id": "worker-a", "field": "worker.duration_s"},
                      "type": "number"}]
        body.journal.record("mission.registered", {"mission_id": spec["mission_id"], "spec": spec,
                                                   "command_digest": "sha256:" + "0" * 64}, key=spec["mission_id"])
    run = _run(tmp_path, monkeypatch, register=legacy, ticks=10)
    assert [c["order"] for c in run["double"].calls] == ["a"], "the consumer with a protected bind never runs"
    asks = [a for a in run["asks"] if a["kind"] == "NO_STRATEGY"]
    assert len(asks) == 1 and "protected" in str(asks[0]["evidence"]["held_by_precondition"]["worker-b"])


# -- D2 -------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("handoff", ["bind", "inline"])
def test_a_rejected_producer_output_never_feeds_a_consumer(tmp_path, monkeypatch, handoff):
    # worker-a's own acceptance test fails, so independent appraisal REJECTS its output; worker-b binds
    # worker-a's commit with no `requires` precondition.
    run = _run(tmp_path, monkeypatch, {"handoff": handoff}, double=Double(a_test="assert sub(3, 1) == 99"), ticks=8)
    assert [c["order"] for c in run["double"].calls] == ["a"], "a rejected output is never consumed"
    assert [a["action_id"] for a in run["actions"]] == ["worker-a"]
    rejected = [o for o in run["observed"] if o["check_id"] == "a_accepted"]
    assert rejected and not rejected[-1]["passed"] and "REJECTED" in rejected[-1]["detail"]
    asks = [a for a in run["asks"] if a["kind"] == "NO_STRATEGY"]
    assert len(asks) == 1 and "REJECTED" in str(asks[0]["evidence"]["held_by_precondition"]["worker-b"])
    assert run["m"].blocker["request_id"] == asks[0]["request_id"] and run["m"].status == "ACTIVE"


def test_an_accepted_producer_output_feeds_its_consumer(tmp_path, monkeypatch):
    run = _run(tmp_path, monkeypatch, {"handoff": "bind"}, ticks=8)
    assert [c["order"] for c in run["double"].calls] == ["a", "b"]
    done = {a["action_id"]: a for a in run["actions"] if a["status"] == "DONE"}
    producer, consumer = done["worker-a"], done["worker-b"]
    commit = run["receipts"][producer["receipt"]]["result"]["output"]["commit"]
    assert commit and len(commit) == 40, commit                       # worker-a's receipted commit sha
    # worker-b consumed exactly that commit, resolved from worker-a's retained receipt through the signed edge
    assert run["double"].calls[1]["context"] == "commit " + commit
    assert consumer["bindings"] == [{"param": "context", "from_action": "worker-a", "from_receipt": producer["receipt"],
                                     "field": "commit", "value_sha256": sha256_json({"v": "commit " + commit})}]
    grants = [run["receipts"][a["receipt"]]["grant_id"] for a in (producer, consumer)]
    assert all(grants) and grants[0] != grants[1], "each worker dispatch carries its own single-action grant"
    assert run["m"].status == "ACHIEVED"


def test_a_worker_handoff_without_an_independent_appraisal_is_refused_at_registration(tmp_path):
    spec = _spec(_repo(tmp_path))
    spec["success_checks"] = [c for c in spec["success_checks"] if c["check_id"] != "a_accepted"]
    spec["strategies"][0]["advances"] = ["b_accepted"]
    with pytest.raises(MissionError, match="appraisal"):
        validate_mission(spec)


# -- D3 -------------------------------------------------------------------------------------------------
def test_an_inline_consumer_listed_first_waits_for_its_producer(tmp_path, monkeypatch):
    run = _run(tmp_path, monkeypatch, {"handoff": "inline", "consumer_first": True}, ticks=8, seconds=4000)
    assert [c["order"] for c in run["double"].calls] == ["a", "b"], run["states"]
    assert run["m"].status == "ACHIEVED"
    consumer = next(a for a in run["actions"] if a["action_id"] == "worker-b")
    assert consumer["input_bindings"][0]["action_id"] == "worker-a"


def test_an_inline_consumer_whose_producer_cannot_run_is_a_recorded_ask(tmp_path, monkeypatch):
    def producer_refused(body, spec):   # the producer names a provider this body does not have: it is refused
        spec["strategies"][1]["params"]["provider"] = "absent-provider"
        body.journal.record("mission.registered", {"mission_id": spec["mission_id"], "spec": validate_mission(spec),
                                                   "command_digest": "sha256:" + "1" * 64}, key=spec["mission_id"])
    run = _run(tmp_path, monkeypatch, {"handoff": "inline", "consumer_first": True}, register=producer_refused,
               ticks=8, seconds=4000)
    assert run["double"].calls == []
    no_strategy = [a for a in run["asks"] if a["kind"] == "NO_STRATEGY"]
    assert len(no_strategy) == 1, run["states"]
    held = no_strategy[0]["evidence"]["held_by_precondition"]["worker-b"]
    assert any("worker-a" in h for h in held)
    assert run["m"].blocker["request_id"] == no_strategy[0]["request_id"]


def test_an_inline_reference_to_an_unknown_or_own_action_is_refused_at_registration(tmp_path):
    for ref in ("worker-zz", "worker-b"):
        spec = _spec(_repo(tmp_path / ref), handoff="inline")
        spec["strategies"][1]["params"]["context"]["$from_action"]["action_id"] = ref
        with pytest.raises(MissionError, match="unknown or own action"):
            validate_mission(spec)
