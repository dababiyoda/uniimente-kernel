# Founder expression — Polyintelligence Cortex — 2026-10-01

PROVENANCE HEADER (not part of the quoted text)

- Source: chat session https://claude.ai/code/session_0174qtqgRsbJVdBkBitTyxkf, one founder message received
  2026-10-01 (transcript timestamp 08:46:25Z). The stable conversation ID is the session URL above.
- Authority: a faithful transcription of founder expression. It is not cryptographic authentication of the
  founder and creates no runtime authority (`docs/FOUNDER_INTENT_LEDGER.md`, SR-INTENT-3).
- Shape: the message is a short preface followed by the full two-pass review, pasted again.
- Rule: nothing between BEGIN and END may be edited. A correction is a new file that supersedes it.

## Preface (verbatim)

=== BEGIN VERBATIM TEXT ===
FOLLOW ALL INSTRUCTIONS VERBATIM MEET THE  LEVEL EXPRESSED IN THIS PROMPT  AND EXCEEED MY EXPECTATIONS. Be an over achiever. Think deeply and thoroughly learn and understand the entire egregore project. NOTHING IS DISCONNECTED, everything is modular and part of the whole. It is the interconnectedness of all things that culminate in the complete product describes in all that exists inside the GitHub that is your context.
=== END VERBATIM TEXT ===

The doubled space in "MEET THE  LEVEL" and "IN THIS PROMPT  AND", and the spellings "EXCEEED" and
"describes", are preserved as written.

## The re-pasted review: comparison with the preserved passes

The rest of the message is the review already preserved in
`POLYINTELLIGENCE-CORTEX-REVIEW-PASS-1-2026-09-30.md` and `POLYINTELLIGENCE-CORTEX-REVIEW-PASS-2-2026-09-30.md`.
It is not copied a third time. Instead, the exact differences are recorded so the whole message can be rebuilt
byte for byte from the files already in the repository.

| Location | Preserved text | Text in this message |
| --- | --- | --- |
| Pass 1, line 1 | `I reran the review from the project sources, …` | `In the review from the project sources, …` |
| Between the passes | one newline | one newline (the same) |
| Pass 2 | identical, 2,386 lines | identical, except that the message has no final newline |

Every other line of both passes is identical.

Rebuild rule, checked by `tests/unit/test_cortex_register.py::TestFounderExpression20261001`:

```text
message = PREFACE
        + "In the review" + PASS_1[len("I reran the review"):]
        + "\n"
        + PASS_2.rstrip("\n")
```

Here PREFACE is the text between BEGIN and END above, plus two newlines, and PASS_1 and PASS_2 are the texts
between BEGIN and END in the two review files.

- Characters in the message: 93,728
- SHA-256 of the message (UTF-8): `4432e84027fc906e9c0bb77e3c0d93be863f4fff17e9a5d515254c45cae768e8`

## How this message is read

- "FOLLOW ALL INSTRUCTIONS VERBATIM" and "EXCEEED MY EXPECTATIONS": read as PC-013 in
  `docs/collaboration/intents-polyintelligence-cortex-20260930.json`. Build every reserved family that can be
  built now, at a higher standard than before, and keep each consequence-inert and unpromoted.
- "NOTHING IS DISCONNECTED, everything is modular and part of the whole": the cortex gets an organ manifest and
  typed adapters, so the Institutional Linker can resolve its edges to DALEOBANKS, WealthMachineIntelligence and
  the Kernel. Resolving an edge is discovery; it grants nothing.
- The first line now reads "In the review" instead of "I reran the review". Nothing else in the review changed, so
  the existing dispositions in `docs/cortex/verbatim-register.json` still apply.
