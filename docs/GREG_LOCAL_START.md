> **Superseded as founder instructions (2026-09-26, `PR113-TO-114-SUPERSESSION.md` residual 2).** This synthetic-authority loop does not authenticate Alfonso and is no longer a founder entry point. Use `greg/FIRST_MISSION.md` (onboarding and VEPMC runbook) and the founder-signed surfaces: `greg console`, the phone channel, the CLI. This page, `egregore/local_console.py` and its tests are kept as provenance and development evidence.

# GREG local development loop

One supported task: **bounded static integration audit of approved local snapshots of Kernel, DALEOBANKS and WMI**, followed by a source-backed morning brief. It is a foundation for the persistent founder-governed egregore destination, not a general assistant or a redefinition of that destination.

The runnable setup is **SYNTHETIC DEVELOPMENT ONLY**. It does not authenticate Alfonso. The loopback page's CSRF token is not identity. Reviews are labeled unverified local operator input. No production authentication mode is hidden behind a flag.

## Start

Requires Python 3.11+, Git and POSIX. Tested on Linux/Python 3.12. Uses `fork`, process groups, `resource` and `fcntl`; Windows is unsupported. Native macOS, launchd, Keychain, signing, installation and machine reboot are untested. No service is installed.

With the three clones alongside each other, run from Kernel:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m egregore.local_console --state ../greg-dev init-synthetic-development \
  --kernel "$PWD" --dale ../DALEOBANKS --wmi ../WealthMachineIntelligence \
  --expected-pin 4999acff1a69502c05af455fbccfca380cad18ee
.venv/bin/python -m egregore.local_console --state ../greg-dev serve
```

Open **http://127.0.0.1:8765**. Submit the approved snapshot audit, refresh for status, and inspect the expandable source evidence/history. Accept, reject or correct its result. Stop is terminal for this session: it prevents new dispatches/submissions, terminates owned in-flight work and retains evidence. There is no console resume command.

The worker is a separate finite process. HTTP-client closure and killing/restarting the entire UI server are tested. An actual browser-window test is not claimed: Chromium was unavailable and its attempted download failed. The tool execution workspace also reset during construction; current evidence was regenerated after reconstruction and published, rather than treating lost local commits as a deliverable.

The expected pin above is the boundary dependency present in the inspected consumers, not a claim that it is latest. Initialization records local `origin/main` refs and never fetches remote state. Mission capture reads exact Git blobs, not executable worktrees or hooks. Missing objects fail; lazy network fetch is disabled. State must live outside inspected repositories.

CLI controls:

```bash
.venv/bin/python -m egregore.local_console --state ../greg-dev submit
.venv/bin/python -m egregore.local_console --state ../greg-dev status
.venv/bin/python -m egregore.local_console --state ../greg-dev stop
```

`submit --budget 0` produces a visible budget wait without dispatch. Each mission admits at most three worker attempts, 20 seconds per worker within a 40-second due window, and zero model calls/external spend. Session limit: 20 missions. Waiting is bounded; there is no endless polling or budget replenishment.

## Recovery and review

A worker interrupted after a retained receipt reuses and independently appraises it. A dispatch claim without a receipt is uncertain and cannot be blindly retried. A hard-killed host reconstructs `HOST_ALREADY_CLAIMED` / `RUNNING_OR_INTERRUPTED`, with an explicit reconciliation action. Ordinary host failures become retained blockers. Audit success without a completed brief remains `VERIFIED_AUDIT_AWAITING_BRIEF`.

`worker --mission ID --budget N` re-enters the finite host using retained authority; N must match the original obligation. It never issues replacement authority or clears a stale claim. This is process-state reconstruction, not machine reboot recovery.

Stop is part of the exact granted job. Stop writes and dispatch admission serialize through canonical ledger writer exclusion. Admission releases its lock after the Gate retains a dispatch claim, so later stop explicitly handles in-flight work. Direct `run_once` cannot omit the bound stop check. The development processes share an OS user: **protection against arbitrary native code rewriting control files is not established**. Privilege-separated target installation remains a blocked acceptance test.

Review binds to the exact current head and retains result, evidence, correction and a bounded proposed presentation improvement. `compare --mission ID --cases FILE` compares a fixed security-first ordering against the unchanged baseline on separate supplied gold cases. Strict gain with all answers correct retains it; ties and regressions remain history. A later negative comparison withdraws the change. This changes presentation only, never policy, grants or stop behavior. The included labels are synthetic and author-supplied, not independent evidence of general intelligence or human benefit.

## Proof

```bash
python -m pytest tests/unit/test_greg_console.py tests/unit/test_greg_resume_authority.py tests/unit/test_greg_local_mission.py tests/unit/test_morning_review.py tests/unit/test_egregore_runtime.py -q
python -m tests.greg_acceptance_driver --state ../fresh-acceptance --output acceptance.json
```

Actual-source tests expect sibling directories `../daleobanks` and `../wmi`; absence explicitly skips that dependency, never establishes acceptance. Retained ledgers and JUnit results are in `tests/evidence/greg-usable/`. DALEOBANKS has its own bounded feedback demonstration and receipts.

## Blocked acceptance and rollback

Real founder identity enrollment and protected key custody are absent. Authenticated Alfonso stop, OS-protected worker separation, native Mac installation, actual browser-window closure and machine reboot have not passed. Genuine founder review and independently evaluated learning remain outstanding. Nothing graduates from the founder-guided period.

Leave the draft unmerged, or use a separate checkout of Kernel base `04b1b7e3bce5fd8ea6fbaf978719249cae8ef90a`. Stop the session and UI first; retain the entire state directory and ledgers. There is no installed service to remove. Never delete uncertain claims to make recovery pass. Rollback of code does not mean deletion of evidence.
