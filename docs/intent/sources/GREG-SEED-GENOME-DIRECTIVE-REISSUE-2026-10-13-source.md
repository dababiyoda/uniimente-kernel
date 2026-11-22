# Founder re-issuance of the Seed Genome build directive — 2026-10-13 (lineage)

Provenance: Alfonso's message in Claude Code session `session_0174qtqgRsbJVdBkBitTyxkf`, transcript timestamp
2026-10-13T18:51:08Z. It arrived after #161 and #162 were reported. The message was extracted byte for byte
from the session transcript, not retyped. Founder language is preserved here as source lineage; it is not
cryptographic founder authentication and creates no runtime authority.

## What the message contains

1. **New opening line, verbatim:**

   > Build this prompt meet and exceed all in this prompt:

2. **A blank line, then the full Seed Genome build directive, byte-identical to the preserved text.**
   The remainder of the message has SHA-256 `3a18620e43e3e38496ad916a5426591e56ce78d6c915f71cc73b4a793cc8d342`
   (87,094 characters). That is the digest of
   [`POLYINTELLIGENCE-SEED-2026-10-01.txt`](POLYINTELLIGENCE-SEED-2026-10-01.txt), which is also the source of
   `docs/cortex/SEED_GENOME_REQUIREMENTS.json`. A line diff against that file is empty. The same text is also
   kept, with its provenance header, in
   [`GREG-SEED-GENOME-DIRECTIVE-2026-10-01-source.md`](GREG-SEED-GENOME-DIRECTIVE-2026-10-01-source.md).

The whole message has SHA-256 `ee71d7de66adad8ce5ace61ee05c0b9329b01e09f2e757e047d4eadf2effc6e1` (87,149 characters).

## How it is applied

The directive was already the controlling source of `INTENT-20261001-greg-seed-genome`, and its requirements
were already mapped line by line. Re-issuing it adds the instruction to meet and exceed all of it. This is
applied by working through the section residuals the requirement map records, on the canonical path. It is not
applied by rebuilding a parallel cortex, which §2 and §3 of the directive forbid. The residual work of this
re-issuance is recorded in `tests/evidence/seed-genome-residuals-2026-10-13/`.

## Repeated 2026-10-14

Alfonso sent the same message again in the same session, at transcript timestamp 2026-10-14T04:59:45Z. It was
extracted from the transcript the same way. The whole message has the same SHA-256,
`ee71d7de66adad8ce5ace61ee05c0b9329b01e09f2e757e047d4eadf2effc6e1` (87,149 characters): opening line and
directive are both byte-identical to the 2026-10-13 message. A transcript entry at 2026-10-14T00:52Z also
contains the directive text, but it is the session's compaction summary, not a founder message, and is not
counted.

Repetition creates no additional authority and changes no requirement. It is applied the same way: by closing the
next residual the requirement map records. This time that is §12, the decision-aware thinking budget on the
compile path (`greg/cognition/budget.py`), recorded in `tests/evidence/seed-genome-residuals-2026-10-13/`.

## Repeated 2026-10-15

Alfonso sent the same message a third time in the same session, at transcript timestamp 2026-10-15T12:21:07Z. It
was extracted from the transcript the same way: the user entries whose text opens with "Build this prompt" and
contains the directive. There are exactly three, at 2026-10-13T18:51:08Z, 2026-10-14T04:59:45Z and
2026-10-15T12:21:07Z, and all three have the whole-message SHA-256
`ee71d7de66adad8ce5ace61ee05c0b9329b01e09f2e757e047d4eadf2effc6e1` (87,149 characters). Compaction summaries that
quote the directive are not founder messages and are not counted.

Repetition creates no additional authority and changes no requirement. It is applied by closing the next residual
the requirement map records: §16's media case, truth-preserving paraphrase against source evidence, recorded in
`tests/evidence/media-case-convergence-2026-10-15/`.

## Repeated 2026-10-15, with a new opening line

Alfonso sent the directive a fourth time, at transcript timestamp 2026-10-15T17:32:27Z, prefixed by a new opening
line and a blank line:

> Continue building, and achieving EVERYTHING IN THE PROMPT:

The whole message has SHA-256 `9b9eed0c126ff343d388ce0870a5f665330bf9dc1f6c0d3d7a71684797187c1f` (87,209
characters). Everything after the prefix is byte-identical to the three earlier messages (SHA-256 `ee71d7de…`). It
was extracted from the transcript the same way.

The new line asks for continued building; it creates no authority and changes no requirement. It is applied by the
next residual: §14's antifragility test, with stress, a frozen holdout, a pre-stress twin and a no-learning
control. That test found that settled competence never heard failures, and the fix makes it hear them
(`tests/evidence/antifragility-2026-10-15/`).

## Repeated 2026-11-22

Alfonso sent the directive again in Claude Code session `session_01CLMsAqMfeDxCT9iN1dnaMh`, at transcript
timestamp 2026-11-22T13:51:48Z, opening "Build this:" and followed by the goal-set quotations, the founder's
interpretation paragraphs and both review passes. It was extracted from the session transcript, not retyped. The
whole message has SHA-256 `a1f3efcaac7edcbb39e942cbbf2358a2d378092a26633938b97ca646fb873e56` (97,218
characters). Each of its 303 paragraphs longer than 80 characters already appears, whitespace-normalized, in
the preserved sources of this directory: almost all of it in
[`POLYINTELLIGENCE-CORTEX-REVIEW-PASS-1-2026-09-30.md`](POLYINTELLIGENCE-CORTEX-REVIEW-PASS-1-2026-09-30.md) and
[`POLYINTELLIGENCE-CORTEX-REVIEW-PASS-2-2026-09-30.md`](POLYINTELLIGENCE-CORTEX-REVIEW-PASS-2-2026-09-30.md).
No new text is copied here.

Repetition adds no authority. It was applied by closing the SG-A42 residual (sections 35 and 42 of the reviews:
"an opponent must attack a specific assumption, evidence item or inference rather than dismissing an opaque AI
conclusion"). A response to an evidence package can now name the committed claims it addresses, and
`greg cognition challenges <holder.json>` shows, per claim, who contests it and on what grounds. The same work
corrected SG-B63: the eight corrections it said were missing are section 63 of the second review pass.
