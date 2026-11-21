"""The DALEOBANKS bridge's confined door shows its organ's interpreter (no organ checkout needed)."""
from __future__ import annotations

import pytest

from greg import daleobanks_bridge as bridge


def test_the_door_shows_the_organ_venv_itself_not_only_its_resolved_base_python(tmp_path, monkeypatch):
    """Found by CI job 8 once its runner could use bubblewrap: the organ venv lived under the hidden $HOME and only
    the base Python its symlink resolves to was shown, so the interpreter path did not exist inside the namespace
    ('No such file or directory: .../daleobanks-venv/bin/python'). A real venv root is shown; a bare bin/ is not."""
    import types
    from foundry.systems import relay_door
    from greg import worker_isolation
    base = tmp_path / "base" / "bin"
    base.mkdir(parents=True)
    (base / "python3").write_text("#!/bin/sh\n")
    venv = tmp_path / "home" / "organs" / "daleobanks-venv"
    (venv / "bin").mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text("home = %s\n" % base)
    (venv / "bin" / "python").symlink_to(base / "python3")
    loose = tmp_path / "home" / "bin"
    loose.mkdir()
    (loose / "python").symlink_to(base / "python3")
    shown = []

    def capture(**kwargs):
        shown.append(list(kwargs["readonly"]))
        raise RuntimeError("captured")
    monkeypatch.setattr(worker_isolation, "_backend", lambda **_: ("bubblewrap", 0, None, []))
    monkeypatch.setattr(relay_door, "namespace_argv", capture)
    ctx = types.SimpleNamespace(manifest=types.SimpleNamespace(capability_id="daleobanks.verify", egress_allowlist=()),
                                egress=types.SimpleNamespace(journal=None, connect=None, proxy=None))
    for python in (venv / "bin" / "python", loose / "python"):
        with pytest.raises(RuntimeError, match="captured"):
            bridge._behind_door([str(python), "-c", "pass"], {}, {}, ctx, root=tmp_path, ledger_dir=tmp_path,
                                draft=tmp_path / "d.txt")
    assert str(venv) in shown[0] and str(base.parent) in shown[0]
    assert str(loose.parent) not in shown[1] and str(tmp_path / "home") not in shown[1]
