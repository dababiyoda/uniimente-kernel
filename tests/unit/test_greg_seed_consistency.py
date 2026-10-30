"""A seed taken from a running body is consistent with itself, and so restores (WU-14 part 1).

Before the change ``foundry.systems.seed.make_seed`` copied every file and then read the ledger head with no
consistency: a body appending in between produced a seed whose recorded head is not where its packed ledger ends, which
``greg.recovery.restore_body`` refuses; and a final line torn by a write in progress made it raise outright (the head
was ``json.loads`` of that line) or pack a ledger no restore accepts. Now the verified ledger prefix is taken first and
everything else after it, and the files the body derives from its ledger are never packed or restored.

The founder key is a per-test Ed25519 key, not Alfonso's.
"""
from __future__ import annotations

import json
import threading

import pytest

from foundry.systems import cas, seed
from greg.body import Body, Layout
from greg.recovery import RestoreError, restore_body
from provenance.ledger import EvidenceLedger
from tests.greg_fixtures import make_body


def appending_during_every_copy(monkeypatch, body: Body) -> list:
    """A writer that appends one ledger record after each object the seed stores: the race, made deterministic."""
    put, appended = cas.put, []

    def put_then_append(store, data):
        address = put(store, data)
        appended.append(len(appended))
        body.journal.record("drill.concurrent_append", {"n": len(appended)}, key=len(appended))
        return address

    monkeypatch.setattr(cas, "put", put_then_append)
    return appended


def packed_ledger(store, made) -> bytes:
    return cas.get(store, json.loads(cas.get(store, made["seed"]))["files"]["ledger.jsonl"])


def restored_held(store, made, target) -> dict:
    report = restore_body(store, made["seed"], target)
    with Body(target) as body:
        assert body.paused(), "a restored body comes back held"
    return report


def test_a_seed_taken_while_the_body_appends_ends_where_its_manifest_says_and_restores(tmp_path, monkeypatch):
    home, *_ = make_body(tmp_path)
    store = tmp_path / "store"
    with Body(home) as body:
        body.boot()
        appended = appending_during_every_copy(monkeypatch, body)
        made = seed.make_seed(home, store)
        monkeypatch.undo()
        live = body.ledger.head
    assert appended and live != made["ledger_head"], "the body moved on while the seed was taken"
    report = restored_held(store, made, tmp_path / "new-machine" / "body")   # RestoreError before the change
    assert report["ledger_head_at_recovery_point"] == made["ledger_head"]
    assert json.loads(packed_ledger(store, made).splitlines()[-1])["hash"] == made["ledger_head"]


@pytest.mark.parametrize("tear", ["half a record", "a whole record without its newline"])
def test_a_torn_last_line_is_left_out_and_the_seed_ends_at_the_last_complete_record(tmp_path, tear):
    home, *_ = make_body(tmp_path)
    with Body(home) as body:
        body.boot()
        body.journal.record("drill.last", {"n": 1}, key="last")
    ledger = Layout(home).ledger
    raw = ledger.read_bytes()
    last = raw[raw.rstrip(b"\n").rfind(b"\n") + 1:]
    torn = raw[:-1] if tear.endswith("newline") else raw[:len(raw) - len(last) // 2]
    ledger.write_bytes(torn)                                   # a write in progress, or one a crash cut short
    complete = torn[:torn.rfind(b"\n") + 1]
    expected = json.loads(complete.splitlines()[-1])["hash"]
    store = tmp_path / "store"
    made = seed.make_seed(home, store)                         # raised on half a record before the change
    report = restored_held(store, made, tmp_path / "new-machine" / "body")   # and refused a whole one
    assert made["ledger_head"] == expected == report["ledger_head_at_recovery_point"]
    assert packed_ledger(store, made) == complete, "never a byte of the torn line"
    assert ledger.read_bytes() == torn, "taking a seed never changes the body"


def test_a_ledger_that_does_not_verify_is_refused_rather_than_packed_into_a_seed_no_restore_accepts(tmp_path):
    home, *_ = make_body(tmp_path)
    with Body(home) as body:
        body.boot()
    ledger = Layout(home).ledger
    lines = ledger.read_text().splitlines(keepends=True)
    record = json.loads(lines[1])
    record["payload"] = {**record["payload"], "tampered": True}
    ledger.write_text("".join([lines[0], json.dumps(record) + "\n", *lines[2:]]))
    with pytest.raises(seed.SeedError, match="does not verify"):
        seed.make_seed(home, tmp_path / "store")


def test_the_heartbeat_is_never_packed_and_a_restored_body_writes_its_own(tmp_path, monkeypatch):
    home, *_ = make_body(tmp_path)
    layout = Layout(home)
    store = tmp_path / "store"
    with Body(home) as body:
        body.boot()
        layout.heartbeat.write_text(json.dumps({"state": "RUNNING", "ledger_head": body.ledger.head}))
        appended = appending_during_every_copy(monkeypatch, body)
        put = cas.put

        def turn(store_, data):                                # a turn of Body.run: append, then publish the head
            address = put(store_, data)
            layout.heartbeat.write_text(json.dumps({"state": "RUNNING", "ledger_head": body.ledger.head}))
            return address

        monkeypatch.setattr(cas, "put", turn)
        made = seed.make_seed(home, store)
        monkeypatch.undo()
    assert appended
    manifest = json.loads(cas.get(store, made["seed"]))
    assert "heartbeat.json" not in manifest["files"] and manifest["derived_not_packed"] == ["heartbeat.json"]
    target = tmp_path / "new-machine" / "body"
    restored_held(store, made, target)
    assert not Layout(target).heartbeat.exists()
    # The derived file is rebuilt by the restored body itself, naming a head its own ledger holds.
    runner = threading.Thread(target=lambda: Body(target).run(tick_seconds=0.01, max_ticks=1))
    runner.start()
    runner.join(timeout=120)
    published = json.loads(Layout(target).heartbeat.read_text())
    assert published["state"] == "STOPPED"
    with Body(target) as body:
        assert body.ledger.find(published["ledger_head"]) is not None


def test_a_heartbeat_inside_a_seed_is_never_restored_as_truth(tmp_path):
    home, *_ = make_body(tmp_path)
    with Body(home) as body:
        body.boot()
    store = tmp_path / "store"
    made = seed.make_seed(home, store)
    manifest = json.loads(cas.get(store, made["seed"]))
    stale = json.dumps({"state": "RUNNING", "ledger_head": "sha256:" + "1" * 64}).encode()   # a head it never held
    carrying = cas.put(store, json.dumps({**manifest, "files": {**manifest["files"],
                                                                 "heartbeat.json": cas.put(store, stale)}},
                                         sort_keys=True).encode())
    target = tmp_path / "new-machine" / "body"
    report = restore_body(store, carrying, target)
    assert not Layout(target).heartbeat.exists()
    with Body(target) as body:
        assert body.paused() and body.ledger.head != report["ledger_head_at_recovery_point"]  # the restore recorded


def test_a_seed_head_is_the_head_a_reader_of_the_packed_ledger_verifies(tmp_path):
    home, *_ = make_body(tmp_path)
    with Body(home) as body:
        body.boot()
        constitution = body.compiled.constitution_hash
    store = tmp_path / "store"
    made = seed.make_seed(home, store)
    copy = tmp_path / "packed.jsonl"
    copy.write_bytes(packed_ledger(store, made))
    ledger = EvidenceLedger(constitution, str(copy), read_only=True)
    try:
        assert ledger.verify_chain()[0] and ledger.head == made["ledger_head"]
    finally:
        ledger.close()


def test_restore_error_is_still_raised_for_a_seed_whose_head_is_not_its_ledger_end(tmp_path):
    home, *_ = make_body(tmp_path)
    store = tmp_path / "store"
    made = seed.make_seed(home, store)
    manifest = json.loads(cas.get(store, made["seed"]))
    wrong = cas.put(store, json.dumps({**manifest, "ledger_head": "sha256:" + "0" * 64}, sort_keys=True).encode())
    with pytest.raises(RestoreError, match="not at the head the seed recorded"):
        restore_body(store, wrong, tmp_path / "t" / "body")
