"""A founder-signed backup cadence, each backup proven by a restore drill (WU-14 part 2; greg/backup.py).

The cadence is a standing mission over ``body.backup_status`` and ``body.backup``: nothing is backed up without the
founder's signature, a backup is written only to the signed store (never inside the body home or a read root), and a
backup counts as verified only through the Gate's positive receipt of a backup whose seed was restored in a scratch
home and re-verified. A damaged store or a failed drill records no verified backup and asks the founder once, while
the body keeps running. After the loss of the disk, the latest verified backup restores, only the records after its
recovery point are lost, and the cadence resumes once the founder resumes the body.

The founder key is a per-test Ed25519 key, not Alfonso's.
"""
from __future__ import annotations

from datetime import timedelta
import json
from pathlib import Path
import shutil

import pytest

from foundry.systems import cas, seed
from greg import backup
from greg.body import Body, Layout
from greg.capabilities import BUILTINS, CapabilityError, InvocationContext, SecretBroker
from greg.missions import validate_mission
from greg import recovery
from greg.recovery import RestoreError, restore_body
from tests.greg_fixtures import Clock, make_body, signed

MID = "m:backup"


def asks(body: Body) -> list[dict]:
    return [e.payload for e in body.journal.replay("decision.requested") if e.payload.get("mission_id") == MID]


def actions(body: Body) -> list[dict]:
    return [e.payload for e in body.journal.replay("mission.action") if e.payload["mission_id"] == MID]


@pytest.fixture
def world(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    clock = Clock()
    store = (tmp_path / "offsite").resolve()
    return {"home": home, "key": key, "body_id": body_id, "data": data, "clock": clock, "store": store,
            "sign": lambda kind, body: signed(key, body_id, kind, body, now=clock())}


def sign_cadence(w, body: Body, **kw) -> None:
    spec = backup.mission(store=w["store"], rpo_seconds=kw.pop("rpo_seconds", 3600), cadence_seconds=60, **kw)
    assert body.apply(w["sign"]("MISSION", spec))["status"] == "APPLIED"


def test_the_spec_names_only_its_store_and_validates():
    spec = backup.mission(store="/srv/greg-backups", rpo_seconds=7200, cadence_seconds=600)
    validate_mission(spec)
    assert spec["light_cone"]["capabilities"] == ["body.backup_status", "body.backup"]
    assert spec["light_cone"]["targets"] == ["backup:/srv/greg-backups"]
    assert spec["light_cone"]["max_consequence_class"] == "internal_write" and spec["light_cone"]["budget_usd"] == 0
    assert {BUILTINS["body.backup"][0].consequence_class, BUILTINS["body.backup_status"][0].consequence_class} == \
        {"internal_write", "read_only"}
    with pytest.raises(ValueError, match="absolute"):
        backup.mission(store="relative/store")


def test_without_a_signed_mission_nothing_is_backed_up(world):
    with Body(world["home"], clock=world["clock"]) as body:
        body.boot()
        for _ in range(3):
            body.tick()
            world["clock"].advance(61)
        assert not body.ledger.select("witness", capability="body.backup")
    assert not world["store"].exists()


def test_a_signed_cadence_writes_a_seed_to_the_store_and_counts_it_only_after_its_drill(world, monkeypatch):
    home, store, clock = world["home"], world["store"], world["clock"]
    by_hand = seed.make_seed(home, store)                             # a seed in the store is not evidence
    with Body(home, clock=clock) as body:
        body.boot()
        sign_cadence(world, body)
        assert body.tick()["missions"][0]["state"] == "ACTED"
        [first] = backup.verified(home, store)
        assert first["seed"] != by_hand["seed"] and backup.verified(home, store.parent / "elsewhere") == []
        assert first["restored_head"] == first["ledger_head"] and first["held"] is True
        clock.advance(61)
        assert body.tick()["missions"][0]["state"] == "HOLDING"     # fresh: no second backup inside the RPO
        assert len(backup.verified(home, store)) == 1
        later = backup._now() + timedelta(seconds=3601)
        monkeypatch.setattr(backup, "_now", lambda: later)
        clock.advance(61)
        assert body.tick()["missions"][0]["state"] == "ACTED"       # the recovery point aged past the RPO
        assert body.ledger.find(first["ledger_head"]) is not None
    second = backup.verified(home, store)[-1]
    assert second["seed"] != first["seed"] and len(backup.verified(home, store)) == 2
    manifest = json.loads(cas.get(store, second["seed"]))
    assert not [f for f in manifest["files"] if seed._excluded(f)], "no key material in a backup"
    assert not (Layout(home).home / "objects").exists() and (store / "objects").is_dir()
    target = store.parent / "new-machine" / "body"
    assert restore_body(store, second["seed"], target)["ledger_head_at_recovery_point"] == second["ledger_head"]


def context(home: Path, data: Path, capability: str, target: str) -> InvocationContext:
    return InvocationContext(workspace=Layout(home).workspace / "m_backup", read_roots=(data,),
                             secrets=SecretBroker(Layout(home).secrets), manifest=BUILTINS[capability][0],
                             target=target, mission_id=MID)


@pytest.mark.parametrize("where", ["the body home", "a read root", "relative", "another prefix"])
def test_a_store_inside_the_body_home_or_a_read_root_is_refused_and_nothing_is_written(world, where):
    home, data = world["home"], world["data"]
    store = {"the body home": Layout(home).home / "backups", "a read root": data / "backups"}.get(where)
    target = {"relative": "backup:backups", "another prefix": f"workspace:{data}"}.get(where, f"backup:{store}")
    for capability, adapter, params in (("body.backup", backup.backup, {}),
                                        ("body.backup_status", backup.status, {"rpo_seconds": 60})):
        with pytest.raises(CapabilityError, match="inside" if store else "absolute path"):
            adapter(params, context(home, data, capability, target))
    if store:
        assert not store.exists()


@pytest.mark.parametrize("damage", ["before the backup", "between the seed and its drill"])
def test_a_damaged_store_records_no_verified_backup_asks_once_and_the_body_keeps_running(world, monkeypatch, damage):
    home, store, clock = world["home"], world["store"], world["clock"]
    body_json = cas.put(store, Layout(home).config.read_bytes())

    def corrupt():
        path = cas._path(store, body_json)
        path.write_bytes(path.read_bytes() + b" ")

    if damage == "before the backup":
        corrupt()
    else:
        made = seed.make_seed

        def then_damaged(*args, **kwargs):
            out = made(*args, **kwargs)
            corrupt()
            return out
        monkeypatch.setattr(seed, "make_seed", then_damaged)
    with Body(home, clock=clock) as body:
        body.boot()
        sign_cadence(world, body)
        for _ in range(4):
            assert "missions" in body.tick()                          # the body keeps running
            clock.advance(61)
        [refused] = [a for a in actions(body) if a["status"] != "DONE"]
        assert ("restore drill" if damage.startswith("between") else "no seed") in " ".join(refused["reasons"])
        assert [a["kind"] for a in asks(body)] == ["NO_STRATEGY"], "exactly one ask"
    assert backup.verified(home, store) == []


def test_disk_loss_restores_the_latest_verified_backup_and_the_cadence_resumes_after_the_founder(world):
    home, store, clock, sign = world["home"], world["store"], world["clock"], world["sign"]
    with Body(home, clock=clock) as body:
        body.boot()
        sign_cadence(world, body)
        body.tick()
        for n in range(3):                                            # after the recovery point
            body.journal.record("drill.after", {"n": n}, key=n)
    [latest] = backup.verified(home, store)
    original = [json.loads(line)["hash"] for line in Layout(home).ledger.read_text().splitlines()]
    shutil.rmtree(home)                                               # the disk is lost
    clock.advance(60)
    report = restore_body(store, latest["seed"], home, clock=clock)
    assert report["ledger_head_at_recovery_point"] == latest["ledger_head"]
    kept = original.index(latest["ledger_head"]) + 1
    with Body(home, clock=clock) as body:
        assert [r.hash for r in body.ledger.records][:kept] == original[:kept], "everything up to the point"
        assert not body.journal.replay("drill.after"), "only what came after the recovery point is lost"
        body.boot()
        clock.advance(1)
        assert body.tick().get("paused") is True and not backup.verified(home, store)
        clock.advance(1)
        body.apply(sign("BODY_RESUME", {}))
        clock.advance(61)
        assert body.tick()["missions"][0]["state"] == "ACTED"         # no interrupted backup to reconcile
        assert asks(body) == []
    [again] = backup.verified(home, store)
    assert again["seed"] != latest["seed"] and again["restored_head"] == again["ledger_head"]


def test_an_earlier_recovery_point_must_lie_in_the_verified_ledger(tmp_path):
    home, *_ = make_body(tmp_path)
    with Body(home) as body:
        body.boot()
        earlier = body.ledger.records[1].hash
    store = tmp_path / "store"
    made = seed.make_seed(home, store, end=earlier)
    assert made["ledger_head"] == earlier
    packed = cas.get(store, json.loads(cas.get(store, made["seed"]))["files"]["ledger.jsonl"])
    assert packed.count(b"\n") == 2 and json.loads(packed.splitlines()[-1])["hash"] == earlier
    restore_body(store, made["seed"], tmp_path / "new" / "body")
    with pytest.raises(seed.SeedError, match="not in this body's verified ledger"):
        seed.make_seed(home, store, end="sha256:" + "0" * 64)


def test_the_drill_re_verifies_the_restored_ledger_from_its_file_and_removes_its_scratch_home(tmp_path, monkeypatch):
    home, *_ = make_body(tmp_path)
    with Body(home) as body:
        body.boot()
    store = tmp_path / "store"
    made = seed.make_seed(home, store)
    proof = recovery.drill(store, made["seed"])
    assert proof["restored_head"] == made["ledger_head"] and proof["held"] is True
    scratch = []
    restore = recovery.restore_body

    def restored_then_damaged(store_, address, target, **kw):        # the restored file, damaged after its restore
        report = restore(store_, address, target, **kw)
        scratch.append(Path(target).parent)
        ledger = Layout(target).ledger
        lines = ledger.read_text().splitlines(keepends=True)
        record = json.loads(lines[1])
        record["payload"] = {**record["payload"], "tampered": True}
        ledger.write_text("".join([lines[0], json.dumps(record) + "\n", *lines[2:]]))
        return report

    monkeypatch.setattr(recovery, "restore_body", restored_then_damaged)
    with pytest.raises(RestoreError, match="does not re-verify"):
        recovery.drill(store, made["seed"])
    assert scratch and not scratch[0].exists(), "the scratch home is removed whatever the outcome"


def test_the_founder_signs_the_printed_cadence_with_the_existing_mission_command(world, tmp_path):
    import os
    import subprocess
    import sys
    from greg import cli
    root = Path(__file__).resolve().parents[2]
    printed = subprocess.run([sys.executable, "-m", "greg.backup", "--store", str(world["store"]), "--rpo-hours", "6",
                              "--cadence-seconds", "900"], cwd=root, env={**os.environ, "PYTHONPATH": str(root)},
                             capture_output=True, text=True, check=True).stdout
    spec = tmp_path / "backup.json"
    spec.write_text(printed)
    assert cli.main(["--home", str(world["home"]), "mission", "submit", str(spec), "--key",
                     str(tmp_path / "founder.pem"), "--no-passphrase"]) == 0
    with Body(world["home"], clock=world["clock"]) as body:
        body.boot()
        [outcome] = body.ingest_inbox()
        assert outcome["status"] == "APPLIED"
        registered = body.engine.book.missions[MID].spec
        assert registered["closure"] == {"kind": "infinite", "cadence_seconds": 900}
        assert registered["success_checks"][0]["sensor"]["params"] == {"rpo_seconds": 21600}
