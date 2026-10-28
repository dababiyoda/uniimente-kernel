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
finding on the head and on #196's `e6c5058c`. Skeptics confirmed E1 and E2; their other runs did not return. It found
12 distinct defects in 15 reports (three were found twice). Four were introduced by this branch and one was widened by
it. Ten are fixed here, each with a test that fails on `c74360cf`:

| Finding | Introduced here | Before | Now |
| --- | --- | --- | --- |
| APR-1: J9 refused a record the sensor itself returned | yes | a `pipeline.inspect` check on `value.sha256` asked the founder (SENSOR_FAILURE); the appraiser refuted what #196 verified | only a receipt that recorded a cut has its records refused; a prefix is never read as a whole string |
| F1: a list of exactly 1000 | yes | the same list closed the mission or stayed open by the length of an unrelated field; the appraiser's re-reading refuted the closure | undecided past item 1000 in every mode; the appraiser judges its fresh re-reading as whole |
| TYPEERROR / APR-3 / J7: a signed value of another type | the long-text case | `contains 5` over a text past 16 KiB raised TypeError out of `Body.tick` (over a short text it always had) | the check fails; nothing raises |
| REUSE: a reading reused after a restart | yes | judged on its prefix only: inconclusive where the fresh reading decided | carries the whole output its receipt kept |
| J-NESTED / F2 / APR-2: a cut below the judged value's own members | no | compared as the receipt's wrapper: a wrong TRUE and wrong FALSEs, kept by `judge_receipt` | compared by digest and length or undecided; the rest over the kept whole |
| APPRAISER-ARTIFACT-BIND | no | the appraiser re-derived a `by: artifact` bind from the prefix and refuted a correct closure | re-derived from the whole, as the engine bound it |
| E1: an abstaining cognitive sensor | no | named "re-observed failing" in the failure closure; VERIFIED_UNMET on no measurement | still pursued (Goal Gravity's attach ask depends on it); never certified as failed, by the engine or the appraiser |
| E4: a refused sensor read | no | named "re-observed failing"; the appraiser then refuted the whole closure | listed as `unmeasured_checks`; the closure names measured failures only |
| E2: a precondition during preparation | no | a strategy ran in the pass that measured its required check failing | held, as `_step` holds it |
| E3: the SENSOR_FAILURE streak | widened here | three unmeasured checks asked the founder on the first reading | counts observation rounds |

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
