"""Genesis self-repair: a formed capability that breaks in service is re-formed and the mission holds.

Reproduced first: a tampered built capability made every later tick raise EventError
(deficit id reused with new content), and a built capability that raised on live input
was only ever escalated to the founder. Both now re-form the function under the same
founder-signed contract and budget, then the ORIGINAL mission re-measures.
"""
import json
import os
from pathlib import Path

from greg import builders
from greg.body import Body
from tests.greg_fixtures import Clock, drop, make_body, signed
from tests.unit.test_greg_genesis_builder import FUNCTION, GOOD, _mission

# Passes every frozen vector (all short) but has a latent bug on longer real input.
BUGGY = ("import re\n\ndef run(text):\n"
         "    if len(text) > 400:\n        raise ValueError('longer than this implementation handles')\n"
         "    return len(re.findall(r'^[ \\t]*[-*+] \\[ \\]', text, re.M))\n")


def _holding(data, **kw):
    spec = _mission(data, **kw)
    spec["closure"] = {"kind": "infinite", "cadence_seconds": 60}
    return spec


def _ticks(body, clock, n, step=120):
    out = []
    for _ in range(n):
        clock.advance(step)
        out.append(body.tick()["missions"][0])
    return out


def _events(body, kind):
    return [e.payload for e in body.journal.replay(kind)]


def test_capability_that_breaks_on_live_input_is_rebuilt_and_the_mission_holds(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _holding(data)))
    builder = builders.StaticBuilder(BUGGY, BUGGY, GOOD, identity="static-test")
    clock = Clock()
    body = Body(home, clock=clock, builder=builder).open()
    body.boot()
    assert "HOLDING" in [r["state"] for r in _ticks(body, clock, 4, 30)]
    first = _events(body, "capability.registered")[0]["manifest"]["capability_id"]

    # The runbook grows past what the first implementation handles; the goal (3 open items) is unchanged.
    doc = data / "FIRST_MISSION.md"
    doc.write_text(doc.read_text() + "".join(f"- [x] done step {i} with a longer description\n" for i in range(12)))
    states = [r["state"] for r in _ticks(body, clock, 6)]
    assert "REPAIRED" in states and states[-1] == "HOLDING", states
    assert not _events(body, "decision.requested")                      # repaired, not escalated

    quarantined = [s for s in _events(body, "capability.state") if s["state"] == "QUARANTINED"]
    assert quarantined[0]["capability_id"] == first and "built capability raised ValueError" in quarantined[0]["why"]
    repair = [d for d in _events(body, "deficit.opened") if d.get("repair")][0]
    assert repair["repair"]["capability_id"] == first
    # The rebuilt BUGGY candidate passes the oracle but is rejected by the live-input replay.
    verdicts = [v for v in _events(body, "genesis.verified") if v["deficit_id"] == repair["deficit_id"]]
    assert [v["passed"] for v in verdicts] == [False, True]
    assert verdicts[0]["report"]["service_replay"]["passed"] is False
    assert verdicts[1]["report"]["service_replay"]["passed"] is True
    # The builder learned how the predecessor failed, never the live input.
    repair_calls = builder.calls[1:]
    assert "failed in service" in repair_calls[0]["feedback"][0]
    assert all("done step" not in json.dumps(c) for c in repair_calls)
    attached = [s for s in _events(body, "capability.state") if s["state"] == "ATTACHED"]
    assert attached[-1]["capability_id"] != first and attached[-1]["deficit_id"] == repair["deficit_id"]
    last = [o for o in _events(body, "mission.observed") if o["check_id"] == "open-items-counted"][-1]
    assert last["passed"] is True
    if os.environ.get("GREG_RECORD_EVIDENCE"):
        out = Path(__file__).resolve().parents[1] / "evidence" / "greg-product"
        out.mkdir(parents=True, exist_ok=True)
        (out / "self-repair-summary.json").write_text(json.dumps({
            "reality": "TESTED: real Body, real journal/ledger, built code in real isolated interpreters; "
                       "deterministic builder; not supervised, not Mac",
            "states_after_breakage": states, "quarantined": quarantined, "repair_deficit": repair,
            "verifications": verdicts, "builder_feedback_on_repair": [c["feedback"] for c in repair_calls],
            "attached": attached, "last_observation": last,
            "decisions_requested": _events(body, "decision.requested")}, indent=1, default=str))
    body.close()

    with Body(home) as reopened:                                        # restart keeps the repaired state
        assert reopened.registry.state[first] == "QUARANTINED"
        assert reopened.registry.state[attached[-1]["capability_id"]] == "ATTACHED"


def test_tampered_capability_is_reformed_after_restart_instead_of_crash_looping(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _holding(data)))
    clock = Clock()
    body = Body(home, clock=clock, builder=builders.StaticBuilder(GOOD)).open()
    body.boot()
    _ticks(body, clock, 4, 30)
    digest = _events(body, "genesis.built")[0]["source_sha256"]
    body.close()
    stored = home / "capabilities" / "built" / f"{digest}.py"
    stored.write_text(stored.read_text() + "\nimport os\n")

    body = Body(home, clock=clock, builder=builders.StaticBuilder(GOOD)).open()
    body.boot()
    states = [r["state"] for r in _ticks(body, clock, 5)]               # previously: EventError on every tick
    assert states[-1] == "HOLDING", states
    opened = _events(body, "deficit.opened")
    assert len(opened) == 2 and opened[1]["repair"]["failure"].startswith("quarantined")
    assert stored.read_text() == GOOD                                   # verified bytes restored ...
    assert list(stored.parent.glob(f"{digest}.py.unverified-*"))       # ... tampered bytes kept as evidence
    body.close()


def test_repairs_share_the_one_signed_build_budget(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    spec = _holding(data, budget=1.0)
    spec["capability_specs"][0]["build_budget_usd"] = 0.05
    drop(home, signed(key, body_id, "MISSION", spec))

    class Costly(builders.StaticBuilder):
        def build(self, request, feedback=None):
            return dict(super().build(request, feedback), cost_usd=0.03)

    builder = Costly(BUGGY, BUGGY, BUGGY, BUGGY, GOOD)
    clock = Clock()
    body = Body(home, clock=clock, builder=builder).open()
    body.boot()
    _ticks(body, clock, 4, 30)
    doc = data / "FIRST_MISSION.md"
    doc.write_text(doc.read_text() + "- [x] a much longer finished step description here\n" * 12)
    states = [r["state"] for r in _ticks(body, clock, 6)]
    assert "REPAIRED" not in states and states[-1] in ("BLOCKED", "WAITING")
    spent = sum(b["cost_usd"] for b in _events(body, "genesis.built"))
    assert spent <= 0.05 + 0.03 + 1e-9                                  # at most one attempt past the cap
    assert any("no founder-signed build budget" in r["result"] for r in _events(body, "genesis.route"))
    request = _events(body, "decision.requested")[-1]
    assert request["kind"] == "CAPABILITY_ATTACH" and request["authority_requested"]["function"] == FUNCTION
    body.close()


def test_a_replacement_is_judged_on_its_own_faults_and_budget_caps_do_not_ratchet(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _holding(data)))

    class Capped(builders.StaticBuilder):
        max_budget_usd = 0.75

    # The replacement also has a (different) latent bug, triggered only by a later, even longer input.
    LATER_BUG = BUGGY.replace("400", "2000")
    builder = Capped(BUGGY, LATER_BUG, GOOD)
    clock = Clock()
    body = Body(home, clock=clock, builder=builder).open()
    body.boot()
    _ticks(body, clock, 4, 30)
    doc = data / "FIRST_MISSION.md"
    doc.write_text(doc.read_text() + "- [x] a finished step with a longer description\n" * 12)
    states = [r["state"] for r in _ticks(body, clock, 4)]
    assert states.count("REPAIRED") == 1 and states[-1] == "HOLDING"
    doc.write_text(doc.read_text() + "- [x] another finished step with a longer description\n" * 40)
    states = [r["state"] for r in _ticks(body, clock, 2)]
    assert states == ["SENSOR_RETRY", "REPAIRED"]    # one fault is not yet a pattern; two of its own are
    states = [r["state"] for r in _ticks(body, clock, 3)]
    assert states[-1] == "HOLDING"
    repairs = [d for d in _events(body, "deficit.opened") if d.get("repair")]
    assert len(repairs) == 2 and repairs[1]["repair"]["capability_id"] != repairs[0]["repair"]["capability_id"]
    assert body.genesis.builder_cap == 0.75 and builder.max_budget_usd <= 0.75
    body.close()
