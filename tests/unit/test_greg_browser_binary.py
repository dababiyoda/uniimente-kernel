"""browser.render uses an installed browser that can render, not merely one that is installed.

Measured on #196's 8d205324 in a Linux container: the full Chrome binary (Chrome for Testing 153) never returns from
a one-shot headless render, with GREG's command line or a minimal one, while the headless shell installed beside it
renders the same page under GREG's isolation flags in half a second. ``chrome_binary`` picked the full binary, every
render ran into its 45 second limit, and both real-browser tests in test_greg_browser.py skipped ("browser present
but cannot run here"). The Playwright paths also named only the earlier ``chrome-linux`` directory.

Every test here runs stand-in executables (shell scripts) through the real selection and the real ``browser_render``:
one writes a page, one never returns, one fails, one writes nothing. No real browser and no network is used; the real
browser is exercised by tests/unit/test_greg_browser.py, which runs here now and skipped before.
"""
from __future__ import annotations

import stat
from pathlib import Path

import pytest

from greg import capabilities, computer
from greg.capabilities import BUILTINS, CapabilityError, InvocationContext, browser_render

PAGE = "<html><head><title>stand-in</title></head><body><p>greg-renders-42</p><p>hello page</p></body></html>"


def stand_in(path: Path, body: str) -> str:
    """An executable that logs each run (its arguments, and its environment per run) and then does ``body``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\nprintf '%s\\n' \"$*\" >> '{path}.runs'\n"
                    f"env | sort > \"{path}.env.$(wc -l < '{path}.runs' | tr -d ' ')\"\n{body}\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path)


def runs(binary: str) -> list[str]:
    log = Path(binary + ".runs")
    return log.read_text().splitlines() if log.exists() else []


RENDERS, HANGS, FAILS, SILENT, OTHER = (f"echo '{PAGE}'", "exec sleep 30", "echo boom >&2\nexit 3", "exit 0",
                                        "echo '<html><p>some other page</p></html>'")


@pytest.fixture
def machine(tmp_path, monkeypatch):
    """A machine with no browser at all: each test installs the stand-ins it needs."""
    monkeypatch.delenv("GREG_CHROMIUM", raising=False)
    monkeypatch.setattr(capabilities, "PLAYWRIGHT_BROWSERS", str(tmp_path / "pw"))
    monkeypatch.setattr(capabilities, "CHROME_CANDIDATES", (str(tmp_path / "sys" / "google-chrome"),
                                                           str(tmp_path / "sys" / "chromium")))
    monkeypatch.setattr(capabilities, "HEADLESS_SHELL_CANDIDATES", (str(tmp_path / "sys" / "chrome-headless-shell"),))
    monkeypatch.setattr(capabilities, "RENDER_SECONDS", 1)
    monkeypatch.setattr(capabilities, "_render_judged", {})
    return tmp_path


def shell(root: Path, build: int, body: str = RENDERS, layout: str = "chrome-headless-shell-linux64") -> str:
    return stand_in(root / "pw" / f"chromium_headless_shell-{build}" / layout / "chrome-headless-shell", body)


def full(root: Path, build: int, body: str = RENDERS, layout: str = "chrome-linux64") -> str:
    return stand_in(root / "pw" / f"chromium-{build}" / layout / "chrome", body)


def test_the_headless_shell_comes_first_and_the_newest_build_by_number(machine):
    """Candidates in the order they are tried. 1243 is newer than 999 as a number and older as text; both spellings of
    the build's OS directory are found. Nothing is run to list them."""
    old_shell, new_shell = shell(machine, 999), shell(machine, 1243)
    old_full, new_full = full(machine, 900, layout="chrome-linux"), full(machine, 1243)
    system = stand_in(machine / "sys" / "google-chrome", RENDERS)
    system_shell = stand_in(machine / "sys" / "chrome-headless-shell", RENDERS)
    assert capabilities.chrome_candidates() == [new_shell, old_shell, system_shell, system, new_full, old_full]
    assert capabilities.installed_chrome() == new_shell
    assert not any(runs(b) for b in (old_shell, new_shell, old_full, new_full, system, system_shell))
    # the session route drives the full browser: the newest full build, never the headless shell
    assert computer.chromium() == new_full


def test_a_browser_that_never_returns_is_passed_over_for_one_that_renders(machine):
    """The measured case: the first installed browser does not return. Before: it was the one used, and every render
    ended at its limit. It is judged once; the next call does not wait for it again."""
    hangs, renders = shell(machine, 1243, HANGS), stand_in(machine / "sys" / "google-chrome", RENDERS)
    assert capabilities.installed_chrome() == hangs                      # installed, and named first
    assert capabilities.chrome_binary() == renders                       # but not the one that renders
    assert capabilities.chrome_binary() == renders
    assert len(runs(hangs)) == 1 and len(runs(renders)) == 1, "each build is judged by one run"
    assert capabilities.cannot_render(hangs) == "did not finish rendering a local page within 1 seconds"


def test_a_failure_is_judged_again_only_after_the_retry_time(machine, monkeypatch):
    hangs = shell(machine, 1243, HANGS)
    stand_in(machine / "sys" / "google-chrome", RENDERS)
    capabilities.chrome_binary()
    capabilities.chrome_binary()
    assert len(runs(hangs)) == 1
    monkeypatch.setattr(capabilities, "RENDER_RETRY_SECONDS", 0.0)       # the retry time has passed
    capabilities.chrome_binary()
    assert len(runs(hangs)) == 2


def test_a_build_that_rendered_is_not_run_again_until_the_binary_changes(machine, monkeypatch):
    monkeypatch.setattr(capabilities, "RENDER_RETRY_SECONDS", 0.0)       # a success is kept whatever the retry time
    renders = shell(machine, 1243)
    assert [capabilities.chrome_binary() for _ in range(3)] == [renders] * 3 and len(runs(renders)) == 1
    Path(renders).write_text(Path(renders).read_text() + "# reinstalled\n")   # another build at the same path
    assert capabilities.chrome_binary() == renders and len(runs(renders)) == 2


@pytest.mark.parametrize("body, why", [
    (FAILS, "did not render a local page: boom"),
    (SILENT, "did not render a local page: it wrote nothing"),
    (OTHER, "did not render a local page: it wrote another page"),
    (f"echo '{PAGE}'\nexit 3", "did not render a local page: exit 3"),
], ids=["fails", "silent", "another-page", "page-then-failure"])
def test_only_a_binary_that_writes_the_page_it_was_given_renders(machine, body, why):
    """Exiting 0 is not rendering: the page's own script has to have run and its text been written out."""
    broken = shell(machine, 1243, body)
    assert capabilities.cannot_render(broken) == why
    with pytest.raises(CapabilityError) as refused:
        capabilities.chrome_binary()
    assert str(refused.value) == f"no installed browser renders a page here: chrome-headless-shell {why}"


def test_a_binary_that_cannot_be_started_is_a_reason_not_a_crash(machine):
    path = machine / "pw" / "chromium_headless_shell-1243" / "chrome-headless-shell-linux64" / "chrome-headless-shell"
    path.parent.mkdir(parents=True)
    path.write_text("#!/nonexistent/interpreter\n")
    path.chmod(0o755)
    assert capabilities.cannot_render(str(path)).startswith("could not be started (")


def test_the_founders_choice_is_never_replaced_by_another_browser(machine, monkeypatch):
    """GREG_CHROMIUM names the browser the founder chose. When it cannot render, GREG refuses and says so; a working
    browser installed beside it is not run in its place."""
    chosen, other = stand_in(machine / "chosen" / "my-chrome", HANGS), shell(machine, 1243)
    monkeypatch.setenv("GREG_CHROMIUM", chosen)
    assert capabilities.chrome_candidates() == [chosen] and capabilities.installed_chrome() == chosen
    with pytest.raises(CapabilityError) as refused:
        capabilities.chrome_binary()
    assert str(refused.value) == ("no installed browser renders a page here: my-chrome did not finish rendering a "
                                  "local page within 1 seconds")
    assert not runs(other)
    monkeypatch.setenv("GREG_CHROMIUM", str(machine / "not-installed"))  # a choice that names nothing, as before:
    assert capabilities.chrome_binary() == other                         # the installed browsers are used


def test_no_installed_browser_is_a_refusal(machine, tmp_path):
    """Before: the render ran a path that does not exist and raised FileNotFoundError, which is not a capability's
    refusal (the Gate records an exception it does not know as an unknown outcome)."""
    manifest, _ = BUILTINS["browser.render"]
    assert capabilities.chrome_candidates() == []
    assert capabilities.installed_chrome() == capabilities.CHROME_CANDIDATES[0]     # the manifest still names one
    with pytest.raises(CapabilityError, match="no Chrome or Chromium is installed on this body"):
        browser_render({"url": "http://127.0.0.1:9/x"},
                       InvocationContext(workspace=tmp_path, read_roots=(), secrets=None, manifest=manifest))


def test_a_render_runs_the_browser_that_passed_and_says_which(machine, tmp_path):
    hangs, renders = shell(machine, 1243, HANGS), stand_in(machine / "sys" / "google-chrome", RENDERS)
    manifest, _ = BUILTINS["browser.render"]
    out = browser_render({"url": "http://127.0.0.1:9/x"},
                         InvocationContext(workspace=tmp_path, read_roots=(), secrets=None, manifest=manifest))
    assert out["browser"] == "google-chrome" and "hello page" in out["text"]
    assert len(runs(hangs)) == 1                                         # its one check; the render did not use it
    check, render = runs(renders)
    assert check.endswith(capabilities.RENDER_CHECK_PAGE) and render.endswith("http://127.0.0.1:9/x")


@pytest.mark.parametrize("own_sandbox", [True, False], ids=["sandboxes-itself", "as-root-on-linux"])
def test_the_check_contacts_no_one_and_runs_as_a_render_runs(machine, tmp_path, monkeypatch, own_sandbox):
    """The check is the render's own command line on a page that has no address: every name resolves to nothing,
    every request goes to a closed port, and the environment is the three variables a render is given."""
    monkeypatch.setattr(capabilities, "_sandboxes_itself", lambda: own_sandbox)
    monkeypatch.setenv("GREG_TEST_NOT_FOR_THE_BROWSER", "1")
    renders = shell(machine, 1243)
    manifest, _ = BUILTINS["browser.render"]
    out = browser_render({"url": "http://127.0.0.1:9/x"},
                         InvocationContext(workspace=tmp_path, read_roots=(), secrets=None, manifest=manifest))
    assert out["os_sandboxed"] is own_sandbox
    check, render = (line.split(" ") for line in runs(renders))
    assert check[-1].startswith("data:text/html,") and "greg-renders-42" not in check[-1]   # the script computes it
    joined = " ".join(check)
    assert "--host-resolver-rules=MAP * ~NOTFOUND --proxy-server=http://127.0.0.1:9 " in joined
    assert "EXCLUDE" not in joined and "--proxy-bypass-list" not in joined                  # nothing is reachable
    assert ("--no-sandbox" in check) == ("--no-sandbox" in render) == (not own_sandbox)
    shared = len(capabilities._headless("b", "p")) - 2 + (not own_sandbox)                  # all but binary, profile
    assert check[:shared] == render[:shared] and shared >= 11                               # the same flags, in order
    for run, home in ((1, "greg-browser-check-"), (2, "greg-browser-")):        # the check's run, then the render's
        env = dict(line.split("=", 1) for line in Path(f"{renders}.env.{run}").read_text().splitlines())
        assert env["PATH"] == "/usr/bin:/bin" and env["LANG"] == "C.UTF-8" and home in env["HOME"]
        assert "GREG_TEST_NOT_FOR_THE_BROWSER" not in env
