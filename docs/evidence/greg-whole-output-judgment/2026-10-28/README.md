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

- a list of 1000 items is all of it, not "possibly cut";
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

- **Engine (J1).** `_step` pursues only measured failures (`failing - errors`), as `_prepare` already did. A strategy
  whose only purpose is an unmeasured check is no longer dispatched, and a failure closure names only measured
  failures. A precondition must still be measured passing: an unmeasured one holds the strategy. The NO_STRATEGY ask
  says which checks GREG could not measure (`unmeasured_checks`).
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

## Limits and residuals

- **Size.** Outputs whose canonical JSON exceeds 1 MiB are not kept, so they still ask. Tested: 200 KiB of control
  characters escapes past 1 MiB. Deciding over sources too large to keep is the named next step; it needs a
  capability query contract with coverage evidence, which #201's `document.text` `phrase` already gives for PDFs.
- **Unicode.** The judge compares code points. A forbidden phrase in another normalization form (NFD text, NFC
  phrase) evades `not_contains` on any value, before and after this change. This is recorded for the integrator and
  the founder, not changed here.
- **Re-observation.** The appraiser re-observes the world with the raw output and judges it as a receipt would. A
  re-read list of exactly 1000 items is still "possibly cut" there. This is pre-existing and not changed.
- **Trust boundary.** The store and the ledger share a host. Whoever controls the host can rewrite both, as before.
- **Independence.** The deliberation record (`deliberation.json`, validated) is self-review: five lenses from one
  session. Independent review is requested.
