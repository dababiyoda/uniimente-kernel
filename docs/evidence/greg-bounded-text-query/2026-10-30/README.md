# A question about a file of any size is answered over all of it

Session `session_01KucyfnPRxLT4YY1UibJ3Ee`, branch `claude/greg-bounded-text-query`, child of item 1
(`claude/greg-faithful-text-evidence`), itself a child of #209 and #196. Claim: #96 comment 6516513997, item 2.
Reality tier: SANDBOX (in-process bodies, per-test founder keys, real files up to 12 MiB, real separate-process
appraiser). VEPMC 0.

## What GREG can do now that it could not before

The founder can ask whether a large file mentions something: *Check that ~/logs/app.log never mentions "FATAL"*.
GREG proposes one read-only mission that reads the whole file, however large. The mission closes when every byte was
read and decoded and the phrase is absent, and the separate appraiser verifies it by reading the file again. If the
phrase is there, the mission stays open and the founder is asked what to do.

**Before**, measured on the base (`7891d8ce`) with a 3 MiB log through `fs.read`, the only file reader: the mission
stayed ACTIVE and asked the founder `SENSOR_FAILURE` on every reading
(`sensor REFUSED: capability refused: file exceeds read ceiling`). `fs.read` refuses a file over 256 KiB. A receipt
keeps an output whole only up to 1 MiB of canonical JSON (#209), so a larger source could not be judged on any path.

## Mechanism

`fs.search` (`greg/textquery.py`) is a read-only builtin. It recombines three mechanisms that already exist:

- **The phrase question from #201's `document.text`.** #201 answers a phrase over a whole PDF extraction, held in
  memory, and reports `found` as True, False or None. Here the question is generalized: up to 16 phrases over any
  file, streamed in 64 KiB chunks. Memory holds one chunk, the end of the text whose normalized form is still open,
  and the last `overlap` characters, so a match across two chunks is found exactly once.
- **The text form from item 1** (`greg/textform.py`). Each piece is normalized up to its last normalization boundary
  (`stable`), so an accent in the next chunk still joins the letter before it. Decoding is strict, in the encoding a
  byte-order mark names; text that cannot be read faithfully decides nothing.
- **The incomplete-observation contract** (`complete`, `decided`, from #201 and #196's J8). A reading stopped by its
  byte or time limit, or by an unreadable byte, declares itself incomplete. It vouches for the phrases it found and
  for its coverage fields, and leaves every absence undecided. The judge now names the reason ("byte limit: read the
  first 1048576 bytes", "holds NUL bytes ...") in what the founder sees.

The result is a few hundred bytes, small enough for any receipt, and it states its coverage:

- `size` and `bytes_read`;
- `read_sha256`, the digest of exactly the bytes read, which is the file's digest when complete;
- `encoding`, `normalization` and `whitespace`;
- `chunk_bytes` and `overlap_chars`;
- `complete` and `stopped`;
- for each phrase, `found`, `first_offset` (in normalized characters) and `occurrences`.

The appraiser re-observes `fs.search`: if the file changed after closure, it records "world no longer matches".

**Integration on the existing path:**

- a planner route (`template:file-search`) turns the founder's words into the mission;
- `templates.file_search` builds the spec;
- the engine, the judge and the appraiser are unchanged in kind.

## Limits

| Limit | Value | Past it |
| --- | --- | --- |
| Bytes read per query | 4 GiB, lowered by `max_bytes` | the answer stops there, and says so |
| Seconds per query | 60, lowered by `max_seconds` | the answer stops there, and says so |
| Phrases | 16, each 1024 characters | refused |
| Text with no normalization boundary | 64 Ki characters (e.g. one letter followed by endless combining marks) | refused as unreadable, before memory grows |

A file can grow while it is read. `size` is the size stated when the file was opened, and `read_sha256` binds the
answer to exactly the bytes that were read.

## Tests and evidence

| Run | Result |
| --- | --- |
| `pytest tests/unit/test_greg_text_query.py tests/integration/test_greg_section_ix_text_scenarios.py` | 28 + 4 passed |
| A 12 MiB log, phrase near the end | found; measured 262 KiB peak traced memory, a 534-byte result, 0.1 s (warm process); the test asserts under 2 MiB and 2 KiB |
| A phrase across a chunk boundary, at 4 offsets | found once, at the right offset |
| A short phrase inside the carried tail | counted once |
| An accent in the next chunk | `cafe au` absent, `café au` found |
| Fed in pieces of 1, 3, 7 and 64 bytes | the same result as fed whole (this test found a defect, below) |
| Byte limit, time limit, exactly at the limit | stopped and stated; found True kept; absence undecided; at the limit, complete |
| UTF-16 with and without a mark; a non-UTF-8 byte midway; a run of marks | read faithfully, or every answer open with the reason |
| A FIFO swapped in after the file check; a path outside the roots; malformed questions | refused |
| Mission: a 3 MiB clean log | ACHIEVED, no ask, appraiser VERIFIED; a fault appended later is reported by the appraiser on its next appraisal |
| Mission: a fault at 2 MiB | stays open; the founder is asked `NO_STRATEGY`, not about a sensor failure |
| Planner words | `never mentions` and `mention` draft the right checks; a note request keeps its own route |
| 13 mutants, added to `scripts/ci/check_whole_output_mutants.py`, then 5 more for the section IX fixes (89 in all) | 89 of 89 killed, each by its named test in a separate copy |

**Negative result found while building.** Fed one byte at a time, the query missed a phrase it found when fed whole.
The tail carried between pieces was sliced with a negative index whenever the text so far was shorter than the
overlap. It is fixed, and the piece-size test and a mutant guard it.

**A subtraction that first survived.** With `fs.search` removed from the appraiser's re-observable set, the appraiser
still returned VERIFIED from the receipt alone, so the test proved nothing about re-observation. The test now changes
the file after closure and requires the appraiser to see it; the subtraction is a gate mutant.

## Alternatives

| Alternative | Why not chosen |
| --- | --- |
| Raise `fs.read`'s ceiling | Memory grows with the file, and the receipt still cuts at 16 KiB; nothing gains coverage evidence |
| `grep` or `rg` as an acquired capability | No normalization, encoding faithfulness or coverage statement, and an exit code is not a declared reading. A reasonable second implementation behind the same contract, not a replacement for it |
| Keep larger artifacts in the store | Moves bytes, not proof; a check still reads a cut |
| Extend #201's `find_phrase` | #201 owns `documents.py`. This module is the shared engine #201 can stream `pdftotext` output through, offered to the #201 lane |

## Section IX scenarios 7 and 8, and the sensing watch

Added after the first push, from the section IX run (`tests/integration/test_greg_section_ix_text_scenarios.py`).

**Scenario 8: valid evidence too narrow for the claim.** A reading capped at 64 KiB of a 2.4 MiB log is authentic:
its `read_sha256` equals the digest of exactly the first 65536 bytes (checked against the file). It cannot prove the
whole log never mentions `FATAL`, so the mission stays open, every observation says "byte limit: read the first 65536
bytes", the founder is asked `SENSOR_FAILURE` and nothing is appraised. The same capped reading proves a phrase it
found, and that closure is verified.

**Scenario 7: a failed capability hands off truthfully and resumes.** Two defects were found and fixed.

1. *A directory read as an absent file.* `fs.search` and `fs.read` answered `exists: false` for anything that was not
   a regular file, so a directory standing where the log should be was a measured failure, and the founder was asked
   `NO_STRATEGY` with the detail "field 'queries.0.found' absent". Only a missing path is now an absence; any other
   non-regular file is refused on its descriptor, so the founder is asked about the sensor, with the reason on every
   observation. A check on a missing path says "the path does not exist" (`219c4fa7`, on #228).
2. *A fixed world stayed unread.* After the third failed reading GREG asked the founder and then read nothing until
   the founder answered. Measured on the old engine: the directory replaced by a clean log, 60 further ticks over ten
   simulated hours, no further reading, mission still open. The block now carries its checks and is watched like a
   `NO_STRATEGY` block, re-read at the mission's cadence with its own signed, read-only sensor, and lifted when the
   sensor reads again, whatever the reading says:
   - a clean log: the question is withdrawn as moot (a body event, never the founder's answer), the same signed
     mission closes and the appraiser verifies it;
   - a log that now holds the fault: the question becomes `NO_STRATEGY`, about the failed check;
   - a sensor that stays broken: one question for the whole day, read once an hour (the mission's cadence).

   All three tests fail on the old engine; the cadence test fails because nothing is read at all. Two gate mutants
   remove the watch and its "reads again" rule.

This changes the shared engine (`greg/missions.py`, the `SENSOR_FAILURE` block and `_watch_while_blocked`). Its owner,
the #196 integrator, decides intake; it is offered on #96 with this commit.

## Next

- **#201 lane:** stream `pdftotext` stdout through `Query`, which removes buffering before the 4 MiB limit (§VIII), and normalize `find_phrase`. Owner: the #201 fix lane (item 3).
- **More predicates:** regular expressions and counts beyond `occurrences`, behind the same coverage contract, only if a mission needs them.
