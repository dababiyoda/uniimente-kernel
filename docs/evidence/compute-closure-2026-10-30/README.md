# Compute closure: measured pressure, a working re-ask, a benchmark and a before/after verdict (WU-05)

Branch `claude/compute-closure-20261030`, based on `b1950be2` (#196 head). Directive sections 48, 58, 60 and 71.
Founder instruction of 2026-10-30: "Continue building and doing the prompt verbatim."

Two rounds of work. Round 1 (`de49224a`..`416a2e54`) built the unit. Round 2 fixed nine review findings; its
dispositions are listed under [Review round 2](#review-round-2).

## What changed

Only these changed: `greg/compute.py` (above `enroll_node`), plus a new `greg compute` group in `greg/cli.py`.
`greg/body.py` is unchanged. It already calls `record_telemetry` and `recommend`, so the new behaviour reaches
the running body through that path.

**1. The re-ask defect, fixed.** `recommend()` built `request_id` from the resource name alone. After one answered
cpu ask, every later sustained cpu bottleneck produced the same id, and the dedupe check returned None forever. This
was reproduced on a real body with a signed DECISION (test key). The fix:

- `ask_state()` reads the COMPUTE asks for one resource the way every founder surface reads them: through
  `asks.open_requests` with the mission book's counted answers.
  - Only a founder-signed answer or a withdrawal closes an ask.
  - An answer row with no signed DECISION behind it leaves the ask open.
  - A `decision.requested` row recorded under another identity is not an ask.
  - Asks are matched by the resource named in their evidence.
- The new id carries an epoch: the number of closed asks for that resource. Epoch 0 keeps the old id, so a ledger
  that already holds an ask is not asked twice.
- No new ask while one for that resource is pending.
- After a close, GREG asks again only when every one of the `SUSTAINED_SAMPLES` window samples lies after the
  closing row in ledger position.

**2. Memory and IO pressure.**

- `sample()` keeps every existing field and adds:
  - PSI `some avg10` and `some avg60` for cpu, memory and io;
  - MemTotal, MemAvailable and their ratio.
- A field that cannot be read, or reads negative, is None, never 0.
- Two new rules:
  - memory: PSI memory `some avg60` >= 10%, or MemAvailable/MemTotal < 10%;
  - io: PSI io `some avg60` >= 20%.
- A sample missing a field never counts as pressure.
- Precedence is memory, io, cpu, disk. The other rules that held are listed in `also_sustained`.

**3. The heaviest measured workload.** `step_times()` reads the ledger's existing record times: each step's latest
write-ahead `mission.dispatching` to its first `mission.action`. A step is timed only if it ran straight through.
These are not timed:

- a step with a body-loop record between its intent and its outcome (`LOOP_RECORDS`: any `mission.*`,
  `decision.*`, `body.*`, `command.*` or `compute.telemetry` record). Such a step waited for the founder or for a
  restart. The body is single-threaded, and a dispatch writes only its intent, its capability's own records and
  its outcome.
- a recovered step;
- an outcome with no intent or no capability;
- a negative span.

`quantify()` names the capability with the largest share of timed step time in the bottleneck window. The ask says
so when no step ran in the window, when nothing was ever timed, or when the window's steps took 0 s. The delay
figure is labelled `estimate (method: ...)`. The uncertainty keeps `unpriced: no ROI claim`. There are no network
calls and no prices.

**4. Benchmark and verification.**

- `benchmark()` runs a fixed stdlib workload N times: a seeded sha256 chain, a scratch Journal/EvidenceLedger
  append-and-verify (in a temporary directory it removes) and one interpreter spawn.
- It measures what competed with each replicate:
  - the share of the chain's wall time this process spent off the CPU (`process_time` against `perf_counter`);
  - the host-wide PSI `some` stall time for cpu, io and memory over the replicate, as a share of it.
- It records host conditions at the start and at the end.
- `verify_improvement()` runs a one-sided rank-sum permutation test, exact up to 50,000 arrangements and seeded
  beyond, with alpha 0.05. The noise floor is the before run's IQR over its median.
- Verdicts:
  - **VERIFIED** also needs per-replicate contention measured during both runs, and the after run must not have met
    measurably less of it (a declared tolerance of 0.05 of each replicate's time, on any measure).
  - **INCONCLUSIVE** when either side has fewer than 5 replicates, the two runs used different workloads, no
    contention was measured during both, the after run was faster on a measurably quieter host, or it was not
    faster on a measurably busier host.
  - **NOT_IMPROVED** otherwise.
- Every verdict carries its `scope`: it measures the code and the host together. A change that works by lowering
  the host's load shows in the next telemetry window, not here.

**5. CLI and the single-writer rule.**

- `greg compute status` is read-only, through `observe()`.
- `greg compute benchmark --out FILE` refuses a path inside the body home, resolved as the body resolves it (`~`
  expanded, symlinks followed, `samefile`). It will not overwrite a file that is not an earlier benchmark result.
- `greg compute verify --before A --after B` reads two files.
- The CLI never writes the body ledger. Recording `compute.benchmark` and `compute.improvement` on the ledger needs a
  path in `greg/body.py`, so it is a follow-up.

## Review round 2

| Finding | Disposition | Regression test(s) (fail at `416a2e54`) |
| --- | --- | --- |
| WU05-F1: approval wait and downtime booked as step time | **Fixed.** Reproduced on real bodies with both reviewer probes. Timing starts at the latest intent, and a loop record between intent and outcome voids it. | `test_a_step_that_waited_for_the_founder_or_for_a_restart_is_not_timed`, `test_any_loop_record_between_an_intent_and_its_outcome_voids_the_timing[*5]`, `test_on_a_real_body_the_founders_approval_wait_is_not_booked_as_step_time`, `test_on_a_real_body_downtime_before_the_gate_claimed_a_dispatch_is_not_step_time` |
| WU05-F2 and F1-verify: VERIFIED for unchanged code when only host load changed | **Fixed.** Per-replicate contention is measured, the guard applies, and the verdict states its scope. Real runs are below. | `test_the_same_code_on_a_quieter_host_is_never_verified`, `test_no_change_on_a_busier_host_is_inconclusive_and_a_speed_up_despite_it_is_verified`, `test_a_verdict_needs_contention_measured_during_both_runs` |
| WU05-F3: `~` home bypasses the `--out` guard and can overwrite the ledger | **Fixed.** Reproduced with the reviewer probe. The guard now uses `Layout(home).home` and `samefile`, and refuses to overwrite any file that is not a benchmark. | `test_cli_benchmark_guard_expands_the_home_and_never_overwrites_a_file_it_did_not_write` |
| WU05-F4: a None capability or a 0 s total crashes `recommend()` | **Fixed in compute.py.** Both reviewer fixture probes reproduced. Capability-less outcomes are not timed, and a 0 s window names no workload. **Deferred:** wrapping `recommend` in `Body._contained` needs `greg/body.py`. | `test_a_step_without_a_capability_or_a_window_of_zero_second_steps_never_breaks_the_ask` |
| F2-mutants: safeguards without mutants | **Fixed.** All 10 named, plus the reviewer's extra probes, are now tests and mutants: 51 in all. The round-1 commit title "mutants for every safeguard" overclaimed; it covered 22. | `test_reconciliations_outcomes_without_an_intent_and_a_stepped_clock_are_not_timing`, `test_an_ask_row_under_another_identity_is_not_an_ask_and_does_not_advance_the_epoch`, `test_tied_samples_take_midranks_so_the_exact_p_value_is_right`, `test_a_scratch_ledger_that_fails_verification_stops_the_benchmark_and_varying_output_is_flagged`, `test_verify_reports_whether_both_runs_used_the_same_host`, the CLI test (`--runs 0`), the negative-PSI check |
| F3-flaky: the scratch-directory assertion races other benchmarks | **Fixed.** The test uses a private `tempfile.tempdir`. With a background benchmark loop sharing TMPDIR, the old test failed 2 of 3 runs and the new one failed 0 of 3 ([log](runs/tempdir-race.log)). | same test |
| F4-product-delta: memory/io and the named workload claimed on a real body loop | **Corrected.** Memory and io naming remain UNIT-TESTED only. The named workload is now LOCAL-REAL (below). | n/a |
| F5: evidence not regenerable; contention unrecorded | **Fixed.** The scripts are in [scripts/](scripts/). Conditions are recorded at the end, and contention per replicate. The `host_facts` docstring no longer claims a start snapshot tells contended from idle. | n/a |

The round-1 files `same-code-*.json`, `verify-same-code.json`, `contended-before.json`,
`contention-removed-after.json` and `verify-contention-removed.json` are kept as pre-fix evidence. In particular,
`verify-contention-removed.json` is a VERIFIED that host drift alone produced, not a validation of the verifier.
The round-1 logs are `runs/fail-before-round1.log` and `runs/mutants-round1.log`.

## Commands and results

Python: `/home/user/venv311/bin/python`. Every run used `PYTHONDONTWRITEBYTECODE=1 ... -B -m pytest -q -p
no:cacheprovider`, from `/home/user/wu05`.

| Check | Result |
| --- | --- |
| Final `tests/unit/test_greg_compute_closure.py` on a detached worktree of `b1950be2` | **46 failed, 2 passed** ([log](runs/fail-before-at-b1950be2.log)); the 2 are the legacy epoch-0 id and the stdlib scan |
| The same file on a detached worktree of `416a2e54` (round 1) | **16 failed, 32 passed** ([log](runs/fail-before-review-at-416a2e54.log)); the 16 are the round-2 regression tests above |
| The reviewer probes (`test_probe_step_timing`, `_downtime`, `_cli_tilde`, `_quantify_crash` x2) on the fixed tree | all 5 now fail, so the defects they assert are gone; `test_probe_uncontained` still passes (`greg/body.py`, deferred) |
| Pass-after, same file | **48 passed** |
| `scripts/ci/check_compute_closure_mutants.py` | **51/51 mutants caught**; unmutated suite passes ([log](runs/mutants.log)) |
| Related suites: compute_closure, platform, founder_asks, crash_loop_breaker, presence, resilience, mind_coverage_record, human_work, continuity, computer, integration phone_asks, integration crash_loop_process | **197 passed, 2 skipped** (both skips need a Chromium binary: `test_greg_computer`, `test_greg_phone_asks`) |
| The 15 other unit files that call `cli.main` | **255 passed** |
| `scripts/ci/check_authority_singleton.py` | passes |

Regenerating the real runs (each script's docstring gives its usage):

```
python -B docs/evidence/compute-closure-2026-10-30/scripts/live_reask.py SCRATCH > runs/live-body-reask.json
python -B docs/evidence/compute-closure-2026-10-30/scripts/live_steps.py SCRATCH > runs/live-mission-step-timing.json
python -B docs/evidence/compute-closure-2026-10-30/scripts/same_code_series.py runs/same-code-series 10 > runs/same-code-series.json
python -B docs/evidence/compute-closure-2026-10-30/scripts/contention_pair.py runs/contention-pair 4 > runs/contention-pair/verdict.json
python -B docs/evidence/compute-closure-2026-10-30/scripts/code_change_pair.py 3 0.15 > runs/code-change-pairs.json
```

## Real runs on this host (LOCAL-REAL; reported, never asserted)

The host is a shared 4-core x86_64 Linux machine with other agents running; load1 was 4.5 to 6.2 during these
runs. Memory PSI read 0.0 throughout.

- **Body loop, ask and re-ask** ([run](runs/live-body-reask.json)). An unchanged `Body.run` sampled `/proc`:
  - its first window raised a cpu ask at epoch 0;
  - nothing more was raised while that ask was pending, or for four samples after the signed answer (test key);
  - the fifth sample raised `req-compute-6fd9…` at epoch 1, citing the first ask.
- **Step timing and the named workload** ([run](runs/live-mission-step-timing.json)):
  - A signed fs.write mission ran straight through; its step measured 0.014 s.
  - A paid mission waited 2 s for its signed approval. That wait was not booked: one timed step, not two.
  - `recommend()` on the real window (load/cores 0.997 to 0.998, so the cpu rule held) raised an ask whose first
    option names `fs.write` at 100% of measured step time.
- **Same code, ten runs back to back** ([series](runs/same-code-series.json)), 9 consecutive pairs:
  - by statistics alone (the round-1 verdict), 2 pairs were VERIFIED, both false;
  - with the guard, 0 were VERIFIED, 6 INCONCLUSIVE and 3 NOT_IMPROVED;
  - both false positives met a drop in cpu wait share (0.25 → 0.08 and 0.16 → 0.08).
- **Busy loops removed** ([verdict](runs/contention-pair/verdict.json)): 4 extra busy loops during the before run.
  - Medians: 0.705 s before, 0.416 s after, p = 0.00058.
  - Verdict **INCONCLUSIVE**: cpu wait share 0.57 → 0.13, PSI cpu share 0.69 → 0.44.
  - The lagging start snapshots pointed the other way (load1 5.68 → 6.11).
- **Positive control: a real code change** ([runs](runs/code-change-pairs.json)). Removing a 0.15 s delay from the
  ledger step was **VERIFIED in 3 of 3 attempts**: effect 24-28%, p 0.0003-0.006, contention shifts within
  tolerance.

## Limitations

- **The guard is a proxy.** It sees descheduling of this process and host PSI stall time. Drift that shows in
  neither (frequency or thermal scaling, a cache-heavy neighbour without run-queue waits) is not caught. Two of two
  false positives were caught in this series; that is not a measured false-positive rate.
- **Noisy hosts get few verdicts.** On this host cpu wait share moved by more than 0.05 between every pair of
  consecutive runs (0.06 to 0.18), and 6 of 9 same-code pairs were INCONCLUSIVE. The 0.05 tolerance is declared,
  not calibrated on a Chromebook.
- **An optimization that lowers the host's load is INCONCLUSIVE here by design.** Its evidence is the next
  telemetry window.
- **Step timing:**
  - wall clock: a host suspend inside a straight-through step still inflates it;
  - a capability that writes `mission.*` or `decision.*` records mid-dispatch would leave its steps untimed (none
    observed);
  - the delay estimate attributes all excess time to the bottleneck, which the journal cannot establish.
- **Re-ask cadence:** after a reject, the next ask comes one sustained window later (about 50 minutes at the default
  interval). There is no back-off.
- **Thresholds:** memory (10% PSI avg60, 10% MemAvailable floor), io (20%) and the precedence order are declared,
  not validated on a Chromebook. Memory and io naming are UNIT-TESTED only: memory PSI was 0 on this host.
- **CLI guard:** the `samefile` branch (case-insensitive volumes, bind mounts) is not exercised on this Linux
  filesystem.
- **Not on the ledger:** `compute.benchmark` and `compute.improvement` are not ledger records, and `recommend` is
  not wrapped in `Body._contained`. Both need `greg/body.py` (follow-ups).
- **No device runs:** no Chromebook or founder-device run (not required by the 2026-10-30 instruction). The two
  Chromium tests were skipped. All signatures use a generated test key.

## Reality level

- **UNIT-TESTED and INTEGRATION-TESTED:** all logic, on real Body and ledger fixtures, including approval and
  restart paths on real bodies.
- **LOCAL-REAL on this shared Linux host:** `/proc` sampling, the cpu ask and epoch-1 re-ask on `Body.run`, step
  timing read back from a real ledger, the workload named in a real-window ask, and the CLI benchmark/verify series
  (same code, contention removed, code change).
- **UNIT-TESTED only:** memory and io bottleneck naming.
- **Not achieved:** founder-device verification and external verification.

Authority delta: none. The asks still buy, rent and install nothing.
