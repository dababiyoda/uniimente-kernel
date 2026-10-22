# Evidence soundness: a mission never closes on evidence it did not retain (proposed patch, 2026-10-22)

**Owner of the file:** the integration owner (`session_01FBS4KNJR59nSbdGbxo8Mbx`), who has claimed the
`greg/missions.py` seams. This session did not edit that file on any pushed branch. The patch is
`patches/missions-incomplete-evidence.patch`. It applies cleanly to #201 `fe82005` and to the integration tip
`abc7a55`. It supersedes the sketch in #96 comment 6333711200.

Directive of 2026-10-22, section VI: "GREG must never call a mission achieved because it inspected only part of
the relevant evidence."

## The defect, measured

`authority.bounded` keeps a receipt small in two ways:

- a long string becomes its first 16,384 characters, a SHA-256 and its length;
- a list keeps its first 1,000 items, with **no marker**.

`missions._field` unwrapped the first, and nothing knew about the second. `evaluate_predicate` then judged what
was kept as if it were the whole value. On `fe82005`, with a 22 KiB text file read through `fs.read` (not a PDF):

- **A forbidden phrase after 16 KiB:** `not_contains` passed, and the mission was **ACHIEVED on a false pass**.
- **A required phrase after 16 KiB:** `contains` failed. The engine blamed the read as a strategy that did not
  work, and the founder was never told the check could not be measured.
- **After a restart:** the replayed false pass stood.
- **A bound value:** `bound_value` would hand the next action the 16 KiB prefix as if it were the whole value.

## The change

The patch changes only `greg/missions.py`. `evaluate_predicate` keeps its `(bool, str)` signature, and
every caller (missions, appraisal, Goal Gravity) is unchanged.

- **`judge(predicate, output)` returns TRUE, FALSE or INSUFFICIENT.** `evaluate_predicate` passes only TRUE,
  and an INSUFFICIENT detail starts with `insufficient evidence: `.
- **What a kept prefix of a long string can prove:**
  - `contains` with a hit inside the prefix is TRUE;
  - `not_contains` with a hit is FALSE;
  - `equals` is decided exactly from the digest and the length;
  - `count_gte` is decided from the length;
  - a miss proves nothing and is INSUFFICIENT.
- **A list at exactly 1,000 items** may have been cut, so the same monotone rule applies to it. Receipts written
  before the patch are covered too. An index past item 1,000 is INSUFFICIENT, not absent.
- **An output that declares itself incomplete** (`"complete": false`, as `document.text` now does for a page with
  no text layer) proves only monotone facts in every field.
- **Only a genuine wrapper is unwrapped:** exactly `{prefix, truncated: true, sha256, length}`, with
  `length > len(prefix)`. A capability's own dict is not.
- **On the mission path,** an INSUFFICIENT observation is recorded as `sensor inconclusive (incomplete
  evidence)`. It joins the existing unmeasured-check path: re-observe, back off, and after three misses ask the
  founder through SENSOR_FAILURE. No strategy is blamed.
- **`bound_value` refuses to bind a kept prefix** as the whole value.

## Evidence

- **`tests/unit/test_greg_incomplete_evidence.py`, 22 tests.** They cover the directive's hostile list:
  - before and after 16 KiB, required and forbidden;
  - a match spanning the boundary;
  - a complete or a truncated miss;
  - equality, complete and truncated;
  - Unicode counted in characters and digested in UTF-8;
  - empty outputs and a forged wrapper;
  - a long non-PDF output;
  - restart and replay, then complete evidence closing the mission;
  - no false ACHIEVED.
- **Fail-before:** the three mission-path tests fail on the unpatched engine (`fe82005`) and pass with the patch.
- **Regressions:** `tests/unit/test_greg_missions.py` plus the new file: 35 passed on the integration tip
  `abc7a55` with the patch applied. The wider GREG, mission, appraisal and Gravity selection on `fe82005` with the
  patch: see the #96 handoff for the count.

## What it does not do

- **INSUFFICIENT is not a third state on the wire.** The Boolean interface refuses positive closure and records
  why. A typed tri-state verdict would be a shared contract change, the integration owner's to make.
- **Human-refusal watches** (`_watch_refusal`) receive `passed=False` on insufficient evidence. A refusal phrase
  past 16 KiB would therefore be missed, not honoured. This is safe for closure but not for the person. The owner
  may want insufficient evidence on a refusal watch to stop and ask.
- **A capability that lies about its own output** (a forged digest) is not detected here. That is the
  appraiser's and the oracle's job.
- **There is no general full-value predicate service.** `document.text`'s `phrase` parameter is the
  whole-document path for PDFs. For other long outputs the sound route is the same pattern: the capability
  answers the question over the whole value and the receipt keeps the answer.

## Follow-up: fields a capability declares decided (review finding 2b), 2026-10-22

**Observed in CI.** The integration owner applied the patch on #196 at `3d2f9cc4`. #201's CI runs on its
merge with #196, so it now has both the patch and `document.text`'s coverage report. Canonical CI job 6 on
`09b60e2` (run 39737759626) then failed
`test_a_phrase_found_on_a_text_page_of_a_partly_scanned_pdf_is_still_found`. The recorded observation was:

    sensor inconclusive (incomplete evidence): insufficient evidence: True == True;
    the capability reported its observation incomplete

The judge treats every field of an output with `"complete": false` as monotone-only, so `found == True` is
INSUFFICIENT. A phrase found on a page that has text is in the document, whatever the scanned pages hold.
The mission therefore waited forever on a proved fact. This is the independent review's finding 2b, and it
reproduces on the merge of `465b3de` with #196 `3b7f443` in two tests.

**Contract.** An output may name fields in `"decided"`. `document.text` does this only for `found`, and only
on a hit. On an incomplete output, a named field that holds a value is judged whole. `decided` never vouches
for:
- a value of `None`;
- an unnamed field;
- a non-list `decided`;
- a list cut at the receipt's item limit.

`decided` is written by GREG's own adapter code (`documents.find_phrase`), not by the binary. A capability
that lies about its own output is still the appraiser's and the oracle's problem, as before.

**Patch:** `patches/missions-decided-fields.patch`. It changes `greg/missions.py` (7 lines) and
`tests/unit/test_greg_incomplete_evidence.py` (3 tests). It applies to #196 at `3b7f443` and not to #201,
which does not carry the first patch. `greg/missions.py` is the integration owner's file, so the patch is
delivered here and not applied on any pushed branch.
