"""Mission H (fault recovery), acceptance gap H.G7: the Body is killed while Capability Genesis builds a capability.

A founder-signed mission needs a function the Body does not have (markdown.unchecked_count). Genesis opens a
CapabilityDeficit and commissions the residual capability from a builder against the founder-frozen contract,
verifies it against held-out vectors, registers it VERIFIED and attaches it under the mission's signed read-only
auto_attach. The Body runs the canonical main loop (Body.run, what `greg run` runs) with a stand-in for a paid
coding agent: each call is bounded by the per-call ceiling Genesis gives it (``max_budget_usd``) and reports its
own cost, which differs per call as a real agent's does. The driver stops the Body at one point of the build,
where the test SIGKILLs it, then starts it again:

- in-build: inside the builder's call, before any source came back (its spend is unknown);
- in-verify: the source came back and was recorded; the held-out verification has not finished (the restart
  judges that paid candidate rather than calling the builder again);
- before-attach: verified and registered VERIFIED; not yet attached;
- before-resolve: attached; the deficit not yet recorded resolved.

What must hold: no capability is attached or used unless the frozen oracle passed it (nothing half-built is
attached, before or after the restart); the deficit is opened once and reused across the restart, never
duplicated; every builder call is charged exactly once, an interrupted one at the ceiling it was given (its spend
was never reported), so the books never undercount what the founder's signed build budget paid for; the retry
stays inside that budget; the original mission then closes and is appraised VERIFIED. A last case interrupts
every build: the retries stop when the signed budget is reserved, no builder is called again, the deficit stays
open and the founder is asked.

The founder key is a per-test Ed25519 key, not Alfonso's; the builder is a test double.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

from greg import sop
from greg.body import observe
from tests.greg_fixtures import drop, make_body, mission, signed

ROOT = Path(__file__).resolve().parents[2]
FUNCTION = "markdown.unchecked_count"
GOOD = ("import re\n\ndef run(text):\n"
        "    return len(re.findall(r'^[ \\t]*[-*+] \\[ \\]', text, re.M))\n")
# The founder-signed build budget and the agent's own per-call ceiling. The ceiling is more than the budget left
# once one call is reserved at it (1.00 - 0.60 = 0.40), so a retry's ceiling shows whether the interrupted call
# was reserved: 0.40 if it was, 0.60 if it was booked at $0.
BUILD_BUDGET, CEILING = 1.00, 0.60
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
    "build_budget_usd": BUILD_BUDGET}

DRIVER = '''
import json, os, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from greg import builders
from greg.body import Body
from greg.journal import Journal

home, control, source = Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
calls = control / "calls"
current = {"step": None}


def stop_here(name):
    tmp = control / ("." + name)
    tmp.write_text(str(os.getpid()))
    tmp.replace(control / name)
    time.sleep(3600)                                   # the test SIGKILLs the Body here


class PaidAgent:
    """A paid coding agent's stand-in: bounded per call by max_budget_usd (Genesis sets it); its cost varies."""
    identity = "test-agent"

    def __init__(self):
        self.max_budget_usd = float(sys.argv[5])

    def build(self, request, feedback=None):
        n = (len(calls.read_text().splitlines()) if calls.exists() else 0) + 1
        with calls.open("a") as f:
            f.write(json.dumps({"call": n, "pid": os.getpid(), "ceiling": self.max_budget_usd}) + "\\n")
        plan = (control / "plan").read_text().split()
        current["step"] = plan[min(n, len(plan)) - 1]
        if current["step"] == "in-build":
            stop_here(f"stopped-{n}")
        return {"source": source, "builder": "test-agent", "prompt_sha256": "sha256:" + "0" * 64,
                "cost_usd": round(0.30 + 0.01 * n, 2)}


verify, record = builders.verify, Journal.record


def stopping_verify(path, vectors):
    if current["step"] == "in-verify":
        stop_here("stopped-verify")
    return verify(path, vectors)


def stopping_record(self, kind, data, **kwargs):
    if current["step"] == "before-attach" and kind == "capability.state" and data.get("state") == "ATTACHED":
        stop_here("stopped-attach")
    if current["step"] == "before-resolve" and kind == "deficit.resolved":
        stop_here("stopped-resolve")
    return record(self, kind, data, **kwargs)


builders.verify, Journal.record = stopping_verify, stopping_record
sys.exit(Body(home, builder=PaidAgent()).run(tick_seconds=0.2))
'''


def start(tmp_path: Path, home: Path, control: Path) -> subprocess.Popen:
    driver = tmp_path / "driver.py"
    driver.write_text(DRIVER)
    return subprocess.Popen([sys.executable, str(driver), str(ROOT), str(home), str(control), GOOD, str(CEILING)],
                            cwd=ROOT, stdout=(tmp_path / "body.log").open("a"), stderr=subprocess.STDOUT,
                            env={**os.environ, "PYTHONPATH": str(ROOT)})


def kill(body: subprocess.Popen) -> None:
    if body.poll() is None:
        body.send_signal(signal.SIGKILL)
    body.wait(timeout=20)


def events(home: Path, prefix: str) -> list[dict]:
    with observe(home, actor="spiffe://uniimente.internal/greg/genesis-kill-test") as journal:
        return [e.payload for e in journal.replay(prefix)]


def wait_for(predicate, *, timeout=60, what="condition"):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            value = predicate()
        except (FileNotFoundError, json.JSONDecodeError, ValueError, KeyError):
            value = None
        if value:
            return value
        time.sleep(0.1)
    raise AssertionError(f"timed out waiting for {what}")


def more_ticks(home: Path, count: int = 5) -> None:
    """Return once the Body wrote its heartbeat ``count`` more times (once per tick), however long that takes."""
    seen = set()

    def advanced():
        seen.add(json.loads((home / "heartbeat.json").read_text())["at"])
        return len(seen) > count
    wait_for(advanced, what=f"{count} more ticks of the Body")


def builder_calls(control: Path) -> list[dict]:
    path = control / "calls"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def setup(tmp_path: Path, plan: list[str]):
    home, key, body_id, data = make_body(tmp_path)
    control = tmp_path / "control"
    control.mkdir()
    (control / "plan").write_text(" ".join(plan))
    doc = data / "RUNBOOK.md"
    doc.write_text("# Runbook\n- [x] install\n- [ ] enroll key\n  - [ ] load launchd\n* [ ] accept closure\n")
    check = {"check_id": "open-items-counted", "description": "the number of open runbook steps is known",
             "sensor": {"function": FUNCTION, "params": {"path": str(doc)}, "target": "fs:RUNBOOK.md"},
             "predicate": {"op": "equals", "field": "unchecked", "value": 3}}
    spec = mission("m:runbook", checks=[check], strategies=[], ceiling="read_only", budget=BUILD_BUDGET,
                   capabilities=["fs.read", f"built.{FUNCTION}.*"], auto_attach=True)
    spec["capability_specs"] = [CONTRACT]
    drop(home, signed(key, body_id, "MISSION", spec))
    return home, control


def books(home: Path) -> dict:
    """What the ledger charges against the signed build budget: every build that reported its cost, and every
    build that started and never reported one, at the ceiling it was given."""
    started = events(home, "genesis.build_started")
    built = {b["build"]: b for b in events(home, "genesis.built")}
    settled = built.keys() | {f["build"] for f in events(home, "genesis.build_failed")}
    return {"started": started, "built": built,
            "interrupted": [s for s in started if s["build"] not in settled],
            "charged": round(sum(b["cost_usd"] for b in built.values())
                             + sum(s["reserved_usd"] for s in started if s["build"] not in settled), 2)}


def sop_usage(home: Path) -> dict:
    with observe(home, actor="spiffe://uniimente.internal/greg/genesis-kill-test") as journal:
        return sop.model_usage(journal)


def nothing_half_built_attached(home: Path) -> None:
    """Every built capability registered or attached is one the frozen oracle passed, byte for byte."""
    passed = {v["capability_id"].split(":", 1)[1] for v in events(home, "genesis.verified") if v["passed"]}
    registered = {r["manifest"]["capability_id"]: r["manifest"]["provenance"]["source_sha256"]
                  for r in events(home, "capability.registered") if r["manifest"]["provider"].startswith("built:")}
    assert set(registered.values()) <= passed
    for state in events(home, "capability.state"):
        if state["capability_id"].startswith("built.") and state["state"] in ("ATTACHED", "VERIFIED"):
            assert state["capability_id"] in registered


# in-verify: the source came back, was billed and recorded; the restart judges that paid candidate against the frozen
# oracle instead of paying a builder again (greg/genesis.py _unjudged_builds), so one builder call, not two.
@pytest.mark.parametrize("point, calls_expected", [("in-build", 2), ("in-verify", 1), ("before-attach", 1),
                                                  ("before-resolve", 1)],
                         ids=["in-build", "in-verify", "before-attach", "before-resolve"])
def test_a_body_killed_mid_build_attaches_nothing_half_built_and_charges_each_build_once(tmp_path, point,
                                                                                          calls_expected):
    home, control = setup(tmp_path, [point, "ok"])
    stop = {"in-build": "stopped-1", "in-verify": "stopped-verify", "before-attach": "stopped-attach",
            "before-resolve": "stopped-resolve"}[point]
    body = start(tmp_path, home, control)
    try:
        wait_for(lambda: (control / stop).exists(), what=f"the Body stopped {point}")
        kill(body)
        before = {kind: events(home, kind) for kind in ("deficit.opened", "deficit.resolved", "genesis.verified",
                                                        "capability.registered", "capability.state")}
        assert len(before["deficit.opened"]) == 1 and before["deficit.resolved"] == []
        attached = [s for s in before["capability.state"] if s["state"] == "ATTACHED"]
        assert attached == [] if point != "before-resolve" else len(attached) == 1
        registered = before["capability.registered"]
        assert (registered == []) == (point in ("in-build", "in-verify"))
        assert before["genesis.verified"] == [] if point in ("in-build", "in-verify") else \
            [v["passed"] for v in before["genesis.verified"]] == [True]
        nothing_half_built_attached(home)

        body = start(tmp_path, home, control)
        wait_for(lambda: events(home, "mission.achieved"), what="the original mission closing")
        [appraisal] = wait_for(lambda: events(home, "mission.appraised"), what="its appraisal")
        assert body.poll() is None
    finally:
        kill(body)

    calls = builder_calls(control)
    assert len(calls) == calls_expected
    assert calls[0]["ceiling"] == CEILING
    ledger = books(home)
    assert len(ledger["started"]) == len(calls), "every builder call is on the books"
    assert len(ledger["built"]) == len(calls) - (point == "in-build"), "every reported cost is booked once"
    assert [s["build"] for s in ledger["interrupted"]] == ([1] if point == "in-build" else [])
    assert [s["reserved_usd"] for s in ledger["interrupted"]] == ([CEILING] if point == "in-build" else [])
    assert ledger["charged"] <= BUILD_BUDGET
    if point == "in-build":   # the retry was bounded by what the interrupted build's reservation left
        assert calls[1]["ceiling"] == round(BUILD_BUDGET - CEILING, 2) < CEILING
        usage = sop_usage(home)   # mission cost measurement sees the interrupted call at its reservation
        assert usage["model_calls"] == 2 and usage["model_cost_usd"] == ledger["charged"]
        assert usage["cost_known"] is False, "what the interrupted call really spent is unknown"
    assert len(events(home, "deficit.opened")) == 1, "the open deficit is reused across the restart"
    nothing_half_built_attached(home)
    built = hashlib.sha256(GOOD.encode()).hexdigest()
    attached = [s for s in events(home, "capability.state") if s["state"] == "ATTACHED"]
    assert [s["capability_id"] for s in attached] == [f"built.{FUNCTION}.{built[:12]}"]
    resolved = events(home, "deficit.resolved")
    assert [r["capability_id"] for r in resolved] == [attached[0]["capability_id"]]
    assert appraisal["verdict"] == "VERIFIED"
    with observe(home) as journal:
        assert journal.ledger.verify_chain()[0]
        order = [e.type for e in journal.replay()]
    # the deficit closes before the mission it served, so the closure counts as formed by genesis (greg/path.py)
    assert order.index("greg.deficit.resolved") < order.index("greg.mission.achieved")


def test_builds_interrupted_every_time_stop_at_the_signed_budget_and_ask_the_founder(tmp_path):
    home, control = setup(tmp_path, ["in-build"])
    body = None
    try:
        boots = 0
        while True:
            n = len(builder_calls(control)) + 1     # before the start: the body may reach the builder at once
            body = start(tmp_path, home, control)
            boots += 1
            outcome = wait_for(lambda: "stopped" if (control / f"stopped-{n}").exists() else
                               [r for r in events(home, "decision.requested") if r["kind"] == "CAPABILITY_ATTACH"],
                               what=f"boot {boots}: a build or the founder ask")
            if outcome != "stopped":
                break
            kill(body)
            assert boots <= 5, "the interrupted builds never stop"
        more_ticks(home)                                # the builder is not called again in 5 more ticks
        assert body.poll() is None
    finally:
        if body is not None:
            kill(body)

    calls = builder_calls(control)
    ledger = books(home)
    assert [round(c["ceiling"], 2) for c in calls] == [0.60, 0.40], "each retry gets only what the books leave"
    assert len(ledger["interrupted"]) == 2 and ledger["built"] == {}
    assert ledger["charged"] == BUILD_BUDGET, "the signed budget is reserved, never exceeded"
    assert any("no founder-signed build budget remains" in r["result"] for r in events(home, "genesis.route"))
    assert len(events(home, "deficit.opened")) == 1 and events(home, "deficit.resolved") == []
    assert events(home, "capability.registered") == [] and events(home, "mission.achieved") == []
    with observe(home) as journal:
        assert journal.ledger.verify_chain()[0]
