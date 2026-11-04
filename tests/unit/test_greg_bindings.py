"""P6: typed output->input edges between strategies of one signed mission.

A strategy may take a param from a field of another strategy's latest DONE Gate receipt.
The edge is signed with the mission; the value is data. Capability, target, cost and
consequence class never change, and the bound params enter the scope digest, so an
approval covers exactly the bound content. Unavailable or mistyped inputs hold the
strategy; they are never coerced. The founder key is a per-test key, not Alfonso's.
"""
import hashlib

import pytest

from greg.authority import AuthorityOffice
from greg.body import Body
from greg.missions import MissionError, Unbound, bound_value, validate_mission
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy


def composed(home, *, edge=None):
    root = workspace(home, "m:composed")
    edge = edge or {"param": "content", "from": {"action_id": "write-a", "field": "sha256"}, "type": "string",
                    "template": "digest of a: {value}"}
    first = write_strategy("write-a", "a.txt", "alive 41", ["a"])
    second = {"action_id": "write-b", "capability": "fs.write", "params": {"relative_path": "b.txt"},
              "bind": [edge], "target": "workspace:b.txt", "advances": ["b"], "requires": ["a"],
              "rationale": "derive b from a's receipted output"}
    expected = "digest of a: " + hashlib.sha256(b"alive 41").hexdigest()
    return mission("m:composed", checks=[note_check("a", root / "a.txt", "alive"),
                                         note_check("b", root / "b.txt", expected)],
                   strategies=[first, second], capabilities=["fs.read", "fs.write"]), expected


def run(home, ticks=6):
    clock = Clock()
    states = []
    with Body(home, clock=clock) as body:
        body.boot()
        for _ in range(ticks):
            clock.advance(60)
            states.append(body.tick()["missions"][0]["state"])
            if states[-1] == "ACHIEVED":
                break
        actions = [e.payload for e in body.journal.replay("mission.action")]
        return states, actions, body


def test_one_signed_mission_composes_two_actions_through_a_receipted_edge(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    spec, expected = composed(home)
    drop(home, signed(key, body_id, "MISSION", spec))
    states, actions, _ = run(home)
    assert states[-1] == "ACHIEVED", states
    assert (workspace(home, "m:composed") / "b.txt").read_text() == expected
    first = next(a for a in actions if a["action_id"] == "write-a")
    second = next(a for a in actions if a["action_id"] == "write-b")
    assert second["bindings"] == [{"param": "content", "from_action": "write-a", "from_receipt": first["receipt"],
                                   "field": "sha256", "value_sha256": second["bindings"][0]["value_sha256"]}]
    # The scope the Gate authorized is the resolved content, not the unbound template.
    resolved = AuthorityOffice.scope_digest(mission_id="m:composed", capability_id="fs.write",
                                            params={"relative_path": "b.txt", "content": expected},
                                            target="workspace:b.txt", consequence_class="internal_write",
                                            cost_usd=0.0)
    assert second["scope_digest"] == resolved


def test_a_mistyped_input_holds_the_strategy_and_is_never_coerced(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    spec, _ = composed(home, edge={"param": "content", "from": {"action_id": "write-a", "field": "sha256"},
                                   "type": "integer"})
    drop(home, signed(key, body_id, "MISSION", spec))
    states, actions, body = run(home)
    assert "ACHIEVED" not in states
    assert [a["action_id"] for a in actions if a["status"] == "DONE"] == ["write-a"]
    assert not (workspace(home, "m:composed") / "b.txt").exists()
    request = body.engine.book.missions["m:composed"].blocker
    assert request and request["type"] == "decision"


def edge(**kw):
    base = {"param": "content", "from": {"action_id": "write-a", "field": "sha256"}, "type": "string"}
    return {**base, **kw}


@pytest.mark.parametrize("bad, why", [
    (edge(**{"from": {"action_id": "nope", "field": "x"}}), "unknown or own"),
    (edge(**{"from": {"action_id": "write-b", "field": "x"}}), "unknown or own"),
    (edge(param="relative_path"), "also signed statically"),
    (edge(template="no placeholder"), "exactly one"),
    (edge(type="object", template="x {value}"), "renders text"),
])
def test_invalid_edges_are_refused_at_registration(tmp_path, bad, why):
    spec, _ = composed(tmp_path, edge=bad)
    with pytest.raises(MissionError, match=why):
        validate_mission(spec)


def test_binding_cycles_are_refused(tmp_path):
    spec, _ = composed(tmp_path)
    spec["strategies"][0]["bind"] = [{"param": "content", "from": {"action_id": "write-b", "field": "sha256"},
                                      "type": "string"}]
    spec["strategies"][0]["params"].pop("content")
    with pytest.raises(MissionError, match="cycle"):
        validate_mission(spec)


def test_bound_values_are_typed_rendered_and_size_bounded():
    output = {"extracted": {"version": "5.1.0.0", "n": 3}, "flag": True}
    assert bound_value(edge(**{"from": {"action_id": "a", "field": "extracted.version"}}), output) == "5.1.0.0"
    assert bound_value({"param": "p", "from": {"action_id": "a", "field": "extracted"}, "type": "object",
                        "render": "json"}, output) == '{\n "n": 3,\n "version": "5.1.0.0"\n}'
    with pytest.raises(Unbound, match="not integer"):
        bound_value({"param": "p", "from": {"action_id": "a", "field": "flag"}, "type": "integer"}, output)
    with pytest.raises(Unbound, match="has no"):
        bound_value(edge(**{"from": {"action_id": "a", "field": "missing"}}), output)
    with pytest.raises(Unbound, match="exceeds"):
        bound_value({"param": "p", "from": {"action_id": "a", "field": "extracted"}, "type": "object",
                     "max_bytes": 8}, output)


def test_research_post_is_one_mission_with_the_browser_to_worker_edge(tmp_path):
    from greg.templates import research_post
    spec = research_post(url="https://pypi.org/project/z3-solver/", session="z3", order="z3-note",
                         steps=[{"op": "extract", "selector": "h1", "as": "title"}],
                         expect={"op": "exists", "field": "extracted.title"}, daleobanks_root=str(tmp_path),
                         brief="Note the release.", workspace_root=tmp_path / "workspace")
    validate_mission(spec)
    by_id = {s["action_id"]: s for s in spec["strategies"]}
    facts = str((tmp_path / "workspace" / "m_research-z3-note" / "facts.json").resolve())
    assert by_id["record-facts"]["bind"][0]["from"] == {"action_id": "operate-browser", "field": "extracted"}
    assert by_id["draft-post"]["params"]["inputs"] == [facts] and by_id["draft-post"]["requires"] == ["facts_recorded"]
    assert by_id["request-publish"]["requires"] == ["draft_verified"]
    # Publishing stays outside the cone: it stops for a founder decision.
    assert "daleobanks.publish" not in spec["light_cone"]["capabilities"]
    assert spec["light_cone"]["max_consequence_class"] == "internal_write"
