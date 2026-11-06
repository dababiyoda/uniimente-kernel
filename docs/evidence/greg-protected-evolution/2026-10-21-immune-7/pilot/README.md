# P8 cycle 7 design pilot: `immune_detect` (immune review seeds 3100-3999 only)

**Verdict under the rules declared before any instance was generated: NOT_VIABLE.**

- The rules were committed in `83c3756` (`scripts/p8_immune_pilot.py`) before the pilot ran.
- The best mean simulated P(RETAIN) at alpha 0.05 is **0.216**. The declared threshold is 0.30.
- The pilot is design knowledge only. It is not evidence for any cycle and it decides nothing about adoption.

## Why `immune_detect`, and not `forecast_quantile`

- **`forecast_quantile` has no data left.** Its pool holds 241 M4 weekly series:
  - cycle 1's split (`evolution.used_instance_keys`) used 201 of them;
  - the development seeds and the admission freezes used 120 (the two sets overlap);
  - 0 are unused, computed at `050c1b2`.
- **Cycle 1's held-out split is spent.** Its record shows the look on 101 series.
- **New data are blocked by the environment.** The network policy refuses `data.cityofnewyork.us`, as recorded for F8, and no other weekly pool is in the repository.
- **`immune_detect` is the only other declared target.** Cycle 2 (2026-10-09) triggered on it and stopped at the scarce-sample stress gate, so its held-out seeds 8000-8059 are unspent.

## Seeds

- **Review seeds 3100-3999, through `guard`.** Immune review seeds 3000-3059 had already been drawn by the native-regime builder measurement (`65b9acc`) and by the unit tests, so this pilot starts at 3100.
- **Unused by any earlier immune measurement.** Grep of scripts, tests and evidence found no immune use of 3100-3999. The constraint-release pilots used 3000-3999, but on another generator, `developmental.constraint_release_instance`; the immune generator seeds `7_400_000 + seed`.
- **Train sets:** T1 3100-3219, T2 3220-3339 and T3 3340-3459, 120 items each. Each was also run on its first 60 items.
- **Look pool:** 3460-3999 (540 items), disjoint from every train set.

## Results

Run on 2026-10-21. `region.json` holds 19,560 evaluations (1,478 s); `simulate.json` holds 34,320 evaluations (3,369 s); `summary.json` derives every number below.

### The trigger fires

| Set | Incumbent worse than z-score |
|---|---|
| T1 | 48.3% |
| T2 | 50.0% |
| T3 | 45.8% |
| Pool | 51.3% |
| 60-item subsets | 41.7-48.3% |

The trigger threshold is 25%.

### Headroom exists in the closed space (`region.json`, pool of 540)

| Configuration (changes from the incumbent) | Wins-losses vs incumbent | Wrong answers / 540 | Mean -F1 without wrong | P(RETAIN), n = 120 / 240 |
|---|---|---|---|---|
| incumbent (`cfg-68b55c07dbdc`) | - | **3** | -0.469 | - |
| whitening full | 267-163 | 2 | -0.490 | 0.48 / 0.40 |
| full, scale [1.0], uniform 0.511 (cycle-2 rank 4) | 295-165 | 1 | -0.489 | 0.69 / 0.64 |
| full, scale [1.0], alarm 0.789 (cycle-2 rank 3) | 300-157 | 1 | -0.493 | 0.74 / 0.64 |
| full, scale [1.0], alarm 0.866 (cycle 2's REJECTED candidate) | 326-153 | 4 | -0.505 | 0.41 / 0.17 |
| alarm 0.95 | 242-103 | 6 | -0.493 | 0.26 / 0.07 |
| alarm 0.40 | 62-405 | 0 | -0.401 | 0 / 0 |

- **A gain exists.** Full whitening with a single detector scale beats the incumbent on paired F1, with no more false-alarm violations.
- **That region was not searched for.** The best fixed configurations come from cycle 2's record. This pilot did not search for them, so they are not a candidate any frozen cycle would select.

### The frozen search does not select that region

Nine simulated cycles ran with the cycle's own `run_search`, gates and rule:

- **Gates.** All nine triggered and advanced. Eight passed the stress gate; T1-60 failed it on `strict` (2 wrong answers against 0).
- **What the search picks.** It selects by train mean loss, which rewards F1. It mostly picks `alarm_fraction` 0.80-0.95.
- **Those picks make false alarms.** On the pool the candidates gave **4-6 wrong answers in 540** (0.7-1.1%), against the incumbent's 3.
- **They still beat the incumbent on paired items.** For example, T1's pick won 355-129.

### Why the rule cannot keep those picks

Any false-alarm violation is a wrong answer. A wrong answer has loss +inf, so a held-out mean that contains one is +inf, and +inf is never lower than another mean. RETAIN therefore requires the candidate to make **no** violation anywhere in the held-out split.

With 4-6 violations per 540 items, the chance of a clean sample is low:

| Held-out size n | P(no violation in the sample) |
|---|---|
| 120 | 0.26-0.41 |
| 240 | 0.07-0.17 |

This caps P(RETAIN) whatever the F1 gain. The resampled rates track the cap:

| Choice | P(RETAIN) at 0.05 | At 0.05/7 |
|---|---|---|
| `mutate-incumbent/1`, 120 train, 120 held-out (best) | 0.216 | 0.192 |
| `cover/1`, 120 train, 120 held-out | 0.191 | 0.166 |
| `cover/1`, 60 train, 120 held-out | 0.195 | 0.187 |
| any choice, 240 held-out | 0.06-0.08 | 0.05-0.07 |
| any choice, 480 held-out | below 0.01 | below 0.01 |

Larger held-out splits lower P(RETAIN).

### The stress gate is often vacuous on this target

`worsened(incumbent, candidate)` is False whenever the incumbent's stress mean is +inf: no candidate value exceeds +inf.

- **The incumbent itself makes stress-set errors.** On T1's stress sets it gave 2 wrong answers on `scarce` and 1 on `strict`.
- **Every train set disarms a stress kind this way.** Each of the six simulated train sets disarms one or both stress kinds.
- **The gate passed a worse candidate.** On T1-120 it passed a candidate with 3 `scarce` and 3 `strict` wrong answers, against the incumbent's 2 and 1.

Cycle 2's REJECT happened on a train set where the incumbent was clean on `scarce`. This is a property of the frozen rule with infinite losses. It is reported, not changed.

## What this means

- **The declared verdict stands: NOT_VIABLE.** A seventh cycle on `immune_detect` under the unchanged rule, space and search would RETAIN with probability about 0.2 at best.
- **It is not "no headroom."** Fixed configurations with lower false-alarm risk keep a measured gain: about 0.64-0.74 resampled at n 120-240.
- **The frozen chain cannot reach them.** It selects by a train mean that favours alarm-heavy configurations, and the rule turns their roughly 1% violation rate into REJECT.
- **Levers that remain are design changes for the session owner** (see `../PREREGISTRATION.md`). None was tried here, because trying one now would be choosing after looking.

## Reproduce

    PYTHONPATH=. python scripts/p8_immune_pilot.py region   --out pilot/region.json
    PYTHONPATH=. python scripts/p8_immune_pilot.py simulate --out pilot/simulate.json
    PYTHONPATH=. python scripts/p8_immune_pilot.py summarise --dir pilot --out pilot/summary.json

Each run uses up to three worker processes. Each worker runs `collective.immune_solve_with` on whole items, so the outputs are deterministic and independent of the worker count.
