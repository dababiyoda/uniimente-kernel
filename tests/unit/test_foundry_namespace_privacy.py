"""The door namespace hides the founder's home and the body's home from every program it runs.

Every confined program (the browser, the model SDK child, the Claude Code CLI, DALEOBANKS, the venture organs) runs in
``relay_door.namespace_argv``. It used to mount the whole filesystem read-only, so any of them could read the founder's
signing key (``~/.greg-founder.pem`` by default) and the body's secrets, keys and ledger (``~/.uniimente/greg``).
Now the user's home and every registered body home are hidden behind empty private mounts; only what a program needs
(its interpreter, GREG's code, the paths its caller names) is shown again, read-only unless the caller says otherwise.

The tests do not mask /tmp (``tmp_roots=()``), so the only thing that can hide the planted files is the new rule.
"""
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from foundry.systems import relay_door
from foundry.systems.relay_door import namespace_argv


def _netns():
    bwrap = shutil.which("bwrap")
    if not bwrap or not sys.platform.startswith("linux"):
        return None
    probe = subprocess.run([bwrap, "--unshare-user", "--unshare-net", "--ro-bind", "/", "/", "--", "/usr/bin/true"],
                           capture_output=True, timeout=10)
    return bwrap if probe.returncode == 0 else None


pytestmark = pytest.mark.skipif(_netns() is None, reason="bubblewrap namespaces unavailable on this host")


@pytest.fixture
def founder(tmp_path, monkeypatch):
    """A founder's home with the signing key in its default place, and a body home outside it."""
    home = tmp_path / "home"
    (home / ".ssh").mkdir(parents=True)
    key = home / ".greg-founder.pem"
    key.write_text("FOUNDER-PRIVATE-KEY-FIXTURE\n")
    key.chmod(0o600)
    (home / ".ssh" / "id_ed25519").write_text("SSH-KEY-FIXTURE\n")
    body = tmp_path / "srv" / "greg-body"
    body.mkdir(parents=True)
    (body / "secrets.json").write_text('{"anthropic": "sk-ant-FIXTURE"}')
    (body / "ledger.jsonl").write_text('{"seq": 0}\n')
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(relay_door, "_PRIVATE_ROOTS", set())
    relay_door.hide_from_namespaces(body)
    return {"home": home, "key": key, "body": body}


def _run(argv, *command):
    return subprocess.run(argv + list(command), capture_output=True, text=True, timeout=30)


def test_a_confined_program_cannot_read_the_founder_key_or_the_body_home(founder):
    argv = namespace_argv(chdir="/", tmp_roots=())
    for secret in (founder["key"], founder["home"] / ".ssh" / "id_ed25519", founder["body"] / "secrets.json",
                   founder["body"] / "ledger.jsonl"):
        out = _run(argv, "/bin/cat", str(secret))
        assert out.returncode != 0 and "FIXTURE" not in out.stdout and "seq" not in out.stdout, (secret, out.stdout)
    listing = _run(argv, "/bin/ls", "-A", str(founder["home"]), str(founder["body"]))
    assert listing.returncode == 0                                       # the directories exist, empty
    assert not any(name in listing.stdout for name in (".greg-founder.pem", ".ssh", "secrets.json", "ledger.jsonl"))


def test_nothing_a_confined_program_writes_reaches_the_body_home(founder):
    argv = namespace_argv(chdir="/", tmp_roots=())
    _run(argv, "/bin/sh", "-c", f"echo forged >> {founder['body']}/ledger.jsonl; echo x > {founder['body']}/planted")
    assert (founder["body"] / "ledger.jsonl").read_text() == '{"seq": 0}\n'
    assert not (founder["body"] / "planted").exists()


def test_a_path_the_caller_names_is_shown_again_and_nothing_beside_it(founder):
    work = founder["body"] / "work-orders" / "w1"
    work.mkdir(parents=True)
    source = founder["home"] / "projects" / "notes.md"
    source.parent.mkdir()
    source.write_text("founder notes\n")
    argv = namespace_argv(writable=[work], readonly=[source], chdir=str(work), tmp_roots=())
    assert _run(argv, "/bin/cat", str(source)).stdout == "founder notes\n"
    assert _run(argv, "/bin/sh", "-c", "echo out > result.txt").returncode == 0
    assert (work / "result.txt").read_text() == "out\n"
    assert _run(argv, "/bin/cat", str(founder["key"])).returncode != 0
    assert _run(argv, "/bin/cat", str(founder["body"] / "secrets.json")).returncode != 0
    assert _run(argv, "/bin/sh", "-c", f"echo x >> {source}").returncode != 0      # read-only stays read-only


def test_binding_a_directory_that_contains_a_hidden_root_does_not_reveal_it(founder, tmp_path):
    # A caller that names a broad directory (here the parent of the body home) still never sees the body home.
    work = founder["body"] / "work-orders" / "w2"
    work.mkdir(parents=True)
    argv = namespace_argv(writable=[work], readonly=[tmp_path], chdir=str(work), tmp_roots=())
    assert _run(argv, "/bin/cat", str(founder["body"] / "secrets.json")).returncode != 0
    assert _run(argv, "/bin/cat", str(founder["key"])).returncode != 0
    assert _run(argv, "/bin/sh", "-c", "echo out > kept.txt").returncode == 0          # the named work dir survives
    assert (work / "kept.txt").read_text() == "out\n"


@pytest.mark.parametrize("layout", ["repository", "virtualenv"])
def test_greg_python_still_runs_inside_when_its_runtime_lives_under_the_hidden_home(founder, monkeypatch, layout):
    # The founder's Chromebook layout: the repository and the virtualenv live under $HOME, which is now hidden.
    home = relay_door.ROOT.parent if layout == "repository" else Path(sys.prefix).parent
    monkeypatch.setenv("HOME", str(home))
    argv = namespace_argv(chdir=str(relay_door.ROOT), tmp_roots=())
    assert ["--tmpfs", str(home.resolve())] in [argv[i:i + 2] for i in range(len(argv) - 1)], argv
    out = _run(argv, sys.executable, "-c", "import json, ssl, foundry.systems.relay_door as d; print('ok', d.__name__)")
    assert out.returncode == 0 and out.stdout.split() == ["ok", "foundry.systems.relay_door"], out.stderr[-400:]


def test_a_symlink_in_a_shown_path_does_not_lead_into_the_hidden_home(founder, tmp_path):
    shown = tmp_path / "shown"
    shown.mkdir()
    (shown / "key.pem").symlink_to(founder["key"])
    argv = namespace_argv(readonly=[shown], chdir="/", tmp_roots=())
    out = _run(argv, "/bin/cat", str(shown / "key.pem"))
    assert out.returncode != 0 and "FIXTURE" not in out.stdout


def test_the_body_process_is_invisible_from_inside(founder):
    import os
    argv = namespace_argv(chdir="/", tmp_roots=())
    out = _run(argv, "/bin/sh", "-c", f"cat /proc/{os.getpid()}/environ; ls /proc/{os.getpid()}/fd")
    assert out.returncode != 0 and out.stdout == ""


def test_greg_code_is_shown_but_its_git_config_is_not(founder, monkeypatch, tmp_path):
    # GitHub Actions' checkout keeps the job's token in .git/config; a founder's clone may hold one in a remote URL.
    repo = tmp_path / "home" / "greg"
    (repo / ".git").mkdir(parents=True)
    (repo / ".git" / "config").write_text('[http]\n\textraheader = AUTHORIZATION: basic TOKEN-FIXTURE\n')
    (repo / "greg").mkdir()
    (repo / "greg" / "__init__.py").write_text("CODE = 1\n")
    monkeypatch.setattr(relay_door, "ROOT", repo)
    argv = namespace_argv(chdir="/", tmp_roots=())
    assert _run(argv, "/bin/cat", str(repo / "greg" / "__init__.py")).stdout == "CODE = 1\n"
    out = _run(argv, "/bin/cat", str(repo / ".git" / "config"))
    assert out.returncode != 0 and "TOKEN-FIXTURE" not in out.stdout


def test_a_system_directory_is_never_hidden(monkeypatch, tmp_path):
    monkeypatch.setattr(relay_door, "_PRIVATE_ROOTS", set())
    for unsafe in ("/", "/usr", "/etc", "/usr/lib"):
        monkeypatch.setenv("HOME", unsafe)
        argv = namespace_argv(chdir="/", tmp_roots=())
        assert ["--tmpfs", unsafe] not in [argv[i:i + 2] for i in range(len(argv) - 1)], unsafe
        assert _run(argv, "/bin/true").returncode == 0
