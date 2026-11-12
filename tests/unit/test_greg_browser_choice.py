"""Which browser browser.render runs, and what its manifest and the office say about it.

In a Linux container on #196's 8d205324 the full Chrome for Testing 153 build never returned from a one-shot headless
render while the headless shell installed beside it rendered at once; the real-browser tests in test_greg_browser.py
skipped at the 45 second limit. The repair kept here is the smallest one measured against #293's render check
(docs/evidence/greg-browser-binary/2026-11-12-smallest): headless shells first; the manifest names no binary, so the
separate appraiser derives the same manifest digest as the body whatever GREG_CHROMIUM says; GREG_CHROMIUM naming no
executable file is refused by name; no installed browser, and an installed one the system cannot start, are
refusals rather than unknown outcomes. The review of #311 added: a path GREG cannot look at is refused like any other,
never an OSError; a render past its limit, and no bubblewrap behind the relay, are the host's (``transient``); a
helper of a killed browser that keeps writing the profile never turns the timeout into an unknown outcome.

Every test here runs stand-in executables (shell scripts that log each run and print a page). No real browser and no
network is used; tests/unit/test_greg_browser.py drives the real one.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from greg import capabilities, worker_isolation
from greg.authority import AuthorityOffice
from greg.capabilities import BUILTINS, CapabilityError, InvocationContext, browser_render
from tests.greg_fixtures import mission

PAGE = "<html><head><title>stand-in</title></head><body><p>hello page</p></body></html>"
URL = "http://127.0.0.1:9/x"
TOO_LONG = "/" + "a" * 300              # one name longer than NAME_MAX: looking at it raises ENAMETOOLONG
TIMED_OUT = "^browser did not finish rendering within 45 seconds$"


def refused_by_name(value: str) -> str:
    return (f"GREG_CHROMIUM is set to {value!r}, which is not the absolute path of an executable file; GREG runs "
            "the browser that variable names or none (unset it to let GREG choose among the installed browsers)")


def stand_in(path: Path) -> str:
    """An executable that logs its arguments and prints a page."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\nprintf '%s\\n' \"$*\" >> '{path}.runs'\necho '{PAGE}'\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path)


def runs(binary: str) -> list[str]:
    log = Path(binary + ".runs")
    return log.read_text().splitlines() if log.exists() else []


@pytest.fixture
def machine(tmp_path, monkeypatch):
    """A machine with no browser at all: each test installs the stand-ins it needs."""
    monkeypatch.delenv("GREG_CHROMIUM", raising=False)
    monkeypatch.setattr(capabilities, "PLAYWRIGHT_BROWSERS", str(tmp_path / "pw"))
    monkeypatch.setattr(capabilities, "CHROME_CANDIDATES", (str(tmp_path / "sys" / "google-chrome"),
                                                           str(tmp_path / "sys" / "chromium")))
    monkeypatch.setattr(capabilities, "HEADLESS_SHELL_CANDIDATES", (str(tmp_path / "sys" / "chrome-headless-shell"),))
    return tmp_path


def context(tmp_path, egress=None) -> InvocationContext:
    return InvocationContext(workspace=tmp_path, read_roots=(), secrets=None, manifest=BUILTINS["browser.render"][0],
                             egress=egress)


@pytest.fixture
def one_second_limit(monkeypatch, tmp_path):
    """browser.render's 45 second limit, cut to one second for stand-ins that never return; its profiles under
    tmp_path. The product's own limit is unchanged, so its refusal still names 45 seconds."""
    run = subprocess.run
    monkeypatch.setattr(capabilities.subprocess, "run",
                        lambda *a, timeout=None, **k: run(*a, timeout=1 if timeout == 45 else timeout, **k))
    (tmp_path / "tmp").mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "tmp"))


def test_headless_shells_come_first_then_installed_browsers_then_full_builds_of_either_layout(machine, tmp_path):
    """The order the four-line reorder set: Playwright's headless shell, the system headless shell, an installed
    Chrome or Chromium, Playwright's full builds under chrome-linux64 or the older chrome-linux. Nothing is run."""
    full_new = stand_in(machine / "pw" / "chromium-1243" / "chrome-linux64" / "chrome")
    full_old = stand_in(machine / "pw" / "chromium-900" / "chrome-linux" / "chrome")
    system = stand_in(machine / "sys" / "google-chrome")
    system_shell = stand_in(machine / "sys" / "chrome-headless-shell")
    shell = stand_in(machine / "pw" / "chromium_headless_shell-1243" / "chrome-headless-shell-linux64"
                     / "chrome-headless-shell")
    assert capabilities.chrome_candidates() == [shell, system_shell, system, full_new, full_old]
    assert capabilities.chrome_binary() == shell
    assert not any(runs(b) for b in (shell, system_shell, system, full_new, full_old))
    out = browser_render({"url": URL}, context(tmp_path))
    assert out["browser"] == "chrome-headless-shell" and "hello page" in out["text"]
    assert len(runs(shell)) == 1 and not any(runs(b) for b in (system_shell, system, full_new, full_old))


def test_a_directory_or_a_file_that_is_not_executable_is_not_installed(machine):
    (machine / "sys" / "google-chrome").mkdir(parents=True)             # a directory is "executable" to os.access
    (machine / "sys" / "chromium").write_text("#!/bin/sh\necho not marked executable\n")
    assert capabilities.chrome_candidates() == []
    real = stand_in(machine / "sys" / "chrome-headless-shell")
    assert capabilities.chrome_candidates() == [real]


def test_the_founders_choice_is_the_only_candidate(machine, monkeypatch, tmp_path):
    chosen, other = stand_in(machine / "chosen" / "my-chrome"), stand_in(machine / "sys" / "google-chrome")
    monkeypatch.setenv("GREG_CHROMIUM", chosen)
    assert capabilities.chrome_candidates() == [chosen]
    assert browser_render({"url": URL}, context(tmp_path))["browser"] == "my-chrome" and not runs(other)
    monkeypatch.setenv("GREG_CHROMIUM", "")                              # empty reads as unset: GREG chooses
    assert capabilities.chrome_binary() == other


@pytest.mark.parametrize("kind", ["a directory", "a file that is not executable", "a path with nothing at it",
                                  "an unexpanded home directory",
                                  "a relative path that resolves from the working directory",
                                  "a working path with a newline after it"])
def test_a_choice_that_names_no_browser_is_refused_by_name_and_nothing_else_is_run(machine, monkeypatch, tmp_path,
                                                                                    kind):
    """Before: the variable was passed over without a word and the first other installed browser ran in its place."""
    other = stand_in(machine / "sys" / "google-chrome")
    working = stand_in(machine / "chosen" / "my-chrome")
    (machine / "chosen" / "adir").mkdir()
    (machine / "chosen" / "notes.txt").write_text("not a program\n")
    monkeypatch.chdir(machine)
    value = {"a directory": str(machine / "chosen" / "adir"),
             "a file that is not executable": str(machine / "chosen" / "notes.txt"),
             "a path with nothing at it": str(machine / "chosen" / "not-installed"),
             "an unexpanded home directory": "~/my-chrome",
             "a relative path that resolves from the working directory": "chosen/my-chrome",
             "a working path with a newline after it": working + "\n"}[kind]
    monkeypatch.setenv("GREG_CHROMIUM", value)
    said = refused_by_name(value)
    for refuses in (capabilities.chrome_candidates, capabilities.chrome_binary,
                    lambda: browser_render({"url": URL}, context(tmp_path))):
        with pytest.raises(CapabilityError) as refused:
            refuses()
        assert str(refused.value) == said
    assert BUILTINS["browser.render"][0].available() == (False, said)      # the office answers UNAVAILABLE with it
    assert not runs(other) and not runs(working)


def test_a_choice_or_a_candidate_too_long_to_look_at_is_refused_or_passed_over_never_an_oserror(machine, monkeypatch,
                                                                                               tmp_path):
    """Before (Python 3.13's Path.is_file): OSError [Errno 36] out of chrome_candidates, chrome_binary, available()
    and the office's precheck, and out of a running body's tick."""
    other = stand_in(machine / "sys" / "google-chrome")
    (machine / "sys" / "chromium").symlink_to(TOO_LONG)                 # an installed name GREG cannot look at
    assert capabilities.chrome_candidates() == [other]
    monkeypatch.setenv("GREG_CHROMIUM", TOO_LONG)
    said, manifest = refused_by_name(TOO_LONG), BUILTINS["browser.render"][0]
    for refuses in (capabilities.chrome_candidates, capabilities.chrome_binary,
                    lambda: browser_render({"url": URL}, context(tmp_path))):
        with pytest.raises(CapabilityError) as refused:
            refuses()
        assert str(refused.value) == said
    assert manifest.available() == (False, said)
    assert AuthorityOffice.precheck(manifest, target="web:127.0.0.1", params={"url": URL}) == ("UNAVAILABLE", said)
    assert not runs(other)


LOOK = f"""
import json
from greg.authority import AuthorityOffice
from greg.capabilities import BUILTINS, CapabilityError, chrome_binary
manifest = BUILTINS["browser.render"][0]
try:
    binary = chrome_binary()
except CapabilityError as exc:
    binary = "refused: " + str(exc)
print(json.dumps({{"binary": binary, "available": manifest.available(),
                  "precheck": AuthorityOffice.precheck(manifest, target="web:127.0.0.1", params={{"url": "{URL}"}})}}))
"""


def child_env(**extra) -> dict:
    return {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1", **extra,
            "PYTHONPATH": os.pathsep.join([str(Path(capabilities.__file__).resolve().parents[1]),
                                           *(p for p in sys.path if "-packages" in p)])}


def test_a_choice_in_a_directory_the_body_cannot_search_is_refused_by_name(tmp_path):
    """Before: PermissionError [Errno 13] out of chrome_binary, available() and the precheck. A body that is not root
    cannot search the directory; as root the child gives up the two capabilities that would let it."""
    locked = tmp_path / "locked"
    chosen = stand_in(locked / "my-chrome")
    argv = [sys.executable, "-c", LOOK]
    if os.geteuid() == 0:
        argv = ["setpriv", "--inh-caps=-all", "--bounding-set=-dac_override,-dac_read_search", *argv]
    locked.chmod(0)
    try:
        ran = subprocess.run(argv, env=child_env(GREG_CHROMIUM=chosen), capture_output=True, text=True, timeout=60)
    finally:
        locked.chmod(0o755)
    assert ran.returncode == 0, ran.stderr[-2000:]
    said = refused_by_name(chosen)
    assert json.loads(ran.stdout) == {"binary": "refused: " + said, "available": [False, said],
                                      "precheck": ["UNAVAILABLE", said]}
    assert not runs(chosen)


def test_no_installed_browser_is_unavailable_at_the_office_and_a_refusal_from_the_adapter(machine, tmp_path):
    """Before: the precheck named a macOS path, and the adapter ran that path and raised FileNotFoundError, which the
    Gate records as an unknown outcome."""
    manifest, _ = BUILTINS["browser.render"]
    assert capabilities.chrome_candidates() == []
    assert manifest.available() == (False, "no Chrome or Chromium is installed on this body")
    for route in (None, object()):                                       # unconfined, and behind the relay
        with pytest.raises(CapabilityError, match="^no Chrome or Chromium is installed on this body$"):
            browser_render({"url": URL}, context(tmp_path, egress=route))


def test_an_installed_browser_the_system_cannot_start_is_a_refusal(machine, monkeypatch, tmp_path):
    """Before: subprocess.run raised FileNotFoundError, which the Gate records as an unknown outcome."""
    broken = machine / "chosen" / "my-chrome"
    broken.parent.mkdir(parents=True)
    broken.write_text("#!/nonexistent/interpreter\n")
    broken.chmod(0o755)
    monkeypatch.setenv("GREG_CHROMIUM", str(broken))
    with pytest.raises(CapabilityError, match=r"^browser could not be started \(No such file or directory\)$"):
        browser_render({"url": URL}, context(tmp_path))


def never_returns(path: Path, helper: str = "") -> str:
    """A browser that never finishes. ``helper``: a shell loop it first starts in the background (its pid written to
    <path>.helper), as a browser's helper that killing the browser does not end."""
    path.parent.mkdir(parents=True, exist_ok=True)
    started = f"sh -c '{helper}' </dev/null >/dev/null 2>&1 &\necho $! > '{path}.helper'\n" if helper else ""
    path.write_text(f"#!/bin/sh\n{started}exec sleep 30\n")
    path.chmod(0o755)
    return str(path)


def test_a_render_past_its_limit_is_the_hosts_timeout_not_a_measured_failure(machine, monkeypatch, tmp_path,
                                                                             one_second_limit):
    """Before: untyped, so the retained record could not tell a timeout from a missing browser (R11, R15)."""
    monkeypatch.setenv("GREG_CHROMIUM", never_returns(machine / "chosen" / "my-chrome"))
    with pytest.raises(CapabilityError, match=TIMED_OUT) as refused:
        browser_render({"url": URL}, context(tmp_path))
    assert refused.value.failure_class == "transient"


def test_behind_the_relay_no_namespaces_is_the_hosts_refusal_and_nothing_runs(machine, monkeypatch, tmp_path):
    """Before: untyped. Isolation this host cannot provide is ``transient``, as run_isolated types it."""
    def unavailable(**_):
        raise worker_isolation.WorkerIsolationError("worker OS filesystem isolation unavailable: bubblewrap is "
                                                    "unavailable on this host")
    monkeypatch.setattr(worker_isolation, "_backend", unavailable)
    browser = stand_in(machine / "sys" / "google-chrome")
    with pytest.raises(CapabilityError, match="^confined egress needs bubblewrap network namespaces here: ") as refused:
        browser_render({"url": URL}, context(tmp_path, egress=object()))
    assert refused.value.failure_class == "transient" and not runs(browser)


WRITES_ITS_PROFILE = 'i=0; while [ -d "$HOME" ] && [ $i -lt 400000 ]; do : > "$HOME/f$i"; i=$((i+1)); done'


def test_a_timeout_stays_a_refusal_while_a_helper_of_the_killed_browser_keeps_writing_its_profile(
        machine, monkeypatch, tmp_path, one_second_limit):
    """Before: the limit killed the browser alone, its helper kept writing the profile, removing the profile raised
    OSError (Directory not empty), and that error replaced the timeout: the Gate records an unknown outcome. GREG
    does not end the helper, and the profile it writes may stay; this test ends the helper itself."""
    browser = never_returns(machine / "chosen" / "my-chrome", helper=WRITES_ITS_PROFILE)
    monkeypatch.setenv("GREG_CHROMIUM", browser)
    pidfile = Path(browser + ".helper")
    try:
        with pytest.raises(CapabilityError, match=TIMED_OUT) as refused:
            browser_render({"url": URL}, context(tmp_path))
        os.kill(int(pidfile.read_text()), 0)          # the helper outlived the browser: the condition was exercised
    finally:
        if pidfile.exists():
            try:
                os.kill(int(pidfile.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass
    assert refused.value.failure_class == "transient"


def test_the_manifest_names_no_binary_and_says_what_is_installed_each_time_it_is_asked(machine, monkeypatch):
    """Before: the manifest named the browser found at import, so a build replaced under a running body made
    browser.render UNAVAILABLE with a working browser installed, and the manifest digest followed GREG_CHROMIUM."""
    manifest, _ = BUILTINS["browser.render"]
    digest = manifest.digest()
    assert manifest.binaries == () and not manifest.validate()
    assert manifest.available() == (False, "no Chrome or Chromium is installed on this body")
    old = stand_in(machine / "pw" / "chromium_headless_shell-1300" / "chrome-headless-shell-linux64"
                   / "chrome-headless-shell")
    assert manifest.available() == (True, "available")
    shutil.rmtree(Path(old).parents[1])                                  # the upgrade: build 1300 goes, 1301 arrives
    assert manifest.available() == (False, "no Chrome or Chromium is installed on this body")
    new = stand_in(machine / "pw" / "chromium_headless_shell-1301" / "chrome-headless-shell-linux64"
                   / "chrome-headless-shell")
    assert manifest.available() == (True, "available") and capabilities.chrome_binary() == new
    monkeypatch.setenv("GREG_CHROMIUM", new)
    assert manifest.digest() == digest


BODY_WITH_A_CHOSEN_BROWSER = """
import json, sys
from pathlib import Path
from greg.body import Body, status
from tests.greg_fixtures import Clock, drop, make_body, signed
home, key, body_id, _ = make_body(Path(sys.argv[1]))
drop(home, signed(key, body_id, "MISSION", json.loads(sys.argv[2])))
clock = Clock()
with Body(home, clock=clock) as body:
    for _ in range(4):
        body.tick()
        clock.advance(1)
    seen = {kind: [e.payload.get("verdict", True) for e in body.journal.replay("mission." + kind)]
            for kind in ("achieved", "appraised")}
    seen["observed"] = [e.payload["detail"] for e in body.journal.replay("mission.observed")]
seen["health"] = next(c["health"] for c in status(home)["capabilities"] if c["capability_id"] == "browser.render")
print(json.dumps(seen))
"""


def body_with(tmp_path, chosen: str) -> dict:
    """One founder-signed mission whose only check renders URL, run for four ticks by a real Body whose process has
    GREG_CHROMIUM set to ``chosen``; then browser.render's health as the founder's status shows it."""
    check = {"check_id": "c", "description": "the page shows its text",
             "sensor": {"capability": "browser.render", "params": {"url": URL}, "target": "web:127.0.0.1"},
             "predicate": {"op": "contains", "field": "text", "value": "hello page"}}
    spec = mission("m:chosen", checks=[check], strategies=[], capabilities=["browser.render"],
                   targets=("web:127.0.0.1",), ceiling="read_only")
    (tmp_path / "body-home").mkdir()
    ran = subprocess.run([sys.executable, "-c", BODY_WITH_A_CHOSEN_BROWSER, str(tmp_path / "body-home"),
                          json.dumps(spec)], env=child_env(GREG_CHROMIUM=chosen), capture_output=True, text=True,
                         timeout=120)
    assert ran.returncode == 0, ran.stderr[-2000:]
    return json.loads(ran.stdout.splitlines()[-1])


def test_a_closure_observed_with_the_founders_chosen_browser_is_verified_by_the_separate_appraiser(machine, tmp_path):
    """The body's process has GREG_CHROMIUM; greg/body.py starts the appraiser without it. Before: the two derived
    different manifest digests and the appraiser answered REFUTED ("receipt not bound to this closure and signed
    sensor") to a true closure. Measured with real browsers on 8d205324 plus the reorder alone, the same."""
    chosen = stand_in(machine / "chosen" / "my-chrome")
    seen = body_with(tmp_path, chosen)
    assert (seen["achieved"], seen["appraised"], seen["health"]) == ([True], ["VERIFIED"], "available")
    assert [line.rsplit(" ", 1)[-1] for line in runs(chosen)] == [URL]


def test_a_body_whose_chosen_browser_is_too_long_to_look_at_keeps_ticking_and_says_why(tmp_path):
    """Before: the OSError left Body.tick, so the body's process ended (every mission stopped, not only this one), and
    the founder's status raised the same OSError."""
    seen = body_with(tmp_path, TOO_LONG)
    said = refused_by_name(TOO_LONG)
    assert (seen["achieved"], seen["appraised"], seen["health"]) == ([], [], said)
    assert seen["observed"] and all(("sensor UNAVAILABLE: " + said).startswith(d) for d in seen["observed"])
