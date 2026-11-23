"""An acquired binary's provenance names the OS package that owns it (acceptance C.G12).

On a body with dpkg, Genesis records beside the DEP-5 licence:
- the owning package;
- its installed version, read from dpkg's status database as a file (no new spawn);
- the copyright file the licence was read from.

The owning package is whatever dpkg names on the host: coreutils on Debian, rust-coreutils on newer Ubuntu.

Where no package manager answers, each field says ``unresolved`` and the binary is acquired exactly as before. A
version is never guessed: a status database that is missing, oversized, not installed, malformed or ambiguous gives
None.
"""
import hashlib
import shutil

import pytest

from greg import genesis as genesis_mod
from greg import licensing
from greg.body import Body
from greg.capabilities import installed_binary
from tests.greg_fixtures import Clock, drop, make_body, mission, signed

DPKG = shutil.which("dpkg-query") is not None and licensing.DPKG_STATUS.is_file()
SHA256SUM = installed_binary("sha256sum")
CID = "acquired.hash.sha256.sha256sum"


def _hash_spec(data):
    doc = data / "notes.txt"
    doc.write_text("provenance\n")
    check = {"check_id": "digest", "description": "the notes have the founder's expected digest",
             "sensor": {"function": "hash.sha256", "params": {"path": str(doc)}, "target": "fs:notes.txt"},
             "predicate": {"op": "equals", "field": "sha256", "value": hashlib.sha256(b"provenance\n").hexdigest()}}
    return mission("m:hash", checks=[check], strategies=[], ceiling="read_only", budget=1.0,
                   capabilities=["fs.read", "acquired.hash.sha256.*"], auto_attach=True)


def _run(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _hash_spec(data)))
    clock = Clock()
    body = Body(home, clock=clock, builder=None).open()
    body.boot()
    states = []
    for _ in range(4):
        clock.advance(30)
        states.append(body.tick()["missions"][0]["state"])
    return body, states


def _provenance(body, cid=CID):
    manifests = [e.payload["manifest"] for e in body.journal.replay("capability.registered")
                 if e.payload["manifest"]["capability_id"] == cid]
    assert manifests, f"{cid} was not registered"
    return manifests[-1]["provenance"]


@pytest.mark.skipif(not (DPKG and SHA256SUM and licensing.system_binary(SHA256SUM or "/")),
                    reason="needs a dpkg body on which a package owns sha256sum")
def test_sha256sum_provenance_names_its_owning_package_installed_version_and_copyright_file(tmp_path):
    body, states = _run(tmp_path)
    assert "ACHIEVED" in states
    prov = _provenance(body)
    owner = _dpkg_owner(SHA256SUM)          # coreutils on Debian; rust-coreutils on newer Ubuntu: whatever dpkg says
    assert prov["package"] == owner
    assert prov["package_version"] == licensing.installed_package_version(owner) != genesis_mod.UNRESOLVED
    assert prov["license"] and prov["license"] == prov["license_assessment"]["parts"][0]["expression"][:200]
    assert prov["license_source"] == f"/usr/share/doc/{owner}/copyright (Debian DEP-5 copyright file)"
    assert prov["license_assessment"]["package"] == owner
    body.close()


def _dpkg_owner(binary):
    """The package dpkg itself names for a binary, asked independently of the code under test."""
    import os
    import subprocess
    out = subprocess.run(["dpkg-query", "-S", os.path.realpath(binary)], capture_output=True, text=True).stdout
    return out.split(":", 1)[0].split(":")[0].strip()


@pytest.mark.skipif(not SHA256SUM, reason="sha256sum is needed")
def test_on_a_body_no_package_manager_answers_every_field_is_unresolved_and_the_binary_still_serves(
        tmp_path, monkeypatch):
    monkeypatch.setattr(licensing, "system_binary", lambda binary: None)       # macOS, or a hand-built binary
    body, states = _run(tmp_path)
    assert "ACHIEVED" in states and body.registry.state[CID] == "ATTACHED"    # still not refused
    prov = _provenance(body)
    assert prov["package"] == prov["package_version"] == prov["license_source"] == genesis_mod.UNRESOLVED
    assert "license_assessment" not in prov
    body.close()


@pytest.mark.skipif(not (DPKG and SHA256SUM), reason="needs dpkg and sha256sum")
def test_a_binary_no_package_owns_is_unresolved_on_a_dpkg_body(tmp_path):
    loose = tmp_path / "bin" / "sha256sum"
    loose.parent.mkdir()
    shutil.copy2(SHA256SUM, loose)
    recorded = genesis_mod._binary_license(str(loose))
    assert recorded["package"] == recorded["package_version"] == genesis_mod.UNRESOLVED


STANZA = "Package: {p}\nStatus: {s}\nArchitecture: {a}\nVersion: {v}\nDescription: x\n continued: line\n"


def _status(tmp_path, *stanzas):
    path = tmp_path / "status"
    path.write_text("\n".join(stanzas))
    return path


def test_the_version_is_read_only_from_an_installed_stanza_that_all_architectures_agree_on(tmp_path):
    ok = "install ok installed"
    agree = _status(tmp_path, STANZA.format(p="zlib1g", s=ok, a="amd64", v="1:1.3.dfsg-3"),
                    STANZA.format(p="zlib1g", s=ok, a="i386", v="1:1.3.dfsg-3"),
                    STANZA.format(p="zlib1g-dev", s=ok, a="amd64", v="9.9"))
    assert licensing.installed_package_version("zlib1g", agree) == "1:1.3.dfsg-3"
    assert licensing.installed_package_version("zlib", agree) is None                 # names match exactly
    split = _status(tmp_path, STANZA.format(p="zlib1g", s=ok, a="amd64", v="1:1.3"),
                    STANZA.format(p="zlib1g", s=ok, a="i386", v="1:1.2"))
    assert licensing.installed_package_version("zlib1g", split) is None               # ambiguous: no guess
    removed = _status(tmp_path, STANZA.format(p="zlib1g", s="deinstall ok config-files", a="amd64", v="1:1.3"))
    assert licensing.installed_package_version("zlib1g", removed) is None             # not installed
    odd = _status(tmp_path, STANZA.format(p="zlib1g", s=ok, a="amd64", v="1.3; rm -rf /"))
    assert licensing.installed_package_version("zlib1g", odd) is None                 # not a Debian version
    assert licensing.installed_package_version("zlib1g", tmp_path / "missing") is None


def test_an_oversized_status_database_is_not_read(tmp_path, monkeypatch):
    path = _status(tmp_path, STANZA.format(p="zlib1g", s="install ok installed", a="amd64", v="1:1.3"))
    monkeypatch.setattr(licensing, "MAX_DPKG_STATUS_BYTES", path.stat().st_size - 1)
    assert licensing.installed_package_version("zlib1g", path) is None
