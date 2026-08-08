# Track-A runtime — lineage and authority

This branch carries the UNIIMENTE Track-A runtime implementation. It is based on
canonical `main` and is **separate from the planning lineage by design**.

## Why this branch exists

The super-planning round produced its decision record on branch
`claude/super-planning-prompt-h8l0oj` (draft PR #68), whose declared scope was
**planning-only**: no runtime change, and deleting the planning trees would leave
the kernel byte-identical to `main`.

Commit `d8c921552660675485f347637f8be08d6880f7cc` on that branch landed
`runtime/contract.py` and its guard tests under the founder's P0/P1
authorization. That work was authorized — but it crossed the branch's own stated
boundary. The PR description still claimed planning-only while the head contained
runtime implementation.

**That is scope drift, and the institution detected it in itself.** It is
preserved, not erased:

- No Git history was rewritten.
- `d8c9215` remains in PR #68's history as evidence that bounded implementation
  briefly entered the planning branch and was separated.
- PR #68 was corrected by an ordinary forward commit removing the runtime files,
  so its final diff again satisfies planning-only scope.
- The runtime work was transferred here byte-identically, with its frozen
  semantics unchanged.

## Lineage

| | |
|---|---|
| Base | `main` @ `8cb3074a4a837c89aada9bdb5351d7d9b3e4a9c1` |
| Transferred from | `d8c921552660675485f347637f8be08d6880f7cc` |
| Planning authority | Draft PR #68 |
| Continuation ledger | Issue #69 |
| Founder authorization | `authorization.p0_p1` (planning graph node) |
| Frozen contract hash | `408b197e73240c2c16cc805d495a1a0f5ed4ec9f6994299b49d1e14a509ea30c` |

`runtime/contract.py` was copied without modification. Its sha256 is
`e052a3c85f3233ada8c804abadbfe54d46592bf5c61bad79fcd6b02e2b0c55ec` on both
branches, and `CONTRACT_SHA256` still matches its own recomputed digest — the
transfer did not alter what was frozen.

## The two lineages

```
PR #68  —  planning truth, decision genome, founder intent, evidence architecture
   |
   |  authorizes
   v
Track-A PR  —  runtime spine, evaluator, candidate development, closure experiment
```

One canonical decision record → separate bounded implementation → evidence →
promotion only after proof. This is the same doctrine UNIIMENTE applies to its
organs, applied to its own development.

## Standing constraints on this branch

- PR #66 is immutable Track B research at `a6f14d3`. Do not touch it.
- No merge, no deploy, no publication, no production credentials, no money
  movement, no external effect of any kind.
- Everything here is `CONSEQUENCE_CLASS = INERT`.
- `VERIFIED_DEVELOPMENTAL_CLOSURES` may move `0 → 1` only when **all twelve**
  frozen conditions in `runtime/contract.py` hold independently. No rounding, no
  "essentially passed", no fixture standing in for runtime consumption.
- Reimplementing the linker, closure controller, registries or adapters is a
  contract violation. The measured defect was disconnection, not absence.
