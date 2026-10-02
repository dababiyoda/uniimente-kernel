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


def fixture_python(tmp: Path, *, fail_engines=False):
    """Record package command construction; pip/venv operations are fixtures.

    Other commands use the actual test interpreter and canonical CLI. No package
    downloads, native builds, services or models are launched by these tests.
    """
    wrapper = tmp / "fixture-python"
    calls = tmp / "pip-commands.jsonl"
    wrapper.write_text(f'''#!{sys.executable}
import json,os,pathlib,shutil,sys
args=sys.argv[1:]
if args[:2]==['-m','venv']:
    target=pathlib.Path(args[2])/'bin'/'python'
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(__file__,target);target.chmod(0o755)
    raise SystemExit(0)
if args[:2]==['-m','pip']:
    with open({str(calls)!r},'a') as stream:stream.write(json.dumps(args)+'\\n')
    failed={fail_engines!r} and any('requirements-cognition' in item for item in args)
    raise SystemExit(1 if failed else 0)
os.execv({sys.executable!r},[{sys.executable!r},*args])
''')
    wrapper.chmod(0o755)
    return wrapper, calls


def install_args(tmp: Path, python: Path):
    return ["--allow-other-linux", "--no-service", "--no-passphrase", "--python", str(python),
            "--venv", str(tmp / "venv"), "--home", str(tmp / "body"), "--key", str(tmp / "founder.pem"),
            "--bin-dir", str(tmp / "bin"), "--read-root", str(tmp / "src"), "--deliver-root", str(tmp / "GREG")]


@pytest.mark.parametrize("mode,recipe", [(None, None), ("--no-engines", None),
                                        ("--with-engines", "requirements-cognition.txt"),
                                        ("--with-expanded-engines", "requirements-cognition-expanded.txt")])
def test_installer_builds_explicit_engine_commands_only_and_never_attaches(mode, recipe, tmp_path):
    if recipe and not (ROOT / recipe).is_file():
        pytest.skip("reviewed expanded recipe not yet present")
    python, calls = fixture_python(tmp_path)
    args = install_args(tmp_path, python) + ([mode] if mode else [])
    result = run(args, tmp_path)
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-2000:]
    commands = [json.loads(line) for line in calls.read_text().splitlines()]
    engine_calls = [args for args in commands if any("requirements-cognition" in value for value in args)]
    if recipe:
        assert engine_calls == [["-m", "pip", "install", "--quiet", "--only-binary=:all:", "-r", str(ROOT / recipe)]]
        assert "Requested reasoning-package recipe installed" in result.stdout
    else:
        assert engine_calls == [] and "were not requested" in result.stdout
    # A designation is queued by the human-invoked script, not self-accepted;
    # installing packages creates no attachment/activation command.
    inbox = list((tmp_path / "body/inbox").glob("*.json"))
    assert inbox and all("capability_attach" not in path.name for path in inbox)
    assert not list((tmp_path / "home").rglob("greg-body.service"))


def test_requested_engine_install_failure_is_truthful_and_keeps_basic_body(tmp_path):
    python, calls = fixture_python(tmp_path, fail_engines=True)
    result = run(install_args(tmp_path, python) + ["--with-engines"], tmp_path)
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-2000:]
    assert "did not fully install" in result.stdout and "Requested reasoning-package recipe installed" not in result.stdout
    assert (tmp_path / "body/body.json").exists()
    commands = [json.loads(line) for line in calls.read_text().splitlines()]
    assert len([args for args in commands if any("requirements-cognition" in value for value in args)]) == 1


def test_skip_deps_cannot_silently_override_explicit_engine_install(tmp_path):
    result = run(dev_args(tmp_path) + ["--with-engines"], tmp_path)
    assert result.returncode == 64 and "--skip-deps cannot install engines" in result.stderr
    assert not (tmp_path / "body").exists() and not (tmp_path / "founder.pem").exists()
