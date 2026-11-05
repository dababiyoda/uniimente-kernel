"""The founder key passphrase as Alfonso types it: at a real terminal (a pty), never GREG_FOUNDER_PASSPHRASE.

Defects reproduced on #196 d35d92a5 (C1, C2): pressing Enter at the passphrase prompt wrote an UNENCRYPTED founder key
that install.sh enrolled without a word, so N1 could never reach the founder tier; keygen asked once, so a typo became
an enrolled key that refused every signature with a ValueError traceback, and a rerun with a missing --key wrote a new
key file before refusing. Here: an empty answer and a mismatched confirmation are refused, a good passphrase gives an
encrypted key that queues the founder-tier attestation, a wrong passphrase is one plain line with exit 2, and
install.sh proves the key opens before it enrols it.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import pty
import select
import shutil
import subprocess
import sys

import pytest

from greg.body import Body
from tests.unit.test_greg_chromebook_install import SCRIPT, dev_args, run

ROOT = Path(__file__).resolve().parents[2]
PROMPTS = (b"founder key passphrase: ", b"founder key passphrase, again: ")
pytestmark = pytest.mark.skipif(shutil.which("bash") is None or shutil.which("git") is None,
                                reason="needs bash and git")


def typed(argv, answers, *, env=None, timeout=240):
    """Run argv on a pty and type the next answer at each passphrase prompt. Returns (exit code, transcript, unused)."""
    answers = list(answers)
    env = {**(env or os.environ), "PYTHONPATH": str(ROOT)}
    env.pop("GREG_FOUNDER_PASSPHRASE", None)
    pid, fd = pty.fork()
    if pid == 0:                                                          # child: the founder's terminal session
        os.chdir(ROOT)
        os.execvpe(argv[0], argv, env)
    out, tail = b"", b""
    while True:
        ready, _, _ = select.select([fd], [], [], timeout)
        if not ready:
            os.kill(pid, 9)
            raise AssertionError("no output for %ss:\n%s" % (timeout, out.decode(errors="replace")[-3000:]))
        try:
            data = os.read(fd, 4096)
        except OSError:
            break
        if not data:
            break
        out, tail = out + data, tail + data
        if tail.endswith(PROMPTS):
            assert answers, "an unexpected passphrase prompt:\n" + out.decode(errors="replace")[-3000:]
            os.write(fd, answers.pop(0).encode() + b"\n")
            tail = b""
    _, status = os.waitpid(pid, 0)
    os.close(fd)
    return os.waitstatus_to_exitcode(status), out.decode(errors="replace"), answers


def greg_typed(home, args, answers):
    return typed([sys.executable, "-B", "-m", "greg", "--home", str(home), *args], answers)


def encrypted(key: Path) -> bool:
    return key.read_text().startswith("-----BEGIN ENCRYPTED PRIVATE KEY-----")


def test_an_empty_typed_passphrase_is_refused_and_writes_no_key(tmp_path):
    key = tmp_path / "founder.pem"
    code, out, _ = greg_typed(tmp_path / "body", ["founder", "keygen", "--key", str(key)], ["", "", ""])
    assert code == 2 and "an empty passphrase is refused" in out and "--no-passphrase" in out
    assert "Traceback" not in out and not key.exists()
    code, out, left = greg_typed(tmp_path / "body", ["founder", "keygen", "--key", str(key)], ["", "kept", "kept"])
    assert code == 0 and not left and encrypted(key)                    # one empty answer, then a real one


def test_a_mismatched_confirmation_is_refused_and_writes_no_key(tmp_path):
    key = tmp_path / "founder.pem"
    code, out, _ = greg_typed(tmp_path / "body", ["founder", "keygen", "--key", str(key)],
                              ["right", "rigth", "one", "two", "a", "b"])
    assert code == 2 and "the two passphrases differ" in out and "Traceback" not in out and not key.exists()


def test_a_good_typed_passphrase_reaches_founder_tier_and_a_wrong_one_is_one_line(tmp_path):
    home, key = tmp_path / "body", tmp_path / "founder.pem"
    code, out, _ = greg_typed(home, ["founder", "keygen", "--key", str(key)], ["correct horse", "correct horse"])
    assert code == 0 and encrypted(key)
    public = out.strip().splitlines()[-1]
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    for args in (["init", "--read-root", str(tmp_path)], ["founder", "enroll", "--pubkey", public]):
        assert subprocess.run([sys.executable, "-B", "-m", "greg", "--home", str(home), *args], cwd=ROOT, env=env,
                              capture_output=True, timeout=60).returncode == 0
    code, out, _ = greg_typed(home, ["body", "designate", "--key", str(key)], ["correct hrose"])
    assert code == 2 and "incorrect passphrase" in out and "Traceback" not in out
    assert not list((home / "inbox").glob("*.json"))                     # nothing was signed
    code, out, _ = greg_typed(home, ["body", "designate", "--key", str(key)], ["correct horse"])
    assert code == 0, out
    kinds = sorted(json.loads(p.read_text())["kind"] for p in (home / "inbox").glob("*.json"))
    assert kinds == ["BODY_DESIGNATE", "FOUNDER_TIER"]                  # the protected key claims the founder tier


def _install(tmp_path, answers, *, extra=()):
    args = [a for a in dev_args(tmp_path) if a != "--no-passphrase"] + list(extra)
    (tmp_path / "home").mkdir(exist_ok=True)
    env = {**os.environ, "HOME": str(tmp_path / "home"), "PATH": f"{tmp_path / 'bin'}:{os.environ['PATH']}"}
    return typed(["bash", str(SCRIPT), *args], answers, env=env, timeout=280)


def _enrolled(tmp_path):
    with Body(tmp_path / "body") as body:
        return body.enrolled_keys()


def test_install_never_enrols_a_key_its_passphrase_cannot_open(tmp_path):
    """C2(b): a typo at keygen used to be enrolled first and found only at designation (a traceback)."""
    key = tmp_path / "founder.pem"
    code, out, _ = _install(tmp_path, ["what I meant", "what I meant", "what I typed"])
    assert code == 16 and "did not open" in out and "Nothing was enrolled" in out and "Traceback" not in out
    assert encrypted(key) and not _enrolled(tmp_path) and not (tmp_path / "founder.pem.pub").exists()
    assert not list((tmp_path / "body/inbox").glob("*.json"))
    # The documented recovery: run the installer again and type the passphrase chosen. The kept key is enrolled.
    code, out, left = _install(tmp_path, ["what I meant", "what I meant"])
    assert code == 0 and not left, out[-3000:]
    assert len(_enrolled(tmp_path)) == 1 and "Enrolled your public key" in out
    kinds = sorted(json.loads(p.read_text())["kind"] for p in (tmp_path / "body/inbox").glob("*.json"))
    assert kinds == ["BODY_DESIGNATE", "FOUNDER_TIER"]


def test_install_refuses_an_unprotected_key_unless_no_passphrase_was_given(tmp_path):
    """C1: an empty typed passphrase is refused at keygen; an unprotected key from anywhere is never enrolled."""
    code, out, _ = _install(tmp_path, ["", "", ""])
    assert code == 16 and "an empty passphrase is refused" in out and not (tmp_path / "founder.pem").exists()
    assert not _enrolled(tmp_path)
    from greg.founder import generate_founder_key
    generate_founder_key(tmp_path / "founder.pem", None)                 # e.g. GREG_FOUNDER_PASSPHRASE="" at keygen
    code, out, _ = _install(tmp_path, [])
    assert code == 17 and "not protected by a passphrase" in out and not _enrolled(tmp_path)
    assert not list((tmp_path / "body/inbox").glob("*.json"))
    assert run(dev_args(tmp_path), tmp_path).returncode == 0              # --no-passphrase: the test body is allowed


def test_a_rerun_without_the_enrolled_key_file_refuses_before_writing_any_key(tmp_path):
    """C2(d): a rerun whose --key names no file wrote a fresh key, then stopped at the enrollment check."""
    assert run(dev_args(tmp_path), tmp_path).returncode == 0
    args = dev_args(tmp_path)
    args[args.index("--key") + 1] = str(tmp_path / "elsewhere.pem")
    result = run(args, tmp_path)
    assert result.returncode == 14 and "already has an enrolled founder key" in result.stderr
    assert not (tmp_path / "elsewhere.pem").exists() and not (tmp_path / "elsewhere.pem.pub").exists()


def test_the_recovery_every_refusal_names_is_in_the_runbook():
    runbook = (ROOT / "greg/CHROMEBOOK_FIRST_MISSION.md").read_text()
    section = runbook[runbook.index("### A key you cannot open"):runbook.index("## 2. Run and judge")]
    assert "never delete" in section and "no mission evidence" in section and "exit 16" in section
    assert "A key you cannot open" in (ROOT / "greg/cli.py").read_text()
    assert "A key you cannot open" in SCRIPT.read_text()
