"""Which Chromium ``browser.session`` launches (greg/computer.py ``chromium``). No browser is started here.

Before 2026-11-12 the session ignored GREG_CHROMIUM, which ``browser.render`` already honours as the founder's
choice, and matched only Playwright's old ``chrome-linux/chrome`` layout. Playwright now installs Chrome for Testing
as ``chrome-linux64/chrome``, so the installed build was passed over: here the session drove a system wrapper
instead, and on a body with only Playwright's build it reported "no Chromium installed on this body".
"""
from __future__ import annotations

import fnmatch
from pathlib import Path

import pytest

from greg import computer
from greg.capabilities import CapabilityError


def executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\nexit 0\n")
    path.chmod(0o755)
    return path


def only_these_builds(monkeypatch, builds: dict):
    """The /opt/pw-browsers builds ``chromium`` sees: {virtual path: real file}; the system paths answer no."""
    monkeypatch.setattr(computer.glob, "glob",
                        lambda pattern: [str(real) for virtual, real in builds.items() if fnmatch.fnmatch(virtual, pattern)])
    real_access = computer.os.access
    monkeypatch.setattr(computer.os, "access",
                        lambda path, mode: not str(path).startswith("/usr/bin/") and real_access(path, mode))


def test_the_founders_greg_chromium_is_the_browser_the_session_launches(tmp_path, monkeypatch):
    chosen = executable(tmp_path / "my-chromium")
    only_these_builds(monkeypatch, {"/opt/pw-browsers/chromium-1243/chrome-linux64/chrome": executable(tmp_path / "pw")})
    monkeypatch.setenv("GREG_CHROMIUM", str(chosen))
    assert computer.chromium() == str(chosen)


def test_a_greg_chromium_that_is_not_an_executable_file_is_passed_over(tmp_path, monkeypatch):
    build = executable(tmp_path / "pw")
    only_these_builds(monkeypatch, {"/opt/pw-browsers/chromium-1243/chrome-linux64/chrome": build})
    for bad in (tmp_path, tmp_path / "absent", tmp_path / "plain"):
        if bad.name == "plain":
            bad.write_text("not a program")
        monkeypatch.setenv("GREG_CHROMIUM", str(bad))
        assert computer.chromium() == str(build), bad


def test_playwrights_chrome_for_testing_layout_is_found_newest_first(tmp_path, monkeypatch):
    monkeypatch.delenv("GREG_CHROMIUM", raising=False)
    new = executable(tmp_path / "1243" / "chrome")
    old = executable(tmp_path / "1194" / "chrome")
    only_these_builds(monkeypatch, {"/opt/pw-browsers/chromium-1243/chrome-linux64/chrome": new,
                                    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome": old})
    assert computer.chromium() == str(new)
    only_these_builds(monkeypatch, {"/opt/pw-browsers/chromium-1194/chrome-linux/chrome": old})
    assert computer.chromium() == str(old)           # the old layout still counts


def test_no_browser_anywhere_is_said_truthfully(monkeypatch):
    monkeypatch.delenv("GREG_CHROMIUM", raising=False)
    only_these_builds(monkeypatch, {})
    with pytest.raises(CapabilityError, match="no Chromium installed"):
        computer.chromium()
