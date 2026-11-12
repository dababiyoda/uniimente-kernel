"""The Mind and Capability Genesis close one loop: recognize, construct, attach, answer, repair.

A signed problem reaches the Competency Compiler (Layer 5). No admitted method fits, but the
problem's shape matches a certified reduction, so the Mind's CapabilityDeficit names a function
Genesis can construct (not an unbuildable geometry label). Genesis acquires the engine, constructs
and qualifies the capability, and attaches it only inside the mission's signed read-only scope. The
Mind then answers with the construction's problem-level certificate and the mission closes. A
construction that faults while the Mind uses it is repaired by the same two-strike mechanism.
"""
from __future__ import annotations

import contextlib

import pytest

pytest.importorskip("networkx")
pytest.importorskip("scipy")

from greg.body import Body  # noqa: E402
from greg.cognition import network  # noqa: E402
from greg.templates import compiled_question  # noqa: E402
from greg.capabilities import CapabilityError  # noqa: E402
from tests.greg_fixtures import Clock, drop, make_body, note_check, signed, workspace, write_strategy  # noqa: E402

STAFFING = {"workers": [{"id": "Ana", "capacity": 2, "skills": ["forklift"]},
                        {"id": "Ben", "capacity": 4, "skills": ["packing", "forklift"]},
                        {"id": "Cy", "capacity": 3, "skills": ["packing"]}],
            "orders": [{"id": "Dock1", "demand": 4, "skill": "forklift"},
                       {"id": "Dock2", "demand": 3, "skill": "forklift"},
                       {"id": "Line", "demand": 2, "skill": "packing"}]}


def ticks(body, clock, n):
    out = []
    for _ in range(n):
        out.append(body.tick()["missions"][0])
        clock.advance(31)
    return out


def compile_receipts(body):
    return [r.payload["result"]["output"] for r in body.ledger.by_type("receipt")
            if isinstance(r.payload["result"].get("output"), dict)
            and str(r.payload["result"]["output"].get("schema", "")).startswith("greg-competency-compilation/")]


def test_the_mind_names_a_constructible_deficit_and_answers_with_what_genesis_built(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    spec = compiled_question(problem_id="staff-1", data=STAFFING, allow_construction=True,
                             objective="staff the docks and the line")
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        states = [s["state"] for s in ticks(body, clock, 4)]
        assert "ACHIEVED" in states, states
        receipts = compile_receipts(body)
        first, last = receipts[0], receipts[-1]
        # 1. the Mind recognized the shape and named a function Genesis can construct
        assert first["state"] == "CAPABILITY_DEFICIT"
        deficit = first["capability_deficit"]
        assert deficit["function"] == "assignment.staffing"
        assert deficit["constructible"] == {"chain": ["staffing-via-maxflow"], "engine": "graph.max_flow",
                                            "alternatives": []}
        assert "constructed" in deficit["search_order"]
        # 2. Genesis acquired the engine and constructed the function under the mission's authority
        opened = [e.payload["function"] for e in body.journal.replay("deficit.opened")]
        assert opened == ["assignment.staffing", "graph.max_flow"]
        # 3. the Mind answered with the attached construction and its certificate
        assert last["state"] == "ANSWERED"
        assert last["method_or_composition_selected"].startswith("composed.assignment.staffing.")
        assert last["result"]["staffed"] == 8 and last["result"]["bottleneck"]["orders"] == ["Dock1", "Dock2"]
        assert last["confidence_type"] == "certified: exact problem-level certificate"
        assert last["authority_created"] is False
        appraised = [e.payload for e in body.journal.replay("mission.appraised")]
        assert appraised and appraised[-1]["verdict"] == "VERIFIED", appraised


def test_without_a_signed_construction_scope_the_founder_attaches_engine_then_construction(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    spec = compiled_question(problem_id="staff-2", data=STAFFING)
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        ticks(body, clock, 2)
        m = body.engine.book.missions[spec["mission_id"]]
        assert m.blocker and m.blocker["function"] == "assignment.staffing"   # not "cognition.optimization:..."
        ask = [e.payload for e in body.journal.replay("decision.requested")
               if e.payload["mission_id"] == spec["mission_id"]][-1]
        named = {c["capability_id"]: c for c in ask["evidence"]["registered"]}
        assert named["acquired.graph.max_flow.networkx"]["state"] == "VERIFIED"   # attachable from this ask
        assert not [c for c in body.registry.manifests if c.startswith("composed.")]
    drop(home, signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": "acquired.graph.max_flow.networkx"}))
    with Body(home, clock=clock) as body:
        body.boot()
        ticks(body, clock, 3)
        [cid] = [c for c in body.registry.manifests if c.startswith("composed.assignment.staffing.")]
        assert body.registry.state[cid] == "VERIFIED"                    # constructed, never self-attached
        m = body.engine.book.missions[spec["mission_id"]]
        assert m.blocker and m.blocker["function"] == "assignment.staffing"
        unblocks = [e for e in body.journal.replay("mission.unblocked") if e.payload["mission_id"] == m.mission_id]
        assert len(unblocks) == 1                                         # one unblock to construct, no churn
        latest = [e.payload for e in body.journal.replay("decision.requested")
                  if e.payload["mission_id"] == m.mission_id][-1]
        waiting = {c["capability_id"]: c["state"] for c in latest["evidence"]["registered"]}
        assert waiting[cid] == "VERIFIED"                                 # a new ask names what to attach next
        from provenance.ledger import sha256_json
        assert latest["scope_digest"] == sha256_json({"function": "assignment.staffing", "awaiting": cid})
    drop(home, signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": cid}))
    with Body(home, clock=clock) as body:
        body.boot()
        assert "ACHIEVED" in [s["state"] for s in ticks(body, clock, 3)]
        assert compile_receipts(body)[-1]["result"]["staffed"] == 8


def test_a_construction_that_lies_through_the_mind_is_repaired_by_the_same_mechanism(tmp_path, monkeypatch):
    home, key, body_id, _ = make_body(tmp_path)
    spec = compiled_question(problem_id="staff-3", data=STAFFING, allow_construction=True)
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        ticks(body, clock, 1)                              # deficit -> construction -> read-only attach
        [first] = [c for c, s in body.registry.state.items() if c.startswith("composed.") and s == "ATTACHED"]
        assert not [r for r in compile_receipts(body) if r["state"] == "ANSWERED"]
        lie = network.RUNNERS["networkx.max_flow"].replace(
            "def solve(req):", "def solve(req):\n    return {'flows': [], 'value': 0}\ndef _honest(req):", 1)
        monkeypatch.setitem(network.RUNNERS, "networkx.max_flow", lie)   # the engine now lies in service
        states = [s["state"] for s in ticks(body, clock, 8)]
        assert "ACHIEVED" in states, states
        faults = [r["capability_fault"] for r in compile_receipts(body) if r.get("capability_fault")]
        assert faults and faults[0]["capability_id"] == first and "faulted" in faults[0]["detail"]
        quarantined = {e.payload["capability_id"] for e in body.journal.replay("capability.state")
                       if e.payload["state"] == "QUARANTINED"}
        assert {first, "acquired.graph.max_flow.networkx"} <= quarantined
        answered = [r for r in compile_receipts(body) if r["state"] == "ANSWERED"]
        assert all(r["result"]["staffed"] == 8 for r in answered)          # the lie never became an answer
        assert answered[-1]["result"]["engine"].startswith("scipy ")
        assert body.registry.state["acquired.graph.max_flow.scipy"] == "ATTACHED"


def test_a_faulting_construction_is_repaired_without_asking_the_founder_for_a_strategy(tmp_path, monkeypatch):
    """The only check that does not pass is the one a faulted construction could not answer. Nothing was measured
    failing, so there is nothing to pursue: the mission re-observes and the second strike re-forms the construction.

    Before (measured on #196 at 8d205324): the first strike was pursued as a failed goal. No strategy advances the
    check, so the founder was asked a NO_STRATEGY question one pass before self-repair mended it. With the faulted
    check only left out of what is pursued, the mission pursued nothing and never looked again."""
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", compiled_question(problem_id="staff-4", data=STAFFING,
                                                                  allow_construction=True)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        ticks(body, clock, 1)                              # deficit -> construction -> read-only attach
        lie = network.RUNNERS["networkx.max_flow"].replace(
            "def solve(req):", "def solve(req):\n    return {'flows': [], 'value': 0}\ndef _honest(req):", 1)
        monkeypatch.setitem(network.RUNNERS, "networkx.max_flow", lie)   # the engine now lies in service
        states = [s["state"] for s in ticks(body, clock, 4)]
        assert states[:3] == ["SENSOR_RETRY", "REPAIRED", "ACHIEVED"], states
        asked = [e.payload["kind"] for e in body.journal.replay("decision.requested")]
        assert asked == [], asked
        assert not list(body.journal.replay("mission.blocked"))
        # The faulted readings are on record as unmeasured and typed, as a failed sensor call is. Recorded as
        # measured failures (before), they blamed the strategy that had asked the question: one routing.outcome
        # "ineffective" against cognition.solve for a fault of the construction under it.
        faulted = [o for o in (e.payload for e in body.journal.replay("mission.observed")) if not o["passed"]][-2:]
        assert [o["failure_class"] for o in faulted] == ["executor_error"] * 2, faulted
        assert all(o["detail"].startswith("sensor inconclusive (capability fault): ") for o in faulted), faulted
        assert not list(body.journal.replay("routing.outcome"))


LIE = "def solve(req):\n    return {'flows': [], 'value': 0}\ndef _honest(req):"


@contextlib.contextmanager
def _serving_construction(tmp_path, spec):
    """A body whose signed question is being answered by a construction GREG formed, with its clock."""
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        for _ in range(6):
            ticks(body, clock, 1)
            if any(c.startswith("composed.") and state == "ATTACHED" for c, state in body.registry.state.items()):
                break
        else:
            pytest.fail("no construction was formed and attached")
        yield body, clock


def test_a_refused_read_beside_a_faulting_construction_keeps_its_route(tmp_path, monkeypatch):
    """Two checks fail in one pass and neither was measured: the construction that answers the question faults, and
    a file another check reads has grown past the read ceiling, so that read is refused. The refused check has a
    strategy that rewrites the file. It runs, as it did on #196 at 8d205324, where the fault counted as a measured
    failure. With every Mind-named fault simply added to the unmeasured checks (the first form of this fix), the
    pass re-observed instead, the strategy never ran, and the mission ended on a founder question it had not asked
    before (independent review, finding 2)."""
    spec = compiled_question(problem_id="staff-r", data=STAFFING, allow_construction=True)
    cone = spec["light_cone"]
    cone["capabilities"] += ["fs.read", "fs.write"]
    cone["targets"] += ["fs:*", "workspace:*"]
    cone["max_consequence_class"] = "internal_write"
    r_file = workspace(tmp_path / "body", spec["mission_id"]) / "r.txt"      # make_body's home
    spec["success_checks"].append(note_check("r", r_file, "y"))
    spec["strategies"].append(write_strategy("maker", "r.txt", "y", ["r"]))
    with _serving_construction(tmp_path, spec) as (body, clock):
        if not r_file.exists() or r_file.read_text() != "y":
            pytest.fail("the story did not reach a written file and a serving construction")
        monkeypatch.setitem(network.RUNNERS, "networkx.max_flow",
                            network.RUNNERS["networkx.max_flow"].replace("def solve(req):", LIE, 1))
        r_file.write_text("z" * (300 * 1024))      # past the read ceiling: the read is refused, not measured
        seen = ticks(body, clock, 4)
        states = [s["state"] for s in seen]
        assert states[0] == "ACTED" and seen[0].get("action") == "maker", seen[0]
        assert "REPAIRED" in states and states[-1] == "ACHIEVED", states
        assert r_file.read_text() == "y"
        assert [e.payload["kind"] for e in body.journal.replay("decision.requested")] == []


def test_a_failure_closure_names_the_check_a_faulted_construction_could_not_answer(tmp_path, monkeypatch):
    """Beside the faulted construction, a check with no strategy fails for real. The mission closes as unmet on that
    check, the closure says which check it could not measure, and the construction is repaired while the mission
    is blocked. Recorded as a measured failure (before), the
    faulted check was named nowhere in the closure once it was left out of what is pursued (independent review,
    finding 5)."""
    spec = compiled_question(problem_id="staff-u", data=STAFFING, allow_construction=True)
    cone = spec["light_cone"]
    cone["capabilities"] += ["fs.read"]
    cone["targets"] += ["fs:*"]
    status = tmp_path / "data" / "status.txt"
    spec["success_checks"].append(note_check("status", status, "shipped"))
    (tmp_path / "data").mkdir(exist_ok=True)
    status.write_text("shipped")
    with _serving_construction(tmp_path, spec) as (body, clock):
        monkeypatch.setitem(network.RUNNERS, "networkx.max_flow",
                            network.RUNNERS["networkx.max_flow"].replace("def solve(req):", LIE, 1))
        status.write_text("not yet")
        states = [s["state"] for s in ticks(body, clock, 2)]
        unmet = [e.payload for e in body.journal.replay("mission.unmet")]
        assert unmet and unmet[-1]["failing_checks"] == ["status"], unmet
        assert unmet[-1].get("unmeasured_checks") == ["answered"], unmet
        # The mission is blocked on the real failure, and the construction is still repaired on its second strike:
        # a blocked mission keeps looking, and a fault of its own machinery never waits on the founder. Before this
        # change a fault the Mind named blocked the mission by itself, and the test of that repair went through
        # that block; now only a real failure beside the fault reaches it.
        assert states == ["BLOCKED", "REPAIRED"], states
        assert [e.payload["kind"] for e in body.journal.replay("decision.requested")] == ["NO_STRATEGY"]


def test_a_fault_hidden_by_a_long_predicate_is_still_repaired(tmp_path, monkeypatch):
    """The kept detail of an observation is cut at 300 characters, and a check with a long predicate fills that
    before the fault's own words are reached. Self-repair recognised a fault by those words when the reading
    carried no type, so it never saw two strikes, and with the pass re-observing instead of pursuing (the first form
    of this fix) the mission retried every 30 seconds for ever and asked nobody (independent review, finding 3).
    The reading is typed now, so the second strike re-forms the construction."""
    spec = compiled_question(problem_id="staff-l", data=STAFFING, allow_construction=True)
    spec["success_checks"][0]["predicate"] = {
        "op": "contains", "field": "assumptions",
        "value": "every worker listed is available for the whole shift named in the order book; " * 5}
    with _serving_construction(tmp_path, spec) as (body, clock):
        monkeypatch.setitem(network.RUNNERS, "networkx.max_flow",
                            network.RUNNERS["networkx.max_flow"].replace("def solve(req):", LIE, 1))
        states = [s["state"] for s in ticks(body, clock, 3)]
        assert "REPAIRED" in states[:3], states
        cut = [o for o in (e.payload for e in body.journal.replay("mission.observed"))
               if o.get("failure_class") == "executor_error"]
        assert len(cut) >= 2 and all("faulted" not in o["detail"] for o in cut), cut   # the words were cut away


def test_a_construction_that_faults_every_other_pass_reaches_the_founder(tmp_path):
    """A construction that faults, then is stopped by the host, then faults again never shows self-repair two
    strikes in a row. Each such pass measured nothing. Three unmeasured rounds ask the founder once, as for any
    sensor that cannot read. With a Mind-named fault recorded as measured, the round count started again at every
    fault: the mission retried for ever and asked nobody (independent review, finding 3)."""
    spec = compiled_question(problem_id="staff-a", data=STAFFING, allow_construction=True)
    with _serving_construction(tmp_path, spec) as (body, clock):
        calls = {"n": 0}

        def flaky(params, ctx):
            calls["n"] += 1
            if calls["n"] % 2:
                raise CapabilityError("capability refused: composed engine acquired.graph.max_flow.networkx faulted: "
                                      "package output failed its certificate")
            raise CapabilityError("capability refused: the runner did not finish within 30s", failure_class="transient")
        for cid in [c for c in body.registry.adapters if c.startswith("composed.")]:
            body.registry.adapters[cid] = flaky
        states = [s["state"] for s in ticks(body, clock, 8)]
        asked = [e.payload["kind"] for e in body.journal.replay("decision.requested")]
        assert asked == ["SENSOR_FAILURE"], (asked, states)
        assert "BLOCKED" in states[:5], states


def test_a_problem_no_reduction_fits_keeps_the_existing_deficit(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    spec = compiled_question(problem_id="fold-1", data={"sequence": "ACDE"}, allow_construction=True,
                             geometry={"geometry": "optimization", "subgeometry": "protein folding"})
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        ticks(body, clock, 2)
        m = body.engine.book.missions[spec["mission_id"]]
        assert m.blocker["function"] == "cognition.optimization:protein folding"
        assert spec["light_cone"]["capabilities"] == ["cognition.solve"]   # nothing constructible to pre-authorize
        assert not [c for c in body.registry.manifests if c.startswith("composed.")]


def test_a_detached_construction_is_never_used_by_the_mind(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    spec = compiled_question(problem_id="staff-4", data=STAFFING, allow_construction=True)
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        ticks(body, clock, 4)
        [cid] = [c for c in body.registry.manifests if c.startswith("composed.")]
    drop(home, signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": cid}))
    other = compiled_question(problem_id="staff-5", data={**STAFFING, "orders": STAFFING["orders"][:2]},
                              allow_construction=True)
    drop(home, signed(key, body_id, "MISSION", other))
    with Body(home, clock=clock) as body:
        body.boot()
        for _ in range(3):
            body.tick()
            clock.advance(31)
        assert body.registry.state[cid] == "DETACHED"
        later = [r for r in compile_receipts(body) if r["problem_id"] == "staff-5"]
        assert later and all(r["method_or_composition_selected"] != cid for r in later)
        assert not any(r["state"] == "ANSWERED" for r in later)


def test_the_appraiser_restores_constructions_without_writing_even_when_one_must_be_quarantined(tmp_path,
                                                                                                monkeypatch):
    from dataclasses import replace
    from events.spine import EventSpine
    from greg import appraisal, recombine
    from greg.journal import Journal
    from provenance.ledger import EvidenceLedger
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", compiled_question(problem_id="staff-6", data=STAFFING,
                                                                 allow_construction=True)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        ticks(body, clock, 3)
        [cid] = [c for c in body.registry.manifests if c.startswith("composed.")]
        constitution, ledger_path, workspace = body.compiled.constitution_hash, str(body.layout.ledger), \
            body.layout.workspace
        head = body.ledger.head
    changed = replace(recombine.REDUCTIONS["assignment.staffing"], encode=lambda p: recombine.encode_staffing(p))
    monkeypatch.setitem(recombine.REDUCTIONS, "assignment.staffing", changed)
    ledger = EvidenceLedger(constitution, ledger_path, read_only=True, expected_head=head, tail="ignore")
    before = len(list(ledger.by_type("event")))
    registry = appraisal._formed_registry(Journal(EventSpine(ledger), actor="spiffe://test/appraiser"), workspace)
    assert registry.state[cid] == "QUARANTINED"                          # same check as restart, nothing written
    assert len(list(ledger.by_type("event"))) == before
