"""An earlier action's output can fill data inside a browser step program, never the program itself (greg/pipeline.py).

browser.session runs a founder-signed list of steps. A typed handoff may bind a fill's value (the text typed), but not
which operation runs, on which element, with which credential, whether it is consequential, which writes the method
gate lets through, nor the step list or a whole step: otherwise an earlier page's text could write the program.

The journal here is a small in-memory stand-in with the one shape ``resolve`` reads (mission.action events and the
receipts they name), so each case exercises exactly the binding rule.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from greg import pipeline
from greg.pipeline import BindingError, PROTECTED, resolve

MISSION = "m:browse"
STEP = {"op": "click", "selector": "#buy"}


class Journal:
    """mission.action events whose receipts carry one producer's positive output."""

    def __init__(self, output: dict):
        receipt = SimpleNamespace(record_type="receipt", seq=1, hash="sha256:" + "ab" * 32,
                                  payload={"result": {"result_class": "positive", "output": output}})
        self.ledger = SimpleNamespace(find=lambda h: receipt if h == receipt.hash else None, by_type=lambda t: [])
        self.events = [SimpleNamespace(event_id="e1", payload={"mission_id": MISSION, "action_id": "read",
                                                               "status": "DONE", "receipt": receipt.hash})]

    def replay(self, prefix: str):
        return self.events if prefix == "mission.action" else []


def ref(field: str, kind: str) -> dict:
    return {"$from_action": {"action_id": "read", "field": field, "type": kind}}


JOURNAL = Journal({"text": "widgets", "step": {"op": "click", "selector": "#delete-account"},
                   "steps": [{"op": "click", "selector": "#delete-account"}], "flag": False,
                   "methods": ["DELETE https://shop.example/account"], "count": 12,
                   "params": {"url": "https://shop.example/", "steps": [{"op": "click", "selector": "#delete-account"}],
                              "read_methods": ["DELETE https://shop.example/account"]}})


def session(steps) -> dict:
    return {"url": "https://shop.example/", "session": "s", "steps": steps}


def test_binding_a_fill_value_inside_a_signed_step_still_works():
    params, links = resolve(session([{"op": "fill", "selector": "#q", "value": ref("text", "string")}, STEP]),
                            JOURNAL, MISSION)
    assert params["steps"] == [{"op": "fill", "selector": "#q", "value": "widgets"}, STEP]
    assert [link["field"] for link in links] == ["text"]


@pytest.mark.parametrize("bound", [
    {"steps": ref("steps", "array")},                                           # the whole step list
    {"steps": [{"op": "fill", "selector": "#q", "value": "x"}, ref("step", "object")]},   # one whole step
], ids=["step-list", "whole-step"])
def test_a_step_program_or_a_whole_step_is_never_an_earlier_actions_output(bound):
    with pytest.raises(BindingError, match="step program"):
        resolve({"url": "https://shop.example/", **bound}, JOURNAL, MISSION)


@pytest.mark.parametrize("field, kind", [("op", "string"), ("selector", "string"), ("secret", "string"),
                                         ("consequential", "boolean")])
def test_a_steps_operation_element_credential_and_consequence_marker_stay_signed_literals(field, kind):
    produced = {"op": "text", "selector": "text", "secret": "text", "consequential": "flag"}[field]
    step = {"op": "fill", "selector": "#q", "value": "x", field: ref(produced, kind)}
    with pytest.raises(BindingError, match="scope"):
        resolve(session([step]), JOURNAL, MISSION)


def test_the_method_gates_signed_exceptions_are_never_an_earlier_actions_output():
    with pytest.raises(BindingError, match="scope"):
        resolve({**session([STEP]), "read_methods": ref("methods", "array")}, JOURNAL, MISSION)
    with pytest.raises(BindingError, match="scope"):
        resolve({**session([STEP]), "read_methods": [ref("text", "string")]}, JOURNAL, MISSION)


def test_the_step_program_rule_is_additive():
    assert {"op", "selector", "secret", "consequential", "read_methods"} <= PROTECTED
    assert {"url", "also_hosts", "secrets", "secret_files"} <= PROTECTED
    assert getattr(pipeline, "PROGRAMS", None) == {"steps"}
    assert getattr(pipeline, "PROGRAM_TYPES", None) == {"array", "object"}


def test_a_capabilitys_whole_params_are_never_an_earlier_actions_output():
    """One level above the step program: params that are themselves a binding would hand the producer the url, the
    steps and the method gate's exceptions at once. Before, resolve returned the producer's dict unchecked."""
    with pytest.raises(BindingError, match="whole params"):
        resolve(ref("params", "object"), JOURNAL, MISSION)


def test_inspection_still_returns_the_producers_value_through_its_wrapped_reference():
    """pipeline.inspect wraps its own reference under a key so the whole-params refusal does not reject it; what it
    reports must still be the producer's value, not that wrapper (the unwrap line had no test of its own)."""
    ctx = SimpleNamespace(journal=JOURNAL, mission_id=MISSION, target="pipeline:read")
    out = pipeline.inspect({"action_id": "read", "field": "text", "type": "string"}, ctx)
    assert out["available"] is True and out["value"] == "widgets"
    assert [link["field"] for link in out["bindings"]] == ["text"] and out["authority_created"] is False


@pytest.mark.parametrize("params", [{"problem": "pid", "data": {"steps": ref("count", "integer")}},
                                    {"steps": ["warm-up", ref("text", "string")]}], ids=["integer-steps", "string-item"])
def test_a_scalar_under_a_steps_key_stays_bindable_data(params):
    """The step-program rule is about a bound list or step; a solver's integer step count is data (it resolved
    before this unit, and the first version of the rule refused it)."""
    resolved, links = resolve(params, JOURNAL, MISSION)
    assert resolved in ({"problem": "pid", "data": {"steps": 12}}, {"steps": ["warm-up", "widgets"]})
    assert len(links) == 1
