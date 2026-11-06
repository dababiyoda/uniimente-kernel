"""GREG_REQUIRE_BROWSER=1 makes a missing Playwright fail the computer-use suites instead of skipping them (conftest.py).

Each case runs pytest in a subprocess from the repository root, with an import shim on PYTHONPATH that withholds
Playwright, so the real root conftest.py and the real suites are exercised; the installed Playwright is not touched.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SUITES = ["tests/unit/test_greg_computer.py",
          "tests/integration/test_greg_confined_egress.py::"
          "test_a_browser_session_drives_pages_behind_the_relay_and_nothing_else_leaves"]


def run(tmp_path: Path, suite: str, *, require: bool) -> subprocess.CompletedProcess:
    shim = tmp_path / "shim" / "playwright"
    shim.mkdir(parents=True, exist_ok=True)
    # ModuleNotFoundError, as an absent package raises: importorskip skips on exactly that.
    (shim / "__init__.py").write_text("raise ModuleNotFoundError('playwright withheld by this test', "
                                      "name='playwright')\n")
    env = {k: v for k, v in os.environ.items() if k not in ("GREG_REQUIRE_BROWSER", "PYTHONPATH")}
    env.update(PYTHONPATH=str(tmp_path / "shim"), PYTHONDONTWRITEBYTECODE="1")
    if require:
        env["GREG_REQUIRE_BROWSER"] = "1"
    return subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rs", suite],
                          cwd=ROOT, env=env, capture_output=True, text=True, timeout=300)


@pytest.mark.parametrize("suite", SUITES)
def test_without_playwright_a_browser_suite_skips_by_default_and_fails_when_the_browser_is_required(tmp_path, suite):
    default = run(tmp_path, suite, require=False)
    assert default.returncode in (0, 5), default.stdout[-2000:]      # 5: a module-level skip collected nothing
    assert "skipped" in default.stdout and "playwright withheld" in default.stdout
    required = run(tmp_path, suite, require=True)
    assert required.returncode in (1, 2), required.stdout[-2000:]    # a failed test or a collection error
    assert "skipped" not in required.stdout.splitlines()[-1]
    assert "GREG_REQUIRE_BROWSER=1 and could not import 'playwright'" in required.stdout


def test_other_optional_imports_still_skip_when_the_browser_is_required(tmp_path):
    (tmp_path / "test_other.py").write_text("import pytest\n\n\ndef test_optional():\n"
                                            "    pytest.importorskip('no_such_module_for_greg')\n")
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env.update(GREG_REQUIRE_BROWSER="1", PYTHONDONTWRITEBYTECODE="1")
    # -p conftest loads the repository's root conftest.py as a plugin for a test file outside the repository.
    out = subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "conftest",
                          "--rootdir", str(tmp_path), str(tmp_path / "test_other.py")],
                         cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0 and "1 skipped" in out.stdout, out.stdout[-2000:]
