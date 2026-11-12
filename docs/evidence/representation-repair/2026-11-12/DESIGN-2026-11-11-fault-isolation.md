**Design only. Nothing was built, committed or posted; the checkout is unchanged. Probes ran in-process on dev seeds 0-9 of scratch generators (namespace `repr-design-probe`); no withheld instance was generated.**

## What fails today (probed at 8d205324)

Two compile requests whose own data contradict their declared model return `ANSWERED`, verified, with only the generic evidence-type dissent:

- `detect_mean_shift` with a stale declared `mu0`: alarm at sample 8 where no change exists.
- `backdoor_ate` with a declared graph missing Z->T: ATE -0.83 where the true effect is +0.76, labelled `identified_by: backdoor criterion`.

Both are correct for the wrong problem.

## 1. Seam

- **Request:** unchanged. `cognition.reason({"problem_id", "compile": {"geometry", "data"}})` (cortex.py:193-199), `data` being one operation's native inputs. No new body key (compiler.py:1857).
- **New module** `greg/cognition/representation.py`, called only by the compile route. It holds a static `FRAMES` table keyed by operation (like `RECIPES`); no registry, ledger, entry point or journal write.
- **compiler.py, three edits**, copying the sensitivity pattern:
  1. One `OPERATORS` entry `representation_repair` (effect kind `evaluation`) that appends to `plan["evaluate"]`, as `_sensitivity` does (:195-198, :255-262). The operator loop records it in `transformations` (:1967-1972).
  2. One call beside the sensitivity call on the operation path (:2317-2320): `representation.compile_hook(chosen, data, inner, budget, rerun)`.
  3. One `selection_level` label, `repaired_representation`.
- **Budget:** the diagnosis is one optional step (`Controller.allot(required=False)`, budget.py:316-336). Probes run in-process through `library.run` and `library.check` (library.py:129, :150), the precedent of `condition_competence.shadow_trial` (:157-178): inert, recorded, never returned. A switched answer is re-run once through `reason` (worker, independent verifier, receipt).
- **Mode:** `MODE = "shadow"` by default (pattern: condition_competence.py:40). The receipt gains the record and `result` is unchanged. `"on"` (harness and tests) switches `result` and `selected_receipt` together, keeping settlement's contract (settlement.py:81-95).
- **Receipt gains** `representation_repair`: each representation (id, operation, input digest, recommendation, verified, each assumption with statistic, threshold and verdict), each intervention (kind, residual, or why not run), `signature`, `causes`, `separable`, `invalid_assumption`, `decision` (source, recommendation, fixed recommendation), probe count, `authority_created: false`; plus one dissent line.

## 2. A representation in code

```python
Assumption(assumption_id, kind, statement, test)   # kind: "assumption" | "formalization"
Representation(rep_id, operation, encode, decide, assumptions)
Frame(operation, representations, conflict, candidates, drop, split, corrupt, conservative)
```

- `encode(data)` is an exact declared transform to native inputs; `decide(output)` is a discrete recommendation.
- `test(data) -> {holds, statistic, threshold}` runs on the request's own numbers at a fixed alpha of 0.001.
- Today these are prose: `Operator.assumptions` (compiler.py:136), receipt `assumptions` (:1906), certificate text (solvers_c.py:1885), counterindications (control_b.py:915). Only `_premises_check` executes one (:2343).

## 3. One diagnosis procedure

Each intervention re-executes the decision; its residual is "the recommendation changed".

- **F** swap formalization, keep method: a rival representation of the frame.
- **M** swap method, keep formalization: the genome's `competitor(data)` (contract.py:128).
- **O** drop one observation: among at most 9 influence-ranked readings, exactly one whose removal changes the recommendation.
- **T** split in time: early and late parts disagree.
- **E** challenge the evaluator: the verifier that accepted the answer also accepts `frame.corrupt(answer)`, a decision-flipped copy.

| Cause | F | M | O | T | E | Also needed |
|---|---|---|---|---|---|---|
| observation | any | 0 | 1 | 0 | 0 | |
| environmental change | any | 0 | 0 | 1 | 0 | |
| assumption | 1 | 0 | 0 | 0 | 0 | a data-level check of the fixed representation fails on both halves |
| formalization | 1 | 0 | 0 | 0 | 0 | a structure-implied check fails |
| method | 0 | 1 | 0 | 0 | 0 | fixed answer verified |
| implementation | | | | | | fixed answer REFUTED (cortex.py:246-249) |
| evaluator | 0 | 0 | 0 | 0 | 1 | |

**Rows that are not unique:**

- Assumption and formalization share one row. Only the declared kind of the failing check separates them; with no failing check both are returned.
- Implementation and a wrongly rejecting evaluator share the REFUTED outcome.
- Observation and environmental change coincide when the indicted readings are the latest ones.
- A consistently wrong evaluator gives the all-zero row.
- Two simultaneous faults match no row and are reported unclassified.

**Decision rule, fixed in the pre-registration:**

- Observation alone: the fixed representation without that reading.
- Environmental change alone: the frame's post-change representation.
- A named failed check plus a rival whose checks all hold: the rival.
- Method or evaluator: answer kept, dissent.
- No failed check: fixed answer kept, causes reported as a set.
- Failed check without a unique row: `frame.conservative`.

**Primitives changed:**

1. Fault-signature residual: from sensor-minus-model under a trusted plant model to a decision disagreement between re-executions. The model is itself a suspect column.
2. Delta debugging: the pass/fail oracle becomes "the recommendation changed", searched over influence-ranked readings only.
3. Mutation testing: from offline code mutants to an online mutant of the answer, aimed at the verifier.
4. Predictive check: a structure's implied independence or level, tested on early and late halves.

Alone, signature matrices cannot indict the model or the judge, differential testing says two runs differ but not why, delta debugging needs an oracle, and predictive checks choose no decision. Together they return a cause set and a repaired decision without ground truth.

**Probe finding that shaped it:** a gross reading produced no conflict between the two representations in 9 of 10 dev streams; in 8 both alarmed at or near it. Representation conflict alone misses common-mode faults, so O and T run on every framed request.

## 4. Families

**D: change alarm** (`detect_mean_shift`, DEFAULT).

- Fixed: declared `mu0`, `sigma`. Rival: self-starting, both estimated from the opening `max(30, T//8)` samples; the genome's counterindication names it (control_b.py:915).
- Disputed assumption: the declared in-control model describes the stream's opening. Test: z of the opening mean against `mu0`, on each half.
- Decision: alarm index or none. Loss: the genome's declared loss (`_cu_loss`, control_b.py:513-520).
- Strata: quiet, change (no fault); stale model, stale model then change (assumption); spike (observation); change inside the opening (environmental change that mimics a stale model); variance shift (no check covers it).

**C: treat or not** (`backdoor_ate`, DEFAULT).

- Fixed: declared graph and adjustment set. Rival: add every observed non-descendant of treatment; the genome's gate abstains when that set is invalid (solvers_c.py:1862-1865). Third: the fixed set on the late half of the rows.
- Disputed assumption: the declared graph is correct (:1885). Test: each independence from treatment the graph implies (`_dsep_moral`, :1767), checked in the samples.
- Decision: TREAT, DO_NOT_TREAT or UNDECIDED from the 95% interval. Truth: the sign of the generator's current effect. Order: correct > undecided > wrong, no weights.
- Strata: unconfounded, declared confounding, M-structure (no fault; the general set must abstain); missing edge (formalization); drift at half (environmental change); drift at 85%.

Rejected by probe: forecast-then-staff. Holt smoothing adapts to a level shift; full and truncated histories differed by 0-2 agents in the 8 dev cases with a shift.

## 5. Evaluation

- **Arms, on every item:** fixed representation (today's compile); always-general (the rival); always-conservative (`frame.conservative`); a hand-built robust rule (D: clip at 4 sigma, alarm only when both representations alarm; C: general set on the late half); always-late-half (C); repair (`MODE="on"` through the compile route).
- **Items:** D 7 strata x 20 (seeds 2100-2239), C 6 x 20 (2240-2359): 260 withheld, 100 of them in no-fault strata. New generators with their own PRNG namespace.
- **Why unspent:** no exposure or declared range in the ledger overlaps 2100-2399 (nearest 2001-2040 and 2600-2629), and the range is outside FORBIDDEN, the review range and the declared dev ranges (data_exposure_ledger.py:59-66). The builder claims the seeds on board #96 before the freeze.
- **Order:** PREREGISTRATION.md; then `cortex/evaluation/representation_repair/freeze-v1.json` with `dev_seeds`, `heldout_seeds` (parsed by the ledger, :756, :798) and code digests; then one run in a clean worktree. `vpl_metrics.validate_preregistration` (:221) plus a local check of arms, strata, thresholds and unspent seeds must pass first.
- **Thresholds per family:**
  - P1: repair beats the fixed representation, one-sided exact sign test on paired outcomes, p < 0.05.
  - P2: the same against always-general and always-conservative, Holm over arms.
  - P3: at most 1 no-fault item where repair is worse than fixed.
  - P4: on fault items whose fixed recommendation differs from the clean twin's, the cause list equals the planted class more often than always naming the family's most frequent class (exact binomial, p < 0.05); at most 10% of no-fault items carry a cause.
  - Cost: median compile latency at most 3x the fixed arm.
- **Verdicts:** GAIN = P1-P4 in both families and wins >= losses against the hand-built rule. GAIN_OVER_FIXED_REPRESENTATIONS = P1-P4 but the hand-built rule wins somewhere. NO_GAIN = P1, P2 or P3 fails in either family. The default stays `shadow` whatever the verdict.
- **Where repair is expected to lose (dev pilots, 70 and 60 items):**
  - D total loss: fixed 8174, general 5372, both-alarm 5192, robust rule 4192, repair 4906. Repair is expected to lose to the hand-built rule.
  - C correct/undecided/wrong: fixed 34/5/21, general 30/12/18, conservative 34/16/10, late half 43/1/16, repair 49/1/10. All ten wrongs are drift at 85%, where every arm is wrong.
  - Variance shift: every arm false-alarms.

## 6. Tests and mutants

`tests/unit/test_greg_representation_repair.py`; each fails on 8d205324 (no such receipt key).

1. Stale `mu0`: cause `assumption`, the check named; in `on` mode `result` is no alarm and `selected_receipt` is among the intermediate receipts.
2. Missing edge: cause `formalization`, the failed independence named, decision TREAT.
3. Spike: cause `observation` with its index; a real change is not explained by one reading.
4. Drift: `environmental_change`, decision from the late half.
5. No-fault requests: no cause, `result` byte-equal, no extra `reason` run.
6. An abstaining rival is not a conflict (M-structure).
7. Stub runners: method, evaluator, REFUTED and each non-unique set.
8. Shadow leaves `result` unchanged; a small budget records the diagnosis as not run.
9. No journal append; `authority_created` false.

Mutation gate `scripts/ci/check_representation_repair_mutants.py` on `mutation_harness.run`: conflict always false; a check always holds; O accepts any changing reading; T removed; first cause returned in place of the set; shadow leaks into `result`; `selected_receipt` not swapped; probes without allotment; a corrupted answer accepted; an extra run on no conflict; an abstention counted as conflict.

## 7. Objection and rejected alternative

**Strongest objection:** the frames, their checks and the planted faults come from one author. The run shows the procedure works where the failure modes were already known, and the D pilot shows a per-family robust rule does better there. Generality to a third, unseen operation is not measured. The variance-shift stratum tests only that repair does no harm on a fault no check covers.

**Rejected simpler alternative:** run both representations and abstain on any conflict. It names no assumption, decides nothing on every fault item (C pilot: 16 undecided) and misses common-mode faults. It is kept as the always-conservative arm and as the fallback for non-unique signatures.
