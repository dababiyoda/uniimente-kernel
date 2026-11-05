"""The appraiser re-reads a compiled cognition receipt with the method, version and route the receipt names.

Ported from unit B onto #243's one pin channel (``greg.cognition.replay``: the appraiser binds the receipt's pin in a
context variable around the ordinary adapter call; ``compiler.run`` reads it once). There is no ``pin=`` parameter.

Directive part 2 section 8 (prove learning). The appraiser used to re-observe a ``cognition.*`` compile by running
current learned routing in its own process. Once a condition preference fired, a failure closure by the incumbent was
re-read with the alternative and REFUTED; a success the alternative served was re-read with the incumbent and
REFUTED; and the appraiser ran inert shadow trials. Either way the paired evidence learning needs never settled.

Requests use the condition hook test's disclosed pilot generator at seed 0 (rosenbrock, 12 dimensions: the
incumbent reaches fitness about 9.2, the alternative about 0.17). No stress or holdout seed of any experiment is
generated here. The alternative's own native catalog route uses a fixed 5-dimension request (``NATIVE``).
"""
from __future__ import annotations

from dataclasses import replace
import json
import random

import pytest

from greg import appraisal
from greg.body import Body
from greg.cognition import condition_competence as cc
from greg.cognition import replay
from greg.cognition.contracts import digest
from tests.greg_fixtures import Clock, drop, make_body, mission, signed

FIRED_COUNTS = {"pairs": 6, "alternative_only": 6, "incumbent_only": 0}
FIRED = {"optimization|d11-30": FIRED_COUNTS}
FITNESS = {"op": "lte", "field": "result.fitness", "value": 1.0}
# the alternative's native input shape: its own catalog route answers it (selection level admission_status)
NATIVE = {"objective": "rosenbrock", "dimension": 5, "lower": -5.12, "upper": 5.12,
          "shift": [0.1, 0.2, 0.3, 0.4, 0.5], "evaluations": 1500, "seed": 0}


def _request(d=12, seed=0):
    rnd = random.Random(seed)
    return {"function": "rosenbrock", "shift": [round(rnd.uniform(-2, 2), 3) for _ in range(d)],
            "bounds": [[-5.12, 5.12]] * d, "budget": 300 * d, "seed": seed}


# both input shapes in one request, naming different objectives (catalog: rosenbrock; native: sphere)
BOTH = {**_request(5), "objective": "sphere", "dimension": 5, "lower": -5.12, "upper": 5.12, "evaluations": 1500}


def _spec(mid, data=None, predicate=FITNESS, consequence=None):
    compile_ = {"geometry": {"geometry": "optimization"}, "data": data or _request(),
                **({"consequence": consequence} if consequence else {})}
    params = {"problem_id": f"real:{mid}", "compile": compile_}
    return mission(mid, checks=[{
        "check_id": "good", "description": "the compile's answer",
        "sensor": {"capability": "cognition.solve", "target": "cognition:bb", "params": params},
        "predicate": predicate}],
        strategies=[{"action_id": "compile", "capability": "cognition.solve", "target": "cognition:bb",
                     "params": params, "advances": ["good"], "rationale": "minimise"}],
        capabilities=["cognition.solve"], targets=("cognition:*",), ceiling="read_only")


UNAVAILABLE = "receipt method unavailable"


def _pinned_run(params, registry, pin):
    """A compile under a bound replay pin: the one channel the appraiser uses."""
    from greg.cognition import compiler
    token = replay.bind(pin)
    try:
        return compiler.run(params, registry=registry)
    finally:
        replay.reset(token)


def _pin(method, version, selection, params):
    return {"method": method, "version": version, "route": {"kind": "compiler", "selection": selection},
            "inputs_digest": digest(params)}


def _refused(findings):
    """The re-read was refused, not judged: #209's unmeasured finding, carrying #243's wording."""
    return bool(findings) and all(f.partition(": ")[2].startswith("the world could not be re-measured (")
                                  and UNAVAILABLE in f for f in findings)


def _run(tmp, mid, *, engine_fired=False, native_demoted=False, **spec):
    """A body that compiles the mission and closes it. ``engine_fired`` fires the cell preference (in the request's
    own cell) in this (the engine's) process only, as an experiment harness does: the body's own appraiser subprocess
    reads none. ``native_demoted`` stands, in the engine's process only, for ten settled failures of the alternative
    on this body, so its native row ranks below the incumbent and the hook can switch a request carrying both shapes."""
    home, key, body_id, _ = make_body(tmp)
    clock = Clock()
    body = Body(home, clock=clock).open()
    body.boot()
    for cid in ("cognition.swarm", "cognition.blackbox", cc.ALTERNATIVE):
        body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": cid}))
    with pytest.MonkeyPatch.context() as mp:
        if engine_fired:
            cell = cc.condition_key("optimization", spec.get("data") or _request())
            mp.setattr(cc, "evidence_from", lambda journal: {cell: FIRED_COUNTS})
        if native_demoted:
            from greg.cognition import compiler
            mp.setattr(compiler, "_settled_counts", lambda journal: {cc.ALTERNATIVE: (10, 0)})
        body.apply(signed(key, body_id, "MISSION", _spec(mid, **spec)))
        for _ in range(5):
            body.tick()
            clock.advance(31)
    return body


def _compiled(body, mid):
    observed = [e.payload for e in body.journal.replay("mission.observed") if e.payload["mission_id"] == mid]
    return body.ledger.find(observed[-1]["receipt"]).payload["result"]["output"]


def _verdicts(body):
    return [e.payload["verdict"] for e in body.journal.replay("mission.appraised")]


@pytest.fixture(scope="module")
def failed(tmp_path_factory):
    """The incumbent's failure closure, appraised VERIFIED_UNMET by the body's own appraiser; yields the request
    for re-appraising that closure in this process."""
    body = _run(tmp_path_factory.mktemp("failed"), "m:disc")
    try:
        receipt = _compiled(body, "m:disc")
        assert receipt["method_or_composition_selected"] == cc.INCUMBENT and receipt["result"]["fitness"] > 1.0
        assert _verdicts(body) == ["VERIFIED_UNMET"]
        [closure] = [e.event_id for e in body.journal.replay("mission.unmet") if e.payload["mission_id"] == "m:disc"]
        yield body.appraisal_request("m:disc", closure_event=closure)
    finally:
        body.close()


def test_a_failure_closure_stays_confirmed_after_the_cell_preference_fires(failed, monkeypatch):
    monkeypatch.setattr(cc, "evidence_from", lambda journal: FIRED)
    verdict = appraisal.appraise(failed)
    assert (verdict["verdict"], verdict["findings"]) == ("VERIFIED_UNMET", [])


@pytest.fixture(scope="module")
def served(tmp_path_factory):
    """The alternative's success, served on the cell preference's route because the engine's process saw the fired
    preference; the body's own appraiser subprocess sees none. Assertions on it are the tests' own."""
    body = _run(tmp_path_factory.mktemp("served"), "m:rev", engine_fired=True)
    try:
        yield body
    finally:
        body.close()


def test_a_success_the_preferred_alternative_served_is_verified_by_the_bodys_own_appraiser(served, monkeypatch):
    receipt = _compiled(served, "m:rev")
    assert receipt["method_or_composition_selected"] == cc.ALTERNATIVE and receipt["result"]["fitness"] <= 1.0
    assert receipt["selection_level"] == "preferred_by_condition_evidence"
    assert _verdicts(served) == ["VERIFIED"]
    # the re-read runs the alternative only while the compile path itself could: admitted and attached
    monkeypatch.setattr(cc, "_admitted", lambda: False)
    assert appraisal.appraise(served.appraisal_request("m:rev"))["verdict"] != "VERIFIED"


def test_a_success_the_preferred_alternative_served_is_not_re_read_once_it_is_detached(served, monkeypatch):
    """Detached since the receipt (admission unchanged): the pinned re-read never offers the alternative's row, so
    no solver is asked for it, and the closure is not confirmed."""
    from greg.cognition import cortex
    retained, asked, real = appraisal._formed_registry, [], cortex.reason

    def detached(journal, workspace):
        registry = retained(journal, workspace)
        registry.set_state(cc.ALTERNATIVE, "DETACHED")
        return registry

    monkeypatch.setattr(appraisal, "_formed_registry", detached)
    # the adapter enters cortex.reason with the compile itself; only a solver call names an operation
    monkeypatch.setattr(cortex, "reason", lambda params, **kw: ("operation" in params and asked.append(
        params["operation"])) or real(params, **kw))
    verdict = appraisal.appraise(served.appraisal_request("m:rev"))
    assert verdict["verdict"] != "VERIFIED"
    assert _refused(verdict["findings"]), verdict["findings"]
    assert asked == []


def test_a_refused_pinned_re_read_reads_as_unmeasured_not_as_a_changed_world(served, monkeypatch):
    """A pin the registry can no longer honour (the alternative's admission withdrawn since the receipt) measured
    nothing: the finding says the world could not be re-measured, never that it no longer matches, and the closure
    is still not confirmed."""
    monkeypatch.setattr(cc, "_admitted", lambda: False)
    verdict = appraisal.appraise(served.appraisal_request("m:rev"))
    assert verdict["verdict"] != "VERIFIED"
    assert len(verdict["findings"]) == 1 and _refused(verdict["findings"]), verdict["findings"]


def test_the_appraiser_runs_no_shadow_trial_when_one_is_due_in_its_view(failed, monkeypatch):
    trials = []
    real = cc.shadow_trial
    monkeypatch.setattr(cc, "evidence_from", lambda journal: {})
    monkeypatch.setattr(cc, "incumbent_unmet", lambda journal, cell, exclude_problem=None: 1)
    monkeypatch.setattr(cc, "pairs_from", lambda journal: [])
    monkeypatch.setattr(cc, "shadow_trial", lambda data: trials.append(1) or real(data))
    assert appraisal.appraise(failed)["verdict"] == "VERIFIED_UNMET"
    assert trials == []


@pytest.mark.parametrize("change", ["version", "detached"])
def test_a_failure_whose_method_changed_since_the_receipt_is_never_confirmed(failed, monkeypatch, change):
    """The receipt's method re-versioned or detached since: the closure cannot be re-measured, so it is not
    confirmed by whatever routing serves the request now."""
    retained = appraisal._formed_registry

    def changed(journal, workspace):
        registry = retained(journal, workspace)
        if change == "version":
            registry.manifests[cc.INCUMBENT] = replace(registry.manifests[cc.INCUMBENT], version="9.9.9")
        else:
            registry.set_state(cc.INCUMBENT, "DETACHED")
        return registry

    monkeypatch.setattr(appraisal, "_formed_registry", changed)
    verdict = appraisal.appraise(failed)
    assert verdict["verdict"] != "VERIFIED_UNMET"
    assert _refused(verdict["findings"]), verdict["findings"]


def test_a_re_read_of_other_inputs_than_the_receipt_answered_is_refused(failed, monkeypatch):
    """A handoff resolved now (not as of the dispatch) that differs from what the receipt answered."""
    from greg import pipeline
    real = pipeline.resolve

    def moved(params, journal, mission_id, **kw):
        bound, rest = real(params, journal, mission_id, **kw)
        if "before_seq" not in kw:                       # the re-read's live resolve, never the binding check's
            bound = {**bound, "problem_id": bound["problem_id"] + ":moved"}
        return bound, rest

    monkeypatch.setattr(pipeline, "resolve", moved)
    verdict = appraisal.appraise(failed)
    assert verdict["verdict"] != "VERIFIED_UNMET"
    assert any(f.endswith("(ValueError)") for f in verdict["findings"])


def test_a_pinned_compile_at_another_registered_version_raises_before_any_solver_runs(monkeypatch):
    from greg.cognition import cortex
    from greg.cognition.contracts import CognitionError
    registry = cortex.registry_view(None)
    for cid in ("cognition.swarm", "cognition.blackbox"):
        registry.set_state(cid, "ATTACHED")
    params = {"problem_id": "pin", "compile": {"geometry": {"geometry": "optimization"}, "data": _request()}}
    pin = _pin(cc.INCUMBENT, registry.manifests[cc.INCUMBENT].version, "admission_status", params)
    registry.manifests[cc.INCUMBENT] = replace(registry.manifests[cc.INCUMBENT], version="9.9.9")
    monkeypatch.setattr(cortex, "reason", lambda *a, **k: pytest.fail("a solver ran"))
    with pytest.raises(CognitionError, match=UNAVAILABLE):
        _pinned_run(params, registry, pin)


def test_routing_changed_since_the_receipt_never_changes_which_method_a_pinned_compile_runs(monkeypatch):
    """Here another fit was admitted since the receipt, so current routing serves it first; the pin still names
    the receipt's method (planned only: no solver runs)."""
    from greg.cognition import compiler, cortex
    index = compiler.evidence_index()
    index["operations"]["blackbox"] = {**index["operations"]["blackbox"], "status": "DEFAULT_FOR_GEOMETRY",
                                       "raw_status": "DEFAULT_FOR_GEOMETRY"}
    monkeypatch.setattr(compiler, "evidence_index", lambda path=None: index)
    registry = cortex.registry_view(None)
    for cid in ("cognition.swarm", "cognition.blackbox"):
        registry.set_state(cid, "ATTACHED")
    params = {"problem_id": "pin", "compile": {"geometry": {"geometry": "optimization"}, "data": _request(),
                                               "execute": False}}
    assert compiler.run(params, registry=registry)["method_or_composition_selected"] == "cognition.blackbox"
    pin = _pin(cc.INCUMBENT, registry.manifests[cc.INCUMBENT].version, "admission_status", params)
    assert _pinned_run(params, registry, pin)["method_or_composition_selected"] == cc.INCUMBENT


@pytest.mark.parametrize("ran, replayed", [
    ({"method_or_composition_selected": None, "state": "CAPABILITY_DEFICIT"}, False),
    ({"method_or_composition_selected": cc.INCUMBENT, "state": "ANSWERED",
      "selected_receipt": {"method": cc.INCUMBENT, "method_version": "9.9.9"}}, False),
    ({"method_or_composition_selected": cc.ALTERNATIVE, "state": "ANSWERED",
      "selected_receipt": {"method": cc.ALTERNATIVE, "method_version": "0.2.0"}}, False),
    ({"method_or_composition_selected": cc.INCUMBENT, "state": "ANSWERED",
      "selected_receipt": {"method": cc.INCUMBENT, "method_version": "0.2.0"}}, True)],
    ids=["ran0-deficit", "ran1-version", "ran2-method", "ran3-same"])
def test_a_re_read_that_did_not_run_the_pinned_method_at_its_version_is_not_a_replay(ran, replayed):
    """The appraiser's postcondition (#243's ``replay.matches``): a compile that left a deficit, or ran another
    version or another method, did not re-read the receipt; only the same method at the same version does."""
    from greg.cognition import compiler
    params = {"problem_id": "pin", "compile": {"geometry": {"geometry": "optimization"}, "data": _request()}}
    pin = _pin(cc.INCUMBENT, "0.2.0", "admission_status", params)
    out = {"schema": compiler.SCHEMA, "inputs_digest": digest(params), "selection_level": "admission_status",
           "selected_receipt": None, "replay": {"learned_routing": False, "shadows": False}, **ran}
    assert replay.matches(out, pin) is replayed
    # a compile that says it consulted learned routing, or ran a shadow, is no replay whatever it ran
    for flag in ("learned_routing", "shadows"):
        assert replay.matches({**out, "replay": {**out["replay"], flag: True}}, pin) is False


def test_a_pinned_re_read_requires_the_signed_cognition_target(tmp_path, monkeypatch):
    from greg.capabilities import BUILTINS, CapabilityError, InvocationContext
    from greg.cognition import compiler, cortex
    monkeypatch.setattr(compiler, "run", lambda params, **kw: pytest.fail("a compile ran"))
    ctx = InvocationContext(workspace=tmp_path, read_roots=(), secrets=None, manifest=BUILTINS["cognition.solve"][0],
                            target="fs:notes", capability_registry=cortex.registry_view(None))
    params = {"problem_id": "pin", "compile": {}}
    token = replay.bind(_pin(cc.INCUMBENT, "0.2.0", "admission_status", params))
    try:
        with pytest.raises(CapabilityError, match="signed bounded target"):
            cortex.solve(params, ctx)
    finally:
        replay.reset(token)


def test_a_formed_mechanism_compile_closure_is_still_re_read_and_verified(tmp_path, monkeypatch):
    """Regression guard: a receipt a Genesis-formed mechanism answered records the package version, not the
    manifest's, and the pinned re-read must find it by that version."""
    pytest.importorskip("scipy")
    pytest.importorskip("ortools")
    from greg.cognition import compiler
    import tests.unit.test_greg_cognition_genesis as genesis_test
    index = tmp_path / "index.json"
    index.write_text(json.dumps({"genomes": {}, "recipes": {}, "routing": {}}))
    monkeypatch.setattr(compiler, "EVIDENCE_INDEX", index)
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", genesis_test.compile_mission(
        "m:formed", {"geometry": "optimization", "subgeometry": "assignment"}, {"costs": genesis_test.COSTS})))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        for attach in (False, True):
            if attach:
                body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": genesis_test.SCIPY}))
            for _ in range(3):
                body.tick()
                clock.advance(31)
        receipt = _compiled(body, "m:formed")
        assert receipt["selection_level"] == "formed_by_capability_genesis"
        assert receipt["selected_receipt"]["method_version"] != body.registry.manifests[genesis_test.SCIPY].version
        assert _verdicts(body) == ["VERIFIED"]
        assert appraisal.appraise(body.appraisal_request("m:formed"))["verdict"] == "VERIFIED"
        # the same mechanism at another package version is not the receipt's route: refused, never re-routed
        from greg import genesis
        real = genesis.formed_cognition

        def repackaged(registry, data, geometry):
            return [(replace(m, provenance={**m.provenance, "version": "0.0.0-other"}), a)
                    for m, a in real(registry, data, geometry)]

        monkeypatch.setattr(genesis, "formed_cognition", repackaged)
        verdict = appraisal.appraise(body.appraisal_request("m:formed"))
        assert verdict["verdict"] != "VERIFIED" and _refused(verdict["findings"]), verdict["findings"]


def test_a_success_the_alternative_answered_on_its_native_route_is_verified(tmp_path):
    """The alternative's own catalog route (its native fields, selection level admission_status) is re-read on that
    route: never through the condition preference's adapter, which cannot read these fields."""
    body = _run(tmp_path, "m:native", data=NATIVE, predicate={"op": "lte", "field": "result.value", "value": 1.0})
    try:
        receipt = _compiled(body, "m:native")
        assert (receipt["state"], receipt["method_or_composition_selected"], receipt["selection_level"]) == (
            "ANSWERED", cc.ALTERNATIVE, "admission_status")
        assert _verdicts(body) == ["VERIFIED"]                        # the body's own appraiser subprocess
        verdict = appraisal.appraise(body.appraisal_request("m:native"))
        assert (verdict["verdict"], verdict["findings"]) == ("VERIFIED", [])
    finally:
        body.close()


def _attached_registry():
    from greg.cognition import cortex
    registry = cortex.registry_view(None)
    for cid in ("cognition.swarm", "cognition.blackbox", cc.ALTERNATIVE):
        registry.set_state(cid, "ATTACHED")
    return registry


def test_a_pinned_compile_answers_on_a_native_route_receipt():
    from greg.cognition import compiler
    registry = _attached_registry()
    params = {"problem_id": "pin", "compile": {"geometry": {"geometry": "optimization"}, "data": NATIVE}}
    out = compiler.run(params, registry=registry)
    assert (out["state"], out["method_or_composition_selected"], out["selection_level"]) == (
        "ANSWERED", cc.ALTERNATIVE, "admission_status")
    pin = replay.receipt_pin(out, params)
    assert pin["route"]["selection"] == "admission_status"
    again = _pinned_run(params, registry, pin)
    assert (again["state"], again["method_or_composition_selected"], again["result"]) == (
        "ANSWERED", cc.ALTERNATIVE, out["result"])
    assert replay.matches(again, pin)


def test_a_request_carrying_both_input_shapes_is_re_read_on_the_route_its_receipt_took():
    """Both shapes, naming different objectives (``BOTH``). While the alternative's native row ranks first the
    compile path answers on that native route (the condition hook only switches a request the incumbent leads), and
    the re-read answers the same native question, never the adapter's translation of the catalog fields. A receipt
    naming the preference's route (pinned by hand here; the body test below produces one, once settled failures rank
    the native row below the incumbent) is re-read through the adapter alone, on the catalog fields, as that route
    ran."""
    from greg.cognition import compiler
    registry = _attached_registry()
    params = {"problem_id": "pin", "compile": {"geometry": {"geometry": "optimization"}, "data": BOTH}}
    out = compiler.run(params, registry=registry)
    assert (out["method_or_composition_selected"], out["selection_level"]) == (cc.ALTERNATIVE, "admission_status")
    assert set(out["result"]) == {"x", "value"}
    pin = replay.receipt_pin(out, params)
    assert _pinned_run(params, registry, pin)["result"] == out["result"]
    route = {**pin["route"], "selection": "preferred_by_condition_evidence"}
    adapted = _pinned_run(params, registry, {**pin, "route": route})
    assert adapted["method_or_composition_selected"] == cc.ALTERNATIVE
    assert set(adapted["result"]) == {"candidate", "fitness", "evaluations"}


def test_a_preference_route_pin_is_never_answered_on_the_native_row_once_the_adapter_row_cannot_run(monkeypatch):
    """The alternative still attached, its admission withdrawn since the receipt: the preference's route cannot run,
    and the native row (which answers the native fields' question) must not run in its place."""
    from greg.cognition import cortex
    from greg.cognition.contracts import CognitionError
    registry = _attached_registry()
    params = {"problem_id": "pin", "compile": {"geometry": {"geometry": "optimization"}, "data": BOTH}}
    pin = _pin(cc.ALTERNATIVE, registry.manifests[cc.ALTERNATIVE].version, "preferred_by_condition_evidence", params)
    assert set(_pinned_run(params, registry, pin)["result"]) == {"candidate", "fitness", "evaluations"}
    monkeypatch.setattr(cc, "_admitted", lambda: False)
    monkeypatch.setattr(cortex, "reason", lambda *a, **k: pytest.fail("a solver ran"))
    with pytest.raises(CognitionError, match=UNAVAILABLE):
        _pinned_run(params, registry, pin)


def test_a_preference_route_failure_on_both_shapes_is_not_confirmed_once_the_adapter_row_cannot_run(tmp_path,
                                                                                                    monkeypatch):
    """A real preference-route failure closure on a request carrying both shapes (the engine's process saw the fired
    preference and settled failures demoting the native row): the body's own appraiser confirms it. Once admission
    is withdrawn the re-read could only run the native row, another question, so it is refused, never confirmed."""
    body = _run(tmp_path, "m:both", engine_fired=True, native_demoted=True, data=BOTH,
                predicate={"op": "lte", "field": "result.fitness", "value": -1.0})      # rosenbrock >= 0: unmet
    try:
        receipt = _compiled(body, "m:both")
        assert (receipt["state"], receipt["method_or_composition_selected"], receipt["selection_level"]) == (
            "ANSWERED", cc.ALTERNATIVE, "preferred_by_condition_evidence")
        assert set(receipt["result"]) == {"candidate", "fitness", "evaluations"}
        assert _verdicts(body) == ["VERIFIED_UNMET"]                  # the body's own appraiser subprocess
        [closure] = [e.event_id for e in body.journal.replay("mission.unmet") if e.payload["mission_id"] == "m:both"]
        request = body.appraisal_request("m:both", closure_event=closure)
        admitted = appraisal.appraise(request)
        assert (admitted["verdict"], admitted["findings"]) == ("VERIFIED_UNMET", [])
        monkeypatch.setattr(cc, "_admitted", lambda: False)
        verdict = appraisal.appraise(request)
        assert verdict["verdict"] != "VERIFIED_UNMET"
        assert len(verdict["findings"]) == 1 and _refused(verdict["findings"]), verdict["findings"]
    finally:
        body.close()


def test_a_receipt_claiming_the_preference_route_without_its_record_is_refused():
    """A native-route receipt on a request carrying both shapes, rewritten to claim the condition preference's route
    and stripped of its condition record. The compiler never writes that level without the fired preference, so the
    receipt names no route a re-read can follow; accepted, its re-read would run the adapter on the catalog fields,
    another objective."""
    from greg.cognition import compiler
    registry = _attached_registry()
    params = {"problem_id": "pin", "compile": {"geometry": {"geometry": "optimization"}, "data": BOTH,
                                               "execute": False}}
    out = compiler.run(params, registry=registry)
    assert (out["method_or_composition_selected"], out["selection_level"]) == (cc.ALTERNATIVE, "admission_status")
    forged = {**out, "selection_level": "preferred_by_condition_evidence"}
    forged.pop("condition", None)
    with pytest.raises(ValueError, match="route"):
        replay.receipt_pin(forged, params)


@pytest.mark.parametrize("preference", [None, {"fired": True, "prefer": cc.ALTERNATIVE},
                                        {"fired": False, "prefer": cc.ALTERNATIVE},
                                        {"fired": True, "prefer": cc.INCUMBENT}],
                         ids=["absent", "agrees", "unfired", "other"])
def test_a_receipt_whose_route_disagrees_with_its_recorded_preference_is_refused(preference):
    """A receipt that says the condition preference chose its method, while it records no preference, or one that
    did not fire or preferred another method, is refused: its route is not known, so no re-read can follow it."""
    from greg.cognition import compiler
    params = {"problem_id": "pin", "compile": {"geometry": {"geometry": "optimization"}, "data": _request()}}
    out = {"schema": compiler.SCHEMA, "inputs_digest": digest(params), "method_or_composition_selected": cc.ALTERNATIVE,
           "selection_level": "preferred_by_condition_evidence", "selected_receipt": None,
           "condition": {"policy": cc.POLICY, **({"preference": preference} if preference else {})}}
    if preference is not None and preference["fired"] and preference["prefer"] == cc.ALTERNATIVE:
        assert replay.receipt_pin(out, params)["route"]["selection"] == "preferred_by_condition_evidence"
    else:
        with pytest.raises(ValueError, match="route"):
            replay.receipt_pin(out, params)


def test_a_compile_receipt_naming_no_method_is_refused_and_never_re_read_on_other_inputs(tmp_path, monkeypatch):
    """A prohibited compile names no method. #243 fails closed on it (kept in this join: a receipt that pins no
    method, route and version is not re-read by current routing); on other inputs than the receipt answered the
    refusal is the inputs digest's, checked first."""
    from greg import pipeline
    body = _run(tmp_path, "m:prohibited", consequence={"lawful": False},
                predicate={"op": "equals", "field": "state", "value": "PROHIBITED"})
    try:
        receipt = _compiled(body, "m:prohibited")
        assert (receipt["state"], receipt["method_or_composition_selected"]) == ("PROHIBITED", None)
        assert _verdicts(body) == ["REFUTED"]
        request = body.appraisal_request("m:prohibited")
        verdict = appraisal.appraise(request)
        assert verdict["verdict"] != "VERIFIED" and _refused(verdict["findings"]), verdict["findings"]
        real = pipeline.resolve

        def moved(params, journal, mission_id, **kw):
            bound, rest = real(params, journal, mission_id, **kw)
            if "before_seq" not in kw:                       # the re-read's live resolve, never the binding check's
                bound = {**bound, "problem_id": bound["problem_id"] + ":moved"}
            return bound, rest

        monkeypatch.setattr(pipeline, "resolve", moved)
        verdict = appraisal.appraise(request)
        assert verdict["verdict"] != "VERIFIED"
        assert any(f.endswith("(ValueError)") for f in verdict["findings"])
    finally:
        body.close()


@pytest.mark.parametrize("how", ["value_error", "timeout"])
def test_a_failure_closure_whose_pinned_re_read_abstains_is_not_confirmed(failed, monkeypatch, how):
    """The incumbent's solver runs on the recorded route at appraisal but gives no answer (it raises, or times out):
    nothing was measured, so the failure closure is refused, never read VERIFIED_UNMET."""
    import subprocess
    from greg.cognition import cortex
    ran = []

    def broken(family, data, effective):
        ran.append(family)
        if how == "timeout":
            raise subprocess.TimeoutExpired("solver", 1)
        raise ValueError("solver unavailable")

    monkeypatch.setattr(cortex, "_numeric", broken)
    verdict = appraisal.appraise(failed)
    assert ran                                      # the recorded route was taken: the solver was asked
    assert verdict["verdict"] != "VERIFIED_UNMET"
    assert len(verdict["findings"]) == 1 and _refused(verdict["findings"]), verdict["findings"]
    assert "gave no answer" in verdict["findings"][0]


@pytest.mark.parametrize("ran, refused", [
    ({"state": "ABSTAIN", "selected_receipt": {"method": cc.INCUMBENT, "abstention_state": "ABSTAIN"}}, True),
    ({"state": "REFUTED", "selected_receipt": {"method": cc.INCUMBENT, "abstention_state": "REFUTED"}}, False),
    ({"state": "ABSTAIN", "selected_receipt": None}, True),
    ({"state": "FORMALIZATION_INCOMPLETE", "selected_receipt": None}, True),
    ({"state": "REFUTED", "selected_receipt": None}, False)],
    ids=["operation-abstained", "operation-refuted", "composition-abstained", "constructed-incomplete",
         "composition-refuted"])
def test_a_pinned_re_read_that_ran_and_gave_no_answer_measured_nothing(ran, refused):
    """A pinned compile that ran the receipt's method and returned no result: an abstention measured nothing (the
    appraiser refuses it, never judges it); a refutation is a measurement. A route with no executed-method receipt (a
    composition or a constructed method) is judged by the compile's own state."""
    out = {"method_or_composition_selected": cc.INCUMBENT, "result": None, **ran}
    assert bool(replay.unmeasured(out)) is refused
    assert replay.unmeasured({**out, "result": {"fitness": 1.0}}) is None


def test_a_receipt_recording_a_fired_preference_for_its_method_off_the_preference_route_is_refused():
    """The alternative answered on its native route (``admission_status``) while the receipt records a fired
    preference for it: the compiler never writes that pair (a preference that fired and switched the route records
    its level), so the receipt's route is not known and no re-read follows it."""
    from greg.cognition import compiler
    registry = _attached_registry()
    params = {"problem_id": "pin", "compile": {"geometry": {"geometry": "optimization"}, "data": BOTH}}
    out = compiler.run(params, registry=registry)
    assert (out["method_or_composition_selected"], out["selection_level"]) == (cc.ALTERNATIVE, "admission_status")
    assert replay.receipt_pin(out, params)["route"]["selection"] == "admission_status"
    forged = {**out, "condition": {"policy": cc.POLICY, "preference": {"fired": True, "prefer": cc.ALTERNATIVE}}}
    with pytest.raises(ValueError, match="route"):
        replay.receipt_pin(forged, params)
    # a recorded preference that did not fire, or preferred another method, is no contradiction
    for preference in ({"fired": False, "prefer": cc.ALTERNATIVE}, {"fired": True, "prefer": cc.INCUMBENT}):
        kept = {**out, "condition": {"policy": cc.POLICY, "preference": preference}}
        assert replay.receipt_pin(kept, params)["route"]["selection"] == "admission_status"


# ------------------------------------------------- the closures #243 refused, re-read on the receipt's own route
def _composed_spec(mid):
    from cortex.evaluation.composition_lift.run import f1
    params = {"problem_id": f"real:{mid}", "compile": {"geometry": {}, "data": f1(3)["payload"]}}
    step = {"capability": "cognition.solve", "target": "cognition:staffing", "params": params}
    return mission(mid, checks=[{"check_id": "good", "description": "a composed answer", "sensor": step,
                                 "predicate": {"op": "equals", "field": "state", "value": "ANSWERED"}}],
                   strategies=[{"action_id": "compile", **step, "advances": ["good"], "rationale": "compose"}],
                   capabilities=["cognition.solve"], targets=("cognition:*",), ceiling="read_only")


def test_a_composition_closure_is_re_read_on_its_recipe_and_verified(tmp_path, monkeypatch):
    """A compile the composition route answered records no executed-method receipt, so its pin names the recipe and
    route with no version. It is re-read on that recipe and verified, by the body's own appraiser and here; once the
    recipe is no fit for the request the re-read is refused, never answered by another route."""
    pytest.importorskip("z3")
    pytest.importorskip("ortools")
    from greg.cognition import compiler
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _composed_spec("m:composed")))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        for _ in range(3):
            body.tick()
            clock.advance(31)
        receipt = _compiled(body, "m:composed")
        assert (receipt["state"], receipt["method_or_composition_selected"], receipt["selected_receipt"]) == (
            "ANSWERED", "composition:estimate_then_optimize", None)
        assert _verdicts(body) == ["VERIFIED"]
        assert appraisal.appraise(body.appraisal_request("m:composed"))["verdict"] == "VERIFIED"
        real = compiler.candidates
        monkeypatch.setattr(compiler, "candidates", lambda *a, **k: [
            r for r in real(*a, **k) if r["method"] != "composition:estimate_then_optimize"])
        verdict = appraisal.appraise(body.appraisal_request("m:composed"))
        assert verdict["verdict"] != "VERIFIED" and _refused(verdict["findings"]), verdict["findings"]


def test_the_human_route_is_re_read_on_that_route_alone():
    from greg.cognition import cortex
    from greg.cognition.contracts import CognitionError
    registry = cortex.registry_view(None)
    params = {"problem_id": "hum", "compile": {"geometry": {"geometry": "optimization",
                                                            "human_judgment_required": True}, "data": {"x": 1}}}
    out = cortex.reason(params, registry=registry)
    assert (out["state"], out["selection_level"]) == ("HUMAN_JUDGMENT_REQUIRED", "constitutional_route")
    pin = replay.receipt_pin(out, params)
    assert pin["version"] is None
    again = _pinned_run(params, registry, pin)
    assert again["state"] == "HUMAN_JUDGMENT_REQUIRED" and replay.matches(again, pin)
    # a pin naming a catalog method cannot be answered by the human route, nor the human route's pin by a method
    with pytest.raises(CognitionError, match=UNAVAILABLE):
        _pinned_run(params, registry, {**pin, "method": cc.INCUMBENT})
    other = {"problem_id": "pin", "compile": {"geometry": {"geometry": "optimization"}, "data": _request()}}
    with pytest.raises(CognitionError, match=UNAVAILABLE):
        _pinned_run(other, _attached_registry(), {**pin, "inputs_digest": digest(other)})


def test_a_versionless_pin_is_never_honoured_on_an_operation_route(monkeypatch):
    """Only a composition, a construction and the human route record no executed-method receipt. A receipt naming an
    operation without one (stripped, or a compile that never executed) is not re-read by the method's name alone."""
    from greg.cognition import cortex
    from greg.cognition.contracts import CognitionError
    params = {"problem_id": "pin", "compile": {"geometry": {"geometry": "optimization"}, "data": _request()}}
    monkeypatch.setattr(cortex, "reason", lambda *a, **k: pytest.fail("a solver ran"))
    with pytest.raises(CognitionError, match=UNAVAILABLE):
        _pinned_run(params, _attached_registry(), _pin(cc.INCUMBENT, None, "admission_status", params))


def test_a_bound_pin_is_honoured_only_on_a_compile_of_the_receipts_inputs(monkeypatch):
    """The pin is bound around the ordinary adapter call. Any other compile under it (other inputs) fails closed;
    it never drops the pin and routes again."""
    from greg.cognition import cortex
    from greg.cognition.contracts import CognitionError
    registry = _attached_registry()
    params = {"problem_id": "pin", "compile": {"geometry": {"geometry": "optimization"}, "data": _request()}}
    other = {"problem_id": "other", "compile": {"geometry": {"geometry": "optimization"}, "data": _request()}}
    pin = _pin(cc.INCUMBENT, registry.manifests[cc.INCUMBENT].version, "admission_status", params)
    monkeypatch.setattr(cortex, "reason", lambda *a, **k: pytest.fail("a solver ran"))
    with pytest.raises(CognitionError, match=UNAVAILABLE):
        _pinned_run(other, registry, pin)


def test_the_pin_has_one_channel_and_nothing_in_the_compiler_rebinds_it():
    """#243's context variable is the one pin channel: ``compiler.run`` takes no ``pin`` parameter that a local
    ``pin = replay_pin()`` could shadow, reads the variable once, and never assigns ``pin`` again."""
    import inspect
    import re
    from greg.cognition import compiler, cortex
    assert "pin" not in inspect.signature(compiler.run).parameters
    assert not hasattr(cortex, "reread")
    source = inspect.getsource(compiler.run)
    assert re.findall(r"^\s*pin\s+=\s", source, re.MULTILINE) == ["    pin = "]       # statements, not keywords
    assert source.count("replay_pin()") == 1


def test_a_re_read_that_lost_its_pin_is_refused_by_the_appraisers_postcondition(failed, monkeypatch):
    """The appraiser's own backstop: a compile that never saw the bound pin (here the compiler's read of the channel
    is cut, and the fired preference routes the request to the alternative) is refused, never judged."""
    from greg.cognition import compiler
    monkeypatch.setattr(cc, "evidence_from", lambda journal: FIRED)
    monkeypatch.setattr(compiler, "replay_pin", lambda: None)
    verdict = appraisal.appraise(failed)
    assert verdict["verdict"] != "VERIFIED_UNMET"
    assert len(verdict["findings"]) == 1 and _refused(verdict["findings"]), verdict["findings"]
    assert "did not replay" in verdict["findings"][0]


def test_a_pinned_compile_reads_no_settled_outcomes(monkeypatch):
    """Learned routing (settled inhibition, ranking, the settled preference) is not consulted under a pin: the
    replay records ``learned_routing: False`` and keeps to it."""
    from greg.cognition import compiler
    registry = _attached_registry()
    params = {"problem_id": "pin", "compile": {"geometry": {"geometry": "optimization"}, "data": _request(),
                                               "execute": False}}
    monkeypatch.setattr(compiler, "_settled_counts", lambda journal: {cc.INCUMBENT: (10, 0)})
    routed = compiler.run(params, registry=registry)
    assert any(d["method"] == cc.INCUMBENT for d in routed["methods_demoted"])          # the control
    pin = _pin(cc.INCUMBENT, registry.manifests[cc.INCUMBENT].version, "admission_status", params)
    again = _pinned_run(params, registry, pin)
    assert again["method_or_composition_selected"] == cc.INCUMBENT
    assert not any(d["method"] == cc.INCUMBENT for d in again["methods_demoted"])
    assert again["replay"]["learned_routing"] is False and "settled_preference" not in again
