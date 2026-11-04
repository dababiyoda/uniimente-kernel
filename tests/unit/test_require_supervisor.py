"""GREG_REQUIRE_SUPERVISOR=1: a supervised rehearsal that cannot find supervisord fails; it never reads as skipped.

Without the variable the rehearsals skip as before where supervisord is not on PATH, which is how "2 skipped" passed
for a run of the Chromebook rehearsal on a machine whose supervisord sits in a virtualenv. The wiring is checked by
running the two rehearsal modules in a child pytest with supervisord hidden from PATH; the helper itself directly.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ElementTree

import pytest

from tests.supervisor_requirement import MISSING, REQUIRE, require_supervisord

ROOT = Path(__file__).resolve().parents[2]
REHEARSALS = ("tests/integration/test_greg_chromebook_rehearsal.py", "tests/integration/test_greg_vepmc_path.py")


def path_without_supervisord() -> str:
    """This process's PATH without any directory that holds a supervisord."""
    kept = [d for d in os.environ.get("PATH", "").split(os.pathsep)
            if d and not os.access(os.path.join(d, "supervisord"), os.X_OK)]
    return os.pathsep.join(kept)


def rehearse(tmp_path: Path, required: bool) -> tuple[subprocess.CompletedProcess, list]:
    """Run the two rehearsal modules with supervisord hidden; (the run, [(test name, outcome, message)])."""
    report = tmp_path / ("required.xml" if required else "unset.xml")
    env = {k: v for k, v in os.environ.items() if k != REQUIRE}
    env.update(PATH=path_without_supervisord(), PYTHONDONTWRITEBYTECODE="1")
    if required:
        env[REQUIRE] = "1"
    run = subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={report}",
                          *REHEARSALS], cwd=ROOT, env=env, capture_output=True, text=True, timeout=300)
    cases = []
    for case in ElementTree.parse(report).getroot().iter("testcase"):
        outcomes = [child for child in case if child.tag in ("error", "failure", "skipped")]
        outcome = outcomes[0] if outcomes else None
        cases.append((case.get("name"), "passed" if outcome is None else outcome.tag,
                      "" if outcome is None else f"{outcome.get('message', '')} {outcome.text or ''}"))
    return run, cases


def test_required_and_missing_every_supervised_rehearsal_fails_with_the_message(tmp_path):
    run, cases = rehearse(tmp_path, required=True)
    assert run.returncode == 1, run.stdout[-3000:]
    assert len(cases) >= 4, cases                          # two in each module today
    for name, outcome, message in cases:
        assert outcome in ("error", "failure") and MISSING in message, (name, outcome, message)
    assert "skipped" not in run.stdout.splitlines()[-1] and "passed" not in run.stdout.splitlines()[-1]


def test_unset_a_missing_supervisord_still_skips(tmp_path):
    run, cases = rehearse(tmp_path, required=False)
    assert run.returncode == 0, run.stdout[-3000:]
    assert len(cases) >= 4 and {outcome for _, outcome, _ in cases} == {"skipped"}, cases
    assert not any(MISSING in message for _, _, message in cases)


def fake_supervisord(directory: Path) -> Path:
    directory.mkdir()
    exe = directory / "supervisord"
    exe.write_text("#!/bin/sh\nexit 0\n")
    exe.chmod(0o755)
    return exe


def test_the_helper_fails_only_when_required_and_returns_a_present_supervisord(tmp_path, monkeypatch):
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    monkeypatch.setenv(REQUIRE, "1")
    with pytest.raises(pytest.fail.Exception) as failed:
        require_supervisord("reason")
    assert str(failed.value) == MISSING
    for value in (None, "0", "yes"):                       # only "1" requires it, as GREG_REQUIRE_LANDLOCK
        if value is None:
            monkeypatch.delenv(REQUIRE)
        else:
            monkeypatch.setenv(REQUIRE, value)
        with pytest.raises(pytest.skip.Exception) as skipped:
            require_supervisord("reason")
        assert str(skipped.value) == "reason"
    exe = fake_supervisord(tmp_path / "bin")
    monkeypatch.setenv("PATH", str(exe.parent))
    for value in ("1", "0"):
        monkeypatch.setenv(REQUIRE, value)
        assert require_supervisord("reason") == str(exe)
