from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

import pytest

from greg.command_queue import CommandQueueError, enqueue


def envelope(nonce, *, issued="2026-10-02T12:00:00Z", value=1):
    return {"nonce": nonce, "issued_at": issued, "body": {"value": value}}


def test_concurrent_deliveries_preserve_capacity_and_pending_retry(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()

    def deliver(i):
        try:
            return enqueue(inbox, envelope(str(i)), max_pending=3)
        except CommandQueueError:
            return None

    with ThreadPoolExecutor(max_workers=12) as pool:
        paths = list(pool.map(deliver, range(12)))
    admitted = [path for path in paths if path]
    assert len(admitted) == 3
    assert len(list(inbox.glob("*.json"))) == 3
    existing = json.loads(admitted[0].read_text())
    assert enqueue(inbox, existing, max_pending=3) == admitted[0]
    assert not list(inbox.glob("*.tmp"))


def test_nonce_collision_is_not_json_boolean_integer_equality(tmp_path):
    original = enqueue(tmp_path, envelope("same", value=1))
    with pytest.raises(CommandQueueError, match="different envelope"):
        enqueue(tmp_path, envelope("same", value=True))
    assert json.loads(original.read_text())["body"]["value"] == 1


def test_timestamp_order_and_no_payload_path_selection(tmp_path):
    later = enqueue(tmp_path, envelope("../../evil", issued="2026-10-02T12:00:01Z"))
    earlier = enqueue(tmp_path, envelope("other", issued="2026-10-02T12:00:00Z"))
    assert sorted(tmp_path.glob("*.json")) == [earlier, later]
    assert later.parent == tmp_path
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in (earlier, later))


def test_invalid_envelopes_still_occupy_capacity_and_unsafe_entry_blocks(tmp_path):
    (tmp_path / "bad.json").write_text("broken")
    with pytest.raises(CommandQueueError, match="inbox full"):
        enqueue(tmp_path, envelope("new"), max_pending=1)
    (tmp_path / "bad.json").unlink()
    (tmp_path / "bad.json").symlink_to(tmp_path / "missing")
    with pytest.raises(CommandQueueError, match="unsafe entry"):
        enqueue(tmp_path, envelope("new"))


def test_oversize_and_untrusted_dates_cannot_publish(tmp_path):
    with pytest.raises(CommandQueueError, match="too large"):
        enqueue(tmp_path, {**envelope("x"), "text": "x" * 65536})
    with pytest.raises(CommandQueueError, match="timestamp"):
        enqueue(tmp_path, envelope("x", issued="../../evil"))
    assert not list(tmp_path.glob("*.json"))


def test_signed_remote_backpressure_deduplicates_and_body_rejects_replay(tmp_path, monkeypatch):
    from greg import remote
    from greg.body import Body
    from greg.founder import sign_command
    from tests.greg_fixtures import make_body

    home, key, body_id, _ = make_body(tmp_path)
    command = sign_command(key, "BODY_PAUSE", {}, body_id=body_id)
    monkeypatch.setattr(remote, "MAX_PENDING", 1)
    raw = json.dumps(command).encode()
    first = remote.handle(home, "POST", "/api/command", {}, raw)
    second = remote.handle(home, "POST", "/api/command", {}, raw)
    assert first[0] == second[0] == 202
    assert json.loads(first[2])["delivered_to_inbox"] == json.loads(second[2])["delivered_to_inbox"]
    with Body(home) as body:
        assert len(body.ingest_inbox()) == 1
        assert body.paused()
    with Body(home) as body:
        assert body.paused()
        assert not body.ingest_inbox()
        assert len(body.journal.replay("command.accepted")) == 1
    with pytest.raises(remote.RemoteError) as denied:
        remote.handle(home, "POST", "/api/command", {}, raw)
    assert denied.value.status == 403
