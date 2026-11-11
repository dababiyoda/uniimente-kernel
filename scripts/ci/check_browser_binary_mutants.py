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
K = "greg/computer.py"

ORDER = ("    for candidate in (*playwright_builds(HEADLESS_SHELLS), *HEADLESS_SHELL_CANDIDATES, *CHROME_CANDIDATES,\n"
         "                      *playwright_builds(FULL_BROWSERS)):")
CHOSEN = "    if _executable(chosen):\n        return [chosen]\n    found: list[str] = []"
KEPT = "    if judged is not None and (judged[1] is None or time.monotonic() - judged[0] < RENDER_RETRY_SECONDS):"
RENDERED = "            why = None if proc.returncode == 0 and RENDER_CHECK_TEXT.encode() in proc.stdout else ("
OFFLINE = ('        argv = [*_headless(binary, profile), "--host-resolver-rules=MAP * ~NOTFOUND",\n'
           '                "--proxy-server=http://127.0.0.1:9", "--virtual-time-budget=1000", "--dump-dom", RENDER_CHECK_PAGE]')
CHECK_ENV = '                                  env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": profile})'
CHECK_SANDBOX = ('        if not _sandboxes_itself():\n            argv.insert(1, "--no-sandbox")\n        try:\n'
                 '            proc = subprocess.run(argv, capture_output=True, timeout=RENDER_SECONDS, cwd=profile,')

MUTANTS = [
    # which installed browsers, in which order
    (C, "the headless shells are tried before the full browsers", ORDER,
     "    for candidate in (*CHROME_CANDIDATES, *playwright_builds(FULL_BROWSERS), *playwright_builds(HEADLESS_SHELLS),\n"
     "                      *HEADLESS_SHELL_CANDIDATES):"),
    (C, "the newest build is the one with the highest build number, not the last as text",
     "key=build, reverse=True)", "reverse=True)"),
    (C, "the full browser is found under either spelling of its OS directory",
     'FULL_BROWSERS = "chromium-*/chrome-linux*/chrome"', 'FULL_BROWSERS = "chromium-*/chrome-linux/chrome"'),
    (C, "the headless shell is found where Playwright installs it",
     'HEADLESS_SHELLS = "chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell"',
     'HEADLESS_SHELLS = "chromium-*/chrome-headless-shell-*/chrome-headless-shell"'),
    (C, "the founder's chosen browser is the only candidate", CHOSEN,
     "    found: list[str] = [chosen] if _executable(chosen) else []"),
    (C, "a candidate that is not installed is not listed",
     "        if _executable(candidate) and candidate not in found:", "        if candidate not in found:"),
    (K, "the session route drives the full browser, never the headless shell",
     "    for path in playwright_builds(FULL_BROWSERS) + [", "    for path in playwright_builds(HEADLESS_SHELLS) + ["),
    # an installed browser is used only once it has rendered
    (C, "a candidate is used only after it rendered the local page",
     "        why = cannot_render(candidate)\n        if why is None:", "        why = None\n        if why is None:"),
    (C, "the render runs the browser that passed, not the first one installed",
     '    binary = chrome_binary()\n    with tempfile.TemporaryDirectory(prefix="greg-browser-") as profile:',
     '    binary = installed_chrome()\n    with tempfile.TemporaryDirectory(prefix="greg-browser-") as profile:'),
    (C, "exiting 0 is not rendering: the page's text must have been written", RENDERED,
     "            why = None if proc.returncode == 0 else ("),
    (C, "writing the text and then failing is not rendering", RENDERED,
     "            why = None if RENDER_CHECK_TEXT.encode() in proc.stdout else ("),
    (C, "a browser that never returns is a reason, not an exception",
     "        except subprocess.TimeoutExpired:\n            why = f\"did not finish rendering a local page",
     "        except ZeroDivisionError:\n            why = f\"did not finish rendering a local page"),
    (C, "a browser that cannot be started is a reason, not an exception",
     "        except OSError as exc:\n            why = f\"could not be started", "        except ZeroDivisionError as exc:\n            why = f\"could not be started"),
    (C, "no installed browser is a refusal that says so",
     '    if not refused:\n        raise CapabilityError("no Chrome or Chromium is installed on this body")\n', ""),
    # what is remembered about a binary
    (C, "a browser that could not render is not run again on every call", KEPT,
     "    if judged is not None and judged[1] is None:"),
    (C, "a browser that could not render is judged again after the retry time", KEPT,
     "    if judged is not None:"),
    (C, "a browser that rendered is not judged again when the retry time passes", KEPT,
     "    if judged is not None and time.monotonic() - judged[0] < RENDER_RETRY_SECONDS:"),
    (C, "a replaced binary at the same path is judged again",
     "    key = (binary, made.st_size, made.st_mtime_ns)", "    key = (binary,)"),
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
    (C, "the check follows the render's sandbox rule", CHECK_SANDBOX,
     "        try:\n            proc = subprocess.run(argv, capture_output=True, timeout=RENDER_SECONDS, cwd=profile,"),
    (C, "a render under its own sandbox says so",
     "        sandboxed = _sandboxes_itself() and ctx.egress is None", "        sandboxed = ctx.egress is None"),
]

if __name__ == "__main__":
    raise SystemExit(run(MUTANTS, TESTS, prefix="greg-browser-binary-mutants-", root=ROOT))
