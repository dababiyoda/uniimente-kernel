"""GREG_REQUIRE_BROWSER=1: a browser test whose Playwright or Chromium is missing fails; it never reads as skipped.

Without the variable the browser tests skip as before. Canonical CI installed no browser, so every pull request
passed with them skipped. The wiring is checked by running browser test modules in a child pytest with Python
Playwright hidden; the helper itself directly.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ElementTree

import pytest

from tests.browser_requirement import MISSING, REQUIRE, chromium_path, no_browser, require_browser

ROOT = Path(__file__).resolve().parents[2]
# Modules whose only missing facility in the child run is Playwright (they need no bubblewrap or supervisord).
MODULES = ("tests/unit/test_greg_computer.py", "tests/integration/test_greg_mission_control_browser.py",
           "tests/integration/test_greg_phone_asks.py")


def without_playwright(tmp_path: Path, required: bool) -> tuple[subprocess.CompletedProcess, list]:
    """Run MODULES with ``import playwright`` failing; (the run, [(test name, outcome, message)])."""
    shadow = tmp_path / "shadow" / "playwright"
    shadow.mkdir(parents=True)
    (shadow / "__init__.py").write_text('raise ImportError("Python Playwright hidden by tests/unit/test_require_browser.py")\n')
    report = tmp_path / ("required.xml" if required else "unset.xml")
    env = {k: v for k, v in os.environ.items() if k != REQUIRE}
    env.update(PYTHONPATH=os.pathsep.join(filter(None, [str(shadow.parent), env.get("PYTHONPATH")])),
               PYTHONDONTWRITEBYTECODE="1")
    if required:
        env[REQUIRE] = "1"
    run = subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={report}",
                          *MODULES], cwd=ROOT, env=env, capture_output=True, text=True, timeout=300)
    cases = []
    for case in ElementTree.parse(report).getroot().iter("testcase"):
        outcomes = [child for child in case if child.tag in ("error", "failure", "skipped")]
        outcome = outcomes[0] if outcomes else None
        cases.append((case.get("name"), "passed" if outcome is None else outcome.tag,
                      "" if outcome is None else f"{outcome.get('message', '')} {outcome.text or ''}"))
    return run, cases


def test_required_and_missing_every_browser_test_fails_with_the_message(tmp_path):
    run, cases = without_playwright(tmp_path, required=True)
    assert run.returncode == 1, run.stdout[-3000:]
    assert len(cases) >= 12, cases                         # 8 + 3 + 1 today
    for name, outcome, message in cases:
        assert outcome in ("error", "failure") and MISSING in message, (name, outcome, message)
    assert "skipped" not in run.stdout.splitlines()[-1] and "passed" not in run.stdout.splitlines()[-1]


def test_unset_a_missing_playwright_still_skips(tmp_path):
    run, cases = without_playwright(tmp_path, required=False)
    assert run.returncode == 0, run.stdout[-3000:]
    assert len(cases) >= 12 and {outcome for _, outcome, _ in cases} == {"skipped"}, cases
    assert not any(MISSING in message for _, _, message in cases)


def test_the_helper_fails_only_when_required_and_names_what_is_missing(monkeypatch):
    monkeypatch.setenv(REQUIRE, "1")
    with pytest.raises(pytest.fail.Exception) as failed:
        no_browser("reason")
    assert str(failed.value) == f"{MISSING}: reason"
    for value in (None, "0", "yes"):                       # only "1" requires it, as GREG_REQUIRE_SUPERVISOR
        if value is None:
            monkeypatch.delenv(REQUIRE)
        else:
            monkeypatch.setenv(REQUIRE, value)
        with pytest.raises(pytest.skip.Exception) as skipped:
            no_browser("reason")
        assert str(skipped.value) == "reason"
    with pytest.raises(pytest.skip.Exception, match="could not import Python Playwright"):
        require_browser(None, "/a/chromium", "what")
    with pytest.raises(pytest.skip.Exception, match="no Chromium binary"):
        require_browser(object(), None, "what")
    assert require_browser(object(), "/a/chromium", "what") is None


def test_greg_chromium_names_the_browser_when_it_is_an_executable_file(tmp_path, monkeypatch):
    exe = tmp_path / "chromium"
    exe.write_text("#!/bin/sh\nexit 0\n")
    exe.chmod(0o755)
    monkeypatch.setenv("GREG_CHROMIUM", str(exe))
    assert chromium_path() == str(exe)
    monkeypatch.setenv("GREG_CHROMIUM", str(tmp_path))      # a directory is not a browser
    assert chromium_path() != str(tmp_path)
