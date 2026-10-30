"""NODE_REVOKE and the enrollment rules around it (WU-06 part a1).

A node is a machine identity under a bounded light cone, never a principal. Only the founder key admits or revokes
one; a node_id is enrolled again only after a revocation or its expiry; a node's key is never a key that has spoken
for the founder (a founder key, a device key) nor another active node's key; an expired node is inactive.
Keys here are test keys generated per test, never Alfonso's.
"""
from datetime import datetime, timedelta, timezone
import json

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import pytest

from foundry.systems import seed
from greg import cli, compute
from greg.body import Body, Layout
from greg.founder import (COMMAND_KINDS, DEVICE_KINDS, FounderAuthError, FounderVerifier, key_id, public_bytes,
                          sign_command, stamp)
from greg.lightcone import LightCone, ScopeError
from greg.recovery import restore_body
from tests.greg_fixtures import Clock, drop, horizon, make_body, mission, note_check, signed, workspace, write_strategy
from tests.unit.test_greg_missions import events, run

CONE = {"capabilities": ["fs.read"], "targets": ["fs:node2/*"], "max_consequence_class": "read_only",
        "budget_usd": 0}


def cone() -> dict:
    return {**CONE, "horizon": horizon(30)}


def new_key() -> tuple[Ed25519PrivateKey, str]:
    key = Ed25519PrivateKey.generate()
    return key, public_bytes(key.public_key()).hex()


def enroll_body(node_id: str, public_hex: str, **extra) -> dict:
    return {"node_id": node_id, "node_public_key": public_hex, "light_cone": cone(), **extra}


def apply(home, key, body_id, kind, body):
    with Body(home) as b:
        return b.apply(signed(key, body_id, kind, body))


def states(home, now=None) -> dict:
    with Body(home) as b:
        return compute.node_states(b.journal, now=now)


def delegate_every_device_kind(home, key, body_id) -> Ed25519PrivateKey:
    phone, phone_public = new_key()
    apply(home, key, body_id, "DEVICE_ENROLL", {
        "public_key": phone_public, "label": "phone", "kinds": list(DEVICE_KINDS),
        "expires_at": stamp(datetime.now(timezone.utc) + timedelta(days=30))})
    return phone


def test_node_revoke_is_a_founder_only_command_kind():
    assert "NODE_REVOKE" in COMMAND_KINDS
    assert not {"NODE_ENROLL", "NODE_REVOKE"} & set(DEVICE_KINDS)


def test_a_device_key_delegated_every_device_kind_cannot_sign_node_commands(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    _, node_public = new_key()
    apply(home, key, body_id, "NODE_ENROLL", enroll_body("body-2", node_public))
    phone = delegate_every_device_kind(home, key, body_id)
    for kind, body in (("NODE_REVOKE", {"node_id": "body-2"}),
                       ("NODE_ENROLL", enroll_body("body-3", new_key()[1]))):
        with Body(home) as b, pytest.raises(FounderAuthError, match=f"device key may not sign {kind}"):
            b.apply(sign_command(phone, kind, body, body_id=body_id))
    assert states(home)["body-2"]["state"] == "ACTIVE" and "body-3" not in states(home)
    assert not events(home, "node.revoked")


def test_a_delegation_record_listing_node_kinds_still_cannot_sign_them():
    """Defence in depth: the verifier refuses a device any kind outside DEVICE_KINDS whatever its record lists."""
    phone, phone_public = new_key()
    kid = key_id(phone_public)
    forged = {"device_key_id": kid, "public_key": phone_public, "label": "phone",
              "kinds": sorted(set(DEVICE_KINDS) | {"NODE_ENROLL", "NODE_REVOKE"}),
              "expires_at": "2099-01-01T00:00:00Z"}
    verifier = FounderVerifier(body_id="b1", enrolled={}, seen_nonce=lambda n: False, devices={kid: forged})
    for kind in ("NODE_ENROLL", "NODE_REVOKE"):
        with pytest.raises(FounderAuthError, match=f"device key may not sign {kind}"):
            verifier.verify(sign_command(phone, kind, {"node_id": "body-2"}, body_id="b1"))
    assert verifier.verify(sign_command(phone, "BODY_STOP", {}, body_id="b1"))["kind"] == "BODY_STOP"


def test_a_node_key_signs_no_founder_command(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    node, node_public = new_key()
    apply(home, key, body_id, "NODE_ENROLL", enroll_body("body-2", node_public))
    for kind, body in (("NODE_REVOKE", {"node_id": "body-2"}), ("MISSION", {"mission_id": "m:x"}),
                       ("DECISION", {"request_id": "r", "decision": "approve"})):
        with Body(home) as b, pytest.raises(FounderAuthError, match="not enrolled or revoked"):
            b.apply(sign_command(node, kind, body, body_id=body_id))
    assert states(home)["body-2"]["state"] == "ACTIVE"


def test_re_enrolling_an_active_node_without_a_revoke_is_refused(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    apply(home, key, body_id, "NODE_ENROLL", enroll_body("body-2", new_key()[1]))
    with pytest.raises(ValueError, match="already enrolled and active"):
        apply(home, key, body_id, "NODE_ENROLL", enroll_body("body-2", new_key()[1]))
    assert len(events(home, "node.enrolled")) == 1


def test_enrol_revoke_re_enrol_is_allowed(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    _, node_public = new_key()
    first = apply(home, key, body_id, "NODE_ENROLL", enroll_body("body-2", node_public))
    assert first["result"]["founder_authority_inherited"] is False and first["result"]["expires_at"] is None
    revoked = apply(home, key, body_id, "NODE_REVOKE", {"node_id": "body-2"})
    assert revoked["result"] == {"node_id": "body-2", "revoked": True, "enrollment_digest": first["digest"]}
    record = events(home, "node.revoked")[0]
    assert record["command_digest"] == revoked["digest"] and record["enrollment_digest"] == first["digest"]
    assert states(home)["body-2"]["state"] == "REVOKED"
    with Body(home) as b:
        assert compute.active_nodes(b.journal) == {}
    again = apply(home, key, body_id, "NODE_ENROLL", enroll_body("body-2", node_public))   # its own key again
    assert states(home)["body-2"]["state"] == "ACTIVE"
    assert states(home)["body-2"]["command_digest"] == again["digest"]
    assert len(events(home, "node.enrolled")) == 2


def test_a_founder_key_never_becomes_a_node_key(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    founder_public = public_bytes(key.public_key()).hex()
    for given in (founder_public, founder_public.upper()):
        with pytest.raises(ValueError, match="enrolled for the founder or delegated to a device"):
            apply(home, key, body_id, "NODE_ENROLL", enroll_body("body-2", given))
    rotated, rotated_public = new_key()
    apply(home, key, body_id, "ROTATE_FOUNDER_KEY", {"new_public_key": rotated_public})
    for given in (founder_public, rotated_public):   # the rotated-out key and the current one
        with pytest.raises(ValueError, match="enrolled for the founder or delegated to a device"):
            apply(home, rotated, body_id, "NODE_ENROLL", enroll_body("body-2", given))
    assert not events(home, "node.enrolled")


def test_a_device_key_never_becomes_a_node_key(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    phone = delegate_every_device_kind(home, key, body_id)
    phone_public = public_bytes(phone.public_key()).hex()
    with pytest.raises(ValueError, match="enrolled for the founder or delegated to a device"):
        apply(home, key, body_id, "NODE_ENROLL", enroll_body("body-2", phone_public))
    apply(home, key, body_id, "DEVICE_REVOKE", {"device_key_id": key_id(phone_public)})
    with pytest.raises(ValueError, match="enrolled for the founder or delegated to a device"):
        apply(home, key, body_id, "NODE_ENROLL", enroll_body("body-2", phone_public))   # revoked: still refused
    assert not events(home, "node.enrolled")


def test_each_active_node_has_its_own_key(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    _, shared = new_key()
    apply(home, key, body_id, "NODE_ENROLL", enroll_body("body-2", shared))
    with pytest.raises(ValueError, match="another active node already holds this key"):
        apply(home, key, body_id, "NODE_ENROLL", enroll_body("body-3", shared))
    apply(home, key, body_id, "NODE_REVOKE", {"node_id": "body-2"})
    apply(home, key, body_id, "NODE_ENROLL", enroll_body("body-3", shared))   # the key is free once body-2 is revoked
    assert {k: v["state"] for k, v in states(home).items()} == {"body-2": "REVOKED", "body-3": "ACTIVE"}


def test_an_expired_node_is_inactive_and_may_be_enrolled_again(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    now = datetime.now(timezone.utc)
    _, node_public = new_key()
    first = apply(home, key, body_id, "NODE_ENROLL",
                  enroll_body("body-2", node_public, expires_at=(now + timedelta(hours=1)).isoformat()))
    assert first["result"]["expires_at"] == stamp(now + timedelta(hours=1))
    later = now + timedelta(hours=2)
    with Body(home) as b:
        assert set(compute.active_nodes(b.journal, now=now)) == {"body-2"}
        assert compute.active_nodes(b.journal, now=later) == {}
        assert compute.node_states(b.journal, now=later)["body-2"]["state"] == "EXPIRED"
        # after expiry the node_id and its key are free without a revoke
        again = compute.enroll_node(b.journal, enroll_body("body-2", node_public), "digest-2", now=later)
        assert again["command_digest"] == "digest-2" and again["expires_at"] is None
        assert compute.node_states(b.journal, now=later)["body-2"]["state"] == "ACTIVE"
    # an expired enrollment may still be revoked explicitly, which records it
    (tmp_path / "second").mkdir()
    home2, key2, body_id2, _ = make_body(tmp_path / "second")
    apply(home2, key2, body_id2, "NODE_ENROLL",
          enroll_body("body-2", node_public, expires_at=stamp(now + timedelta(hours=1))))
    with Body(home2) as b:
        compute.revoke_node(b.journal, {"node_id": "body-2"}, "digest-r", now=later)
        assert compute.node_states(b.journal, now=later)["body-2"]["state"] == "REVOKED"


@pytest.mark.parametrize("given, why", [
    ("past", "later than the command time"),
    ("2099-01-01T00:00:00", "timezone"),
    ("not a time", "Invalid isoformat|isoformat"),
    (12345, "ISO 8601 instant with a timezone"),
    ("9999-12-31T23:00:00-05:00", "out of range"),
])
def test_a_bad_expiry_is_refused(tmp_path, given, why):
    home, key, body_id, _ = make_body(tmp_path)
    if given == "past":
        given = stamp(datetime.now(timezone.utc) - timedelta(seconds=1))
    with pytest.raises(ValueError, match=why):
        apply(home, key, body_id, "NODE_ENROLL", enroll_body("body-2", new_key()[1], expires_at=given))
    assert not events(home, "node.enrolled")


@pytest.mark.parametrize("body, why", [
    ({"node_id": "body-2", "node_public_key": "ab" * 32, "light_cone": CONE, "extra": 1}, "optionally expires_at"),
    ({"node_id": "", "node_public_key": "ab" * 32}, "1..128 characters"),
    ({"node_id": "x" * 129, "node_public_key": "ab" * 32}, "1..128 characters"),
    ({"node_id": ["x"], "node_public_key": "ab" * 32}, "1..128 characters"),
    ({"node_id": "body-2", "node_public_key": "ab" * 31}, "32-byte Ed25519"),
    ({"node_id": "body-2", "node_public_key": "ab" * 31 + "  "}, "32-byte Ed25519"),       # 64 characters, 31 bytes
    ({"node_id": "body-2", "node_public_key": "ab" * 16 + " " + "ab" * 16}, "32-byte Ed25519"),  # 32 bytes, padded
    ({"node_id": "body-2", "node_public_key": "zz" * 32}, "32-byte Ed25519"),
])
def test_a_malformed_enrollment_is_refused(tmp_path, body, why):
    home, key, body_id, _ = make_body(tmp_path)
    body = {"light_cone": cone(), **body} if "light_cone" not in body else body
    with pytest.raises(ValueError, match=why):
        apply(home, key, body_id, "NODE_ENROLL", body)
    assert not events(home, "node.enrolled")


def test_a_node_id_of_128_characters_is_enrolled(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    apply(home, key, body_id, "NODE_ENROLL", enroll_body("n" * 128, new_key()[1]))
    assert states(home)["n" * 128]["state"] == "ACTIVE"


def test_this_bodys_own_identity_key_and_id_never_become_a_node(tmp_path):
    """A node is another machine. The body's own identity key (whose private half is in this body's home) is not a
    node key under any node_id, and no node takes this body's own id."""
    home, key, body_id, _ = make_body(tmp_path)
    own = json.loads(Layout(home).config.read_text())["device_public_key"]
    for given in (own, own.upper()):
        with pytest.raises(ValueError, match="this body's own identity key"):
            apply(home, key, body_id, "NODE_ENROLL", enroll_body("body-2", given))
    with pytest.raises(ValueError, match="this body's own id"):
        apply(home, key, body_id, "NODE_ENROLL", enroll_body(body_id, new_key()[1]))
    assert not events(home, "node.enrolled")


def test_a_restore_voids_every_node_enrollment_from_before_it(tmp_path):
    """A restored body knows nothing after its recovery point. A node the founder revoked after the backup (its key
    perhaps compromised) must not come back ACTIVE: like device delegations, every node enrollment not already
    revoked is voided whatever the clock says, and the founder enrolls again each node still trusted."""
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()

    def sign(kind, body):
        return sign_command(key, kind, body, body_id=body_id, now=clock())

    keys = {n: new_key()[1] for n in ("body-2", "body-3", "body-4", "body-5")}
    real_now = datetime.now(timezone.utc)
    with Body(home, clock=clock) as b:
        for node_id in ("body-2", "body-3", "body-4"):
            b.apply(sign("NODE_ENROLL", enroll_body(node_id, keys[node_id])))
        b.apply(sign("NODE_ENROLL", enroll_body("body-5", keys["body-5"],
                                                expires_at=stamp(real_now + timedelta(hours=1)))))
        b.apply(sign("NODE_REVOKE", {"node_id": "body-4"}))           # revoked before the backup: stays as it is
    made = seed.make_seed(home, tmp_path / "seed-store")
    clock.advance(60)
    with Body(home, clock=clock) as b:                               # after the backup: the founder revokes body-2
        b.apply(sign("NODE_REVOKE", {"node_id": "body-2"}))
    home.rename(home.parent / "lost-machine")
    clock.advance(2 * 3600)                                          # the restoring machine's clock is past body-5's
    report = restore_body(tmp_path / "seed-store", made["seed"], home, clock=clock)   # expiry; a later one is not
    assert report["voided"]["node_enrollments"] == ["body-2", "body-3", "body-5"]
    assert any("NODE_ENROLL again" in need for need in report["needs_from_founder"])
    restored = states(home, now=real_now)                            # a clock set back cannot revive body-5
    assert {k: v["state"] for k, v in restored.items()} == {n: "REVOKED" for n in keys}
    assert restored["body-3"]["revoked_by_restore"] == report["restore_id"]
    assert "revoked_by_restore" not in restored["body-4"]
    clock.advance(1)
    with Body(home, clock=clock) as b:   # a node still trusted is enrolled again by a command issued after the restore
        b.apply(sign("NODE_ENROLL", enroll_body("body-3", keys["body-3"])))
        assert set(compute.active_nodes(b.journal, now=real_now)) == {"body-3"}


def test_an_out_of_range_light_cone_budget_is_a_refusal_not_a_crash(tmp_path):
    """float(10**400) raises OverflowError, which no ingest path catches: a founder-signed command with such a
    budget would stop the running body on every restart. The cone refuses it as a scope error instead."""
    huge = {**cone(), "budget_usd": 10 ** 400}
    with pytest.raises(ScopeError, match="finite and nonnegative"):
        LightCone.from_dict(huge)
    home, key, body_id, _ = make_body(tmp_path)
    note = workspace(home, "m:huge") / "n.txt"
    bad_mission = mission("m:huge", checks=[note_check("n", note, "x")],
                          strategies=[write_strategy("w", "n.txt", "x", ["n"])], capabilities=["fs.read"],
                          ceiling="read_only")
    bad_mission["light_cone"]["budget_usd"] = 10 ** 400
    drop(home, signed(key, body_id, "NODE_ENROLL", {**enroll_body("body-2", new_key()[1]), "light_cone": huge}),
         "a-node.json")
    drop(home, signed(key, body_id, "MISSION", bad_mission), "b-mission.json")
    drop(home, signed(key, body_id, "NODE_ENROLL", enroll_body("body-3", new_key()[1])), "c-node.json")
    run(home, Clock(), ticks=1)                                      # the body runs on through both
    reasons = [e["reason"] for e in events(home, "command.rejected")]
    assert len(reasons) == 2 and all("finite and nonnegative" in r for r in reasons)
    layout = Layout(home)
    assert sorted(p.name for p in layout.rejected.glob("*.json")) == ["a-node.json", "b-mission.json"]
    assert not list(layout.inbox.glob("*.json"))
    assert {k: v["state"] for k, v in states(home).items()} == {"body-3": "ACTIVE"}


def test_an_unknown_or_already_revoked_node_cannot_be_revoked(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    with pytest.raises(ValueError, match="names no enrolled node"):
        apply(home, key, body_id, "NODE_REVOKE", {"node_id": "body-9"})
    apply(home, key, body_id, "NODE_ENROLL", enroll_body("body-2", new_key()[1]))
    apply(home, key, body_id, "NODE_REVOKE", {"node_id": "body-2"})
    with pytest.raises(ValueError, match="already revoked"):
        apply(home, key, body_id, "NODE_REVOKE", {"node_id": "body-2"})
    apply(home, key, body_id, "NODE_ENROLL", enroll_body("body-3", new_key()[1]))
    for bad in ({"node_id": "body-3", "why": "x"}, {}, {"node_id": "body-3", "node_ids": ["body-3"]}):
        with pytest.raises(ValueError, match="exactly node_id"):
            apply(home, key, body_id, "NODE_REVOKE", bad)
    with pytest.raises(ValueError, match="names no enrolled node"):
        apply(home, key, body_id, "NODE_REVOKE", {"node_id": ["body-3"]})
    assert len(events(home, "node.revoked")) == 1 and states(home)["body-3"]["state"] == "ACTIVE"


def test_the_same_signed_command_applied_again_after_a_crash_changes_nothing(tmp_path):
    """A crash after the node record but before command.accepted re-applies the same envelope: same digest, same
    record, no second event and no refusal of the founder's own command."""
    home, key, body_id, _ = make_body(tmp_path)
    with Body(home) as b:
        first = compute.enroll_node(b.journal, enroll_body("body-2", new_key()[1]), "digest-1")
        assert compute.enroll_node(b.journal, enroll_body("body-2", new_key()[1]), "digest-1") == first
        revoked = compute.revoke_node(b.journal, {"node_id": "body-2"}, "digest-2")
        assert compute.revoke_node(b.journal, {"node_id": "body-2"}, "digest-2") == revoked
        assert len(b.journal.replay("node.enrolled")) == 1 and len(b.journal.replay("node.revoked")) == 1


def test_refused_node_commands_in_the_inbox_are_recorded_and_the_body_runs_on(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    apply(home, key, body_id, "NODE_ENROLL", enroll_body("body-2", new_key()[1]))
    phone = delegate_every_device_kind(home, key, body_id)
    drop(home, sign_command(phone, "NODE_REVOKE", {"node_id": "body-2"}, body_id=body_id))
    drop(home, signed(key, body_id, "NODE_ENROLL", enroll_body("body-2", new_key()[1])))
    run(home, Clock(), ticks=1)
    reasons = sorted(e["reason"] for e in events(home, "command.rejected"))
    assert len(reasons) == 2
    assert any("device key may not sign NODE_REVOKE" in r for r in reasons)
    assert any("already enrolled and active" in r for r in reasons)
    assert states(home)["body-2"]["state"] == "ACTIVE"


def test_cli_enrolls_revokes_and_lists_nodes(tmp_path, capsys):
    home, key, body_id, _ = make_body(tmp_path)
    keyfile = tmp_path / "founder.pem"
    cone_file = tmp_path / "cone.json"
    cone_file.write_text(json.dumps(cone()))
    _, node_public = new_key()
    expires = stamp(datetime.now(timezone.utc) + timedelta(days=3))

    def cli_out(*argv) -> str:
        assert cli.main(["--home", str(home), *argv]) == 0
        return capsys.readouterr().out

    cli_out("node", "enroll", "body-2", "--pubkey", node_public, "--cone", str(cone_file), "--expires-at", expires,
            "--key", str(keyfile), "--no-passphrase")
    run(home, Clock(), ticks=1)
    with Body(home):   # a running body holds the ledger's one writer: the list reads beside it, never as a writer
        listed = json.loads(cli_out("node", "list"))["nodes"]
    assert [(n["node_id"], n["state"], n["expires_at"]) for n in listed] == [("body-2", "ACTIVE", expires)]
    cli_out("node", "revoke", "body-2", "--key", str(keyfile), "--no-passphrase")
    run(home, Clock(), ticks=1)
    assert [n["state"] for n in json.loads(cli_out("node", "list"))["nodes"]] == ["REVOKED"]
    accepted = [e["kind"] for e in events(home, "command.accepted")]
    assert accepted.count("NODE_ENROLL") == 1 and accepted.count("NODE_REVOKE") == 1
    assert json.loads(cli_out("--home", str(tmp_path / "none"), "node", "list")) == {
        "nodes": [], "reality_status": "NO_BODY_LEDGER"}
