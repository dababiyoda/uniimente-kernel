"""A founder-signed backup cadence, each backup proven by a restore drill (WU-14 part 2; greg/backup.py).

The cadence is a standing mission over ``body.backup_status`` and ``body.backup``: nothing is backed up without the
founder's signature, a backup is written only to the signed store (never inside the body home or a read root, never a
store it had to create, never on the body's own filesystem unless the founder accepts it), and a backup counts as
verified only through the Gate's positive receipt of a backup whose seed was restored in a scratch home, re-verified
and came back held. A damaged store or a failed drill records no verified backup and asks the founder once, while
the body keeps running; a store that is gone is never fresh. After the loss of the disk, the latest verified backup
restores, only the records after its recovery point are lost, and the cadence resumes once the founder resumes the
body. On one clock, a cadence with an RPO of at least twice its period keeps every recovery point within the RPO.

Most stores here are directories on the test machine's one disk, so their missions sign ``accept_same_filesystem``.
This machine's only other writable filesystem is ``/dev/shm``, a tmpfs, which a backup refuses as held in memory
(tested); the tests that need a store on another filesystem use it with that one check stubbed, as a stand-in for a
second disk.

The founder key is a per-test Ed25519 key, not Alfonso's.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile

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
ACCEPT = "accept_same_filesystem"                                       # body.backup's one signed parameter


def asks(body: Body) -> list[dict]:
    return [e.payload for e in body.journal.replay("decision.requested") if e.payload.get("mission_id") == MID]


def actions(body: Body) -> list[dict]:
    return [e.payload for e in body.journal.replay("mission.action") if e.payload["mission_id"] == MID]


@pytest.fixture
def world(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    clock = Clock()
    store = (tmp_path / "offsite").resolve()
    store.mkdir()                                                     # the founder creates or mounts the store
    return {"home": home, "key": key, "body_id": body_id, "data": data, "clock": clock, "store": store,
            "sign": lambda kind, body: signed(key, body_id, kind, body, now=clock())}


def sign_cadence(w, body: Body, *, accept_same_filesystem: bool = True, **kw) -> None:
    spec = backup.mission(store=kw.pop("store", w["store"]), rpo_seconds=kw.pop("rpo_seconds", 3600),
                          cadence_seconds=kw.pop("cadence_seconds", 60), **kw)
    if accept_same_filesystem:                  # what mission(accept_same_filesystem=True) writes (see the spec test)
        spec["strategies"][0]["params"] = {ACCEPT: True}
    assert body.apply(w["sign"]("MISSION", spec))["status"] == "APPLIED"


def refusals(body: Body) -> str:
    return " ".join(r for a in actions(body) if a["status"] != "DONE" for r in a["reasons"])


def shm_store(world) -> Path:
    shm = Path("/dev/shm")
    if not shm.is_dir() or os.stat(shm).st_dev == os.stat(world["home"]).st_dev:
        pytest.skip("no second filesystem on this machine")
    return Path(tempfile.mkdtemp(prefix="greg-backup-store-", dir=shm)).resolve()


@pytest.fixture
def other_filesystem(world, monkeypatch):
    """A store on another filesystem than the body home: ``/dev/shm``, with the memory-filesystem refusal stubbed so
    that it stands in for a second disk (this machine has no other writable filesystem)."""
    store = shm_store(world)
    monkeypatch.setattr(backup, "_volatile", lambda path: None)
    yield store
    shutil.rmtree(store, ignore_errors=True)


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
    assert spec["strategies"][0]["params"] == {}, "a store on the body's own filesystem is refused unless accepted"
    accepted = backup.mission(store="/srv/greg-backups", rpo_seconds=7200, cadence_seconds=600,
                              accept_same_filesystem=True)
    assert accepted["strategies"][0]["params"] == {ACCEPT: True} and "own filesystem" in accepted["founder_expression"]


def test_without_a_signed_mission_nothing_is_backed_up(world):
    with Body(world["home"], clock=world["clock"]) as body:
        body.boot()
        for _ in range(3):
            body.tick()
            world["clock"].advance(61)
        assert not body.ledger.select("witness", capability="body.backup")
    assert not (world["store"] / "objects").exists()


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


ADAPTERS = (("body.backup", backup.backup, {ACCEPT: True}),
            ("body.backup_status", backup.status, {"rpo_seconds": 60}))


@pytest.mark.parametrize("where", ["the body home", "a read root", "the body home itself", "a read root itself",
                                   "relative", "another prefix"])
def test_a_store_inside_the_body_home_or_a_read_root_is_refused_and_nothing_is_written(world, where):
    home, data = world["home"], world["data"]
    store = {"the body home": Layout(home).home.resolve() / "backups", "a read root": data.resolve() / "backups",
             "the body home itself": Layout(home).home.resolve(), "a read root itself": data.resolve()}.get(where)
    target = {"relative": "backup:backups", "another prefix": f"workspace:{data}"}.get(where, f"backup:{store}")
    for capability, adapter, params in ADAPTERS:
        with pytest.raises(CapabilityError, match="inside" if store else "absolute path"):
            adapter(params, context(home, data, capability, target))
    if store:
        assert not (store / "objects").exists() and (store.exists() == where.endswith("itself"))


@pytest.mark.parametrize("spelling", ["a trailing slash", "a dot-dot segment", "a glob character"])
def test_a_target_that_is_not_its_stores_canonical_form_is_refused(world, spelling):
    home, data, store = world["home"], world["data"], world["store"]
    if spelling == "a glob character":
        (store.parent / "backups[1]").mkdir()
    target = {"a trailing slash": f"backup:{store}/", "a dot-dot segment": f"backup:{store}/../{store.name}",
              "a glob character": f"backup:{store.parent}/backups[1]"}[spelling]
    for capability, adapter, params in ADAPTERS:
        with pytest.raises(CapabilityError, match="glob character" if "glob" in spelling else "canonical form"):
            adapter(params, context(home, data, capability, target))
    assert not (store / "objects").exists()
    with pytest.raises(ValueError, match="glob character"):
        backup.mission(store=store.parent / "backups[1]")


def test_a_store_that_does_not_exist_is_never_created(world):
    """An unmounted disk leaves its mount point missing: the backup asks instead of writing to the body's own disk."""
    home, clock = world["home"], world["clock"]
    store = world["store"].parent / "media" / "usb-backup-disk" / "greg"
    with Body(home, clock=clock) as body:
        body.boot()
        sign_cadence(world, body, store=store)
        for _ in range(3):
            body.tick()
            clock.advance(61)
        assert "not an existing directory" in refusals(body)
        assert [a["kind"] for a in asks(body)] == ["NO_STRATEGY"]
    assert not store.parent.parent.exists() and backup.verified(home, store) == []


def test_a_store_on_the_bodys_own_filesystem_needs_the_founders_acceptance(world):
    home, clock = world["home"], world["clock"]
    with Body(home, clock=clock) as body:
        body.boot()
        sign_cadence(world, body, accept_same_filesystem=False)          # world["store"] shares the home's disk
        for _ in range(2):
            body.tick()
            clock.advance(61)
        assert "on the body's own filesystem" in refusals(body)
        assert [a["kind"] for a in asks(body)] == ["NO_STRATEGY"]
    assert backup.verified(home, world["store"]) == [] and not (world["store"] / "objects").exists()


def test_a_store_on_another_filesystem_needs_no_acceptance(world, other_filesystem):
    home, clock = world["home"], world["clock"]
    with Body(home, clock=clock) as body:
        body.boot()
        sign_cadence(world, body, accept_same_filesystem=False, store=other_filesystem)
        assert body.tick()["missions"][0]["state"] == "ACTED"
    [other] = backup.verified(home, other_filesystem)
    assert other["same_filesystem"] is False and other["restored_head"] == other["ledger_head"]


def test_a_store_that_is_gone_or_damaged_is_never_fresh(world):
    home, data, store, clock = world["home"], world["data"], world["store"], world["clock"]
    with Body(home, clock=clock) as body:
        body.boot()
        sign_cadence(world, body)
        body.tick()
    ctx = context(home, data, "body.backup_status", backup.PREFIX + str(store))
    assert backup.status({"rpo_seconds": 3600}, ctx)["fresh"] is True
    unplugged = store.with_name("unplugged")
    store.rename(unplugged)                                           # the disk is unplugged
    assert backup.status({"rpo_seconds": 3600}, ctx)["why"].startswith("the store is not there")
    store.mkdir()                                                     # an empty directory where the mount was
    assert backup.status({"rpo_seconds": 3600}, ctx)["why"].endswith("a link or on another filesystem")
    (store / "objects").mkdir()
    assert backup.status({"rpo_seconds": 3600}, ctx)["why"].endswith("missing or damaged in the store")
    shutil.rmtree(store)
    unplugged.rename(store)
    [latest] = backup.verified(home, store)
    manifest = json.loads(cas.get(store, latest["seed"]))
    cas._path(store, manifest["files"]["body.json"]).unlink()         # one object of the backup lost
    out = backup.status({"rpo_seconds": 3600}, ctx)
    assert out["fresh"] is False and out["why"].endswith("missing or damaged in the store")


def test_a_store_replaced_while_the_backup_is_written_is_refused(world, monkeypatch):
    home, store, clock = world["home"], world["store"], world["clock"]
    made = seed.make_seed

    def then_replaced(home_, store_, **kw):                       # the drill alone would pass: same objects
        out = made(home_, store_, **kw)
        Path(store_).rename(Path(store_).with_name("unmounted"))
        shutil.copytree(Path(store_).with_name("unmounted"), store_)
        return out
    monkeypatch.setattr(seed, "make_seed", then_replaced)
    with Body(home, clock=clock) as body:
        body.boot()
        sign_cadence(world, body)
        body.tick()
        assert "changed while the backup was written" in refusals(body)
    assert backup.verified(home, store) == []


def test_a_drill_whose_restored_body_is_not_held_is_not_a_verified_backup(world, monkeypatch):
    home, store, clock = world["home"], world["store"], world["clock"]
    paused = Body.paused
    monkeypatch.setattr(Body, "paused", lambda self: False if "greg-restore-drill-" in str(self.layout.home)
                        else paused(self))
    made = seed.make_seed(home, world["store"].parent / "by-hand")
    with pytest.raises(RestoreError, match="did not come back held"):
        recovery.drill(world["store"].parent / "by-hand", made["seed"])
    with Body(home, clock=clock) as body:
        body.boot()
        sign_cadence(world, body)
        body.tick()
        assert "did not come back held" in refusals(body)
    assert backup.verified(home, store) == []


@pytest.mark.parametrize("rpo,cadence", [(60, 60), (3000, 3600), (119, 60)])
def test_an_rpo_shorter_than_twice_the_cadence_is_refused_before_signing(rpo, cadence):
    with pytest.raises(ValueError, match="half the RPO"):
        backup.mission(store="/srv/greg-backups", rpo_seconds=rpo, cadence_seconds=cadence)
    root = Path(__file__).resolve().parents[2]
    printed = subprocess.run([sys.executable, "-m", "greg.backup", "--store", "/srv/greg-backups", "--rpo-hours", "1"],
                             cwd=root, env={**os.environ, "PYTHONPATH": str(root)}, capture_output=True, text=True)
    assert printed.returncode == 2 and "half the RPO" in printed.stderr and not printed.stdout


def test_on_one_clock_the_cadence_keeps_the_recovery_point_within_the_rpo(world, monkeypatch):
    """The body's clock, the seed's time and the sensor's time are one clock (an RPO of 150 s, a cadence of 60 s)."""
    home, store, clock = world["home"], world["store"], world["clock"]
    wall = clock

    class OneClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return wall()
    monkeypatch.setattr(backup, "_now", wall)
    monkeypatch.setattr(seed, "datetime", OneClock)
    states, ages = [], []
    ctx = context(home, world["data"], "body.backup_status", backup.PREFIX + str(store))
    with Body(home, clock=clock) as body:
        body.boot()
        sign_cadence(world, body, rpo_seconds=150, cadence_seconds=60)
        for _ in range(8):
            states.append(body.tick()["missions"][0]["state"])
            ages.append(backup.status({"rpo_seconds": 150}, ctx)["age_seconds"])
            clock.advance(61)
        assert asks(body) == []
    # Acts when the latest recovery point is older than the RPO, and only then: judged from the latest backup.
    assert states == ["ACTED", "HOLDING", "HOLDING", "ACTED", "HOLDING", "HOLDING", "ACTED", "HOLDING"]
    assert len(backup.verified(home, store)) == 3 and max(ages) <= 150 + 61


def test_a_store_damaged_between_the_seed_and_its_drill_records_no_verified_backup_asks_once_and_the_body_runs(
        world, monkeypatch):
    home, store, clock = world["home"], world["store"], world["clock"]
    body_json = cas.put(store, Layout(home).config.read_bytes())
    made = seed.make_seed

    def then_damaged(*args, **kwargs):
        out = made(*args, **kwargs)
        path = cas._path(store, body_json)
        path.write_bytes(path.read_bytes() + b" ")
        return out
    monkeypatch.setattr(seed, "make_seed", then_damaged)
    with Body(home, clock=clock) as body:
        body.boot()
        sign_cadence(world, body)
        for _ in range(4):
            assert "missions" in body.tick()                          # the body keeps running
            clock.advance(61)
        [refused] = [a for a in actions(body) if a["status"] != "DONE"]
        assert "restore drill" in " ".join(refused["reasons"])
        assert [a["kind"] for a in asks(body)] == ["NO_STRATEGY"], "exactly one ask"
    assert backup.verified(home, store) == []


def test_a_rotten_object_is_never_fresh_and_the_next_backup_rewrites_it(world, monkeypatch):
    """One flipped bit in an object the latest backup needs: it no longer restores, so it is not fresh, and the next
    backup rewrites the object from the correct bytes it holds instead of failing on it ever after."""
    home, data, store, clock = world["home"], world["data"], world["store"], world["clock"]
    with Body(home, clock=clock) as body:
        body.boot()
        sign_cadence(world, body)
        assert body.tick()["missions"][0]["state"] == "ACTED"
        clock.advance(61)
        assert body.tick()["missions"][0]["state"] == "HOLDING"     # re-observed: the backup did what it should
        [first] = backup.verified(home, store)
        manifest = json.loads(cas.get(store, first["seed"]))
        ctx = context(home, data, "body.backup_status", backup.PREFIX + str(store))
        assert backup.status({"rpo_seconds": 3600}, ctx)["fresh"] is True
        rotten = cas._path(store, manifest["files"]["body.json"])     # an unchanged file: every later seed shares it
        raw = bytearray(rotten.read_bytes())
        raw[0] ^= 1
        rotten.write_bytes(bytes(raw))
        with pytest.raises(cas.IntegrityError):
            restore_body(store, first["seed"], store.parent / "would-be-machine" / "body")
        out = backup.status({"rpo_seconds": 3600}, ctx)
        assert out["fresh"] is False and out["current"] is False and out["why"].endswith("missing or damaged in "
                                                                                          "the store")
        clock.advance(61)
        assert body.tick()["missions"][0]["state"] == "ACTED"         # due again: a new backup, not an ask
        assert asks(body) == []
    second = backup.verified(home, store)[-1]
    assert second["repaired_objects"] == 1
    assert json.loads(cas.get(store, second["seed"]))["repaired_objects"] == [manifest["files"]["body.json"]]
    assert cas.intact(store, manifest["files"]["body.json"])
    restore_body(store, first["seed"], store.parent / "new-machine" / "body")   # the repair heals the older seed too


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


def one_clock(monkeypatch, clock) -> None:
    """The body's clock, the seed's time and the sensor's time as one clock, so that hours can pass in a test."""
    class OneClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock()
    monkeypatch.setattr(backup, "_now", clock)
    monkeypatch.setattr(seed, "datetime", OneClock)


@pytest.mark.parametrize("rpo,cadence,down", [(86400, 3600, 48 * 3600), (7200, 3600, 9 * 3600)],
                         ids=["a weekend off after a backup", "a night asleep after a backup"])
def test_a_body_stopped_between_a_backup_and_its_first_read_keeps_its_cadence_without_an_ask(world, monkeypatch, rpo,
                                                                                             cadence, down):
    """The engine judges a backup by the next read of its check. Stopped, asleep or paused before that read for longer
    than the RPO, the body used to find the backup it had just taken stale, blame it and stop the cadence on a founder
    ask although nothing had failed. The first read now judges the backup as it was taken; the next one by age."""
    home, data, store, clock = world["home"], world["data"], world["store"], world["clock"]
    one_clock(monkeypatch, clock)
    with Body(home, clock=clock) as body:
        body.boot()
        sign_cadence(world, body, rpo_seconds=rpo, cadence_seconds=cadence)
        assert body.tick()["missions"][0]["state"] == "ACTED"
    clock.advance(down)                                                # the body is stopped, asleep or paused
    out = backup.status({"rpo_seconds": rpo}, context(home, data, "body.backup_status", backup.PREFIX + str(store)))
    assert out["fresh"] is False and out["current"] is True and "first read" in out["why"]
    states = []
    with Body(home, clock=clock) as body:
        body.boot()
        for _ in range(3):
            states.append(body.tick()["missions"][0]["state"])
            clock.advance(cadence + 1)
        assert asks(body) == []
    # The first read judges the backup as taken; one cadence later the next read finds it due and takes a new one.
    assert states == ["HOLDING", "ACTED", "HOLDING"]
    first, second = backup.verified(home, store)
    assert second["seed"] != first["seed"] and second["restored_head"] == second["ledger_head"]


def test_a_backup_already_older_than_the_rpo_when_taken_is_judged_by_its_age_at_its_first_read(world, monkeypatch):
    home, data, store, clock = world["home"], world["data"], world["store"], world["clock"]
    one_clock(monkeypatch, clock)

    class Behind(datetime):                                            # a seed stamped an hour and a half too early
        @classmethod
        def now(cls, tz=None):
            return clock() - timedelta(seconds=5400)
    monkeypatch.setattr(seed, "datetime", Behind)
    with Body(home, clock=clock) as body:
        body.boot()
        sign_cadence(world, body)                                      # RPO 3600
        assert body.tick()["missions"][0]["state"] == "ACTED"
    out = backup.status({"rpo_seconds": 3600}, context(home, data, "body.backup_status", backup.PREFIX + str(store)))
    assert out["first_read"] is True and out["current"] is False and out["fresh"] is False


def test_a_store_held_in_memory_is_refused(world):
    """A tmpfs store is gone after every reboot, including the one after a disk failure."""
    home, clock = world["home"], world["clock"]
    store = shm_store(world)
    try:
        if backup._volatile(store) != "tmpfs":
            pytest.skip("/dev/shm is not a tmpfs here")
        assert backup._volatile(home) is None
        with Body(home, clock=clock) as body:
            body.boot()
            sign_cadence(world, body, store=store)                     # even with the same-filesystem acceptance
            for _ in range(2):
                body.tick()
                clock.advance(61)
            assert "held in memory" in refusals(body)
            assert [a["kind"] for a in asks(body)] == ["NO_STRATEGY"]
        assert backup.verified(home, store) == [] and not (store / "objects").exists()
    finally:
        shutil.rmtree(store, ignore_errors=True)


@pytest.mark.parametrize("where", ["the read root itself", "a directory inside the read root"])
def test_a_store_whose_objects_directory_is_a_link_is_refused_and_nothing_lands_where_it_leads(world, where):
    home, data, store = world["home"], world["data"], world["store"]
    elsewhere = (data / "objects-on-the-body-disk").resolve()
    elsewhere.mkdir()
    if where == "the read root itself":
        os.symlink(elsewhere, store / "objects")
    else:
        (store / "objects").mkdir(mode=0o700)
        os.symlink(elsewhere, store / "objects" / "ab")                 # one fan-out directory
    ctx = context(home, data, "body.backup", backup.PREFIX + str(store))
    with pytest.raises(CapabilityError, match="not a directory" if where.endswith("itself") else "symbolic links"):
        backup.backup({ACCEPT: True}, ctx)
    assert list(elsewhere.iterdir()) == []


def test_a_store_whose_objects_directory_is_another_filesystem_is_refused(world, monkeypatch):
    home, data, store = world["home"], world["data"], world["store"]
    lstat = os.lstat

    def other_device(path, *args, **kwargs):                           # a separate mount at <store>/objects
        info = lstat(path, *args, **kwargs)
        if str(path) == str(store / "objects"):
            return os.stat_result((*tuple(info)[:2], info.st_dev + 1, *tuple(info)[3:10]))
        return info
    monkeypatch.setattr(os, "lstat", other_device)
    with pytest.raises(CapabilityError, match="another filesystem than the store"):
        backup.backup({ACCEPT: True}, context(home, data, "body.backup", backup.PREFIX + str(store)))
    monkeypatch.undo()
    assert not [p for p in (store / "objects").iterdir()]


@pytest.mark.parametrize("inside", ["objects", "objects/ab"])
def test_a_read_root_inside_the_stores_objects_is_refused(world, inside):
    home, data, store = world["home"], world["data"], world["store"]
    root = store / inside
    root.mkdir(parents=True)
    for capability, adapter, params in ADAPTERS:
        ctx = context(home, data, capability, backup.PREFIX + str(store))
        ctx = InvocationContext(workspace=ctx.workspace, read_roots=(data, root), secrets=ctx.secrets,
                                manifest=ctx.manifest, target=ctx.target, mission_id=MID)
        with pytest.raises(CapabilityError, match="inside the backup store's objects directory"):
            adapter(params, ctx)
    assert list(root.iterdir()) == []


def test_a_backup_is_private_to_the_bodys_user(world, monkeypatch):
    """The body home is 0700; its backup must not be readable by other users of the store's machine either."""
    home, data, store = world["home"], world["data"], world["store"]
    (store / "objects").mkdir(mode=0o755)
    os.chmod(store / "objects", 0o755)                                 # left open by an earlier tool
    ctx = context(home, data, "body.backup", backup.PREFIX + str(store))
    backup.backup({ACCEPT: True}, ctx)
    assert stat.S_IMODE(os.lstat(store / "objects").st_mode) == 0o700
    os.chmod(store / "objects", 0o755)
    monkeypatch.setattr(os, "chmod", lambda *args, **kwargs: None)   # a filesystem that ignores permissions
    with pytest.raises(CapabilityError, match="cannot be made private"):
        backup.backup({ACCEPT: True}, ctx)


def test_a_store_whose_objects_directory_is_replaced_while_the_backup_is_written_is_refused(world, monkeypatch):
    home, data, store = world["home"], world["data"], world["store"]
    made = seed.make_seed

    def then_replaced(home_, store_, **kw):
        out = made(home_, store_, **kw)
        objects = Path(store_) / "objects"
        objects.rename(Path(store_) / "objects.moved")
        shutil.copytree(Path(store_) / "objects.moved", objects)       # same objects, another directory
        return out
    monkeypatch.setattr(seed, "make_seed", then_replaced)
    with pytest.raises(CapabilityError, match="changed while the backup was written"):
        backup.backup({ACCEPT: True}, context(home, data, "body.backup", backup.PREFIX + str(store)))


def test_status_is_not_fresh_once_the_stores_objects_directory_is_a_link(world):
    home, data, store, clock = world["home"], world["data"], world["store"], world["clock"]
    with Body(home, clock=clock) as body:
        body.boot()
        sign_cadence(world, body)
        body.tick()
    ctx = context(home, data, "body.backup_status", backup.PREFIX + str(store))
    assert backup.status({"rpo_seconds": 3600}, ctx)["fresh"] is True
    copy = (data / "copy-of-objects").resolve()                       # intact copies, on the body's own disk
    shutil.copytree(store / "objects", copy)
    shutil.rmtree(store / "objects")
    os.symlink(copy, store / "objects")
    out = backup.status({"rpo_seconds": 3600}, ctx)
    assert out["fresh"] is False and out["why"].endswith("a link or on another filesystem")


def test_status_is_not_fresh_once_a_store_taken_on_another_filesystem_is_on_the_bodys(world, other_filesystem,
                                                                                     monkeypatch):
    home, data, clock = world["home"], world["data"], world["clock"]
    with Body(home, clock=clock) as body:
        body.boot()
        sign_cadence(world, body, accept_same_filesystem=False, store=other_filesystem)
        assert body.tick()["missions"][0]["state"] == "ACTED"
    ctx = context(home, data, "body.backup_status", backup.PREFIX + str(other_filesystem))
    assert backup.status({"rpo_seconds": 3600}, ctx)["fresh"] is True
    identity = backup._identity

    def unmounted(path, **kwargs):                       # the disk is gone and its mount point is on the body's disk
        found = identity(path, **kwargs)
        return (os.stat(home).st_dev, found[1]) if found and Path(path) == other_filesystem else found
    monkeypatch.setattr(backup, "_identity", unmounted)
    out = backup.status({"rpo_seconds": 3600}, ctx)
    assert out["fresh"] is False and out["why"].startswith("the store is now on the body's own filesystem")


def test_a_backup_takes_no_parameter_but_the_signed_acceptance(world):
    home, data, store = world["home"], world["data"], world["store"]
    with pytest.raises(CapabilityError, match="takes only"):
        backup.backup({ACCEPT: True, "end": "sha256:" + "0" * 64},
                      context(home, data, "body.backup", backup.PREFIX + str(store)))
    assert not (store / "objects").exists()
