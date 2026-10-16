"""Capability Genesis, builder route: a real deficit is closed by built code and the ORIGINAL mission resumes.

The builder here is deterministic (StaticBuilder); a live Claude Code build is retained
in tests/evidence/greg-product/. Built code always runs in a separate no-network interpreter.
"""
import json
import subprocess

import pytest

from greg import builders
from greg.body import Body
from tests.greg_fixtures import Clock, drop, make_body, mission, signed

FUNCTION = "markdown.unchecked_count"
GOOD = ("import re\n\ndef run(text):\n"
        "    return len(re.findall(r'^[ \\t]*[-*+] \\[ \\]', text, re.M))\n")
WRONG = "def run(text):\n    return text.count('[ ]') + 1\n"                      # fails a public example
OVERFIT = ("def run(text):\n    return {'- [ ] a\\n- [x] b': 1, '* [ ] x\\n  + [ ] y': 2}.get(text, 0)\n")
ESCAPE = "import os\n\ndef run(text):\n    return len(os.listdir('/'))\n"

CONTRACT = {
    "function": FUNCTION,
    "description": "Count unchecked Markdown task items: lines that start with optional spaces or tabs, then "
                   "'-', '*' or '+', one space, then '[ ]'. Checked items '[x]' do not count.",
    "returns": "an integer", "output_field": "unchecked",
    "examples": [{"input_text": "- [ ] a\n- [x] b", "expected": 1},
                 {"input_text": "* [ ] x\n  + [ ] y", "expected": 2}],
    "held_out": [{"input_text": "", "expected": 0},
                 {"input_text": "text - [ ] not at start\n\t- [ ] tabbed\n-[ ] no space", "expected": 1},
                 {"input_text": "- [X] done\n- [ ] open\n+ [ ] also", "expected": 2},
                 {"input_text": "1. [ ] numbered is not a bullet\n    * [ ] deep", "expected": 1}],
    "build_budget_usd": 1.0}


def _mission(data, *, budget=1.0, contract=CONTRACT, auto_attach=True):
    doc = data / "FIRST_MISSION.md"
    doc.write_text("# Runbook\n- [x] install\n- [ ] enroll key\n  - [ ] load launchd\n* [ ] accept closure\n")
    check = {"check_id": "open-items-counted", "description": "the number of open runbook steps is known",
             "sensor": {"function": FUNCTION, "params": {"path": str(doc)}, "target": "fs:FIRST_MISSION.md"},
             "predicate": {"op": "equals", "field": "unchecked", "value": 3}}
    spec = mission("m:runbook", checks=[check], strategies=[], ceiling="read_only", budget=budget,
                   capabilities=["fs.read", f"built.{FUNCTION}.*"], auto_attach=auto_attach)
    spec["capability_specs"] = [dict(contract, build_budget_usd=min(contract["build_budget_usd"], budget))]
    return spec


def _run(home, builder, ticks=4):
    clock = Clock()
    body = Body(home, clock=clock, builder=builder).open()
    body.boot()
    states = []
    for _ in range(ticks):
        clock.advance(30)
        states.append(body.tick()["missions"][0]["state"])
    return body, states


def test_deficit_is_built_verified_attached_and_the_original_mission_closes(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _mission(data)))
    builder = builders.StaticBuilder(WRONG, GOOD, identity="static-test")
    body, states = _run(home, builder)
    j = body.journal
    assert "ACHIEVED" in states                                     # the ORIGINAL mission, not the detour
    opened = j.replay("deficit.opened")[0].payload
    assert opened["acceptance"]["oracle"] == "founder-signed mission contract"
    assert opened["acceptance"]["held_out_vectors"] == 4
    built = [e.payload for e in j.replay("genesis.built")]
    assert [b["attempt"] for b in built] == [1, 2]
    verified = [e.payload for e in j.replay("genesis.verified")]
    assert [v["passed"] for v in verified] == [False, True] and verified[1]["report"]["cases"] == 6
    feedback = builder.calls[1]["feedback"]
    assert feedback and all("numbered" not in f and "tabbed" not in f for f in feedback)   # held-out never leaks
    assert all("held_out" not in json.dumps(call["request"]) for call in builder.calls)
    registered = j.replay("capability.registered")[0].payload["manifest"]
    assert registered["provider"] == "built:static-test" and registered["consequence_class"] == "read_only"
    assert registered["provenance"]["runtime"].startswith("isolated interpreter")
    assert j.replay("deficit.resolved")[0].payload["resume"] == "original mission"
    obs = [e.payload for e in j.replay("mission.observed") if e.payload["passed"]]
    assert obs and obs[-1]["check_id"] == "open-items-counted"
    appraisal = j.replay("mission.appraised")[-1].payload
    assert appraisal["checks"]["checks_rederived_from_receipts"] is True
    body.close()

    body = Body(home, clock=Clock()).open()                          # restart: the capability is restored
    cid = registered["capability_id"]
    assert body.registry.state[cid] == "ATTACHED" and body.registry.usable(cid)[0]
    body.close()


@pytest.mark.parametrize("candidates, why", [((ESCAPE, ESCAPE), "import of 'os'"),
                                             ((OVERFIT, OVERFIT), "failed verification")])
def test_escaping_or_overfit_candidates_are_never_registered(tmp_path, candidates, why):
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _mission(data)))
    body, states = _run(home, builders.StaticBuilder(*candidates), ticks=3)
    assert "ACHIEVED" not in states and not body.journal.replay("capability.registered")
    verified = [e.payload for e in body.journal.replay("genesis.verified")]
    assert verified and not any(v["passed"] for v in verified)
    text = json.dumps([e.payload for e in body.journal.replay("genesis.")])
    assert why in text and "escalated" in text
    body.close()


def test_no_signed_build_budget_means_no_build(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _mission(data, budget=0.0)))
    builder = builders.StaticBuilder(GOOD)
    body, _ = _run(home, builder, ticks=2)
    assert builder.calls == []
    assert any("no founder-signed build budget" in e.payload["result"] for e in body.journal.replay("genesis.route"))
    body.close()


def test_built_source_tampered_after_verification_is_quarantined(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _mission(data)))
    body, _ = _run(home, builders.StaticBuilder(GOOD))
    digest = body.journal.replay("genesis.built")[0].payload["source_sha256"]
    cid = body.journal.replay("capability.registered")[0].payload["manifest"]["capability_id"]
    body.close()
    stored = home / "capabilities" / "built" / f"{digest}.py"
    stored.write_text(stored.read_text() + "\nimport os\n")
    with Body(home) as reopened:
        assert reopened.registry.state[cid] == "QUARANTINED" and not reopened.registry.usable(cid)[0]


def test_isolated_runtime_blocks_network_and_filesystem_escape(tmp_path):
    source = tmp_path / "c.py"
    source.write_text("def run(text):\n    return [c for c in ().__class__.__mro__]\n")
    assert builders.screen(source.read_text())                     # statically refused ...
    ok, report = builders.verify(source, [{"input_text": "", "expected": 0}])
    assert not ok                                                   # ... and fails at runtime too
    netty = tmp_path / "n.py"
    netty.write_text("import json\n\ndef run(text):\n    return __builtins__['open']('/etc/hostname').read()\n")
    ok, _ = builders.verify(netty, [{"input_text": "", "expected": ""}])
    assert not ok


def test_claude_code_builder_has_no_tools_no_disk_and_a_spend_cap():
    seen = {}

    def runner(argv, **kw):
        seen.update(argv=argv, cwd=kw["cwd"], input=kw["input"])
        reply = "Here:\n```python\n" + GOOD + "```"
        return subprocess.CompletedProcess(argv, 0, json.dumps({"is_error": False, "result": reply,
                                                                "total_cost_usd": 0.02}), "")

    builder = builders.ClaudeCodeBuilder("/usr/bin/claude", max_budget_usd=0.4, runner=runner)
    result = builder.build({"function": FUNCTION, "description": CONTRACT["description"], "returns": "an integer",
                            "examples": CONTRACT["examples"]})
    assert result["source"].startswith("import re") and result["cost_usd"] == 0.02
    argv = seen["argv"]
    assert argv[argv.index("--tools") + 1] == "" and argv[argv.index("--max-budget-usd") + 1] == "0.40"
    assert "held_out" not in seen["input"] and "numbered" not in seen["input"]
