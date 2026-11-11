"""Reviewer's scratch: a completed (or refused) compensation whose capability is attached but unavailable when the
body restarts. The office's precheck answers before the retained receipt is looked for."""
from __future__ import annotations

import pytest

from greg.body import Body
from greg.capabilities import CapabilityManifest
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy

MID = "m:adv3"
BROKEN = {"capability": "fs.write", "params": {"relative_path": "other.txt", "content": "original"},
          "target": "workspace:note.txt"}
RESTORE = {"capability": "fs.write", "params": {"relative_path": "note.txt", "content": "original"},
           "target": "workspace:note.txt"}


class Killed(BaseException):
    pass


def tick(body, clock, n):
    for _ in range(n):
        body.tick()
        clock.advance(1)


def facts(body, kind):
    return [e.payload for e in body.journal.replay(kind) if e.payload.get("mission_id") == MID]


@pytest.mark.parametrize("compensate, kept", [(RESTORE, "positive"), (BROKEN, "negative")])
def test_p9_a_compensation_receipt_retained_before_its_capability_became_unavailable(tmp_path, monkeypatch, capsys,
                                                                                    compensate, kept):
    home, key, body_id, _ = make_body(tmp_path)
    note = workspace(home, MID) / "note.txt"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("original")
    drop(home, signed(key, body_id, "MISSION", mission(
        MID, checks=[note_check("c", note, "final")],
        strategies=[write_strategy("w", "note.txt", "draft", ["c"], compensate=compensate)],
        capabilities=["fs.read", "fs.write"])))
    clock = Clock()
    with Body(home, clock=clock) as body:
        tick(body, clock, 3)
        drop(home, signed(key, body_id, "LIFECYCLE", {"mission_id": MID, "state": "ABANDONED", "reason": "no"}))
        record = body.journal.record

        def dies(name, data, **kw):
            if name == "mission.compensated":
                raise Killed()
            return record(name, data, **kw)
        body.journal.record = dies
        with pytest.raises(Killed):
            tick(body, clock, 3)
        klass = [r.payload["result"]["result_class"] for r in body.ledger.by_type("receipt")][-1]
        claims = len(body.ledger.by_type("grant_dispatch"))
    assert klass == kept
    real = CapabilityManifest.available
    monkeypatch.setattr(CapabilityManifest, "available",
                        lambda self: (False, "binary /usr/bin/x not installed or not executable")
                        if self.capability_id == "fs.write" else real(self))
    with Body(home, clock=clock) as body:
        tick(body, clock, 4)
        comp = [(c["status"], c["reasons"], bool(c["receipt"])) for c in facts(body, "mission.compensated")]
        open_ = [(r["kind"], (r.get("evidence") or {}).get("compensation_failed")) for r in body.engine.book.open_requests()]
        claims_after = len(body.ledger.by_type("grant_dispatch"))
    monkeypatch.undo()
    with Body(home, clock=clock) as body:               # the capability is available again
        tick(body, clock, 4)
        later = [(c["status"], bool(c["receipt"])) for c in facts(body, "mission.compensated")]
    with capsys.disabled():
        print(f"\nP9 kept={kept}: note={note.read_text()!r} compensated={comp} open={open_} claims {claims}->{claims_after} "
              f"| after the capability returned: {later}")
    assert [c[0] for c in comp] == [{"positive": "DONE", "negative": "REFUSED"}[kept]]
