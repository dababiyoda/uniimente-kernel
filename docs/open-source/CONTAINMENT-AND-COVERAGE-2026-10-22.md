# Open-source metabolism, increment 3: honest coverage and bounded acquired binaries (2026-10-22)

Session `session_013k41DnwrjzpXL33r3j9BgB`. Branch `claude/oss-metabolism-capability-pw6dew` (#201), base #196 `a3fa3795`.
Directive of 2026-10-22, sections VI (evidence soundness), VIII (output limits and document reliability) and IX
(scanned PDFs). Intent: `INTENT-20261022-OSS-METABOLISM` (`intents-oss-metabolism-2026-10-22.json`).

## What GREG can do now that it could not before

1. **A scanned page is never read as "the phrase is absent".** `document.text` reports which pages carried no
   text layer (`pages`, `pages_without_text`, `complete`). Over an incomplete extraction, a phrase it did not
   find is `found: null` (unknown), so a check for the phrase fails and a check for its absence also fails. A
   phrase found on a page that has text is still proof. On `fe82005` a PDF whose second page was an image
   answered `found: false`, and a mission forbidding a clause closed on it.
2. **The reader must say when it could not read everything, or it does not qualify.** The frozen oracle gained a
   seventh case (text, a scanned page, text) and requires `complete: false` on it and on the blank-page case.
   A reader that claims full coverage is rejected at qualification.
3. **Acquired binaries run under ceilings they cannot raise.** Every catalog binary (`pdftotext`,
   `sha256sum`, `wc`, ...) now writes its stdout and stderr to files in the workspace. `RLIMIT_FSIZE` stops it
   at the first byte past the 4 MiB output ceiling (SIGXFSZ), and `RLIMIT_AS` bounds its memory at 2 GiB, which
   covers decompression bombs. Python ignores SIGXFSZ and `execv` would inherit that, so the limiter restores
   the default. The limiter is the standard library's `resource` module applied in a child of the existing
   isolated process; `capabilities.run_isolated` is unchanged.
   - **Before:** `subprocess.run(capture_output=True)` buffered the whole output and only then compared its
     length. Under a 6 GB memory guard, the old adapter fed an endless writer ran the test process out of memory
     (`MemoryError`).
   - **Now:** the same writer is refused in under a second, with "stopped at the ceiling, never buffered".
4. **A failing binary's stderr reaches the mission record** (its last 200 characters), so a corrupt PDF says why.

## Tests and evidence

- **Five new tests** in `tests/unit/test_greg_document_text.py`, each failing on `fe82005`:
  - a scanned page never proves a phrase absent;
  - a phrase on a text page of a partly scanned PDF is still found;
  - the oracle rejects a reader that claims a scanned page was read;
  - an oversized output is stopped at the ceiling without being buffered;
  - a binary runs under a memory ceiling and reports its stderr.
- **Oracle:** the PDF with a scanned page was cross-checked with PDFium (`pypdfium2`), which reads 3 pages: text, none, text.
- **Mutants** (`scripts/ci/check_cortex_mutants.py`, open-source group): five new, all caught.
  - The size check is removed.
  - `RLIMIT_FSIZE` is removed.
  - `RLIMIT_AS` is removed.
  - An unknown phrase is reported absent.
  - Qualification ignores `complete`.
  - The stale mutant on the old `len(proc.stdout)` check was replaced.
- **Runs:**
  - `tests/unit/test_greg_document_text.py` and `test_greg_license_qualification.py`: 71 passed.
  - Genesis, mission, scope, mechanism, license, document, recombine and acquired suites: 766 passed, 7 skipped.
  - `python -m cortex.evaluation.seed_genome.run`: exit 0.
- **Full suite on the pinned `bd7e3f9`:** 7,055 passed, 148 skipped and 3 failed. All three failures fail
  identically on the base `a3fa3795`, reported on #96: the appraisal re-delegation test (two parameters) and
  `test_commerce_words_find_the_commerce_systems`.

## Limits, stated

- A page with no text layer may be blank. The reader cannot tell a blank page from a scan, so both count as
  unread. `pdfimages -list` (same poppler package) could tell them apart; it is not acquired yet.
- No OCR. A scanned page is now reported, not read. Tesseract (Apache-2.0) is the acquisition candidate. It is
  not installed on this body, and installing it is the founder's.
- `RLIMIT_AS` is not enforced on macOS. There the output ceiling still holds and memory is not bounded.
- The generic mission predicate still reads a receipt's 16 KiB prefix as the whole value. That is the
  integration owner's seam (`greg/missions.py`). A tested patch is in `patches/` and on #96; see
  `EVIDENCE-SOUNDNESS-PATCH-2026-10-22.md`.
