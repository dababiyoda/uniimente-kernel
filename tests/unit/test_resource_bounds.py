"""Bounds on the stores that still grew after ledger verification was narrowed.

The evidence-ledger file, its in-memory records, the spine views and the
Consequence Gate's grant map are not changed here: the first two are an open
claim, and the Gate's source is a hash-bound continuity artifact. These tests
cover the passport registry, the organ queue, the egress journal and the
supervisor logs.
"""
from datetime import datetime, timedelta, timezone

import pytest

from foundry.systems import queue as queue_mod
from foundry.systems.segmentation import Journal
from greg import service
from identity.machine_passport import PassportError, PassportRegistry

Queue = queue_mod.Queue
IdempotentConsumer = queue_mod.IdempotentConsumer
QueueFull = getattr(queue_mod, "QueueFull", type("QueueFull", (Exception,), {}))


def _passport(registry, **kw):
    defaults = dict(kind="agent", creator="alfonso", owner_organ="uniimente-kernel",
                    legal_principal="alfonso_lopez", declared_capabilities=["propose"],
                    budget_ceiling_usd=0.0, consequence_class="read_only", ttl_seconds=1)
    defaults.update(kw)
    return registry.issue(**defaults)


def test_expired_passports_fold_and_a_revocation_is_kept():
    registry = PassportRegistry(max_expired_audit=3)
    issued = [_passport(registry).passport_id for _ in range(8)]
    revoked = _passport(registry, ttl_seconds=3600)
    registry.revoke(revoked.passport_id, reason="compromise suspected", revoker="alfonso")
    later = datetime.now(timezone.utc) + timedelta(hours=2)
    report = registry.retain(at=later)
    assert report["live"] == 0
    assert report["expired_retained"] == 3
    assert report["folded"] == 5
    assert report["revoked"] == 1
    assert report["folded_head"].startswith("sha256:")
    for passport_id in issued[-3:]:
        ok, why = registry.verify(passport_id, at=later)
        assert (ok, why) == (False, "expired")
    ok, why = registry.verify(issued[0], at=later)
    assert (ok, why) == (False, "unknown_identity")
    ok, why = registry.verify(revoked.passport_id, at=later)
    assert ok is False and why.startswith("revoked:")
    assert registry.inspect(revoked.passport_id)["which_entity_bears_liability"] == "alfonso_lopez"
    # Another long run must not push the audit window back open.
    more = [_passport(registry).passport_id for _ in range(6)]
    again = registry.retain(at=later + timedelta(hours=2))
    assert again["expired_retained"] == 3
    assert again["folded"] == 11
    assert again["revoked"] == 1
    assert registry.verify(more[0])[1] == "unknown_identity"


def test_live_passport_ceiling_refuses_another_issue():
    registry = PassportRegistry(max_live=2)
    _passport(registry, ttl_seconds=3600)
    _passport(registry, ttl_seconds=3600)
    with pytest.raises(PassportError, match="live passport ceiling"):
        _passport(registry, ttl_seconds=3600)


def test_a_finished_passport_frees_its_live_slot_and_a_revocation_still_stays():
    """A governed act's passport must leave the live set when the act finishes.

    The ceiling counts identities still in use. A run longer than that ceiling
    still issues, one finished passport at a time. Finishing is not revocation:
    a revoked identity stays, and folding never drops it.
    """
    registry = PassportRegistry(max_live=2, max_expired_audit=3)
    body = _passport(registry, kind="process", ttl_seconds=3600)
    finished = []
    for _ in range(6):
        worker = _passport(registry, kind="agent", ttl_seconds=900)
        finished.append(worker.passport_id)
        registry.retire(worker.passport_id)
    report = registry.retention()
    assert report["live"] == 1
    assert report["expired_retained"] == 3
    assert report["folded"] == 3
    assert report["revoked"] == 0
    assert registry.verify(body.passport_id) == (True, "identity_verified")
    assert registry.verify(finished[-1]) == (False, "expired")
    assert registry.verify(finished[0]) == (False, "unknown_identity")
    assert registry.inspect(finished[-1])["which_entity_bears_liability"] == "alfonso_lopez"
    registry.retire(finished[-2])  # already in the audit window
    assert registry.verify(finished[-2]) == (False, "expired")
    registry.revoke(finished[-1], reason="compromise suspected", revoker="alfonso")
    registry.retire(finished[-1])
    assert registry.retention()["revoked"] == 1
    assert registry.verify(finished[-1])[1].startswith("revoked:")
    _passport(registry, ttl_seconds=3600)
    with pytest.raises(PassportError, match="live passport ceiling"):
        _passport(registry, ttl_seconds=3600)


def test_queue_drops_acked_bodies_and_refuses_an_unbounded_backlog(tmp_path):
    queue = Queue(tmp_path, "signals", visibility=1, max_unacked=2, max_acked=2)
    for i in range(40):
        queue.publish({"n": i, "blob": "x" * 200}, message_id=f"m{i}")
        queue.ack(queue.receive(now=float(i))["id"])
    state = queue._state()
    assert len(state["messages"]) == 2
    assert state["audit"]["released"] == 38
    assert state["audit"]["head"].startswith("sha256:")
    assert all(message["body"] is None for message in state["messages"].values())
    size = (tmp_path / "signals" / "state.json").stat().st_size
    assert size < 4_000
    queue.publish({"n": "a"}, message_id="held-1")
    queue.publish({"n": "b"}, message_id="held-2")
    with pytest.raises(QueueFull):
        queue.publish({"n": "c"}, message_id="held-3")


def test_consumer_forgets_ids_only_after_the_retention_window(tmp_path):
    consumer = IdempotentConsumer(tmp_path, "w", retain_seconds=10)
    effects = []
    assert consumer.handle({"id": "m", "body": {"a": 1}}, effects.append, now=0) is True
    assert consumer.handle({"id": "m", "body": {"a": 1}}, effects.append, now=9) is False
    assert effects == [{"a": 1}]
    for i in range(15):
        consumer.handle({"id": f"c{i}", "body": {}}, lambda body: None, now=0)
    consumer.handle({"id": "later", "body": {}}, lambda body: None, now=100)
    assert list(consumer.done) == ["later"]
    assert consumer.audit["released"] == 16
    assert consumer.audit["head"].startswith("sha256:")


def test_egress_journal_compacts_and_still_verifies(tmp_path):
    path = tmp_path / "egress-journal.jsonl"
    journal = Journal(path, max_records=5, keep_records=2, max_segment_bytes=80)
    for i in range(30):
        journal.append({"identity": "http.get", "verdict": "DENIED", "n": i, "pad": "z" * 40})
    checked = journal.verify()
    assert checked["intact"] is True
    assert checked["entries"] <= 5
    assert "COMPACTED" in path.read_text()
    segments = list(tmp_path.glob("egress-journal.jsonl.segment-*"))
    sealed = sum(segment.stat().st_size for segment in segments)
    assert sealed <= 80
    assert path.stat().st_size < 8_000
    # A rewritten hot line is still a broken chain.
    lines = path.read_text().splitlines()
    path.write_text("\n".join([lines[0].replace("COMPACTED", "ALLOWED")] + lines[1:]) + "\n")
    assert journal.verify()["intact"] is False


def test_supervisor_logs_name_a_finite_size(tmp_path):
    program = service.supervisord_program(tmp_path)
    assert f"stdout_logfile_maxbytes={service.LOG_MAX_BYTES}" in program
    assert f"stderr_logfile_maxbytes={service.LOG_MAX_BYTES}" in program
    assert f"stdout_logfile_backups={service.LOG_BACKUPS}" in program
    remote = service.install(tmp_path, "supervisord", remote=True).read_text()
    assert f"stdout_logfile_maxbytes={service.LOG_MAX_BYTES}" in remote
    rotate = (tmp_path / "logs" / "greg-logs.rotate").read_text()
    assert "size 1M" in rotate and "copytruncate" in rotate
    assert "body.out.log" in rotate and "remote.err.log" in rotate
