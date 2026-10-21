"""Acceptance C.G6: a Capability Genesis deficit is genuine, never a reflex.

Mission C: "A mission reaches a genuinely missing function." The positive case
(tests/unit/test_greg_missions.py::test_capability_genesis_acquires_installed_tool_and_resumes_mission) shows a
missing hash.sha256 function opening exactly one verified deficit and being acquired. This is its negative control:
once that capability is attached, a second founder-signed mission that needs the same function, and a third that
needs only a builtin, both close with no new deficit, no Genesis route and no new verification, and the second
mission's receipts name the capability already attached.

In-process Body with a test clock (SANDBOX); the founder key is a per-test key, not Alfonso's.
"""
from __future__ import annotations

import hashlib

import pytest

from greg import genesis as genesis_mod
from greg.body import Body
from tests.greg_fixtures import Clock, make_body, mission, note_check
from tests.unit.test_greg_missions import events, run, submit


def digest_check(path, content: bytes) -> dict:
    return {"check_id": "hashed", "description": "digest of evidence known",
            "sensor": {"function": "hash.sha256", "params": {"path": str(path)}, "target": f"fs:{path.name}"},
            "predicate": {"op": "equals", "field": "sha256", "value": hashlib.sha256(content).hexdigest()}}


def test_a_function_already_attached_or_builtin_opens_no_deficit(tmp_path):
    if genesis_mod.installed_binary("sha256sum") is None and genesis_mod.installed_binary("shasum") is None:
        pytest.skip("no sha256 tool installed on this body; genesis would correctly escalate")
    home, key, body_id, data = make_body(tmp_path)
    first, second = data / "evidence.bin", data / "second.bin"
    first.write_bytes(b"founder evidence bytes")
    second.write_bytes(b"other evidence bytes")
    note = data / "note.txt"
    note.write_text("already here")
    scope = dict(capabilities=["fs.read", "acquired.hash.sha256.*"], ceiling="read_only", auto_attach=True)
    submit(home, key, body_id, "MISSION", mission("m:hash", checks=[digest_check(first, b"founder evidence bytes")],
                                                  strategies=[], **scope))
    clock = Clock()
    missions, _ = run(home, clock, ticks=4)
    assert missions["m:hash"].status == "ACHIEVED"
    [opened] = events(home, "deficit.opened")                    # the positive case: one genuine deficit
    routes, verified = len(events(home, "genesis.route")), len(events(home, "genesis.verified"))
    [acquired] = [e["capability_id"] for e in events(home, "deficit.resolved")]
    assert acquired.startswith("acquired.hash.sha256.")

    submit(home, key, body_id, "MISSION", mission("m:hash-again", checks=[digest_check(second, b"other evidence bytes")],
                                                  strategies=[], **scope))
    submit(home, key, body_id, "MISSION", mission("m:builtin", checks=[note_check("n", note, "already here")],
                                                  strategies=[], capabilities=["fs.read"], ceiling="read_only"))
    missions, _ = run(home, clock, ticks=4)
    assert missions["m:hash-again"].status == "ACHIEVED" and missions["m:builtin"].status == "ACHIEVED"
    assert len(events(home, "deficit.opened")) == 1, "a function already attached or builtin opens no deficit"
    assert len(events(home, "genesis.route")) == routes and len(events(home, "genesis.verified")) == verified
    with Body(home) as b:                                       # the second mission was served by the attached one
        observed = [e.payload for e in b.journal.replay("mission.observed") if e.payload["mission_id"] == "m:hash-again"]
        grant = b.ledger.find(observed[-1]["receipt"]).payload["grant_id"]
        [witness] = [r.payload for r in b.ledger.by_type("witness") if r.payload.get("grant_id") == grant]
    assert witness["capability"] == acquired
