"""Encrypted native continuity, with externally retained laboratory root trust.

These are real Ed25519/AES/Scrypt operations. They do not authenticate Alfonso,
prove physical off-device custody, or establish distributed consensus.
"""
from datetime import timedelta
import json
from pathlib import Path

import pytest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from greg import backup
from greg.body import Body, BodyError
from greg.founder import key_id, public_bytes
from tests.greg_fixtures import make_body, signed

PASSWORD = b"laboratory backup passphrase"


def export(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    (home / "secrets.json").write_text(json.dumps({"example_handle": "private-laboratory-credential"}))
    (home / "STOP").write_text("deliberate local offline export")
    archive, witness = tmp_path / "off-body.greg", tmp_path / "authority.json"
    result = backup.export_backup(home, archive, witness, key, PASSWORD)
    reference = json.loads(witness.read_text())
    public = public_bytes(key.public_key()).hex()
    return home, key, body_id, archive, reference, public, result


def test_real_encrypted_backup_preserves_state_but_cannot_activate_without_fresh_authority(tmp_path):
    home, key, body_id, archive, reference, public, result = export(tmp_path)
    assert b"private-laboratory-credential" not in archive.read_bytes()
    assert archive.stat().st_mode & 0o077 == 0
    target = tmp_path / "replacement-body"
    restored = backup.restore_backup(archive, target, PASSWORD, reference, public)
    assert restored["status"] == "AUTHORITY_VERIFICATION_REQUIRED" and not restored["service_started"]
    assert (target / "secrets.json").read_bytes() == (home / "secrets.json").read_bytes()
    assert (target / "witness.key").read_bytes() == (home / "witness.key").read_bytes()
    with pytest.raises(BodyError, match="restored authority is unverified"):
        Body(target).open()
    fresh = backup.checkpoint(home, key, challenge=restored["restore_challenge"])
    verified = backup.verify_restored_authority(target, fresh, public)
    assert verified["status"] == "CURRENT_AUTHORITY_VERIFIED"
    assert verified["shutdown_preserved"] and not verified["authority_created"]
    assert (target / "STOP").read_bytes() == (home / "STOP").read_bytes()
    with Body(target) as body:
        assert body.config["body_id"] == body_id
        assert body.enrolled_keys() == {key_id(public): public}
        assert body._stop_now()
        assert body.ledger.verify_chain()[0]


@pytest.mark.parametrize("attack", ["wrong_key", "wrong_password", "tampered_ciphertext", "stale_head"])
def test_invalid_encryption_authentication_or_newer_source_refuses_before_destination_creation(tmp_path, attack):
    home, key, body_id, archive, reference, public, _ = export(tmp_path)
    if attack == "wrong_key":
        public = public_bytes(Ed25519PrivateKey.generate().public_key()).hex()
    elif attack == "wrong_password":
        pass
    elif attack == "tampered_ciphertext":
        encoded = json.loads(archive.read_text())
        cipher = encoded["ciphertext"]
        encoded["ciphertext"] = ("A" if cipher[0] != "A" else "B") + cipher[1:]
        archive.write_text(json.dumps(encoded))
    else:
        with Body(home) as body:
            body.apply(signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": "fs.write"}))
        reference = backup.checkpoint(home, key)
    target = tmp_path / "must-not-be-created"
    with pytest.raises(backup.BackupError):
        backup.restore_backup(archive, target, b"incorrect password" if attack == "wrong_password" else PASSWORD, reference, public)
    assert not target.exists()


def test_static_or_expired_checkpoint_cannot_release_restore_guard(tmp_path):
    home, key, _, archive, reference, public, _ = export(tmp_path)
    target = tmp_path / "replacement"
    restored = backup.restore_backup(archive, target, PASSWORD, reference, public)
    with pytest.raises(backup.BackupError, match="fresh restoration-specific"):
        backup.verify_restored_authority(target, reference, public)
    fresh = backup.checkpoint(home, key, challenge=restored["restore_challenge"])
    with pytest.raises(backup.BackupError, match="replay/expiry"):
        backup.verify_restored_authority(target, fresh, public, now=backup._now() + timedelta(hours=1))
    assert (target / "RESTORE_PENDING").exists()


def test_new_revocation_after_restore_invalidates_old_backup_even_with_fresh_signature(tmp_path):
    home, key, body_id, archive, reference, public, _ = export(tmp_path)
    target = tmp_path / "replacement"
    restored = backup.restore_backup(archive, target, PASSWORD, reference, public)
    with Body(home) as body:
        body.apply(signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": "fs.write"}))
        body.apply(signed(key, body_id, "BODY_PAUSE", {}))
    fresh = backup.checkpoint(home, key, challenge=restored["restore_challenge"])
    with pytest.raises(backup.BackupError, match="current source differs"):
        backup.verify_restored_authority(target, fresh, public)
    assert (target / "RESTORE_PENDING").exists()
    with pytest.raises(BodyError):
        Body(target).open()


def test_source_requires_persisted_stop_and_body_writer_cannot_be_snapshotted(tmp_path):
    home, key, _, _ = make_body(tmp_path)
    with pytest.raises(backup.BackupError, match="persisted.*STOP"):
        backup.export_backup(home, tmp_path / "archive", tmp_path / "checkpoint", key, PASSWORD)
    (home / "STOP").write_text("local stop")
    with Body(home):
        with pytest.raises(backup.BackupError, match="body is running"):
            backup.export_backup(home, tmp_path / "archive", tmp_path / "checkpoint", key, PASSWORD)


def test_pending_clone_cannot_certify_itself_as_the_authoritative_source(tmp_path):
    _, key, _, archive, reference, public, _ = export(tmp_path)
    target = tmp_path / "replacement"
    restored = backup.restore_backup(archive, target, PASSWORD, reference, public)
    with pytest.raises(backup.BackupError, match="cannot export or certify"):
        backup.checkpoint(target, key, challenge=restored["restore_challenge"])


def test_export_scope_rejects_symlinks_existing_files_and_inside_body_archive(tmp_path):
    home, key, _, _ = make_body(tmp_path)
    (home / "STOP").write_text("stop")
    with pytest.raises(backup.BackupError, match="outside the body"):
        backup.export_backup(home, home / "archive", tmp_path / "checkpoint", key, PASSWORD)
    (home / "symlink").symlink_to(tmp_path / "elsewhere")
    with pytest.raises(backup.BackupError, match="symlinks"):
        backup.export_backup(home, tmp_path / "archive", tmp_path / "checkpoint", key, PASSWORD)
    assert not (tmp_path / "archive").exists()


def test_restore_will_not_overwrite_body_or_let_local_start_clear_revocation_guard(tmp_path):
    home, _, _, archive, reference, public, _ = export(tmp_path)
    with pytest.raises(backup.BackupError, match="destination must not exist"):
        backup.restore_backup(archive, home, PASSWORD, reference, public)
    target = tmp_path / "replacement"
    backup.restore_backup(archive, target, PASSWORD, reference, public)
    from greg.cli import main
    assert main(["--home", str(target), "start", "--local"]) == 2
    assert main(["--home", str(target), "run", "--clear-stop", "--max-ticks", "1"]) == 2
    assert (target / "STOP").exists() and (target / "RESTORE_PENDING").exists()


@pytest.mark.parametrize("corrupt_after_interrupt", [False, True])
def test_interrupted_verification_is_idempotent_but_does_not_hide_corruption(tmp_path, monkeypatch, corrupt_after_interrupt):
    home, key, _, archive, reference, public, _ = export(tmp_path)
    target = tmp_path / "replacement"
    restored = backup.restore_backup(archive, target, PASSWORD, reference, public)
    fresh = backup.checkpoint(home, key, challenge=restored["restore_challenge"])
    unlink = Path.unlink
    def interrupt(path, *a, **kw):
        if path == target / "RESTORE_PENDING":
            raise OSError("injected interruption after durable verification, before guard removal")
        return unlink(path, *a, **kw)
    monkeypatch.setattr(Path, "unlink", interrupt)
    with pytest.raises(OSError, match="injected interruption"):
        backup.verify_restored_authority(target, fresh, public)
    monkeypatch.setattr(Path, "unlink", unlink)
    assert (target / "RESTORE_PENDING").exists()
    if corrupt_after_interrupt:
        (target / "secrets.json").write_text('{"tampered":true}')
        with pytest.raises(backup.BackupError, match="restored state changed"):
            backup.verify_restored_authority(target, fresh, public)
        assert (target / "RESTORE_PENDING").exists()
    else:
        assert backup.verify_restored_authority(target, fresh, public)["status"] == "CURRENT_AUTHORITY_VERIFIED"
        with Body(target) as body:
            assert len(body.journal.replay("body.restore_authority_verified")) == 1
