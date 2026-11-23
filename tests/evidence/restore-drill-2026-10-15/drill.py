"""The restore drill after the change, checked against THRESHOLDS.md (run from the repository root).

Two parts:

- **Authority:** the scenario of reproduce.py, restored with ``greg.recovery.restore_body``.
- **Recovery time:** a body grown past 200 ledger records, seeded, lost, then restored, verified and booted by the
  wall clock.

Every key is a per-test key, not Alfonso's.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0, os.getcwd())
sys.path.insert(0, str(Path(__file__).parent))
from foundry.systems import seed                                                       # noqa: E402
from greg.body import Body                                                              # noqa: E402
from greg.founder import sign_command                                                   # noqa: E402
from greg.recovery import restore_body                                                  # noqa: E402
from reproduce import FIRST, SECOND, asks, gated, lose_the_machine, original, writes  # noqa: E402
from tests.greg_fixtures import Clock, make_body                                        # noqa: E402


def authority(tmp: Path) -> dict:
    o = original(tmp)
    lose_the_machine(o)
    clock = o["clock"]
    clock.advance(60)
    report = restore_body(o["store"], o["seed"], o["home"], clock=clock)
    sign = lambda k, kind, body: sign_command(k, kind, body, body_id=o["body_id"], now=clock())   # noqa: E731
    out = {"recovery_point": report["recovery_point"], "voided": report["voided"],
           "witness_key": report["witness_key"]}
    with Body(o["home"], clock=clock) as body:
        out["head_is_the_recovery_point"] = report["ledger_head_at_recovery_point"] == o["backed_up_head"]
        body.boot()
        clock.advance(30)
        body.tick()
        out["actions_while_held"] = writes(body, FIRST)
        try:
            out["replayed_second_mission"] = body.apply(o["second"])["status"]
        except Exception as exc:                                                         # noqa: BLE001
            out["replayed_second_mission"] = f"refused: {exc}"[:200]
        out["revoked_phone_delegated"] = o["phone_id"] in body.device_keys()
        try:
            body.apply(sign(o["phone"], "BODY_RESUME", {}))
            out["phone_resume"] = "APPLIED"
        except Exception as exc:                                                         # noqa: BLE001
            out["phone_resume"] = f"refused: {exc}"[:160]
        clock.advance(1)
        out["founder_resume"] = body.apply(sign(o["key"], "BODY_RESUME", {}))["status"]
        clock.advance(30)
        body.tick()
        out["first_writes_after_resume"] = writes(body, FIRST)
        fresh = [a for a in asks(body, FIRST) if a["request_id"] not in report["voided"]["approvals"]]
        out["asked_again"] = len(fresh)
        if fresh:
            clock.advance(1)
            body.apply(sign(o["key"], "DECISION", {"request_id": fresh[0]["request_id"], "answer": "approve",
                                                   "reason": "re-decided after the restore"}))
            clock.advance(30)
            body.tick()
            out["first_writes_after_redecision"] = writes(body, FIRST)
        out["second_mission_present"] = SECOND in body.engine.book.missions
        out["chain_verifies"] = body.ledger.verify_chain()[0]
    return out


def recovery_time(tmp: Path, records: int = 200) -> dict:
    home, key, body_id, _ = make_body(tmp)
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        n = 0
        while len(body.ledger.records) < records:
            body.journal.record("drill.filler", {"n": n}, key=n)
            n += 1
        size = len(body.ledger.records)
    made = seed.make_seed(home, tmp / "seed-store")
    home.rename(home.parent / "lost-machine")
    started = time.monotonic()
    report = restore_body(tmp / "seed-store", made["seed"], home)
    with Body(home) as body:
        body.boot()
        booted = body.paused()
    return {"ledger_records": size, "restore_verify_boot_seconds": round(time.monotonic() - started, 3),
            "restore_seconds_reported": report["recovery_seconds"], "held_after_boot": booted,
            "threshold_seconds": 60}


def detection(tmp: Path) -> dict:
    """A tampered object or manifest is refused before any body exists."""
    from foundry.systems import cas
    out = {}
    home, *_ = make_body(tmp / "a")
    with Body(home) as body:
        body.boot()
    made = seed.make_seed(home, tmp / "store")
    manifest = json.loads(cas.get(tmp / "store", made["seed"]))
    ledger_object = cas._path(tmp / "store", manifest["files"]["ledger.jsonl"])
    original_bytes = ledger_object.read_bytes()
    ledger_object.write_bytes(original_bytes.replace(b'"seq": 1', b'"seq": 9', 1))
    try:
        restore_body(tmp / "store", made["seed"], tmp / "t1" / "body")
        out["tampered_object"] = "booted"
    except Exception as exc:                                                             # noqa: BLE001
        out["tampered_object"] = f"refused: {type(exc).__name__}"
    ledger_object.write_bytes(original_bytes)
    forged = dict(manifest, ledger_head="sha256:" + "0" * 64)
    forged_address = cas.put(tmp / "store", json.dumps(forged, sort_keys=True).encode())
    try:
        restore_body(tmp / "store", forged_address, tmp / "t2" / "body")
        out["head_mismatch"] = "booted"
    except Exception as exc:                                                             # noqa: BLE001
        out["head_mismatch"] = f"refused: {type(exc).__name__}: {str(exc)[:80]}"
    out["witness_key_written_after_refusal"] = (tmp / "t2" / "body" / "witness.key").exists()
    return out


if __name__ == "__main__":
    tmp = Path(tempfile.mkdtemp(prefix="greg-drill-"))
    for part in ("authority", "rto", "detection/a"):
        (tmp / part).mkdir(parents=True)
    print(json.dumps({"authority": authority(tmp / "authority")}, sort_keys=True))
    print(json.dumps({"recovery_time": recovery_time(tmp / "rto")}, sort_keys=True))
    print(json.dumps({"detection": detection(tmp / "detection")}, sort_keys=True))
