# Representation repair on a real decision: pre-registration (2026-11-12)

Written and committed before any code for this pilot exists, before the withheld cases exist, and before any
arm has run on them. Nothing below is changed after a result is seen; a deviation is added as a dated, labelled
section and never edits a threshold.

## Why this pilot, and what came before

The founder, 2026-11-12: "Preserve the representation-repair failures. Neither pilot beating the baseline is
valuable negative evidence. Now connect the experiment to a real decision problem within the developmental
workflow. ... Was a request rejected because the applicant was ineligible, because evidence was missing, or because
the system applied the wrong rule? ... Declare the baseline, evaluation budget, withheld cases, and success
conditions before the next pilot. Test whether the additional reasoning improves final decisions enough to justify
its cost. If the simpler method continues to win, retain it for that task."

Preserved in this folder, unchanged:

- `DESIGN-2026-11-11-fault-isolation.md`: the compile-route design (families D, change alarm; C, treat or not).
- `dev-pilots/pilot_c.py`, `dev-pilots/pilot_d.py`: the dev pilots (seeds 0-9, scratch namespace).
- Their results, as the design recorded them (dev items only; no withheld run was made):
  - D, total loss (lower is better): fixed 8174, always-general 5372, both-alarm 5192, hand-built robust rule 4192,
    repair 4906. **The simple hand-built rule beat repair.**
  - C, correct/undecided/wrong: fixed 34/5/21, general 30/12/18, conservative 34/16/10, late half 43/1/16,
    repair 49/1/10. All ten remaining wrongs are drift at 85%, where every arm is wrong. A better count than every
    arm, on dev items written by the design's author; not a withheld result.
  - Variance shift: every arm false-alarms.
  - Strongest objection, recorded then and kept: the frames, checks and planted faults came from one author.

## The decision

The operational slice (`case.assess`, branch `claude/operational-slice-request-case-20261112`) decides, for a
request to be paid for completed work: `eligible`, `ineligible`, `undetermined` (no rule failed, some unknown),
`disputed`, or `duplicate`, and routes it. The decision that matters to the participant is an **exclusion**:
`ineligible` declines the request.

A request can be declined for three different reasons that look alike in the output:

1. **ineligible in fact** (a rule genuinely fails);
2. **missing or unreadable evidence read as failure** (a fact the rule needs was absent, and the evaluation
   treated absence as a failing value);
3. **the wrong reading of a fact** (the evidence is present, but the evaluator read it under a wrong assumption:
   a date in another format or time zone, an amount with a thousands separator or another currency, a reference
   with different padding or case, a percent written as a fraction, a signature line read as unsigned).

Reasons 2 and 3 are **wrongful exclusions**. The participant bears their cost (a valid request declined); the
founder's doctrine names "fewer wrongful exclusions" as a participant benefit.

The mirror error is a **wrongful approval**: `eligible` where a rule genuinely fails, typically because a lenient
reading made a failing value pass.

## Arms (all run on every withheld item)

- **A0, fixed reading (baseline):** `case.assess` as built and reviewed on the slice branch, with its rulebook, one
  reading per fact. Frozen at the slice's reviewed commit, named in `freeze-v1.json` before the run.
- **A1, conservative:** A0, but any fact that any extractor could not parse with full confidence is `unknown`;
  any rule that needs it is `unknown`. Never repairs; can only move `ineligible` toward `undetermined`.
- **A2, deterministic normalization (the simpler alternative):** one fixed normalization layer before A0 (dates to
  ISO in the document's declared zone, amounts to minor units with the declared currency, references
  case-folded and stripped, percent forms unified). No diagnosis, no alternative readings.
- **A3, representation repair:** for each fact a rule uses, at most three declared readings; when the rule's state
  differs across readings, the repair names the assumption that separates them and keeps the reading whose
  declared checks hold on the document's own content (for example, the date format consistent with every other
  date in the same document, the currency stated on the document). If no reading is supported by a check, the
  rule is `unknown` with the assumption named. Implemented inside `case.assess`'s evaluation, not as a new
  subsystem, registry, ledger or entry point. Its receipt names each assumption tested and its verdict.

## Withheld cases

- 60 cases, written by a worker who has not seen any arm's implementation, from the founder's path description,
  the slice's published rulebook format and the case-1 document kinds only. 20 per stratum:
  - **S1 genuinely ineligible** (a rule truly fails; some with an ambiguous-looking but correctly readable fact);
  - **S2 missing or unreadable evidence** (truth: `undetermined`, the missing facts named);
  - **S3 wrong-reading traps** (truth: `eligible` or `ineligible` as the document actually says, with one fact
    written in a form a naive reader misreads).
- Labels (eligibility, deciding rule, missing facts) are written by the same worker from the documents by hand,
  before any arm runs, and frozen with a sha256 recorded in `freeze-v1.json`.
- Not read by the builder of A3 until after the run.

## Measures

- **M1, wrongful exclusions:** items labelled `eligible` or `undetermined` that the arm declares `ineligible`.
- **M2, wrongful approvals:** items labelled `ineligible`, `undetermined` or `disputed` that the arm declares
  `eligible`.
- **M3, unknown reported as pass or fail:** items where a fact the label marks missing or unreadable is used by
  the arm as a value (`met` or `not_met`). Any count above zero is a defect in that arm, reported separately.
- **M4, exact decision:** eligibility equal to the label.
- **M5, cost:** median and maximum wall time per case on this machine, and the product lines each arm adds over A0
  (`git diff --stat`, outside tests and fixtures).
- **M6, intervention:** founder asks raised per case.

## Promotion rule (fixed now)

A3 is promoted for this task only if, on the 60 withheld items:

1. M1 + M2 for A3 is lower than for **every** other arm, by at least 3 items against A2;
2. M3 for A3 is 0;
3. M4 for A3 is at least A2's;
4. A3's median wall time is at most 3x A0's;
5. A3 has no item worse than A0 in stratum S1.

If A2 meets or beats A3 on 1 and 3, **A2 is retained for this task** and A3 is recorded as not justified here,
with its per-stratum results. If A1 beats both on M1 + M2, A1 is retained. A tie keeps the arm with fewer product
lines. Whatever the verdict, the compile-route design above stays preserved and unattached.

## Budget

- One run, one machine, in a clean worktree at the frozen commits. No re-run after seeing results except to report
  a crash, which is labelled as such.
- Building A1-A3 and the case generator: at most one build pass and one independent review pass.
- Cost of the pilot is reported (wall time, agent runs used).

## Not claimed

- That the withheld cases describe any real payer, document or industry practice.
- Generality beyond request-led eligibility decisions.
- Any external validation, payment or participant outcome.

## Order

1. This file, committed first (this commit).
2. The slice's reviewed commit is named in `freeze-v1.json`; the withheld cases and labels are written and their
   digests frozen there.
3. A1, A2, A3 are built against A0; reviewed once.
4. One run; `RESULT.md` with the five measures per arm and stratum, the verdict, and every deviation.
