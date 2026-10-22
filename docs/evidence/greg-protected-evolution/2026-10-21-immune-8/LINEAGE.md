# immune-8: identity, lineage and the gate audit of its predecessor (step A, 2026-10-21)

**Identity.** immune-8 is the successor design pilot for P8 on the target `immune_detect`. Its predecessor is **immune-7**: the cycle-7 design pilot in `../2026-10-21-immune-7/`.

- immune-7 judged the target **NOT_VIABLE** under its declared rule. Its decision, draft pre-registration, observations, thresholds and seeds are kept unchanged; no file in that directory is touched.
- The founder authorized this successor on 2026-10-21 (`docs/intent/sources/MIND-MAXIMUM-CONTINUATION-2026-10-21-source.md`, sections 1-2). The authorization is option 2 of immune-7's decision: a narrower immune search space, evaluated through a new declared pilot on genuinely unused review data.
- **Attempt count.** This is the **second design pilot** on `immune_detect`. If it qualified, its cycle would be the second recorded cycle on this target (after cycle 2, 2026-10-09) and the **seventh P8 cycle**, because cycle 7 was never run.
- **Unchanged, as the directive requires:** the shared frozen `RULE`, its constants, the score, the stress derivations, the genome's shipped `IMMUNE_CONFIG_SPACE` and its incumbent `IMMUNE_DEFAULT_CONFIG` (`cfg-68b55c07dbdc`).

## The gate implementation

Every adversarial gate in this pilot calls the gate merged from the independent stress-gate audit (`09555108`, merged into this branch at `180cd32` before any immune-8 gate ran):

- `evolution.stress_summary` on **item-level** stress losses: items are grouped by exact kind and paired by key, and malformed values are marked;
- `evolution.stress_worsened` on each kind's record, which fails closed;
- `evolution.outputs_verified`.

These are the same three calls `evolution.cycle` makes in its step 5. The pilot holds no replica of the gate (`test_the_pilot_gate_is_the_merged_stress_summary_and_stress_worsened`).

## Did immune-7's conclusions depend on the stress-gate defect?

immune-7's pilot (`scripts/p8_immune_pilot.py`, `stress_report`) applied the **pre-32246ee** gate: `worsened` on the two stress means alone. That gate never fires when the incumbent's mean is +inf. The independent audit (`../2026-10-21-stress-gate-audit/README.md`) reached the same reading.

`gate-audit.json` re-applies the merged gate to immune-7's own retained cycles and region rows.

- **Data used:** only immune-7's train items 3100-3459, regenerated deterministically. They were already generated and looked at by immune-7.
- **Not touched:** no new seed and no held-out data.
- **Cost:** 6,720 evaluations, 429 s, on cores 2-3.
- **Reproduction check:** the old gate, recomputed here, reproduces every one of immune-7's 9 recorded adversarial verdicts.

### Simulated cycles (the basis of the verdict)

| Run | Old gate | Merged gate | Why it changed |
|---|---|---|---|
| T1-120 `cover/1` | pass | **fail** | 3 wrong on `scarce` against the incumbent's 2; 3 against 1 on `strict` |
| T2-120 `cover/1` | pass | pass | |
| T3-120 `cover/1` | pass | pass | |
| T1-120 `mutate-incumbent/1` | pass | pass | |
| T2-120 `mutate-incumbent/1` | pass | pass | |
| T3-120 `mutate-incumbent/1` | pass | pass | |
| T1-60 `cover/1` | fail | fail | |
| T2-60 `cover/1` | pass | **fail** | 3 wrong on `scarce` against 2 |
| T3-60 `cover/1` | pass | pass | |

- **The verdict does not depend on the defect.** It stays **NOT_VIABLE**.
- **The best cell is unchanged:** `mutate-incumbent/1`, 120 train, 120 held-out, mean P(RETAIN) **0.216**. Those three runs pass both gates.
- **Two cells fall:**
  - `cover/1` with 120 train items: 0.191 to **0.109**;
  - `cover/1` with 60 train items: 0.195 to **0.083**.
- **Why the verdict cannot improve:** the merged gate only adds rejections, so immune-7's figures were an upper bound.

### Region rows: one of immune-7's conclusions did depend on the defect

immune-7's README said: "fixed configurations with lower false-alarm risk keep a measured gain: about 0.64-0.74 resampled at n 120-240."

- **That figure never included a stress gate.** It is the held-out step alone, resampled from the pool.
- **Under the old gate every region row "passed" T1's stress sets,** because the incumbent itself was +inf on both kinds there.
- **Under the merged gate, 10 of the 20 rows fail T1's stress sets.** The two configurations behind the 0.69-0.74 figure are among them:

| Configuration (immune-7's label) | Pool wrong / 540 | Merged gate on T1 stress |
|---|---|---|
| full, scale [1.0], uniform 0.511, alarm 0.789 (cycle-2 rank 3) | 1 | **fail** |
| full, scale [1.0], uniform 0.511, alarm 0.75 (cycle-2 rank 4) | 1 | **fail** |
| full, scale [1.0], uniform 0.492, alarm 0.75 (rank 5) | 1 | pass |
| full, scale [1.0], uniform 0.39, alarm 0.75 (rank 6) | 1 | pass |
| whitening full only | 2 | **fail** |
| cycle 2's REJECTED candidate (alarm 0.866) | 4 | **fail** |

**Corrected reading.**

- **The paired-F1 headroom does not depend on the gate.** Full whitening with one detector scale beat the incumbent on paired items on the pool.
- **The "0.64-0.74 if fixed" figure does depend on it.** It omitted the gate. On T1's stress sets only the rank-5 and rank-6 configurations survive the merged gate, at 0.59-0.67 without further gating.
- **One stress check is not a rate.** One train set's stress check is a single draw, so it is not a pass rate. immune-8 measures the merged gate on three fresh train sets instead.

This corrects how immune-7's README should be read. That README is not edited; this file records the correction.

## Causal reason for narrowing the space

Immune-7's observations on review seeds 3100-3999:

1. **The search moved to high alarm budgets.** It selects by train mean -F1 and picked `alarm_fraction` 0.80-0.95 in all nine simulations.
2. **The mechanism is direct.** The detector calibrates its self radius to a false-alarm target of `alarm_fraction x tolerance` (`immune_solve_with`: conformal rank `k = floor(target (n + 1)) - 1`).
   - A higher fraction flags more points. That raises recall and F1.
   - It also raises the realised false-alarm count on the 200 normal test points.
3. **The score turns that into infinite loss.** `immune_score` calls an item **wrong** when its false alarms exceed the binomial 95% limit at the full tolerance. A wrong item has loss +inf.
   - A model of the conformal miss rate as Beta(k + 1, n - k), with false alarms Bin(200, rate) (`DESIGN.md`), predicts that the violation probability rises monotonically with `alarm_fraction`.
   - The model overstates the absolute level: at 0.75 it predicts about 2% per item, against 3 in 540 observed.
4. **What immune-7 observed:** the alarm-heavy picks made 4-6 violations per 540 pool items, against the incumbent's 3.
5. **The rule makes that decisive.** One violation anywhere in the held-out split makes the candidate's held-out mean +inf, and +inf is never lower. Under the repaired gate, one more stress-set violation than the incumbent also rejects.
6. **The gain did not need the extra budget.** The paired-F1 headroom immune-7 found came from full whitening and one detector scale, at the incumbent's own alarm fraction of 0.75.

**The narrowing.** Only the axis that causes the added violations is narrowed: `alarm_fraction` is capped at the **incumbent's own value, 0.75**.

- The space keeps the full space's lower bound of 0.4. Every other axis is unchanged.
- **Principle:** a candidate may not buy F1 by spending more of the false-alarm budget than the shipped detector spends.
- **Why 0.75, and not 0.789 or 0.80:** 0.75 is the incumbent's value, not a value fitted to immune-7's best configuration (0.789). Fitting that value would be choosing after looking.
- **What the cap does not do:** it does not by itself lower the violation rate below the incumbent's. Structural changes (whitening, scale set, folds, detectors) can still change the rate either way; the pilot measures that.

The narrowed space is declared in code before any immune-8 instance is generated (step C).
