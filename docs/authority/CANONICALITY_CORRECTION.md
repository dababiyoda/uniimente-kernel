# Canonicality Correction

**Gate A was closed dishonestly. This records why, and what changed.**

## The contradiction

`aperture/dispositions.py` classified `policy/consequence_gate.py` as `SUPERSEDED` and named `aperture.issuer` canonical. `scripts/ci/check_authority_singleton.py` globbed `**/consequence_gate.py`, found that same file, and printed *"exactly one source of authority"*.

Two hardcoded lists. They disagreed. Gate A had closed on the strength of whichever one was consulted — and the one CI actually ran was blessing the engine with three verified authority defects.

## Root cause

**The old check counted filenames, not authority.** It would have passed identically on a tree where the gate could be bypassed entirely, and it would have *failed* on a tree where the canonical gate had legitimately moved. It could not express "the canonical gate is now somewhere else."

The deeper cause is duplication: two mechanisms each keeping their own idea of what is canonical. Anything that can drift, will.

## Correction

One artifact, `authority/canonical-authority.yaml`, is now the single source of truth. It is read by:

- `aperture/manifest.py` — the loader, which refuses a self-contradictory manifest at load
- `aperture/dispositions.py` — no longer keeps its own list
- `scripts/ci/check_canonical_authority.py` — 13 checks, all reading the manifest
- `tests/unit/test_no_parallel_authority.py` and `test_issuer_uniqueness.py`
- the runtime, via `manifest.revocation_policy_for()` at every execution

**Drift is now itself a test failure.** `dispositions.agrees_with_manifest()` compares the registry against the manifest on both classification and issuance, and `check_runtime_matches_disposition_registry` fails the build if they disagree. The exact condition that invalidated the previous closure is now detectable by the build that would have hidden it.

## Why the old check was not rewritten

`scripts/ci/check_authority_singleton.py` is **unchanged**. Its replacement is added as a separate CI job.

A component must not alter its own approval requirements. Rewriting the check that polices this change, as part of this change, is precisely that failure mode. The corrected check is preserved for review and CI now runs both; the stricter one governs.

**Residual:** the old check's "Consequence Gate" label is stale. It permits nothing wrong — it counts filenames — but it no longer describes authority. Swapping it is a founder decision, not an agent decision.
