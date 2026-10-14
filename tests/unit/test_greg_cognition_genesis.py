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
        assert ("genome_library", "no registered intelligence has this geometry and these inputs", None) in routes
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
        # frozen negative evidence: a superseded family is reported, never offered
        index.write_text(json.dumps({"genomes": {"queue_erlang": {"status": "SUPERSEDED",
                                                                   "version": item.genome.version}},
                                     "recipes": {}, "routing": {}}))
        other = body.genesis.resolve(mission=m, function="cognition.prediction:queue", purpose="queue", now=clock(),
                                     deficit={**deficit, "function": "cognition.prediction:queue"})
        assert other is None
        assert body.genesis.attach_candidates("m:direct", "cognition.prediction:queue") == []
        assert any(e.payload["result"] == "cognition.queue_erlang fits but is not a candidate: frozen admission "
                                          "status SUPERSEDED" for e in body.journal.replay("genesis.route"))
