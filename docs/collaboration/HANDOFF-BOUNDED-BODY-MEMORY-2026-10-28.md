# Handoff: bounded body memory and ARM Chromebook engines (2026-10-28)

Session `session_01Kucyfm6YBHMTjaiC1M9hqD`, a Claude Code cloud session. Claim: kernel #96, comment 6472033495.
Branch `claude/bounded-body-memory-arm-engines` on #196's head `190c58fb`; draft PR #211 into #196's branch.
The founder's directive asked for the 40-item report: this file is that report, kept short. The earlier
same-directive report is `HANDOFF-GREG-RECONCILIATION-2026-10-28.md`. It still holds for everything not changed
here; this file does not repeat it.

## 1. Source coverage

| Source | State | Notes |
|---|---|---|
| Kernel `main` `d64a6c93`; #196 head `190c58fb` (worktree) | inspected | doctrine files, `docs/founder-loop-entry-gate.json`, `EGREGORE_V1_INTEGRATION_PROGRAM.md`, `provenance/ledger.py`, `events/spine.py`, `policy/consequence_gate.py` (read only), `greg/doctor.py`, `greg/chromebook/install.sh`, `greg/CHROMEBOOK_FIRST_MISSION.md`, `greg/path.json` (nodes, horizons) |
| Kernel open PRs (#11–#208, 141 open) | titles, heads and dates listed; #196 read in full | not every PR body was read |
| Kernel issue #96 (newest 8 comments), Discussion #89 (REST API) | inspected | |
| `FINDING-LEDGER-APPEND-COST-2026-10-14.md`, `HANDOFF-GREG-RECONCILIATION-2026-10-28.md` | inspected | the measured limit taken up here |
| WealthMachineIntelligence and DALEOBANKS open PRs | titles and heads listed | code not read this session; organ pins unchanged |
| PyPI release files for `z3-solver` 4.15.4.0, 5.1.0.0, 5.3.2.0 and `ortools` 9.15.6755 | inspected (pypi.org JSON API) | binary-only resolution run for cp311 and cp313, aarch64 and x86-64, at glibc 2.36 and 2.41 |
| ChromeOS Linux default container version | unavailable | a web search did not confirm whether Debian 13 is now the default; Debian 12 assumed |
| Project conversations and ChatGPT project files | unavailable | not accessible from this session |

## 2–4. Founder intent, corrections and capability horizon

- **Unchanged since the earlier report.**
  - BODY + ORGANS + MIND is the completion boundary.
  - Destination effects are kept on all 40 `greg/path.json` horizons.
  - Founder corrections reroute; they do not delete.
- **Intent advanced here:**
  - `persistent_goal_pursuit` (N1): a body that keeps working while the founder is away;
  - INTENT-GREG-EMBODIED-2026-09-11, INTENT-2026-09-22-FIRST-BODY;
  - founder decision 5 of the earlier handoff (ledger memory bounding), prepared, not decided.
- **No horizon added, removed or reclassified.**

## 5–9. Reality, destination, node, gate, metric

- **Current reality:** INTEGRATION-TESTED and SANDBOX. Nothing is founder-used or on the Chromebook.
- **Active node:** N1. **Gate:** the founder's Chromebook run of `greg/CHROMEBOOK_FIRST_MISSION.md`.
- **Single bottleneck metric:** VEPMC, **0**, unchanged.
- **Kept behind N1:** a body that survives weeks of operation.
  - This session removed most of the memory growth that would have ended it.
  - It also removed one silent failure on ARM Chromebooks: no engines at all.

## 10. Intent conflict matrix (new items only)

| Conflict | Resolution |
|---|---|
| The earlier finding called all memory options "evidence-plane decisions" | Option 1 changes no written byte, so it is built as a draft. Adoption stays the founder's (deliberation: NEEDS_FOUNDER_DECISION) |
| Runbook: "bubblewrap optional, only coding workers need it" vs the installer turning on confined egress whenever bubblewrap is present | Runbook corrected: without it the body's network runs unconfined |
| Runbook: "every compiled dependency has ARM64 wheels" vs the Z3 5.1.0.0 pin | Corrected. The installer installs engine by engine, and the doctor states why one is missing |

## 11–13. Repository roles, ownership, PR metabolism

- Roles and ownership are unchanged.
- **Canonical owner for retention of ledger records:** `provenance/ledger.py`. The spine reads through it and no
  longer holds payloads.
- **This branch:** STACKED NEXT on #196. It does not touch #196's claimed interfaces or the SR-002 Gate bytes.
- No other PR's disposition was changed.
- The earlier report's open item still stands: place #197–#208 on `greg/path.json`. It belongs to the #196
  integrator.

## 14–19. Superseded assumptions, preserved effects, mechanisms

| Item | Detail |
|---|---|
| Superseded implementation assumption | "Every retained payload is held in memory". It is replaced, for file-backed ledgers, by a window of 1,024 plus byte-checked reads. The effect (complete, verifiable, readable history) is preserved |
| Ported mechanism | Option 1 of `FINDING-LEDGER-APPEND-COST-2026-10-14` |
| Recombined mechanisms | Content addressing (SHA-256 of exact line bytes) + the existing incremental/whole reconstruction schedule + a running hash chain over skeletons. Together they let the commit path stay whole-chain without touching disk; none of them does that alone |
| Retained alternatives | In-memory ledger (no path) keeps everything. The window is a constructor parameter |
| Historical evidence | The first version's 2× slowdown, its fail-open, and the reviewer's five breaks (all in `FINDING-BODY-MEMORY-2026-10-28.md`) |

## 20–30. Status by area (changes only)

| Area | Change in this session | Reality |
|---|---|---|
| Body / runtime | Memory per retained record 2,639 → 1,390 B resident; heap 2,287 → 807 B (final head `e3c6e723`; 1,458 and 833 on `45d65a30`) | sandbox measured |
| Body / runtime | Run 361 s → 279 s for 1,800 ticks on the final head (334 → 223 on `45d65a30`; concurrent runs; indicative) | sandbox measured |
| Body / runtime | Ledger file tampering detected while running | unit-tested |
| Zero trust / evidence | Explicit `verify_chain()` re-derives every dropped record from the file. Commit path: running digest. Replaced files and changed bytes stop appends | unit-tested; independently attacked |
| Install / doctor | One pip call per engine. `why_missing` and `platform.glibc` in the doctor | unit-tested; real installer run end to end on x86-64 Ubuntu (5 of 5 engines, body, key, designation) |
| Install / doctor | ARM64 Debian 12 behaviour | derived from PyPI tags only |
| Infinite Goal Chase, computer use, Capability Genesis, AI workforce, SOP, human work, business runtime, economic/compute | unchanged | see the earlier report |

## 31. Exact code changes

`provenance/ledger.py`, `events/spine.py`, `greg/chromebook/install.sh`, `greg/doctor.py`,
`greg/CHROMEBOOK_FIRST_MISSION.md`, `scripts/measure_body_memory.py` (new), `scripts/ci/check_cortex_mutants.py`
(one stale mutant repaired, eight ledger mutants added),
`tests/unit/test_ledger_dropped_payloads.py` (new, 35 tests), `tests/unit/test_greg_chromebook_install.py` (+2),
`docs/collaboration/FINDING-BODY-MEMORY-2026-10-28.md`, `docs/collaboration/deliberation-bounded-body-memory-20261028.json`,
`docs/evidence/body-memory-2026-10-28/`, this file.

## 32–33. Tests and CI

On the final code (`e3c6e723`), locally with Python 3.11, `-n 3`:

- `tests/unit`: 7,255 passed, 109 skipped, 0 failed.
- `tests/integration`: 464 passed, 51 skipped, 0 failed. The skips need Playwright, bubblewrap or supervisord,
  none of which this container has.
- The ledger, provenance and installer files again after the last test edit: 94 passed.

Exact commands, the review and the measurements are in the PR #211 receipt. Canonical CI runs on every push.

## 34. Negative evidence

- **The first version doubled run time.**
- **The first version failed open after detecting on-disk change.** A Commit Witness could still be appended.
- **Five breaks were found by the independent review**, all fixed:
  - pointer laundering;
  - type-only changes;
  - exceptions after fsync;
  - a race that erased the tamper signal;
  - shared payload objects.
- **Memory still grows by about 1.4 KB per record.**
- **Whole-history spine replays read old events from the file:** about 2.3× the old cost per event.
- **`malloc_trim` reclaims nothing material.**

## 35–36. Reality level and limitations

- Nothing here is above SANDBOX / unit-tested.
- The ARM finding was not reproduced on ARM hardware.
- The memory numbers come from one scenario, on a 4-core x86-64 container, not the Chromebook.

## 37–39. Bottleneck, next node, next action

- **Bottleneck:** VEPMC 0 → 1.
- **Founder's next action (unchanged):** run the Chromebook runbook. It now says to install
  `bubblewrap libseccomp2` first. On an ARM Chromebook, expect Z3 to be reported missing with its reason.
- **Next agent-side actions:**
  1. The #196 integrator reviews and takes in, or declines, this child.
  2. Decide the Consequence Gate's retention of used single-use grants. It is now the largest growing in-memory
     structure outside the ledger: `_grants`, `_meta` and `_reservations` gain one entry per observation, and the
     Gate's bytes are pinned (SR-002). The passport registry has the same issue.
  3. `greg/cognition/settlement.py` replays history every tick. Folding it incrementally, as `MissionBook` was
     folded, would remove the per-tick whole-history read.

## 40. Founder decisions required

1. **Adopt or decline** the dropped-payload ledger into the evidence plane (deliberation:
   NEEDS_FOUNDER_DECISION; all five roles recommend RETAIN).
2. **Consequence Gate retention:** let the Gate forget used single-use grants and settled reservations. This
   changes SR-002 bytes and must be decided with the earlier 3-line claim-scan patch.
3. **Option 2 (checkpointed segments):** the only route to memory that does not grow with history.
4. **Z3 on ARM Debian 12:** keep the exact 5.1.0.0 pin (Z3 absent there), or permit 4.15.4.0, which has a
   `manylinux_2_34_aarch64` wheel, on such bodies. Frozen evaluations are bound to 5.1.0.0.
5. **Unchanged:** run the Chromebook runbook; merge path for #196.
