"""A founder key that does not open is one plain line and exit 2, whatever the cryptography library's wording.

Defect (#299 job 9, 2026-11-12): `greg body designate` with a wrong passphrase exited 1 with a traceback once in CI and
passed on the re-run. `_load_key` decided "wrong passphrase" by looking for "password" or "decrypt" in the library's
message. A wrong passphrase on an AES-CBC-encrypted key fails the padding check almost always ("Incorrect password,
could not decrypt key"), but about one wrong passphrase in 290 leaves valid padding over garbage, and the library then
says "Could not deserialize key data ..." with neither word: 344 of 100,000 wrong passphrases on one key, with
cryptography 50.0.2. The founder saw a traceback, and the installer's self-test said "see the line above" over one.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest

from greg.cli import BodyError, _load_key
from greg.founder import generate_founder_key, load_founder_key

ROOT = Path(__file__).resolve().parents[2]
RIGHT = b"correct horse"


def _rare_wrong_passphrase(key: Path) -> bytes:
    """A wrong passphrase whose failure the library words without 'password' or 'decrypt' (about 1 in 290)."""
    for i in range(50_000):                       # (1 - 1/290) ** 50_000 < 1e-70: the search cannot miss by chance
        wrong = f"wrong {i}".encode()
        try:
            load_founder_key(key, wrong)
        except ValueError as exc:
            text = str(exc).lower()
            if "password" not in text and "decrypt" not in text:
                return wrong
        else:
            raise AssertionError(f"{wrong!r} opened a key made with another passphrase")
    raise AssertionError("no wrong passphrase reached the library's other wording; re-measure the defect")


def _greg(args: list, passphrase: str | None) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    env.pop("GREG_FOUNDER_PASSPHRASE", None)
    if passphrase is not None:
        env["GREG_FOUNDER_PASSPHRASE"] = passphrase
    return subprocess.run([sys.executable, "-B", "-m", "greg", *args], cwd=ROOT, env=env, capture_output=True,
                          text=True, timeout=60)


@pytest.fixture
def key(tmp_path) -> Path:
    path = tmp_path / "founder.pem"
    generate_founder_key(path, RIGHT)
    return path


def test_the_rare_wording_of_a_wrong_passphrase_is_the_same_plain_refusal(key):
    wrong = _rare_wrong_passphrase(key)
    with pytest.raises(BodyError, match="incorrect passphrase for the founder key"):
        _load_key(key, wrong)
    with pytest.raises(BodyError, match="incorrect passphrase for the founder key"):
        _load_key(key, b"an ordinary wrong passphrase")      # the common wording: unchanged
    assert _load_key(key, RIGHT) is not None


def test_the_cli_refuses_the_rare_wrong_passphrase_in_one_line_with_exit_2(key):
    """What the installer's self-test runs (`greg founder public`): one line on stderr, exit 2, no traceback."""
    wrong = _rare_wrong_passphrase(key).decode()
    done = _greg(["founder", "public", "--key", str(key)], wrong)
    assert done.returncode == 2, done.stderr[-2000:]
    assert "incorrect passphrase" in done.stderr and "Traceback" not in done.stderr + done.stdout
    assert done.stdout == ""                                     # no public key printed for a key that did not open
    right = _greg(["founder", "public", "--key", str(key)], RIGHT.decode())
    assert right.returncode == 0 and len(right.stdout.strip()) == 64


def test_a_damaged_key_file_is_one_line_with_or_without_a_passphrase(tmp_path):
    damaged = tmp_path / "damaged.pem"
    damaged.write_text("-----BEGIN PRIVATE KEY-----\nAAAAnotakey\n-----END PRIVATE KEY-----\n")
    damaged.chmod(0o600)
    for args, passphrase, words in ((["--no-passphrase"], None, "could not be read as a PEM private key"),
                                    ([], "anything", "incorrect passphrase")):
        done = _greg(["founder", "public", "--key", str(damaged), *args], passphrase)
        assert done.returncode == 2 and words in done.stderr, done.stderr[-2000:]
        assert "Traceback" not in done.stderr + done.stdout
