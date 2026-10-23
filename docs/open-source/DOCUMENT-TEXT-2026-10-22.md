# GREG reads PDFs on the mission path, and system binaries carry their license — 2026-10-22

Open-Source Metabolism workstream, increment 2. Session `session_013k41DnwrjzpXL33r3j9BgB`. Stacked on #201. Claim: [#96 comment 6333350310](https://github.com/dababiyoda/uniimente-kernel/issues/96#issuecomment-6333350310). Authority delta: none.

## Product delta

**Before:**
- GREG could not check a fact inside a PDF.
- `fs.read` returns a PDF's bytes. A compressed PDF, the normal kind, shows none of its words.
- No catalog function read documents.

**After:** a founder-signed mission can carry a success check such as:

```json
{"sensor": {"function": "document.text", "params": {"path": "~/docs/lease.pdf"}, "target": "fs:lease.pdf"},
 "predicate": {"op": "contains", "field": "text", "value": "renewal term is twelve months"}}
```

1. Observing the check opens one verified CapabilityDeficit.
2. Capability Genesis's existing binary route finds the installed `pdftotext`.
3. It qualifies pdftotext on a frozen oracle.
4. It reads pdftotext's license from the OS package.
5. It attaches pdftotext under the mission's signed read-only scope.
6. The mission closes on the document's own words.

For documents longer than a receipt keeps (16 KiB), the check names the phrase. The reader judges it over every word it extracted, so a receipt's bounded prefix never decides the result:

```json
{"sensor": {"function": "document.text", "params": {"path": "~/docs/lease.pdf", "phrase": "renewal term is twelve months"}},
 "predicate": {"op": "equals", "field": "found", "value": true}}
```

A PDF that says otherwise does not close the mission. A path outside the read roots is refused by the acquired reader itself.

**Binary licenses:** acquired system binaries now carry a license read from Debian's machine-readable copyright files (DEP-5) instead of `license not inspected by GREG`. This closes #201's residual 1.

## Make / adopt

| Need | Route taken | Alternatives recorded |
|---|---|---|
| PDF text extraction | **installed commodity**: `pdftotext`, poppler-utils (GPL-2 or GPL-3), run as a separate no-network process | `pypdf` (BSD-3, PyPI, pure Python) and `pypdfium2` (PDFium; its ambiguous license declaration goes to founder review under #201's gate) as package fallbacks for bodies without poppler. Not built now. |
| A test of extraction that the candidate cannot game | **GREG-owned residual**: `greg/documents.py`, a minimal PDF 1.4 writer (standard Type 1 font, plain and Flate-compressed streams, exact xref) and seeded word cases. It shares no code with any candidate. | Using poppler's or pypdf's own test PDFs: rejected, because they are not independent of the candidate |
| Binary license | **commodity**: `dpkg-query -S` plus the DEP-5 format, with a small GREG reader | `licensecheck`, ScanCode: heavier; recorded |

**Oracle sanity check, independent of the candidate:**
- Over 20 seeds × 6 cases (120 PDFs, plain and compressed), poppler's `pdftotext` and Google's PDFium (`pypdfium2`), two unrelated codebases, both extract exactly the oracle's words: 0 mismatches each.
- The oracle is not tuned to the engine it qualifies.

## Binary license policy (asymmetry stated)

A Python package must carry a cleared assessment to auto-attach; it fails closed (#201). A system binary is held only when its OS package declares a license that is **known and not cleared** (network copyleft or not open source).

An undeterminable or unclassified binary license keeps today's behaviour, and its card says so. This covers macOS and hand-built binaries (no dpkg), or a DEP-5 file naming a license GREG does not classify.

**Why the asymmetry:** coreutils' file lists documentation licenses (GFDL-NIV-1.3) beside GPL-3+. Failing closed would have stopped `sha256sum` on every Debian body, breaking the existing verify-download mission for no legal reason.

**On this body:** pdftotext, sha256sum, wc and openssl read as cleared with obligations. `shasum` (Perl) stays unclassified and keeps prior behaviour.

## Evidence

`tests/unit/test_greg_document_text.py` (15 tests):

- **End to end:** a signed mission whose check reads a GREG-written compressed PDF.
  - The deficit opens once and is resolved by `acquired.document.text.pdftotext`.
  - Qualification passes 6 of 6 cases.
  - The license is GPL, cleared with obligations.
  - The mission is ACHIEVED.
- **Negatives:**
  - A PDF stating "six months" does not close the mission.
  - A PDF outside the read roots: `sensor REFUSED ... outside permitted roots`.
  - A reader that drops one word fails qualification.
- **Baseline:** `fs.read` on the same compressed PDF reads its bytes and fails the `contains` check.
- **DEP-5:** seven expressions (or, and, with-exception, AGPL, unknown) are classified; a licence-definition paragraph does not count as applying; a non-DEP-5 file is not interpreted; a body without dpkg says "not readable".
- **Fail-before:** 5 of these tests fail with `genesis.py` at #201's head (`1d9d873`) and pass with the change.
- **Non-regression:** the Genesis, missions, verify-download and scope suites, with #201's license tests, run with `greg/documents.py` staged: 355 passed, and packaging passes after the owned-source refresh, which adds `greg/documents.py` only.
- **Mutants:** four new mutants were run directly, all caught:
  - the oracle accepting any extraction;
  - a not-open binary attaching itself;
  - DEP-5 `and` taking the most permissive term;
  - a definition paragraph read as applying.
  They are added to `check_cortex_mutants.py`'s open-source group. The full gate on #201's content had caught 198 of 198, and the residual gate 82 of 82, before these four were added.
- **Seed freeze:** none of the changed files is pinned by seed `freeze-v12`.

**Falsifier:**
- a PDF check closes a mission when the document does not contain the phrase;
- or the reader returns words outside the read roots;
- or a binary under a known not-open license attaches under a mission scope.

## Review of bd7e3f9 (a separate agent in this same session, so not independent)

Each finding below is fixed in the next commit with a test that fails before the fix, and each has a mutant.

1. **Serious: an AGPL term was hidden by any unclassified term beside it.** `_worst` ranks unclassified highest, and 346 of 833 DEP-5 files on this host contain an unclassified term.
   - A binary is now held when **any** term is network copyleft or not open.
   - Spellings added: SPDX (`AGPL-3.0+`, `AGPL-3.0-or-later`, `SSPL-1`, `BUSL-1.1`) and Debian's `non-free` and `proprietary`.
   - Across the host's 833 copyright files, the hold fires on none: no false positives here.
2. **Serious: a receipt keeps a 16 KiB prefix of long text, and predicates read only that prefix.** A phrase after the prefix was missed, and a forbidden one would have been missed too. `document.text` now answers `phrase` over the whole extraction (`found`, `occurrences`, `words`, `text_sha256`).
   - Plain `contains` / `not_contains` on `text` still reads the prefix (`missions._field`). That is an integrator-owned seam; a patch is proposed on #96.
3. **Moderate: binary output was unbounded.** It is now refused above `mechanisms.MAX_OUTPUT` (4 MB).
4. **Minor: a binary card said FOUNDER_REVIEW but attached.** Its verdict now matches the behaviour: UNCLASSIFIED_PRIOR_BEHAVIOUR.
5. **Minor: DEP-5's `, and` binds loosest.** The reader follows that precedence.

The reviewer also confirmed:
- 0 oracle mismatches over 2,400 PDFs;
- read roots are resolved through symlinks;
- the binary hash is re-checked on every call;
- `dpkg` parsing falls back to None, safely.

It noted that lines longer than the page are dropped by pdftotext. The oracle's longest line (10 words) is near that edge.

## Limits

- **PDF shape:** only text drawn with a usable encoding. Scanned images need OCR, which is not acquired. Multi-column reading order and right-to-left scripts are not claimed.
- **Bodies without poppler:** a Chromebook body needs `sudo apt install poppler-utils`, which GREG never runs itself. Until then, the deficit escalates to the founder with "install software" among the options.
- **Not a legal review:** the license is read from declarations; a false declaration is not detected.

## Residual deficits, next

1. A `pypdf` package route for bodies without poppler. It needs a file-reading package contract in Genesis, which is wider than this increment.
2. OCR (Tesseract, Apache-2.0) for scanned PDFs.
3. Model-weight licenses on `OllamaRoute`. Deferred, because `greg/models.py` is pinned by seed `freeze-v12`, a re-seal its owners must make. Real model tests are also blocked here: the network policy refuses `huggingface.co` and `registry.ollama.ai`.
