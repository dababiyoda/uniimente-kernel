# A check judges the text the evidence holds

Session `session_01KucyfnPRxLT4YY1UibJ3Ee`, branch `claude/greg-faithful-text-evidence`, child of #209 at
`9b9945c1b025dfdf9b17a0e31f69a1c1140dad3b` (itself a child of #196). Claim: #96 comment 6516513997, item 1.
Reality tier: SANDBOX (in-process bodies, per-test founder keys, real `fs.read`, real separate-process appraiser).
VEPMC 0.

## What GREG can do now that it could not before

Three ways a mission check could pass on text the evidence did not hold are closed. The directive of 2026-10-22
names them: section VI test 8 (Unicode, malformed encoding, normalization) and section VIII (limits enforced before
uncontrolled buffering).

- **A forbidden name in another normalization form is found.** macOS file names, many PDFs and some editors write
  "José" as `Jose` plus a combining accent (NFD). The founder types it precomposed (NFC). The judge compared code
  points, so `not_contains "José"` passed on a file that names him. The founder's required phrase failed `contains`,
  and the mission asked instead of closing. Both now read one text.
- **A kept prefix no longer "contains" a letter the rest of the text accents.** A receipt keeps 16 KiB of a long
  string. A prefix ending in `cafe`, followed in the full text by a combining accent, used to prove `contains "cafe"`
  although the full text reads "café".
- **UTF-16 and other encodings are read faithfully or not at all.** `fs.read`, `http.get`, `browser.render`, the
  shell helper and `business.reconcile` decoded with replacement characters. A UTF-16 contract read as UTF-8 hid
  every phrase, so `not_contains "terminate without notice"` passed and the mission closed. The text is now read in
  the encoding its byte-order mark names (UTF-8, UTF-16 or UTF-32), or else as strict UTF-8. When no faithful reading
  exists, the output says why (`text_unreadable`) and the check stays undecided. The founder is asked with that
  reason ("holds NUL bytes: UTF-16 or UTF-32 without a byte-order mark, or not text").
- **A statement in another encoding is no longer reported unmatched.** `business.reconcile` read a CP-1252 statement
  with replacement characters and could report "no posting carries the case reference". A reference typed in one
  normalization form now matches a statement written in the other.
- **Cut output is declared cut.** The shell helper kept the first 256 KiB of stdout, `browser.render` the first
  1 MiB of DOM and 256 KiB of text, and a 300-character title, with nothing to show the cut. A check that a phrase is
  absent now decides only on output kept whole. `dom_bytes` and `dom_sha256` describe the whole page.
- **An oversized file is refused before it is read.** `fs.read` and `business.reconcile` read the whole file, then
  compared it to the 256 KiB ceiling: a 64 MiB file cost 64 MiB of memory to refuse. They now refuse by the size the
  file states. A file that misstates its size (a `/proc` file states 0) is never read past the ceiling plus one byte.
  A FIFO swapped in for a file is refused without blocking.

## Mechanism

No new store, ledger, authority or capability. Two existing mechanisms are joined, and the faithful decoder is added
as a small shared utility:

- **The judge** (`greg/missions.py`, from #196 and #209) compares text in Unicode Normalization Form C on both sides:
  for `contains`, `not_contains` and `equals`, for list members and object keys, over a whole value and over a cut.
  Over a kept prefix it reads only `_stable(prefix)`: everything before the last character that starts a new
  normalization segment, meaning a starter that composes with nothing before it. That character may still compose
  with marks the receipt did not keep, so it is left out with what follows it. The NFC form of the stable part
  begins the NFC form of every string the prefix starts. The test checks this on 4000 random head and tail pairs
  drawn from a hostile alphabet: accents of several combining classes, Hangul jamo, an Oriya vowel sign that composes
  backwards, a Tibetan vowel that decomposes into marks, and singletons such as KELVIN SIGN. A long string whose
  digest differs but whose kept part agrees as text is INSUFFICIENT, then decided over the whole output its receipt
  kept (#209).
- **The incomplete-observation contract** (`complete: false` plus `decided`, from #201 and #196's J8) carries
  unreadable and cut text. An output that cannot hold its text faithfully leaves the field out, says why beside it,
  declares itself incomplete and vouches only for the fields it read whole (`path`, `bytes`, `sha256`, status). No
  check on the text decides either way, and a check on the digest still does.
- **The decoder** (`greg/capabilities.py`: `faithful_text`, `with_text`, `bounded_read`). An incremental strict
  decoder leaves out a character a cut split. Strict UTF-8 refuses encoded surrogates, and strict UTF-16 refuses
  unpaired ones. The backward-composition table is derived from the same `unicodedata` the normalizer uses
  (Unicode 14.0.0 on CI's Python 3.11), so the boundary rule cannot disagree with the normalization it protects.

## Effect compilation

- **Founder expression:** "No mission predicate may manufacture certainty from incomplete or truncated data"
  (directive of 2026-10-22, section VI), including test 8.
- **Observable effect:** a verdict on text is the same whichever normalization form either side is written in. No
  verdict is drawn from bytes that were not faithfully decoded. A verdict from a kept prefix never contradicts the
  verdict on the whole.
- **Falsifier:** any pair of canonically equivalent inputs with different verdicts; any decided text verdict on
  output that was replaced, misdecoded or silently cut; a prefix verdict that differs from the whole-value verdict;
  a refused oversized file whose read allocated more than the ceiling.
- **Simplest mechanism:** the standard library (`unicodedata.normalize`, `codecs` incremental decoders, `os.fstat`)
  and two existing GREG contracts. Nothing was built that these provide.

## Alternatives

| Alternative | Why not chosen |
| --- | --- |
| Do nothing: compare code points (recorded as a limit on #209) | The false `not_contains` passes on NFD text and on UTF-16 are live on the mission path |
| NFD instead of NFC | Equivalent for invariance; NFC is what founders type and what most stored text uses, so details read naturally |
| NFKC (compatibility) or case folding | Changes what text means: a ligature, a full-width digit or a superscript is not the same text, and case changes names. A predicate that wants loose matching should say so; none does today |
| Keep lossy text and flag it | `contains` stays decided on it, which is unsound when the encoding is wrong. UTF-16 bytes `61 62 63 00` decode as "abc" in UTF-8 and as "扡c" in UTF-16 |
| Decode by the HTTP charset header | The confined route returns no headers, so the same page would read differently by route. Recorded as a limit |
| Record an NFC digest in the receipt's cut record | Would decide long-string `equals` without the kept whole, but changes the receipt format all readers share. The kept whole already decides it |

## Five roles

- **Builder.** Smallest change that closes the class: one judge rule, one decoder, one bounded reader, applied at
  every sensor that hands text to a predicate. No new capability.
- **Adversary.** Can a phrase be forged across the boundary? `_stable` drops the last segment start. The property
  test and three boundary mutants (keeping the starter, ignoring backward composers, ignoring a decomposition's
  first character) attack it. Can a lossy decode slip through? The NUL, mark and strict-decode mutants show each
  safeguard is needed. Residual: NFKC-only lookalikes (a Cyrillic "а" for Latin "a") are different texts by design.
  Spoofing by confusables is a separate defense GREG does not have.
- **Operator.** Cost: one NFC pass per comparison, and a 50 ms table build once per process. Founders see a reason
  instead of a silent pass. A non-UTF-8 file that was "readable" with replacement characters now asks. This is a
  behaviour change on purpose.
- **Beneficiary representative.** Names with accents (José, Núñez, Müller, Nguyễn) now match on every path, where
  they failed silently before.
- **Constitutional reviewer.** No authority change. Every change narrows what a verdict may claim. No path decides
  more than before, except where two strings are the same text.

**Pass 1 (structural inversion):** the invariance property becomes a standing test that every future comparison
must meet. Pass 1 also produced the "statement in another encoding" fix. Code-point comparison was a liability in
`business.reconcile` too, not only in the judge.

**Pass 2 (adversarial compounding):** the first mutant run left two survivors, which became tests. The statement test
signed the reference only in NFC, so dropping normalization of the signed side went unnoticed. No test read an
oversized statement. Both mutants are now killed. Other open items: #201's `documents.find_phrase` counts code
points too. That was found here and goes to the #201 fix lane. It is not changed in this PR, because #201 owns that
file.

## Tests and evidence

| Run | Result |
| --- | --- |
| `pytest tests/unit/test_greg_faithful_text.py` on this branch | 33 passed |
| The same 33 on `9b9945c1` (fail-before) | 31 failed, 2 passed; the two are controls: a file at the ceiling is still read, and a prefix verdict agrees with the whole |
| 31 mutants of the change, one at a time, in a separate copy, no bytecode | first run 29 killed, 2 survived (above); after two tests were added, 31 of 31 killed |
| Judge, capability, business, browser, whole-output suites | 108 passed, 3 skipped |

Mutants are listed in `scripts/ci/check_whole_output_mutants.py`, so Canonical CI job 1 runs them on every push.

## Limits

- NFKC lookalikes and case are not folded (see Alternatives).
- `http.get` ignores a declared charset: a Latin-1 page is unreadable, never misread.
- `count_gte` on text counts the code points kept, not NFC characters.
- A long string whose kept part agrees with the expected text but whose digest differs is INSUFFICIENT when the
  receipt kept no whole output (over 1 MiB of canonical JSON).
- UTF-8 that genuinely contains NUL is refused as text.
- Cut page text is a prefix of what the HTML parser emitted from a cut DOM; a phrase that the cut separates from the
  rest of its text node is not found in the prefix. It stays undecided, not refuted.
- SANDBOX tier only; no founder-device run.

## Rollback

Revert this branch's commits. No data migration. Receipts written before it keep their meaning: their text was
decoded with replacement, and the judge reads them as recorded.

## Independent review and its fixes (2026-10-30)

A separate session (`session_01Kucyfm2rRpECfxggpZqMes`) reviewed this branch at `00dea61` and `f12858a`. It ran every
repro it reports; it pushed nothing. Each confirmed finding is fixed with a test that fails on `6de575f7`:
`test_greg_faithful_text.py` gives 10 failed and 34 passed there, and 44 passed after. The 10 are eight of the nine
new tests and two browser tests with a new `cut_at` assertion. The ninth new test, for the needle, passes on the
base: it holds a safeguard that already worked and that nothing tested.

| Finding | Fix |
| --- | --- |
| 1 (high): a text the capability cut itself (stdout at the read ceiling, a page's text or title, stderr's tail) was searched whole, so `contains "cafe"` held when the cut fell before a combining accent, and the whole reads "café" | The capability names the side it cut (`cut_at`: run_cli's stdout at its end and stderr at its start; a page's text and title at their ends), and the judge searches only the part the rest cannot change. At a cut end it drops the last segment start and what follows (`textform.stable`). At a cut start it drops everything before the first segment start (`textform.stable_tail`, the mirror rule), in a receipt's prefix of such a text too. A side it does not know reads as both. A property test cuts 3,000 random texts at each declared side: no verdict from the kept part contradicts the whole |
| 2 (medium): three tests passing on the base failed at the head | `greg/textform.py` is in `foundry/owned-source.json`. The two `incomplete_evidence` tests now expect INSUFFICIENT for a string whose kept part agrees with the expected text but whose digest differs, as the review recommended: a tail the receipt did not keep can make it canonically equal (U+212A KELVIN SIGN reads "K"). A difference inside the kept part stays FALSE |
| 3 (low-medium): `exists` and `absent` depended on the form a key was written in | A path segment names the key that spells it in either form. Two keys spelling it leave the check INSUFFICIENT. The walk that finds a declared-incomplete observation uses the same rule, so one nested under a key in the other form still limits the verdict |
| 4 (low): a UTF-8 byte-order mark before UTF-16 bytes passed the NUL guard | The guard covers `utf-8-sig` |
| 5 (low): no test held the needle's normalization in the cut path | A test, and 15 gate mutants: the four safeguards the review found unguarded in the gate, and every fix above |

The review's suspicions:

- **Applied:**
  - `bounded_read` opens with `O_NOFOLLOW`, so a link swapped in after the roots were checked is refused.
  - `git.inspect` turns history that is not UTF-8 into a failed read instead of a `UnicodeDecodeError`. `git commit` now re-encodes such a message, so the test writes the commit object directly.
  - `_judge_whole`'s unreachable `equals` branch reads an undecidable comparison as INSUFFICIENT, never FALSE.
  - The `textform` docstring no longer names a module that is not on this branch.
- **Kept:** an `equals` on an object whose two keys spell one text stays INSUFFICIENT, so such a mission does not close. Equal key spellings cannot tell which value the expected key means.

**Where the fix departs from the review:** the review proposed trimming every declared-incomplete text. The first
version did that, and the gate's baseline refused it. `test_a_declared_incomplete_output_stays_monotone_over_its_whole`
holds a phrase at the very end of `document.text`'s words: that text is whole and the document is not, and what more
pages add comes after a space. Trimming there turns a provable TRUE into INSUFFICIENT. The capability knows where it
cut, so it says so, and a text it did not cut keeps its verdicts. A capability that cuts a text without saying where
is the open risk. The two that cut text here, `run.cli` and `browser.render`, both say so, each held by a gate mutant.
