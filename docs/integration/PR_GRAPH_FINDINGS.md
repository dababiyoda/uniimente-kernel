# PR Graph — Decision F resolved

**Read 2026-07-27, after the merge simulations.** These findings **change the recommendation in `MERGE_TRAIN_RECOVERY_AND_CANONICALIZATION.md` §10.** That document's selection (B′, merge `phase7`) is superseded by the option below.

## 1. The stall has a precise mechanical cause: a 10-deep stacked PR chain

```
#11  phase2/decision-ledger-extraction        → main          ← only entry point
#12  phase2/raw-vault-capability-extraction   → #11
#13  phase2/firewall-context-extraction       → #12
#14  phase2/guard-heartbeat-approval-extr.    → #13
#15  phase2/sdk-packaging                     → #14
#16  phase2/sdk-package-absorption            → #15
#17  phase3/signal-contracts                  → #16
#18  phase4/event-spine                       → #17
#19  phase4/commit-witness                    → #18
#20  docs/egregore                            → #19
#22  phase5/consequence-gate                  → #19

#21  build/consequence-gate                   → main          ← INDEPENDENT
```

**Eleven open PRs. Exactly two target `main`.** Every other PR is based on its predecessor, so the chain can only land in strict order starting at #11. One stalled review anywhere blocks everything downstream. This is the mechanism behind the stall I could previously only infer.

## 2. The PR graph and the commit graph disagree — a real hazard

PR #19 declares its base as `phase4/event-spine`. Git says otherwise:

```
event-spine IS ancestor of commit-witness?  NO
common ancestor: acddc29 "Phase 4: event spine (3/3d) — final run record"
  event-spine    +2 commits since
  commit-witness +3 commits since
```

**`phase4/event-spine` was force-pushed or rebased after `phase4/commit-witness` branched from it.** Merging #18 then #19 in PR order would not reproduce what #19 was built and tested against. This resolves my earlier "sibling, not ancestor" puzzle — it is not a design choice, it is branch drift under an open PR.

**Landing the stack in PR order is unsafe without re-verifying #19 against the current #18 tip.**

## 3. PR #21 is a clean, self-contained shortcut past the entire stack

`build/consequence-gate → main`, **0 conflicts, 30 files**. Its commit log is a complete vertical slice:

```
(1/7)  packaging + crypto primitives (Ed25519, canonical-JSON hashing)
(2/7)  contracts base + institutional + venture (frozen, extra-forbid, tz-aware)
(3/7)  action + execution contracts (fingerprint-bound approvals, CommitWitness)
(4/7)  governance contracts + contract registry (20 contracts)
(5/7)  event spine — append-only hash-chained JSONL + merkle sealing
(6/7)  gate support — fingerprint binding, revalidation, refusal taxonomy
(7/8)  the 15-stage Consequence Gate pipeline (fail-closed, deterministic)
(8/9)  founder approval authority + witness-bounded adapters
(9/10) spine tests + happy-path pipeline tests
(10/11) contract invariant tests (20 frozen contracts, literal guards)
(11/12) hostile test suite — 12 attacks, all must fail closed
(12/12) HANDOFF.md — state, evidence, ADRs, next-agent instructions
```

It carries fingerprint-bound approvals, a commit witness, a fail-closed 15-stage gate, 20 frozen contracts, **a hostile suite of 12 attacks that must all fail closed**, and a handoff document. It depends on nothing in the stack.

## 4. #31 does not supersede the train — Decision F answered

| PR | State | Base | Verdict |
|---|---|---|---|
| **#31** | closed, **MERGED** | `integration/uniimente-egregore-v1` | Phase Zero three-organ connection layer (doctrine, manifests, linker, adapters, causal episode). **A different workstream that already landed** — it produced `organs/`, `linker/`, `adapters/` on main. Does **not** supersede the SDK train. |
| **#30** | closed, **MERGED** | `integration/uniimente-egregore-v1` | Morphogenetic control contract + ADE-1 translation |
| **#32** | closed, **NOT merged** | `integration/uniimente-egregore-v1` | "Phases 6+7 + Regenerative Treasury: media foundry, business foundry, capital metabolism" — **closed unmerged; lost work worth recovering** |
| **#27** | closed, **NOT merged** | main | "Bounded Foundry and OMNIMORPH modules" — yet `foundry/` and `omnimorph/` exist on main, so this re-landed by another route. Confirm before archiving. |

`integration/uniimente-egregore-v1` is an **existing integration branch** that #30 and #31 already merged into — precedent for the integration-branch approach, and a candidate base.

## 5. Revised recommendation — supersedes §10

**Land #21 first.** It is strictly better than merging `phase7` as the first move:

| | #21 `build/consequence-gate` | `phase7` merge (prior selection) |
|---|---|---|
| Conflicts | **0** | 4 |
| Files | 30 | 95 |
| Targets main directly | **yes** | yes, but 127 behind |
| Depends on the stack | **no** | contains it |
| Hostile test suite | **yes, 12 attacks** | not observed |
| Handoff doc | **yes** | no |
| Duplicate-engine risk | must still be checked | high (two gates) |

Sequence: **land #21 → re-verify #19 against the current #18 tip → then decide whether the stack still adds anything the slice lacks.** Much of the stack may become archivable rather than mergeable.

**Still required before #21 lands:** confirm its 15-stage gate does not become a *second* engine alongside `policy/consequence_gate.py` (355 lines). The one-canonical-engine constraint from §10 applies unchanged, and is now the primary open question rather than conflict count.

## 6. What I changed my mind about, again

| Before reading the PRs | After |
|---|---|
| Merge `phase7` first (B′) | **Land #21 first** — 0 conflicts, self-contained, hostile-tested |
| `phase4/event-spine` is a design sibling | It is **branch drift under an open PR**; #19's declared base no longer contains it |
| Stall cause inferred as "mutual branch pin" | Confirmed **and** compounded: a 10-deep stacked chain with one entry point |
| #31 might supersede the train (BLOCKING) | **Resolved** — different workstream, already merged, does not supersede |
| 15 branches to triage | 11 open PRs, of which **one is independently landable today** |

I would not have found #21 by reading git alone. The branch was in my inventory as "UNKNOWN — merges cleanly, lineage unknown." Reading the PR told me what it was.
