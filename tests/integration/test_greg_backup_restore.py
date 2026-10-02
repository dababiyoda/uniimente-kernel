"""Complete offline continuity ceremony through the canonical CLI entry point."""
import json
from pathlib import Path
import pytest

from greg import backup
from greg.body import Body
from greg.cli import main
from greg.founder import public_bytes
from tests.greg_fixtures import make_body, signed


def test_cli_native_encrypted_restore_replays_revocation_pause_nonce_and_identity(tmp_path, monkeypatch, capsys):
    home, key, body_id, _ = make_body(tmp_path)
    key_path = tmp_path / "founder.pem"
    detached = signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": "fs.write"})
    with Body(home) as body:
        body.apply(detached)
        body.apply(signed(key, body_id, "BODY_PAUSE", {}))
        body.apply(signed(key, body_id, "BODY_STOP", {}))
    archive, reference_path = tmp_path / "encrypted-body.greg", tmp_path / "authority-reference.json"
    monkeypatch.setattr("greg.cli.getpass.getpass", lambda _: "laboratory backup passphrase")
    assert main(["--home", str(home), "backup", "export", "--out", str(archive), "--checkpoint", str(reference_path),
                 "--key", str(key_path), "--no-passphrase"]) == 0
    capsys.readouterr()
    replacement = tmp_path / "replacement"
    public = public_bytes(key.public_key()).hex()
    assert main(["--home", str(replacement), "backup", "restore", "--archive", str(archive),
                 "--checkpoint", str(reference_path), "--trusted-founder", public]) == 0
    restored = json.loads(capsys.readouterr().out)
    fresh_path = tmp_path / "fresh-authority-reference.json"
    assert main(["--home", str(home), "backup", "checkpoint", "--challenge", restored["restore_challenge"],
                 "--out", str(fresh_path), "--key", str(key_path), "--no-passphrase"]) == 0
    capsys.readouterr()
    assert main(["--home", str(replacement), "backup", "verify-authority", "--checkpoint", str(fresh_path),
                 "--trusted-founder", public]) == 0
    capsys.readouterr()
    assert (replacement / "STOP").exists()
    with Body(replacement) as body:
        assert body.config["body_id"] == body_id
        assert body.registry.state["fs.write"] == "DETACHED"
        assert body.paused() and body._stop_now()
        assert body.apply(detached)["status"] == "ALREADY_APPLIED"
        assert len(body.journal.replay("body.restore_authority_verified")) == 1
        assert body.ledger.verify_chain()[0]
        assert not body.journal.replay("mission.achieved")
