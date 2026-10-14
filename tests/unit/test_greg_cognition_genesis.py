"""Capability Genesis for cognition deficits (directive 2026-10-07 section 24; section 31 item 14).

When the Competency Compiler finds no method for a geometry, the mission's one Genesis loop searches the
registered repertoire first (a withheld genome that fits is named for the founder to attach), then installed
open-source mechanisms (a Mechanism Card, a frozen oracle drawn from an admission instance generator on
development seeds only, GREG's certificate on every answer). Nothing is attached by GREG, not even under a
mission's auto_attach; the founder is asked once, through greg.asks. After the founder's attach the compiler
routes the geometry to the formed mechanism and the original mission closes.
"""
from __future__ import annotations

from fractions import Fraction
import itertools
import json
import random

import pytest

pytest.importorskip("scipy")
pytest.importorskip("ortools")

from greg import genesis as G  # noqa: E402
from greg import mechanisms  # noqa: E402
from greg.body import Body  # noqa: E402
from greg.capabilities import CapabilityError  # noqa: E402
from greg.cognition import assignment as A  # noqa: E402
from greg.cognition import compiler  # noqa: E402
from greg.cognition.cortex import reason, registry_view  # noqa: E402
from greg.cognition.genomes import library  # noqa: E402
from tests.greg_fixtures import Clock, drop, make_body, mission, signed  # noqa: E402

COSTS = [[7, 3, 9, 4], [2, 8, 6, 5], [6, 4, 3, 8]]          # optimum 8: rows to columns 1, 0, 2
SCIPY = f"acquired.{A.FUNCTION}.scipy"


def candidate(distribution):
    return next(c for c in G.CATALOG[A.FUNCTION]["candidates"] if c.distribution == distribution)


def compile_mission(mission_id, geometry, data, **kw):
    params = {"problem_id": f"real:{mission_id}", "compile": {"geometry": geometry, "data": data}}
    return mission(mission_id, checks=[{
        "check_id": "answered", "description": "a competent method answered",
        "sensor": {"capability": "cognition.solve", "target": "cognition:residual", "params": params},
        "predicate": {"op": "equals", "field": "state", "value": "ANSWERED"}}],
        strategies=[{"action_id": "compile", "capability": "cognition.solve", "target": "cognition:residual",
                     "params": params, "advances": ["answered"], "rationale": "compile the residual geometry"}],
        capabilities=["cognition.solve"], targets=("cognition:*",), ceiling="read_only", **kw)


def ticks(body, clock, n):
    out = []
    for _ in range(n):
        out.append(body.tick()["missions"][0])
        clock.advance(31)
    return out


def compilations(body):
    return [r.payload["result"]["output"] for r in body.ledger.by_type("receipt")
            if isinstance(r.payload["result"].get("output"), dict)
            and str(r.payload["result"]["output"].get("schema", "")).startswith("greg-competency-compilation")]


def attach_asks(body):
    return [e.payload for e in body.journal.replay("decision.requested") if e.payload["kind"] == "CAPABILITY_ATTACH"]


@pytest.fixture
def index(tmp_path, monkeypatch):
    """A frozen evidence index this test controls (the compiler and Genesis read the same one)."""
    path = tmp_path / "index.json"
    monkeypatch.setattr(compiler, "EVIDENCE_INDEX", path)
    path.write_text(json.dumps({"genomes": {}, "recipes": {}, "routing": {}}))
    return path


def attached_registry(tmp_path):
    """A registry view with the SciPy assignment mechanism registered as Genesis forms it, then founder-attached."""
    registry = registry_view()
    c = candidate("scipy")
    card = mechanisms.card(c, A.FUNCTION, mechanisms.installed("scipy"))
    manifest = G.Genesis(journal=None, registry=registry, workspace_root=tmp_path / "ws")._package_manifest(
        A.FUNCTION, c, card, "deficit-test")
    registry.register(manifest, G.package_adapter(A.FUNCTION, c), state="ATTACHED")
    return registry


# -- the mechanism: competence, certificate, oracle ------------------------------------------

def test_the_certificate_accepts_any_optimum_and_refutes_suboptimal_or_malformed_claims():
    req = A.normalize_assignment({"costs": [[4, 1, 3], [2, 0, 5]]})
    for tie in ([[0, 1], [1, 0]], [[0, 2], [1, 1]]):                       # two optimal assignments, total 3
        assert A.certify_assignment(req, {"pairs": tie})["total"] == 3
    with pytest.raises(A.CertificateError, match="unassigned column"):
        A.certify_assignment(req, {"pairs": [[0, 0], [1, 1]]})           # row 0 is cheaper on free column 2
    with pytest.raises(A.CertificateError, match="distinct column"):
        A.certify_assignment(req, {"pairs": [[0, 2], [1, 2]]})
    with pytest.raises(A.CertificateError, match="distinct column"):
        A.certify_assignment(req, {"pairs": [[0, 1]]})
    with pytest.raises(A.CertificateError, match="integers"):
        A.certify_assignment(req, {"pairs": [[0, True], [1, 0]]})
    square = A.normalize_assignment({"costs": [[1, 5, 9], [9, 1, 5], [5, 9, 1]]})
    with pytest.raises(A.CertificateError, match="cycle of exchanges"):
        A.certify_assignment(square, {"pairs": [[0, 1], [1, 2], [2, 0]]})   # 15 against the diagonal's 3
    tall = A.normalize_assignment({"costs": [[4, 2], [1, 0], [3, 5]], "maximize": True})
    best = A.certify_assignment(tall, {"pairs": [[0, 0], [1, 2]]})        # columns -> rows 0 and 2: 4 + 5
    assert best["total"] == 9 and best["pairs"] == [[0, 0], [2, 1]] and best["shape"] == [3, 2]


@pytest.mark.parametrize("seed", range(40))
def test_every_suboptimal_assignment_is_refuted_and_every_optimal_one_certified(seed):
    rng = random.Random(seed)
    m, n = rng.randint(1, 5), rng.randint(1, 5)
    params = {"costs": [[rng.choice([rng.randint(-6, 6), round(rng.uniform(-5, 5), 3)]) for _ in range(n)]
                        for _ in range(m)], "maximize": seed % 3 == 0}
    req = A.normalize_assignment(params)
    sign = -1 if params["maximize"] else 1
    totals = {chosen: sign * sum(Fraction(req["costs"][i][j]) for i, j in enumerate(chosen))   # original units
              for chosen in itertools.permutations(range(req["cols"]), req["rows"])}
    optimum = (max if params["maximize"] else min)(totals.values())
    assert A.brute_force(params) == A._plain(optimum)                     # the oracle's own enumeration agrees
    for chosen, total in totals.items():
        claim = {"pairs": [[i, j] for i, j in enumerate(chosen)]}
        if total == optimum:
            assert A.certify_assignment(req, claim)["total"] == A._plain(optimum)
        else:
            with pytest.raises(A.CertificateError):
                A.certify_assignment(req, claim)
    assert A.local_hungarian(req)["total"] == A._plain(optimum)           # the local baseline agrees


def test_the_frozen_oracle_draws_admission_instances_on_development_seeds_only(monkeypatch):
    from greg.cognition.genomes import admission, collective
    seen, real = [], collective.flock_instance
    monkeypatch.setattr(collective, "flock_instance", lambda seed: seen.append(seed) or real(seed))
    A._frozen_cases.cache_clear()
    try:
        cases = A.oracle_assignment(123456789)
    finally:
        A._frozen_cases.cache_clear()
    assert sorted(seen) == list(admission.DEV_SEEDS)                      # never a held-out or reserved seed
    assert not set(seen) & set(admission.HELDOUT_SEEDS) and not set(seen) & set(admission.P8_RESERVED)
    assert cases == A.oracle_assignment(7)                                 # frozen: the deficit seed chooses nothing
    flocks = [c for c in cases if c["name"].startswith("flock-dev")]
    shapes = {(len(c["input"]["costs"]) > len(c["input"]["costs"][0]), len(c["input"]["costs"]) <
               len(c["input"]["costs"][0]), c["input"].get("maximize", False)) for c in flocks}
    assert len(flocks) == 10 and len(shapes) == 4                          # square, tall, wide, maximise
    assert any(isinstance(x, float) for c in flocks for row in c["input"]["costs"] for x in row)


@pytest.mark.parametrize("params, message", [
    ({"costs": []}, "1-200 rows"),
    ({"costs": [[1, 2], [3]]}, "rectangular"),
    ({"costs": [[float("nan")]]}, "not finite"),
    ({"costs": [[True]]}, "not a number"),
    ({"costs": [[1e13]]}, "1e12"),
    ({"costs": [[1]], "maximize": "yes"}, "maximize"),
    ({"costs": [[0] * 201]}, "1-200 columns"),
])
def test_requests_outside_competence_are_refused_before_any_engine_and_are_not_engine_faults(params, message):
    with pytest.raises(CapabilityError, match=message) as caught:
        A.normalize_assignment(params)
    manifest = type("M", (), {"provider": "installed:python:scipy==1", "binaries": ()})()
    assert not G.is_capability_fault(manifest, f"capability refused: {caught.value}")


def test_scipy_qualifies_on_the_frozen_oracle_and_or_tools_integer_assignment_does_not():
    c = candidate("scipy")
    passed, report = G.qualify_package(A.FUNCTION, c, mechanisms.card(c, A.FUNCTION, mechanisms.installed("scipy")),
                                       seed=20261014)
    assert passed, report["failures"]
    assert report["cases"] == len(A.FIXED) + 10 and "development seeds" in report["oracle"]
    probe = report["scale_probe"]
    assert probe["certified"] and probe["agrees_with_local"] and (probe["rows"], probe["cols"]) == (200, 200)
    o = candidate("ortools")
    passed, report = G.qualify_package(A.FUNCTION, o, mechanisms.card(o, A.FUNCTION, mechanisms.installed("ortools")),
                                       seed=20261014)
    failed = {f["case"] for f in report["failures"]}
    assert not passed and "decimal" in failed and "flock-dev0" in failed     # real-valued costs: outside it
    assert not failed & {"wide", "tall", "negative", "maximize", "flock-dev1"}  # integer cases: correct


def test_a_lying_engine_is_caught_by_the_frozen_oracle(monkeypatch):
    lie = A.RUNNERS["scipy.assignment"].replace(
        "return {", "rows, cols = rows, cols[::-1] if len(cols) > 1 else cols\n    return {")
    monkeypatch.setitem(A.RUNNERS, "scipy.assignment", lie)
    c = candidate("scipy")
    passed, report = G.qualify_package(A.FUNCTION, c, mechanisms.card(c, A.FUNCTION, mechanisms.installed("scipy")), 7)
    assert not passed and any("certificate" in f for f in report["failures"])


def test_a_mechanism_matches_a_residual_geometry_only_when_it_reads_every_input():
    assert G.cognition_mechanisms({"costs"}, "optimization") == [A.FUNCTION]
    assert G.cognition_mechanisms({"costs", "maximize", "formalization_complete"}, None) == [A.FUNCTION]
    assert G.cognition_mechanisms({"costs", "budget"}, "optimization") == []      # a budget is never ignored
    assert G.cognition_mechanisms({"costs"}, "prediction") == []
    assert G.cognition_mechanisms({"maximize"}, "optimization") == []


def test_only_compiler_deficits_take_the_cognition_route():
    assert G.is_cognition_deficit("cognition.optimization:assignment")
    assert G.is_cognition_deficit("cognition.unknown:unspecified")
    for function in ("cognition.exact", "graph.shortest_path", "hash.sha256", A.FUNCTION):
        assert not G.is_cognition_deficit(function)
    assert compiler.GENESIS_SEARCH == tuple(G.COGNITION_SEARCH)
    record = G.cognition_record("cognition.optimization:assignment")
    assert record["geometry"] == "optimization" and record["required_inputs"] == [] and not record["inputs_known"]


# -- the compiler routes to a founder-attached formed mechanism, on GREG's certificate only -----

def test_an_attached_formed_mechanism_serves_its_geometry_and_a_lie_is_refused(tmp_path, monkeypatch, index):
    registry = attached_registry(tmp_path)
    request = {"geometry": {"geometry": "optimization"}, "data": {"costs": COSTS}}
    r = reason({"problem_id": "assign", "compile": request}, registry=registry)
    assert r["state"] == "ANSWERED" and r["method_or_composition_selected"] == SCIPY
    assert r["selection_level"] == "formed_by_capability_genesis" and r["authority_created"] is False
    assert r["result"]["total"] == 8 and r["result"]["pairs"] == [[0, 1], [1, 0], [2, 2]]
    assert r["confidence_type"] == "optimality_certificate" and "GREG-owned" in r["verification_method"]
    high = reason({"problem_id": "assign", "compile": {**request, "geometry": {
        "geometry": "optimization", "consequence_class": "financial"}}}, registry=registry)
    assert high["state"] == "FORMALIZATION_INCOMPLETE"
    complete = reason({"problem_id": "assign", "compile": {"geometry": {"geometry": "optimization",
                                                                         "consequence_class": "financial"},
                                                            "data": {"costs": COSTS, "formalization_complete": True}}},
                      registry=registry)
    assert complete["state"] == "WORLD_UNVERIFIED" and complete["result"]["total"] == 8
    budgeted = reason({"problem_id": "assign", "compile": {**request, "data": {"costs": COSTS, "budget": 5}}},
                      registry=registry)
    assert budgeted["state"] == "CAPABILITY_DEFICIT"                     # an input it cannot read: not routed
    identity = A.RUNNERS["scipy.assignment"].replace("return {", "cols = rows\n    return {")
    monkeypatch.setitem(A.RUNNERS, "scipy.assignment", identity)        # the engine now lies in service
    lied = reason({"problem_id": "assign", "compile": request}, registry=registry)
    assert lied["state"] == "CAPABILITY_DEFICIT" and lied["result"] is None
    assert any("certificate" in a for a in lied["abstentions"])
    registry.set_state(SCIPY, "DETACHED")
    assert reason({"problem_id": "assign", "compile": request}, registry=registry)["state"] == "CAPABILITY_DEFICIT"


# -- the body: deficit -> card -> one founder ask -> founder attach -> the mission closes ------

def test_an_assignment_deficit_forms_scipy_on_a_card_and_asks_the_founder_exactly_once(tmp_path, index):
    home, key, body_id, _ = make_body(tmp_path)
    geometry = {"geometry": "optimization", "subgeometry": "assignment"}
    drop(home, signed(key, body_id, "MISSION", compile_mission("m:assign", geometry, {"costs": COSTS},
                                                                auto_attach=True)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        assert ticks(body, clock, 3)[-1]["state"] in ("BLOCKED", "WAITING")
        [opened] = [e.payload for e in body.journal.replay("deficit.opened")]
        assert opened["function"] == "cognition.optimization:assignment"
        assert opened["search_order"] == G.COGNITION_SEARCH and opened["cognition"]["required_inputs"] == ["costs"]
        assert opened["acceptance"]["oracle"] == {A.FUNCTION: G.CATALOG[A.FUNCTION]["oracle_kind"]}
        routes = [(e.payload["route"], e.payload["result"], e.payload["capability_id"])
                  for e in body.journal.replay("genesis.route")]
        assert ("genome_library", "no registered intelligence fits: none of geometry optimization takes its native "
                                  "inputs from ['costs']", None) in routes
        # the registered same-engine genome is reported with why it does not fit, never passed over in silence
        [lsa] = [r for r in routes if r[0] == "existing_project" and r[2] == "cognition.assignment_lsa"]
        assert "same engine" in lsa[1] and "reads cost_matrix" in lsa[1]
        assert body.registry.state["cognition.assignment_lsa"] == "VERIFIED"
        assert ("installed_package", "acquired", SCIPY) in routes
        assert any(r[1].startswith("networkx: ") for r in routes)          # the same engine, not counted twice
        [verified] = [e.payload for e in body.journal.replay("genesis.verified")]
        card = verified["mechanism"]                                       # the Mechanism Card, as for #144
        assert verified["passed"] and card["mode"] == "DEPEND" and card["distribution"] == "scipy"
        assert len(card["package_digest"]) == 64 and "did not download or install" in card["acquisition"]
        assert body.registry.state[SCIPY] == "VERIFIED"                    # never attached by GREG
        [ask] = attach_asks(body)                                          # exactly one founder ask
        assert len(list(body.journal.replay("decision.requested"))) == 1
        assert not list(body.journal.replay("ask.wording_withheld"))
        [named] = [c for c in ask["evidence"]["registered"] if c["capability_id"] == SCIPY]
        assert named["state"] == "VERIFIED" and named["mechanism"]["qualification"]["failures"] == 0
        state = body.engine.book.missions["m:assign"]
        assert state.blocker["attach_candidates"] == [SCIPY] and state.blocker["request_id"] == ask["request_id"]
        from greg.console import _attachable
        assert [c["capability_id"] for c in _attachable(ask)] == [SCIPY]
        assert not [c for c in compilations(body) if c["state"] == "ANSWERED"]
        body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": SCIPY}))
        assert "ACHIEVED" in [s["state"] for s in ticks(body, clock, 3)]
        answered = [c for c in compilations(body) if c["state"] == "ANSWERED"][-1]
        assert answered["method_or_composition_selected"] == SCIPY
        assert answered["result"]["total"] == A.brute_force({"costs": COSTS}) == 8
        assert answered["result"]["engine"].startswith("scipy ")
        assert len(attach_asks(body)) == 1                                # no further ask
        [closed] = [e.payload for e in body.journal.replay("decision.withdrawn")]
        assert closed["request_id"] == ask["request_id"] and closed["why"].startswith("resolved: ")
        assert ask["request_id"] not in {r["request_id"] for r in body.engine.book.open_requests()}
        # the formed mechanism's answer settles, credited by capability id and pinned package version
        settled = [e.payload for e in body.journal.replay("cognition.settled")]
        assert [(o["method"], o["correct"]) for o in settled] == [(SCIPY, True)]
        assert settled[0]["method_version"] == mechanisms.installed("scipy").version
        assert settled[0]["compile_receipt"] == answered["receipt_id"]
        assert settled[0]["cognitive_receipt"] == answered["selected_receipt"]["receipt_id"]
    with Body(home, clock=clock) as body:                                  # restart: the pinned card holds
        assert body.registry.state[SCIPY] == "ATTACHED"


def test_a_second_mission_reuses_the_qualified_mechanism_and_one_attach_closes_both(tmp_path, index):
    home, key, body_id, _ = make_body(tmp_path)
    geometry = {"geometry": "optimization", "subgeometry": "assignment"}
    drop(home, signed(key, body_id, "MISSION", compile_mission("m:first", geometry, {"costs": COSTS})))
    drop(home, signed(key, body_id, "MISSION", compile_mission("m:second", {"geometry": "optimization"},
                                                                {"costs": [[0.5, 2.25], [1.75, 0.125]],
                                                                 "maximize": True})))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        for _ in range(3):
            body.tick()
            clock.advance(31)
        assert len(list(body.journal.replay("genesis.verified"))) == 1    # qualified once, for the first deficit
        reused = [e.payload for e in body.journal.replay("genesis.route")
                  if e.payload["result"] == "qualified earlier; awaiting the founder's attach"]
        assert [r["capability_id"] for r in reused] == [SCIPY]
        asks = attach_asks(body)                                           # one per mission, never shared across
        assert sorted(a["mission_id"] for a in asks) == ["m:first", "m:second"]
        body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": SCIPY}))
        for _ in range(3):
            body.tick()
            clock.advance(31)
        assert {m: body.engine.book.missions[m].status for m in ("m:first", "m:second")} == \
            {"m:first": "ACHIEVED", "m:second": "ACHIEVED"}
        totals = {c["problem_id"]: c["result"]["total"] for c in compilations(body) if c["state"] == "ANSWERED"}
        assert totals == {"real:m:first": 8, "real:m:second": 4}           # 2.25 + 1.75, off the diagonal


def test_a_deficit_that_fits_a_withheld_genome_names_it_as_the_attach_candidate(tmp_path, index):
    item = library.executables()["queue_erlang"]
    index.write_text(json.dumps({"genomes": {"queue_erlang": {
        "status": "DEFAULT_FOR_GEOMETRY", "version": item.genome.version, "evidence": "results.json#queue_erlang"}},
        "recipes": {}, "routing": {}}))
    home, key, body_id, _ = make_body(tmp_path)
    geometry = {"geometry": item.genome.epistemic_class, "subgeometry": "staffing"}
    drop(home, signed(key, body_id, "MISSION", compile_mission("m:staff", geometry, item.instance(2)[0],
                                                                auto_attach=True)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        assert body.registry.state["cognition.queue_erlang"] == "VERIFIED"
        assert ticks(body, clock, 3)[-1]["state"] in ("BLOCKED", "WAITING")
        routes = [(e.payload["route"], e.payload["result"], e.payload["capability_id"])
                  for e in body.journal.replay("genesis.route")]
        [candidate_route] = [r for r in routes if r[0] == "genome_library"]
        assert candidate_route[1].startswith("attach candidate: cognition.queue_erlang (DEFAULT_FOR_GEOMETRY)")
        assert candidate_route[2] == "cognition.queue_erlang"
        assert ("installed_package", "not searched: a registered intelligence fits this geometry; attaching it is "
                                     "the simpler route", None) in routes
        assert not list(body.journal.replay("genesis.verified"))           # nothing else was qualified
        [awaiting] = [e.payload for e in body.journal.replay("deficit.awaiting_attach")]
        assert awaiting["capability_id"] == "cognition.queue_erlang"
        assert awaiting["admission_status"] == "DEFAULT_FOR_GEOMETRY"
        assert body.registry.state["cognition.queue_erlang"] == "VERIFIED"   # auto_attach does not apply
        state = body.engine.book.missions["m:staff"]
        assert state.blocker["attach_candidates"] == ["cognition.queue_erlang"] and state.blocker["shared_ask"]
        [ask] = attach_asks(body)                                          # the compiler's one ask, shared
        assert ask["request_id"] == state.blocker["request_id"]
        assert ask["authority_requested"]["attach"] == "cognition.queue_erlang"
        body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": "cognition.queue_erlang"}))
        assert "ACHIEVED" in [s["state"] for s in ticks(body, clock, 3)]
        answered = [c for c in compilations(body) if c["state"] == "ANSWERED"][-1]
        assert answered["method_or_composition_selected"] == "cognition.queue_erlang"
        assert len(attach_asks(body)) == 1 and not list(body.journal.replay("decision.withdrawn"))


def test_without_the_compiler_genesis_alone_names_the_withheld_genome_in_the_one_mission_ask(tmp_path, index):
    item = library.executables()["queue_erlang"]
    index.write_text(json.dumps({"genomes": {"queue_erlang": {"status": "NICHE_CAPABILITY",
                                                               "version": item.genome.version}},
                                 "recipes": {}, "routing": {}}))
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        body.apply(signed(key, body_id, "MISSION", compile_mission("m:direct", {"geometry": "prediction"},
                                                                   item.instance(2)[0])))
        body.engine.book.rebuild()
        m = body.engine.book.missions["m:direct"]
        deficit = {"function": "cognition.prediction:staffing", "required_inputs": sorted(item.instance(2)[0]),
                   "geometry": {"geometry": "prediction", "subgeometry": "staffing"}}
        assert body.engine._deficit(m, {"function": deficit["function"]}, clock(), purpose="staffing",
                                    cognition=deficit) is None
        assert body.genesis.attach_candidates("m:direct", deficit["function"]) == ["cognition.queue_erlang"]
        [ask] = attach_asks(body)
        assert ask["mission_id"] == "m:direct" and "shared_ask" not in m.blocker
        from greg.console import _attachable
        assert [c["capability_id"] for c in _attachable(ask)] == ["cognition.queue_erlang"]
        assert any(s["route"] == "genome_library" and "NICHE_CAPABILITY" in s["result"]
                   for s in ask["evidence"]["searched"])
        # frozen negative evidence arriving later, on the same open deficit: the family is reported, no longer offered
        index.write_text(json.dumps({"genomes": {"queue_erlang": {"status": "SUPERSEDED",
                                                                   "version": item.genome.version}},
                                     "recipes": {}, "routing": {}}))
        assert body.genesis.resolve(mission=m, function=deficit["function"], purpose="staffing", now=clock(),
                                    deficit=deficit) is None
        assert len(list(body.journal.replay("deficit.opened"))) == 1          # the same deficit, a new pass
        assert body.genesis.attach_candidates("m:direct", deficit["function"]) == []
        assert body.engine._capability_ask(m, deficit["function"], "staffing")["evidence"]["registered"] == []
        assert any(e.payload["result"] == "cognition.queue_erlang fits but is not a candidate: frozen admission "
                                          "status SUPERSEDED" for e in body.journal.replay("genesis.route"))
        # re-admitted later: offered again on the same deficit
        index.write_text(json.dumps({"genomes": {"queue_erlang": {"status": "NICHE_CAPABILITY",
                                                                   "version": item.genome.version}},
                                     "recipes": {}, "routing": {}}))
        body.genesis.resolve(mission=m, function=deficit["function"], purpose="staffing", now=clock(), deficit=deficit)
        assert body.genesis.attach_candidates("m:direct", deficit["function"]) == ["cognition.queue_erlang"]


# -- review fixes: asks, candidates, the authority guard, the residual record, settlement -------------

def test_a_body_level_ask_the_founder_already_rejected_is_never_shared(tmp_path, index):
    """A rejected or withdrawn body-level ask is closed. A mission sharing it would wait on a closed request that no
    open ask names, so the founder would never be asked about its deficit: it asks on its own instead. A mission that
    shared the ask before the founder answered it takes the answer as its own for what the ask named, and is not asked
    again about it (section 60). An approved ask awaiting its attach is shared (see the approve test below)."""
    item = library.executables()["queue_erlang"]
    index.write_text(json.dumps({"genomes": {"queue_erlang": {"status": "DEFAULT_FOR_GEOMETRY",
                                                               "version": item.genome.version}},
                                 "recipes": {}, "routing": {}}))
    home, key, body_id, _ = make_body(tmp_path)
    geometry = {"geometry": item.genome.epistemic_class, "subgeometry": "staffing"}
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        body.apply(signed(key, body_id, "MISSION", compile_mission("m:first", geometry, item.instance(2)[0])))
        ticks(body, clock, 1)
        [shared] = attach_asks(body)                                       # the compiler's body-level ask
        assert shared["mission_id"] is None
        assert body.engine.book.missions["m:first"].blocker["request_id"] == shared["request_id"]
        body.apply(signed(key, body_id, "DECISION", {"request_id": shared["request_id"], "answer": "reject",
                                                      "reason": "keep it withheld for now"}))
        body.apply(signed(key, body_id, "MISSION", compile_mission("m:staff", geometry, item.instance(3)[0])))
        for _ in range(3):
            body.tick()
            clock.advance(31)
        book = body.engine.book
        open_asks = {r["request_id"]: r for r in book.open_requests()}
        staff = book.missions["m:staff"].blocker                           # arrived after the answer: asks on its own
        assert staff["request_id"] not in book.answers and "shared_ask" not in staff
        assert staff["attach_candidates"] == ["cognition.queue_erlang"]
        assert open_asks[staff["request_id"]]["mission_id"] == "m:staff"
        first = book.missions["m:first"].blocker                           # shared it before: the reject is its answer
        assert first.get("shared_ask") and first["request_id"] == shared["request_id"]
        assert [a["mission_id"] for a in attach_asks(body)] == [None, "m:staff"]   # never asked again for m:first
        assert body.registry.state["cognition.queue_erlang"] == "VERIFIED"


def test_genesis_offers_exactly_what_the_compiler_would_route_and_never_a_relaxation(tmp_path, index):
    """flow_maxflow reads only the edges, source and sink of a capacity-expansion request: the compiler rejects it as
    a relaxation. Offering it would let an attach unblock the mission while the compiler still refuses it."""
    data, _ = library.executables()["flow_expansion_mcf"].instance(1)        # development seed
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", compile_mission(
        "m:expand", {"geometry": "optimization", "subgeometry": "expansion"}, data)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        assert ticks(body, clock, 3)[-1]["state"] in ("BLOCKED", "WAITING")
        rejected = {r["method"]: r["why"] for r in compilations(body)[-1]["methods_rejected"]}
        assert rejected["cognition.flow_maxflow"].startswith("answers a relaxation")
        candidates = body.engine.book.missions["m:expand"].blocker["attach_candidates"]
        assert "cognition.flow_maxflow" not in candidates and "cognition.flow_expansion_mcf" in candidates
        assert any(e.payload["result"].startswith("cognition.flow_maxflow fits but is not a candidate: answers a "
                                                  "relaxation") for e in body.journal.replay("genesis.route"))
        rows = compiler.family_rows(set(data), compiler.CompetencyGeometry(geometry="optimization"),
                                    compiler.evidence_index())
        assert sorted(candidates) == sorted({r["method"] for r in rows if not r["rejected"]
                                             and body.registry.state.get(r["method"]) == "VERIFIED"})


def test_auto_attach_inside_an_admitting_cone_never_attaches_a_mechanism_formed_for_cognition(tmp_path, index):
    home, key, body_id, _ = make_body(tmp_path)
    spec = compile_mission("m:assign", {"geometry": "optimization"}, {"costs": COSTS}, auto_attach=True)
    spec["light_cone"]["capabilities"] = ["cognition.solve", "acquired.*"]     # the cone admits the mechanism
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        assert ticks(body, clock, 3)[-1]["state"] in ("BLOCKED", "WAITING")
        assert body.engine.book.missions["m:assign"].cone._capability_inside(SCIPY)
        assert body.registry.state[SCIPY] == "VERIFIED"
        assert not [e for e in body.journal.replay("capability.state")
                    if e.payload["capability_id"] == SCIPY and e.payload["state"] == "ATTACHED"]
        [awaiting] = [e.payload for e in body.journal.replay("deficit.awaiting_attach")
                      if e.payload["capability_id"] == SCIPY]
        assert awaiting["why"] == "a capability formed for cognition is attached only by the founder's own command"
        assert not [c for c in compilations(body) if c["state"] == "ANSWERED"]


def test_auto_attach_never_attaches_a_withheld_genome_named_directly(tmp_path, index):
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        spec = compile_mission("m:direct", {"geometry": "prediction"}, {"x": 1}, auto_attach=True)
        spec["light_cone"]["capabilities"] = ["cognition.*"]               # the cone admits every genome
        body.apply(signed(key, body_id, "MISSION", spec))
        body.engine.book.rebuild()
        m = body.engine.book.missions["m:direct"]
        assert m.cone._capability_inside("cognition.queue_erlang")
        assert body.registry.state["cognition.queue_erlang"] == "VERIFIED"
        assert body.engine._deficit(m, {"function": "cognition.queue_erlang"}, clock(), purpose="staffing") is None
        assert body.registry.state["cognition.queue_erlang"] == "VERIFIED"
        assert not [e for e in body.journal.replay("capability.state") if e.payload["state"] == "ATTACHED"]
        [awaiting] = [e.payload for e in body.journal.replay("deficit.awaiting_attach")
                      if e.payload["capability_id"] == "cognition.queue_erlang"]
        assert awaiting["why"] == "a capability formed for cognition is attached only by the founder's own command"


def test_the_residual_keeps_the_compilers_geometry_and_every_input(tmp_path, index):
    """Genesis matches the residual exactly as the compiler will: a declared geometry that is not an epistemic class
    matches nothing, and an input is never dropped, whatever its name (beyond the compiler's own count bound the
    residual is matched to nothing)."""
    record = G.cognition_record("cognition.assignment:unspecified",
                                {"required_inputs": ["costs"], "geometry": {"geometry": "assignment"}})
    assert record["geometry"] == "assignment" and G.cognition_mechanisms(record["required_inputs"], "assignment") == []
    undeclared = G.cognition_record("cognition.unknown:unspecified", {"required_inputs": ["costs"], "geometry": {}})
    assert undeclared["geometry"] is None and G.cognition_mechanisms(["costs"], None) == [A.FUNCTION]
    extra = "budget_that_the_total_assignment_cost_must_not_exceed_in_dollars_x"   # 66 characters
    long = G.cognition_record("cognition.optimization:assignment",
                              {"required_inputs": ["costs", extra], "geometry": {"geometry": "optimization"}})
    assert long["inputs_known"] and long["required_inputs"] == sorted(["costs", extra])
    assert G.residual_mechanisms(long) == []                       # SciPy does not read the extra input
    assert G.residual_mechanisms(record) == [] and G.residual_mechanisms(undeclared) == [A.FUNCTION]
    # a receipt keeps a name beyond its text bound as a digest: no mechanism reads it, so none is matched
    digest = G.cognition_record("cognition.optimization:assignment", {
        "required_inputs": ["costs", {"prefix": "x", "truncated": True, "sha256": "0" * 64, "length": 20000}],
        "geometry": {"geometry": "optimization"}})
    assert digest["inputs_known"] and digest["required_inputs"] == ["costs"] and digest["unnamed_inputs"] == 1
    assert G.residual_mechanisms(digest) == []
    beyond = G.cognition_record("cognition.optimization:assignment",
                                {"required_inputs": [f"k{i}" for i in range(G.MAX_INPUTS + 1)],
                                 "geometry": {"geometry": "optimization"}})
    assert not beyond["inputs_known"] and beyond["required_inputs"] == []
    assert "bound of 1000" in beyond["inputs_refused"]["why"]
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", compile_mission("m:class", {"geometry": "assignment"}, {"costs": COSTS})))
    drop(home, signed(key, body_id, "MISSION", compile_mission("m:long", {"geometry": "optimization"},
                                                                {"costs": COSTS, extra: 5})))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        for _ in range(3):
            body.tick()
            clock.advance(31)
        opened = {e.payload["mission_id"]: e.payload["cognition"] for e in body.journal.replay("deficit.opened")}
        assert opened["m:class"]["geometry"] == "assignment" and extra in opened["m:long"]["required_inputs"]
        assert not list(body.journal.replay("genesis.verified")) and SCIPY not in body.registry.state
        for mid in ("m:class", "m:long"):
            blocker = body.engine.book.missions[mid].blocker
            assert blocker["type"] == "capability" and "attach_candidates" not in blocker


@pytest.mark.parametrize("extra", ["x" * 66, ""])
def test_an_extra_input_of_any_name_never_stops_the_compilers_withheld_genome_being_offered(tmp_path, index, extra):
    """A family fits when its native inputs are among the request's, so the compiler fits queue_erlang to a request that
    also carries an input with a long or empty name. Genesis offers the same family on the compiler's own ask, and the
    founder's attach closes the mission; the mission never asks a second time about it."""
    item = library.executables()["queue_erlang"]
    index.write_text(json.dumps({"genomes": {"queue_erlang": {"status": "DEFAULT_FOR_GEOMETRY",
                                                               "version": item.genome.version}},
                                 "recipes": {}, "routing": {}}))
    data = dict(item.instance(2)[0])                                       # development seed
    data[extra] = 5
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", compile_mission(
        "m:staff", {"geometry": item.genome.epistemic_class, "subgeometry": "staffing"}, data)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        assert ticks(body, clock, 3)[-1]["state"] in ("BLOCKED", "WAITING")
        assert compilations(body)[-1]["withheld_best_fit"]["method"] == "cognition.queue_erlang"
        [record] = [e.payload["cognition"] for e in body.journal.replay("deficit.opened")]
        assert record["inputs_known"] and record["required_inputs"] == sorted(data)
        blocker = body.engine.book.missions["m:staff"].blocker
        assert blocker["attach_candidates"] == ["cognition.queue_erlang"] and blocker["shared_ask"]
        [ask] = attach_asks(body)                                          # the compiler's ask, shared
        assert ask["mission_id"] is None and ask["request_id"] == blocker["request_id"]
        body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": "cognition.queue_erlang"}))
        assert "ACHIEVED" in [s["state"] for s in ticks(body, clock, 3)]
        assert len(attach_asks(body)) == 1


@pytest.mark.parametrize("answer", ["approve", "reject"])
def test_the_founders_answer_to_a_shared_ask_is_never_followed_by_another_ask(tmp_path, index, answer):
    """asks.py: approving only records the answer, and attaching is its own signed command. A mission that shares the
    compiler's ask takes the founder's answer as its own, as for its own ask: after an approve it waits for the attach,
    after a reject it is not asked again about what the ask named (section 60). Here the ask names the mission's only
    candidate, so nothing is left to ask about."""
    item = library.executables()["queue_erlang"]
    index.write_text(json.dumps({"genomes": {"queue_erlang": {"status": "DEFAULT_FOR_GEOMETRY",
                                                               "version": item.genome.version}},
                                 "recipes": {}, "routing": {}}))
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", compile_mission(
        "m:staff", {"geometry": item.genome.epistemic_class, "subgeometry": "staffing"}, item.instance(2)[0])))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        ticks(body, clock, 2)
        [ask] = attach_asks(body)
        blocker = body.engine.book.missions["m:staff"].blocker
        assert blocker["shared_ask"] and blocker["request_id"] == ask["request_id"]
        body.apply(signed(key, body_id, "DECISION", {"request_id": ask["request_id"], "answer": answer,
                                                      "reason": "the founder's answer"}))
        assert [s["state"] for s in ticks(body, clock, 3)] == ["WAITING"] * 3
        assert len(attach_asks(body)) == 1 and body.engine.book.open_requests() == []
        assert body.engine.book.missions["m:staff"].blocker == blocker
        if answer == "approve":
            body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": "cognition.queue_erlang"}))
            assert "ACHIEVED" in [s["state"] for s in ticks(body, clock, 3)]
            assert len(attach_asks(body)) == 1


def test_a_shared_ask_withdrawn_unanswered_is_asked_about_on_the_missions_own(tmp_path, index):
    """The founder never decided a shared ask that was withdrawn unanswered: the mission's need is asked about once."""
    item = library.executables()["queue_erlang"]
    index.write_text(json.dumps({"genomes": {"queue_erlang": {"status": "DEFAULT_FOR_GEOMETRY",
                                                               "version": item.genome.version}},
                                 "recipes": {}, "routing": {}}))
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", compile_mission(
        "m:staff", {"geometry": item.genome.epistemic_class, "subgeometry": "staffing"}, item.instance(2)[0])))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        ticks(body, clock, 2)
        [ask] = attach_asks(body)
        body.journal.record("decision.withdrawn", {"request_id": ask["request_id"], "mission_id": None,
                                                   "why": "withdrawn by the body", "evidence": [], "at": "2026-01-01"},
                            key=[ask["request_id"], "withdrawn"])
        ticks(body, clock, 2)
        blocker = body.engine.book.missions["m:staff"].blocker
        assert "shared_ask" not in blocker and blocker["attach_candidates"] == ["cognition.queue_erlang"]
        assert [r["mission_id"] for r in body.engine.book.open_requests()] == ["m:staff"]
        assert [a["mission_id"] for a in attach_asks(body)] == [None, "m:staff"]


@pytest.mark.parametrize("answer", ["approve", "reject"])
def test_a_rejected_shared_ask_decides_only_what_it_named_and_the_rest_is_asked_about_once(tmp_path, index, answer):
    """The compiler's ask names only its best fit, while the mission's blocker keeps every candidate Genesis found.
    The founder's reject decides exactly what that ask named: none of it is asked about again for this need (section
    60), and the candidates it did not name, never put to the founder, are asked about once on the mission's own ask.
    The founder's answer to that ask is final in turn: an approve waits for the attach, a reject is not followed by
    another ask."""
    from greg.console import _attachable
    data, _ = library.executables()["dp_knapsack"].instance(2)               # development seed
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", compile_mission("m:pack", {"geometry": "optimization"}, data)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        ticks(body, clock, 3)
        blocker = body.engine.book.missions["m:pack"].blocker
        [shared] = attach_asks(body)
        assert blocker["shared_ask"] and blocker["request_id"] == shared["request_id"]
        named = shared["authority_requested"]["attach"]
        assert [c["capability_id"] for c in _attachable(shared)] == [named]
        [other] = [c for c in blocker["attach_candidates"] if c != named]
        body.apply(signed(key, body_id, "DECISION", {"request_id": shared["request_id"], "answer": "reject",
                                                      "reason": "keep it withheld"}))
        ticks(body, clock, 2)
        book = body.engine.book
        [own] = book.open_requests()
        assert own["mission_id"] == "m:pack" and own["kind"] == "CAPABILITY_ATTACH"
        assert [c["capability_id"] for c in _attachable(own)] == [other]   # never the candidate just rejected
        assert own["evidence"]["already_answered"] == [{"capability_id": named, "request_id": shared["request_id"],
                                                        "answer": "reject"}]
        blocker = book.missions["m:pack"].blocker
        assert "shared_ask" not in blocker and blocker["request_id"] == own["request_id"]
        assert sorted(blocker["attach_candidates"]) == sorted([named, other])   # an attach of either resolves it
        body.apply(signed(key, body_id, "DECISION", {"request_id": own["request_id"], "answer": answer,
                                                      "reason": "the founder's answer"}))
        assert [s["state"] for s in ticks(body, clock, 3)] == ["WAITING"] * 3
        assert len(attach_asks(body)) == 2 and body.engine.book.open_requests() == []
        if answer == "approve":
            body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": other}))
            assert "ACHIEVED" in [s["state"] for s in ticks(body, clock, 3)]
            assert len(attach_asks(body)) == 2


def test_an_approved_ask_awaiting_its_attach_is_shared_by_a_mission_that_arrives_after_the_approve(tmp_path, index):
    """An approve is the founder's yes to the attach it names; the signed attach then resolves every mission waiting on
    it. A mission with the same need that arrives between the approve and the attach waits on that ask too, instead of
    asking the founder about the attach just approved. A rejected ask is still never shared."""
    item = library.executables()["queue_erlang"]
    index.write_text(json.dumps({"genomes": {"queue_erlang": {"status": "DEFAULT_FOR_GEOMETRY",
                                                               "version": item.genome.version}},
                                 "recipes": {}, "routing": {}}))
    home, key, body_id, _ = make_body(tmp_path)
    geometry = {"geometry": item.genome.epistemic_class, "subgeometry": "staffing"}
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        body.apply(signed(key, body_id, "MISSION", compile_mission("m:first", geometry, item.instance(2)[0])))
        ticks(body, clock, 2)
        [ask] = attach_asks(body)
        body.apply(signed(key, body_id, "DECISION", {"request_id": ask["request_id"], "answer": "approve",
                                                      "reason": "yes, attach it"}))
        body.apply(signed(key, body_id, "MISSION", compile_mission("m:second", geometry, item.instance(3)[0])))
        for _ in range(3):
            body.tick()
            clock.advance(31)
        book = body.engine.book
        second = book.missions["m:second"].blocker
        assert second["shared_ask"] and second["request_id"] == ask["request_id"]
        assert second["attach_candidates"] == ["cognition.queue_erlang"]
        assert len(attach_asks(body)) == 1 and book.open_requests() == []
        body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": "cognition.queue_erlang"}))
        states = {}
        for _ in range(3):
            states.update({s["mission_id"]: s["state"] for s in body.tick()["missions"]})
            clock.advance(31)
        assert states == {"m:first": "ACHIEVED", "m:second": "ACHIEVED"}
        assert len(attach_asks(body)) == 1 and not list(body.journal.replay("decision.withdrawn"))


@pytest.mark.parametrize("answer", ["approve", "reject"])
def test_a_founder_detach_decides_a_candidate_and_an_approve_stands_only_while_its_candidate_is_withheld(
        tmp_path, index, answer):
    """A founder detach of a withheld candidate is a decision against it, as a reject is. After a reject of the shared
    ask and a detach of the other candidate, nothing is left undecided: the mission waits and is never asked again
    (section 60). An approve stands only while the candidate it named can still be attached by it: once the founder
    detaches that candidate instead, the candidate never put to the founder is asked about once, alone, and an attach
    of the detached one still resolves the mission."""
    from greg.console import _attachable
    data, _ = library.executables()["dp_knapsack"].instance(2)               # development seed
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", compile_mission("m:pack", {"geometry": "optimization"}, data)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        ticks(body, clock, 3)
        [shared] = attach_asks(body)
        named = shared["authority_requested"]["attach"]
        [other] = [c for c in body.engine.book.missions["m:pack"].blocker["attach_candidates"] if c != named]
        body.apply(signed(key, body_id, "DECISION", {"request_id": shared["request_id"], "answer": answer,
                                                      "reason": "the founder's answer"}))
        detached = named if answer == "approve" else other
        body.apply(signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": detached}))
        ticks(body, clock, 3)
    with Body(home, clock=clock) as body:                                    # the decision survives a restart
        body.boot()
        assert [s["state"] for s in ticks(body, clock, 2)] == ["WAITING"] * 2
        book = body.engine.book
        if answer == "reject":
            assert len(attach_asks(body)) == 1 and book.open_requests() == []
            assert book.missions["m:pack"].blocker["request_id"] == shared["request_id"]
            return
        [own] = book.open_requests()
        assert own["mission_id"] == "m:pack" and [c["capability_id"] for c in _attachable(own)] == [other]
        assert len(attach_asks(body)) == 2
        blocker = book.missions["m:pack"].blocker
        assert blocker["request_id"] == own["request_id"]
        assert sorted(blocker["attach_candidates"]) == sorted([named, other])
        body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": named}))   # the founder relents
        assert "ACHIEVED" in [s["state"] for s in ticks(body, clock, 3)]
        assert [e.payload["request_id"] for e in body.journal.replay("decision.withdrawn")] == [own["request_id"]]


def test_a_founder_detach_of_what_an_open_shared_ask_named_lapses_it_for_the_waiting_mission(tmp_path, index):
    """A founder detach of the candidate an open shared ask names decides that candidate without an answer to the ask.
    The ask then no longer stands for the mission's need, just as a mission arriving now would not share it: the
    waiting mission is asked once, on its own ask, about the candidate never put to the founder, the same as a new
    mission with the same need. The compiler's ask stays open for its own use, and one attach resolves both missions."""
    from greg.console import _attachable
    dp = library.executables()["dp_knapsack"]
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", compile_mission("m:pack", {"geometry": "optimization"},
                                                               dp.instance(2)[0])))     # development seed
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        ticks(body, clock, 3)
        [shared] = attach_asks(body)
        named = shared["authority_requested"]["attach"]
        [other] = [c for c in body.engine.book.missions["m:pack"].blocker["attach_candidates"] if c != named]
        body.apply(signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": named}))   # the ask is not answered
        ticks(body, clock, 3)
    with Body(home, clock=clock) as body:                                    # the lapse survives a restart
        body.boot()
        ticks(body, clock, 2)
        book = body.engine.book
        assert shared["request_id"] not in book.answers and shared["request_id"] not in book.withdrawn
        [own] = [r for r in book.open_requests() if r["mission_id"] == "m:pack"]
        assert [c["capability_id"] for c in _attachable(own)] == [other]   # never the candidate just detached
        blocker = book.missions["m:pack"].blocker
        assert "shared_ask" not in blocker and blocker["request_id"] == own["request_id"]
        assert sorted(blocker["attach_candidates"]) == sorted([named, other])   # an attach of either resolves it
        assert len(attach_asks(body)) == 2
        body.apply(signed(key, body_id, "MISSION", compile_mission("m:pack2", {"geometry": "optimization"},
                                                                   dp.instance(3)[0])))  # development seed
        for _ in range(3):
            body.tick()
            clock.advance(31)
        book = body.engine.book
        [second] = [r for r in book.open_requests() if r["mission_id"] == "m:pack2"]
        assert [c["capability_id"] for c in _attachable(second)] == [other]   # the same treatment as m:pack
        assert len(attach_asks(body)) == 3
        body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": other}))
        states = {}
        for _ in range(3):
            states.update({s["mission_id"]: s["state"] for s in body.tick()["missions"]})
            clock.advance(31)
        assert states == {"m:pack": "ACHIEVED", "m:pack2": "ACHIEVED"}
        assert sorted(e.payload["request_id"] for e in body.journal.replay("decision.withdrawn")) == sorted(
            [own["request_id"], second["request_id"]])


@pytest.mark.parametrize("acts", [
    (), ("approve",), ("reject",), ("withdraw",), ("detach named",), ("detach other",),
    ("detach named", "detach other"), ("approve", "detach named"), ("approve", "detach other"),
    ("reject", "detach other"), ("reject", "detach named"), ("withdraw", "detach named"),
    ("detach named", "approve"), ("detach named", "reject"), ("detach other", "reject")])
def test_a_mission_with_an_undecided_candidate_only_ever_waits_on_an_ask_that_stands(tmp_path, index, acts):
    """The rule for the whole class, over orders of founder acts on the shared ask and on the candidates, each followed
    by ticks. A candidate is decided by a founder detach, or by the founder's reject of an ask the mission waited on
    that named it. While a candidate is undecided, the mission waits on an ask that names one and that the founder can
    still answer or has approved. No ask offers a candidate already decided. The rest of the need is asked about at
    most once, and nothing is asked once every candidate is decided (section 60)."""
    from greg.console import _attachable
    data, _ = library.executables()["dp_knapsack"].instance(2)               # development seed
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", compile_mission("m:pack", {"geometry": "optimization"}, data)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        ticks(body, clock, 3)
        [shared] = attach_asks(body)
        named = shared["authority_requested"]["attach"]
        [other] = [c for c in body.engine.book.missions["m:pack"].blocker["attach_candidates"] if c != named]
        undecided, seen = {named, other}, {shared["request_id"]}
        for act in acts:
            if act in ("approve", "reject"):
                body.apply(signed(key, body_id, "DECISION", {"request_id": shared["request_id"], "answer": act,
                                                              "reason": "the founder's answer"}))
                undecided -= {named} if act == "reject" else set()
            elif act == "withdraw":
                body.journal.record("decision.withdrawn", {"request_id": shared["request_id"], "mission_id": None,
                                                           "why": "withdrawn by the body", "evidence": [],
                                                           "at": "2026-01-01"}, key=[shared["request_id"], "withdrawn"])
            else:
                detached = named if act == "detach named" else other
                body.apply(signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": detached}))
                undecided -= {detached}
            ticks(body, clock, 3)
            for ask in attach_asks(body):
                if ask["request_id"] not in seen:
                    seen.add(ask["request_id"])
                    offered = {c["capability_id"] for c in _attachable(ask)}
                    assert ask["mission_id"] == "m:pack" and offered and offered <= undecided, (act, offered)
        assert len(seen) <= 2                                                # the rest is asked about once
        book = body.engine.book
        rid = book.missions["m:pack"].blocker["request_id"]
        stands = rid not in book.withdrawn and (book.answers.get(rid) or {}).get("answer") in (None, "approve") \
            and bool({c["capability_id"] for c in _attachable(book.requests[rid])} & undecided)
        assert stands or not undecided, (rid, undecided)


def test_several_withheld_genomes_fit_and_the_founder_is_asked_once(tmp_path, index):
    data, _ = library.executables()["dp_knapsack"].instance(2)               # development seed
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", compile_mission("m:pack", {"geometry": "optimization"}, data)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        assert ticks(body, clock, 3)[-1]["state"] in ("BLOCKED", "WAITING")
        blocker = body.engine.book.missions["m:pack"].blocker
        assert blocker["attach_candidates"] == ["cognition.dp_knapsack", "cognition.knapsack_bnb"]
        [ask] = attach_asks(body)                                          # the compiler's ask, shared
        assert blocker["shared_ask"] and blocker["request_id"] == ask["request_id"]
        assert ask["authority_requested"]["attach"] in blocker["attach_candidates"]
        body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": ask["authority_requested"]["attach"]}))
        assert "ACHIEVED" in [s["state"] for s in ticks(body, clock, 3)]
        assert len(attach_asks(body)) == 1


def test_a_formed_answer_carries_its_own_receipt_and_poor_settled_outcomes_demote_it(tmp_path, monkeypatch, index):
    from greg.cognition import settlement
    registry = attached_registry(tmp_path)
    request = {"geometry": {"geometry": "optimization"}, "data": {"costs": COSTS}}
    r = reason({"problem_id": "assign", "compile": request}, registry=registry)
    inner = r["selected_receipt"]
    assert inner["method"] == SCIPY and inner["method_version"] == mechanisms.installed("scipy").version
    assert r["intermediate_receipts"] == [inner["receipt_id"]] and settlement._valid_receipt(inner)
    assert inner["evaluator_result"]["verdict"] == "STRUCTURALLY_VERIFIED" and inner["output"] == r["result"]
    assert inner["abstention_state"] == "NONE" and settlement._compiled(r) is r
    # credited only as the identity Genesis's registration pinned, never through BUILTINS
    assert settlement._known_method(inner, r, {}, {(SCIPY, inner["method_version"])})
    assert not settlement._known_method(inner, r, {}, set())
    assert not settlement._known_method(inner, r, {}, {(SCIPY, "0.0.0")})
    # live negative evidence demotes it, never deletes it: nothing else fits, so it still serves, with dissent
    monkeypatch.setattr(compiler, "_settled_counts", lambda journal: {SCIPY: (12, 1)})
    demoted = reason({"problem_id": "assign", "compile": request}, registry=registry)
    assert demoted["state"] == "ANSWERED" and demoted["method_or_composition_selected"] == SCIPY
    assert [d["method"] for d in demoted["methods_demoted"]] == [SCIPY]
    assert any(d.startswith(f"{SCIPY}: settled outcomes on this body: 1 of 12") for d in demoted["dissent"])
