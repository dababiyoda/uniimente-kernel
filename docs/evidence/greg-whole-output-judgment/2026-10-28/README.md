# A check is decided over the whole output its receipt kept

Session `session_01KucyfnPRxLT4YY1UibJ3Ee`, branch `claude/greg-whole-output-judgment`, child of #196 at
`190c58fb5a69a1268407d380a7f7c670c5602deb`. Claim: #96 comment 6472686919. Reality tier: SANDBOX (in-process
bodies, per-test founder keys, real `fs.read`, real separate-process appraiser). VEPMC 0.

## What GREG can do now that it could not before

- **Long outputs.** A mission whose check reads a fact past the first 16 KiB of any long output (`fs.read`,
  `document.text` with #201, any capability) closes on its own. Before, the check was INSUFFICIENT and GREG
  re-observed, then asked the founder (`SENSOR_FAILURE`), although the whole output was already kept in the body's
  store.
- **The appraiser agrees.** The separate appraiser re-derives the same verdict from the same kept output and returns
  VERIFIED. It refutes the closure if that output is altered.
- **Refusals.** A person who declines inside a long note (shared work, N6) is heard and the refusal honored. Before,
  the refusal was inconclusive and GREG kept waiting on them.
- **Goal Gravity.** It reads a long observation as the engine decided it ("attributed"). Before, it disagreed with
  the engine and distrusted the reading.
- **Two pre-existing defects fixed:**
  - A mission with one passing check and one unmeasurable check now reaches the founder. Before, it re-observed
    forever and asked nothing.
  - A lone surrogate past 16 KiB, which JSON from an untrusted tool or MCP server can carry, no longer fails a read
    into a "did it execute?" reconciliation.

## Mechanism

This recombines two existing mechanisms; it adds no new store, ledger or authority:

- **The evidence judge** (`3d2f9cc4`, `8d0a2303`, `af6fdfe1`) proves from a receipt's kept prefix only what the
  prefix can prove, and calls the rest INSUFFICIENT.
- **The kept-output route** (`f9086781`, `40ce615d`) keeps the whole output (up to 1 MiB of canonical JSON)
  content-addressed, records the address on the receipt, and reads it back only by that address, re-hashed, after
  checking that it cuts to exactly the kept output (`artifact_output`).

`judge_receipt` joins them. It judges the kept output first. Only a check left INSUFFICIENT is judged again, over
the whole output read through `artifact_output`, with `whole=True`.

**Every reader of a receipt now uses it:**

- the engine's sensor path;
- the refusal watch;
- the appraiser's re-derivation and its precondition check;
- Goal Gravity.

**The whole is judged as the value itself:**

- a value shaped like a receipt's record of a cut string is data, not a cut;
- a list of exactly 1000 items still decides only what more items could not undo, in every mode. A capability may cut
  its own list there without saying so (`fs.list`), and the appraiser's fresh re-reading must reach the engine's
  verdict. The first version read it as all of it (corrected after the review of #209, F1);
- an output that declares itself incomplete (`complete: false`) still proves only monotone facts.

**Anything else keeps INSUFFICIENT, with the reason:** a missing, altered, non-JSON or foreign artifact, a body
with no store, a store that refused the output, or an output claiming its own artifact record.

## Results

| Check | Result |
| --- | --- |
| `tests/unit/test_greg_whole_output_judgment.py` | 31 passed, 1 skipped (the #201 PDF case, which needs `greg.documents`) |
| The same tests against #196 `190c58fb` | 22 failed, 9 passed: every mission-path case fails. The 9 that pass are the damage/forgery controls, the prefix hit and digest equality, which the base also gets right because it never reads a whole |
| `scripts/ci/check_whole_output_mutants.py` | 13 mutants, 0 survived |
| Ablation (mutant 1: never read the whole) | the founder ask returns; the closure test fails |
| `test_greg_incomplete_evidence.py` | 30 passed. Its three end-to-end tests now run with no whole kept (the store refuses), the case that still asks |
| Neighbouring suites (missions, appraisal, artifacts, bindings, continuity, Goal Gravity ×11, human work, shared work, precondition, live intake, cognition) | 359 passed, 4 skipped. The first run had 3 failures in `test_greg_cognition.py`: `z3-solver` was missing from this venv (`requirements-cognition.txt`, which CI job 1 installs); 37 passed after installing it |
| Mind convergence map, exposure ledger, packaging, developmental inheritance | 156 passed, 1 skipped |
| `check_schema_refs`, `check_authority_singleton`, `check_sealed_developmental`, `refresh_owned_source` | pass; owned-source manifest unchanged |
| Combined with #201 `a1d2abf` (clean merge) | 173 passed: document, license and use-context suites, incomplete evidence, this file. A plain `contains` on a long PDF's `text` closes with 0 asks |

The full suite on the final head is recorded in the PR.

## Follow-up: an unmeasured check is neither pursued nor certified as failed

Independent review of #196's judge (separate process, findings J1 and J2) found that a check the evidence could not
decide still counted as failed whenever another check truly failed. This holds at any output size, with or without the
whole-output read above. Both are fixed on this branch:

- **Engine (J1).** `_step` no longer pursues a reading the evidence could not decide (INSUFFICIENT, or a
  construction the host stopped): `failing - self.inconclusive`. A strategy whose only purpose is such a check is no
  longer dispatched. A sensor the capability refused keeps its route, since a strategy may create what it reads (the
  first version, `failing - errors`, broke two canonical shop tests and was corrected in `c74360cf`). A precondition
  must still be measured passing: an unmeasured one holds the strategy. The NO_STRATEGY ask says which checks GREG
  could not measure (`unmeasured_checks`).
- **Appraiser (J2).** It judges three-valued, with `judge_receipt` on the receipt and `judge` on the re-reading. An
  undecided receipt proves neither a success nor the claimed failure. An undecided re-reading of the world (for
  example `fs.list`, which keeps at most 1000 entries and says nothing of the rest) is "could not be re-measured",
  not "still fails". Before, both were read as a verified failure, and VERIFIED_UNMET certified a check that was
  never measured.

| Check | Result |
| --- | --- |
| `tests/unit/test_greg_unmeasured_not_failed.py` | 4 passed |
| The same tests on this branch before the fix (`2a59329c`) | 3 failed, 1 passed. The test that passes guards the precondition rule, which held before by a different route |
| `scripts/ci/check_whole_output_mutants.py` | 17 mutants (4 new), 0 survived |

## Follow-up: review of this branch (#209)

A review of `c74360cf` by four lenses (subagents of this session, so self-review, not independent) reproduced each
finding on the head and on #196's `e6c5058c`, and two skeptics re-ran each one. When `709475cc` was written, only the
skeptics for E1 and E2 had returned. The final verdicts, received afterwards:

- 15 reports. Both skeptics confirmed 12, which are 9 distinct defects: the nested cut was reported three times and
  the type error twice.
- Three of the 9 were introduced by this branch: APR-1, F1 and the type error. Six were pre-existing.
- `709475cc` fixes seven of them (APR-1, F1, the type error, the nested cut, the appraiser bind by artifact, E1 and
  E4) and the preparation case of E2. E2's ladder case and E5 are recorded below. Each fix has a test that fails on
  `c74360cf`.
- Both skeptics refuted three reports. EXACT-1000 is not changed here.
- REUSE and E3, two of the refuted reports, are marked below. `709475cc` had treated them as defects and changed both,
  so this record no longer counts them as defect fixes.

| Finding | Introduced here | Before | Now |
| --- | --- | --- | --- |
| APR-1: J9 refused a record the sensor itself returned | yes | a `pipeline.inspect` check on `value.sha256` asked the founder (SENSOR_FAILURE); the appraiser refuted what #196 verified | only a receipt that recorded a cut has its records refused; a prefix is never read as a whole string |
| F1: a list of exactly 1000 | yes | the same list closed the mission or stayed open by the length of an unrelated field; the appraiser's re-reading refuted the closure | undecided past item 1000 in every mode; the appraiser judges its fresh re-reading as whole |
| TYPEERROR / APR-3 / J7: a signed value of another type | the long-text case | `contains 5` over a text past 16 KiB raised TypeError out of `Body.tick` (over a short text it always had) | the check fails; nothing raises |
| REUSE: a reading reused after a restart (refuted as a defect by both skeptics) | — | the omission is real, but the engine's reading on that path is the same as on the base, and Goal Gravity skips it; the next fresh reading decides the check | carries the whole output its receipt kept: one fewer undecided reading after a restart; kept as an improvement, not a fix |
| J-NESTED / F2 / APR-2: a cut below the judged value's own members | no | compared as the receipt's wrapper: a wrong TRUE and wrong FALSEs, kept by `judge_receipt` | compared by digest and length or undecided; the rest over the kept whole |
| APPRAISER-ARTIFACT-BIND | no | the appraiser re-derived a `by: artifact` bind from the prefix and refuted a correct closure | re-derived from the whole, as the engine bound it |
| E1: an abstaining cognitive sensor | no | named "re-observed failing" in the failure closure; VERIFIED_UNMET on no measurement | still pursued (Goal Gravity's attach ask depends on it); never certified as failed, by the engine or the appraiser |
| E4: a refused sensor read | no | named "re-observed failing"; the appraiser then refuted the whole closure | listed as `unmeasured_checks`; the closure names measured failures only |
| E2: a precondition during preparation | no | a strategy ran in the pass that measured its required check failing | held, as `_step` holds it |
| E3: the SENSOR_FAILURE streak (refuted as a defect by both skeptics) | — | counting readings across checks is the base's design: three unmeasured checks asked the founder on the first round, on the base too | counts observation rounds, so a mission with several unmeasured checks retries three rounds before asking, as a one-check mission does. This is a policy change, not a fix; the integrator decides, and reverting it is one hunk in `_pursue` plus its test |

Recorded, not changed here: E2's second case (a required check outside the current ladder rung is never observed, so
its strategy runs and the appraiser refutes the run; the fix changes ladder semantics and goes to the integrator); E5
(after the founder answers SENSOR_FAILURE, the mission re-blocks on the same request every tick); a list of exactly
1000 items is never decided past its end (conservative; `fs.list` should declare its own cut).

| Check | Result |
| --- | --- |
| New and changed tests on `c74360cf` | 24 fail; the other 83 in those four files pass there (guards and controls) |
| The same tests with the fixes | pass |
| `scripts/ci/check_whole_output_mutants.py` | 37 mutants (15 new), 0 survived or stale |

## Follow-up: handoffs, inspection and non-finite numbers (review of #196, J3, J4, J6)

Three more findings from the review of #196's judge, each confirmed by both skeptics, are fixed in the commit that follows `709475cc`:

| Finding | Before | Now |
| --- | --- | --- |
| J3 | `pipeline.inspect` dropped a producer's `complete: false`. A `not_contains` on a partly read document passed, and the mission closed VERIFIED | inspection carries the declaration and vouches for the fields it states in full; the judge reads incompleteness on any observation along the predicate's path |
| J4 | a `$from_action` handoff bound a list the receipt kept to 1000 items, or an object holding a prefix record, as the whole value | refused, as bind edges refuse it; inspection still reports the record as an observation |
| J6 | NaN or an infinity passed the receipt bound; the ledger's strict JSON then raised after the action had run, out of every tick | kept as `{"non_finite": ...}`; the whole output keeps the number; NaN is no reading (INSUFFICIENT); an infinity is decided over the whole |

| Check | Result |
| --- | --- |
| `tests/unit/test_greg_handoff_evidence.py` on `709475cc` | 7 of 8 fail (the control passes) |
| The same with the fix | 8 passed |
| `scripts/ci/check_whole_output_mutants.py` | 42 mutants (5 new; the two J8 mutants re-anchored) |

Not changed here:

- J5's deep-nesting case: about 500 levels raise RecursionError in `bounded`. This is pre-existing.
- A Gate that turns a receipt that cannot be serialized into a refusal. That code is `policy/consequence_gate.py`,
  which is not this branch's.
- Handoffs by `$from_action` still read only the receipt. A cut value is refused, not re-read from the kept whole
  output as a `by: artifact` bind edge does. The resolver has no artifact root, and handing on up to 1 MiB of input
  changes what the next action receives, so that is a separate change.
- A sensor that itself returns exactly `{"non_finite": "NaN"}` (or an infinity) is read as the receipt's marker, so
  a check on that field is INSUFFICIENT. That direction is conservative: no verdict is manufactured.

## Follow-up: the mutation gate read another mutant's bytecode

Canonical CI job 1 on `c74360cf` ran the full suite and passed it: 7846 passed, 48 skipped, 0 failed. It then
failed the whole-output gate, reporting "the refusal watch judges a decline by the prefix only" as SURVIVED. The
same gate on the same commit caught all 22 mutants here. Earlier records said this run was cancelled; it was not.

The cause was the gate, not the product.

- Mutants run one after another in one scratch copy.
- Python reuses a cached `.pyc` when the source has the same size and the same whole-second mtime.
- The engine-sensor mutant and the refusal-watch mutant both shorten `greg/missions.py` by 14 bytes. On CI's faster
  runner they were written within one second, so the refusal-watch test ran the engine mutant's bytecode, in which
  the refusal watch is intact.

The same mechanism can also report a mutant as caught when its test fails only on the previous mutant's code.

Job 1 on `709475cc` showed it again. The full suite passed (7870 passed, 48 skipped), and the gate reported 36 of
37 caught; the survivor was "a declared-incomplete output is judged whole once read from the store". Mutants 3, 4
and 5 each lengthen `greg/missions.py` by 14 bytes, so mutant 5's test ran mutant 4's bytecode, where the
declared-incomplete limit is intact.

| Check | Result |
| --- | --- |
| Refusal-watch mutant applied with no `.pyc` present, on `c74360cf` | test fails (caught) |
| The same, after importing the engine mutant and stamping the refusal mutant with the same mtime and size | test passes (survives), as in CI |
| Old harness, every mutant write stamped to one whole-second mtime | 42 mutants, 1 survived: the refusal watch |
| New harness, same forced collisions | 42 mutants, 0 survived |

The gate now runs each mutant with `python -B` and `PYTHONDONTWRITEBYTECODE=1`. Before each mutant it also removes
any `__pycache__` that a child process wrote: a confined worker starts with a clean environment and may still write
bytecode. A surviving mutant prints its test output, so a survivor in CI can be diagnosed from the log.

The repository's other nine mutation gates use the same pattern. Each excludes `__pycache__` only when it copies the
repository. They are not this branch's files, and they are reported on #96.

## Follow-up: review by a different session

Session `session_01KucyfmkWSE2nV8bUbyqmk4` reviewed `9057d92a` against #196 `9e5a0b09`. It did not write this
branch. Its verdict was that the core mechanism holds and that nothing on the mission path decides a wrong TRUE. Its
run of the mutation gate gave 42 mutants, 0 survived. It made five findings, each reproduced.

| Finding | Disposition |
| --- | --- |
| F1: the failure closure (`mission.unmet`) does not name a check the evidence could not decide, though the ask does | Fixed. The closure lists it under `unmeasured_checks`. Pinned by an assertion in `test_an_unmeasured_check_is_not_pursued_beside_a_measured_failure` and by a mutant |
| F2: a handoff refuses a 1000-item list even when its receipt recorded no cut | Kept. `fs.list` cuts its own listing at 1000 without saying so (`greg/capabilities.py`, `[:1000]`). Handing such a list on as whole is J4, the defect this branch fixed. Recorded under Limits |
| F3: a NaN nested in a value was decided over the whole output | Fixed. A NaN is no reading in every mode, at every depth (`_compare`). Pinned by `test_a_nan_inside_a_value_is_no_reading_over_the_whole_output_either` and by a mutant |
| F4: genuine data shaped like `{"non_finite": ...}` is never decidable | Kept. Only receipts write that shape. `pipeline.inspect` hands another receipt's markers on, in a receipt that records no cut. Read as data there, an inspected infinity would make `gte 10` FALSE. INSUFFICIENT is the honest answer. Recorded under Limits |
| F5: "decided over the whole output" was appended to a verdict still INSUFFICIENT | Fixed: "still undecided over the whole output". Pinned by an assertion and by a mutant |

On the fixed tree:
- the mutation gate gives 45 mutants (3 new), 0 survived or stale;
- the judgment, handoff, unmeasured, incomplete-evidence and wrapper suites give 116 passed, 1 skipped.

## Follow-up: the gate's own evidence

The gate is evidence, so it was attacked like the judge. An audit of the `a917a7dd` fix, with two skeptics per
finding, confirmed the bytecode mechanism and the fix for it, and found three ways the gate could still report a
result the code did not earn:

- **F6.** The gate never ran its tests on the unmutated copy, and it counted any "FAILED " line with exit 1 as a
  catch. A test that already failed therefore read as catching every mutant aimed at it. Today's full disk did this
  to every run on this machine.
- **F3.** The purge ran only before each write. A process that outlived its run could write a `.pyc` after the
  purge, and a later mutant then ran that code.
- **F4.** `rmtree(..., ignore_errors=True)` silently left a symlinked `__pycache__` in place, and Python read
  through it.

Two further rounds of attack on the fix, by separate agents, found that matching pytest's text cannot be made sound.
A test can print a line that starts with `FAILED <node>`. `-qq` prints no summary, colour codes wrap the node id,
and "xpassed" contains "passed". They also found that a joint baseline passes a test that only passes after another
one. The gate now:

- reads pytest's own per-test reports, written by a small plugin outside the copy, never its text;
- runs each named test alone on the unmutated copy, exactly as its mutants run it, and stops if any phase fails,
  skips or is an expected failure;
- counts a mutant as caught only when its own test, a parameter of it or a test inside it fails in some phase, not
  as an expected failure;
- dates every write it makes to its own whole second, earlier than any file the copy started with, so no cache
  written in good faith for another version can match, and no write is dated in the future;
- kills each run's process group however the run ends, including when the gate itself is stopped;
- walks the tree itself to remove every cache and removes links without following them. It stops if a link
  survives; a cache directory a running process writes meanwhile is harmless under the dating.

| Case (previous gate → this gate) | Result |
| --- | --- |
| A named test fails, skips or is an expected failure on the unmutated copy | false CAUGHT → stops at BASELINE, no mutant judged |
| A named test passes only after another test in the same session | false CAUGHT → stops at BASELINE |
| A harmless mutant's own test passes while another test fails, errors or prints `FAILED <node>` | false CAUGHT → SURVIVED |
| A test leaves `__pycache__` as a link to a cache of mutated code | false CAUGHT, or a real mutant masked → link removed, correct verdict |
| A process outside the run caches the previous version, same size, with the new version on disk | stale code ran when the two shared a second → rejected (control: same second → stale code ran) |
| `-qq`, forced colour, a class node, `]` in a parameter id, a failure in setup | wrong or no verdict → read from the reports, correct |
| The gate is stopped (SIGTERM, Ctrl-C) mid-run | pytest left running → no pytest left |
| The real list | 45 of 45 caught in both; this gate first passes all 34 named tests alone (about 215 s against 105 s) |

Boundary: this defends against caches written in good faith by any process, at any time. A test written to forge a
cache, or a report, could as easily rewrite the sources, and no gate run in place stops that.

## Limits and residuals

- **Size.** Outputs whose canonical JSON exceeds 1 MiB are not kept, so they still ask. Tested: 200 KiB of control
  characters escapes past 1 MiB. Deciding over sources too large to keep is the named next step; it needs a
  capability query contract with coverage evidence, which #201's `document.text` `phrase` already gives for PDFs.
- **Unicode.** The judge compares code points. A forbidden phrase in another normalization form (NFD text, NFC
  phrase) evades `not_contains` on any value, before and after this change. This is recorded for the integrator and
  the founder, not changed here.
- **Re-observation.** The appraiser judges its fresh re-reading as a whole output (nothing cut it). A re-read list of
  exactly 1000 items is still undecided past its end, as it is for the engine.
- **Trust boundary.** The store and the ledger share a host. Whoever controls the host can rewrite both, as before.
- **Independence.** The deliberation record (`deliberation.json`, validated) is self-review: five lenses from one
  session. Independent review is requested.
