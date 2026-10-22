# Binding a value larger than a receipt keeps: by artifact (2026-10-22)

## Problem

A mission action's receipt keeps bounded data (`greg/authority.py` `bounded`):
- a string past 16 KiB is cut to a `{prefix, truncated, sha256, length}` wrapper;
- a list is cut to 1000 items.

`bound_value` correctly refuses a cut value. Before this change, a long answer could therefore never reach the next action in the same mission.

## Mechanism

The change reuses the body's content-addressed artifact store (`greg/artifacts.py`). It adds no second store and no authority.

1. **Keeping, in exactly one place: `greg/authority.py` `keep_output`.**
   - This is called by the Gate executor in `AuthorityOffice.act`, the only place an action's output is bounded for a receipt.
   - When `bounded` would change the output, the whole output is put in the store as canonical JSON, with an object ceiling of 1 MiB (`OUTPUT_ARTIFACT_BYTES`).
   - The receipt's `result` then carries `output_artifact: {address, bytes, encoding}` beside the cut `output`. That output is unchanged and bounded as before.
   - If the body has no store, or the put fails (size, quota, a non-JSON value), the receipt records `{address: null, unavailable: <why>}`.
   - An uncut output records nothing.
2. **Opt-in edge: `"by": "artifact"`** on a `strategies[].bind[]` edge (contract schema extended).
   - `greg/missions.py` `artifact_output` reads the store only by the address the ledger receipt recorded.
   - `ArtifactStore.read` re-hashes the bytes against that address.
   - It also checks that `bounded(whole)` equals the output the receipt kept.
   - The edge's `type`, `render`, `template` and `max_bytes` still apply. Its default `max_bytes` is 1 MiB (`DEFAULT_ARTIFACT_BIND_BYTES`), and `validate_mission` refuses `max_bytes` above 64 KiB on any other edge.
   - If the receipt recorded no artifact, the output was kept whole and the edge binds it under the ordinary rules.
3. **Proof.** The action's binding record keeps `value_sha256` and adds `from_artifact` (the address the value was read from), next to `from_receipt`.

## Rule

- An edge without `by: artifact` behaves exactly as before: a cut value is refused even when an artifact exists.
- If an opted-in edge's artifact is missing, altered, foreign to its receipt, unreadable or never kept, the edge is `Unbound` with a reason, and the strategy holds.
- A prefix is never bound.
- Restart and replay re-read the same ledger receipt and the same address, so they bind the same value.

## Evidence

`tests/unit/test_greg_artifact_bind.py` has 13 tests. All of them fail on `13c963a0`, where the module's imports do not exist.

- **(a)** A 100 KB string binds whole and is hash-equal.
- **(b)** Without the opt-in, a cut value is refused.
- **(c)** A missing, tampered or foreign artifact is `Unbound`.
  - With no store, the receipt records why.
  - `max_bytes` above 64 KiB requires the artifact route.
- **(d)** End to end on a real Body:
  1. `fs.read` reads a 100 KB file, and its receipt is cut.
  2. `fs.write` binds the text through the route.
  3. The mission closes ACHIEVED on a check of the written file's sha256.

  The binding names the artifact address, and a restart between the two actions binds the same value.
- **Ablations:**
  - Remove the opt-in: the mission blocks with "no admissible strategy" and `b.txt` is never written.
  - Stub `keep_output` to keep nothing: the opted-in edge holds and the mission does not close.
  - Tamper with the artifact after action 1: nothing is written.

## What it does not do

- It grants nothing. The bound value is data, and it enters the next action's scope digest like any bound param.
- It does not prove the value is true, only that it is the bytes the earlier receipt's action produced. Like the receipt itself, it rests on the integrity of the hash-chained ledger and the content address.
- It does not make cut values visible to success-check predicates. Those still judge the kept output (`judge`: INSUFFICIENT beyond the prefix).

## Limits

- The whole output must be JSON-serialisable and at most 1 MiB as canonical JSON. A larger output keeps only its cut form, with the reason recorded.
- Kept outputs share the store's quota (512 objects, 64 MiB) with `artifact.store` imports. A body that cuts many large outputs can exhaust it. After that, later outputs record `unavailable` and `artifact.store` refuses until the founder reviews it. There is no garbage collection.
- A bound value up to 1 MiB enters the next action's params, and so whatever the Gate and mission records keep of those params. The ledger grows accordingly.
- Receipts written before this change carry no `output_artifact`. Their cut values stay unbindable.
