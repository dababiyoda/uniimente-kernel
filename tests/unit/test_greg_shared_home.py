"""A body home on a shared or network folder is refused: by greg init, when a body opens, and by restore.

On 9p and FUSE (ChromeOS shares /mnt/chromeos over 9p or virtio-fs), NFS, SMB and cluster filesystems, Linux can keep
serving its cached copy of a file after another machine replaced or deleted it, beyond any check the evidence ledger
can make, so recorded evidence could vanish without notice. The filesystem is the one statfs(2) reports for the path
(or its nearest existing ancestor), as greg/chromebook/install.sh asks with `stat -f`.
"""
from __future__ import annotations

import os
import sys

import pytest

from greg import body as body_mod
from greg.body import Body, BodyError, init_body, shared_filesystem
from greg.recovery import restore_body


def _share(monkeypatch, folder, magic):
    real = body_mod._statfs_type
    monkeypatch.setattr(body_mod, "_statfs_type", lambda path: magic if path == str(folder) else real(path))


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="statfs(2) is asked on Linux")
def test_statfs_reports_the_kernels_filesystem_type():
    assert body_mod._statfs_type("/proc") == 0x9FA0                         # PROC_SUPER_MAGIC
    assert body_mod._statfs_type("/no/such/path/here") is None


@pytest.mark.parametrize("magic", sorted(body_mod._SHARED_FILESYSTEMS))
def test_init_refuses_a_home_on_a_shared_or_network_folder(tmp_path, monkeypatch, magic):
    share = tmp_path / "share"
    share.mkdir()
    _share(monkeypatch, share, magic)
    with pytest.raises(BodyError, match="shared or network filesystem") as refused:
        init_body(share / "greg" / "body", read_roots=[str(tmp_path)])       # not there yet: its folder is asked
    assert body_mod._SHARED_FILESYSTEMS[magic] in str(refused.value)
    assert not (share / "greg").exists()
    assert shared_filesystem(tmp_path / "elsewhere") is None                 # outside the share: accepted
    init_body(tmp_path / "body", read_roots=[str(tmp_path)])


def test_a_body_moved_onto_a_shared_folder_does_not_open(tmp_path, monkeypatch):
    home = tmp_path / "body"
    init_body(home, read_roots=[str(tmp_path)])
    _share(monkeypatch, home, 0x01021997)
    with pytest.raises(BodyError, match=r"shared or network filesystem \(9p\)"):
        Body(home).open()
    monkeypatch.undo()
    body = Body(home)
    body.open()
    body.close()


def test_restore_never_writes_onto_a_shared_folder(tmp_path, monkeypatch):
    share = tmp_path / "share"
    share.mkdir()
    _share(monkeypatch, share, 0x65735546)
    with pytest.raises(BodyError, match="shared or network filesystem"):
        restore_body(tmp_path / "store", "0" * 64, share / "greg")
    assert os.listdir(share) == []
