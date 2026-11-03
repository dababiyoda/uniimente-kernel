"""greg/chromebook/install.sh: one command to a designated Body 1, idempotent, honest refusals.

Exercised in a Linux container without systemd, so --no-service and --allow-other-linux
are used; the ChromeOS path, the systemd user service and Alfonso's passphrase-protected
key are NOT exercised here. This proves the composition of existing greg commands, not
a Chromebook install.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "greg/chromebook/install.sh"
pytestmark = pytest.mark.skipif(shutil.which("bash") is None or shutil.which("git") is None,
                                reason="needs bash and git")


def run(args, tmp: Path, **kw):
    env = {**os.environ, "HOME": str(tmp / "home"), "PATH": f"{tmp / 'bin'}:{os.environ['PATH']}"}
    env.pop("GREG_FOUNDER_PASSPHRASE", None)
    (tmp / "home").mkdir(exist_ok=True)
    return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, env=env, timeout=300, **kw)


def dev_args(tmp: Path):
    return ["--allow-other-linux", "--no-service", "--skip-deps", "--no-passphrase", "--python", sys.executable,
            "--home", str(tmp / "body"), "--key", str(tmp / "founder.pem"), "--bin-dir", str(tmp / "bin"),
            "--read-root", str(tmp / "src"), "--deliver-root", str(tmp / "GREG")]


def greg(tmp: Path, *args):
    out = subprocess.run([str(tmp / "bin/greg"), *args], capture_output=True, text=True, timeout=120,
                         env={**os.environ, "HOME": str(tmp / "home")})
    assert out.returncode == 0, out.stderr[-2000:]
    return out.stdout


def test_one_command_reaches_a_designated_body_and_a_rerun_changes_nothing(tmp_path):
    first = run(dev_args(tmp_path), tmp_path)
    assert first.returncode == 0, first.stdout[-3000:] + first.stderr[-3000:]
    assert "WARNING: not ChromeOS Linux" in first.stdout and "unprotected" in first.stdout
    assert (tmp_path / "founder.pem").exists() and len((tmp_path / "founder.pem.pub").read_text().strip()) == 64
    assert list((tmp_path / "body/inbox").glob("*body_designate*.json"))          # queued, not self-accepted

    greg(tmp_path, "run", "--tick-seconds", "0.05", "--max-ticks", "2")          # the body accepts it
    status = json.loads(greg(tmp_path, "status"))
    assert len(status["security"]["founder_keys_enrolled"]) == 1
    assert [d["purpose"] for d in status["designation"]] == ["first_founder_body"]
    assert status["developmental_position"]["active"] == "N1"

    key_before = (tmp_path / "founder.pem").read_bytes()
    second = run(dev_args(tmp_path), tmp_path)
    assert second.returncode == 0, second.stdout[-3000:] + second.stderr[-3000:]
    assert "already designated" in second.stdout and "already enrolled" in second.stdout
    assert (tmp_path / "founder.pem").read_bytes() == key_before                  # never regenerates a key
    assert not list((tmp_path / "body/inbox").glob("*body_designate*.json"))      # no second designation
    path = json.loads(greg(tmp_path, "path"))
    assert path["active"]["id"] == "N1" and path["active"]["measurement"]["met"] is False


def test_it_refuses_to_pretend_another_linux_is_the_chromebook(tmp_path):
    args = [a for a in dev_args(tmp_path) if a != "--allow-other-linux"]
    if Path("/dev/.cros_milestone").exists() or Path("/opt/google/cros-containers").exists():
        pytest.skip("running inside ChromeOS Linux")
    out = run(args, tmp_path)
    assert out.returncode == 10 and "Settings > About ChromeOS > Developers" in out.stderr
    assert not (tmp_path / "body").exists() and not (tmp_path / "founder.pem").exists()


def test_it_stops_with_the_fix_when_no_python_311_exists(tmp_path):
    fake_bin = tmp_path / "fakebin"
    fake_bin.mkdir()
    old = fake_bin / "python3"
    old.write_text("#!/bin/sh\nexit 1\n")                                         # every version check fails
    old.chmod(0o755)
    for name in ("bash", "git", "uname", "dirname", "cat", "mkdir", "chmod"):
        found = shutil.which(name)
        if found:
            (fake_bin / name).symlink_to(found)
    env = {"HOME": str(tmp_path), "PATH": str(fake_bin)}
    out = subprocess.run([str(fake_bin / "bash"), str(SCRIPT), "--allow-other-linux", "--no-service"],
                         capture_output=True, text=True, env=env, timeout=60)
    assert out.returncode == 11 and "sudo apt install -y python3 python3-venv git" in out.stderr


def test_engines_are_best_effort_and_can_be_skipped(tmp_path):
    usage = run(["--help"], tmp_path)
    assert "--no-engines" in usage.stdout
    text = SCRIPT.read_text()
    assert "--only-binary=:all:" in text and "Body 1 continues" in text     # never compiles; never blocks Body 1
    done = run(dev_args(tmp_path) + ["--no-engines"], tmp_path)
    assert done.returncode == 0, done.stdout[-3000:] + done.stderr[-3000:]
    assert "Reasoning engines present:" in done.stdout
