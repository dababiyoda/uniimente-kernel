# immune-8 design pilot: results (step D, 2026-10-21)

**Verdict under the rules declared in `../DESIGN.md` (committed at `e7cbe72`, before any instance of seeds 4000-4999 was generated): NOT_VIABLE.**

- **Best mean simulated P(RETAIN) at alpha 0.05: 0.000.** The declared threshold is 0.30.
- **All six simulated cycles fail** the merged adversarial gate (`stress_summary` + `stress_worsened` on item-level losses).
- **The pilot completed within its limits:**

| Mode | Evaluations | Wall-clock | Limit |
|---|---|---|---|
| region | 8,520 | 647 s | 15,000 evaluations / 3,600 s |
| simulate | 23,120 | 2,953 s | 50,000 evaluations / 10,800 s |

  Both ran on cores 2-3.
- **No pre-registration is drafted.** Under `DESIGN.md` section 9, this lane proposes no third immune pilot. The negative result is kept.

This pilot is design knowledge only. It is not evidence for any cycle and decides nothing about adoption.

Files: `region.json`, `simulate.json` and `summary.json`. `summary.json` holds `choose()`'s output; every number below comes from them.

## The trigger fires

The incumbent is worse than z-score on 49.2% (T1), 55.0% (T2) and 55.8% (T3) of train items. The threshold is 25%.

## Simulated cycles (narrowed space `immune-8/alarm-cap/1`, merged gate)

The picks are the same configuration for both procedures on T1 and T3, and differ only in `alarm_fraction` (0.699 against 0.75) on T2.

| Train | Procedure | Pick (changes from the incumbent) | Train gain | Wrong on `scarce`: incumbent / candidate | Wrong on `strict`: incumbent / candidate | Gate |
|---|---|---|---|---|---|---|
| T1 | `mutate-incumbent/1` | full, folds 5, 5000 detectors, uniform 0.549 | +inf (incumbent 1 train wrong) | 3 / **6** | 0 / **3** | **fail** |
| T2 | `mutate-incumbent/1` | full, folds 5, 4000 detectors, scale [1.0], alarm 0.699 | +inf (incumbent 1 train wrong) | 2 / **4** | 0 / **1** | **fail** |
| T3 | `mutate-incumbent/1` | full, 4000 detectors, uniform 0.796 | 6.8% | 1 / **3** | 0 / 0 | **fail** |
| T1 | `cover/1` | same as `mutate-incumbent/1` | +inf | 3 / **6** | 0 / **3** | **fail** |
| T2 | `cover/1` | full, folds 5, 4000 detectors, scale [1.0] | +inf | 2 / **4** | 0 / **1** | **fail** |
| T3 | `cover/1` | same as `mutate-incumbent/1` | 6.8% | 1 / **3** | 0 / 0 | **fail** |

- **Every pick passes independent verification.** Every pick fails the gate because it makes more false-alarm violations on the `scarce` set than the incumbent (80 self samples).
- **The `strict` set adds failures** on T1 and T2 (a five-fold tighter tolerance).
- **The cap did what it was declared to do.** No pick exceeds `alarm_fraction` 0.75.
- **The cap did not remove the fragility.** Every pick uses **full whitening**, which estimates a full covariance from the self samples; with 80 samples that estimate is noisy. Cycle 2 found the same failure on `scarce:s7002`.

## Pool (640 fresh items, 4360-4999): the picks and every comparator

Error columns: false-alarm violations out of 640, with the exact one-sided 95% Clopper-Pearson upper bound on the rate.

| Arm | Wrong / 640 (upper 95%) | Mean -F1 without wrong | vs incumbent (wins-losses) | vs Hotelling |
|---|---|---|---|---|
| incumbent `cfg-68b55c07dbdc` | 3 (1.21%) | -0.474 | - | 81-546 |
| z-score (trigger baseline) | 55 (10.6%) | -0.486 | 304-323 | |
| **Hotelling prediction ellipsoid** | 11 (2.83%) | **-0.575** | **546-81** | - |
| 5-NN split-conformal | 21 (4.69%) | -0.488 | 349-254 | |
| T1 pick | 4 (1.42%) | -0.514 | 404-150 | 119-494 |
| T2 pick (`cover/1`) | 6 (1.84%) | -0.513 | 384-160 | 124-485 |
| T3 pick | 5 (1.64%) | -0.502 | 339-206 | 118-502 |

**What the gate would have allowed.** If a pick had passed the gate, its held-out P(RETAIN) at 0.05, resampled from the pool, would have been:

| Held-out size n | P(RETAIN) |
|---|---|
| 120 | 0.31-0.47 |
| 240 | 0.11-0.23 |
| 360 | 0.03-0.10 |
| 480 | 0.01-0.05 |

Only n = 120 would have cleared 0.30 on any pick, and only before the gate is applied. One violation anywhere in the held-out split still forces REJECT.

### Fixed configurations informed by prior observations (comparators only; never candidates)

| Configuration | Wrong / 640 | vs incumbent | Gate on T1 / T2 / T3 | P(RETAIN) as a fixed protocol, n = 120 / 240 |
|---|---|---|---|---|
| whitening full | 3 | 325-177 | fail / fail / fail | 0 / 0 |
| full, scale [1.0], uniform 0.511 (cycle-2 rank 4) | 5 | 331-212 | pass / pass / fail | 0.18 / 0.10 |
| full, scale [1.0], uniform 0.492 | 3 | 349-198 | fail / pass / fail | 0.16 / 0.11 |
| full, scale [1.0], uniform 0.511, alarm 0.789 (outside the space) | 5 | 344-200 | pass / pass / fail | 0.21 / 0.10 |
| cycle 2's REJECTED candidate (alarm 0.866; outside the space) | 4 | 390-186 | fail / pass / fail | 0.15 / 0.08 |

None of these reaches 0.30 either, even with the configuration fixed in advance and no search.

## What the pilot established

1. **The paired-F1 headroom replicates on fresh data.** Every full-whitening configuration beats the incumbent on 640 fresh items, by 325-177 to 404-150. The headroom is real.
2. **It does not survive the rule's own adversarial gate.**
   - Full whitening is the source of the F1 gain. It is also the source of extra violations when self samples are scarce.
   - The incumbent's diagonal standardisation is more robust there.
   - Capping the alarm budget removed the effect immune-7 identified; it did not remove this second effect.
3. **The immune-7 gate audit predicted this.** Once wrong answers are counted (the repair in 32246ee, merged as `stress_summary`), most full-whitening configurations fail on some train set's stress items.
4. **The target is dominated by a simple detector.** On this Gaussian regime, the exact Gaussian prediction ellipsoid (Hotelling) beats the incumbent 546-81 and every pick by roughly 490-120.
   - Admission v1 had already found this (5-25).
   - Hotelling also makes more false-alarm violations (11/640) than the incumbent (3/640). So it is "better" on F1 and worse on errors, and the rule would not rank it ahead.
   - Evolving `collective_immune` on this regime improves a method that GREG's competence routing would not choose for this geometry.

## Error-rate statement

- **No arm makes zero violations on the pool.** The incumbent's rate is 3/640, at most 1.21% at 95%. The picks' rates are 4-6/640, at most 1.42-1.84%.
- **A RETAIN would need zero candidate violations in the held-out split.** At n = 240 that bounds the rate at 1.24%, and at n = 480 at 0.62%. The pool rates make a clean held-out split unlikely at any n at or above 240.
- **Zero observed violations would never show zero risk.**

## Mechanical verdict

From `summary.json`:

- `complete` is true;
- the trigger fired on all three train sets;
- the best cell mean at 0.05 is 0.0, below 0.30.

**NOT_VIABLE.** There is no choice of held-out size or procedure.

## Reproduce

    D=docs/evidence/greg-protected-evolution/2026-10-21-immune-8/pilot
    PYTHONPATH=. taskset -c 2,3 python scripts/p8_immune8_pilot.py region --out $D/region.json
    PYTHONPATH=. taskset -c 2,3 python scripts/p8_immune8_pilot.py simulate --out $D/simulate.json
    PYTHONPATH=. python scripts/p8_immune8_pilot.py summarise --dir $D --out $D/summary.json

Outputs are deterministic: workers run whole items, and the resampling streams are seeded.
