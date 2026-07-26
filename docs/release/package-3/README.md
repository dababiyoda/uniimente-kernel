# Package 3 — document index

Governed functional replacement of a specialist component, on
`release/canonical-v1` @ `cb234faf932d239d79b0e7ab28e54f576b8a15bf`.

Read in this order.

| Document | Status | What it is |
|---|---|---|
| `PLAN.md` | **superseded, preserved verbatim** | The pre-approval plan, exactly as written on branch `package3/plan` @ `5a1f744`. Its header still says "PLAN ONLY. NOT AUTHORIZED" because that was true when it was written. |
| `EXPERIMENT_SPEC.md` | **frozen** | The human-readable frozen experiment. Machine form: `evolution/repair/spec.py`, seal `6f6d7dab…c4ab7f4a`. |
| `RESULTS.md` | **final** | What actually happened, including two failed predictions. |
| `EVIDENCE_RECORD.json` | **generated** | Full machine record. Regenerate: `python -m evolution.repair`. |

## Why `PLAN.md` is not edited

Its header is now stale — implementation *was* subsequently authorized. It is
preserved unmodified anyway, at sha256
`e820662db9f821fca672cfa2589ce16612eeefc227d6027f1d7b1723821e57b3`, identical to
`package3/plan:docs/release/package-3/PLAN.md`. Rewriting a historical document
to match a later decision falsifies the record; the correction belongs in this
index instead. Same discipline as the Package 2 protected historical record.

## Two corrections the plan received before implementation

1. **The threshold.** `PLAN.md` §6 wrote the success condition as *"≥90% of
   measured function restored: ≥4 of 4 exact edge triples."* That phrasing is
   internally ambiguous — on a four-item target, 90% would admit 3/4, which is
   75%. The founder's correction: **four exact edges means 4/4, and 3/4 is a
   failure, not a ninety-percent pass.** The frozen spec encodes the exact
   fraction and `test_four_of_four_is_the_threshold_and_three_of_four_fails`
   asserts `resolves(0.9) is False`.

2. **The "missing mechanisms."** `PLAN.md` §7 listed four items under
   *"Missing — must be built."* The founder's correction: these are small
   connectors and test controls, not new architecture. They landed as four thin
   adapters — `disable.py`, `detector.py`, `candidate.py`, `cost.py` — around
   machinery that already existed. No second Foundry, morphogenesis engine,
   recovery framework, authority system, memory system, or governance layer was
   created.

## What the plan predicted, and what happened

The plan recorded predictions before implementation so that being wrong would be
visible. It was wrong twice, and both are reported in `RESULTS.md`:

- **R3 predicted to "fail or place last" on function.** It scored 1.0 on all
  five corpora. At full reachability the local rule's "no producer among cells I
  have heard from" coincides exactly with the global negative.
- **R2/R3 repair-cost ranks swapped** (predicted 3/4, actual 4/3).

The plan's central expectation *did* hold: **restoring the original is the
cheapest and safest repair, and structural replacement bought nothing here on
cost.** The plan said in advance that this would be the honest conclusion if it
happened, and it happened.

## Lineage

- Plan branch: `package3/plan` @ `5a1f744` (pushed, retained)
- Implementation branch: `package3/governed-functional-replacement`
- `linker/` is byte-identical to the base commit and is never deleted — permanent
  benchmark, strongest conventional repair, rollback target.
