"""Revocation wins: a device being revoked acts in no way, whatever order its command and the revocation arrive in.

The body applies its inbox in file-name order, and a file's name starts with its signer's own ``issued_at`` (greg
serve and ``greg``'s CLI both name files that way). A device sets its own clock, and the verifier accepts a command
signed up to seven days back (its longest lifetime). The independent review of 7474e937 reproduced it (B2, present on
8d205324 already): the founder drops DEVICE_REVOKE for a phone; before the body's next tick the phone posts BODY_PAUSE
signed 120 s back; greg serve answers 202; the body applies the phone's pause first, then the revocation.

A crash torn inside the body's own ``device.revoked`` line widened it (B3, from 7474e937): greg serve read past the
incomplete line and served and accepted the phone until the body restarted, and on restart the phone's command could
again be applied before the revocation. Nothing on /api/status said the history ended inside a record (B4).

The founder's rule: capability repair cannot restore revoked authority; unreadable evidence remains unknown until
reconciled. Every key here is a per-test Ed25519 key, not Alfonso's.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import pytest

from events.spine import EventSpine
from greg import remote
from greg.body import Body, send_signed, status
from greg.founder import FounderAuthError, key_id, public_bytes, sign_command, sign_read, stamp
from greg.journal import Journal
from provenance.ledger import EvidenceLedger
from tests.greg_fixtures import make_body

BACK = timedelta(seconds=120)     # the review's probe: inside the five minutes the verifier allows a device's clock


def _now():
    return datetime.now(timezone.utc)


def _delegated(tmp_path, *labels, kinds=("DECISION", "BODY_PAUSE", "BODY_RESUME", "BODY_STOP")):
    """A body with one delegated device key per label: (home, founder key, body id, {label: (device key, key id)})."""
    home, key, body_id, _ = make_body(tmp_path)
    devices = {}
    with Body(home) as body:
        for label in labels:
            device = Ed25519PrivateKey.generate()
            public = public_bytes(device.public_key()).hex()
            body.apply(sign_command(key, "DEVICE_ENROLL", {"public_key": public, "label": label, "kinds": list(kinds),
                                                           "expires_at": stamp(_now() + timedelta(days=30))},
                                    body_id=body_id))
            devices[label] = (device, key_id(public))
    return home, key, body_id, devices


def _drop(home, envelope, tag):
    """Into the inbox under the name greg serve gives it: the signer's issued_at first."""
    path = Path(home) / "inbox" / f"{envelope['issued_at'].replace(':', '')}-{tag}-{envelope['nonce'][:8]}.json"
    path.write_text(json.dumps(envelope))
    return path


def _post(home, envelope):
    try:
        code, _, payload = remote.handle(home, "POST", "/api/command", {}, json.dumps(envelope).encode())
        return code, json.loads(payload)
    except remote.RemoteError as exc:
        return exc.status, {"error": str(exc)}


def _read(home, signer, body_id, route="/api/status"):
    now = _now()
    try:
        code, _, payload = remote.handle(home, "GET", route, sign_read(signer, body_id=body_id, method="GET",
                                                                        path=route, now=now), b"", now=now)
        return code, json.loads(payload)
    except remote.RemoteError as exc:
        return exc.status, {"error": str(exc)}


def _accepted(body):
    return [(e.payload["kind"], e.payload["signer"]) for e in body.journal.replay("command.accepted")]


# ------------------------------------------------------------------------------------------- B2: the body's inbox
def test_a_backdated_device_command_sorted_before_a_waiting_revocation_is_refused(tmp_path):
    home, key, body_id, devices = _delegated(tmp_path, "phone")
    phone, kid = devices["phone"]
    send_signed(home, key, "DEVICE_REVOKE", {"device_key_id": kid})          # the founder revokes the phone
    pause = _drop(home, sign_command(phone, "BODY_PAUSE", {}, body_id=body_id, now=_now() - BACK), "remote-body_pause")
    assert sorted(p.name for p in (home / "inbox").glob("*.json"))[0] == pause.name   # the phone's file sorts first
    with Body(home) as body:
        body.tick()
        assert ("BODY_PAUSE", "device:phone") not in _accepted(body)          # was applied before the revocation
        assert ("DEVICE_REVOKE", "founder") in _accepted(body) and kid not in body.device_keys()
        assert not body.paused()
        rejected = [e.payload for e in body.journal.replay("command.rejected")]
        assert [r["file"] for r in rejected] == [pause.name] and "revocation" in rejected[0]["reason"]


def test_a_device_command_greg_serve_took_before_the_founder_revoked_is_refused_on_the_next_tick(tmp_path):
    """The phone's command reached the inbox first (greg serve answered 202), then the founder revoked it, while the
    body was down: the same pass over the inbox refuses the command, wherever it sorts."""
    home, key, body_id, devices = _delegated(tmp_path, "phone")
    phone, kid = devices["phone"]
    assert _post(home, sign_command(phone, "BODY_PAUSE", {}, body_id=body_id, now=_now() - BACK))[0] == 202
    send_signed(home, key, "DEVICE_REVOKE", {"device_key_id": kid})
    with Body(home) as body:
        body.tick()
        assert _accepted(body)[-1] == ("DEVICE_REVOKE", "founder") and not body.paused()
        assert ("BODY_PAUSE", "device:phone") not in _accepted(body)


def test_greg_serve_refuses_a_device_whose_revocation_waits_in_the_inbox(tmp_path):
    """The review's probe (revoke_order.py, BACK=120): greg serve answered 202 and dropped the phone's command."""
    home, key, body_id, devices = _delegated(tmp_path, "phone")
    phone, kid = devices["phone"]
    assert _read(home, phone, body_id)[0] == 200
    send_signed(home, key, "DEVICE_REVOKE", {"device_key_id": kid})
    before = sorted(p.name for p in (home / "inbox").glob("*.json"))
    code, data = _post(home, sign_command(phone, "BODY_PAUSE", {}, body_id=body_id, now=_now() - BACK))
    assert code == 403 and "revocation is waiting" in data["error"]             # was: 202, dropped in the inbox
    assert sorted(p.name for p in (home / "inbox").glob("*.json")) == before
    code, data = _read(home, phone, body_id)
    assert code == 401 and "revocation is waiting" in data["error"]             # was: 200
    assert _read(home, key, body_id)[0] == 200                                  # the founder is served


def test_another_device_and_the_founder_are_not_held_by_one_device_revocation(tmp_path):
    home, key, body_id, devices = _delegated(tmp_path, "phone", "laptop")
    (phone, phone_kid), (laptop, _) = devices["phone"], devices["laptop"]
    send_signed(home, key, "DEVICE_REVOKE", {"device_key_id": phone_kid})
    assert _post(home, sign_command(laptop, "BODY_PAUSE", {}, body_id=body_id, now=_now() - BACK))[0] == 202
    assert _read(home, laptop, body_id)[0] == 200
    with Body(home) as body:
        body.tick()
        assert ("BODY_PAUSE", "device:laptop") in _accepted(body) and body.paused()
        assert phone_kid not in body.device_keys() and len(body.device_keys()) == 1


def test_a_revocation_nobody_signed_holds_no_device(tmp_path):
    """Only a revocation that verifies as the founder's counts: one with a broken signature, one signed by another
    key or by the device itself, one for another body, and one whose body is not exactly one key change who may sign
    nothing."""
    home, key, body_id, devices = _delegated(tmp_path, "phone")
    phone, kid = devices["phone"]
    forged = sign_command(key, "DEVICE_REVOKE", {"device_key_id": kid}, body_id=body_id)
    forged["signature"] = "00" * 64
    _drop(home, forged, "forged")
    _drop(home, sign_command(Ed25519PrivateKey.generate(), "DEVICE_REVOKE", {"device_key_id": kid},
                             body_id=body_id), "stranger")
    _drop(home, sign_command(phone, "DEVICE_REVOKE", {"device_key_id": kid}, body_id=body_id), "itself")
    _drop(home, sign_command(key, "DEVICE_REVOKE", {"device_key_id": kid}, body_id="another-body"), "elsewhere")
    _drop(home, sign_command(key, "DEVICE_REVOKE", {"device_key_id": kid, "extra": 1}, body_id=body_id), "shape")
    assert _read(home, phone, body_id)[0] == 200
    pause = sign_command(phone, "BODY_PAUSE", {}, body_id=body_id, now=_now() - BACK)
    assert _post(home, pause)[0] == 202
    with Body(home) as body:
        body.tick()
        assert ("BODY_PAUSE", "device:phone") in _accepted(body) and kid in body.device_keys()


def test_a_direct_apply_reads_the_waiting_revocations_too(tmp_path):
    home, key, body_id, devices = _delegated(tmp_path, "phone")
    phone, kid = devices["phone"]
    send_signed(home, key, "DEVICE_REVOKE", {"device_key_id": kid})
    with Body(home) as body:
        with pytest.raises(FounderAuthError, match="revocation is waiting"):
            body.apply(sign_command(phone, "BODY_PAUSE", {}, body_id=body_id))
        assert not body.paused()


def test_a_device_stop_read_mid_tick_is_refused_while_its_revocation_waits(tmp_path):
    """While a worker runs, the body reads only BODY_STOP files (Body._stop_now); a stop the device being revoked
    signed is refused there too, not applied ahead of the revocation the next full pass applies."""
    home, key, body_id, devices = _delegated(tmp_path, "phone")
    phone, kid = devices["phone"]
    send_signed(home, key, "DEVICE_REVOKE", {"device_key_id": kid})
    stop = _drop(home, sign_command(phone, "BODY_STOP", {}, body_id=body_id, now=_now() - BACK), "remote-body_stop")
    with Body(home) as body:
        assert body.ingest_inbox(only_kind="BODY_STOP")[0]["status"] == "REJECTED"
        assert not body.stop_requested and not body.layout.stop_file.exists()
        assert (body.layout.rejected / stop.name).exists() and kid in body.device_keys()   # applied next pass


# Floors: the founder's own commands keep their order, and a device not being revoked keeps its place. Moving a
# revocation ahead of the founder's earlier enrollment, a pause ahead of a resume, or every device command behind
# every revocation would each change what the founder's commands do (greg.body.pending_revocations).
def test_the_founders_enroll_then_revoke_of_one_key_in_one_pass_ends_revoked(tmp_path):
    home, key, body_id, _ = _delegated(tmp_path)
    device = Ed25519PrivateKey.generate()
    public = public_bytes(device.public_key()).hex()
    issued = _now() - timedelta(seconds=30)
    _drop(home, sign_command(key, "DEVICE_ENROLL", {"public_key": public, "label": "tablet", "kinds": ["DECISION"],
                                                    "expires_at": stamp(_now() + timedelta(days=30))},
                             body_id=body_id, now=issued), "device_enroll")
    _drop(home, sign_command(key, "DEVICE_REVOKE", {"device_key_id": key_id(public)}, body_id=body_id,
                             now=issued + timedelta(seconds=1)), "device_revoke")
    with Body(home) as body:
        body.ingest_inbox()
        assert [k for k, _ in _accepted(body)][-2:] == ["DEVICE_ENROLL", "DEVICE_REVOKE"]
        assert key_id(public) not in body.device_keys()


def test_a_device_resume_before_the_founders_pause_stays_before_it_whatever_else_is_revoked(tmp_path):
    home, key, body_id, devices = _delegated(tmp_path, "phone", "laptop")
    (_, phone_kid), (laptop, _) = devices["phone"], devices["laptop"]
    with Body(home) as body:
        body.apply(sign_command(key, "BODY_PAUSE", {}, body_id=body_id))
    t = _now() - timedelta(seconds=30)
    _drop(home, sign_command(laptop, "BODY_RESUME", {}, body_id=body_id, now=t), "remote-body_resume")
    _drop(home, sign_command(key, "BODY_PAUSE", {}, body_id=body_id, now=t + timedelta(seconds=1)), "body_pause")
    _drop(home, sign_command(key, "DEVICE_REVOKE", {"device_key_id": phone_kid}, body_id=body_id,
                             now=t + timedelta(seconds=2)), "device_revoke")
    with Body(home) as body:
        body.ingest_inbox()
        assert [k for k, _ in _accepted(body)][-3:] == ["BODY_RESUME", "BODY_PAUSE", "DEVICE_REVOKE"]
        assert body.paused()                                                  # the founder's pause came last


# --------------------------------------------------------------- B3 and B4: a revocation torn by a crash, greg serve
def _crash_torn_inside_the_revocation(tmp_path):
    """The body applied the phone's revocation and died inside the write of its ``device.revoked`` line: the file
    ends inside that line, and the command file is still in the inbox (it moves only once the record is
    acknowledged). A device command dropped before the revocation sorts ahead of it (signed 120 s back)."""
    home, key, body_id, devices = _delegated(tmp_path, "phone")
    phone, kid = devices["phone"]
    revoke = send_signed(home, key, "DEVICE_REVOKE", {"device_key_id": kid})
    with Body(home) as body:
        body.ingest_inbox()
    ledger = home / "ledger.jsonl"
    data = ledger.read_bytes()
    at = data.index(b'"greg.device.revoked"')
    start, end = data.rfind(b"\n", 0, at) + 1, data.index(b"\n", at) + 1
    ledger.write_bytes(data[:start + (end - start) // 2])                     # torn inside device.revoked
    (home / "inbox" / "processed" / revoke.name).replace(revoke)
    return home, key, body_id, phone, kid, revoke


def test_greg_serve_refuses_a_device_while_its_revocation_is_torn_and_the_body_applies_it_first_on_restart(tmp_path):
    """The review's probe (remote_revoke_real.py, BACK=120): on 7474e937 the phone read 200 twice, its backdated
    BODY_PAUSE was 202, and after the restart the body applied that pause before re-applying the revocation."""
    home, key, body_id, phone, kid, revoke = _crash_torn_inside_the_revocation(tmp_path)
    backdated = sign_command(phone, "BODY_PAUSE", {}, body_id=body_id, now=_now() - BACK)
    for _ in range(2):
        assert _read(home, phone, body_id)[0] in (401, 503)                    # was: 200, principal device:phone
    assert _post(home, backdated)[0] in (403, 503)                             # was: 202
    code, data = _read(home, key, body_id)
    assert code == 200 and data["data"]["security"]["unacknowledged_tail"]["bytes"] > 0      # B4: was absent
    landed = _drop(home, backdated, "remote-body_pause")                      # had it landed earlier, all the same
    assert sorted(p.name for p in (home / "inbox").glob("*.json"))[0] == landed.name
    with Body(home) as body:                                                   # the restart quarantines the tail
        body.tick()
        assert ("BODY_PAUSE", "device:phone") not in _accepted(body) and not body.paused()
        assert _accepted(body)[-1] == ("DEVICE_REVOKE", "founder") and kid not in body.device_keys()
    assert _read(home, phone, body_id)[0] == 401


def test_greg_serve_refuses_every_device_while_history_ends_inside_a_record_and_serves_the_founder(tmp_path):
    """Any incomplete last line, revocation or not: it may change what a device key may do. The device gets a fixed
    503 (no path, no exception text); the founder is served and sees that the line is incomplete."""
    home, key, body_id, devices = _delegated(tmp_path, "phone")
    phone, _ = devices["phone"]
    ledger = home / "ledger.jsonl"
    start = ledger.stat().st_size
    constitution = json.loads((home / "body.json").read_text())["constitution_hash"]
    writer = EvidenceLedger(constitution, str(ledger))                         # the body's writer, a record
    try:                                                                       # longer than a page
        Journal(EventSpine(writer), actor="spiffe://uniimente.internal/greg/body").record("probe.note",
                                                                                         {"pad": "p" * 6000})
    finally:
        writer.close()
    longer = ledger.read_bytes()
    cut = (start // 4096 + 1) * 4096
    assert start < cut < len(longer)
    os.truncate(ledger, cut)                                                   # as a reader finds it mid-write
    for route in ("/api/status", "/api/commands", "/api/decisions", "/api/vepmc"):
        code, data = _read(home, phone, body_id, route)
        assert code == 503 and data == {"error": remote.DEVICE_WAITS}           # was: 200
    code, data = _post(home, sign_command(phone, "DECISION", {"request_id": "r", "answer": "approve", "reason": ""},
                                          body_id=body_id))
    assert code == 503 and data == {"error": remote.DEVICE_WAITS}               # was: 202
    assert not list((home / "inbox").glob("*.json")) and str(home) not in remote.DEVICE_WAITS
    code, data = _read(home, key, body_id)
    tail = data["data"]["security"]["unacknowledged_tail"]
    assert code == 200 and (tail["offset"], tail["bytes"]) == (start, cut - start) and "device keys" in tail["meaning"]
    assert _post(home, sign_command(key, "BODY_PAUSE", {}, body_id=body_id))[0] == 202
    ledger.write_bytes(longer)                                                 # the line completes
    assert _read(home, phone, body_id)[0] == 200
    assert _read(home, key, body_id)[1]["data"]["security"]["unacknowledged_tail"] is None


def test_greg_status_names_an_incomplete_last_record(tmp_path):
    home, *_ = _crash_torn_inside_the_revocation(tmp_path)
    tail = status(home)["security"]["unacknowledged_tail"]
    assert tail["bytes"] > 0 and tail["sha256"].startswith("sha256:") and "crash" in tail["meaning"]


def test_the_phone_page_says_the_last_record_is_incomplete(tmp_path):
    from tests.unit.test_greg_ask_terms_surfaces import NEEDS_NODE, _phone
    if NEEDS_NODE.args[0]:
        pytest.skip(NEEDS_NODE.kwargs["reason"])
    home, *_ = _crash_torn_inside_the_revocation(tmp_path)
    assert "last record INCOMPLETE (device keys refused" in _phone(home, tmp_path)["state"]
