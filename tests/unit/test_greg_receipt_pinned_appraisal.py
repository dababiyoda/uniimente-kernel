"""Appraisal re-reads a compiled cognition receipt by the method it names.

Diagnosis on issue #96, comment 6520187727 §1: ``greg/appraisal.py`` re-observes a
``cognition.*`` sensor by calling the adapter again, so the re-read follows today's
learned routing (``condition_competence.compile_hook``, ``_settled_preference``,
``_settled_inhibition``). Once a cell preference fires, that re-read runs a different
method than the receipt and disagrees exactly on a discordant pair, which is the
evidence learning needs. A failure closure is then REFUTED ("world no longer matches")
instead of VERIFIED_UNMET.

The re-read must replay the method, route and version pinned on the original receipt,
run no shadow, and fail closed when that method cannot be run. It must not fall back
to whatever routing would choose today.
"""
from __future__ import annotations

import random

from greg.appraisal import appraise
from greg.body import Body
from greg.cognition import condition_competence as cc
from greg.cognition.cortex import reason, registry_view
from tests.greg_fixtures import Clock, host_worker_confinement, make_body, mission, signed

TAU = 1e-6
FIRED = {"optimization|d<=10": {"pairs": 6, "alternative_only": 6, "incumbent_only": 0}}


def _data() -> dict:
    rnd = random.Random(1)
    return {"function": "sphere", "shift": [round(rnd.uniform(-2, 2), 3) for _ in range(3)],
            "bounds": [[-5.12, 5.12]] * 3, "budget": 200, "seed": 1}


def _spec(mid: str) -> dict:
    params = {"problem_id": f"real:{mid}", "compile": {"geometry": {"geometry": "optimization"}, "data": _data()}}
    return mission(mid, checks=[{
        "check_id": "good", "description": f"fitness at most {TAU}",
        "sensor": {"capability": "cognition.solve", "target": "cognition:bb", "params": params},
        "predicate": {"op": "lte", "field": "result.fitness", "value": TAU}}],
        strategies=[{"action_id": "compile", "capability": "cognition.solve", "target": "cognition:bb",
                     "params": params, "advances": ["good"], "rationale": "minimise"}],
        capabilities=["cognition.solve"], targets=("cognition:*",), ceiling="read_only")


def _open(tmp_path):
    home, key, body_id, _ = make_body(tmp_path, worker_confinement=host_worker_confinement())
    body = Body(home, clock=Clock()).open()
    body.boot()
    for cid in ("cognition.swarm", "cognition.blackbox", cc.ALTERNATIVE):
        body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": cid}))
    return body, key, body_id


def _fail_unmet(tmp_path):
    """One real failure closure whose receipt is the incumbent, before any preference fires."""
    body, key, body_id = _open(tmp_path)
    body.apply(signed(key, body_id, "MISSION", _spec("m:pinned")))
    clock = body.clock
    for _ in range(5):
        body.tick()
        clock.advance(31)
    unmet = [e for e in body.journal.replay("mission.unmet") if e.payload["mission_id"] == "m:pinned"]
    assert len(unmet) == 1, "the incumbent must still fail this check; the fixture is not discordant"
    verdicts = {e.payload["mission_id"]: e.payload for e in body.journal.replay("mission.appraised")}
    assert verdicts["m:pinned"]["verdict"] == "VERIFIED_UNMET"
    return body, key, body_id, unmet[0]


def _prefer(monkeypatch):
    monkeypatch.setattr(cc, "evidence_from", lambda journal: FIRED)


def test_a_fired_preference_answers_with_the_other_method(monkeypatch):
    """The precondition of the bug: today's routing and the receipt's method disagree, and the
    predicate passes only for the method routing would pick now."""
    _prefer(monkeypatch)
    registry = registry_view(None)
    for cid in ("cognition.swarm", "cognition.blackbox", cc.ALTERNATIVE):
        registry.set_state(cid, "ATTACHED")
    out = reason({"problem_id": "pref", "compile": {"geometry": {"geometry": "optimization"}, "data": _data()}},
                 registry=registry)
    assert out["method_or_composition_selected"] == cc.ALTERNATIVE
    assert out["selection_level"] == "preferred_by_condition_evidence"
    assert out["result"]["fitness"] <= TAU


def test_a_discordant_failure_stays_verified_unmet_after_routing_moves(tmp_path, monkeypatch):
    body, _key, _body_id, unmet = _fail_unmet(tmp_path)
    try:
        _prefer(monkeypatch)
        verdict = appraise(body.appraisal_request("m:pinned", closure_event=unmet.event_id))
        assert verdict["verdict"] == "VERIFIED_UNMET", verdict["findings"]
        assert not any("world no longer matches" in f for f in verdict["findings"])
    finally:
        body.close()


def test_an_unavailable_pinned_method_fails_closed(tmp_path, monkeypatch):
    """Detaching the receipt's method must not let today's preferred method stand in for it."""
    body, key, body_id, unmet = _fail_unmet(tmp_path)
    try:
        applied = body.apply(signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": cc.INCUMBENT}))
        assert applied["status"] == "APPLIED"
        _prefer(monkeypatch)
        verdict = appraise(body.appraisal_request("m:pinned", closure_event=unmet.event_id))
        assert verdict["verdict"] == "REFUTED", verdict
        assert any("receipt method unavailable" in f for f in verdict["findings"]), verdict["findings"]
    finally:
        body.close()
