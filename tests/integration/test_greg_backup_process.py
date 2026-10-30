"""Backups of a body that is running as its own OS process (`python -m greg run`) all restore (WU-14).

A feeder hands the body untrusted intake items every few milliseconds, so on every tick it appends to its ledger and
moves files, while twenty seeds are taken from outside the process with no lock on the writer. Every seed's recorded
head is where its packed ledger ends, every seed restores with ``greg.recovery.restore_body`` and comes back held, and
every recovery point is a prefix of the body's own history. One restored seed is then run as a body process of its
own: it stays held, takes no action and publishes its own heartbeat.

The second test is the founder-signed cadence (greg/backup.py) on a body running as its own process: the signed
mission's first backup lands in the signed store, counts as verified only through the Gate's receipt of its drill, and
restores on another "machine". Its store is on another filesystem (``/dev/shm``) where this machine has one; otherwise
the mission signs that it accepts the body's own. ``greg.backup`` is imported inside it, so the first test also runs
on a tree that predates the cadence (the fail-before run).

The founder key is a per-test Ed25519 key, not Alfonso's.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

from foundry.systems import cas, seed
from greg.body import Body, Layout, drop_intake
from greg.recovery import restore_body
from provenance.ledger import EvidenceLedger
from tests.greg_fixtures import drop, make_body, signed

ROOT = Path(__file__).resolve().parents[2]
ENV = {**os.environ, "PYTHONPATH": str(ROOT)}
SEEDS = 20


def run_body(home: Path, log: Path, *extra: str) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-m", "greg", "--home", str(home), "run", "--tick-seconds", "0.1", *extra],
                            cwd=ROOT, env=ENV, stdout=log.open("a"), stderr=subprocess.STDOUT)


def stop(body: subprocess.Popen) -> None:
    body.send_signal(signal.SIGTERM)
    try:
        body.wait(timeout=60)
    except subprocess.TimeoutExpired:
        body.kill()
        body.wait(timeout=10)


def wait_for(predicate, *, timeout=120, what="condition"):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    raise AssertionError(f"timed out waiting for {what}")


def records(path: Path) -> int:
    raw = path.read_bytes()
    return raw[:raw.rfind(b"\n") + 1].count(b"\n")


def test_twenty_seeds_of_a_running_body_all_restore_held(tmp_path):
    home, *_ = make_body(tmp_path)
    layout, store, log = Layout(home), tmp_path / "offsite", tmp_path / "body.log"
    briefs = home / "deliveries" / "briefs"                     # a body with some delivered work to back up
    briefs.mkdir(parents=True)
    for n in range(400):
        (briefs / f"brief-{n}.md").write_text(f"# brief {n}\n" + "evidence line\n" * 200)
    body = run_body(home, log)
    feeding = threading.Event()
    feeding.set()

    def feed():
        n = 0
        while feeding.is_set():
            drop_intake(home, source="backup-drill", content=f"item {n}", channel="test")
            n += 1
            time.sleep(0.005)

    feeder = threading.Thread(target=feed, daemon=True)
    made, raced = [], 0
    try:
        wait_for(layout.heartbeat.exists, what="the body's first turn")
        feeder.start()
        wait_for(lambda: (layout.intake / "ingested").is_dir(), what="the body ingesting intake")
        for _ in range(SEEDS):
            before = records(layout.ledger)
            try:
                made.append(seed.make_seed(home, store))
            except Exception as exc:                            # noqa: BLE001 - counted, then reported below
                made.append(exc)
            raced += records(layout.ledger) > before            # the body appended while this seed was taken
        assert body.poll() is None, log.read_text()[-3000:]
    finally:
        feeding.clear()
        stop(body)
    assert raced >= 1, "no seed raced the writer; the drill did not exercise the race"

    config = json.loads(layout.config.read_text())
    history = EvidenceLedger(config["constitution_hash"], str(layout.ledger), read_only=True)
    restored, failed, carried = [], [], 0
    try:
        for n, one in enumerate(made):
            if isinstance(one, Exception):
                failed.append(f"seed {n}: make_seed raised {type(one).__name__}: {one}")
                continue
            target = tmp_path / "drills" / str(n) / "body"
            try:
                report = restore_body(store, one["seed"], target)
            except Exception as exc:                            # noqa: BLE001 - counted, then reported below
                failed.append(f"seed {n}: restore_body raised {type(exc).__name__}: {exc}")
                continue
            manifest = json.loads(cas.get(store, one["seed"]))
            packed = cas.get(store, manifest["files"]["ledger.jsonl"])
            assert json.loads(packed.splitlines()[-1])["hash"] == manifest["ledger_head"]
            assert report["ledger_head_at_recovery_point"] == manifest["ledger_head"]
            assert history.find(manifest["ledger_head"]) is not None, "a recovery point is in the body's history"
            carried += "heartbeat.json" in manifest["files"]
            with Body(target) as again:
                assert again.paused() and again.ledger.verify_chain()[0]
            restored.append(target)
    finally:
        history.close()
    print(f"{raced} of {SEEDS} seeds were taken while the body appended; {len(restored)} of {SEEDS} restored held")
    assert not failed, f"{len(failed)} of {SEEDS} seeds did not restore: {failed[:3]}"
    assert carried == 0, f"{carried} of {SEEDS} seeds packed the heartbeat, which the body derives and rewrites"

    # The latest restored seed, run as a body of its own on its "new machine": held, no action, its own heartbeat.
    newest = restored[-1]
    again = run_body(newest, tmp_path / "restored.log", "--max-ticks", "3")
    assert again.wait(timeout=180) == 0, (tmp_path / "restored.log").read_text()[-3000:]
    published = json.loads(Layout(newest).heartbeat.read_text())
    assert published["state"] == "STOPPED"
    with Body(newest) as held:
        assert held.paused() and held.ledger.find(published["ledger_head"]) is not None
        assert not held.journal.replay("mission.action")


def test_a_running_body_takes_a_verified_backup_on_its_signed_cadence(tmp_path):
    from greg import backup
    home, key, body_id, _ = make_body(tmp_path)
    log = tmp_path / "body.log"
    shm = Path("/dev/shm")
    other = shm.is_dir() and os.stat(shm).st_dev != os.stat(home).st_dev
    store = Path(tempfile.mkdtemp(prefix="greg-backup-store-", dir=shm if other else tmp_path)).resolve()
    try:
        drop(home, signed(key, body_id, "MISSION", backup.mission(store=store, rpo_seconds=3600, cadence_seconds=60,
                                                                 accept_same_filesystem=not other)))
        body = run_body(home, log)
        try:
            wait_for(lambda: backup.verified(home, store), what="a verified backup")
            assert body.poll() is None, log.read_text()[-3000:]
        finally:
            stop(body)
        [first] = backup.verified(home, store)
        assert first["restored_head"] == first["ledger_head"] and first["held"] is True
        assert first["same_filesystem"] is not other
        target = tmp_path / "new-machine" / "body"
        assert restore_body(store, first["seed"], target)["ledger_head_at_recovery_point"] == first["ledger_head"]
        with Body(target) as again:
            assert again.paused()
        assert not (Layout(home).home / "objects").exists(), "nothing of the store is inside the body home"
    finally:
        shutil.rmtree(store, ignore_errors=True)
