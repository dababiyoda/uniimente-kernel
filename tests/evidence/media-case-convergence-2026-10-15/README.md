# Section 16 media case on the converged Mind — 2026-10-15

Directive section 16: "DALEOBANKS may consume cognitive results for truthful research, multilingual explanation,
and audience feedback ... A media case can test truth-preserving paraphrase against source evidence ... Never
publish, message others, spend, or activate live accounts solely to demonstrate integration."

**Lineage:** applied on the third byte-identical repeat of the Seed Genome directive (2026-10-15T12:21:07Z, the
same whole-message SHA-256 `ee71d7de…`), recorded in
`docs/intent/sources/GREG-SEED-GENOME-DIRECTIVE-REISSUE-2026-10-13-source.md`.

## The defect, reproduced first (`reproduction.log`)

At the base `1530d24`:
- GREG's evidence family accepted a declared `supports` binding without comparing the claim with its span. Its
  own limitation said so: "span binding is not entailment".
- DALEOBANKS's `daleobanks.verify` checked only that each figure appears in the source.

A paraphrase that dropped a hedge, removed a negation, widened a scope or reversed a direction passed both, as
answered and VERIFIED. No search of the other branches found an existing media case to carry, so this one is built.

## What was built (`9f7dac8`)

- **The Mind** (`greg/cognition/evidence.py`). A conservative refuter compares a claim with its supporting spans
  for six kinds of change, and the receipt says that finding none is not entailment:

  | Class | Detects |
  |---|---|
  | figure | numbers and percentages, spelled-out ones from two up included |
  | negation | explicit negators, plus "failed to" and "unable to" |
  | certainty | a dropped hedge, or a stronger word |
  | scope | universal quantification the spans do not state |
  | direction | up against down |
  | named term | a capitalised name the spans do not contain |

  - A change makes the claim ABSTAIN with DISTORTION.
  - A claim given only `context` spans ABSTAINs with INSUFFICIENT_EVIDENCE.
- **The verifier** (`greg/cognition/verification.py`) rechecks figures and polarity with separately written code.
  An answer that reports no change where one exists is REFUTED. It stands aside on figures when the spans spell
  their numbers out; that reading is the solver's, and the verifier reads digits only.
- **The organ** (`greg/daleobanks_bridge.py`).
  - **With the Mind's receipts:** `daleobanks.verify` requires every sentence of the draft to be a claim the
    evidence family answered as written. A receipt from another family vouches for nothing, and a sentence no
    receipt covers is held back.
  - **Without them:** it now says that meaning went unchecked (`truth_preservation.checked: false`). The figure
    check alone is unchanged, because the existing `daleobanks_post` mission relies on it.
  - **Ledger access:** it reads receipts through the venture case's `LedgerReader`, which exposes `by_type` and
    nothing else.
- **The mission** (`greg/templates.py`, `daleobanks_paraphrase`). One signed mission:
  - one `cognition.solve` evidence receipt per claim, then `daleobanks.verify` over the whole draft;
  - read-only, with no publish capability in its light cone;
  - a distorted draft closes BLOCKED with the Mind's reason.

## On the real DALEOBANKS checkout (`real-daleobanks-missions.log`)

The DALEOBANKS checkout `a8341ba` was read only, and its own EthicsGuard, Critic and PromptFirewall ran in their
own process. The source is a synthetic three-sentence summary.

| Draft | Mission | daleobanks.verify | DALEOBANKS's own checks | The Mind's finding |
|---|---|---|---|---|
| faithful (two claims) | ACHIEVED | VERIFIED | pass | none |
| hedge dropped | ACTED → BLOCKED | REJECTED | pass | c1: certainty |
| negation removed | ACTED → BLOCKED | REJECTED | pass | c2: negation |
| scope widened | ACTED → BLOCKED | REJECTED | pass | c1: scope |
| direction reversed | ACTED → BLOCKED | REJECTED | pass | c1: direction |
| name substituted | ACTED → BLOCKED | REJECTED | pass | c1: named term |

DALEOBANKS's own checks passed every distorted draft. What held them back is the Mind's check, consumed through
a shared contract.

A side finding: DALEOBANKS's Critic marks "maybe" and "perhaps" as `too_vague`, so its quality gate leans toward
dropping uncertainty. The two gates now pull against each other on that point. A draft that keeps its source's
"may" satisfies both.

## How far the check goes (`characterization.log`)

Twelve faithful rewordings and ten distortions, all written by the author of the check:
- **False positives:** none of the 12 faithful rewordings is flagged.
- **Distortions caught:** 8 of 10. The two misses are outside the checked classes: a change of magnitude
  ("large" for "small") and polarity carried by an antonym ("rejected" for "approved"). Those need an entailment
  model or a person.
- **Not a benchmark:** the set was used for development. Its first run found three defects, all fixed before
  commit: "each" for "all" flagged as scope, a name at the start of a sentence missed, and "failed to" against
  "did not" flagged as negation. It also showed that a spelled-out figure was invisible to the figure check.
- **The case set grew once:** the spelled-out-figure case was added after the first run.

## Verification

- `media-tests.log`: 25 passed with the real checkout set (`GREG_TEST_DALEOBANKS`); without it the real-organ test
  skips.
- `mutants.log`: 35 of 35 caught. Seven target this case:
  - the claim is not compared;
  - a dropped hedge goes unnoticed;
  - polarity is not compared;
  - the verifier trusts the reported changes;
  - DALEOBANKS ignores the Mind's answer;
  - an uncovered sentence passes;
  - DALEOBANKS gets the writable journal.

  The venture mutant whose target line changed was updated, not dropped.
- **Reproduction scripts:** `reproduce.py`, `missions.py` and `characterization.py`. Run them from the repository
  root.
- `full-suite.log`: the whole suite at `9f7dac8` gave 3814 passed, 5 failed, 24 skipped. The five are the environmental Landlock
  tests, which fail identically at the pristine base with this interpreter and pass in CI.

## Not done

- multilingual explanation and audience feedback, which need a permitted local model;
- entailment itself;
- Task Fabric and worker leases;
- any live use.

Nothing was posted, sent or activated. Authority delta: DALEOBANKS's verify reads the Mind's receipts through a
handle with no write method. VEPMC: 0.
