"""Actual guarded packaging, not just a registry or standalone component."""
import hashlib
import json
from pathlib import Path
import tarfile

import pytest

from foundry.systems import build
from greg import foundry_bridge
from greg.capabilities import CapabilityError
from greg.foundry_worker import source_files
from tests.unit.test_greg_foundry_worker import context


def test_guarded_owned_bundle_rebuilds_in_fixed_independent_child(tmp_path):
    ctx = context(tmp_path)
    created = foundry_bridge.apply({"system": 53, "op": "build"}, ctx)
    assert created["result"]["files"] == len(source_files())
    bundle = ctx.workspace / "foundry" / "system-53" / created["result"]["bundle"]
    assert hashlib.sha256(bundle.read_bytes()).hexdigest() == created["result"]["sha256"]
    with tarfile.open(bundle, "r:gz") as archive:
        names = archive.getnames()
        manifest = json.load(archive.extractfile("BUILD-MANIFEST.json"))
    assert "foundry/systems/community.py" in names
    assert "greg/foundry_protocol_worker.py" in names
    assert set(names) == set(manifest["files"]) | {"BUILD-MANIFEST.json"}
    verified = foundry_bridge.apply({"system": 53, "op": "verify"}, ctx)
    assert verified["result"]["reproduced"]
    assert verified["result"]["expected"] == created["result"]["sha256"]
    assert verified["execution"]["persistence"] == "atomic-store-commit"


def test_source_inventory_cannot_alias_unreviewed_data(tmp_path, monkeypatch):
    from greg import foundry_worker
    # Validation runs before granting the reviewed source read allowance.
    original = Path.read_text
    def forged(path, *args, **kwargs):
        if path.name == "owned-source.json":
            return json.dumps({"version": "owned-source/1", "files": ["../body-key.json"]})
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", forged)
    with pytest.raises(ValueError, match="source path"):
        foundry_worker.source_files()


def test_inventory_covers_every_current_owned_source_file():
    assert source_files() == build._files(build.ROOT)
