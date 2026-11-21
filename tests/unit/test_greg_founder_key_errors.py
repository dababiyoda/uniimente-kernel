"""A founder key that does not open is one plain line and exit 2, whatever the cryptography library's wording.

Defect (#299 job 9, 2026-11-12): `greg body designate` with a wrong passphrase exited 1 with a traceback once in CI and
passed on the re-run. `_load_key` decided "wrong passphrase" by looking for "password" or "decrypt" in the library's
message. A wrong passphrase on an AES-CBC-encrypted key fails the padding check almost always ("Incorrect password,
could not decrypt key"), but about one wrong passphrase in 250 leaves valid padding over garbage, and the library then
says "Could not deserialize key data ..." with neither word: 4,288 of 1,080,000 wrong passphrases over 9 keys, with
cryptography 50.0.2 (an independent review's measurement; the first probe, on one key, gave 344 of 100,000). The founder
saw a traceback, and the installer's self-test said "see the line above" over one. A file that is not an encrypted key
is never called a wrong passphrase, so the founder is not sent to the steps that move a good key aside.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
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
    # The defect needs the library's other wording; a release without it cannot show it here. The logic is still
    # tested without the library by test_the_refusal_follows_the_file_not_the_wording.
    pytest.skip("this cryptography release no longer words any wrong passphrase without 'password' or 'decrypt'")


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


def test_a_file_that_is_not_an_encrypted_key_is_never_called_a_wrong_passphrase(tmp_path):
    """Review of 8626d692: with the right passphrase, a damaged plain key, a public-key companion, an empty file and
    binary data were all called "incorrect passphrase", which points to the steps that move a good key aside."""
    files = {"damaged.pem": "-----BEGIN PRIVATE KEY-----\nAAAAnotakey\n-----END PRIVATE KEY-----\n",
             "companion.pub": "ab" * 32 + "\n", "empty.pem": "", "binary.der": "\x00\x01garbage"}
    for name, text in files.items():
        path = tmp_path / name
        path.write_text(text)
        path.chmod(0o600)
        for args, passphrase in ((["--no-passphrase"], None), ([], "correct horse")):
            done = _greg(["founder", "public", "--key", str(path), *args], passphrase)
            assert done.returncode == 2, (name, done.stderr[-2000:])
            assert "could not be read as a PEM private key" in done.stderr, (name, done.stderr[-2000:])
            assert "incorrect passphrase" not in done.stderr and "Traceback" not in done.stderr + done.stdout


def test_a_damaged_encrypted_key_is_the_passphrase_line_naming_damage(key):
    text = key.read_text().splitlines()
    key.write_text("\n".join(text[:2] + text[-1:]) + "\n")           # header, one body line, footer
    done = _greg(["founder", "public", "--key", str(key)], RIGHT.decode())
    assert done.returncode == 2 and "incorrect passphrase" in done.stderr and "damaged" in done.stderr, done.stderr
    assert "Traceback" not in done.stderr + done.stdout


def test_a_missing_key_file_or_a_directory_is_one_line(tmp_path):
    for path in (tmp_path / "missing.pem", tmp_path):
        done = _greg(["founder", "public", "--key", str(path)], RIGHT.decode())
        assert done.returncode == 2 and "cannot be read" in done.stderr, done.stderr[-2000:]
        assert "Traceback" not in done.stderr + done.stdout


def test_the_refusal_follows_the_file_not_the_wording(key, tmp_path, monkeypatch):
    """Without the library: whatever a ValueError says, an encrypted key with a passphrase is the passphrase line and
    anything else is the unreadable-file line."""
    import greg.cli as cli
    plain = tmp_path / "plain.pem"
    plain.write_text("-----BEGIN PRIVATE KEY-----\nAAAA\n-----END PRIVATE KEY-----\n")
    for wording in ("Could not deserialize key data.", "Incorrect password, could not decrypt key", "anything"):
        def fail(path, passphrase, wording=wording):
            raise ValueError(wording)
        monkeypatch.setattr(cli, "load_founder_key", fail)
        with pytest.raises(BodyError, match="incorrect passphrase"):
            _load_key(key, b"a wrong one")
        with pytest.raises(BodyError, match="could not be read as a PEM private key"):
            _load_key(plain, b"a wrong one")
        with pytest.raises(BodyError, match="could not be read as a PEM private key"):
            _load_key(key, None)


@pytest.mark.skipif(shutil.which("openssl") is None, reason="needs the openssl command to write the key")
def test_a_key_in_a_form_this_library_cannot_read_is_not_a_wrong_passphrase(tmp_path):
    """Review of 8626d692: a key encrypted with a cipher cryptography does not read, opened with its right passphrase."""
    plain, odd = tmp_path / "plain.pem", tmp_path / "odd.pem"
    subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", str(plain)], check=True, capture_output=True)
    made = subprocess.run(["openssl", "pkcs8", "-topk8", "-in", str(plain), "-out", str(odd), "-v2", "aria-256-cbc",
                           "-passout", "pass:correct horse"], capture_output=True)
    if made.returncode != 0:
        pytest.skip("this openssl cannot write the cipher: " + made.stderr.decode()[-200:])
    odd.chmod(0o600)
    with pytest.raises(BodyError) as refused:
        _load_key(odd, RIGHT)
    assert "Traceback" not in str(refused.value)
    assert str(refused.value).startswith(("incorrect passphrase", "the founder key"))
