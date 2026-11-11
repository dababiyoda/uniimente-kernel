"""Each safeguard of browser.render's binary choice must fail a behavioural test when removed.

    python scripts/ci/check_browser_binary_mutants.py

A mutant counts as caught only when tests/unit/test_greg_browser_binary.py reports a FAILED test (an import or
collection error does not count). The tests run stand-in executables, so the gate needs no browser and no network.
A scratch copy is mutated; the live source never is. Exit 1 on any survivor or stale anchor.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mutation_harness import ROOT, run  # noqa: E402

TESTS = "tests/unit/test_greg_browser_binary.py"
C = "greg/capabilities.py"

ORDER = ("    for candidate in (*playwright_builds(HEADLESS_SHELLS), *HEADLESS_SHELL_CANDIDATES, *CHROME_CANDIDATES,\n"
         "                      *playwright_builds(FULL_BROWSERS)):")
IS_A_FILE = "    return bool(path) and Path(path).is_file() and os.access(path, os.X_OK)"
NUMBERED = "        return int(number) if number.isascii() and number.isdigit() else -1"
A_CHOICE = "        if not (os.path.isabs(chosen) and _executable(chosen)):"
REFUSED_CHOICE = (A_CHOICE + """
            raise CapabilityError(f"GREG_CHROMIUM is set to {chosen!r}, which is not the absolute path of an "
                                  "executable file; GREG runs the browser that variable names or none (unset it "
                                  "to let GREG choose among the installed browsers)")
        return [chosen]
""")
BUILD = "    return (made.st_size, made.st_mtime_ns, made.st_ctime_ns)"
KEPT = "            judged[2] is None or time.monotonic() - judged[1] < RENDER_RETRY_SECONDS):"
RENDERED = "            why = None if proc.returncode == 0 and RENDER_CHECK_TEXT.encode() in proc.stdout else ("
OFFLINE = ('        argv = [*_headless(binary, profile), "--host-resolver-rules=MAP * ~NOTFOUND",\n'
           '                "--proxy-server=http://127.0.0.1:9", "--virtual-time-budget=1000", "--dump-dom", RENDER_CHECK_PAGE]')
CHECK_ENV = '                                  env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": profile})'
CHECK_SANDBOX = ('        if not _sandboxes_itself():\n            argv.insert(1, "--no-sandbox")\n        try:\n'
                 '            proc = subprocess.run(argv, capture_output=True, timeout=RENDER_SECONDS, cwd=profile,')
ROUTE = "    binary = chrome_binary() if ctx.egress is None else installed_chrome()"
SANDBOXED = "        sandboxed = _sandboxes_itself() and ctx.egress is None"
RENDER_RUN = "timeout=RENDER_SECONDS, env=env, cwd=profile)"
BOUNDED = "        if _must_run_to_judge(candidate) and time.monotonic() - started >= JUDGING_SECONDS:"
ASKED_NOW = '        return asked_now() if asked_now is not None else (True, "available")'
DECLARED = ('                                network="target-host-only", data_classes=("public_web",), retry_safe=True,\n'
            "                                # no ``binaries``")

MUTANTS = [
    # which installed browsers, in which order
    (C, "the headless shells are tried before the full browsers", ORDER,
     "    for candidate in (*CHROME_CANDIDATES, *playwright_builds(FULL_BROWSERS), *playwright_builds(HEADLESS_SHELLS),\n"
     "                      *HEADLESS_SHELL_CANDIDATES):"),
    (C, "the newest build is the one with the highest build number, not the last as text",
     "key=build, reverse=True)", "reverse=True)"),
    (C, "a build directory without a number is listed after every numbered build", NUMBERED,
     "        return int(number) if number.isascii() and number.isdigit() else 10 ** 9"),
    (C, "a directory name ending in a digit int() refuses does not raise", NUMBERED,
     "        return int(number) if number.isdigit() else -1"),
    (C, "the full browser is found under either spelling of its OS directory",
     'FULL_BROWSERS = "chromium-*/chrome-linux*/chrome"', 'FULL_BROWSERS = "chromium-*/chrome-linux/chrome"'),
    (C, "the headless shell is found where Playwright installs it",
     'HEADLESS_SHELLS = "chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell"',
     'HEADLESS_SHELLS = "chromium-*/chrome-headless-shell-*/chrome-headless-shell"'),
    (C, "a candidate that is not installed is not listed",
     "        if _executable(candidate) and candidate not in found:", "        if candidate not in found:"),
    (C, "a directory is not an installed browser", IS_A_FILE, "    return bool(path) and os.access(path, os.X_OK)"),
    (C, "a file that is not executable is not an installed browser", IS_A_FILE,
     "    return bool(path) and Path(path).is_file()"),
    # the founder's choice
    (C, "the founder's chosen browser is the only candidate",
     "        return [chosen]\n    found: list[str] = []", "    found: list[str] = [chosen] if chosen else []"),
    (C, "a choice that does not name an executable file is refused, not passed over for another browser", REFUSED_CHOICE,
     "        if os.path.isabs(chosen) and _executable(chosen):\n            return [chosen]\n"),
    (C, "a choice that is not an absolute path is refused", A_CHOICE, "        if not _executable(chosen):"),
    (C, "a refused choice makes the capability unavailable with that reason",
     "    except CapabilityError as exc:\n        return False, str(exc)",
     '    except CapabilityError as exc:\n        return True, "available"'),
    # an installed browser is used only once it has rendered
    (C, "a candidate is used only after it rendered the local page",
     "        why = cannot_render(candidate)\n        if why is None:", "        why = None\n        if why is None:"),
    (C, "an unconfined render runs the browser that passed, not the first one installed", ROUTE,
     "    binary = installed_chrome()"),
    (C, "exiting 0 is not rendering: the page's text must have been written", RENDERED,
     "            why = None if proc.returncode == 0 else ("),
    (C, "writing the text and then failing is not rendering", RENDERED,
     "            why = None if RENDER_CHECK_TEXT.encode() in proc.stdout else ("),
    (C, "a browser that never returns is a reason, not an exception",
     "        except subprocess.TimeoutExpired:\n            why = f\"did not finish rendering a local page",
     "        except ZeroDivisionError:\n            why = f\"did not finish rendering a local page"),
    (C, "a browser that cannot be started is a reason, not an exception",
     "        except OSError as exc:\n            why = f\"could not be started", "        except ZeroDivisionError as exc:\n            why = f\"could not be started"),
    (C, "a candidate that vanished before it was judged is a reason, not an exception",
     '        return f"cannot be read ({exc.strerror})"', "        raise"),
    (C, "no installed browser is a refusal that says so (unconfined)",
     "    if not candidates:\n        raise CapabilityError(NO_BROWSER)\n", ""),
    (C, "no installed browser is a refusal that says so (behind the relay)",
     "    if not found:\n        raise CapabilityError(NO_BROWSER)\n", ""),
    # what is remembered about a binary
    (C, "a browser that could not render is not run again on every call", KEPT, "            judged[2] is None):"),
    (C, "a browser that could not render is judged again after the retry time", KEPT, "            True):"),
    (C, "a browser that rendered is not judged again when the retry time passes", KEPT,
     "            time.monotonic() - judged[1] < RENDER_RETRY_SECONDS):"),
    (C, "a failure is remembered with the time it was judged",
     "    _render_judged[binary] = (build, time.monotonic(), why)",
     "    _render_judged[binary] = (build, time.monotonic() + 10 ** 9, why)"),
    (C, "a replaced binary at the same path is judged again",
     "    if judged is not None and judged[0] == build and (", "    if judged is not None and ("),
    (C, "a build's size is part of which build it is", BUILD, "    return (made.st_mtime_ns, made.st_ctime_ns)"),
    (C, "a build's modification time is part of which build it is", BUILD,
     "    return (made.st_size, made.st_ctime_ns)"),
    (C, "a build's change time is part of which build it is (same size, modification time put back)", BUILD,
     "    return (made.st_size, made.st_mtime_ns)"),
    (C, "a success is forgotten when a render with that binary never returns",
     "            _render_judged.pop(binary, None)\n            raise CapabilityError(f\"browser did not finish",
     "            raise CapabilityError(f\"browser did not finish"),
    (C, "a success is forgotten when the binary can no longer be started",
     "                    _render_judged.pop(binary, None)        # it passed its check and is gone or broken now\n", ""),
    (C, "a browser that can no longer be started is a refusal, not an exception",
     "                except OSError as exc:\n                    _render_judged.pop",
     "                except ZeroDivisionError as exc:\n                    _render_judged.pop"),
    # one call judges for a bounded time
    (C, "no check starts once a call has judged for JUDGING_SECONDS", BOUNDED, "        if False:"),
    (C, "a candidate already known to render is used however long the others took", BOUNDED,
     "        if time.monotonic() - started >= JUDGING_SECONDS:"),
    (C, "a candidate that was not judged is named in the refusal",
     '            + ", ".join(waiting) if waiting else ""))', '            + ", ".join(waiting) if False else ""))'),
    (C, "the limits keep the longest call under the stale-heartbeat rule", "JUDGING_SECONDS = 60.0",
     "JUDGING_SECONDS = 600.0"),
    # the check itself contacts no one and runs as a render runs
    (C, "in the check every name resolves to nothing", OFFLINE,
     '        argv = [*_headless(binary, profile),\n'
     '                "--proxy-server=http://127.0.0.1:9", "--virtual-time-budget=1000", "--dump-dom", RENDER_CHECK_PAGE]'),
    (C, "in the check every request goes to a closed port", OFFLINE,
     '        argv = [*_headless(binary, profile), "--host-resolver-rules=MAP * ~NOTFOUND",\n'
     '                "--virtual-time-budget=1000", "--dump-dom", RENDER_CHECK_PAGE]'),
    (C, "the check's page has no address",
     'RENDER_CHECK_PAGE = "data:text/html," + urllib.parse.quote(', 'RENDER_CHECK_PAGE = "http://127.0.0.1:9/?" + urllib.parse.quote('),
    (C, "the check's page computes its text, so the address alone does not contain it",
     """'<script>document.getElementById("out").textContent = "greg-renders-" + (20 + 22)</script>')""",
     """'<script>document.getElementById("out").textContent = "greg-renders-42"</script>')"""),
    (C, "the check runs with the three variables a render is given", CHECK_ENV, "                                  env=None)"),
    (C, "the check runs in its own fresh directory, not the body's",
     "timeout=RENDER_SECONDS, cwd=profile,", "timeout=RENDER_SECONDS,"),
    (C, "the check follows the unconfined render's sandbox rule", CHECK_SANDBOX,
     "        try:\n            proc = subprocess.run(argv, capture_output=True, timeout=RENDER_SECONDS, cwd=profile,"),
    (C, "as root on Linux the browser is told it cannot sandbox itself",
     '    return not (sys.platform.startswith("linux") and os.geteuid() == 0)', "    return True"),
    (C, "every headless run keeps the browser's background networking off",
     '"--disable-extensions", "--disable-background-networking", "--disable-sync",',
     '"--disable-extensions", "--enable-logging", "--disable-sync",'),
    (C, "failing to remove a profile never replaces the result",
     "            shutil.rmtree(self.path, ignore_errors=True)", "            shutil.rmtree(self.path)"),
    (C, "removing a profile is tried again when helper processes were still writing",
     "PROFILE_REMOVALS = 5", "PROFILE_REMOVALS = 1"),
    # the render itself
    (C, "a render under its own sandbox says so", SANDBOXED, "        sandboxed = ctx.egress is None"),
    (C, "a render (not the check) that never returns ends at RENDER_SECONDS", RENDER_RUN,
     "timeout=RENDER_SECONDS * 10000, env=env, cwd=profile)"),
    (C, "a render that ran out of time is a refusal naming the limit",
     '            raise CapabilityError(f"browser did not finish rendering within {RENDER_SECONDS} seconds") from exc',
     "            raise"),
    (C, "a render runs in its own fresh directory, not the body's", RENDER_RUN, "timeout=RENDER_SECONDS, env=env)"),
    # a confined-egress body: nothing is judged outside the namespace
    (C, "behind the relay no browser is started outside the namespace", ROUTE, "    binary = chrome_binary()"),
    (C, "a confined render is not held to the unconfined sandbox rule", SANDBOXED,
     "        sandboxed = _sandboxes_itself()"),
    # the manifest and the office's precheck
    (C, "the manifest names no binary, so it is the same in every process", DECLARED,
     '                                network="target-host-only", data_classes=("public_web",), retry_safe=True,\n'
     "                                binaries=tuple(chrome_candidates()[:1]),\n"
     "                                # no ``binaries``"),
    (C, "browser.render's availability is what is installed when it is asked",
     'AVAILABLE_AT_CALL_TIME["browser.render"] = browser_installed\n', ""),
    (C, "a manifest asks its call-time availability", ASKED_NOW, '        return True, "available"'),
    (C, "a body with no browser says browser.render is unavailable",
     '        return (True, "available") if chrome_candidates() else (False, NO_BROWSER)',
     '        return (True, "available") if chrome_candidates() is not None else (False, NO_BROWSER)'),
]

if __name__ == "__main__":
    raise SystemExit(run(MUTANTS, TESTS, prefix="greg-browser-binary-mutants-", root=ROOT))
