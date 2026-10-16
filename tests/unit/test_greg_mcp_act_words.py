"""The founder's words become one ``mcp.act`` mission: a change they approve, which GREG checks by reading the file.

Words that ask a writing tool for a change ("append “ship it” to ~/notes/plan.md") become one proposal whose light
cone stops at read-only, so the act waits for the founder's decision on its exact scope: the folder the server may
write, no network, no credentials. GREG closes the mission only when it reads the file itself and finds the change.
Whatever the words do not settle (the text, a file GREG can read back) becomes a question.
"""
from __future__ import annotations

import pytest

from greg.missions import validate_mission
from greg.planner import PlannerContext, authority_summary, propose
from tests.unit.test_greg_mcp_planner import install_notes, needs_namespaces


@pytest.fixture
def founder(tmp_path):
    data = tmp_path / "data"
    (data / "notes").mkdir(parents=True)
    (data / "notes" / "plan.md").write_text("one\ntwo\n")
    install_notes(data)
    return {"data": data, "ctx": PlannerContext(read_roots=(str(data),), capabilities=[], workspace=tmp_path / "ws")}


@needs_namespaces
def test_words_asking_for_a_change_become_one_act_the_founder_approves(founder):
    plan = founder["data"] / "notes" / "plan.md"
    words = f"Use the notes server to append “ship the wedge” to {plan}"
    out = propose(words, founder["ctx"])
    assert out["status"] == "PROPOSED" and out["origin"] == "template:mcp-act", out
    spec = out["spec"]
    validate_mission(spec)
    [strategy] = spec["strategies"]
    assert strategy["capability"] == "mcp.act" and strategy["target"] == "mcp:notes"
    params = strategy["params"]
    assert params["tool"] == "append_line" and params["arguments"] == {"path": str(plan), "line": "ship the wedge"}
    assert params["writable"] == [str(plan.parent)] and "hosts" not in params and "secrets" not in params
    [check] = spec["success_checks"]
    assert check["sensor"]["capability"] == "fs.read" and check["sensor"]["params"]["path"] == str(plan)
    assert check["predicate"] == {"op": "contains", "field": "text", "value": "ship the wedge"}
    assert spec["light_cone"]["max_consequence_class"] == "read_only" and spec["light_cone"]["budget_usd"] == 0.0
    summary = authority_summary(spec, [])                 # the caller's list may be empty: the class is still known
    assert summary["must_ask_you_first"] and "mcp.act" in summary["must_ask_you_first"][0]
    assert summary["may_do_without_asking"] == ["observe: fs.read"]
    assert any("may write " + str(plan.parent) + " and nothing else" in n for n in out["notes"])


@needs_namespaces
def test_a_new_file_can_be_named_when_its_folder_exists(founder):
    new = founder["data"] / "notes" / "today.md"
    out = propose(f"Use the notes server to append 'first line' to {new}", founder["ctx"])
    assert out["status"] == "PROPOSED", out
    params = out["spec"]["strategies"][0]["params"]
    assert params["arguments"]["path"] == str(new) and params["writable"] == [str(new.parent)]
    assert out["spec"]["success_checks"][0]["predicate"]["value"] == "first line"


@needs_namespaces
@pytest.mark.parametrize("words, question", [
    ("Use the notes server to append a line to {data}/notes/plan.md", "(put it in quotes)"),
    ("Use the notes server to append \"x\" to {data}/missing/plan.md", "append_line needs path"),
    ("Use the notes server to append \"x\" to /etc/hostname", "GREG may only read under"),
])
def test_what_the_words_do_not_settle_for_a_change_becomes_a_question(founder, words, question):
    out = propose(words.format(data=founder["data"]), founder["ctx"])
    assert out["status"] == "NEEDS_INPUT" and question in out["questions"][0], out


@needs_namespaces
def test_a_tool_that_claims_to_only_read_stays_a_read_only_call(founder):
    plan = founder["data"] / "notes" / "plan.md"
    out = propose(f"Use the notes server to count the lines of {plan} and record them", founder["ctx"])
    assert out["status"] == "PROPOSED" and out["origin"] == "template:mcp-tool", out


def test_an_unknown_capability_is_never_summarized_as_allowed_without_asking():
    spec = {"light_cone": {"capabilities": ["*"], "max_consequence_class": "external_contact", "budget_usd": 0.0,
                           "horizon": "2026-12-01T00:00:00Z"},
            "success_checks": [{"sensor": {"capability": "fs.read"}}], "closure": {"kind": "bounded"},
            "strategies": [{"action_id": "x", "capability": "made.up", "target": "anything"}]}
    assert authority_summary(spec, [])["must_ask_you_first"] == ["x: made.up (unknown consequence) on anything"]


@needs_namespaces
def test_a_slash_inside_the_quoted_text_is_not_taken_for_the_file(founder):
    plan = founder["data"] / "notes" / "plan.md"
    out = propose(f"Use the notes server to append “ship/now” to {plan}", founder["ctx"])
    assert out["status"] == "PROPOSED", out
    assert out["spec"]["strategies"][0]["params"]["arguments"] == {"path": str(plan), "line": "ship/now"}
