"""The founder's words become one approved call to a hosted MCP server they logged in to or registered.

"Use the notes service to add 'ship the wedge'; check https://notes.example/board" becomes one ``mcp.act`` by URL,
its tool taken from the list the service gave at login (drafting contacts nobody), its one argument from the quotes.
GREG cannot read a hosted service's disk, so the mission closes only when GREG renders the page the words name and
finds the text. Whatever the words do not settle becomes a question.
"""
from __future__ import annotations

from greg.missions import validate_mission
from greg.planner import PlannerContext, authority_summary, propose

NOTES = {"server": "https://notes.example/mcp", "kind": "registered token", "renews_at": None, "handle": "mcp:notes",
         "tools": [{"name": "add_note", "description": "Add a note.", "needs": ["text"], "claims_read_only": None},
                   {"name": "list_notes", "description": "List notes.", "needs": [], "claims_read_only": True}]}
ISSUES = {"server": "https://mcp.issues.example/mcp", "kind": "OAuth login", "renews_at": "auth.issues.example",
          "handle": "mcp:issues",
          "tools": [{"name": "open_issue", "description": "Open an issue.", "needs": ["title"], "claims_read_only": False}]}


def ctx(tmp_path, **hosted):
    return PlannerContext(read_roots=(str(tmp_path),), capabilities=[], workspace=tmp_path / "ws",
                          hosted=hosted or {"notes": NOTES, "issues": ISSUES})


def test_words_naming_a_hosted_service_become_one_approved_call_checked_on_a_named_page(tmp_path):
    words = "Use the notes service to add 'ship the wedge', then check https://notes.example/board."
    out = propose(words, ctx(tmp_path))
    assert out["status"] == "PROPOSED" and out["origin"] == "template:mcp-remote-act", out
    spec = out["spec"]
    validate_mission(spec)
    [strategy] = spec["strategies"]
    assert strategy["capability"] == "mcp.act" and strategy["target"] == "mcp:notes"
    assert strategy["params"] == {"server": "notes", "url": "https://notes.example/mcp", "tool": "add_note",
                                  "arguments": {"text": "ship the wedge"}, "bearer": "mcp:notes"}
    [check] = spec["success_checks"]
    assert check["sensor"] == {"capability": "browser.render", "params": {"url": "https://notes.example/board"},
                               "target": "web:notes.example"}
    assert check["predicate"] == {"op": "contains", "field": "text", "value": "ship the wedge"}
    cone = spec["light_cone"]
    assert cone["max_consequence_class"] == "read_only" and cone["budget_usd"] == 0.0
    assert sorted(cone["targets"]) == ["mcp:notes", "web:notes.example"]
    summary = authority_summary(spec, [])                 # the call itself waits for approval; the render does not
    assert summary["must_ask_you_first"] and "mcp.act" in summary["must_ask_you_first"][0], summary
    assert summary["may_do_without_asking"] == ["observe: browser.render"], summary
    assert "drafting contacted nobody" in " ".join(out["notes"])


def test_a_login_that_renews_elsewhere_names_that_host_in_the_approval(tmp_path):
    out = propose('Use the issues service to open an issue "relay door leaks"; check https://issues.example/open',
                  ctx(tmp_path))
    params = out["spec"]["strategies"][0]["params"]
    assert params["tool"] == "open_issue" and params["arguments"] == {"title": "relay door leaks"}
    assert params["hosts"] == ["mcp.issues.example", "auth.issues.example"] and params["bearer"] == "mcp:issues"


def test_what_the_words_do_not_settle_is_asked_never_guessed(tmp_path):
    c = ctx(tmp_path)
    no_page = propose("Use the notes service to add 'ship the wedge'", c)
    assert no_page["status"] == "NEEDS_INPUT" and "Which page" in no_page["questions"][0]
    two_pages = propose("Use the notes service to add 'x'; check https://a.example/1 and https://b.example/2", c)
    assert two_pages["status"] == "NEEDS_INPUT" and "Which page" in two_pages["questions"][0]
    no_quote = propose("Use the notes service to add ship the wedge; check https://notes.example/board", c)
    assert no_quote["status"] == "NEEDS_INPUT" and "in quotes" in no_quote["questions"][0]
    read_only = propose("Use the notes service list_notes; check https://notes.example/board", c)
    assert read_only["status"] == "NEEDS_INPUT" and "approval" in read_only["questions"][0]   # its read-only claim
    unknown_tool = propose("Use the notes service to update 'x'; check https://notes.example/board", c)
    assert unknown_tool["status"] == "NEEDS_INPUT" and "add_note" in unknown_tool["questions"][0]
    the_server = propose("Use the notes service to add 'x'; check https://notes.example/mcp only", c)
    assert the_server["status"] == "NEEDS_INPUT"       # the server's own address is not a page that shows the effect


def test_words_that_name_no_hosted_service_are_left_to_other_routes(tmp_path):
    out = propose("Use the calendar service to add 'x'; check https://cal.example/", ctx(tmp_path))
    assert out.get("origin") != "template:mcp-remote-act"
    assert propose("add 'x' to my notes", ctx(tmp_path, notes=NOTES)).get("origin") != "template:mcp-remote-act"


def test_the_proposal_says_which_evidence_the_page_is(tmp_path):
    from greg.templates import remote_evidence
    assert remote_evidence("https://notes.example/mcp", "https://notes.example/board") == "same_service"
    # a sibling is not the service's own host; without a public-suffix list GREG cannot tell a sibling from another
    # tenant of a shared suffix, so it gets the cautious label (fifth review of #184, F2)
    assert remote_evidence("https://mcp.notes.example/mcp", "https://www.notes.example/board") == "separate_host"
    assert remote_evidence("https://notes.example/mcp", "https://status.other.example/board") == "separate_host"
    same = propose("Use the notes service to add 'x', then check https://notes.example/board", ctx(tmp_path))
    assert "not an independent corroboration" in " ".join(same["notes"])
    assert "read-after-write" in same["spec"]["success_checks"][0]["description"]
    other = propose("Use the notes service to add 'x', then check https://status.other.example/board", ctx(tmp_path))
    assert "not proven independent corroboration" in " ".join(other["notes"])
    assert "service's answer to the call is its own claim" in " ".join(other["notes"])
