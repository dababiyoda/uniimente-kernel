"""Run records must bind to the commit they measured — or say MIRROR_UNKNOWN.

Lock for the Finding-3 repair proposed in
docs/audit/INDEPENDENT_VERIFICATION_8cb3074a.md: verifier run records used to
float free of the tree they measured, so a record written against a partial
mirror could sit atop the canonical-v1 merge and read as if it described it.
These tests pin the fail-closed contract of verifier/run_binding.py.
"""
import os
import subprocess

from verifier.run_binding import MIRROR_UNKNOWN, head_commit


def test_no_git_store_yields_mirror_unknown(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert head_commit() == MIRROR_UNKNOWN


def test_git_checkout_yields_head_sha(tmp_path, monkeypatch):
    env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", HOME=str(tmp_path))
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True, env=env)
    subprocess.run(
        ["git", "-c", "user.email=test@test", "-c", "user.name=test",
         "commit", "-q", "--allow-empty", "-m", "x"],
        cwd=tmp_path, check=True, env=env)
    expected = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, check=True,
        capture_output=True, text=True, env=env).stdout.strip()
    monkeypatch.chdir(tmp_path)
    got = head_commit()
    assert got == expected
    assert len(got) == 40


def test_malformed_git_output_yields_mirror_unknown(monkeypatch):
    class FakeProc:
        returncode = 0
        stdout = "definitely-not-a-sha\n"
    monkeypatch.setattr("verifier.run_binding.subprocess.run",
                        lambda *a, **k: FakeProc())
    assert head_commit() == MIRROR_UNKNOWN


def test_git_absent_or_error_yields_mirror_unknown(monkeypatch):
    def boom(*a, **k):
        raise FileNotFoundError("git not on PATH")
    monkeypatch.setattr("verifier.run_binding.subprocess.run", boom)
    assert head_commit() == MIRROR_UNKNOWN


def test_nonzero_exit_yields_mirror_unknown(monkeypatch):
    class FakeProc:
        returncode = 128
        stdout = ""
    monkeypatch.setattr("verifier.run_binding.subprocess.run",
                        lambda *a, **k: FakeProc())
    assert head_commit() == MIRROR_UNKNOWN
