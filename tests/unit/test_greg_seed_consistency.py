"""A seed taken from a running body is consistent with itself, and so restores (WU-14 part 1).

Before the change ``foundry.systems.seed.make_seed`` copied every file and then read the ledger head with no
consistency: a body appending in between produced a seed whose recorded head is not where its packed ledger ends, which
``greg.recovery.restore_body`` refuses; and a final line torn by a write in progress made it raise outright (the head
was ``json.loads`` of that line) or pack a ledger no restore accepts. Now the verified ledger prefix is taken first and
everything else after it, and the files the body derives from its ledger are never packed or restored.

A seed also packs only what it should: never a file reached through a symbolic link or another name of a key (it
followed links before), never a device or a pipe, and one unreadable file is listed rather than failing the seed. An
item waiting in the body's intake when the ledger is read is carried even when the running body consumes it before
the walk reaches it, and one consumed just before is read again by the restored body without a second record.

The founder key is a per-test Ed25519 key, not Alfonso's.
"""
from __future__ import annotations

import errno
import json
import os
import threading

import pytest

from foundry.systems import cas, seed
from greg.body import Body, Layout, drop_intake
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


def test_a_seed_never_follows_a_link_or_packs_another_name_of_a_key(tmp_path):
    """A confined worker can write links into its workspace; a cloned repository can carry them."""
    home, *_ = make_body(tmp_path)
    layout = Layout(home)
    with Body(home) as body:
        body.boot()
    layout.secrets.write_text(json.dumps({"github_token": "ghp_NEVER_IN_A_BACKUP"}))
    workspace = layout.workspace / "m_other"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "report.md").write_text("# real work\n")
    planted = {"notes.txt": "../../device_ed25519.pem", "cache.bin": "../../witness.key",
               "config.json": "../../secrets.json", "env.txt": "/proc/self/environ",
               "readme.md": str(tmp_path / "founder.pem"), "whole-home": "../.."}
    for name, to in planted.items():
        os.symlink(to, workspace / name)
    os.link(layout.device_key, workspace / "hardlinked.pem.txt")
    os.mkfifo(workspace / "pipe")
    store = tmp_path / "store"
    made = seed.make_seed(home, store)
    manifest = json.loads(cas.get(store, made["seed"]))
    packed = b"".join(cas.get(store, a) for a in manifest["files"].values())
    for secret in (layout.device_key.read_bytes(), layout.witness_key.read_bytes(), b"ghp_NEVER_IN_A_BACKUP",
                   (tmp_path / "founder.pem").read_bytes(), b"PATH="):
        assert secret not in packed
    where = {rel.rsplit("/", 1)[-1]: why for rel, why in manifest["not_packed"].items()}
    assert {name: where[name] for name in planted} == dict.fromkeys(planted, "symbolic link")
    assert where["hardlinked.pem.txt"] == "another name for excluded key material"
    assert where["pipe"] == "not a regular file"
    assert "workspace/m_other/report.md" in manifest["files"] and made["not_packed"] == manifest["not_packed"]
    target = tmp_path / "new-machine" / "body"
    restored_held(store, made, target)
    assert sorted(p.name for p in (Layout(target).workspace / "m_other").iterdir()) == ["report.md"]


def test_one_unreadable_file_is_listed_and_never_stops_the_seed(tmp_path, monkeypatch):
    """A failing sector, or a file the body may not read: the rest of the body is still backed up."""
    home, *_ = make_body(tmp_path)
    with Body(home) as body:
        body.boot()
    workspace = Layout(home).workspace / "m_other"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "scratch.bin").write_bytes(b"unreadable")
    contents = seed._contents

    def failing(dirfd, name, listed):                  # root reads a mode-000 file, so the I/O error is injected
        if name == "scratch.bin":
            raise OSError(errno.EIO, "Input/output error")
        return contents(dirfd, name, listed)
    monkeypatch.setattr(seed, "_contents", failing)
    store = tmp_path / "store"
    made = seed.make_seed(home, store)
    assert made["not_packed"] == {"workspace/m_other/scratch.bin": "unreadable: EIO"}
    restored_held(store, made, tmp_path / "new-machine" / "body")


def test_a_home_that_is_a_link_is_backed_up_where_it_leads(tmp_path):
    home, *_ = make_body(tmp_path)
    with Body(home) as body:
        body.boot()
    link = tmp_path / "greg-home"
    os.symlink(home, link)
    store = tmp_path / "store"
    made = seed.make_seed(link, store)
    assert {"body.json", "ledger.jsonl"} <= set(json.loads(cas.get(store, made["seed"]))["files"])
    restored_held(store, made, tmp_path / "new-machine" / "body")


@pytest.mark.parametrize("when", ["after the ledger, before the walk", "between listing it and reading it",
                                  "just before the ledger"])
def test_an_item_waiting_in_the_intake_is_never_lost_whenever_the_running_body_consumes_it(tmp_path, monkeypatch,
                                                                                           when):
    home, *_ = make_body(tmp_path)
    store = tmp_path / "store"
    with Body(home) as body:
        body.boot()
        item = drop_intake(home, source="drill", content="arrived before the recovery point", channel="test")
        raw, prefix, read = item.read_bytes(), seed.ledger_prefix, []

        def ledger_then_consumed(h, **kw):
            if when == "just before the ledger":
                body.ingest_intake()
            out = prefix(h, **kw)
            read.append(True)
            if when == "after the ledger, before the walk":
                body.ingest_intake()
            return out

        def consumed_once_listed(h, walk=None):
            for rel, dirfd, name in walk(h):
                if when.startswith("between") and read and rel == f"intake/{item.name}":
                    body.ingest_intake()                # listed by the walk after the ledger, moved before its read
                yield rel, dirfd, name
        monkeypatch.setattr(seed, "ledger_prefix", ledger_then_consumed)
        if when.startswith("between"):
            monkeypatch.setattr(seed, "_walk", lambda h, walk=seed._walk: consumed_once_listed(h, walk))
        made = seed.make_seed(home, store)
        monkeypatch.undo()
        assert len(body.journal.replay("external.ingested")) == 1, "the original body consumed it"
    manifest = json.loads(cas.get(store, made["seed"]))
    assert cas.get(store, manifest["files"][f"intake/{item.name}"]) == raw
    target = tmp_path / "new-machine" / "body"
    restored_held(store, made, target)
    assert (Layout(target).intake / item.name).is_file(), "still waiting in the restored body"
    with Body(target) as again:
        recorded = len(again.journal.replay("external.ingested"))
        assert recorded == (when == "just before the ledger")
        again.ingest_intake()                           # read again: a retained fact, never a second record
        assert len(again.journal.replay("external.ingested")) == 1
        assert not (Layout(target).intake / item.name).exists()
