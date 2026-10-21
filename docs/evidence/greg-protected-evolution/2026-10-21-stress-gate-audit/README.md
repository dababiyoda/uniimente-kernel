# P8 stress gate: independent audit of the wrong-answer repair, 2026-10-21

- **Audited:** `239a87f`. The repair under review is `b7b1ed9` (merged in `32246ee`): `stress_worsened` and the inline wrong-answer block in `cycle()`.
- **Directive:** `docs/intent/sources/MIND-MAXIMUM-CONTINUATION-2026-10-21-source.md`, section 3.
- **Reviewer:** a separate agent that did not write the repair.
- **Branch:** `audit/stress-gate`. Fixes are in `8498fd5` (pairing) and `3587fcf` (fail closed).
- **Not changed:** every original record, its decision and every file that existed under `docs/evidence/` at `239a87f`.

## 1. The historical claim

`b7b1ed9` claimed that "no recorded decision changes". Its test passed only the two recorded means, so it ran the old comparison through the `wrong is None` fallback. That proves nothing about the new branch (`test_the_means_only_form_never_reaches_the_wrong_answer_branch`).

**Method.** No per-item outputs were retained for any cycle, so every cycle was reproduced from train items, at its own source commit, in a detached checkout. `reproduce_stress.py` did the following:

1. Rebuilt the train items with that commit's generator.
2. Recomputed the train evaluator seal and required it to equal the record's.
3. Derived the stress sets with that commit's own stress function.
4. Ran the incumbent and the recorded candidate configurations through that commit's method. Data was round-tripped through JSON, as the sandbox did, and the sandbox's caught exceptions were treated the same way.
5. Scored the outputs with that commit's `SealedEvaluator`.

The 239a87f aggregation and `stress_worsened`, and the audited fix, were then applied to the per-item losses (`item_losses.json`).

**Results.**
- Every train seal equals its record.
- Every reproduced stress mean equals the recorded mean to all six decimals.
- No sandbox error occurred.

| Cycle | Source commit | Recorded gate / decision | Wrong answers (inc / cand) per set | Gate: old means rule | Gate: 239a87f | Gate: audited fix | Status |
|---|---|---|---|---|---|---|---|
| 1 forecast | `fe222f4` | PASS / REJECT (held-out) | short 0/0, shift 0/0 | PASS | PASS | PASS | RESOLVED |
| 2 immune | `ed4ee29` | REJECT / REJECT | scarce 0/1, strict 1/1 (both on `s7002`) | REJECT | REJECT | REJECT | RESOLVED |
| 3 cr | `5287303` | REJECT / REJECT | fewval 0/0, lean 0/0 | REJECT | REJECT | REJECT | RESOLVED |
| 4 cr | `2cbb43d` | PASS / REJECT (held-out) | 0/0, 0/0 | PASS | PASS | PASS | RESOLVED |
| 5 cr | `6fa98ff` | REJECT / REJECT | 0/0, 0/0 | REJECT | REJECT | REJECT | RESOLVED |
| 6 cr | `70bb77d` | PASS / RETAIN | 0/0, 0/0 | PASS | PASS | PASS | RESOLVED |

**The claim is verified for cycles 1-6, as reproduced from item-level data.**
- **Cycle 2 is the only cycle that reaches the item-level branch.**
  - On `strict`, both configurations give one wrong answer, on the same item (`s7002`).
  - On the 39 items both answered, the candidate's loss is lower: −0.233221 against −0.201329. The set passes.
  - `scarce` (0 against 1 wrong answer) rejects under every gate.
  - The record's `all_outputs_verified: false` came from a harness defect later fixed in `94d2295` (see `../2026-10-09/README.md`). The decision would still be REJECT if that flag were true.
- **In cycles 1 and 3-6 no stress loss is infinite.** The new code takes the same path as the old one.

**Regenerated (all of them train splits that their cycles had already exposed):**
- cycle 1: 100 M4 weekly train series. The pool file was loaded and shuffled, as `forecasting_split(808)` did at `fe222f4`, but only the train half became items.
- cycle 2: immune seeds 7000-7039.
- cycle 3: CR seeds 7200-7259.
- cycle 4: CR seeds 7400-7459.
- cycle 5: CR seeds 7600-7659.
- cycle 6: CR seeds 7880-7999.

**Never generated or scored:** any held-out item. This includes 8000-8059, 7300-7389, 7500-7589, 7700-7879, 8060-8299, the canary seeds 8300-8539 and the cycle-7 immune split 8600-8839. `reanalysis.json` gives each cycle's method, inputs and verdicts.

## 2. Semantics checked with hostile cases

`probe.py` runs 22 cases. `probe-at-239a87f.txt` holds the output against the verbatim inline aggregation; `probe-at-3587fcf.txt` holds it after the fixes. To reproduce:

    python -B docs/evidence/greg-protected-evolution/2026-10-21-stress-gate-audit/probe.py .

| Check | Finding at 239a87f |
|---|---|
| Wrong, abstain, finite | Score maps "wrong" to +inf. An abstention is finite: immune 0.0 (equal to a correct answer with F1 0), CR 1.0, forecast 1e6. A sandbox exception becomes a missing output and is scored as an abstention. |
| Pairing | Correct in `cycle()` only because both loss maps come from one `SealedEvaluator` in one order. `zip` paired by position, and `startswith(kind)` mixed a kind with any kind it prefixes. The current kinds (short/shift, scarce/strict, lean/fewval) do not collide, so these were latent. **Fixed** in `8498fd5`. |
| Equal and fewer wrong answers | Behave as documented. More wrong answers rejects. Fewer wrong answers passes, whatever the answered items show. Equal counts compare the both-answered means. |
| Empty sets, `both_answered == 0` | A kind is derived from item keys, so a set is never empty. Equal counts with no item both answered PASS. |
| NaN, -inf, malformed | All **failed open**: NaN items or means, a -inf mean, negative counts and NaN answered means passed. A -inf incumbent item counted as a "wrong answer". +inf with -inf raised `ValueError`. None answered means raised `TypeError`. The old means-only gate shared the NaN and -inf holes. **Fixed** in `3587fcf`. |
| Rounding and `None` | Means are rounded to 6 dp before the decision, as before the repair. Below about 1e-4 a 22% worsening can round to equality (case 21-22); the recorded loss scales (0.005-1) are unaffected. `None` means occur only with `both_answered == 0`, which short-circuits. |
| Monotonicity | On 20,000 random well-formed sets the 239a87f gate rejects every set the old gate rejects, plus 3,277 more. It never relaxes. |
| Documented `RULE` | It still reads "no stress set worsens by > 5%". The executable gate also orders by wrong-answer count with zero tolerance, then compares both-answered means. See P5. |

## 3. Policy changes, not faithful implementation (for founder review; not decided here)

- **P1 — zero tolerance on wrong answers.** One more wrong answer than the incumbent rejects, whatever the set's size; finite losses get 5%. Under the documented rule, any set where the incumbent already had a wrong answer had an infinite mean, so `worsened` never fired. The cycle-7 pilot README called this "a property of the frozen rule … reported, not changed" (`../2026-10-21-immune-7/pilot/README.md`); `b7b1ed9` then changed it. Elsewhere the project uses the same zero-tolerance ordering (`genomes/admission.py`: `c["wrong"] > b["wrong"]`).
- **P2 — a new statistic for equal counts.** With equal counts the gate compares means over the items *both* answered. That subset drops every item either side got wrong, even when the two got different items wrong. With disjoint wrong items and nothing else (`both_answered == 0`) the set passes, and the candidate's loss on the item the incumbent got wrong is ignored (cases 5-6).
- **P3 — fewer wrong answers dominate.** A candidate with fewer wrong answers passes however much worse its answered items are. That includes abstaining on every item when the incumbent had one wrong answer (case 1). The old rule passed these cases too, because an infinite incumbent mean beats any finite one. The repair keeps the behaviour and states it as policy ("Fewer wrong answers is better").
- **P4 — abstentions and crashes are never "wrong".** They lower the wrong-answer count and are judged only through finite means. The cost of an abstention differs by target (immune 0.0, CR 1.0, forecast 1e6).
- **P5 — documented rule versus executable gate.** `RULE` is unchanged, and it is part of every freeze and every evaluator seal. Bringing the text into line with the gate, or the gate back to the text, is a freeze-affecting decision.
- **P6 — failing closed (the audit's own fix, `3587fcf`).** A set holding a NaN or -inf loss now rejects, even when the bad value is on the incumbent's side. This reads "no stress set worsens" as requiring a rankable comparison. Recorded data never contains such a value.

**Related observation.** `scripts/p8_immune_pilot.py` still simulates the gate with means-only `worsened`. So the pilot's P(RETAIN) figures describe the pre-repair gate. The repaired gate only adds rejections, so its NOT_VIABLE verdict cannot become more favourable; its numbers are an upper bound.

## 4. Fixes (each with regression tests that fail at 239a87f)

- **`8498fd5` — `stress_summary()`.** Items are grouped by exact kind, paired by key, and unpaired maps are refused (`STRESS_UNPAIRED`). On well-formed aligned input its output equals the inline 239a87f output: tested on 3,000 random sets and on all six reproduced cycles.
- **`3587fcf` — fail closed.** Only +inf counts as wrong. A NaN, -inf or non-numeric loss makes its set `malformed`. `stress_worsened` rejects any malformed set, NaN or -inf mean, invalid count, or non-finite answered mean. The +inf/+inf fallback for records without item data is unchanged.
- **Historical test replaced.** `test_every_recorded_stress_decision_is_unchanged_on_reproduced_item_level_losses` runs the gate on `item_losses.json`. It requires the reproduced means and train seals to equal each frozen record, and requires the item-level branch to run (cycle 2).

**Effect on freezes.** Any change to `greg/cognition/evolution.py` changes the trusted-code digest. A freeze written before these commits will refuse to run (`FROZEN_INPUT_CHANGED`); no uncommitted cycle freeze existed at `239a87f`.

## UNRESOLVED

None for cycles 1-6.

**Could not verify:**
- That the in-process run equals the confined sandbox run byte for byte. Equal means on every set are strong evidence, but they are not proof per item.
- Cycle 2's per-item verification flags under the current verifier. They were not re-checked, and the decision does not depend on them.
