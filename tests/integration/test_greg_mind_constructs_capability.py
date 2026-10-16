"""The Mind and Capability Genesis close one loop: recognize, construct, attach, answer, repair.

A signed problem reaches the Competency Compiler (Layer 5). No admitted method fits, but the
problem's shape matches a certified reduction, so the Mind's CapabilityDeficit names a function
Genesis can construct (not an unbuildable geometry label). Genesis acquires the engine, constructs
and qualifies the capability, and attaches it only inside the mission's signed read-only scope. The
Mind then answers with the construction's problem-level certificate and the mission closes. A
construction that faults while the Mind uses it is repaired by the same two-strike mechanism.
"""
from __future__ import annotations

import pytest

pytest.importorskip("networkx")
pytest.importorskip("scipy")

from greg.body import Body  # noqa: E402
from greg.cognition import network  # noqa: E402
from greg.templates import compiled_question  # noqa: E402
from tests.greg_fixtures import Clock, drop, make_body, signed  # noqa: E402

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
