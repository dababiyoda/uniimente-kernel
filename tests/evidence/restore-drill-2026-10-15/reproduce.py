"""The defect, reproduced before the change (run from the repository root).

A body's machine is lost and its Institutional Seed is restored on another. The scenario:

1. the original body enrolls a phone, registers a mission whose write needs the founder's approval, and the founder
   approves it;
2. the seed is taken;
3. after the seed, the original executes the approved write, the founder revokes the phone, and the original
   accepts a second mission;
4. the machine is lost (its home is moved aside, kept only to compare), and the seed is restored to the same path
   on the new machine.

At the base the restored body cannot boot: the seed excludes the witness key, and the founder was never given it.
With the key copied by hand, the restored body:
- executes the approved write a second time;
- accepts the second mission's envelope again;
- honours the phone the founder had revoked.

Every key is a per-test key, not Alfonso's.
"""
from __future__ import annotations

from datetime import timedelta
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

sys.path.insert(0, os.getcwd())
from foundry.systems import seed                                                     # noqa: E402
from greg.body import Body, Layout                                                    # noqa: E402
from greg.founder import generate_founder_key, key_id, load_founder_key, sign_command, stamp  # noqa: E402
from tests.greg_fixtures import Clock, make_body, mission, note_check, workspace, write_strategy  # noqa: E402

FIRST, SECOND = "m:restore", "m:second"


def gated(mid: str, home: Path, text: str) -> dict:
    """A mission whose only write lies outside its read-only cone, so it asks the founder first."""
    note = workspace(home, mid) / "n.txt"
    return mission(mid, checks=[note_check("n", note, text)], strategies=[write_strategy("w", "n.txt", text, ["n"])],
                   capabilities=["fs.read"], ceiling="read_only")


def asks(body: Body, mid: str) -> list[dict]:
    return [e.payload for e in body.journal.replay("decision.requested") if e.payload["mission_id"] == mid]


def writes(body: Body, mid: str) -> int:
    return sum(1 for e in body.journal.replay("mission.action")
               if e.payload["mission_id"] == mid and e.payload["status"] == "DONE")


def original(tmp: Path) -> dict:
    """The original body up to the seed, then what it does after the seed."""
    home, key, body_id, _ = make_body(tmp)
    phone_public = generate_founder_key(tmp / "phone.pem", None)
    phone = load_founder_key(tmp / "phone.pem", None)
    clock = Clock()
    sign = lambda k, kind, body: sign_command(k, kind, body, body_id=body_id, now=clock())   # noqa: E731
    with Body(home, clock=clock) as body:
        body.boot()
        body.apply(sign(key, "DEVICE_ENROLL", {"public_key": phone_public, "label": "phone", "kinds": ["DECISION"],
                                               "expires_at": stamp(clock() + timedelta(days=30))}))
        body.apply(sign(key, "MISSION", gated(FIRST, home, "approved once")))
        body.tick()
        [ask] = asks(body, FIRST)
        body.apply(sign(key, "DECISION", {"request_id": ask["request_id"], "answer": "approve",
                                          "reason": "write it once"}))
        backed_up_head = body.ledger.head
    made = seed.make_seed(home, tmp / "seed-store")                    # the backup: approval in, write not yet
    clock.advance(60)
    second = sign(key, "MISSION", gated(SECOND, home, "second"))
    with Body(home, clock=clock) as body:                              # the original keeps running after the seed
        body.tick()
        body.apply(sign(key, "DEVICE_REVOKE", {"device_key_id": key_id(phone_public)}))
        body.apply(second)
        body.tick()
        after = {"first_writes": writes(body, FIRST), "phone_delegated": key_id(phone_public) in body.device_keys()}
    return {"home": home, "key": key, "phone": phone, "phone_id": key_id(phone_public), "body_id": body_id,
            "seed": made["seed"], "store": tmp / "seed-store", "second": second, "clock": clock,
            "backed_up_head": backed_up_head, "original_after_seed": after}


def lose_the_machine(o: dict) -> Path:
    """The original home disappears from its path; it is kept aside only to compare what it did."""
    lost = o["home"].parent / "lost-machine"
    o["home"].rename(lost)
    return lost


def restore_at_base(o: dict) -> dict:
    lost, target = lose_the_machine(o), o["home"]
    out = {"needs_from_founder": seed.restore(o["store"], o["seed"], target)["needs_from_founder"]}
    try:
        with Body(target) as body:
            body.boot()
        out["boots_as_restored"] = True
    except Exception as exc:                                           # noqa: BLE001 - the reported defect
        out["boots_as_restored"] = f"no: {type(exc).__name__}: {exc}"[:200]
        shutil.copyfile(Layout(lost).witness_key, Layout(target).witness_key)   # by hand: never offered
    clock = o["clock"]
    clock.advance(60)
    with Body(target, clock=clock) as body:
        out["head_is_the_backup"] = body.ledger.head == o["backed_up_head"]
        body.boot()
        body.tick()
        out["first_writes_on_restored"] = writes(body, FIRST)
        out["replayed_second_mission"] = body.apply(o["second"])["status"]
        body.tick()
        out["revoked_phone_still_delegated"] = o["phone_id"] in body.device_keys()
        second_asks = asks(body, SECOND)
        if second_asks:
            env = sign_command(o["phone"], "DECISION", {"request_id": second_asks[0]["request_id"],
                                                        "answer": "approve", "reason": "from the revoked phone"},
                               body_id=o["body_id"], now=clock())
            try:
                out["revoked_phone_decision"] = body.apply(env)["status"]
            except Exception as exc:                                   # noqa: BLE001
                out["revoked_phone_decision"] = f"refused: {exc}"[:160]
    return out


if __name__ == "__main__":
    tmp = Path(tempfile.mkdtemp(prefix="greg-restore-"))
    o = original(tmp)
    print(json.dumps({"original_after_seed": o["original_after_seed"]}, sort_keys=True))
    print(json.dumps({"restored": restore_at_base(o)}, sort_keys=True))
