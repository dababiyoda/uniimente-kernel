"""RECOMBINE: Capability Genesis constructs capabilities from engines it already trusts.

A mission asks for a function no catalog entry, package or founder contract provides
(staffing with skills, one-to-one matching, project crashing). Genesis reduces it onto
an engine it can certify (maximum flow, linear programming), acquiring that engine first
when needed, qualifies the construction on the function's own brute-force oracle through
the real engine, and attaches it only under a founder-signed read-only auto_attach. Every
answer is re-proved in the original problem's terms; a lying engine is caught at that
level, quarantined together with the construction, and replaced.
"""
from __future__ import annotations

import random
from dataclasses import replace

import pytest

pytest.importorskip("networkx")
pytest.importorskip("scipy")

from greg import genesis as genesis_mod  # noqa: E402
from greg import recombine  # noqa: E402
from greg.body import Body  # noqa: E402
from greg.cognition import network  # noqa: E402
from greg.templates import constructed_question  # noqa: E402
from tests.greg_fixtures import Clock, drop, make_body, signed  # noqa: E402

STAFFING = {"workers": [{"id": "Ana", "capacity": 2, "skills": ["forklift"]},
                        {"id": "Ben", "capacity": 4, "skills": ["packing", "forklift"]},
                        {"id": "Cy", "capacity": 3, "skills": ["packing"]}],
            "orders": [{"id": "Dock1", "demand": 4, "skill": "forklift"},
                       {"id": "Dock2", "demand": 3, "skill": "forklift"},
                       {"id": "Line", "demand": 2, "skill": "packing"}]}
MATCHING = {"left": ["a", "b", "c"], "right": ["x", "y", "z"], "pairs": [["a", "x"], ["a", "y"], ["a", "z"],
                                                                        ["b", "x"], ["c", "x"]]}
CRASH = {"tasks": [{"id": "Design", "duration": 5, "min_duration": 3, "cost_per_unit": 4},
                   {"id": "Build", "duration": 8, "min_duration": 5, "cost_per_unit": 2},
                   {"id": "Docs", "duration": 4, "min_duration": 4},
                   {"id": "Test", "duration": 3, "min_duration": 2, "cost_per_unit": 7}],
         "precedences": [["Design", "Build"], ["Build", "Test"], ["Design", "Docs"]], "deadline": 12}


def ticks(body, clock, n):
    out = []
    for _ in range(n):
        out.append(body.tick()["missions"][0])
        clock.advance(31)
    return out


def answers(body, field="composed_of"):
    return [r.payload["result"]["output"] for r in body.ledger.by_type("receipt")
            if isinstance(r.payload["result"].get("output"), dict) and field in r.payload["result"]["output"]]


def routes(body):
    return [(e.payload["route"], e.payload["result"]) for e in body.journal.replay("genesis.route")]


def staffing_answer(params):
    p = recombine.normalize_staffing(params)
    flow = network.certify_max_flow(network.normalize_max_flow(recombine.encode_staffing(p)),
                                    _local_flow(recombine.encode_staffing(p)))
    return p, recombine.decode_staffing(p, flow)


def _local_flow(params):
    import networkx as nx                     # test-only: the body never imports an engine in-process
    req = network.normalize_max_flow(params)
    g = nx.DiGraph()
    g.add_nodes_from(req["nodes"])
    for u, v, c in req["arcs"]:
        g.add_edge(u, v, capacity=c)
    value, flows = nx.maximum_flow(g, req["source"], req["sink"])
    return {"flows": [[u, v, x] for u, out in flows.items() for v, x in out.items() if x], "value": value}


# -- the certificates refute wrong answers in the problem's own terms --------------------------

def test_the_deficiency_set_names_who_is_short_and_refutes_a_false_shortage():
    p, decoded = staffing_answer(STAFFING)
    answer = recombine.certify_staffing(p, decoded)
    assert answer["staffed"] == 8 and answer["shortage"] == 1
    assert answer["bottleneck"]["orders"] == ["Dock1", "Dock2"]
    assert answer["bottleneck"]["eligible_workers"] == ["Ana", "Ben"]
    assert answer["bottleneck"]["demand"] - answer["bottleneck"]["capacity"] == 1
    worse = {**decoded, "assignment": decoded["assignment"][:-1], "staffed": decoded["staffed"]
             - decoded["assignment"][-1][2]}
    with pytest.raises(recombine.ReductionError, match="does not meet the bound"):
        recombine.certify_staffing(p, worse)                 # a suboptimal assignment cannot be passed off
    with pytest.raises(recombine.ReductionError, match="does not meet the bound"):
        recombine.certify_staffing(p, {**decoded, "bottleneck_orders": ["Line"]})   # a false bottleneck
    over = {**decoded, "assignment": [["Cy", "Dock1", 1]] + decoded["assignment"]}
    with pytest.raises(recombine.ReductionError, match="not eligible"):
        recombine.certify_staffing(p, over)                  # Cy cannot drive a forklift


def test_the_oracle_theorem_matches_exhaustive_enumeration():
    rng = random.Random(5)
    for _ in range(40):
        p = recombine.normalize_staffing(recombine._random_staffing(rng))
        assert recombine.staffing_brute_force(p) == recombine.staffing_exhaustive(p)


def test_an_impossible_deadline_is_proved_without_any_engine():
    p = recombine.normalize_crash({**CRASH, "deadline": 9})
    shortcut = recombine.direct_crash(p)
    answer = recombine.certify_crash(p, shortcut)
    assert answer == {**answer, "feasible": False, "chain": ["Design", "Build", "Test"], "shortest_chain_length": 10}
    with pytest.raises(recombine.ReductionError, match="not a precedence chain"):
        recombine.certify_crash(p, {**shortcut, "chain": ["Design", "Test"]})


def test_a_crash_plan_that_breaks_a_limit_or_overpays_is_refused():
    p = recombine.normalize_crash(CRASH)
    good = {"feasible": True, "plan": [["Build", 4, 9], ["Design", 0, 4], ["Docs", 4, 8], ["Test", 9, 12]],
            "lp_objective": 10}
    assert recombine.certify_crash(p, good)["cost"] == 10 == recombine.crash_brute_force(p)
    assert recombine.certify_crash(p, good)["shorten"] == {"Build": 3, "Design": 1}
    with pytest.raises(recombine.ReductionError, match="duration bounds"):
        recombine.certify_crash(p, {**good, "plan": [["Build", 4, 8]] + good["plan"][1:]})
    overpaid = {**good, "plan": [["Build", 3, 9], ["Design", 0, 3], ["Docs", 3, 7], ["Test", 9, 12]]}
    with pytest.raises(recombine.ReductionError, match="plan cost 12 differs from the certified optimum"):
        recombine.certify_crash(p, overpaid)              # feasible, but not the cheapest
    with pytest.raises(recombine.ReductionError, match="starts before"):
        recombine.certify_crash(p, {**good, "plan": good["plan"][:3] + [["Test", 8, 11]]})


def test_the_chain_compiler_is_bounded_and_ends_only_at_a_catalogued_engine():
    catalog = genesis_mod.CATALOG
    path, engine = recombine.chain("assignment.matching", catalog)
    assert [r.reduction_id for r in path] == ["matching-via-staffing", "staffing-via-maxflow"]
    assert engine == "graph.max_flow"
    assert recombine.chain("hash.sha256", catalog) is None              # not a reduction
    loop = {"a": replace(recombine.REDUCTIONS["assignment.staffing"], function="a", target="b"),
            "b": replace(recombine.REDUCTIONS["assignment.staffing"], function="b", target="a")}
    assert recombine.chain("a", catalog, loop) is None                  # cycles never resolve
    dangling = {"a": replace(recombine.REDUCTIONS["assignment.staffing"], function="a", target="nowhere")}
    assert recombine.chain("a", catalog, dangling) is None
    assert [row["function"] for row in recombine.library("hall")] == ["assignment.staffing", "assignment.matching"]


# -- end to end on a real body ----------------------------------------------------------------

def test_a_staffing_mission_constructs_its_capability_over_an_acquired_engine(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", constructed_question(function="assignment.staffing",
                                                                    params=STAFFING, auto_attach=True)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        assert "ACHIEVED" in [s["state"] for s in ticks(body, clock, 3)]
        answer = answers(body)[-1]
        assert answer["certified"] and answer["staffed"] == 8 and answer["shortage"] == 1
        assert answer["bottleneck"]["orders"] == ["Dock1", "Dock2"] and answer["authority_created"] is False
        assert answer["composed_of"] == ["staffing-via-maxflow"] and answer["engine"].startswith("networkx ")
        attached = {cid for cid, s in body.registry.state.items() if s == "ATTACHED"}
        assert "acquired.graph.max_flow.networkx" in attached
        [composed] = [cid for cid in attached if cid.startswith("composed.assignment.staffing.networkx.")]
        manifest = body.registry.manifests[composed]
        assert manifest.consequence_class == "read_only" and manifest.provider == "composed:staffing-via-maxflow"
        assert manifest.provenance["target_capability_id"] == "acquired.graph.max_flow.networkx"
        assert manifest.provenance["qualification"]["failures"] == []
        opened = [e.payload for e in body.journal.replay("deficit.opened")]
        assert [o["function"] for o in opened] == ["assignment.staffing", "graph.max_flow"]
        assert opened[1]["purpose"].startswith("engine for constructed assignment.staffing")
        assert opened[0]["search_order"] == ["attached", "verified_detached", "constructed", "builder", "founder"]
        assert ("constructed", "constructed and verified") in routes(body)
        assert not [r for r in routes(body) if r[0] == "builder"]          # no builder was needed


def test_a_second_function_reuses_the_attached_engine_without_requalifying_it(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", constructed_question(function="assignment.staffing",
                                                                    params=STAFFING, auto_attach=True)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        ticks(body, clock, 3)
        engine_checks = len([e for e in body.journal.replay("genesis.verified")
                             if e.payload["capability_id"].startswith("acquired.")])
    drop(home, signed(key, body_id, "MISSION", constructed_question(function="assignment.matching",
                                                                    params=MATCHING, auto_attach=True)))
    with Body(home, clock=clock) as body:
        body.boot()
        states = [body.tick()["missions"] for _ in range(3)]
        assert any(s["state"] == "ACHIEVED" for batch in states for s in batch)
        match = [a for a in answers(body) if "size" in a][-1]
        # y and z can only be served by a: a Hall set of two rights with one partner (deficit 1)
        assert match["size"] == 2 and match["deficiency"]["deficit"] == 1
        assert match["composed_of"] == ["matching-via-staffing", "staffing-via-maxflow"]
        verified = [e.payload for e in body.journal.replay("genesis.verified")]
        assert len([v for v in verified if v["capability_id"].startswith("acquired.")]) == engine_checks
        functions = [e.payload["function"] for e in body.journal.replay("deficit.opened")]
        assert functions.count("graph.max_flow") == 1                       # the engine deficit was not reopened


def test_a_crash_mission_constructs_over_the_lp_engine(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", constructed_question(function="project.crash", params=CRASH,
                                                                    auto_attach=True)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        assert "ACHIEVED" in [s["state"] for s in ticks(body, clock, 3)]
        answer = answers(body)[-1]
        # The normal plan takes 16. Shortening Build by 3 (6) and Design by 1 (4) meets 12 for 10;
        # Build by 3 and Test by 1 would cost 13. GREG's brute force agrees with the certified optimum.
        p = recombine.normalize_crash(CRASH)
        assert answer["cost"] == recombine.crash_brute_force(p) == 10 and answer["finish"] <= 12
        assert answer["shorten"] == {"Build": 3, "Design": 1}
        assert answer["engine"].split()[0] in ("scipy", "ortools")


def test_without_auto_attach_greg_constructs_nothing_into_service(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", constructed_question(function="assignment.staffing",
                                                                    params=STAFFING)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        assert ticks(body, clock, 2)[-1]["state"] in ("BLOCKED", "WAITING")
        assert all(body.registry.state[cid] != "ATTACHED" for cid in body.registry.manifests
                   if cid.startswith(("acquired.", "composed.")))
        assert ("constructed", "engine graph.max_flow is not attached yet") in routes(body)
        assert not answers(body)


def test_a_lying_engine_is_caught_through_the_construction_and_both_are_replaced(tmp_path, monkeypatch):
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", constructed_question(function="assignment.staffing",
                                                                    params=STAFFING, auto_attach=True)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        ticks(body, clock, 1)
        first = [cid for cid, s in body.registry.state.items() if cid.startswith("composed.") and s == "ATTACHED"]
        assert first
        lie = network.RUNNERS["networkx.max_flow"].replace("def solve(req):", "def solve(req):\n    return "
                                                           "{'flows': [], 'value': 0}\ndef _honest(req):", 1)
        monkeypatch.setitem(network.RUNNERS, "networkx.max_flow", lie)
        states = [s["state"] for s in ticks(body, clock, 8)]
        assert "ACHIEVED" in states, states
        quarantined = [e.payload for e in body.journal.replay("capability.state") if e.payload["state"] == "QUARANTINED"]
        assert {q["capability_id"] for q in quarantined} == {first[0], "acquired.graph.max_flow.networkx"}
        assert all("certificate" in q["why"] for q in quarantined)
        final = answers(body)
        assert final and all(a["staffed"] == 8 for a in final)             # no lie was ever accepted
        assert final[-1]["engine"].startswith("scipy ")
        assert body.registry.state["acquired.graph.max_flow.scipy"] == "ATTACHED"


def test_a_construction_survives_restart_and_is_quarantined_when_its_reduction_code_changes(tmp_path, monkeypatch):
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", constructed_question(function="assignment.staffing",
                                                                    params=STAFFING, auto_attach=True)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        ticks(body, clock, 3)
        [cid] = [c for c in body.registry.manifests if c.startswith("composed.")]
    with Body(home, clock=clock) as body:
        assert body.registry.state[cid] == "ATTACHED"
    changed = replace(recombine.REDUCTIONS["assignment.staffing"], encode=lambda p: recombine.encode_staffing(p))
    monkeypatch.setitem(recombine.REDUCTIONS, "assignment.staffing", changed)
    with Body(home, clock=clock) as body:
        assert body.registry.state[cid] == "QUARANTINED"
        why = [e.payload["why"] for e in body.journal.replay("capability.state")
               if e.payload["capability_id"] == cid and e.payload["state"] == "QUARANTINED"]
        assert why == ["reduction code changed since qualification"]


def test_a_founder_detached_construction_is_not_silently_reattached(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", constructed_question(function="assignment.staffing",
                                                                    params=STAFFING, auto_attach=True)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        ticks(body, clock, 3)
        [cid] = [c for c in body.registry.manifests if c.startswith("composed.")]
    drop(home, signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": cid}))
    staffing_b = {**STAFFING, "orders": STAFFING["orders"][:2]}
    drop(home, signed(key, body_id, "MISSION", constructed_question(function="assignment.staffing",
                                                                    params=staffing_b, auto_attach=True)))
    with Body(home, clock=clock) as body:
        body.boot()
        for _ in range(3):
            body.tick()
            clock.advance(31)
        assert body.registry.state[cid] == "DETACHED"
        assert ("constructed", "founder-detached; explicit attach required") in routes(body)


def test_detaching_the_engine_stops_every_construction_built_on_it(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", constructed_question(function="assignment.staffing",
                                                                    params=STAFFING, auto_attach=True)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        ticks(body, clock, 3)
        [cid] = [c for c in body.registry.manifests if c.startswith("composed.")]
        ctx_manifest = body.registry.manifests[cid]
        body.registry.set_state("acquired.graph.max_flow.networkx", "DETACHED")
        from greg.capabilities import CapabilityError, InvocationContext
        ctx = InvocationContext(workspace=tmp_path, read_roots=(tmp_path,), secrets=None, manifest=ctx_manifest)
        with pytest.raises(CapabilityError, match="engine acquired.graph.max_flow.networkx is not usable"):
            body.registry.adapters[cid](STAFFING, ctx)       # a construction never outlives its engine's attach


def test_every_reduction_carries_a_complete_mechanism_card():
    for r in recombine.REDUCTIONS.values():
        assert set(recombine.CARD_FIELDS) <= set(r.card), r.reduction_id
        assert all(r.card[f] for f in recombine.CARD_FIELDS), r.reduction_id
        assert r.card["classification"] == "BUILDABLE" and r.baseline


def _attached_engine(registry):
    from greg import mechanisms
    from greg.genesis import Genesis, CATALOG, package_adapter
    candidate = next(c for c in CATALOG["graph.max_flow"]["candidates"] if c.distribution == "networkx")
    card = mechanisms.card(candidate, "graph.max_flow", mechanisms.installed("networkx"))
    g = Genesis.__new__(Genesis)
    manifest = g._package_manifest("graph.max_flow", candidate, card, "deficit-test")
    registry.register(manifest, package_adapter("graph.max_flow", candidate), state="ATTACHED")
    return g, manifest


def test_qualification_runs_every_oracle_case_in_one_isolated_engine_run(monkeypatch):
    from greg import mechanisms
    from greg.capabilities import CapabilityRegistry
    registry = CapabilityRegistry()
    g, engine = _attached_engine(registry)
    path, _ = recombine.chain("assignment.staffing", genesis_mod.CATALOG)
    composed = g._composed_manifest("assignment.staffing", path, engine, "deficit-test")
    runs = []
    real = mechanisms.run
    monkeypatch.setattr(mechanisms, "run", lambda *a, **k: runs.append(len(a[2])) or real(*a, **k))
    ok, report = recombine.qualify(path, recombine.composed_adapter(path, registry), composed, 3)
    assert ok and report["engine_calls"] == report["cases"] == 10
    assert runs == [10]                                       # one isolated run, not one per case


def test_a_malformed_request_in_a_batch_is_refused_alone(tmp_path):
    from greg.capabilities import CapabilityError, CapabilityRegistry, InvocationContext
    registry = CapabilityRegistry()
    g, engine = _attached_engine(registry)
    path, _ = recombine.chain("assignment.staffing", genesis_mod.CATALOG)
    composed = g._composed_manifest("assignment.staffing", path, engine, "deficit-test")
    ctx = InvocationContext(workspace=tmp_path, read_roots=(tmp_path,), secrets=None, manifest=composed)
    bad = {"workers": [{"id": "A", "capacity": -1}], "orders": [{"id": "X", "demand": 1}]}
    answers = recombine.composed_adapter(path, registry).batch([STAFFING, bad, STAFFING], ctx)
    assert answers[0]["staffed"] == answers[2]["staffed"] == 8
    assert isinstance(answers[1], CapabilityError) and "constructed request invalid" in str(answers[1])


def test_repair_does_not_readmit_the_construction_that_failed_in_service(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    spec = constructed_question(function="assignment.staffing", params=STAFFING, auto_attach=True)
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        ticks(body, clock, 3)
        [cid] = [c for c in body.registry.manifests if c.startswith("composed.")]
        body.registry.set_state(cid, "QUARANTINED")
        found = body.genesis.resolve(mission=body.engine.book.missions[spec["mission_id"]],
                                     function="assignment.staffing", purpose="repair test", now=clock(),
                                     repair={"capability_id": cid, "replay_path": None,
                                             "failure": "capability refused: composed capability failed its "
                                                        "certificate: test"})
        assert found is None and body.registry.state[cid] == "QUARANTINED"
        assert ("constructed", "this construction failed in service; a different engine is required (the founder "
                               "may re-attach it)") in routes(body)


def test_the_matching_certificate_refuses_a_matching_that_is_not_maximum():
    p = recombine.normalize_matching(MATCHING)
    small = {"pairs": [["b", "x"]], "size": 1, "deficient_right": ["y", "z"]}
    with pytest.raises(recombine.ReductionError, match="maximality is not shown"):
        recombine.certify_matching(p, small)                 # a-y would extend it
    with pytest.raises(recombine.ReductionError, match="matched twice"):
        recombine.certify_matching(p, {"pairs": [["a", "x"], ["a", "y"]], "size": 2, "deficient_right": []})


def test_a_construction_that_fails_its_oracle_is_never_registered(tmp_path, monkeypatch):
    broken = replace(recombine.REDUCTIONS["assignment.staffing"],
                     certify=lambda p, a: {**recombine.certify_staffing(p, a), "staffed": 0})
    monkeypatch.setitem(recombine.REDUCTIONS, "assignment.staffing", broken)
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", constructed_question(function="assignment.staffing",
                                                                    params=STAFFING, auto_attach=True)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        assert ticks(body, clock, 2)[-1]["state"] in ("BLOCKED", "WAITING")
        assert ("constructed", "failed qualification") in [(r, res) for r, res in routes(body)]
        assert not [c for c in body.registry.manifests if c.startswith("composed.")]
        assert not answers(body)
