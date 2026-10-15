"""#9/#10 non-privileged hardening: approval gate, no root images, root-confined unpacking. Nothing here runs runc,
runsc, sudo or any privileged operation, and nothing touches the network."""
import io
import json
import os
import subprocess
import tarfile

import pytest

from foundry.systems import containers, sandbox
from foundry.systems.containers import ContainerError, _extract, runtime_spec, secure_join


def test_privileged_runtimes_are_refused_without_named_host_approval(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: calls.append(a) or None)
    monkeypatch.delenv(containers.APPROVAL_ENV, raising=False)
    for name in ("runc", "runsc"):
        with pytest.raises(ContainerError, match="not approved"):
            containers.run(tmp_path / "bundle", runtime_name=name, container_id="c1")
    monkeypatch.setenv(containers.APPROVAL_ENV, "some-other-host")       # approval for another machine is no approval
    with pytest.raises(ContainerError, match="not approved"):
        containers.run(tmp_path / "bundle", runtime_name="runsc", container_id="c2")
    with pytest.raises(ContainerError, match="not approved"):
        containers._privileged(["true"])
    assert calls == [] and not list(tmp_path.glob(".*state*")), "nothing was executed or created"


def test_the_sandbox_inherits_the_refusal(tmp_path, monkeypatch):
    monkeypatch.delenv(containers.APPROVAL_ENV, raising=False)
    with pytest.raises(ContainerError, match="not approved"):
        containers.run(tmp_path / "b", runtime_name="runsc", container_id="probe")
    assert sandbox.containers is containers


def test_runtime_spec_is_fail_closed_and_root_images_are_refused(tmp_path):
    spec = runtime_spec(["/bin/true"], env=[])
    p = spec["process"]
    assert p["noNewPrivileges"] is True and all(v == [] for v in p["capabilities"].values())
    assert p["user"]["uid"] != 0 and spec["root"]["readonly"] is True
    assert {"type": "network"} in spec["linux"]["namespaces"] and spec["linux"]["resources"]["pids"]["limit"] <= 128
    layout = tmp_path / "layout"
    (layout / "blobs" / "sha256").mkdir(parents=True)
    config = {"config": {"Entrypoint": ["/bin/true"], "Env": [], "User": "0:0"}}
    cdata = json.dumps(config).encode()
    import hashlib
    cdig = hashlib.sha256(cdata).hexdigest()
    (layout / "blobs" / "sha256" / cdig).write_bytes(cdata)
    manifest = {"config": {"digest": "sha256:" + cdig}}
    mdata = json.dumps(manifest).encode()
    mdig = hashlib.sha256(mdata).hexdigest()
    (layout / "blobs" / "sha256" / mdig).write_bytes(mdata)
    monkey_unpack = lambda layout_, rootfs: {"image": "sha256:" + mdig, "rootfs": str(rootfs)}
    original = containers.unpack
    containers.unpack = monkey_unpack
    try:
        with pytest.raises(ContainerError, match="root"):
            containers.prepare_bundle(layout, tmp_path / "bundle")
    finally:
        containers.unpack = original


def _layer(entries):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for kind, name, extra in entries:
            info = tarfile.TarInfo(name)
            if kind == "file":
                data = extra.encode()
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
            elif kind == "sym":
                info.type, info.linkname = tarfile.SYMTYPE, extra
                tar.addfile(info)
            elif kind == "link":
                info.type, info.linkname = tarfile.LNKTYPE, extra
                tar.addfile(info)
            elif kind == "dev":
                info.type, info.devmajor, info.devminor = tarfile.CHRTYPE, 1, 3
                tar.addfile(info)
    buf.seek(0)
    return tarfile.open(fileobj=buf, mode="r")


def test_hostile_layers_stay_inside_the_root(tmp_path):
    outside = tmp_path / "host-secret"
    outside.write_text("host")
    rootfs = tmp_path / "rootfs"
    rootfs.mkdir()
    tar = _layer([("sym", "etc", "/"), ("sym", "up", "../../.."), ("file", "etc/passwd", "image"),
                  ("file", "up/host-secret", "overwrite?"), ("file", ".profile", "dotfile"),
                  ("dev", "dev-null", None)])
    for m in tar.getmembers():
        _extract(tar, m, rootfs)
    assert outside.read_text() == "host", "a symlinked parent cannot write outside the root"
    assert (rootfs / "passwd").read_text() == "image"            # "/etc" resolved inside the root
    assert (rootfs / ".profile").read_text() == "dotfile"        # dotfiles keep their names
    assert not (rootfs / "dev-null").exists()                    # device nodes are never created
    for bad in ("../escape", "a/../../escape"):
        bad_tar = _layer([("file", bad, "x")])
        with pytest.raises(ContainerError, match="escapes"):
            _extract(bad_tar, bad_tar.getmembers()[0], rootfs)
    assert (rootfs / "host-secret").read_text() == "overwrite?"   # "up/..." landed inside the root
    link_tar = _layer([("link", "hard", "/../../host-secret")])
    _extract(link_tar, link_tar.getmembers()[0], rootfs)
    assert os.path.samefile(rootfs / "hard", rootfs / "host-secret")      # the hard link resolved inside the root
    assert not os.path.samefile(rootfs / "hard", outside) and outside.read_text() == "host"
    assert secure_join(rootfs, "/../../../../host-secret").parent == rootfs
