"""Whether a browser test may skip for want of a browser.

The browser tests drive a real Chromium: through Python Playwright (``browser.session`` in greg/computer.py, Mission
Control and the phone page in tests/integration, step 9 of the ten-step proof) or as a one-shot headless process
(``browser.render``). Where Playwright or a runnable Chromium is absent they skip. Canonical CI installed neither, so
on every pull request these tests read "SKIPPED could not import 'playwright'" beside a passing run, and a test that
had stopped matching the product (the phone page's decision record, 2026-11-12) went unnoticed. With
GREG_REQUIRE_BROWSER=1 (Canonical CI job 11) the same condition fails, naming what is missing, so a run that must
exercise the browser cannot pass without one. Unset (or any other value), a missing browser skips as before.

Only the browser is governed here. A test's other facilities keep their own skips and variables: bubblewrap
(GREG_REQUIRE_WORKER_ISOLATION), supervisord (GREG_REQUIRE_SUPERVISOR), numpy (requirements-cognition.txt).
"""
from __future__ import annotations

import glob
import os
from pathlib import Path
import shutil

import pytest

REQUIRE = "GREG_REQUIRE_BROWSER"
MISSING = ("GREG_REQUIRE_BROWSER=1 and the browser this test drives is missing or cannot run here (pip install "
           "playwright==1.63.0, then python -m playwright install --with-deps chromium; GREG_CHROMIUM names the "
           "binary)")


def browser_required() -> bool:
    """Whether this run requires the browser (GREG_REQUIRE_BROWSER=1 exactly, as the other GREG_REQUIRE_* do)."""
    return os.environ.get(REQUIRE) == "1"


def no_browser(reason: str):
    """Skip with ``reason``, or fail with MISSING and ``reason`` when GREG_REQUIRE_BROWSER=1. Never returns."""
    if browser_required():
        pytest.fail(f"{MISSING}: {reason}", pytrace=False)
    pytest.skip(reason, allow_module_level=True)


def playwright_api():
    """Python Playwright's sync API, or None when it cannot be imported (``require_browser`` decides what follows)."""
    try:
        import playwright.sync_api as api
    except ImportError:
        return None
    return api


def chromium_path() -> str | None:
    """The Chromium a Playwright test launches: GREG_CHROMIUM when it names one, else an installed build, else None.

    Playwright's own builds sit under ``chromium-<revision>/chrome-linux64/chrome`` (``chrome-linux`` before Chrome
    for Testing) in PLAYWRIGHT_BROWSERS_PATH; /opt/pw-browsers/chromium is this container's link to its build."""
    roots = [p for p in (os.environ.get("PLAYWRIGHT_BROWSERS_PATH"), "/opt/pw-browsers") if p and p != "0"]
    builds = [b for root in roots for layout in ("chrome-linux64", "chrome-linux")
              for b in sorted(glob.glob(f"{root}/chromium-*/{layout}/chrome"), reverse=True)]
    for candidate in (os.environ.get("GREG_CHROMIUM"), "/opt/pw-browsers/chromium", *builds,
                      shutil.which("chromium"), shutil.which("chromium-browser"), shutil.which("google-chrome")):
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


def require_browser(api, chromium, what: str) -> None:
    """Skip, or under GREG_REQUIRE_BROWSER=1 fail, a test whose Playwright (``api``) or Chromium is absent."""
    if api is None:
        no_browser(f"{what}: could not import Python Playwright")
    if chromium is None:
        no_browser(f"{what}: no Chromium binary (GREG_CHROMIUM unset and none installed)")
