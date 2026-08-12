# CONTRADICTION-0001 — a sealed experiment measures a corpus the institution must grow

Status: **OPEN — requires a founder decision.**
Raised: 2026-08-12, branch `claude/opus-maximus-audit-eay0ek`.
Preserved rather than resolved, per the standing order: *"If repository truth
contradicts the plan, preserve the contradiction, fail closed, and report it. Do not
silently weaken an invariant or expand scope."*

## The two things that cannot both hold

1. **Founder-approved deliverable.** Publish organ manifests for PumpStation and
   RESEARCH-IN so the Institutional Linker can see them. Manifests live in
   `organs/*.manifest.yaml`; that is the only path the linker reads.

2. **Sealed Package 3 experiment.** `evolution/repair/spec.py` freezes its
   measurement corpus as *the live institution*:

   ```python
   MEASUREMENT_CORPUS = {
       "corpus_id": "LIVE",
       "manifests": "organs/*.manifest.yaml",
       "contracts": "contracts/*.schema.json",
       "expected": "REQUIRED_EDGE_TRIPLES + REQUIRED_REFUSALS",
   }
   ```

   and pins `REQUIRED_REFUSALS["unresolved_count"] = 7`, measured when `organs/`
   held three manifests.

Adding two manifests takes the live linker report from 7 unresolved rows to 17. The
seal fires. **20 tests fail**, all from this one cause:

| File | Failing |
|---|---|
| `tests/unit/test_repair_harness.py` | 9 |
| `tests/unit/test_repair_candidates.py` | 8 |
| `tests/unit/test_repair_spec_frozen.py` | 1 |
| `tests/unit/test_repair_inertness.py` | 1 |
| `tests/unit/test_repair_adapters.py` | 1 |

This is the seal working, not breaking. `test_repair_spec_frozen.py` says so in its
own docstring: *"If organs/ or contracts/ change, this fails and the experiment must
be re-frozen rather than quietly re-interpreted."*

## What was NOT done, and why

No file under `evolution/repair/` or `tests/unit/test_repair*.py` was modified. That
is another session's sealed proof record (Package 3, merged PR #49). Amending it to
make this branch green would be:

- an in-place weakening of an invariant, which the standing order forbids;
- a silent invalidation of `docs/release/package-3/EVIDENCE_RECORD.json`, whose
  recorded run was measured against the three-manifest corpus.

The two new manifests were **not** withheld either — they are the approved
deliverable, and hiding them from `organs/` to keep a test green would be the same
dishonesty in the other direction.

## The real defect underneath

A sealed experiment whose result depends on a mutable glob is not reproducible. The
recorded Package 3 run cannot be re-executed today and get the same answer, and that
was already true before this branch — adding manifests only made it visible. Any
resolution should fix that property, not just restore the number 7.

## Options, with their exact costs

**Option A — pin the experiment to a frozen corpus snapshot.**
Copy the three freeze-time manifests into `evolution/repair/corpus/` byte-identically
and point the experiment there. No frozen expectation value changes; `SPEC_SHA256`
stays valid; the recorded run becomes reproducible for the first time. Cost: edits
five sealed files (spec + four test modules) to change *where* they read, never *what*
they expect. Nothing is deleted.

**Option B — re-freeze Package 3 against the five-manifest corpus.**
The remedy the spec's own docstring prescribes. Expectations get *stronger* (more
edges, 17 unresolved rows), so it is not a weakening. Cost: the experiment must be
re-run and `docs/release/package-3/{RESULTS,EVIDENCE_RECORD}` re-recorded, or the
spec will describe a run that no record satisfies. Preserve v1 values alongside v2
with lineage per §4.5.

**Option C — leave it open.**
The branch ships with 20 known-red tests and this record. Honest, and useless as a
merge candidate.

**Recommendation: Option A.** It is the only one that fixes the underlying
reproducibility defect, changes no frozen expectation, and keeps the existing
Package 3 evidence record valid. It should still be a founder decision because it
touches a sealed experiment.

## Current state on this branch

`python -m pytest` → **539 passed, 21 failed.** 20 failures are this contradiction.
The 21st is `tests/unit/test_closure.py::test_integrated_modules_close_all_five`,
which is a separate, smaller matter recorded in the pull request body.

All 65 tests covering the work this branch actually adds — blueprint, discovery,
knowledge graph, decision router — pass. `python verifier/v2/verify.py` reports
V1, V3, V4, V5 green and V2 red for the reason above.
