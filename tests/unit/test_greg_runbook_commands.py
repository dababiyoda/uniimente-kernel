"""The runbook's signed commands work as written on the body install.sh creates.

Found rehearsing CHROMEBOOK_FIRST_MISSION.md on the installed body: the N3 and N6 commands omit
--key, and the CLI then asked for a passphrase and died with a TypeError; the N4 and N7 commands
named ~/greg-founder.pem while install.sh writes ~/.greg-founder.pem. Every signed step after N2
failed as written. Now every signed runbook step names --key with the installer's path, a missing or
unnamed key is one plain line before any passphrase prompt (the candidate's rule, kept over #168's default).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from greg import cli
from tests.greg_fixtures import make_body

ROOT = Path(__file__).resolve().parents[2]
RUNBOOK = ROOT / "greg" / "CHROMEBOOK_FIRST_MISSION.md"


def installer_key() -> str:
    [path] = re.findall(r'^KEY="\$HOME/([^"]+)"', (ROOT / "greg/chromebook/install.sh").read_text(), re.M)
    return "~/" + path


def greg_cli(user_home, body_home, *args):
    return subprocess.run([sys.executable, "-m", "greg", "--home", str(body_home), *args], text=True, input="",
                          capture_output=True, cwd=ROOT, timeout=60,
                          env={**os.environ, "PYTHONPATH": str(ROOT), "HOME": str(user_home)})


def test_every_key_path_in_the_runbook_is_the_one_install_sh_writes():
    expected = installer_key()
    assert cli.DEFAULT_FOUNDER_KEY == expected
    named = re.findall(r"--key\s+([^\s`]+)", RUNBOOK.read_text())
    assert named and set(named) == {expected}, sorted(set(named))


def test_a_signed_command_names_its_key_and_a_missing_key_is_one_line(tmp_path):
    """Joined with the candidate (founder decision recorded on the merge): a signing command signs only with the key
    file it names. #168 (1dfef4e1) signed with ~/.greg-founder.pem when --key was absent; the candidate refuses in
    one line naming that path, and the runbook names --key on every signed step (the test above), so the runbook
    still works as written. Both lineages' fixes hold: no traceback, nothing signed or dropped without a usable key."""
    body_home, *_ = make_body(tmp_path)
    user = tmp_path / "user"
    user.mkdir()
    draft = tmp_path / "data" / "draft.md"
    draft.write_text("a short draft\n")
    args = ("mission", "new", "word-limit", "--file", str(draft), "--max-words", "50", "--no-passphrase")

    unnamed = greg_cli(user, body_home, *args)
    assert unnamed.returncode == 2 and "Traceback" not in unnamed.stderr
    assert unnamed.stderr.strip().count("\n") == 0 and "add --key ~/.greg-founder.pem" in unnamed.stderr
    named = (*args, "--key", "~/.greg-founder.pem")
    missing = greg_cli(user, body_home, *named)
    assert missing.returncode == 2 and "Traceback" not in missing.stderr
    assert missing.stderr.strip() == ("greg: no founder key file at ~/.greg-founder.pem; "
                                      "the installer creates ~/.greg-founder.pem")
    assert not list((body_home / "inbox").glob("*.json"))                   # nothing signed, nothing dropped

    shutil.copy(tmp_path / "founder.pem", user / ".greg-founder.pem")
    os.chmod(user / ".greg-founder.pem", 0o600)
    still_unnamed = greg_cli(user, body_home, *args)                       # the key exists; it is still not named
    assert still_unnamed.returncode == 2 and not list((body_home / "inbox").glob("*.json"))
    signed = greg_cli(user, body_home, *named)                             # the runbook's form: --key named
    assert signed.returncode == 0, signed.stderr
    [dropped] = list((body_home / "inbox").glob("*.json"))
    assert json.loads(dropped.read_text())["kind"] == "MISSION"
