"""The phone channel: delegated device keys and a server that is transport, never authority."""
from datetime import timedelta
import json
from pathlib import Path
import shutil
import subprocess

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import pytest

from greg import remote
from greg.body import Body
from greg.founder import (FounderAuthError, public_bytes, sign_command, sign_read, stamp, validate_device_grant)
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, workspace, write_strategy
from tests.unit.test_greg_missions import events, run, submit

ROOT = Path(__file__).resolve().parents[2]


def _phone(tmp_path, clock=None, kinds=("DECISION", "CRITIQUE", "BODY_PAUSE", "BODY_RESUME", "BODY_STOP"), days=30):
    home, key, body_id, data = make_body(tmp_path)
    phone = Ed25519PrivateKey.generate()
    clock = clock or Clock()
    grant = {"public_key": public_bytes(phone.public_key()).hex(), "label": "phone", "kinds": list(kinds),
             "expires_at": stamp(clock.now + timedelta(days=days))}
    submit(home, key, body_id, "DEVICE_ENROLL", grant)
    run(home, clock, ticks=1)
    return home, key, body_id, phone, clock


def _approval_mission(home, key, body_id):
    note = workspace(home, "m:phone") / "n.txt"
    submit(home, key, body_id, "MISSION", mission(
        "m:phone", checks=[note_check("n", note, "approved from the phone")],
        strategies=[write_strategy("w", "n.txt", "approved from the phone", ["n"])],
        capabilities=["fs.read"], ceiling="read_only"))  # the write is outside the cone: needs a decision
    return note


def test_a_delegated_phone_key_answers_a_decision_and_is_recorded_as_the_device(tmp_path):
    home, key, body_id, phone, clock = _phone(tmp_path)
    note = _approval_mission(home, key, body_id)
    _, requests = run(home, clock, ticks=3)
    assert [r["kind"] for r in requests] == ["APPROVAL"] and not note.exists()
    drop(home, sign_command(phone, "DECISION", {"request_id": requests[0]["request_id"], "answer": "approve",
                                                "reason": "aprobado desde el teléfono ✓"}, body_id=body_id))
    missions, _ = run(home, clock, ticks=4)
    assert missions["m:phone"].status == "ACHIEVED" and note.read_text() == "approved from the phone"
    accepted = {e["kind"]: e["signer"] for e in events(home, "command.accepted")}
    assert accepted["DECISION"] == "device:phone" and accepted["MISSION"] == "founder"
    appraisal = events(home, "mission.appraised")[0]
    assert appraisal["verdict"] == "VERIFIED" and appraisal["checks"]["approval_boundaries_honored"]


@pytest.mark.parametrize("kind,body", [
    ("MISSION", {"mission_id": "m:x"}),
    ("CAPABILITY_ATTACH", {"capability_id": "fs.write"}),
    ("DEVICE_ENROLL", {"public_key": "00" * 32, "label": "x", "kinds": ["DECISION"], "expires_at": "2099-01-01T00:00:00Z"}),
    ("ROTATE_FOUNDER_KEY", {"new_public_key": "00" * 32}),
])
def test_a_phone_key_can_never_do_what_only_the_founder_key_may(tmp_path, kind, body):
    home, key, body_id, phone, clock = _phone(tmp_path)
    drop(home, sign_command(phone, kind, body, body_id=body_id))
    run(home, clock, ticks=1)
    rejected = events(home, "command.rejected")
    assert rejected and "device key may not sign" in rejected[-1]["reason"]
    assert [e["kind"] for e in events(home, "command.accepted")] == ["DEVICE_ENROLL"]


def test_expired_and_revoked_delegations_stop_working(tmp_path):
    home, key, body_id, phone, clock = _phone(tmp_path, days=1)
    clock.advance(2 * 86400)
    drop(home, sign_command(phone, "BODY_PAUSE", {}, body_id=body_id, now=clock.now))
    run(home, clock, ticks=1)
    assert "expired" in events(home, "command.rejected")[-1]["reason"]
    (tmp_path / "second").mkdir()
    home2, key2, body_id2, phone2, clock2 = _phone(tmp_path / "second")
    with Body(home2) as body:
        kid = next(iter(body.device_keys()))
    submit(home2, key2, body_id2, "DEVICE_REVOKE", {"device_key_id": kid})
    run(home2, clock2, ticks=1)
    drop(home2, sign_command(phone2, "BODY_PAUSE", {}, body_id=body_id2, now=clock2.now))
    run(home2, clock2, ticks=1)
    assert "not enrolled or revoked" in events(home2, "command.rejected")[-1]["reason"]


def test_device_grants_are_narrow_and_bounded():
    now = Clock().now
    pub = public_bytes(Ed25519PrivateKey.generate().public_key()).hex()
    ok = validate_device_grant({"public_key": pub, "label": "p", "kinds": ["BODY_STOP"],
                                "expires_at": stamp(now + timedelta(days=90))}, now=now)
    assert ok["kinds"] == ["BODY_STOP"]
    for bad in ({"kinds": ["MISSION"]}, {"kinds": []}, {"expires_at": stamp(now + timedelta(days=91))},
                {"expires_at": stamp(now - timedelta(seconds=1))}, {"label": ""}):
        body = {"public_key": pub, "label": "p", "kinds": ["DECISION"], "expires_at": stamp(now + timedelta(days=1)),
                **bad}
        with pytest.raises(FounderAuthError):
            validate_device_grant(body, now=now)


def test_remote_server_reads_need_a_signature_and_commands_are_pre_verified(tmp_path):
    home, key, body_id, phone, clock = _phone(tmp_path)
    before = (home / "ledger.jsonl").read_bytes()
    status, _, page = remote.handle(home, "GET", "/", {}, b"", now=clock.now)
    assert status == 200 and b"GREG" in page
    hello = json.loads(remote.handle(home, "GET", "/api/hello", {}, b"", now=clock.now)[2])
    assert hello["body_id"] == body_id
    with pytest.raises(remote.RemoteError) as unsigned:
        remote.handle(home, "GET", "/api/status", {}, b"", now=clock.now)
    assert unsigned.value.status == 401
    wrong_path = sign_read(phone, body_id=body_id, method="GET", path="/api/decisions", now=clock.now)
    with pytest.raises(remote.RemoteError):
        remote.handle(home, "GET", "/api/status", wrong_path, b"", now=clock.now)
    stale = sign_read(phone, body_id=body_id, method="GET", path="/api/status", now=clock.now - timedelta(minutes=5))
    with pytest.raises(remote.RemoteError):
        remote.handle(home, "GET", "/api/status", stale, b"", now=clock.now)
    stranger = Ed25519PrivateKey.generate()
    with pytest.raises(remote.RemoteError):
        remote.handle(home, "GET", "/api/status",
                      sign_read(stranger, body_id=body_id, method="GET", path="/api/status", now=clock.now), b"",
                      now=clock.now)
    for signer, principal in ((phone, "device:phone"), (key, "founder")):
        headers = sign_read(signer, body_id=body_id, method="GET", path="/api/status", now=clock.now)
        code, _, payload = remote.handle(home, "GET", "/api/status", headers, b"", now=clock.now)
        assert code == 200 and json.loads(payload)["principal"] == principal
    for bad in (b"not json", json.dumps(sign_command(stranger, "BODY_STOP", {}, body_id=body_id, now=clock.now)).encode(),
                json.dumps(sign_command(phone, "MISSION", {}, body_id=body_id, now=clock.now)).encode()):
        with pytest.raises(remote.RemoteError) as refused:
            remote.handle(home, "POST", "/api/command", {}, bad, now=clock.now)
        assert refused.value.status in (400, 403)
    assert not list((home / "inbox").glob("*.json"))  # nothing unauthenticated reached the body
    stop = sign_command(phone, "BODY_PAUSE", {}, body_id=body_id, now=clock.now)
    code, _, payload = remote.handle(home, "POST", "/api/command", {}, json.dumps(stop).encode(), now=clock.now)
    assert code == 202 and json.loads(payload)["signer"] == "device:phone"
    assert len(list((home / "inbox").glob("*.json"))) == 1
    assert (home / "ledger.jsonl").read_bytes() == before  # the server never writes history
    with pytest.raises(ValueError, match="loopback"):
        remote.make_server(home, host="0.0.0.0", port=0)


def _node_major():
    try:
        return int(subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip().lstrip("v").split(".")[0])
    except (OSError, ValueError):
        return 0


@pytest.mark.skipif(shutil.which("node") is None or _node_major() < 20, reason="needs node >= 20 (global WebCrypto)")
def test_the_phone_javascript_signs_bytes_the_python_body_accepts(tmp_path):
    """core.js (the code the phone runs) and founder.py must agree byte for byte, including
    non-ASCII text, or Alfonso's phone would be silently locked out."""
    home, key, body_id, _, clock = _phone(tmp_path)
    script = tmp_path / "sign.mjs"
    script.write_text(f"""
import {{ newDeviceKey, signCommand, signRead }} from {json.dumps((ROOT / 'greg/phone/core.js').as_uri())};
const d = await newDeviceKey();
const env = await signCommand(d, {{ kind: "CRITIQUE", bodyId: {json.dumps(body_id)},
  body: {{ target_event_id: "e", verdict: "note", evidence_type: "founder_judgment",
          text: "Revisión: ¿funciona? — sí ✓ \\"quoted\\" \\\\ tab\\t", nested: {{ b: [1, true, null], a: "z" }} }} }});
const read = await signRead(d, {{ bodyId: {json.dumps(body_id)}, method: "GET", path: "/api/status" }});
console.log(JSON.stringify({{ publicHex: d.publicHex, keyId: d.keyId, env, read }}));
""")
    out = subprocess.run(["node", str(script)], capture_output=True, text=True, timeout=60)
    if out.returncode and "Ed25519" in out.stderr:
        pytest.skip("this node lacks WebCrypto Ed25519: " + out.stderr[-200:])
    assert out.returncode == 0, out.stderr
    produced = json.loads(out.stdout)
    from greg.founder import FounderVerifier, key_id
    assert produced["keyId"] == key_id(produced["publicHex"])
    device = {"device_key_id": produced["keyId"], "public_key": produced["publicHex"], "label": "node",
              "kinds": ["CRITIQUE"], "expires_at": "2099-01-01T00:00:00Z"}
    verifier = FounderVerifier(body_id=body_id, enrolled={}, seen_nonce=lambda n: False,
                               devices={produced["keyId"]: device})
    assert verifier.verify(produced["env"])["body"]["text"].startswith("Revisión")
    assert verifier.verify_read(produced["read"], method="GET", path="/api/status") == "device:node"
    tampered = dict(produced["env"], body={**produced["env"]["body"], "text": "changed"})
    with pytest.raises(FounderAuthError):
        verifier.verify(tampered)


def test_an_answer_to_a_request_raised_in_this_same_process_is_accepted(tmp_path):
    """Regression (found by the phone end-to-end test): the engine's book was rebuilt only at
    the start of a tick, after inbox commands were applied, so an approval for a request the
    running body had just raised was refused as 'unknown' unless the body happened to restart."""
    home, key, body_id, phone, clock = _phone(tmp_path)
    note = _approval_mission(home, key, body_id)
    with Body(home, clock=clock) as body:  # one long-lived body, like launchd keeps it
        body.tick()  # applies the mission AND raises the approval request in this same tick
        clock.advance(1)
        request = body.journal.replay("decision.requested")[0].payload
        # The answer lands before any further tick: exactly the phone's fast tap.
        drop(home, sign_command(phone, "DECISION", {"request_id": request["request_id"], "answer": "approve",
                                                    "reason": ""}, body_id=body_id, now=clock.now))
        for _ in range(3):
            body.tick(); clock.advance(1)
        rejected = [e.payload for e in body.journal.replay("command.rejected")]
    assert not rejected, rejected
    assert note.read_text() == "approved from the phone"
