# Abstention-to-resolution routing: pre-registration v2 (2026-11-13)

**Status:** pre-registered. Run v2 is a new pre-registration under the v1 rule ("a change is a new pre-registration
with a new run id and a new suite, and the old one is kept with its result"). Everything in
`../PREREGISTRATION.md` holds unchanged except the instrument corrections, seed and suite below.

## What changed, and when it was decided

- **Instrument corrections D1 and D2** (`../INSTRUMENT-DEFECTS.md`, committed at `44f2ed4` before any v1 held-out
  arm finished). They were found on development items only.
  - D1: the founder fills a path through lists.
  - D2: harm for a detached organ is "every organ in the item's `detach` list is unusable", the v1 text. "Any of
    them" is recorded as `harm_any_detached`, descriptive only.
  - The v2 harness is `cortex/evaluation/resolution/v2/harness_v2.py`. It imports the frozen v1 harness and replaces
    exactly `_fill`, `_harm` and the wrapper that records `harm_any_detached`.
- **Disclosure:** these files were written after v1's NEW arm finished, and its one-line summary was seen: 203 rows,
  29 errors, 44 closed, 19 harm. The corrections are exactly those recorded at `44f2ed4`; nothing in v2 was chosen
  from v1's per-item results.
- **The dividend's code is unchanged:** NEW is `1d6b1c1` in both runs. P is the #194 head `610c343` and B0 is
  `55e6d74`, as in v1.

## Suite

- Seed 20261114.
- Base items: `crossgeo-heldout-v0.3` standard items, excluding the development items and **every base item v1's
  suite used** (`suite_v2.py`).
- Labelling on B0 by the same rule and code (`label.py`): base controls, the floor partition for closure-eligible
  operators, no floor for the harm-scored operators, and the first 30 eligible per operator. A shortfall is
  reported, never padded.

## Endpoints, floors, ablations

These are v1's, unchanged, applied by `analyze_v2.py`, which is v1's `analyze.py` with v2's freeze. E1, E2 and H1
decide. A v1 result and a v2 result are both reported, and neither replaces the other.

## Freeze

`freeze.json` in this directory hashes the v2 files, the v1 files they import, and this file. It is committed
before the v2 candidates are drawn.
