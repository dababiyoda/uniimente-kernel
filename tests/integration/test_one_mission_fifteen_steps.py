"""ONE MISSION, FIFTEEN STEPS: the loop of docs/collaboration/LOOP-15-MAP-2026-10-22.md in one traceable run.

The map binds each of directive section 7's fifteen steps to an episode that shows it, and says that no single
mission crossed all fifteen: episode T (scripts/greg_whole_machine_trace.py) lacks a waking observation, a worker
task and an organ consumer; episode X (test_one_machine_ten_steps.py) lacks the deficit and formation; Goal Gravity
showed the wake only in unit tests. Here ONE founder-signed goal and ONE founder-signed mission cross all of them in
one body's ledger, every step is asserted on ledger events by id, and a step->event map is printed with the result:

 1  the signed GOAL and MISSION are persisted on the body ledger and survive SIGKILLs and restarts
 2  the mission waits on a precondition only the world can satisfy (a staffing request on file). The request lands
    and nothing moves: the mission's own cadence is 30 days, and a SIGKILL and restart alone move nothing either.
    An observation naming the mission arrives through the untrusted data plane, wakes the goal, and the goal's pull
    (timing only) makes the mission observe the request and resume
 3  the Competency Compiler compiles the request, recording the methods it considered and rejected, creating no
    authority
 4  the admitted catalog is searched first: the first compile is a typed CAPABILITY_DEFICIT
 5  the deficit names the missing function (assignment.staffing, then its engine graph.max_flow)
 6  Capability Genesis acquires the engine and constructs the function, each qualified on GREG's own oracle
 7  nothing attaches before the founder's own signed CAPABILITY_ATTACH (a forged attach is refused); the mission
    carries no auto_attach
 8  a founder-signed script in the bubblewrap envelope, with no network, records the Mind's certified answer (bound
    from the passing observation's receipt) with a first-principles test; GREG re-runs the test, and worker.appraise
    ACCEPTS the change in a fresh clone
 9  DALEOBANKS and WealthMachine, two organ processes running their own pinned code in their own interpreters,
    consume the Mind's answer (bound into DALEOBANKS's seed) over the signed bridge; a second WealthMachine process
    reproduces the assessment
10  the body is SIGKILLed while that worker is in flight
11  on restart the in-flight commission is UNCERTAIN and is never retried blind; the founder's signed standing
    mandate settles it with a recorded proof that the run was consequence-inert; the work runs exactly once more.
    Attach state, the signed budget and the one mission survive: no re-ask, no re-qualification, spend within cap
12  the separate-process appraiser re-derives the closure (VERIFIED), and again from the stopped body's ledger
13  the closure settles once: one mission.achieved, one cognition.settled for the cognition check, one DONE per
    strategy, unchanged by later restarts and ticks
14  a second, fresh mission on the same body routes straight to the formed construction (no deficit, no ask) ...
15  ... on fresh work (a different staffing request), while the identical mission on a fresh control body opens a
    deficit and asks

Gaps are recorded in the step map, never hidden (GAPS below). Gated as the one-machine proofs are: the bubblewrap
envelope (skipped with the reason, as X), and the real organ checkouts with their own interpreters (the four
UNIIMENTE_* variables, as test_one_machine.py: skipped with the reason, failed instead under
UNIIMENTE_REQUIRE_ORGANS=1, which CI job 8 sets).

Reality: LABORATORY-VERIFIED on the host that runs it. A per-test Ed25519 key stands in for the founder; nothing here
counts toward VEPMC, authenticates Alfonso, spends money, publishes or contacts anyone. Set GREG_LOOP15_EVIDENCE=<dir>
to keep the ledger and the step map.
"""
from __future__ import annotations

from collections import Counter
import json
import os
from pathlib import Path
import shutil
import signal
import sys
import time
from types import SimpleNamespace

import pytest

pytest.importorskip("networkx")
pytest.importorskip("scipy")
pytest.importorskip("z3")
pytest.importorskip("ortools")
if not sys.platform.startswith("linux"):
    pytest.skip("the interruption steps rely on Linux SIGKILL and parent-death signals", allow_module_level=True)

from tests.one_machine_worker import TEST as PLAN_TEST  # noqa: E402
from tests.unit.test_greg_organs import SEED  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import greg_whole_machine_trace as T  # noqa: E402  (episode T's ledger readers, reused)

MID = "m:loop15-staffing"
PROBLEM_ID = "loop15-staff"
LATER_ID = "loop15-later"
ORDER = "loop15-plan"
CADENCE = 2592000                       # 30 days: the mission never re-observes on its own during the test
DEMAND = "Staffing request: staff the docks and the line from problem.json, as many units as can be staffed.\n"
OBSERVATION = (f"ops note: a staffing request landed in requests/staffing.txt for {MID}; "
               "the docks and the line need staffing today")
# The organs' own seed (DALEOBANKS refines it into an opportunity), carrying the Mind's certified answer as evidence
SEED_TEMPLATE = SEED + " Evidence from GREG's certified staffing plan for the docks and the line: {value}"
# The founder signs this script with the mission. The one bound datum is the Mind's certified answer rendered as
# JSON: with true/false/null named, a JSON object is a Python literal, so the bound value is data, never code.
SCRIPT_TEMPLATE = '''# founder-signed script; the only data bound into it is the Mind's certified answer, as a JSON literal
true, false, null = True, False, None
ANSWER = {value}
import json
import time
from pathlib import Path
Path("tests").mkdir(exist_ok=True)
Path("tests/started.txt").write_text("in flight\\n")      # visible from outside: the worker is running
time.sleep(5)
Path("plan").mkdir(exist_ok=True)
Path("plan/plan.json").write_text(json.dumps({"assignment": ANSWER["assignment"], "staffed": ANSWER["staffed"],
                                              "source": "bound from GREG's competency compiler receipt"}, indent=1) + "\\n")
Path("tests/test_plan.py").write_text(TEST)
print('WORK_REPORT: {"changed": ["plan/plan.json", "tests/test_plan.py"], "tests_run": [], "unresolved": [], "confidence": 0.9}')
'''
GAPS = {
    2: "the observation is a local file drop (greg intake): a local process stands in for an external feed, and no "
       "connector delivers it from outside the host. The wake is timing only: it changes when the "
       "mission observes, never what it may do",
    9: "DALEOBANKS takes in the whole bound seed (its own ledger counts its characters) but its refinery builds the "
       "packet from the seed's thesis, so the staffing figures do not reach WealthMachine's assessment; the organs run "
       "pinned code on the body's host and UID, and the second WealthMachine process makes the assessment REPRODUCED "
       "(same-code determinism), not VERIFIED by an independent party",
    10: "a SIGKILL on a Linux test host, not on the founder's device",
    12: "the appraiser shares reviewed Kernel code: process independence, not an independent implementation",
    14: "the changed decision is capability retention (the formed construction is reused); settled outcomes alone "
        "do not reorder a choice here (one fit for this geometry)",
    15: "the fresh work is a second synthetic staffing request, not founder work; no external verification",
}


def loop_mission(*, data: Path, repo: Path, organs: dict, horizon_days: float = 2) -> dict:
    """One founder-signable mission: wait for the request, compile, form what is missing, have the organs assess the
    answer, and have a confined script worker record and re-check it. Composed from existing capabilities only."""
    from greg.cognition.compiler import CERTIFIED
    from greg.genesis import CATALOG
    from greg.organs import TARGET
    from greg.recombine import chain, fits
    from greg.templates import _horizon
    from tests.integration.test_greg_mind_constructs_capability import STAFFING

    demand = Path(data) / "requests" / "staffing.txt"
    compile_params = {"problem_id": PROBLEM_ID, "compile": {"geometry": {"geometry": "optimization"}, "data": STAFFING}}
    capabilities = ["cognition.solve"]
    for reduction in fits(STAFFING):
        found = chain(reduction.function, CATALOG)
        if found:
            capabilities += [f"composed.{reduction.function}.*", f"acquired.{found[1]}.*"]
    organ_keys = ("daleobanks_root", "daleobanks_python", "wealthmachine_root", "wealthmachine_python")
    script = "TEST = " + repr(PLAN_TEST) + "\n" + SCRIPT_TEMPLATE
    return {
        "mission_id": MID,
        "founder_expression": "TEST FOUNDER KEY, not Alfonso: when a staffing request arrives, answer it with the "
                              "smallest competent method, form what is missing, have the organs assess the answer, "
                              "and have a confined worker record and re-check it",
        "intended_effect": "a certified staffing answer, assessed by both organs and recorded with an independently "
                           "accepted test; nothing is sent, published, merged or paid",
        "priority": 70, "closure": {"kind": "bounded", "cadence_seconds": CADENCE},
        "success_checks": [
            {"check_id": "demand", "description": "a staffing request is on file",
             "sensor": {"capability": "fs.read", "params": {"path": str(demand)}, "target": "fs:staffing.txt"},
             "predicate": {"op": "contains", "field": "text", "value": "Staffing request"}},
            {"check_id": "answered", "description": "a constructed method answered with a problem-level certificate",
             "sensor": {"capability": "cognition.solve", "target": f"cognition:{PROBLEM_ID}", "params": compile_params},
             "predicate": {"op": "equals", "field": "confidence_type", "value": CERTIFIED}},
            {"check_id": "organs-assessed",
             "description": "both organ messages on the answer verified at the kernel and reproduced",
             "sensor": {"capability": "organ.status", "target": TARGET, "params": {}},
             "predicate": {"op": "equals", "field": "verdict", "value": "REPRODUCED"}},
            {"check_id": "work_accepted", "description": "independent appraisal ACCEPTED the work order",
             "sensor": {"capability": "worker.appraise", "params": {"order": ORDER}, "target": f"work:{ORDER}"},
             "predicate": {"op": "equals", "field": "verdict", "value": "ACCEPTED"}}],
        "strategies": [
            {"action_id": "compile", "capability": "cognition.solve", "target": f"cognition:{PROBLEM_ID}",
             "params": compile_params, "advances": ["answered"], "requires": ["demand"],
             "rationale": "compile the request's geometry to a competent method; form one if missing"},
            {"action_id": "organs", "capability": "organ.exchange", "target": TARGET,
             "params": {k: str(organs[k]) for k in organ_keys},
             "bind": [{"param": "seed", "from": {"check_id": "answered", "field": "result"}, "type": "object",
                       "render": "json", "template": SEED_TEMPLATE, "max_bytes": 2000}],
             "requires": ["answered"], "advances": ["organs-assessed"],
             "rationale": "the organs assess the Mind's certified answer through their own code over the signed bridge"},
            {"action_id": "commission", "capability": "worker.commission", "target": f"work:{ORDER}",
             "params": {"order": ORDER, "mode": "repository", "repo": str(Path(repo).resolve()),
                        "objective": "record GREG's certified staffing plan in plan/plan.json and add a first-principles "
                                     "test of it (founder-signed script)",
                        "acceptance": {"run_changed_tests": True, "max_changed_files": 4},
                        "allowed_paths": ["plan/*", "tests/*"], "provider": "script",
                        "max_budget_usd": 0.01, "timeout_seconds": 300},
             "bind": [{"param": "context", "from": {"check_id": "answered", "field": "result"}, "type": "object",
                       "render": "json", "template": script, "max_bytes": 8000}],
             "requires": ["answered", "organs-assessed"], "cost_usd": 0.01, "advances": ["work_accepted"],
             "rationale": "the Hands act only on a certified answer the organs assessed"}],
        "light_cone": {"capabilities": list(dict.fromkeys(capabilities + [
                           "fs.read", "organ.exchange", "organ.status", "worker.commission", "worker.appraise"])),
                       "targets": ["cognition:*", "fs:staffing.txt", TARGET, f"work:{ORDER}"],
                       "max_consequence_class": "internal_write", "budget_usd": 0.01,
                       "horizon": _horizon(horizon_days)},
        # the founder's standing mandate (X step 7c): an interruption GREG can prove consequence-inert is settled
        "standing_reconciliation": {"consequence_inert": True},
    }


def best_staffing(problem: dict) -> int:
    """Independent check: the most units any feasible assignment staffs, by exhaustive search (no GREG code)."""
    import itertools
    workers = {w["id"]: w for w in problem["workers"]}
    orders = {o["id"]: o for o in problem["orders"]}
    pairs = [(w, o) for w in workers for o in orders if orders[o]["skill"] in workers[w]["skills"]]
    best = 0
    for units in itertools.product(*[range(min(workers[w]["capacity"], orders[o]["demand"]) + 1) for w, o in pairs]):
        used, served = Counter(), Counter()
        for (w, o), u in zip(pairs, units):
            used[w] += u
            served[o] += u
        if all(used[w] <= workers[w]["capacity"] for w in used) and all(served[o] <= orders[o]["demand"] for o in served):
            best = max(best, sum(units))
    return best


# ---------------------------------------------------------------------------------------------- ledger readers
def ev(home: Path, kind: str, **match) -> list[dict]:
    """Events of ``kind`` (with their event ids) whose payload matches ``match``."""
    from greg.body import observe
    with observe(home, actor="spiffe://uniimente.internal/test/loop15") as journal:
        return [{"event_id": e.event_id, **e.payload} for e in journal.replay(kind)
                if all(e.payload.get(k) == v for k, v in match.items())]


def records(home: Path, record_type: str) -> list[dict]:
    from greg.body import observe
    with observe(home, actor="spiffe://uniimente.internal/test/loop15") as journal:
        return [{"seq": r.seq, "hash": r.hash, **r.payload} for r in journal.ledger.by_type(record_type)]


def receipt_output(home: Path, receipt: str):
    from greg.body import observe
    with observe(home, actor="spiffe://uniimente.internal/test/loop15") as journal:
        return journal.ledger.find(receipt).payload["result"]["output"]


def statuses(home: Path, action_id: str, mid: str = MID) -> list[str]:
    return [a["status"] for a in ev(home, "mission.action", mission_id=mid, action_id=action_id)]


def passing(home: Path, check_id: str, mid: str = MID) -> list[dict]:
    return [o for o in ev(home, "mission.observed", mission_id=mid, check_id=check_id) if o["passed"]]


def asks(home: Path, mid: str = MID) -> list[dict]:
    return ev(home, "decision.requested", mission_id=mid)


def stop(home: Path, body, greg):
    from greg.body import Layout
    assert greg(home, "stop", "--local").returncode == 0
    assert body.wait(timeout=60) == 0
    Layout(home).stop_file.unlink()


def kill(body):
    os.kill(body.pid, signal.SIGKILL)      # actual SIGKILL: no orderly close, no flush, no tick completion
    body.wait(timeout=30)


# ---------------------------------------------------------------------------------------------- the episode
def test_one_mission_crosses_all_fifteen_steps(tmp_path, capsys):
    from tests.integration.test_one_machine_ten_steps import _appraise, _need_envelope
    from tests.unit.test_greg_organs import live_organs, organ_roots
    _need_envelope()
    organs = live_organs()

    from greg import goal_gravity as gg
    from greg import templates
    from greg.body import Body, Layout, observe
    from greg.capabilities import BUILTINS
    from greg.founder import generate_founder_key, load_founder_key
    from greg.missions import MissionBook, bound_value
    from provenance.ledger import sha256_json
    from tests.greg_fixtures import Clock, make_body, signed
    from tests.integration.test_greg_mind_constructs_capability import STAFFING
    from tests.integration.test_one_machine import KERNEL, greg, sandbox_repo, start_body, wait_for

    data = tmp_path / "data"
    data.mkdir()
    repo = sandbox_repo(data)
    (data / "requests").mkdir()
    home, key, body_id, _ = make_body(tmp_path, read_roots=[data, *organ_roots(organs)])   # confinement: required
    spec = loop_mission(data=data, repo=repo, organs=organs)
    assert "auto_attach" not in spec
    goal = gg.goal_from_mission(spec, {m.capability_id: m for m, _ in BUILTINS.values()})["goal_command"]
    T.drop_atomic(home, signed(key, body_id, "MISSION", spec), "1-mission.json")
    T.drop_atomic(home, signed(key, body_id, "GOAL", goal), "2-goal.json")
    worker = KERNEL / "tests" / "one_machine_worker.py"     # the harness's local-cli double; this mission never uses it
    log = tmp_path / "body.log"
    order_root = Layout(home).workspace / MID.replace(":", "_") / "work-orders" / ORDER
    W = lambda pred, what, body, timeout=180: wait_for(pred, timeout=timeout, what=what, body=body, log=log)  # noqa: E731

    # ---- P1: the goal and mission are admitted; the mission waits on the world -------------------------------
    body = start_body(home, worker, log)
    no_strategy = W(lambda: [a for a in asks(home) if a["kind"] == "NO_STRATEGY"], "the mission to wait on the "
                    "request", body)[0]
    assert no_strategy["evidence"]["held_by_precondition"]["compile"] == ["demand"], no_strategy["evidence"]
    authorized = W(lambda: records(home, "egregore.goal_authorized"), "the goal on the body ledger", body)
    goal_id = authorized[0]["goal"]["goal_id"]
    W(lambda: [s for s in ev(home, "mission.schedule", mission_id=MID) if "cause" not in s], "the mission to settle "
      "on its own 30-day cadence while blocked", body)
    (data / "requests" / "staffing.txt").write_text(DEMAND)          # the request lands; nobody tells GREG yet
    time.sleep(4)                                                       # ~4 body-minutes of ticks
    assert not passing(home, "demand") and not statuses(home, "compile"), "the request moved the mission unprompted"

    # ---- P2: a SIGKILL and restart alone do not move it either ------------------------------------------------
    kill(body)
    body = start_body(home, worker, log)
    W(lambda: len(ev(home, "body.booted")) >= 2, "restart after the first SIGKILL", body)
    time.sleep(4)
    assert not passing(home, "demand") and not statuses(home, "compile"), "a restart alone moved the mission"
    assert [a["kind"] for a in asks(home)] == ["NO_STRATEGY"], "the restart re-asked"

    # ---- the observation arrives through the untrusted data plane while the body runs (live intake) ----------
    boots_before = len(ev(home, "body.booted"))
    note = tmp_path / "observation.txt"
    note.write_text(OBSERVATION)
    dropped = greg(home, "intake", "--source", "feed://ops", "--channel", "ops", "--file", str(note))
    assert dropped.returncode == 0, dropped.stderr
    intake = W(lambda: [e for e in ev(home, "external.ingested") if e["content"] == OBSERVATION],
               "the running body to read the observation from its intake", body)[0]
    assert intake["may_command"] is False and intake["quarantined"] is False

    # ---- P3: the goal wakes and pulls the mission; Mind, deficit, Genesis, founder attach, organs, Hands ------
    W(lambda: ev(home, "genesis.verified"), "the first qualified capability", body)
    assert len(ev(home, "body.booted")) == boots_before, "the observation needed a restart to arrive"
    intruder = tmp_path / "intruder.pem"
    generate_founder_key(intruder, None)
    first = ev(home, "genesis.verified")[0]["capability_id"]
    T.drop_atomic(home, signed(load_founder_key(intruder, None), body_id, "CAPABILITY_ATTACH",
                               {"capability_id": first}), "3-forged-attach.json")
    rejected = W(lambda: ev(home, "command.rejected"), "the forged attach to be refused", body)
    assert not ev(home, "capability.state", state="ATTACHED"), "a forged attach attached something"
    attached = []
    deadline = time.monotonic() + 240
    while not (order_root / "repo" / "tests" / "started.txt").exists():
        assert time.monotonic() < deadline and body.poll() is None, log.read_text()[-3000:]
        for v in ev(home, "genesis.verified"):
            if v["passed"] and v["capability_id"] not in attached:   # the founder answers each attach ask
                attached.append(v["capability_id"])
                T.drop_atomic(home, signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": v["capability_id"]}),
                              f"4-attach-{len(attached)}.json")
        time.sleep(0.2)

    # ---- 10. SIGKILL while the confined worker is in flight ---------------------------------------------------
    at_kill = {"commission": statuses(home, "commission"), "genesis.verified": len(ev(home, "genesis.verified")),
               "attach_asks": len([a for a in asks(home) if a["kind"] == "CAPABILITY_ATTACH"])}
    kill(body)
    assert at_kill["commission"] == [] and not (order_root / "evidence.json").exists()

    # ---- P4: recovery, closure, appraisal, settlement, then extra ticks ---------------------------------------
    body = start_body(home, worker, log)
    W(lambda: ev(home, "mission.appraised", mission_id=MID), "closure and the separate-process appraisal", body,
      timeout=300)
    W(lambda: ev(home, "cognition.settled", mission_id=MID), "settlement", body)
    settled_at_close = len(ev(home, "cognition.settled", mission_id=MID))
    time.sleep(3)                                                       # extra ticks: nothing may act or settle twice
    stop(home, body, greg)

    # ---- 12. the appraiser again, as its own process over the stopped body's ledger ---------------------------
    reappraised = _appraise(SimpleNamespace(home=home), MID)

    # ---- P5: 14-15. a second, fresh mission routes by retained evidence --------------------------------------
    later = templates.compiled_question(problem_id=LATER_ID, data={**STAFFING, "orders": STAFFING["orders"][:2]},
                                        allow_construction=True)   # as test_one_machine.py's later mission
    later_id = later["mission_id"]
    T.drop_atomic(home, signed(key, body_id, "MISSION", later), "5-later.json")
    verified_before = len(ev(home, "genesis.verified"))
    body = start_body(home, worker, log)
    W(lambda: ev(home, "mission.appraised", mission_id=later_id), "the later mission", body)
    stop(home, body, greg)
    control = tmp_path / "control"
    control.mkdir()
    c_home, c_key, c_body, _ = make_body(control)
    T.drop_atomic(c_home, signed(c_key, c_body, "MISSION", later), "1-later.json")
    clock = Clock()
    with Body(c_home, clock=clock) as cbody:
        cbody.boot()
        for _ in range(4):
            cbody.tick()
            clock.advance(31)

    # ================================================================ assertions, each on ledger events by id
    index = T.ledger_index(home)
    assert index["chain_verified"], index["chain_detail"]
    ref = lambda e: T.ref(index, e["event_id"])                          # noqa: E731
    seq = lambda e: index["events"][e["event_id"]]["seq"]                 # noqa: E731
    steps = {}

    # 1. persisted goal and mission, across SIGKILL and stop restarts
    registered = ev(home, "mission.registered", mission_id=MID)
    accepted = {a["kind"]: a for a in ev(home, "command.accepted") if a["kind"] in ("MISSION", "GOAL")}
    boots = ev(home, "body.booted")
    assert len(registered) == 1 and set(accepted) == {"MISSION", "GOAL"} and len(boots) >= 4
    assert ev(home, "body.recovered"), "a SIGKILL restart was not recorded as a recovery"
    steps[1] = {"name": "founder-authorized goal persisted", "events": [ref(registered[0]), ref(accepted["MISSION"]),
                                                                        ref(accepted["GOAL"])],
                "records": {"egregore.goal_authorized": {"seq": authorized[0]["seq"], "goal_id": goal_id}},
                "boots": len(boots)}

    # 2. the observation wakes the goal, whose pull resumes the mission
    pulls = [s for s in ev(home, "mission.schedule", mission_id=MID) if "cause" in s]
    turns = [t for t in records(home, "egregore.gravity_turn")
             if goal_id in (t["turn"].get("woken") or []) and t["seq"] > seq(intake)]
    seen = passing(home, "demand")
    withdrawn = ev(home, "decision.withdrawn", request_id=no_strategy["request_id"])
    unblocked = [u for u in ev(home, "mission.unblocked", mission_id=MID)
                 if (u.get("resolved") or {}).get("request_id") == no_strategy["request_id"]]
    first_compile = ev(home, "mission.action", mission_id=MID, action_id="compile")[0]
    assert pulls and all(goal_id[7:23] in p["cause"] for p in pulls), pulls
    assert all(seq(p) > seq(intake) for p in pulls), "the goal pulled the mission before the observation existed"
    assert turns and seq(intake) < turns[0]["seq"] < seq(pulls[0]), "no wake turn between the observation and pull"
    assert seq(pulls[0]) < seq(seen[0]) < seq(withdrawn[0]) <= seq(unblocked[0]) < seq(first_compile)
    assert "precondition that held compile now passes" in withdrawn[0]["why"]
    steps[2] = {"name": "an observation wakes the goal, which drives the mission",
                "events": [ref(intake), ref(pulls[0]), ref(seen[0]), ref(withdrawn[0]), ref(unblocked[0])],
                "records": {"egregore.gravity_turn (woken)": {"seq": turns[0]["seq"]}},
                "intake": "live: dropped with `greg intake` while the body ran; read on its next tick, no restart",
                "controls": ["request on file for ~4 body-minutes: no observation, no compile",
                             "SIGKILL and restart alone: no observation, no compile, no re-ask"]}

    # 3-7. Mind, catalog search, typed deficit, Genesis, founder-only attach
    comps = T.compilations(home, PROBLEM_ID)
    first_receipt, answer = comps[0]["receipt"], next(c for c in reversed(comps) if c["receipt"]["state"] == "ANSWERED")
    deficits = ev(home, "deficit.opened", mission_id=MID)
    verified = [v for v in ev(home, "genesis.verified") if v["passed"]]
    states = ev(home, "capability.state", state="ATTACHED")
    attach_asks = [a for a in asks(home) if a["kind"] == "CAPABILITY_ATTACH"]
    assert first_receipt["state"] == "CAPABILITY_DEFICIT" and first_receipt["authority_created"] is False
    assert first_receipt["methods_considered"], first_receipt
    assert [d["function"] for d in deficits] == ["assignment.staffing", "graph.max_flow"]
    assert {v["capability_id"] for v in verified} == set(attached) and len(verified) == 2
    assert [s["by"] for s in states] == ["founder command"] * 2 and {s["capability_id"] for s in states} == set(attached)
    assert len(attach_asks) == 2 and all(seq(a) < seq(s) for a, s in zip(attach_asks, states))
    assert answer["receipt"]["method_or_composition_selected"].startswith("composed.assignment.staffing.")
    assert answer["receipt"]["result"]["staffed"] == 8 and answer["receipt"]["authority_created"] is False
    steps[3] = {"name": "the Mind compiles with provenance", "events": [ref(first_compile)], "compile_receipts": [
        {"ledger_seq": c["seq"], "state": c["receipt"]["state"], "receipt_id": c["receipt"]["receipt_id"]} for c in comps],
        "methods_considered": first_receipt["methods_considered"], "authority_created": False}
    steps[4] = {"name": "existing capabilities searched first", "events": [ref(r) for r in ev(home, "genesis.route")
                                                                           if r.get("mission_id", MID) == MID][:8],
                "first_compile_state": first_receipt["state"]}
    steps[5] = {"name": "a typed deficit", "events": [ref(d) for d in deficits],
                "functions": [d["function"] for d in deficits]}
    steps[6] = {"name": "Genesis forms the capability", "events": [ref(v) for v in verified],
                "capabilities": [v["capability_id"] for v in verified]}
    steps[7] = {"name": "attach only on the founder's signed command",
                "events": [ref(a) for a in attach_asks] + [ref(r) for r in rejected] + [ref(s) for s in states],
                "forged_attach_refused": rejected[0]["reason"][:160]}

    # 8. the confined worker uses the Mind's answer; GREG re-checks it
    commission = ev(home, "mission.action", mission_id=MID, action_id="commission")
    done = [c for c in commission if c["status"] == "DONE"]
    [binding] = done[0]["bindings"]
    answered_receipts = {o["receipt"] for o in passing(home, "answered")}
    assert binding["from_check"] == "answered" and binding["from_receipt"] in answered_receipts
    edge = spec["strategies"][2]["bind"][0]
    assert binding["value_sha256"] == sha256_json({"v": bound_value(edge, receipt_output(home, binding["from_receipt"]))})
    summary = json.loads((order_root / "evidence.json").read_text())["summary"]
    report = json.loads((order_root / "worker-report.json").read_text())
    plan = json.loads((order_root / "repo" / "plan" / "plan.json").read_text())
    accepted_work = passing(home, "work_accepted")
    assert summary["status"] == "COMPLETED" and summary["greg_tests_passed"] and summary["commit"]
    assert report["provider"] == "script" and report["isolation"]["mechanism"] == "bubblewrap"
    assert report["isolation"]["network_isolated"] is True
    assert plan["staffed"] == answer["receipt"]["result"]["staffed"]
    assert plan["assignment"] == answer["receipt"]["result"]["assignment"]
    assert accepted_work and not (repo / "plan").exists(), "the source checkout is never touched"
    steps[8] = {"name": "a confined worker uses the Mind's answer, re-checked by GREG",
                "events": [ref(done[0]), ref(accepted_work[0])], "binding": binding,
                "isolation": report["isolation"]["mechanism"], "network": report["isolation"]["network"],
                "greg_tests_passed": summary["greg_tests_passed"], "commit": summary["commit"]}

    # 9. the organs consume the Mind's answer
    organs_done = [a for a in ev(home, "mission.action", mission_id=MID, action_id="organs") if a["status"] == "DONE"]
    [obind] = organs_done[0]["bindings"]
    observed = ev(home, "organ.observed", mission_id=MID)
    appraised_organs = ev(home, "organ.appraised", mission_id=MID)
    exchange = receipt_output(home, organs_done[0]["receipt"])
    oedge = spec["strategies"][1]["bind"][0]
    assert len(organs_done) == 1 and obind["from_check"] == "answered" and obind["from_receipt"] in answered_receipts
    seed = bound_value(oedge, receipt_output(home, obind["from_receipt"]))
    prefix = SEED_TEMPLATE.split("{value}")[0]
    assert obind["value_sha256"] == sha256_json({"v": seed}) and seed.startswith(prefix)
    assert json.loads(seed[len(prefix):]) == answer["receipt"]["result"], "the organs were not handed the Mind's answer"
    assert {o["organ"] for o in observed} == {"daleobanks", "wealthmachine"}
    assert all(o["transport_verified"] for o in observed)
    assert appraised_organs[-1]["verdict"] == "REPRODUCED" and exchange["appraisal_verdict"] == "REPRODUCED"
    assert exchange["organ_heads"] and exchange["authority_created"] is False
    # DALEOBANKS's own hash-chained ledger: it took in exactly the bound seed and refined it into the packet the
    # kernel verified and WealthMachine assessed
    dale = [json.loads(line) for line in (Layout(home).workspace / MID.replace(":", "_") / "organs" /
                                          "daleobanks-wealthmachine" / "daleobanks-decision-ledger.jsonl").read_text()
            .splitlines()]
    intake_row = next(r for r in dale if r["event"] == "idea_intake")
    refined = next(r for r in dale if r["event"] == "idea_refined")
    assert intake_row["payload"]["chars"] == len(seed) and refined["payload"]["id"] == intake_row["payload"]["id"]
    assert refined["payload"]["opportunity"] == exchange["packet_id"]
    steps[9] = {"name": "a real organ process consumes the answer",
                "events": [ref(organs_done[0])] + [ref(o) for o in observed] + [ref(appraised_organs[-1])],
                "binding": obind, "organ_heads": exchange["organ_heads"], "packet_id": exchange["packet_id"],
                "daleobanks_ledger": {"idea_intake_chars": intake_row["payload"]["chars"], "bound_seed_chars": len(seed),
                                      "idea_refined_opportunity": refined["payload"]["opportunity"]},
                "assessment": exchange["assessment"]}

    # 10-11. SIGKILL in flight; recovery keeps authority, budget and the unresolved effect
    assert [c["status"] for c in commission] == ["UNCERTAIN", "RECONCILED_NOT_EXECUTED", "DONE"], commission
    settled_by = commission[1]
    assert settled_by["route"] == "standing_reconciliation" and settled_by["proof"]["holds"], settled_by
    assert not [a for a in asks(home) if a["kind"] in ("RECONCILIATION", "APPROVAL")], "the founder was asked"
    assert len(ev(home, "genesis.verified")) == at_kill["genesis.verified"], "re-qualified after restart"
    assert len(attach_asks) == at_kill["attach_asks"], "re-asked to attach after restart"
    assert [a["kind"] for a in ev(home, "command.accepted")].count("MISSION") == 2   # this one and, later, mission 2
    with observe(home) as journal:
        book = MissionBook(journal).missions[MID]
        spent, budget = book.spent_usd, book.cone.budget_usd
    assert spent <= budget, (spent, budget)
    steps[10] = {"name": "an interruption occurs", "events": [ref(commission[0])],
                 "point": "SIGKILL of the body while the bubblewrap worker was in flight (started.txt present)"}
    steps[11] = {"name": "recovery keeps authority, budget and unresolved-effect state",
                 "events": [ref(c) for c in commission] + [ref(b) for b in ev(home, "body.recovered")],
                 "proof_predicates": settled_by["proof"].get("predicates"), "spent_usd": spent, "budget_usd": budget,
                 "founder_questions_after_kill": 0, "completed_runs": [c["status"] for c in commission].count("DONE")}

    # 12. independent appraisal
    appraisals = ev(home, "mission.appraised", mission_id=MID)
    assert appraisals[-1]["verdict"] == "VERIFIED", appraisals[-1].get("findings")
    assert reappraised["verdict"] == "VERIFIED", reappraised.get("findings")
    steps[12] = {"name": "independent appraisal re-derives the closure", "events": [ref(appraisals[-1])],
                 "rerun_from_stopped_ledger": reappraised["verdict"], "checks": appraisals[-1].get("checks")}

    # 13. settlement exactly once
    achieved = ev(home, "mission.achieved", mission_id=MID)
    settled = ev(home, "cognition.settled", mission_id=MID)
    assert len(achieved) == 1 and len(appraisals) == 1
    assert len(settled) == settled_at_close == 1 and settled[0]["check_id"] == "answered"
    assert Counter(a["action_id"] for a in ev(home, "mission.action", mission_id=MID) if a["status"] == "DONE") == \
        {"compile": 1, "organs": 1, "commission": 1}
    steps[13] = {"name": "settlement happens once", "events": [ref(achieved[0])] + [ref(s) for s in settled],
                 "restarts_after_closure": 2}

    # 14-15. retained evidence changes a later decision on fresh work
    later_comps = T.compilations(home, LATER_ID)
    control_comps = T.compilations(c_home, LATER_ID)
    assert later_comps[0]["receipt"]["state"] == "ANSWERED"
    assert later_comps[0]["receipt"]["method_or_composition_selected"] in attached
    assert not ev(home, "deficit.opened", mission_id=later_id) and not asks(home, later_id)
    assert len(ev(home, "genesis.verified")) == verified_before, "the later mission re-formed a capability"
    assert ev(home, "mission.appraised", mission_id=later_id)[-1]["verdict"] == "VERIFIED"
    assert control_comps[0]["receipt"]["state"] == "CAPABILITY_DEFICIT"
    assert [d["function"] for d in ev(c_home, "deficit.opened")][:1] == ["assignment.staffing"]
    later_answer = later_comps[0]["receipt"]["result"]
    fresh = later["success_checks"][0]["sensor"]["params"]["compile"]["data"]
    assert fresh != STAFFING and later_answer["staffed"] == best_staffing(fresh), "the later answer is not optimal"
    steps[14] = {"name": "retained evidence changes a later decision",
                 "events": [ref(e) for e in ev(home, "mission.appraised", mission_id=later_id)],
                 "same_body_first_compile": {"state": "ANSWERED", "method":
                                             later_comps[0]["receipt"]["method_or_composition_selected"]},
                 "fresh_control_body_first_compile": {"state": control_comps[0]["receipt"]["state"]}}
    steps[15] = {"name": "the changed decision is tested on fresh work", "mission_id": later_id,
                 "events": [ref(e) for e in ev(home, "mission.registered", mission_id=later_id)
                            + ev(home, "mission.achieved", mission_id=later_id)],
                 "answer": {"staffed": later_answer["staffed"]},
                 "independent_check": "exhaustive search over every feasible assignment (no GREG code)"}

    # ---------------------------------------------------------------- the step -> event map
    for n, step in steps.items():
        step["status"] = "SHOWN"
        if n in GAPS:
            step["gap"] = GAPS[n]
    assert sorted(steps) == list(range(1, 16))
    step_map = {"schema": "greg-loop15-step-map/1", "mission_id": MID, "goal_id": goal_id, "ledger_head": index["head"],
                "ledger_records": index["records"], "chain_verified": index["chain_verified"],
                "founder_key": "per-test Ed25519 key; NOT Alfonso", "counts_toward_vepmc": False, "steps": steps}
    with capsys.disabled():
        print("\nLOOP-15 step -> ledger events (mission %s):" % MID)
        for n, step in steps.items():
            ids = [e["event_id"] for e in step.get("events", [])]
            print(f"  {n:>2} {step['name']}: {step['status']}; events {ids[:4]}{' ...' if len(ids) > 4 else ''}"
                  + (f"; GAP: {step['gap'][:90]}..." if "gap" in step else ""))
    evidence = os.environ.get("GREG_LOOP15_EVIDENCE")
    if evidence:
        out = Path(evidence)
        out.mkdir(parents=True, exist_ok=True)
        shutil.copy(Layout(home).ledger, out / "ledger.jsonl")
        (out / "step-map.json").write_text(json.dumps(step_map, indent=1, default=str) + "\n")
        (out / "mission.json").write_text(json.dumps(spec, indent=1) + "\n")

