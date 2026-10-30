# Compute closure: measured pressure, a working re-ask, a benchmark and a before/after verdict (WU-05)

Branch `claude/compute-closure-20261030`, based on `b1950be2` (#196 head). Directive sections 48, 58, 60 and 71.
Founder instruction of 2026-10-30: "Continue building and doing the prompt verbatim."

## What changed

`greg/compute.py` changed only above `enroll_node`, and `greg/cli.py` gained a `greg compute` group. `greg/body.py`
is unchanged: it already calls `record_telemetry` and `recommend`, so the new behaviour reaches the running body
through that existing path.

**1. The re-ask defect, fixed.** `recommend()` built `request_id` from the resource name alone. After one cpu ask
was answered, a later sustained cpu bottleneck produced the same id, and the dedupe check returned None forever.
This was reproduced on a real body with a signed DECISION (test key). The fix:

- `ask_state()` reads the COMPUTE asks for one resource the way every founder surface reads them: through
  `asks.open_requests` with the mission book's counted answers.
  - An ask is closed only by a founder-signed answer or by a withdrawal.
  - An answer row that no signed DECISION stands behind leaves the ask open.
  - Asks are matched by the resource named in their evidence, not by their id.
- `recommend()` builds the new id from an epoch: the number of closed asks for that resource. The epoch-0 id is
  the old id, so a ledger that already holds an ask is not asked twice.
- `recommend()` never asks while an ask for that resource is pending, whatever that ask's id.
- After a close, `recommend()` asks again only when all `SUSTAINED_SAMPLES` samples in the window were recorded
  after the closing row, by ledger position.

**2. Memory and IO pressure.**

- `sample()` keeps every existing field and adds the PSI `some avg10` and `some avg60` values for cpu, memory and
  io (from `/proc/pressure/*`), and MemTotal, MemAvailable and their ratio (from `/proc/meminfo`).
- A field that cannot be read or parsed is None, never 0.
- `bottleneck()` adds two rules:
  - memory: PSI memory `some avg60` >= 10%, or MemAvailable/MemTotal < 10%;
  - io: PSI io `some avg60` >= 20%.
- A sample missing a field never counts as pressure.
- Precedence is memory, io, cpu, disk. Reclaim and swap appear as IO stalls and as load, and Linux counts IO waits
  in the load average. The old cpu-before-disk order is kept. Every other rule that also held is reported in
  `also_sustained`.

**3. The heaviest measured workload.** The ledger already records step timing: each step's write-ahead
`mission.dispatching` event and its first `mission.action` event carry their record times. `quantify()` reads these:

- It skips recovered steps, later reconciliations and steps with no intent.
- It names the capability with the largest share of step time inside the bottleneck window.
- If no step ran in the window, it says the load may come from outside GREG's missions.
- If nothing has ever been timed, it says the journal records no step timing yet.

The delay figure is labelled `estimate (method: ...)` and never "measured". Uncertainty states
`unpriced: no ROI claim`. Nothing touches the network and nothing reads prices.

**4. Benchmark and verification.**

- `benchmark()` runs a fixed stdlib workload N times: a seeded sha256 chain, a scratch Journal/EvidenceLedger
  append-and-verify, and one interpreter spawn. The scratch ledger lives in a temporary directory that the
  function removes. The result carries per-run seconds, the median, the IQR, per-component medians, the workload
  digest and host facts.
- `verify_improvement()` uses an exact rank-sum permutation test, or a seeded one when there are more than 50,000
  arrangements. The test is one-sided: after faster.
  - VERIFIED needs p <= 0.05 and a relative median improvement above the noise floor (the before run's IQR over its
    median).
  - INCONCLUSIVE means fewer than 5 replicates on a side, or different workloads.
  - Every other case is NOT_IMPROVED.
- No scipy is used.

**5. CLI and the single-writer rule.** `greg compute status` is read-only through `observe()`. `greg compute
benchmark --out FILE` refuses a path inside the body home. `greg compute verify --before A --after B` reads two
files. The body is the ledger's only writer, and no sanctioned path records `compute.benchmark` or
`compute.improvement` without editing `greg/body.py`. So the CLI writes files only, and ledger recording is a
follow-up.

## Commands and results

Python: `/home/user/venv311/bin/python`, with `PYTHONDONTWRITEBYTECODE=1 ... -B -m pytest -q -p no:cacheprovider`.

| Check | Result |
| --- | --- |
| Fail-before: `tests/unit/test_greg_compute_closure.py` copied into a detached worktree of `b1950be2` | **27 failed, 2 passed** ([log](runs/fail-before.log)) |
| The defect test on base | `assert (None is not None)`: no second ask after the answer |
| The memory test on base | `assert (None is not None)`: no bottleneck under memory pressure |
| The 2 that pass on base | the legacy epoch-0 id, and the stdlib/no-provisioning scan |
| Pass-after: the same file | **29 passed** |
| `scripts/ci/check_compute_closure_mutants.py` | **22/22 mutants caught**, unmutated suite passes ([log](runs/mutants.log)) |
| Related suites: compute_closure, platform, founder_asks, crash_loop_breaker, presence, resilience, mind_coverage_record, human_work, continuity, integration phone_asks, integration crash_loop_process | **178 passed, 1 skipped**. The skip is `test_greg_phone_asks`, which needs a Chromium binary. Its expected wording is preserved. |
| The 18 other unit files that drive `cli.main` (final code) | **248 passed** |
| `scripts/ci/check_authority_singleton.py` | passes |

Commands (from `/home/user/wu05`, each with `PYTHONDONTWRITEBYTECODE=1`):

```
/home/user/venv311/bin/python -B -m pytest -q -p no:cacheprovider tests/unit/test_greg_compute_closure.py
/home/user/venv311/bin/python -B scripts/ci/check_compute_closure_mutants.py
/home/user/venv311/bin/python -B -m greg --home H compute status
/home/user/venv311/bin/python -B -m greg --home H compute benchmark --out B.json
/home/user/venv311/bin/python -B -m greg --home H compute verify --before A.json --after B.json
```

## Real runs on this host (LOCAL-REAL; reported, never asserted)

The host is a shared 4-core x86_64 Linux machine (16 GB) with other agents running. The load ratio was about 1.3
throughout, and the cpu PSI `some` readings (avg10 and avg60) ranged from 12 to 42%. "Idle" is therefore not available here.

- **A real body loop** ([run](runs/live-body-reask.json)). An unchanged `Body.run` sampled `/proc` for real
  (telemetry every 2 ticks), and the steps happened in this order:
  1. The first 5-sample window raised a cpu ask, epoch 0.
  2. A further window while that ask was pending raised nothing.
  3. A signed DECISION (reject, test key) was applied by the body.
  4. Four samples after the answer raised nothing.
  5. The fifth raised `req-compute-6fd9…`, epoch 1, citing the first ask. The screen found nothing to withhold.
- **Real step timing** ([run](runs/live-mission-step-timing.json)). A signed fs.write mission closed on a real body.
  Its step measured 0.047 s from ledger record times, and `quantify` named `fs.write` at a 100% share.
- **`greg compute status`** on a real body ([output](runs/compute-status-real-body.json)) returned numeric PSI and
  MemAvailable. The ledger's sha256 was unchanged by the command.
- **Same code, run twice** ([a](runs/same-code-a.json), [b](runs/same-code-b.json),
  [verdict](runs/verify-same-code.json)):
  - medians 0.347 s and 0.350 s;
  - **NOT_IMPROVED**, p = 0.27, noise floor 25.6%.
  - This is the expected null result.
- **Contention removed** ([before](runs/contended-before.json), [after](runs/contention-removed-after.json),
  [verdict](runs/verify-contention-removed.json)):
  - before: four extra busy loops, median 0.626 s;
  - after: no extra loops, median 0.310 s;
  - **VERIFIED**: p = 0.00029 (every after run beat every before run), effect 50.5% against a 28.3% noise floor.

## Limitations

- **Re-ask cadence.** After a reject, the next ask comes one sustained window after the answer: about 50 minutes at
  the body's default telemetry interval. There is no back-off and no "stop asking" control.
- **Live-run spacing.** The live body run used a 0.1 s sample spacing. Its five samples share one load average.
  Production spacing is about 10 minutes.
- **Thresholds and precedence** are declared, not learned or validated on a Chromebook. PSI may be absent on some
  Crostini kernels; the fields are then None and only the MemAvailable floor, load and disk rules apply.
- **Step timing** is wall clock, so a host suspend inside a step inflates it. The delay estimate attributes all
  excess to the bottleneck, which the journal cannot establish. A capability with no history before the window
  gives no estimate.
- **Benchmark scope.** The benchmark measures this fixed workload, not GREG's missions. A verdict compares the two
  benchmark runs only. A different host is reported, not refused.
- **Not recorded on the ledger.** `compute.benchmark` and `compute.improvement` are not ledger records: the CLI
  writes files only, and recording them needs a sanctioned body path (follow-up, `greg/body.py`).
- **No real Chromebook run** (not required by the founder's 2026-10-30 instruction). The Chromium phone test was
  skipped here.

## Reality level

- **UNIT-TESTED and INTEGRATION-TESTED:** the logic, on real Body and ledger fixtures with a signed DECISION from a
  test key (not Alfonso's key).
- **LOCAL-REAL:** `/proc` sampling, the body-loop ask and re-ask, mission step timing, and the two benchmark
  verdicts, all on this shared Linux host.
- **Not achieved:** founder-device verification and external verification.

Authority delta: none. The asks still buy, rent and install nothing.
