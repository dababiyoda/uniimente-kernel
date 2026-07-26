# Rollback Instructions

## Anchors

| Ref | Commit | Meaning |
|---|---|---|
| `archive/main-2026-07-19` | `3d9b5779a7093d6ddd07f225c8329ead6d0c6393` | Immutable rollback target |
| `release/canonical-v1` | `8b55efa6393d811ff544d22006f441f03dc8dc19` | Candidate + baseline CI |
| candidate base | `a4fa43e8c74b56130314c21736dfaf767567f3de` | Untouched integration head |

**The commit SHA is the real anchor.** Refs are names for it.

## DEVIATION — archive is a branch, not a tag

The founder specified an immutable **tag**. Tag creation is not possible in this session: the git proxy returns HTTP 403 on tag pushes, and the available GitHub tooling exposes read operations for tags but no create operation. A **branch** was created at the identical commit instead.

**Consequence:** a branch is mutable unless protected, where an annotated tag would be immutable by default.

**Required founder action:** either add branch protection to `archive/main-2026-07-19`, or create the tag manually:

```
git tag -a archive/main-2026-07-19 3d9b5779a7093d6ddd07f225c8329ead6d0c6393 \
  -m "Immutable archive of main prior to canonical-line evaluation"
git push origin archive/main-2026-07-19
```

Until then the archive is recoverable but not tamper-evident.

## Rollback procedure

Nothing in Package 1 requires rollback — `main` was never moved and nothing was merged. These instructions apply after a future canonical merge.

1. **Restore.** `main` returns to `3d9b5779a7093d6ddd07f225c8329ead6d0c6393`. Use a revert commit, not a force push — history is never rewritten.
2. **Revoke.** Every capability grant issued after the release is revoked. Grants are TTL-bounded; expiry is not sufficient — revoke explicitly.
3. **Preserve.** All events, evidence, provenance records, and verifier runs are retained. Rollback removes authority, never evidence.
4. **Do not delete.** `release/canonical-v1` and every historical branch remain. `UNIIMENTE_FINAL_BUILD_ORDER` §2 and §12 forbid destructive simplification.
5. **Record.** Write a failed-release record naming the cause, the reverting commit, what was revoked, and what evidence was preserved.

## What Package 1 can currently undo

| Action | Reversal |
|---|---|
| `archive/main-2026-07-19` created | Delete branch — but only after a tag exists |
| `release/canonical-v1` created | Delete branch; base commit `a4fa43e` remains reachable from integration branches |
| Baseline CI commit `8b55efa` | Revert; nothing else on the candidate depends on it |
| Two existing workflows scoped to `workflow_dispatch` | Revert the same commit; the files were preserved, not deleted |
| Draft PR opened | Close; it is a draft and merges nothing |

**`main` is untouched. No merge, no deploy, no external effect, no spend.**
