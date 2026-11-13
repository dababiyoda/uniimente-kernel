# P8 cycle 7 on `immune_detect`: not run (decision of 2026-10-21)

The pilot's verdict was **NOT_VIABLE** under its declared rule: the best mean simulated P(RETAIN) was 0.216, against
a threshold of 0.30. That rule was committed at `83c3756`, before any pilot instance was generated, and its result is
followed here. Nothing was frozen and nothing was run. `PREREGISTRATION.md` stays a DRAFT record of the strongest
design the pilot found, and the reserved seeds stay unused:

- train 8600-8719 and held-out 8720-8839, under `IMMUNE_SPLITS["cycle-7"]`;
- 8840-9199, under `P8_RESERVED`.

**What the pilot established:**

- **There is real headroom.** Fixed full-whitening configurations taken from cycle 2's record beat the incumbent
  295-165 and 300-157 on 540 review items.
- **The frozen search does not find that headroom.** It picks high `alarm_fraction` configurations, which win paired
  items but make 4-6 false-alarm violations per 540 items.
- **Under the unchanged rule, a single wrong answer decides the outcome.** One wrong answer makes a held-out mean
  infinite, and an infinite mean cannot be lower. P(RETAIN) falls as the held-out split grows: 0.22 at 120 items and
  below 0.01 at 480.
- **The adversarial gate was blind to added wrong answers.** When the incumbent itself had a wrong answer, a candidate
  with more of them still passed. That defect is fixed in this branch (`stress_worsened`, with a regression test); no
  recorded decision changes.

**Options that remain, all outside this branch:**

1. **A different target.** It needs a declared configuration space and fresh data. `forecast_quantile` has no unused
   M4 series, and new data are blocked by the network policy.
2. **A narrower immune search space.** This draws on what the pilot saw, so it needs a fresh declared pilot on unused
   review seeds.
3. **A change to how `RULE` treats wrong answers at the held-out gate,** for example counting wrong answers and the
   loss of answered items separately. `RULE` is shared by every target and is frozen in every pre-registration, so
   this is the founder's decision. It is recorded as an open question, not made here.
