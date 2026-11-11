"""Functional reconstitution on one mission: a lost function returns by another mechanism, a completed effect is not
replayed, and a capability the founder detached is not brought back.

The founder's minimum test (2026-11-11), verbatim: "remove a dependency unknown to the repair designer; restore
bounded function using a different permitted mechanism, without replaying completed effects or resurrecting revoked
authority." Earlier tests show each clause alone (test_greg_self_repair.py, test_greg_recombine.py,
test_greg_genesis_restore.py, tests/integration/test_greg_adversarial_machine.py). None shows them together on a
mission that has already completed an effect. These tests add no product code.

One story, on the builder route (no networkx or scipy needed):

1. written        A signed mission needs ``markdown.unchecked_count``. Genesis builds it, attaches it under the
                  mission's signed ``auto_attach``, and the mission's one write step completes.
2. reconstituted  The isolated runtime that runs built code stops offering the ``re`` module, which the serving
                  implementation imports. No repair code names that module: the loss reaches it only as a capability
                  that exits. GREG quarantines it. The screen that judges every candidate refuses a rebuilt copy
                  that needs the same module, and GREG attaches an implementation the changed runtime still permits.
3. revoked        The founder detaches the replacement. The builder can only produce that same implementation again,
                  and the first one is quarantined and cannot run.
4. restarted      The body stops and starts.
5. reattached     The founder signs CAPABILITY_ATTACH for the detached capability.

The last test is a measured defect, kept as a strict expected failure: in a nearby mission shape the completed write
IS dispatched again. The test before it is its control.

Reality tier: an in-process Body in a cloud container, a test clock, a per-test founder key (not Alfonso's), a
deterministic StaticBuilder, built code in real isolated interpreters. No founder device.
"""
from __future__ import annotations

import pytest

from greg import builders
from greg.body import Body
from greg.genesis import AUTO_ATTACH
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy
from tests.unit.test_greg_genesis_builder import CONTRACT, FUNCTION, GOOD

MID = "m:reconstitute"
TICK = 61                                        # one second past the mission's cadence: every tick re-observes
FIRST = GOOD                                     # a regular expression: it imports ``re``
# A different mechanism for the same contract: a line scanner, no regular expression, no import.
SECOND = ("def run(text):\n    count = 0\n    for line in text.split('\\n'):\n        body = line.lstrip(' \\t')\n"
          "        if body[:2] in ('- ', '* ', '+ ') and body[2:5] == '[ ]':\n            count += 1\n"
          "    return count\n")
RUNBOOK = "# Runbook\n- [x] install\n- [ ] enroll key\n  - [ ] load launchd\n* [ ] accept closure\n"


def _function_check(check_id, path, expected):
    return {"check_id": check_id, "description": f"{path.name} has {expected} open steps",
            "sensor": {"function": FUNCTION, "params": {"path": str(path)}, "target": f"fs:{path.name}"},
            "predicate": {"op": "equals", "field": "unchecked", "value": expected}}


def _events(body, kind):
    return [e.payload for e in body.journal.replay(kind)]


def _write_records(body, action):
    """The Gate's own records of one action, through the proposal each write-ahead intent names: a second dispatch
    at another attempt would be counted too."""
    intents = [i for i in _events(body, "mission.dispatching") if i["action_id"] == action]
    proposals = [i["proposal_id"] for i in intents]
    claims = [c.payload for p in proposals for c in body.ledger.select("grant_dispatch", proposal_id=p)]
    return {"intents": len(intents), "claims": len(claims),
            "grants": len([r for r in body.ledger.by_type("event") if r.payload.get("proposal_id") in proposals
                           and r.payload.get("type") == "greg.authority.grant_issued"]),
            "receipts": [r.hash for c in claims for r in body.ledger.select("receipt", grant_id=c["grant_id"])]}


def _record(body, builder, calls, states):
    built = {cid: state for cid, state in body.registry.state.items() if cid.startswith(f"built.{FUNCTION}.")}
    return {"states": list(states), "registry": built,
            "capability_states": [(s["capability_id"], s["state"], s.get("by"))
                                  for s in _events(body, "capability.state")],
            "registered": [(r["manifest"]["capability_id"], r["origin"]["source_sha256"],
                            r["manifest"]["consequence_class"]) for r in _events(body, "capability.registered")],
            "verified": [(v["deficit_id"], v["passed"], (v["report"].get("screen") or []))
                         for v in _events(body, "genesis.verified")],
            "deficits": _events(body, "deficit.opened"), "resolved": _events(body, "deficit.resolved"),
            "routes": [(r["route"], r["result"], r.get("capability_id")) for r in _events(body, "genesis.route")],
            "asks": _events(body, "decision.requested"), "withdrawn": _events(body, "decision.withdrawn"),
            "counted": [(o["passed"], o["capability"]) for o in _events(body, "mission.observed")
                        if o["check_id"] == "open-items-counted"],
            "writes": list(calls), "actions": [(a["action_id"], a["status"], a["attempt"])
                                               for a in _events(body, "mission.action")],
            "gate": _write_records(body, "note"), "builder_calls": [c["feedback"] for c in builder.calls]}


def _open(home, clock, builder, calls):
    body = Body(home, clock=clock, builder=builder).open()
    real = body.registry.adapters["fs.write"]

    def counted(params, ctx):                    # the registered adapter itself, counted: every real write passes here
        calls.append(params["relative_path"])
        return real(params, ctx)
    body.registry.adapters["fs.write"] = counted
    body.boot()
    return body


def _ticks(body, clock, n):
    states = []
    for _ in range(n):
        clock.advance(TICK)
        states.append(body.tick()["missions"][0]["state"])
    return states


def _serving(body):
    found = body.genesis.find_attached(FUNCTION)
    return found.capability_id if found is not None else None


@pytest.fixture(scope="module")
def story(tmp_path_factory):
    """The five moments above, recorded after each. The fixture asserts nothing, and raises nothing under the
    mutants of scripts/ci/check_reconstitution_mutants.py: each test below fails on its own clause."""
    home, key, body_id, data = make_body(tmp_path_factory.mktemp("reconstitution"))
    doc = data / "FIRST_MISSION.md"
    doc.write_text(RUNBOOK)
    spec = mission(MID, checks=[_function_check("open-items-counted", doc, 3),
                                note_check("noted", workspace(home, MID) / "note.txt", "three open steps")],
                   strategies=[write_strategy("note", "note.txt", "three open steps", ["noted"],
                                              requires=["open-items-counted"])],
                   capabilities=["fs.read", "fs.write", f"built.{FUNCTION}.*"], budget=1.0, auto_attach=True,
                   closure={"kind": "infinite", "cadence_seconds": 60})
    spec["capability_specs"] = [dict(CONTRACT)]
    drop(home, signed(key, body_id, "MISSION", spec))
    # The builder repeats the first implementation once, then has one other left and can only repeat that.
    builder = builders.StaticBuilder(FIRST, FIRST, SECOND, SECOND, SECOND, identity="static-test")
    clock, calls, out = Clock(), [], {}
    body = _open(home, clock, builder, calls)
    patch = pytest.MonkeyPatch()
    try:
        out["written"] = _record(body, builder, calls, _ticks(body, clock, 5))
        first = out["first"] = _serving(body)
        # The dependency nobody planned for: built code may no longer import ``re``, here and for the rest of the
        # story. The real isolated interpreter enforces the list it is handed on every run.
        patch.setattr(builders, "ALLOWED_IMPORTS", builders.ALLOWED_IMPORTS - {"re"})
        out["reconstituted"] = _record(body, builder, calls, _ticks(body, clock, 5))
        second = out["second"] = _serving(body)
        if second is not None:
            drop(home, signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": second}))
        out["revoked"] = _record(body, builder, calls, _ticks(body, clock, 6))
        body.close()
        body = _open(home, clock, builder, calls)
        out["restarted"] = _record(body, builder, calls, _ticks(body, clock, 4))
        if second is not None and body.registry.state.get(second) in ("VERIFIED", "DETACHED"):
            drop(home, signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": second}))
        out["reattached"] = _record(body, builder, calls, _ticks(body, clock, 4))
    finally:
        patch.undo()
        body.close()
    return out


ONE_WRITE = {"intents": 1, "claims": 1, "grants": 1}


def test_the_write_step_completed_once_while_the_first_built_capability_served(story):
    written, first = story["written"], story["first"]
    assert first is not None and written["registry"] == {first: "ATTACHED"}
    assert written["counted"] and written["counted"][-1] == (True, first)
    assert written["actions"] == [("note", "DONE", 0)] and written["writes"] == ["note.txt"]
    assert {k: written["gate"][k] for k in ONE_WRITE} == ONE_WRITE and len(written["gate"]["receipts"]) == 1
    assert written["asks"] == [] and written["states"][-1] == "HOLDING", written["states"]


def test_the_lost_function_returns_under_a_different_capability_by_gregs_own_repair(story):
    after, first, second = story["reconstituted"], story["first"], story["second"]
    assert second is not None and second != first                    # a different capability id serves it now
    sources = dict((cid, digest) for cid, digest, _ in after["registered"])
    assert sources[second] != sources[first]                         # and a different implementation, not a copy
    assert after["registry"] == {first: "QUARANTINED", second: "ATTACHED"}
    # GREG's own repair: it quarantined the faulting capability itself and re-formed the function for this mission.
    assert (first, "QUARANTINED", "self-repair (repeated capability fault)") in after["capability_states"]
    repair = [d for d in after["deficits"] if d.get("repair")]
    assert [d["repair"]["capability_id"] for d in repair] == [first]
    assert [(r["deficit_id"], r["capability_id"]) for r in after["resolved"]][-1] == (repair[0]["deficit_id"], second)
    assert after["counted"][-1] == (True, second)                    # the function is back: the check is measured
    assert "REPAIRED" in after["states"] and after["states"][-1] == "HOLDING", after["states"]
    # A different permitted mechanism: the rebuilt copy that still needs the removed module was refused first.
    assert [(passed, screen) for deficit, passed, screen in after["verified"]
            if deficit == repair[0]["deficit_id"]] == [(False, ["import of 're' is not allowed"]), (True, [])]


def test_the_repair_asked_the_founder_nothing_and_stayed_inside_the_signed_scope(story):
    after, second = story["reconstituted"], story["second"]
    assert after["asks"] == []                                       # no founder ask up to here
    assert after["capability_states"][-1] == (second, "ATTACHED", AUTO_ATTACH)       # the signed auto_attach, no other
    assert [klass for cid, _, klass in after["registered"] if cid == second] == ["read_only"]
    assert second.startswith(f"built.{FUNCTION}.")                   # inside the cone's signed capability pattern
    # The builder was told that its predecessor failed in service, then what the screen refused. Two attempts, the
    # most one deficit allows; no third was needed.
    assert len(after["builder_calls"]) == 3 and "failed in service" in after["builder_calls"][1][0]
    assert after["builder_calls"][2] == ["import of 're' is not allowed"]


def test_the_completed_write_is_never_dispatched_again(story):
    """Across the loss, the repair, the founder's detach, a restart and the re-attach: one adapter call, one
    write-ahead intent, one Gate claim, one grant and the same one receipt. This is a write to the body's own
    workspace through its own Gate; nothing here speaks for an effect on another system."""
    receipt = story["written"]["gate"]["receipts"]
    assert len(receipt) == 1
    for moment in ("written", "reconstituted", "revoked", "restarted", "reattached"):
        record = story[moment]
        assert record["writes"] == ["note.txt"], moment
        assert record["actions"] == [("note", "DONE", 0)], moment
        assert {k: record["gate"][k] for k in ONE_WRITE} == ONE_WRITE, moment
        assert record["gate"]["receipts"] == receipt, moment


def test_a_capability_the_founder_detached_is_not_used_though_nothing_else_can_serve(story):
    first, second = story["first"], story["second"]
    for moment in ("revoked", "restarted"):
        record = story[moment]
        assert record["registry"] == {first: "QUARANTINED", second: "DETACHED"}, moment      # nothing else exists
        detached = record["capability_states"].index((second, "DETACHED", "founder command"))
        assert record["capability_states"][detached + 1:] == [], moment          # no state change behind the founder
        # No reading by the detached capability after the last one it gave while attached.
        assert record["counted"] == story["reconstituted"]["counted"], moment
    revoked = story["revoked"]
    # GREG did look for a way: the builder was asked twice more and could only return the detached implementation.
    assert ("builder", "founder-detached; explicit attach required", second) in revoked["routes"]
    assert len(revoked["builder_calls"]) == 5
    assert "detached by the founder" in revoked["builder_calls"][4][0]
    assert story["restarted"]["builder_calls"] == revoked["builder_calls"]       # and not again after the restart


def test_the_mission_asks_and_waits_instead(story):
    first, second = story["first"], story["second"]
    for moment in ("revoked", "restarted"):
        record = story[moment]
        assert [a["kind"] for a in record["asks"]] == ["CAPABILITY_ATTACH"], moment          # one ask, asked once
        ask = record["asks"][0]
        assert ask["authority_requested"]["function"] == FUNCTION
        assert sorted((c["capability_id"], c["state"]) for c in ask["evidence"]["registered"]) == \
            sorted([(first, "QUARANTINED"), (second, "DETACHED")])
        assert record["withdrawn"] == [] and set(record["states"]) <= {"BLOCKED", "WAITING"}, record["states"]


def test_only_the_founders_own_attach_returns_the_detached_capability_to_service(story):
    after, first, second = story["reattached"], story["first"], story["second"]
    assert after["capability_states"][-2:] == [(second, "DETACHED", "founder command"),
                                               (second, "ATTACHED", "founder command")]
    assert after["registry"] == {first: "QUARANTINED", second: "ATTACHED"}
    assert after["counted"][-1] == (True, second) and len(after["counted"]) > len(story["restarted"]["counted"])
    [ask] = after["asks"]                                            # the one ask, now withdrawn as resolved
    assert [w["request_id"] for w in after["withdrawn"]] == [ask["request_id"]]
    assert len(after["builder_calls"]) == 5 and after["states"][-1] == "HOLDING", after["states"]


# -- a measured defect: the completed write is replayed in a nearby mission shape ------------------------------------
def _loss_beside(tmp_path, monkeypatch, *, other_check_fails):
    """The write's own check is read through the formed function. After the write a person appends a line to the
    note (both checks on it still hold). Then the same dependency is removed as in the story above; with
    ``other_check_fails`` an unrelated check with no strategy fails for real in the same pass. Returns the fs.write
    calls, the note's action records, whether the person's line is still in the note, and the tick states after
    the loss. A story that does not reach the loss or the repair is a broken test, not the defect: it fails
    outright (pytest.fail does not raise an AssertionError)."""
    home, key, body_id, data = make_body(tmp_path)
    note = workspace(home, "m:replay") / "note.md"
    (data / "request.txt").write_text("go")
    spec = mission("m:replay", checks=[_function_check("note-open-items", note, 2),
                                       note_check("noted", note, "enroll key"),
                                       note_check("request", data / "request.txt", "go")],
                   strategies=[write_strategy("note", "note.md", "- [ ] enroll key\n- [ ] accept closure\n",
                                              ["note-open-items", "noted"])],
                   capabilities=["fs.read", "fs.write", f"built.{FUNCTION}.*"], budget=1.0, auto_attach=True,
                   closure={"kind": "infinite", "cadence_seconds": 60})
    spec["capability_specs"] = [dict(CONTRACT)]
    drop(home, signed(key, body_id, "MISSION", spec))
    clock, calls = Clock(), []
    body = _open(home, clock, builders.StaticBuilder(FIRST, SECOND, identity="static-test"), calls)
    try:
        before = _ticks(body, clock, 4)
        if before[-1] != "HOLDING" or calls != ["note.md"]:
            pytest.fail(f"the story did not reach a completed write and a holding mission: {before}, {calls}")
        note.write_text(note.read_text() + "- [x] reviewed by a person\n")      # still two open steps
        if _ticks(body, clock, 1) != ["HOLDING"]:
            pytest.fail("the mission did not hold over the note with the person's line")
        monkeypatch.setattr(builders, "ALLOWED_IMPORTS", builders.ALLOWED_IMPORTS - {"re"})
        if other_check_fails:
            (data / "request.txt").write_text("halt")
        states = _ticks(body, clock, 3)
        noted = [o["passed"] for o in _events(body, "mission.observed") if o["check_id"] == "noted"]
        if "REPAIRED" not in states or not all(noted[-3:]):
            pytest.fail(f"the function was not repaired, or the fs.read check on the note stopped passing: {states}")
        return (list(calls), [(a["status"], a["attempt"]) for a in _events(body, "mission.action")
                              if a["action_id"] == "note"], "reviewed by a person" in note.read_text(), states)
    finally:
        body.close()


def test_a_completed_write_is_not_replayed_when_only_the_function_that_reads_it_is_lost(tmp_path, monkeypatch):
    """The control for the defect below: the same loss with every other check passing. SENSOR_RETRY, then REPAIRED."""
    writes, actions, kept, states = _loss_beside(tmp_path, monkeypatch, other_check_fails=False)
    assert writes == ["note.md"] and actions == [("DONE", 0)] and kept, states
    assert states[:2] == ["SENSOR_RETRY", "REPAIRED"], states


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=(
    "measured defect on #196 at 8d205324: a check left unmeasured because its formed sensor capability faulted is "
    "pursued beside another check's real failure, so the completed write that advances it is dispatched again at "
    "attempt 1 (second adapter call, second Gate claim and receipt) and overwrites the file, one pass before "
    "self-repair replaces the capability. greg/missions.py pursues `failing - self.inconclusive`, and a check its "
    "own sensor capability failed to read is not counted as inconclusive. Remove this mark when such a check no "
    "longer rides along with a measured failure."))
def test_a_completed_write_is_not_replayed_when_the_function_that_reads_it_faults_beside_a_real_failure(
        tmp_path, monkeypatch):
    """Smallest reproduction found. The note is on disk with a person's line added, and the fs.read check on it
    still passes. Only the formed capability that counts its open steps fails (it may no longer import ``re``), and
    an unrelated check with no strategy fails for real in the same pass. Observed on 8d205324: states ACTED,
    REPAIRED, BLOCKED; fs.write called twice for note.md; action records note DONE attempt 0 and note DONE attempt
    1; the person's line is gone. Only this assertion may fail: the mark expects an AssertionError and every setup
    problem raises something else."""
    writes, actions, kept, states = _loss_beside(tmp_path, monkeypatch, other_check_fails=True)
    assert writes == ["note.md"] and actions == [("DONE", 0)] and kept, (writes, actions, kept, states)
