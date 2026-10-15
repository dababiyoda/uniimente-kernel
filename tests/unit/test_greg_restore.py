"""Directive section 14: restoration from tested backups, against the thresholds declared before the drill.

Each test reproduced a defect before the change (tests/evidence/restore-drill-2026-10-15/reproduction.log). A body
restored from its Institutional Seed could not boot, because the seed excludes the witness key and the founder is
never given it. With the key copied by hand, the restored copy:
- re-executed a write the original already performed on the same approval;
- accepted again a mission envelope the original consumed after the backup;
- honoured a phone the founder had revoked after the backup.

Every key here is a per-test key, not Alfonso's.
"""
from __future__ import annotations

from datetime import timedelta
import json
import os
from pathlib import Path
import time

import pytest

from foundry.systems import cas, seed
from greg.body import Body, Layout
from greg.founder import FounderAuthError, generate_founder_key, key_id, load_founder_key, sign_command, stamp
from greg.missions import MissionError
from greg.recovery import RestoreError, restore_body
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, workspace, write_strategy

FIRST, SECOND = "m:restore", "m:second"


def gated(mid: str, home: Path, text: str) -> dict:
    note = workspace(home, mid) / "n.txt"
    return mission(mid, checks=[note_check("n", note, text)], strategies=[write_strategy("w", "n.txt", text, ["n"])],
                   capabilities=["fs.read"], ceiling="read_only")


def writes(body: Body, mid: str) -> int:
    return sum(1 for e in body.journal.replay("mission.action")
               if e.payload["mission_id"] == mid and e.payload["status"] == "DONE")


def asks(body: Body, mid: str) -> list[dict]:
    return [e.payload for e in body.journal.replay("decision.requested") if e.payload["mission_id"] == mid]


@pytest.fixture
def lost(tmp_path):
    """The original: a phone, an approved write not yet executed, a seed; then it keeps going and is lost."""
    home, key, body_id, _ = make_body(tmp_path)
    phone_public = generate_founder_key(tmp_path / "phone.pem", None)
    clock = Clock()

    def sign(k, kind, body):
        return sign_command(k, kind, body, body_id=body_id, now=clock())

    with Body(home, clock=clock) as body:
        body.boot()
        body.apply(sign(key, "DEVICE_ENROLL", {"public_key": phone_public, "label": "phone", "kinds": ["DECISION"],
                                               "expires_at": stamp(clock() + timedelta(days=30))}))
        body.apply(sign(key, "MISSION", gated(FIRST, home, "approved once")))
        body.tick()
        [ask] = asks(body, FIRST)
        body.apply(sign(key, "DECISION", {"request_id": ask["request_id"], "answer": "approve", "reason": "once"}))
        head = body.ledger.head
    made = seed.make_seed(home, tmp_path / "seed-store")
    clock.advance(60)
    second = sign(key, "MISSION", gated(SECOND, home, "second"))
    leftover = sign(key, "MISSION", gated("m:leftover", home, "leftover"))
    with Body(home, clock=clock) as body:          # after the seed: write, revoke the phone, a second mission
        body.tick()
        body.apply(sign(key, "DEVICE_REVOKE", {"device_key_id": key_id(phone_public)}))
        body.apply(second)
        assert writes(body, FIRST) == 1
    home.rename(home.parent / "lost-machine")
    clock.advance(60)
    return {"home": home, "key": key, "phone": load_founder_key(tmp_path / "phone.pem", None),
            "phone_public": phone_public, "body_id": body_id, "clock": clock, "store": tmp_path / "seed-store",
            "seed": made["seed"], "head": head, "second": second, "leftover": leftover, "sign": sign}


def test_the_seed_records_its_recovery_point(lost):
    manifest = json.loads(cas.get(lost["store"], lost["seed"]))
    assert manifest["ledger_head"] == lost["head"] and manifest["backed_up_at"].endswith("Z")


def test_a_restored_body_boots_held_and_takes_no_action(lost):
    report = restore_body(lost["store"], lost["seed"], lost["home"], clock=lost["clock"])
    assert report["ledger_head_at_recovery_point"] == lost["head"] and report["witness_key"] == "fresh"
    assert report["recovery_point"] and "BODY_RESUME" in report["needs_from_founder"][0]
    with Body(lost["home"], clock=lost["clock"]) as body:
        body.boot()
        lost["clock"].advance(30)
        assert body.tick().get("paused") is True and body.paused()
        assert writes(body, FIRST) == 0
        assert body.ledger.verify_chain()[0]
    with Body(lost["home"], clock=lost["clock"]) as body:   # the hold and the voids survive a restart
        assert body.paused() and body.device_keys() == {}
    layout = Layout(lost["home"])
    assert all(d.is_dir() for d in (layout.inbox, layout.processed, layout.rejected, layout.outbox))
    assert oct(layout.home.stat().st_mode & 0o777) == "0o700"


def test_a_command_issued_before_the_restore_is_refused_however_it_arrives(lost):
    restore_body(lost["store"], lost["seed"], lost["home"], clock=lost["clock"])
    with Body(lost["home"], clock=lost["clock"]) as body:
        body.boot()
        with pytest.raises(FounderAuthError, match="issued before this body was restored"):
            body.apply(lost["second"])                      # consumed by the original after the backup
        drop(lost["home"], lost["leftover"], "leftover.json")
        [outcome] = body.ingest_inbox()
        assert outcome["status"] == "REJECTED" and "issued before this body was restored" in outcome["reason"]
        assert SECOND not in body.engine.book.missions and "m:leftover" not in body.engine.book.missions


def test_no_device_delegation_from_before_the_restore_is_usable(lost):
    report = restore_body(lost["store"], lost["seed"], lost["home"], clock=lost["clock"])
    assert report["voided"]["device_delegations"] == [key_id(lost["phone_public"])]   # revoked after the backup
    with Body(lost["home"], clock=lost["clock"]) as body:
        assert body.device_keys() == {}
        lost["clock"].advance(1)
        with pytest.raises(FounderAuthError, match="not enrolled or revoked"):
            body.apply(lost["sign"](lost["phone"], "BODY_RESUME", {}))


def test_only_the_founder_key_releases_the_restore_hold(lost):
    restore_body(lost["store"], lost["seed"], lost["home"], clock=lost["clock"])
    sign, clock = lost["sign"], lost["clock"]
    with Body(lost["home"], clock=clock) as body:
        clock.advance(1)
        body.apply(sign(lost["key"], "DEVICE_ENROLL", {"public_key": lost["phone_public"], "label": "phone again",
                                                       "kinds": ["BODY_RESUME", "BODY_PAUSE"],
                                                       "expires_at": stamp(clock() + timedelta(days=30))}))
        clock.advance(1)
        with pytest.raises(FounderAuthError, match="only the founder key releases a restore hold"):
            body.apply(sign(lost["phone"], "BODY_RESUME", {}))
        assert body.paused()
        body.apply(sign(lost["key"], "BODY_RESUME", {}))
        assert not body.paused()
        clock.advance(1)
        body.apply(sign(lost["phone"], "BODY_PAUSE", {}))   # an ordinary pause later is not a restore hold
        clock.advance(1)
        body.apply(sign(lost["phone"], "BODY_RESUME", {}))
        assert not body.paused()


def test_an_approval_granted_before_the_restore_is_asked_again(lost):
    report = restore_body(lost["store"], lost["seed"], lost["home"], clock=lost["clock"])
    [voided] = report["voided"]["approvals"]
    sign, clock = lost["sign"], lost["clock"]
    with Body(lost["home"], clock=clock) as body:
        body.boot()
        clock.advance(1)
        body.apply(sign(lost["key"], "BODY_RESUME", {}))
        clock.advance(30)
        body.tick()
        assert writes(body, FIRST) == 0                     # the original may already have written on it
        fresh = [a for a in asks(body, FIRST) if a["request_id"] != voided]
        assert len(fresh) == 1
        clock.advance(1)
        with pytest.raises(MissionError, match="request withdrawn"):
            body.apply(sign(lost["key"], "DECISION", {"request_id": voided, "answer": "approve", "reason": "x"}))
        body.apply(sign(lost["key"], "DECISION", {"request_id": fresh[0]["request_id"], "answer": "approve",
                                                  "reason": "re-decided after the restore"}))
        clock.advance(30)
        body.tick()
        assert writes(body, FIRST) == 1


def test_a_tampered_or_inconsistent_seed_never_boots(tmp_path):
    home, *_ = make_body(tmp_path)
    with Body(home) as body:
        body.boot()
    store = tmp_path / "store"
    made = seed.make_seed(home, store)
    manifest = json.loads(cas.get(store, made["seed"]))
    lines = Layout(home).ledger.read_text().splitlines(keepends=True)

    def variant(**change):
        return cas.put(store, json.dumps({**manifest, **change}, sort_keys=True).encode())

    # a broken chain whose last line, and so the recorded head, is unchanged
    record = json.loads(lines[1])
    record["payload"] = {**record["payload"], "tampered": True}
    broken = cas.put(store, "".join([lines[0], json.dumps(record) + "\n", *lines[2:]]).encode())
    cases = {"wrong head": (variant(ledger_head="sha256:" + "0" * 64), "not at the head the seed recorded"),
             "broken chain": (variant(files={**manifest["files"], "ledger.jsonl": broken}), "does not verify")}
    for name, (address, why) in cases.items():
        target = tmp_path / name / "body"
        with pytest.raises(RestoreError, match=why):
            restore_body(store, address, target)
        assert not (target / "witness.key").exists(), name     # nothing can open it
    obj = cas._path(store, manifest["files"]["ledger.jsonl"])
    obj.write_bytes(obj.read_bytes() + b"x")
    with pytest.raises(cas.IntegrityError):
        restore_body(store, made["seed"], tmp_path / "t3" / "body")
    manifest_object = cas._path(store, made["seed"])          # the manifest itself, edited in place
    manifest_object.write_bytes(manifest_object.read_bytes().replace(b"uniimente-seed/1", b"uniimente-seed/9"))
    with pytest.raises(cas.IntegrityError):
        restore_body(store, made["seed"], tmp_path / "t4" / "body")
    assert not (tmp_path / "t4").exists()


@pytest.mark.parametrize("rel,why", [("../outside.txt", "leaves the restore target"),
                                     ("/etc/greg-test", "leaves the restore target"),
                                     ("witness.key", "never holds key material")])
def test_a_seed_someone_else_built_cannot_write_outside_or_plant_keys(tmp_path, rel, why):
    home, *_ = make_body(tmp_path)
    store = tmp_path / "store"
    made = seed.make_seed(home, store)
    manifest = json.loads(cas.get(store, made["seed"]))
    crafted = cas.put(store, json.dumps({**manifest, "files": {**manifest["files"], rel: cas.put(store, b"x")}},
                                        sort_keys=True).encode())
    target = tmp_path / "new" / "body"
    with pytest.raises(RestoreError, match=why):
        restore_body(store, crafted, target)
    assert not (tmp_path / "new" / "outside.txt").exists() and not target.exists()


def test_a_restore_never_overwrites_a_living_body(tmp_path):
    home, *_ = make_body(tmp_path)
    made = seed.make_seed(home, tmp_path / "store")
    with pytest.raises(RestoreError, match="never overwrites a living body"):
        restore_body(tmp_path / "store", made["seed"], home)


def test_recovery_time_is_within_the_declared_threshold(tmp_path):
    home, *_ = make_body(tmp_path)
    with Body(home) as body:
        body.boot()
        n = 0
        while len(body.ledger.records) < 200:
            body.journal.record("drill.filler", {"n": n}, key=n)
            n += 1
    made = seed.make_seed(home, tmp_path / "store")
    home.rename(home.parent / "lost-machine")
    started = time.monotonic()
    restore_body(tmp_path / "store", made["seed"], home)
    with Body(home) as body:
        body.boot()
        assert body.paused()
    assert time.monotonic() - started <= 60


def test_the_cli_restores_and_reports(tmp_path, capsys):
    from greg import cli
    home, *_ = make_body(tmp_path)
    assert cli.main(["--home", str(home), "foundry", "seed", "--out", str(tmp_path / "offsite")]) == 0
    address = json.loads(capsys.readouterr().out)["seed"]
    target = tmp_path / "new-machine" / "body"
    assert cli.main(["--home", str(target), "foundry", "restore", "--store", str(tmp_path / "offsite"),
                     "--seed", address]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["witness_key"] == "fresh" and report["hold"].startswith("restored from a backup")
    assert cli.main(["--home", str(target), "foundry", "restore", "--store", str(tmp_path / "offsite"),
                     "--seed", address]) != 0                  # a living body is never overwritten
