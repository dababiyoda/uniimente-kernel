# Governed recovery: quarantine → probe → eligibility (2026-10-14)

Third leap under `INTENT-20261013-FRONTIER-LEAP-RECOMBINE`, built on #173 together with the port of #164 and #172. One agent wrote, attacked and reviewed this change. That is not independent peer review.

## Original deficit

1. **No path back from quarantine.** A capability quarantined for an in-service fault never returned without the founder. If every provider for a function faulted transiently, the function was lost, and missions escalated after the fault had already cleared.
2. **A pre-existing crash, found while building this and reproduced on #173's head `bd47242`.** The sequence was:
   - the founder attached a capability, and it faulted with no alternative available;
   - the re-escalation produced a blocker identical to the earlier one, and content-keyed de-duplication swallowed it;
   - the mission looked unblocked and re-entered Genesis on its open deficit;
   - Genesis re-ran a recorded qualification, and the ledger refused the repeated fact (`EventError`).

   From then on, every tick crashed.

## Source mechanisms and REA observations

- **opossum 10.0.0** was analysed with REA and then read in source. Details are in `../../mechanisms/MC-0002-governed-half-open-recovery.md`, `rea-opossum-extract.json` and `rea-opossum-circuit-observations.txt`.
- REA established the reset timer, half-open and close structure statically. Nothing was executed.
- The full 75 MB evidence JSON is not committed. Its sha256 and evidence ID are recorded in the extract.
- **GREG precursor:** route demotion with a cooldown in `greg/models.py`.

## Mutation and recombination

| Donor (opossum) | GREG |
|---|---|
| The next **live** call is the probe | A sandbox probe on a **fresh frozen-oracle seed**, counterfactual and never live work |
| One success closes the breaker, putting the component back in service | Success restores **eligibility** (VERIFIED). Authority (ATTACHED) comes only from the founder or the mission's signed scope. |
| Fixed `resetTimeout` | 15 min × 2^(failed probes + prior quarantines − 1), capped at 24 h |
| Flapping repeats forever | Stops after more than 3 in-service quarantines or 5 failed probes; the founder decides |
| One breaker per call site | **Dependency-ordered:** engines are probed before constructions, and a construction probes through its own pinned engine (`_ProbeView`, probe-only). On re-admission its exact engine is attached under the same scope. |

**New behaviour:** a function lost to transient faults returns and the original mission closes without founder attention. Recovery stays inside the founder-signed scope and never grants authority.

## Implementation

| File | Change |
|---|---|
| `greg/genesis.py` | `recover`, `_probe`, `_ProbeView`, `recovered_for`, `_attach_dependency`; constants `RECOVERY_*`, `RECOVERED_BY`; quarantine facts carry `incident` and `at`; `_recorded_qualification`, which reuses a recorded qualification on the same deficit for packages, binaries and constructions; the `verified_detached` route re-attaches a construction's exact engine |
| `greg/missions.py` | Block and unblock facts keyed by generation (the crash fix); one re-admission per recovery in `_blocker_resolved` |
| `greg/body.py` | `Genesis.recover(now)` each tick; never while paused or stopping |
| `scripts/ci/check_cortex_mutants.py` | `recovery` group, 8 mutants |
| `docs/mechanisms/MC-0002-*` | Mechanism Card (JSON with all 20 fields, plus a Markdown summary) |

## Authority

- Recovery writes only `capability.probe`, `capability.state` VERIFIED and `capability.recovery_stopped` facts.
- It never attaches anything.
- Identity-changing quarantines (changed pins, changed code, missing source) are never probed.
- Founder-detached capabilities are never touched.

## Evidence

All scenarios run on a real body with real engines, in `tests/integration/test_greg_capability_recovery.py` (9 tests):

1. **Transient fault:** recovery happens and the mission is ACHIEVED with no founder answer.
2. **Failed probe:** the wait doubles, every probe draws a fresh seed, and eligibility is never restored.
3. **Flapping:** recovery stops.
4. **Changed identity:** never probed.
5. **Construction:** the engine is probed before its construction in the same pass, the exact engine is re-attached under scope, and the mission is ACHIEVED.
6. **No signed scope:** the capability stays VERIFIED and the founder is asked.
7. **Re-escalation after a founder attach:** recorded, and the body keeps ticking.
8. **Same open deficit:** the recorded qualification is reused, not re-run.
9. **Mechanism Card:** complete.

The `recovery` mutation group (8 mutants) is all caught.

## Classification and continuation

**BUILDABLE**, as implemented. Not covered: probes for builder-made and CLI-binary capabilities (`_probe` returns "no recovery probe for this kind"). Next:

- extend recovery probes to those kinds;
- let Goal Gravity treat a recovery as an awakening event;
- measure founder-attention saved on a long-running body.
