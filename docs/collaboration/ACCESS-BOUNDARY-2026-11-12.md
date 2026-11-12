# Access boundary of this session, as inspected on 2026-11-12 (16:20-16:30 UTC)

Founder, 2026-11-12: "Distinguish: Headless browser operation in your container. Cloud browser or desktop control,
if your environment exposes it. Control of my actual device. Founder-device installation and acceptance. Inspect
what is available and attempt the permitted local test before declaring the entire capability unavailable."

| Kind of access | Available here? | How it was checked | What it permits |
|---|---|---|---|
| Headless browser in the container | **Yes** | node Playwright with its pinned Chromium (`/opt/pw-browsers/chromium-1243`) loads; `/usr/bin/google-chrome` and `Xvfb` present. #293's browser suites with `GREG_REQUIRE_BROWSER=1` (a missing browser fails, never skips): 44 passed in 17.77 s | browser adapters, rendering, relay and namespace tests, replay, interruption tests |
| Python Playwright (`browser.session`, multi-step computer use, `greg/computer.py`) | **Yes, after setup** | absent from both session venvs and from Canonical CI, where `tests/unit/test_greg_computer.py` and Mission Control's browser tests are therefore skipped on every PR. A separate venv `scratchpad/venv-pw` with Python Playwright 1.63.0 (matching the installed browser) renders a page; on `8d205324`: `test_greg_computer.py` 8 passed (1 skipped without it); `test_greg_product_path.py` passes with `supervisord` on the PATH; `test_greg_mission_control.py` 2 failed, 6 passed | multi-step browser work here; the two Mission Control failures and running browser tests in CI are a unit in progress (`claude/browser-tests-run-in-ci-20261112`) |
| Cloud browser or desktop control (computer use, the desktop app's built-in browser) | No | no such tool is exposed to this session | — |
| The founder's computer (Remote Control folders) | No | `list_computer_folders`: no folder offered, none listed as unusable | — |
| Founder-device installation and acceptance (VEPMC, N1) | No | follows from the row above; also needs the founder's own key | stays at 0; nothing here moves it |
| Bubblewrap envelope | No (`bwrap` absent) | the intake mission recorded the `supervised` floor (Landlock ABI 7 and a seccomp network filter) | `required`-posture paths are exercised in CI, where jobs 1 and 10 install bubblewrap |
| GitHub | Yes, through the MCP tools for the repositories in scope; `gh` for search only | used throughout | draft PRs, comments, check runs |
| Solver packages | In `scratchpad/venv-mind` only (networkx, scipy, z3, ortools; no httpx) | import | cognition tests; one routing-integrity file skips there |

What the absent device still leaves buildable here: local test applications, browser adapters, packaging,
installation rehearsals (`greg rehearse`), scoped credential handling with test keys, replay and interruption
tests. What it blocks: any claim of founder-device behaviour, persistence across the founder's reboots, and N1.
