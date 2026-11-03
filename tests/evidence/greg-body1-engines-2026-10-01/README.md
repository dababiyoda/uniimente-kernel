# Body 1 carries the engines — evidence, 2026-10-01

Backcast node A (`docs/cortex/BACKCAST_GPS_FULL_MIND_2026-10-01.md`): before this change,
`greg/chromebook/install.sh` installed `requirements-dev.txt` only, so a clean Body 1 carried none
of the five reasoning engines and every certified family verified in the container was absent there.

## What was run (Linux x86_64 container, Python 3.11.15; not a Chromebook)

1. A fresh venv with `requirements-dev.txt`, then the installer's engine step verbatim:
   `pip install --quiet --only-binary=:all: -r requirements-cognition.txt` — exit 0 in 33 s.
2. `greg doctor` engine report in that venv: 5 of 5 present.

| Engine | Version | License (installed metadata) |
| --- | --- | --- |
| z3-solver | 5.1.0.0 | MIT License (license text; no SPDX expression) |
| ortools | 9.15.6755 | Apache Software License (trove classifier) |
| scipy | 1.17.1 | BSD License (trove classifier) |
| networkx | 3.6.1 | BSD-3-Clause |
| sympy | 1.14.0 | BSD License (trove classifier) |

3. In the same fresh venv: `pytest tests/unit/test_greg_open_source_genesis.py
   tests/unit/test_greg_linear_genesis.py tests/unit/test_greg_schedule_words.py
   tests/unit/test_greg_chromebook_doctor.py tests/unit/test_greg_chromebook_install.py` — 89 passed, 0 skipped.

## Not verified

- ChromeOS Linux, an ARM Chromebook, or Alfonso's machine: wheel availability there is unknown.
- Disk use on the Chromebook: about 550 MB installed, measured in the container.
- The step is best-effort by design: a missing wheel never blocks Body 1 (tested in the installer
  test); the doctor lists what is missing; `--no-engines` skips it.
