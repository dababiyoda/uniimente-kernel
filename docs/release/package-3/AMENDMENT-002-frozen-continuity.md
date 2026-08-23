# Amendment 002 — the continuity check reads frozen copies

**Status:** applied.
**Authority:** `FOUNDER-RULING-2026-08-23` (CONTRADICTION-0002, Option A) —
`docs/deliberations/FOUNDER-RULING-2026-08-23-infinite-goal-chase.md`.
**Analysis:** `docs/deliberations/CONTRADICTION-0002-continuity-baseline.md`.
**Defect closed:** CONTRADICTION-0002.

Second amendment to a sealed experiment. Same procedure as Amendment 001, which
the seal's own test prescribes: say so in the commit message and here, and update
the pins in the same change.

---

## 1. The defect

`evolution/repair/spec.CONTINUITY_ARTIFACT_SHA256` pins twelve files — the five
constitutional documents, the three authority documents, the three identity
registries and `policy/consequence_gate.py` — and
`test_continuity_hashes_describe_the_real_artifacts_now` asserted those
freeze-time hashes against the **live** files.

The test's own docstring said what it meant to check:

> The continuity baseline must be true **at freeze time**, or the later
> before/after comparison proves nothing.

Freeze time. The assertion ran against whatever was on disk today.

This is CONTRADICTION-0001 in a second location — a sealed historical experiment
bound to live artifacts — but on a more serious subject. 0001 bound an experiment
to `organs/`. This one bound it to the Constitution, the authority matrix and the
Consequence Gate, so **the institution could not amend its own constitution
without a sealed experiment failing**.

It was blocking real work, which is how it surfaced: emitting Witness v2 needs
about three lines in `policy/consequence_gate.py`, and the gate is one of the
twelve pinned files.

## 2. What changed

One binding, in two places, plus a split that was overdue.

| Before | After |
|---|---|
| `continuity_fingerprint(root=KERNEL_ROOT)` | `continuity_fingerprint(root=spec.CONTINUITY_DIR)` |
| test read `ROOT/<rel>` | test reads `spec.CONTINUITY_DIR/<rel>` |
| — | new `live_continuity_fingerprint(root=KERNEL_ROOT)` |

`evolution/repair/continuity/` holds byte-identical copies of all twelve
artifacts. Each was verified against its pinned hash **before** being written,
and the combined hash of the copies equals `CONTINUITY_COMBINED_SHA256` exactly.

## 3. What did NOT change — and the proof

**No expectation value moved. Neither did the seal.**

Amendment 001 had to move `SPEC_SHA256`, because the corpus binding lived
*inside* a frozen table (`MEASUREMENT_CORPUS`). That is why
`expectations_hash()` exists: it excludes `measurement_corpus` so that the claim
"no expectation moved" could be proven rather than promised.

The continuity binding was never in a frozen table. The pins are *relative
paths*; the root they were joined to lived in `harness.py`. So this amendment
gets the stronger property:

```
spec.spec_hash()          == spec.SPEC_SHA256          # unchanged
spec.expectations_hash()  == spec.EXPECTATIONS_SHA256  # unchanged
```

Both asserted by `test_amendment_002_moved_no_expectation_and_did_not_move_the_seal`
and again by `test_amendment_002_left_the_historical_evidence_exactly_where_it_was`.

The founder's constraint was *"do not update an old historical hash merely to
make current implementation pass"*. Not one of the twelve hashes was touched.
`CONTINUITY_COMBINED_SHA256` is the same string it has always been.

## 4. The duty that moved out

Amendment 001's remedy had a known cost, recorded when it was proposed: pointing
a check at frozen copies means it stops being a tripwire on the live tree. For
the manifests that was fine — `live_health.py` took over. For the Constitution it
is not fine, and the founder ruled the duty must move somewhere explicit.

It moved to **`governance/integrity/`**, which:

- replays a genesis baseline plus an append-only chain of amendment records into
  the hash each artifact is authorised to have *today*;
- reports `UNAUTHORISED_CHANGE`, `MISSING` and `UNGOVERNED_ADDITION`;
- refuses to give any verdict at all when the chain does not follow from itself;
- contains no code path that writes an amendment record, asserted over the AST;
- does not import `evolution.repair.spec`, asserted over the AST — importing it
  would re-fuse exactly what this amendment separated.

This makes `constitution/amendment-policy.ucl`'s `no_silent_amendment = true`
executable for the first time. It was prose; it is now arithmetic.

## 5. A third reading, split out

The harness had fused two more meanings under one function. Inside a run,
"continuity unchanged" should mean *this experiment disturbed nothing* — a live
before/after self-comparison. Compared against a freeze-time constant instead, it
would go permanently false the first time the institution lawfully amended
anything, and the experiment would report its own healthy runs as failures.

So `run()` now records three separate facts:

| Field | Question |
|---|---|
| `unchanged` | did this run change anything? (live, before vs after) |
| `frozen_baseline_reproduces` | does the historical experiment still reproduce? |
| `live_matches_freeze_time` | does the live tree still sit on July's bytes? |

The third is recorded and never gated on. It is expected to become `False`, and
that will be correct rather than alarming.

## 6. Scope

Sealed files touched: `evolution/repair/spec.py` (adds `CONTINUITY_DIR`, a path
constant outside `_FROZEN_TABLES`) and `tests/unit/test_repair_spec_frozen.py`
(reads it, plus three new guards). Declared in `AMENDED_BY_002` and enforced by
`test_amendment_002_touched_exactly_the_files_it_declared`.

That guard exists because the 001 guard could not see this amendment: measured
against the pre-001 pins, the set of moved files is identical, since 002 moves
two files 001 had already moved. A second amendment hiding inside the first one's
scope would have been invisible. Every future amendment needs its own guard for
the same reason — the cost of the content-pin design, and cheaper than a seal
nobody can audit.

`harness.py` is not a sealed file and is not in the pin set, but its change is
declared here because a reader looking for the amendment should find all of it in
one place.

## 7. Verification

```
python -m pytest tests/unit/ -k repair     153 passed
python -m pytest tests/unit/test_governance_integrity.py   15 passed
python -m governance.integrity             12 artifacts, all as authorised (exit 0)
```
