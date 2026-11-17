"""browser.render uses an installed browser that can render, not merely one that is installed.

Measured on #196's 8d205324 in a Linux container: the full Chrome binary (Chrome for Testing 153) never returns from
a one-shot headless render, with GREG's command line or a minimal one, while the headless shell installed beside it
renders the same page under GREG's isolation flags in half a second. ``chrome_binary`` picked the full binary, every
render ran into its 45 second limit, and both real-browser tests in test_greg_browser.py skipped ("browser present
but cannot run here"). The Playwright path also named only the earlier ``chrome-linux`` directory. (The session
route's own lookup, ``greg.computer.chromium``, has the same stale path; draft #233 fixes it and this change leaves
that file alone.)

Every test here runs stand-in executables (shell scripts) through the real selection and the real ``browser_render``:
one writes a page, one never returns, one fails, one writes nothing. No real browser and no network is used; the real
browser is exercised by tests/unit/test_greg_browser.py, which runs here now and skipped before.

What the stand-ins show and a real browser in that container does not: docs/evidence/greg-browser-binary/2026-11-11.
"""
from __future__ import annotations

import errno
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from greg import capabilities
from greg.capabilities import BUILTINS, CapabilityError, InvocationContext, browser_render
from tests.greg_fixtures import Clock, drop, make_body, mission, signed

PAGE = "<html><head><title>stand-in</title></head><body><p>greg-renders-42</p><p>hello page</p></body></html>"


def stand_in(path: Path, body: str) -> str:
    """An executable that logs each run (its arguments, and per run its environment and its working directory) and
    then does ``body``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\nprintf '%s\\n' \"$*\" >> '{path}.runs'\n"
                    f"run=$(wc -l < '{path}.runs' | tr -d ' ')\n"
                    f"env | sort > \"{path}.env.$run\"\npwd > \"{path}.cwd.$run\"\n{body}\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path)


def runs(binary: str) -> list[str]:
    log = Path(binary + ".runs")
    return log.read_text().splitlines() if log.exists() else []


RENDERS, HANGS, FAILS, SILENT, OTHER = (f"echo '{PAGE}'", "exec sleep 30", "echo boom >&2\nexit 3", "exit 0",
                                        "echo '<html><p>some other page</p></html>'")
# passes the check (a data: page) and never returns from a real page within the render's limit
RENDERS_ONLY_THE_CHECK = f"case \"$*\" in *data:text/html*) echo '{PAGE}';; *) exec sleep 5;; esac"
# the behaviour of Chrome where an ordinary user may not create its sandbox
NEEDS_NO_SANDBOX = (f"case \" $* \" in *' --no-sandbox '*) echo '{PAGE}';; "
                    "*) echo 'No usable sandbox!' >&2; exit 1;; esac")
URL = "http://127.0.0.1:9/x"


def context(tmp_path, egress=None) -> InvocationContext:
    return InvocationContext(workspace=tmp_path, read_roots=(), secrets=None, manifest=BUILTINS["browser.render"][0],
                             egress=egress)


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


def test_a_browser_that_never_returns_is_passed_over_for_one_that_renders(machine):
    """The measured case: the first installed browser does not return. Before: it was the one used, and every render
    ended at its limit. It is judged once; the next call does not wait for it again."""
    hangs, renders = shell(machine, 1243, HANGS), stand_in(machine / "sys" / "google-chrome", RENDERS)
    assert capabilities.installed_chrome() == hangs                      # installed, and listed first
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


def test_the_founders_choice_is_the_only_browser_run(machine, monkeypatch):
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
    monkeypatch.setenv("GREG_CHROMIUM", "")                              # empty reads as unset: GREG chooses
    assert capabilities.chrome_binary() == other


def _not_a_browser(machine, monkeypatch, kind: str) -> str:
    """One way GREG_CHROMIUM can be set without naming the absolute path of an executable file."""
    working = stand_in(machine / "chosen" / "my-chrome", RENDERS)
    if kind == "a directory":
        (machine / "chosen" / "adir").mkdir()
        return str(machine / "chosen" / "adir")
    if kind == "a file that is not executable":
        (machine / "chosen" / "notes.txt").write_text("not a program\n")
        return str(machine / "chosen" / "notes.txt")
    if kind == "a path with nothing at it":
        return str(machine / "chosen" / "not-installed")
    if kind == "an unexpanded home directory":
        return "~/my-chrome"
    if kind == "a relative path that resolves from the working directory":
        monkeypatch.chdir(machine)
        return "chosen/my-chrome"
    assert kind == "a working path with a newline after it"
    return working + "\n"


@pytest.mark.parametrize("kind", [
    "a directory", "a file that is not executable", "a path with nothing at it", "an unexpanded home directory",
    "a relative path that resolves from the working directory", "a working path with a newline after it"])
def test_a_choice_that_names_no_browser_is_refused_by_name_and_nothing_else_is_run(machine, tmp_path, monkeypatch,
                                                                                    kind):
    """Before: GREG_CHROMIUM set to anything but an executable file was ignored, and GREG ran another installed
    browser without saying so (a relative path was run from the check's own directory, where it names nothing). A
    founder who set the variable gets that browser or a refusal that names the variable and its value."""
    other = shell(machine, 1243)
    value = _not_a_browser(machine, monkeypatch, kind)
    monkeypatch.setenv("GREG_CHROMIUM", value)
    said = (f"GREG_CHROMIUM is set to {value!r}, which is not the absolute path of an executable file; GREG runs "
            "the browser that variable names or none (unset it to let GREG choose among the installed browsers)")
    for refuses in (capabilities.chrome_candidates, capabilities.chrome_binary, capabilities.installed_chrome,
                    lambda: browser_render({"url": URL}, context(tmp_path))):
        with pytest.raises(CapabilityError) as refused:
            refuses()
        assert str(refused.value) == said
    assert BUILTINS["browser.render"][0].available() == (False, said)      # the office answers UNAVAILABLE with it
    assert not runs(other) and not runs(str(machine / "chosen" / "my-chrome"))


def test_no_installed_browser_is_a_refusal(machine, tmp_path):
    """A body with no browser: the manifest says so when asked (the office's precheck answers UNAVAILABLE with this
    reason before the adapter runs), and the adapter called directly, or reached after the last browser was removed,
    refuses with a CapabilityError. Before, the adapter ran a path that does not exist and raised FileNotFoundError,
    which is not a capability's refusal (the Gate records an exception it does not know as an unknown outcome)."""
    manifest, _ = BUILTINS["browser.render"]
    assert capabilities.chrome_candidates() == []
    assert manifest.available() == (False, "no Chrome or Chromium is installed on this body")
    for route in (None, object()):                                       # unconfined, and behind the relay
        with pytest.raises(CapabilityError, match="^no Chrome or Chromium is installed on this body$"):
            browser_render({"url": URL}, context(tmp_path, egress=route))
    with pytest.raises(CapabilityError, match="^no Chrome or Chromium is installed on this body$"):
        capabilities.installed_chrome()


def test_a_render_runs_the_browser_that_passed_and_says_which(machine, tmp_path):
    hangs, renders = shell(machine, 1243, HANGS), stand_in(machine / "sys" / "google-chrome", RENDERS)
    out = browser_render({"url": URL}, context(tmp_path))
    assert out["browser"] == "google-chrome" and "hello page" in out["text"]
    assert len(runs(hangs)) == 1                                         # its one check; the render did not use it
    check, render = runs(renders)
    assert check.endswith(capabilities.RENDER_CHECK_PAGE) and render.endswith(URL)


@pytest.mark.parametrize("own_sandbox", [True, False], ids=["sandboxes-itself", "as-root-on-linux"])
def test_the_check_contacts_no_one_and_runs_as_a_render_runs(machine, tmp_path, monkeypatch, own_sandbox):
    """The check is the render's own command line on a page that has no address: every name resolves to nothing,
    every request goes to a closed port, the environment is the three variables a render is given, and it runs in
    its own fresh profile directory, not wherever the body happens to be."""
    monkeypatch.setattr(capabilities, "_sandboxes_itself", lambda: own_sandbox)
    monkeypatch.setenv("GREG_TEST_NOT_FOR_THE_BROWSER", "1")
    renders = shell(machine, 1243)
    out = browser_render({"url": URL}, context(tmp_path))
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
        assert Path(f"{renders}.cwd.{run}").read_text().strip() == env["HOME"] != os.getcwd()
        assert not Path(env["HOME"]).exists()                                   # each profile is removed afterwards
    for flag in ("--headless=new", "--no-first-run", "--no-default-browser-check", "--disable-extensions",
                 "--disable-background-networking", "--disable-sync", "--disable-component-update",
                 "--disable-default-apps"):
        assert flag in check and flag in render, flag                           # nothing of the browser's own runs


@pytest.mark.parametrize("platform, euid, own_sandbox", [("linux", 0, False), ("linux", 1000, True),
                                                         ("darwin", 0, True), ("darwin", 501, True)])
def test_only_root_on_linux_is_told_the_browser_cannot_sandbox_itself(monkeypatch, platform, euid, own_sandbox):
    monkeypatch.setattr(capabilities.sys, "platform", platform)
    monkeypatch.setattr(capabilities.os, "geteuid", lambda: euid)
    assert capabilities._sandboxes_itself() is own_sandbox


# -- what counts as an installed candidate -----------------------------------------------------------------------------

def test_a_directory_or_a_file_that_is_not_executable_is_not_a_candidate(machine):
    (machine / "sys" / "google-chrome").mkdir(parents=True)             # a directory is "executable" to os.access
    (machine / "sys" / "chromium").write_text("#!/bin/sh\necho not marked executable\n")
    assert capabilities.chrome_candidates() == []
    real = stand_in(machine / "sys" / "chrome-headless-shell", RENDERS)
    assert capabilities.chrome_candidates() == [real]


def test_a_build_directory_without_a_plain_number_is_listed_last_and_breaks_nothing(machine):
    """Before: a directory name ending in a digit that int() refuses (a superscript two passes str.isdigit) raised
    ValueError while greg.capabilities was imported, so no GREG process started."""
    numbered = [shell(machine, 999), shell(machine, 1243)]
    odd = [stand_in(machine / "pw" / f"chromium_headless_shell-{name}" / "chrome-headless-shell-linux64"
                    / "chrome-headless-shell", RENDERS) for name in ("1243\u00b2", "beta")]
    listed = capabilities.chrome_candidates()
    assert listed[:2] == [numbered[1], numbered[0]] and sorted(listed[2:]) == sorted(odd)


def test_a_candidate_that_vanished_before_it_was_judged_is_a_reason_not_a_crash(machine, monkeypatch):
    gone, renders = str(machine / "sys" / "google-chrome"), stand_in(machine / "sys" / "chromium", RENDERS)
    monkeypatch.setattr(capabilities, "chrome_candidates", lambda: [gone, renders])   # listed, then removed
    assert capabilities.cannot_render(gone) == "cannot be read (No such file or directory)"
    assert capabilities.chrome_binary() == renders
    monkeypatch.setattr(capabilities, "chrome_candidates", lambda: [gone])
    with pytest.raises(CapabilityError, match="google-chrome cannot be read"):
        capabilities.chrome_binary()


# -- what is remembered of a binary ------------------------------------------------------------------------------------

def test_a_build_is_its_size_its_modification_time_and_its_change_time():
    """Each of the three alone makes another build: a rewrite changes the size or the modification time, and a file
    replaced by one of the same size with its modification time put back still has a new change time."""
    made = dict(st_size=198, st_mtime_ns=1_700_000_000_000_000_000, st_ctime_ns=1_700_000_000_000_000_000)
    same = capabilities._build(SimpleNamespace(**made))
    for field in made:
        assert capabilities._build(SimpleNamespace(**{**made, field: made[field] + 1})) != same, field


def test_a_replacement_of_the_same_size_with_the_same_modification_time_is_judged_again(machine):
    """Before: the build was (size, modification time), so this replacement kept the earlier build's success."""
    binary = shell(machine, 1243)
    before = os.stat(binary)
    assert capabilities.chrome_binary() == binary
    Path(binary).write_text(Path(binary).read_text().replace("greg-renders-42", "greg-renders-43"))
    os.utime(binary, ns=(before.st_atime_ns, before.st_mtime_ns))
    after = os.stat(binary)
    assert (after.st_size, after.st_mtime_ns) == (before.st_size, before.st_mtime_ns)
    assert capabilities.cannot_render(binary) == "did not render a local page: it wrote another page"
    assert len(runs(binary)) == 2 and len(capabilities._render_judged) == 1     # one entry per path, not per build


def wrapper(machine: Path, real_body: str) -> tuple[str, Path]:
    """A candidate that is a script around the real browser, as both first candidates are where this was measured
    (the Playwright headless shell and /usr/bin/google-chrome are shell wrappers there)."""
    real = machine / "pw" / "chromium_headless_shell-1243" / "chrome-headless-shell-linux64" / "the-real-browser"
    stand_in(real, real_body)
    return shell(machine, 1243, f"exec '{real}' \"$@\""), real


def test_a_render_that_never_returns_ends_at_the_limit_and_the_binary_is_judged_again(machine, tmp_path):
    """The render itself (not the check) runs into RENDER_SECONDS: a refusal that names the limit. What was
    remembered of that binary is forgotten, so the next call runs its check again."""
    binary = shell(machine, 1243, RENDERS_ONLY_THE_CHECK)
    started = time.monotonic()
    with pytest.raises(CapabilityError, match="^browser did not finish rendering within 1 seconds$"):
        browser_render({"url": URL}, context(tmp_path))
    assert time.monotonic() - started < 4
    assert [line.rsplit(" ", 1)[-1] for line in runs(binary)] == [capabilities.RENDER_CHECK_PAGE, URL]
    assert capabilities.chrome_binary() == binary
    assert len(runs(binary)) == 3 and runs(binary)[-1].endswith(capabilities.RENDER_CHECK_PAGE)


def test_a_success_is_not_kept_when_the_browser_behind_a_wrapper_stops_rendering(machine, tmp_path):
    """Before: the wrapper file had not changed, so its success was kept and every later render ran into the limit
    with a working browser installed beside it."""
    wrapped, real = wrapper(machine, RENDERS)
    other = stand_in(machine / "sys" / "google-chrome", RENDERS)
    assert browser_render({"url": URL}, context(tmp_path))["browser"] == "chrome-headless-shell"
    stand_in(real, HANGS)                                               # the real browser is replaced; the wrapper is not
    with pytest.raises(CapabilityError, match="did not finish rendering within 1 seconds"):
        browser_render({"url": URL}, context(tmp_path))
    assert browser_render({"url": URL}, context(tmp_path))["browser"] == "google-chrome"
    assert not runs(other)[0].endswith(URL)                             # it was judged before it was used


def test_a_success_is_not_kept_when_the_browser_can_no_longer_be_started(machine, tmp_path):
    """The file is unchanged and still executable, and starting it fails (here: its interpreter is gone). Before:
    an OSError the Gate records as an unknown outcome, on every call."""
    interpreter = machine / "interp"
    interpreter.symlink_to("/bin/sh")
    binary = shell(machine, 1243)
    Path(binary).write_text(Path(binary).read_text().replace("#!/bin/sh", f"#!{interpreter}"))
    other = stand_in(machine / "sys" / "google-chrome", RENDERS)
    assert capabilities.chrome_binary() == binary
    interpreter.unlink()
    with pytest.raises(CapabilityError, match=r"^browser could not be started \(No such file or directory\)$"):
        browser_render({"url": URL}, context(tmp_path))
    assert browser_render({"url": URL}, context(tmp_path))["browser"] == "google-chrome" and runs(other)


def test_failing_to_remove_a_profile_never_replaces_the_result(machine, monkeypatch):
    """Measured with the real full Chrome: killed at its limit, its helper processes were still writing into the
    profile, removing it raised "Directory not empty", and that OSError came out of the check in place of its
    answer. Removal is tried again; a failure to remove is never the result. (Helpers that outlive the retries
    still leave a directory behind: the browser's process group is not killed. Recorded, not fixed here.)"""
    real_rmtree, calls = shutil.rmtree, []

    def straggler_still_writing(path, ignore_errors=False):
        calls.append(path)
        if len(calls) == 1:                                             # the first attempt loses the race
            if not ignore_errors:
                raise OSError(errno.ENOTEMPTY, "Directory not empty", path)
            return
        real_rmtree(path, ignore_errors=ignore_errors)

    monkeypatch.setattr(capabilities.shutil, "rmtree", straggler_still_writing)
    try:
        assert capabilities.cannot_render(shell(machine, 1243)) is None
        assert len(calls) == 2 and calls[0] == calls[1] and not Path(calls[0]).exists()
    finally:
        for left in calls[:1]:                                          # nothing is left behind when this test fails
            real_rmtree(left, ignore_errors=True)


# -- one call judges for a bounded time --------------------------------------------------------------------------------

def test_the_longest_call_ends_before_the_body_is_taken_for_stopped():
    """A render runs inside the body's turn. The longest one (checks that start just inside JUDGING_SECONDS and run
    to their limit, then a render that runs to its limit) is shorter than the heartbeat age at which the console,
    Mission Control and acceptance call the body not running. This bounds the render's share of a turn; the turn's
    other work is not counted here."""
    from greg.acceptance import STALE_HEARTBEAT_SECONDS
    assert (capabilities.RENDER_SECONDS, capabilities.JUDGING_SECONDS, capabilities.RENDER_RETRY_SECONDS) == (
        45, 60.0, 600.0)
    assert capabilities.JUDGING_SECONDS + 2 * capabilities.RENDER_SECONDS < STALE_HEARTBEAT_SECONDS


def test_one_call_judges_for_a_bounded_time_and_names_what_it_did_not_judge(machine, monkeypatch):
    """Before: every installed candidate was judged in one call, 45 seconds for each that never returns, inside the
    body's turn. Now no check starts once the call has judged for JUDGING_SECONDS. A candidate it did not get to is
    named as not judged (not as unable to render), and the next call gets to it, because the first two are
    remembered."""
    monkeypatch.setattr(capabilities, "JUDGING_SECONDS", 1.5)           # with checks of 1 second: two of them
    first, second = shell(machine, 1243, HANGS), shell(machine, 999, HANGS)
    third = stand_in(machine / "sys" / "google-chrome", RENDERS)
    started = time.monotonic()
    with pytest.raises(CapabilityError) as refused:
        capabilities.chrome_binary()
    assert time.monotonic() - started < 1.5 + 1 + 1
    assert str(refused.value) == (
        "no browser judged so far renders a page here: "
        "chrome-headless-shell did not finish rendering a local page within 1 seconds; "
        "chrome-headless-shell did not finish rendering a local page within 1 seconds; "
        "not judged in this call, which starts no check after 1.5 seconds of judging: google-chrome")
    assert (len(runs(first)), len(runs(second)), len(runs(third))) == (1, 1, 0)
    assert capabilities.chrome_binary() == third                        # the next call starts where this one stopped
    assert (len(runs(first)), len(runs(second)), len(runs(third))) == (1, 1, 1)
    # A candidate already known to render costs nothing, so it is used however long the others took to judge.
    monkeypatch.setattr(capabilities, "RENDER_RETRY_SECONDS", 0.0)      # the two failures are due to be judged again
    assert capabilities.chrome_binary() == third
    assert (len(runs(first)), len(runs(second)), len(runs(third))) == (2, 2, 1)


# -- a confined-egress body ----------------------------------------------------------------------------------------------

def test_behind_the_relay_no_browser_is_started_outside_the_namespace(machine, tmp_path, monkeypatch):
    """Before: the check ran first, so a body configured for confined egress started a browser outside the namespace
    that route exists to keep it in, even on a host where the route then refused for lack of namespaces. Behind the
    relay nothing is judged: the first installed candidate is handed to the namespace as it is."""
    first, second = shell(machine, 1243, HANGS), stand_in(machine / "sys" / "google-chrome", RENDERS)
    handed = []

    def namespace(argv, relay, host, port, loopback, profile, env):
        handed.append((argv[0], len(runs(first)) + len(runs(second)), relay, host, port))
        return subprocess.CompletedProcess(argv, 0, PAGE.encode(), b"")

    monkeypatch.setattr(capabilities, "_render_behind_relay", namespace)
    relay = object()
    out = browser_render({"url": URL}, context(tmp_path, egress=relay))
    assert handed == [(first, 0, relay, "127.0.0.1", 9)]                 # the first installed, and nothing run before
    assert out["browser"] == "chrome-headless-shell" and out["os_sandboxed"] is False
    assert not runs(first) and not runs(second) and capabilities._render_judged == {}


def test_behind_the_relay_without_namespaces_nothing_runs_at_all(machine, tmp_path, monkeypatch):
    """The confined route's own rule ("without namespaces nothing runs") holds for the choice of browser too."""
    from greg import worker_isolation

    def no_namespaces(**kw):
        raise worker_isolation.WorkerIsolationError("no bubblewrap on this host")

    monkeypatch.setattr(worker_isolation, "_backend", no_namespaces)
    browsers = [shell(machine, 1243), stand_in(machine / "sys" / "google-chrome", RENDERS)]
    with pytest.raises(CapabilityError, match="confined egress needs bubblewrap network namespaces here"):
        browser_render({"url": URL}, context(tmp_path, egress=object()))
    assert not any(runs(b) for b in browsers)


def test_behind_the_relay_a_browser_is_not_refused_by_the_unconfined_sandbox_rule(machine, tmp_path, monkeypatch):
    """A confined render always runs with --no-sandbox (the browser cannot nest its own namespace inside GREG's).
    Before: the check applied the unconfined rule first, so a browser that an ordinary user can only run with
    --no-sandbox was refused before the confined route was reached."""
    monkeypatch.setattr(capabilities, "_sandboxes_itself", lambda: True)            # an ordinary user
    binary = shell(machine, 1243, NEEDS_NO_SANDBOX)
    monkeypatch.setattr(capabilities, "_render_behind_relay",
                        lambda argv, relay, host, port, loopback, profile, env:
                        subprocess.run(argv, capture_output=True, timeout=10, env=env))
    out = browser_render({"url": URL}, context(tmp_path, egress=object()))
    assert out["os_sandboxed"] is False and "hello page" in out["text"]
    assert len(runs(binary)) == 1 and runs(binary)[0].startswith("--no-sandbox ")
    assert capabilities.cannot_render(binary) == "did not render a local page: No usable sandbox!"   # unconfined rule


# -- the manifest and the office ---------------------------------------------------------------------------------------

def test_the_manifest_names_no_binary_and_says_what_is_installed_each_time_it_is_asked(machine, monkeypatch):
    """Before: the manifest named the first installed candidate as it was when the module was imported. The office's
    precheck read that path, so a build replaced under a running body made browser.render UNAVAILABLE with a working
    browser installed; and a path that differed between the body's process and its appraiser's gave the two different
    manifest digests."""
    manifest, _ = BUILTINS["browser.render"]
    digest = manifest.digest()
    assert manifest.binaries == () and not manifest.validate()
    assert manifest.available() == (False, "no Chrome or Chromium is installed on this body")
    old = shell(machine, 1300)
    assert manifest.available() == (True, "available")
    shutil.rmtree(Path(old).parents[1])                                 # the upgrade: build 1300 goes, 1301 arrives
    assert manifest.available() == (False, "no Chrome or Chromium is installed on this body")
    new = shell(machine, 1301)
    assert manifest.available() == (True, "available") and capabilities.chrome_binary() == new
    monkeypatch.setenv("GREG_CHROMIUM", new)
    assert manifest.digest() == digest and not runs(old)                # the same manifest whatever is installed


def _render_check(mission_id: str) -> dict:
    check = {"check_id": "c", "description": "the page shows its text",
             "sensor": {"capability": "browser.render", "params": {"url": URL}, "target": "web:127.0.0.1"},
             "predicate": {"op": "contains", "field": "text", "value": "hello page"}}
    return mission(mission_id, checks=[check], strategies=[], capabilities=["browser.render"],
                   targets=("web:127.0.0.1",), ceiling="read_only")


def test_a_running_body_renders_across_a_browser_upgrade(machine, tmp_path):
    """Through the canonical path (signed mission, office, Gate, receipt, separate appraiser). The body starts with
    no browser, then build 1300 is installed, then replaced by 1301 while the body runs."""
    from greg.body import Body
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _render_check("m:upgrade")))
    clock = Clock()
    with Body(home, clock=clock) as body:
        def facts(kind):
            return [e.payload for e in body.journal.replay(kind) if e.payload.get("mission_id") == "m:upgrade"]
        body.tick()
        assert facts("mission.observed")[-1]["detail"] == (
            "sensor UNAVAILABLE: no Chrome or Chromium is installed on this body")
        old = shell(machine, 1300)
        assert body.registry.usable("browser.render") == (True, "available")
        shutil.rmtree(Path(old).parents[1])
        new = shell(machine, 1301)
        for _ in range(4):
            clock.advance(4000)
            body.tick()
        assert facts("mission.achieved"), facts("mission.observed")
        assert [a["verdict"] for a in facts("mission.appraised")] == ["VERIFIED"]
        assert not runs(old) and [line.rsplit(" ", 1)[-1] for line in runs(new)] == [capabilities.RENDER_CHECK_PAGE, URL]


BODY_WITH_A_CHOSEN_BROWSER = """
import json, sys
from pathlib import Path
from greg.body import Body
from tests.greg_fixtures import Clock, drop, make_body, signed
home, key, body_id, _ = make_body(Path(sys.argv[1]))
drop(home, signed(key, body_id, "MISSION", json.loads(sys.argv[2])))
clock = Clock()
with Body(home, clock=clock) as body:
    for _ in range(4):
        body.tick()
        clock.advance(1)
    print(json.dumps({kind: [e.payload.get("verdict", True) for e in body.journal.replay("mission." + kind)]
                      for kind in ("achieved", "appraised")}))
"""


def test_a_closure_observed_with_the_founders_chosen_browser_is_verified(machine, tmp_path):
    """The body's process has GREG_CHROMIUM in its environment; the appraiser's process is started without it.
    Before: the manifest named the chosen binary in the body and another in the appraiser, their digests differed,
    and the appraiser answered REFUTED ("receipt not bound to this closure and signed sensor") to a true closure."""
    chosen = stand_in(machine / "chosen" / "my-chrome", RENDERS)
    env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1", "GREG_CHROMIUM": chosen,
           "PYTHONPATH": os.pathsep.join([str(Path(capabilities.__file__).resolve().parents[1]),
                                          *(p for p in sys.path if "-packages" in p)])}
    (tmp_path / "body-home").mkdir()
    ran = subprocess.run([sys.executable, "-c", BODY_WITH_A_CHOSEN_BROWSER, str(tmp_path / "body-home"),
                          json.dumps(_render_check("m:chosen"))], env=env, capture_output=True, text=True, timeout=120)
    assert ran.returncode == 0, ran.stderr[-2000:]
    assert json.loads(ran.stdout.splitlines()[-1]) == {"achieved": [True], "appraised": ["VERIFIED"]}
    assert [line.rsplit(" ", 1)[-1] for line in runs(chosen)] == [capabilities.RENDER_CHECK_PAGE, URL]
