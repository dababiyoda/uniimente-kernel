"""``greg rehearse --dir`` must not write a throwaway key into a real GREG home or an existing body.

Aimed at ``GREG_HOME``, at ``~/.uniimente/greg``, at a directory inside either, at a directory that
contains either, or at a directory that holds ``body.json``, the base command creates
``<dir>/body`` and writes an unencrypted ``REHEARSAL-throwaway-founder-key.pem`` in ``<dir>``.
``greg rehearse --path --dir`` does the same. Both refuse before creating anything.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import site
import subprocess
import sys
import time

import pytest

from greg import rehearsal

ROOT = Path(__file__).resolve().parents[2]
KEY = "REHEARSAL-throwaway-founder-key.pem"
PYTHONPATH = os.pathsep.join([str(ROOT), *site.getsitepackages(), site.getusersitepackages()])


def _files(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def _invoke(args: list[str], env: dict, watch: Path) -> tuple[int | None, str, str]:
    """Run the command until it exits, or until it writes under ``watch`` (the base keeps running)."""
    before = set(_files(watch))
    proc = subprocess.Popen(args, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    deadline = time.monotonic() + 30
    while proc.poll() is None and time.monotonic() < deadline:
        if set(_files(watch)) - before:
            break
        time.sleep(0.05)
    if proc.poll() is None:
        proc.kill()
        proc.wait(timeout=10)
    out, err = proc.communicate(timeout=10)
    return proc.returncode, out, err


def _layout(tmp_path: Path, kind: str) -> tuple[Path, dict, str]:
    user = tmp_path / "user"
    user.mkdir()
    env_home = tmp_path / "env-home"
    env_home.mkdir()
    (env_home / "body.json").write_text('{"body_id":"founder"}\n')
    env = os.environ.copy()
    env.pop("GREG_HOME", None)
    env["HOME"] = str(user)
    env["PYTHONPATH"] = PYTHONPATH
    env["GREG_HOME"] = str(env_home)
    if kind == "equals_env_home":
        return env_home, env, "GREG home"
    if kind == "equals_env_home_empty":
        empty = tmp_path / "empty-home"
        empty.mkdir()
        env["GREG_HOME"] = str(empty)
        return empty, env, "GREG home"
    if kind == "inside_env_home":
        nested = env_home / "scratch"
        nested.mkdir()
        return nested, env, "GREG home"
    if kind == "contains_env_home":
        parent = tmp_path / "parent"
        parent.mkdir()
        home = parent / "real-home"
        home.mkdir()
        (home / "body.json").write_text('{"body_id":"founder"}\n')
        env["GREG_HOME"] = str(home)
        return parent, env, "GREG home"
    if kind == "holds_body_json":
        other = tmp_path / "other-body"
        other.mkdir()
        (other / "body.json").write_text("{}\n")
        return other, env, "body.json"
    if kind == "equals_default_home":
        env.pop("GREG_HOME")
        default = user / ".uniimente" / "greg"
        default.mkdir(parents=True)
        (default / "body.json").write_text('{"body_id":"founder"}\n')
        return default, env, "GREG home"
    if kind == "inside_default_home":
        scratch = user / ".uniimente" / "greg" / "scratch"
        scratch.mkdir(parents=True)
        return scratch, env, "GREG home"
    if kind == "symlink_to_env_home":
        link = tmp_path / "link-home"
        link.symlink_to(env_home, target_is_directory=True)
        return link, env, "GREG home"
    raise AssertionError(kind)


@pytest.mark.parametrize("command", [["rehearse"], ["rehearse", "--path"]])
@pytest.mark.parametrize("kind", [
    "equals_env_home",
    "equals_env_home_empty",
    "inside_env_home",
    "contains_env_home",
    "holds_body_json",
    "equals_default_home",
    "inside_default_home",
    "symlink_to_env_home",
])
def test_the_command_refuses_a_dir_that_would_write_the_throwaway_key_into_a_real_home(tmp_path, command, kind):
    target, env, fragment = _layout(tmp_path, kind)
    before = _files(tmp_path)
    code, out, err = _invoke([sys.executable, "-m", "greg", *command, "--dir", str(target)], env, tmp_path)
    after = _files(tmp_path)
    new = sorted(set(after) - set(before))
    changed = sorted(name for name in before if after.get(name) != before[name])
    detail = f"code={code} new={new} changed={changed}\nstdout={out}\nstderr={err}"
    assert code == 1, detail
    assert not new and not changed, detail
    payload = json.loads(out)
    assert payload["label"] == "REHEARSAL" and payload["ok"] is False
    assert fragment in payload["error"]
    if "--path" in command:
        assert payload["mode"] == "path"
    else:
        assert "mode" not in payload
    assert not list(tmp_path.rglob(KEY))


def test_a_scratch_directory_is_not_a_founder_home(tmp_path, monkeypatch):
    user = tmp_path / "user"
    user.mkdir()
    monkeypatch.setenv("GREG_HOME", str(tmp_path / "env-home"))
    monkeypatch.setattr(rehearsal.Path, "home", lambda: user)
    scratch = tmp_path / "scratch" / "run"
    assert rehearsal.refuse_rehearsal_directory(scratch) == scratch.resolve()
    assert not scratch.exists()
    assert not list(tmp_path.rglob(KEY))


def test_a_relative_directory_inside_the_home_is_refused_before_anything_is_created(tmp_path, monkeypatch):
    user = tmp_path / "user"
    user.mkdir()
    home = tmp_path / "env-home"
    home.mkdir()
    monkeypatch.setenv("GREG_HOME", str(home))
    monkeypatch.setattr(rehearsal.Path, "home", lambda: user)
    monkeypatch.chdir(home)
    with pytest.raises(rehearsal.RehearsalDirError, match="GREG home"):
        rehearsal.refuse_rehearsal_directory(Path("nested"))
    assert not (home / "nested").exists()
    assert not list(tmp_path.rglob(KEY))
