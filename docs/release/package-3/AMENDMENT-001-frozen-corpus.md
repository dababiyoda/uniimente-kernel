# Amendment 001 — the sealed experiment reads a frozen corpus

**Status:** applied.
**Authority:** `FOUNDER-RULING-2026-08-22` (DEC-OM-002, Option A) —
`docs/deliberations/FOUNDER-RULING-2026-08-22-opus-maximus-frontier.md`.
**Record:** `docs/deliberations/DEC-OM-002-sealed-corpus-contradiction.json`.
**Defect closed:** CONTRADICTION-0001.

This is the first amendment to a sealed experiment in this institution. The
seal's own test (`test_no_sealed_repair_file_was_modified_to_achieve_this`)
prescribes the procedure for one: *say so in the commit message and in
`docs/release/package-3/`, and update the pins in the same change.* This file is
that record.

---

## 1. The defect

`evolution/repair/spec.py` froze the Package 3 experiment — every threshold,
edge triple, refusal count and expected result — and hashed all of it into
`SPEC_SHA256`. But one of the frozen tables was this:

```python
MEASUREMENT_CORPUS = {
    "corpus_id": "LIVE",
    "manifests": "organs/*.manifest.yaml",     # <- a mutable directory
    ...
}
```

A sealed experiment bound to a live glob. The seal covered the *string*
`"organs/*.manifest.yaml"`, not the bytes that string resolves to. Everything
about the freeze was rigorous except the one binding that made it reproducible.

The defect was not theoretical. At freeze time the live corpus held three organ
manifests and produced **7 unresolved rows**, which is the number
`REQUIRED_REFUSALS["unresolved_count"]` records. Two more organs —
`pumpstation` and `research-in` — were published afterwards, entirely
legitimately. The live corpus produces **17** at the time of writing.
Re-running the recorded experiment against its own recorded expectation
therefore failed, and it would have kept failing harder as the institution
grew, because *growth* was being read as *regression*.

Twenty tests were failing on this before the remedy. Zero fail now.

## 2. What changed

Exactly one thing: which input the experiment reads.

| | before | after |
|---|---|---|
| `corpus_id` | `LIVE` | `FROZEN-627ec48` |
| `manifests` | `organs/*.manifest.yaml` | `evolution/repair/corpus/*.manifest.yaml` |
| `contracts` | `contracts/*.schema.json` | unchanged |
| `expected` | `REQUIRED_EDGE_TRIPLES + REQUIRED_REFUSALS` | unchanged |

The frozen corpus under `evolution/repair/corpus/` is **byte-identical** to the
three manifests as they stood at `627ec48`, the commit that froze the spec. Not
path-identical — content-identical, pinned by git blob id in
`tests/unit/test_repair_frozen_corpus.py::FREEZE_BLOBS`. That distinction earns
its keep: `organs/kernel.manifest.yaml` drifted after the freeze without anyone
noticing, so a path pin would still have been reading changed bytes.

## 3. No expectation value was changed — verifiable, not promised

The founder's ruling was explicit: *"Do not change the frozen expectation values
and do not rewrite the historical evidence."*

That constraint is worth more than a sentence claiming it was honoured, so it is
machine-checked. `spec.expectations_hash()` seals every frozen table **except**
`measurement_corpus`. It is invariant under a corpus repoint, and moves the
instant any threshold, edge triple, refusal count or expected result is touched.

```
expectations hash, spec at 6f6d7dab…c4ab7f4a (before) :
    8720b0b1c94ceba58ef2babfb0adef3466b85e72c8c5e0a8d4d069d7b3cd746a
expectations hash, spec today (after)                 :
    8720b0b1c94ceba58ef2babfb0adef3466b85e72c8c5e0a8d4d069d7b3cd746a
```

Identical. A table-by-table comparison of the pre- and post-amendment
`_FROZEN_TABLES` confirms the same result from the other direction: the set of
differing tables is exactly `['measurement_corpus']`, and no table was added or
removed. `test_the_amendment_changed_the_corpus_binding_and_nothing_else`
asserts both.

`unresolved_count` is still 7. All four edge triples are unchanged. The 3.8×
cost finding, the two failed predictions, and every negative result in
`RESULTS.md` stand exactly as recorded.

## 4. The seal moved, and both values are kept

| | value |
|---|---|
| `SPEC_SHA256_ORIGINAL` | `6f6d7dab40cf023dd69995511a3db298482c31b0bb39675d4a5c47f7c4ab7f4a` |
| `SPEC_SHA256` (now) | `c02e634203e2dd2e4689cc90548a917eadaadfcdc324350ac086ed937b0a6fc8` |

The superseded seal is retained in `spec.py` rather than deleted. An amendment
that erased the value it replaced would be indistinguishable, to a later reader,
from an experiment that had never been amended at all.

Documents citing `6f6d7dab…` — `README.md`, `RESULTS.md`, `EXPERIMENT_SPEC.md` —
are **not** edited. They were correct when written and they describe the run
that actually happened. Same discipline as `PLAN.md`, whose stale "NOT
AUTHORIZED" header is preserved for the same reason.

## 5. Files amended

Five call sites plus the spec. Each previously reconstructed the live `organs/`
path by hand; each now reads `spec.CORPUS_DIR`, so no caller can drift from the
binding the seal declares.

| file | change |
|---|---|
| `evolution/repair/spec.py` | corpus binding, `CORPUS_DIR`, `expectations_hash()`, both seals |
| `evolution/repair/harness.py` | reads `spec.CORPUS_DIR` |
| `tests/unit/test_repair_adapters.py` | reads `spec.CORPUS_DIR` |
| `tests/unit/test_repair_candidates.py` | reads `spec.CORPUS_DIR` |
| `tests/unit/test_repair_inertness.py` | reads `spec.CORPUS_DIR` (inside the denial subprocess) |
| `tests/unit/test_repair_spec_frozen.py` | reads `spec.CORPUS_DIR` |

`tests/unit/test_repair_harness.py` is untouched and its pin is unchanged.

## 6. The strengthening condition, and why it is not optional

Option A has an adversarial weakness the founder named while approving it: a
frozen experiment that always passes could be mistaken for evidence that the
live institution is fine. It is not evidence of that, and it stopped being
capable of being evidence of that the moment it was repointed.

`evolution/repair/live_health.py` is the other half, and it is deliberately
built so it cannot be confused with the sealed experiment:

- it imports **no** expectation from `spec.py`;
- it never asserts `unresolved_count == 7`;
- it holds no frozen table and carries no seal;
- it emits a reading, not a verdict.

Run it with `python -m evolution.repair.live_health`.

> The frozen experiment answers **"can I reproduce the historical
> experiment?"** The live check answers **"is the institution healthy now?"**
> Neither may be presented as the other.

`test_repair_live_health.py` asserts that separation structurally rather than
trusting it: the module's AST is inspected for any import of a frozen
expectation, and for any comparison against the literal 7.

One reading the live check makes explicit, because it is counter-intuitive: a
rising `unresolved` count is usually the institution **growing**, not breaking.
The linker reports fields it cannot resolve instead of inventing them, so six
organs raise more open questions than three. The health signal is in the
*kind* of finding — an untyped edge, an unproduced contract or an overlapping
authority is a structural defect; an unresolved field is an open question with
an owner.

## 7. What deliberately still fails

`test_the_live_corpus_still_disagrees_and_that_is_the_contradiction` is kept,
and it still passes — meaning the live corpus still does *not* match the sealed
expectation of 7.

That is intentional. A remedy that made the divergence invisible would be worse
than the defect, because the next reader could not see why the frozen corpus
exists. The divergence is now *expected and named* rather than *unexplained and
failing*. That is the difference between resolving a contradiction and hiding
one.

## 8. Rollback

Revert this commit. The frozen corpus under `evolution/repair/corpus/` is
additive and can stay; with `MEASUREMENT_CORPUS` restored to the live glob, the
twenty pre-existing failures return, along with CONTRADICTION-0001. Nothing
about the rollback is destructive, and no historical record needs restoring
because none was rewritten.
