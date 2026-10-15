"""Capability Genesis, builder route: a real deficit is closed by built code and the ORIGINAL mission resumes.

The builder here is deterministic (StaticBuilder); a live Claude Code build is retained
in tests/evidence/greg-product/. Built code always runs in a separate no-network interpreter.
"""
import sys
from pathlib import Path
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


def test_a_billed_attempt_without_a_candidate_carries_its_cost():
    """Genesis books BuildError.cost_usd against the signed build budget: an answer is paid for even when
    it holds no source, and a CLI error after spending is still spend."""
    request = {"function": FUNCTION, "description": CONTRACT["description"], "examples": CONTRACT["examples"]}

    class Router:
        last = None

        def complete(self, system, user, *, budget_usd=None):
            return {"text": "I would rather explain it in prose.", "route": "r", "cost_usd": 0.04}

    with pytest.raises(builders.BuildError) as info:
        builders.ModelBuilder(Router()).build(request)
    assert info.value.cost_usd == 0.04

    def runner(argv, **kw):
        return subprocess.CompletedProcess(argv, 0, json.dumps({"is_error": True, "result": "budget exceeded",
                                                                "total_cost_usd": 0.4}), "")
    with pytest.raises(builders.BuildError) as info:
        builders.ClaudeCodeBuilder("/usr/bin/claude", max_budget_usd=0.4, runner=runner).build(request)
    assert info.value.cost_usd == 0.4


def test_a_file_over_the_input_ceiling_is_not_a_fault_of_the_built_capability(tmp_path):
    """Second review (typed failures 0): the world changed (the file grew past the built-capability
    input ceiling), not the capability. That refusal used to default to executor_error: the working
    capability was quarantined, a second deficit generation opened and the builder was called again."""
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _mission(data)))
    builder = builders.StaticBuilder(GOOD, GOOD, GOOD, identity="static-test")
    body, states = _run(home, builder)
    try:
        assert "ACHIEVED" in states
        cid = body.journal.replay("capability.registered")[0].payload["manifest"]["capability_id"]
        calls, deficits = len(builder.calls), len(body.journal.replay("deficit.opened"))
        big = data / "BIG.md"
        big.write_text("- [ ] x\n" * (builders.MAX_INPUT // 8 + 10))
        check = {"check_id": "big-counted", "description": "count",
                 "sensor": {"function": FUNCTION, "params": {"path": str(big)}, "target": "fs:BIG.md"},
                 "predicate": {"op": "equals", "field": "unchecked", "value": 1}}
        spec = mission("m:big", checks=[check], strategies=[], ceiling="read_only", budget=1.0,
                       capabilities=["fs.read", f"built.{FUNCTION}.*"], auto_attach=True)
        spec["capability_specs"] = [dict(CONTRACT, build_budget_usd=1.0)]
        drop(home, signed(key, body_id, "MISSION", spec))
        clock = body.clock
        for _ in range(8):
            clock.advance(31)
            body.tick()
        assert body.registry.state[cid] == "ATTACHED"
        assert len(builder.calls) == calls and len(body.journal.replay("deficit.opened")) == deficits
        observed = [e.payload for e in body.journal.replay("mission.observed") if e.payload["mission_id"] == "m:big"]
        assert observed and all(p.get("failure_class") != "executor_error" for p in observed)
    finally:
        body.close()


def test_build_spend_counts_against_the_signed_light_cone_budget(tmp_path):
    """Second review (spend 1): the build budget is carved from the light-cone budget, but only action
    spend reached the budget gate; a mission could spend its budget on builds and then the whole budget
    again on paid actions without an ask. Build spend now counts against the cone."""
    from tests.greg_fixtures import note_check, workspace, write_strategy

    class PaidBuilder(builders.StaticBuilder):
        def build(self, request, feedback=None):
            return {**super().build(request, feedback), "cost_usd": 0.9}

    home, key, body_id, data = make_body(tmp_path)
    doc = data / "FIRST_MISSION.md"
    doc.write_text("# Runbook\n- [x] install\n- [ ] enroll key\n  - [ ] load launchd\n* [ ] accept closure\n")
    note = workspace(home, "m:both") / "c.txt"
    counted = {"check_id": "counted", "description": "open steps known",
               "sensor": {"function": FUNCTION, "params": {"path": str(doc)}, "target": "fs:FIRST_MISSION.md"},
               "predicate": {"op": "equals", "field": "unchecked", "value": 3}}
    spec = mission("m:both", checks=[counted, note_check("note", note, "ok")],
                   strategies=[write_strategy("w", "c.txt", "ok", ["note"], cost_usd=1.0)],
                   capabilities=["fs.read", "fs.write", f"built.{FUNCTION}.*"], budget=1.0, auto_attach=True)
    spec["capability_specs"] = [dict(CONTRACT, build_budget_usd=1.0)]
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    body = Body(home, clock=clock, builder=PaidBuilder(GOOD, identity="paid")).open()
    try:
        body.boot()
        for _ in range(8):
            clock.advance(30)
            body.tick()
        m = body.engine.book.missions["m:both"]
        assert m.spent_usd == pytest.approx(0.9)                       # the build, booked on the cone
        assert not [a for a in (e.payload for e in body.journal.replay("mission.action"))
                    if a["status"] == "DONE" and a.get("cost_usd")]   # the paid action did not slip past it
        assert "APPROVAL" in [e.payload["kind"] for e in body.journal.replay("decision.requested")]
    finally:
        body.close()


class _PaidBuilder(builders.StaticBuilder):
    def build(self, request, feedback=None):
        return {**super().build(request, feedback), "cost_usd": 0.30}


def test_an_outage_before_a_build_pays_for_nothing_and_the_build_runs_once_the_host_is_back(tmp_path, monkeypatch):
    """Third review (typed failures): an outage during builder verification failed each paid candidate,
    paid for a second, then asked the founder; the mission stayed blocked after the host returned."""
    from greg.capabilities import CapabilityError
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _mission(data)))
    builder = _PaidBuilder(GOOD, GOOD, GOOD, GOOD, identity="paid")
    real = builders.run_isolated

    def down(argv, **kw):
        raise CapabilityError("network isolation unavailable; command refused", failure_class="transient")

    monkeypatch.setattr(builders, "run_isolated", down)
    body, states = _run(home, builder, ticks=3)
    try:
        assert not body.journal.replay("genesis.built") and not body.journal.replay("genesis.verified")
        monkeypatch.setattr(builders, "run_isolated", real)
        clock = body.clock
        for _ in range(6):
            clock.advance(600)
            states.append(body.tick()["missions"][0]["state"])
        assert "ACHIEVED" in states
        assert [e.payload["cost_usd"] for e in body.journal.replay("genesis.built")] == [0.30]
        assert "CAPABILITY_ATTACH" not in [e.payload["kind"] for e in body.journal.replay("decision.requested")]
    finally:
        body.close()


def test_a_paid_candidate_an_outage_left_unjudged_is_judged_later_and_never_paid_for_again(tmp_path, monkeypatch):
    from greg.capabilities import CapabilityError
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _mission(data)))
    builder = _PaidBuilder(GOOD, GOOD, GOOD, GOOD, identity="paid")
    real, calls = builders.verify, []

    def outage_once(path, vectors):
        calls.append(path)
        if len(calls) == 1:
            raise CapabilityError("the isolated verifier did not finish within 10s", failure_class="transient")
        return real(path, vectors)

    monkeypatch.setattr(builders, "verify", outage_once)
    body, states = _run(home, builder, ticks=1)
    try:
        assert len(body.journal.replay("genesis.built")) == 1 and not body.journal.replay("genesis.verified")
        clock = body.clock
        for _ in range(6):
            clock.advance(600)
            states.append(body.tick()["missions"][0]["state"])
        assert "ACHIEVED" in states
        assert len(builder.calls) == 1 and len(body.journal.replay("genesis.built")) == 1    # paid once
        assert [e.payload["passed"] for e in body.journal.replay("genesis.verified")] == [True]
    finally:
        body.close()


def test_a_candidate_that_loops_is_judged_failed_by_its_cpu_limit_not_deferred_as_an_outage(tmp_path):
    loop = "def run(text):\n    while True:\n        pass\n"
    path = tmp_path / "candidate.py"
    path.write_text(loop)
    passed, report = builders.verify(path, CONTRACT["examples"])
    assert passed is False and "exited" in report["failures"][0]["error"]


class _CapBillingBuilder(builders.StaticBuilder):
    """Bills exactly the bound it is given (worst case)."""
    max_budget_usd = 0.5

    def build(self, request, feedback=None):
        return {**super().build(request, feedback), "cost_usd": self.max_budget_usd}


def test_a_build_after_a_paid_action_is_bounded_by_what_the_cone_has_left(tmp_path):
    """Third review (spend): build spend was booked on the cone but never bounded by it, so a build after a
    paid action overspent the cone and every free sensor was then refused (a SENSOR_SCOPE stall)."""
    from tests.greg_fixtures import note_check, workspace, write_strategy
    home, key, body_id, data = make_body(tmp_path)
    doc = data / "FIRST_MISSION.md"
    doc.write_text("# Runbook\n- [x] install\n- [ ] enroll key\n  - [ ] load launchd\n* [ ] accept closure\n")
    note = workspace(home, "m:order") / "c.txt"
    counted = {"check_id": "counted", "description": "open steps known",
               "sensor": {"function": FUNCTION, "params": {"path": str(doc)}, "target": "fs:FIRST_MISSION.md"},
               "predicate": {"op": "equals", "field": "unchecked", "value": 3}}
    spec = mission("m:order", checks=[note_check("note", note, "ok"), counted],
                   strategies=[write_strategy("w", "c.txt", "ok", ["note"], cost_usd=0.8)],
                   capabilities=["fs.read", "fs.write", f"built.{FUNCTION}.*"], budget=1.0, auto_attach=True,
                   closure={"kind": "infinite", "ladder": [["note"], ["note", "counted"]]})
    spec["capability_specs"] = [dict(CONTRACT, build_budget_usd=0.5)]
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    body = Body(home, clock=clock, builder=_CapBillingBuilder(GOOD, identity="paid")).open()
    try:
        body.boot()
        for _ in range(12):
            clock.advance(60)
            body.tick()
        m = body.engine.book.missions["m:order"]
        assert [e.payload["cost_usd"] for e in body.journal.replay("genesis.built")] == [pytest.approx(0.2)]
        assert m.spent_usd == pytest.approx(1.0)
        assert "SENSOR_SCOPE" not in [e.payload["kind"] for e in body.journal.replay("decision.requested")]
    finally:
        body.close()


def test_an_overspent_cone_still_observes_its_checks_for_free():
    from greg.lightcone import LightCone
    cone = LightCone.from_dict({"capabilities": ["fs.read", "fs.write"], "targets": ["workspace:*"],
                                "max_consequence_class": "internal_write", "budget_usd": 1.0,
                                "horizon": "2099-01-01T00:00:00Z"})
    assert cone.admits(capability="fs.read", target="workspace:x", consequence_class="read_only", cost_usd=0.0,
                       spent_usd=1.9) == []
    assert cone.admits(capability="fs.write", target="workspace:x", consequence_class="internal_write", cost_usd=0.0,
                       spent_usd=1.9)                                  # a write is still refused
    assert cone.admits(capability="fs.read", target="workspace:x", consequence_class="read_only", cost_usd=0.1,
                       spent_usd=1.9)                                  # so is a paid read


def test_a_re_judged_candidate_keeps_its_attempt_so_an_outage_never_buys_a_third_build(tmp_path, monkeypatch):
    """Fix verification (closure 1): the re-judged candidate took a fresh slot of the two-attempt loop, so an
    outage while judging attempt 2 bought a third paid build without asking the founder."""
    from greg.capabilities import CapabilityError
    wrong2 = "def run(text):\n    return text.count('[ ]') + 2\n"
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _mission(data)))
    builder = _PaidBuilder(WRONG, wrong2, GOOD, identity="paid")
    real, judged = builders.verify, []

    def outage_on_wrong2(path, vectors):
        judged.append(path.read_text())
        if path.read_text() == wrong2 and judged.count(wrong2) == 1:
            raise CapabilityError("the isolated verifier did not finish within 10s", failure_class="transient")
        return real(path, vectors)

    monkeypatch.setattr(builders, "verify", outage_on_wrong2)
    body, states = _run(home, builder, ticks=1)
    try:
        clock = body.clock
        for _ in range(6):
            clock.advance(600)
            states.append(body.tick()["missions"][0]["state"])
        built = [(e.payload["attempt"], e.payload["cost_usd"]) for e in body.journal.replay("genesis.built")]
        assert built == [(1, 0.30), (2, 0.30)] and len(builder.calls) == 2
        assert "CAPABILITY_ATTACH" in [e.payload["kind"] for e in body.journal.replay("decision.requested")]
    finally:
        body.close()


def test_a_candidate_that_hangs_while_the_host_is_healthy_is_judged_failed(tmp_path, monkeypatch):
    """Fix verification (closure 1): a candidate that blocks without using CPU never meets its CPU limit; the
    whole-run timeout was read as a host outage, so it was never judged. A healthy host makes it the candidate's."""
    import subprocess
    path = tmp_path / "candidate.py"
    path.write_text(GOOD)

    def hangs(source_path, inputs, **kw):
        raise subprocess.TimeoutExpired(["harness"], builders.RUN_TIMEOUT)

    monkeypatch.setattr(builders, "execute", hangs)
    passed, report = builders.verify(path, CONTRACT["examples"])
    assert passed is False and "while the host was healthy" in report["failures"][0]["error"]


def test_a_build_and_the_paid_act_it_enables_are_admitted_against_one_cone(tmp_path):
    """Fix verification (closure 6): the act after a same-step build was admitted on the spend read before
    the build, so build plus act overspent the cone with no approval."""
    home, key, body_id, data = make_body(tmp_path)
    doc = data / "FIRST_MISSION.md"
    doc.write_text("# Runbook\n- [ ] one\n")
    check = {"check_id": "counted", "description": "count", "sensor": {"capability": "fs.read",
             "params": {"path": str(doc)}, "target": "fs:FIRST_MISSION.md"},
             "predicate": {"op": "equals", "field": "never", "value": 1}}
    strategy = {"action_id": "compute", "function": FUNCTION, "target": "fs:FIRST_MISSION.md",
                "params": {"path": str(doc)}, "advances": ["counted"], "rationale": "count", "cost_usd": 0.8}
    spec = mission("m:same-step", checks=[check], strategies=[strategy], ceiling="read_only", budget=1.0,
                   capabilities=["fs.read", f"built.{FUNCTION}.*"], auto_attach=True)
    spec["capability_specs"] = [dict(CONTRACT, build_budget_usd=0.5)]
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    body = Body(home, clock=clock, builder=_CapBillingBuilder(GOOD, identity="paid")).open()
    try:
        body.boot()
        for _ in range(4):
            clock.advance(60)
            body.tick()
        m = body.engine.book.missions["m:same-step"]
        assert m.spent_usd <= m.cone.budget_usd + 1e-9
        assert "APPROVAL" in [e.payload["kind"] for e in body.journal.replay("decision.requested")]
    finally:
        body.close()


def test_a_paid_candidate_that_used_the_whole_budget_is_still_judged_after_an_outage(tmp_path, monkeypatch):
    """Fix verification (regressions): the budget gates ran before pending candidates were judged, so a
    candidate whose own bill used up the budget was never judged after an outage."""
    from greg.capabilities import CapabilityError

    class WholeBudget(builders.StaticBuilder):
        max_budget_usd = 1.0

        def build(self, request, feedback=None):
            return {**super().build(request, feedback), "cost_usd": self.max_budget_usd}

    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _mission(data)))
    builder = WholeBudget(GOOD, GOOD, identity="paid")
    real, calls = builders.verify, []

    def outage_once(path, vectors):
        calls.append(path)
        if len(calls) == 1:
            raise CapabilityError("the isolated verifier did not finish within 10s", failure_class="transient")
        return real(path, vectors)

    monkeypatch.setattr(builders, "verify", outage_once)
    body, states = _run(home, builder, ticks=1)
    try:
        clock = body.clock
        for _ in range(6):
            clock.advance(600)
            states.append(body.tick()["missions"][0]["state"])
        assert "ACHIEVED" in states and len(builder.calls) == 1
        assert [e.payload["passed"] for e in body.journal.replay("genesis.verified")] == [True]
    finally:
        body.close()


def test_a_timed_out_built_run_leaves_no_process_behind(tmp_path):
    """Fix verification (closure 1): the timeout killed only the stdin wrapper, so a candidate's harness that
    hung kept running (one orphan per retry). The whole process group now ends with the run."""
    import subprocess
    import time as _time
    import uuid
    marker = f"greg-orphan-probe-{uuid.uuid4().hex}"
    with pytest.raises(subprocess.TimeoutExpired):
        builders._run_with_stdin([sys.executable, "-c", f"import time  # {marker}\ntime.sleep(60)"],
                                 cwd=tmp_path, data=b"{}", timeout=1)

    def alive():
        found = []
        for proc in Path("/proc").iterdir():
            try:
                if proc.name.isdigit() and marker in (proc / "cmdline").read_bytes().decode(errors="replace") \
                        and (proc / "stat").read_text().rsplit(")", 1)[1].split()[0] != "Z":
                    found.append(proc.name)
            except OSError:
                continue
        return found

    deadline = _time.monotonic() + 3
    while alive() and _time.monotonic() < deadline:
        _time.sleep(0.05)
    assert not alive()
