# Merge Train Recovery and Canonicalization

**Date:** 2026-07-27 · **Scope:** the canonical integration bottleneck only · **Status:** analysis. Nothing merged, no production authority or credential changed.

> **§10's selection is SUPERSEDED.** PRs #11–#22 were read after this document was written. See [`PR_GRAPH_FINDINGS.md`](PR_GRAPH_FINDINGS.md): the stall is a 10-deep stacked PR chain with one entry point, PR #19's declared base no longer contains PR #18's current tip, and **PR #21 (`build/consequence-gate`) lands on main with 0 conflicts and a 12-attack hostile suite, bypassing the stack entirely.** Land #21 first. Everything else in this document stands.

---

## The result, first

I simulated the merges instead of reasoning about them. The headline:

```
git merge origin/phase7/fast-capability-evolution   (onto current main)
  → 4 conflicts, 95 files staged
  → conflicts: policy/README.md, verifier/README.md,
               verifier/v2/criteria.json, contracts/outcome.schema.json
  → outcome.schema.json `required` arrays are IDENTICAL on both sides
  → resolved by keeping main
  → python -m pytest: 679 passed
  → import uniimente_kernel: OK
```

**The merge train is not blocked by technical incompatibility.** Zero source-code conflicts. Two READMEs, one criteria file, and one schema whose semantic content is identical. The combined suite is green.

The train stalled for organisational reasons — a mutual branch pin waiting on PRs that were never landed — and nobody ran the merge to find out it was nearly clean.

---

## 1. Known facts (`primary_source` — executed commands, this session)

| Fact | Evidence |
|---|---|
| Phase train is **cumulative** | `git merge-base --is-ancestor` for every phase branch → all contained in `phase7`, ahead-counts monotonic 3→5→7→10→11→23→30→39→41→45→49 |
| **Two siblings, not ancestors** | `phase4/event-spine` (38 ahead) and `build/consequence-gate` (12 ahead) are **NOT** in `phase7` |
| All phase branches **127 commits behind main** | `git rev-list --count origin/$b..origin/main` |
| `phase7` → main: **4 conflicts, 95 staged** | dry-run merge in disposable worktree |
| `build/consequence-gate` → main: **0 conflicts, 30 staged** | same |
| Merged tree: **679 tests pass** | `pytest` in the merged worktree |
| SDK imports against merged main | `import uniimente_kernel` → `ApprovalQueue`, `CapabilityError`, `BranchGenerator`, … |
| `sdk-python/tests` standalone: **184 pass** | `pytest sdk-python/tests` |
| Main is **ahead** on two core mechanisms | `policy/consequence_gate.py` 355 lines vs SDK `gate.py` 254; `events/spine.py` 320 vs SDK `events.py` 259 |
| SDK is ahead on two others | SDK `ledger.py` 272 vs main `provenance/ledger.py` 120; SDK `commit_witness.py` 245 vs main 122 |
| Organ pins target a **branch tip** | `DALEOBANKS@phase5/.../requirements.txt` → `uniimente-kernel@phase5/consequence-gate#subdirectory=sdk-python` |

## 2. Inferences (`inference`)

- The stall cause is the **mutual branch pin**, not code divergence. The organ pins a kernel branch; the kernel branch cannot land without breaking the pin; neither side moves.
- Main did not idle for 127 commits. It **independently reimplemented** the gate and event spine as root packages, in both cases more extensively than the SDK versions. The phase train's unique surviving contribution is therefore **packaging and tooling**, not core mechanism.
- `phase4/event-spine` being a sibling suggests it was superseded by main's own `events/spine.py` (320 lines vs the SDK's 259). Worth confirming before archiving.

## 3. Uncertainties — stated, not resolved

- **Test count does not reconcile.** main 560 + sdk 184 = 744, but the merged run reports **679**. A 65-test delta. Either ~65 SDK tests are not collected by root `pytest` configuration, or they duplicate root tests. **I did not resolve this and am not treating 679 as a validated superset.** Resolving it is a gate condition in §11.
- **PRs #11–#22, #27, #30, #31, #32 were not read.** The GitHub MCP tools were intermittently unavailable during this pass. All PR-state fields in `BRANCH_AND_PR_INVENTORY.json` are marked `UNKNOWN`. **The PR graph is incomplete and the strategy selection below is provisional on it.**
- Whether `build/consequence-gate` (clean merge, 30 files) supersedes or complements `phase5` is unresolved.
- No deployment manifests, network egress rules, secret stores, or service accounts inspected. **Mediation coverage remains uncomputable.**

## 4–5. Branch graph and phase lineage

```
origin/main ────────────────────────────────────────────── (127 commits ahead of every phase branch)
     │
     └── phase2/decision-ledger-extraction        +3  ─┐
         phase2/raw-vault-capability-extraction   +5   │
         phase2/firewall-context-extraction       +7   │ all contained in phase7
         phase2/guard-heartbeat-approval-extr.   +10   │ (cumulative lineage confirmed)
         phase2/sdk-packaging                    +11   │
         phase2/sdk-package-absorption           +23   │
         phase3/signal-contracts                 +30   │
         phase4/commit-witness                   +39   │
         phase5/consequence-gate                 +41   │
         phase6/first-evolution-cycle            +45   │
         phase7/fast-capability-evolution        +49  ─┘  ← cumulative tip

         phase4/event-spine                      +38   ✗ SIBLING — not in phase7
         build/consequence-gate                  +12   ✗ SIBLING — merges clean
```

| Phase | Capability added | In `phase7`? | Disposition |
|---|---|---|---|
| phase2 (×6) | SDK extraction: ledger, raw vault, firewall/context, guard/heartbeat/approval, packaging, absorption | yes | **superseded by phase7** — archive, do not merge individually |
| phase3/signal-contracts | typed signal contracts | yes | superseded by phase7 |
| phase4/commit-witness | commit witness | yes | superseded by phase7 |
| **phase4/event-spine** | event spine | **no** | **compare against main's `events/spine.py` (320 vs 259) before archiving** |
| phase5/consequence-gate | gate + the DALEOBANKS pin target | yes | superseded by phase7 |
| phase6/first-evolution-cycle | evolution cycle | yes | superseded by phase7 |
| phase7/fast-capability-evolution | fast capability evolution + full SDK | — | **merge candidate** |
| **build/consequence-gate** | unknown; merges clean | **no** | **inspect — 0 conflicts is suspicious in a good way** |

## 6. Unique capability inventory — what `phase7` gives main that main lacks

Net-new files on merge, by area:

| Area | Files | Verdict |
|---|---|---|
| `sdk-python/uniimente_kernel/` | 16 | **required** — the consumable package |
| `sdk-python/tests/` | 14 | required |
| `verifier/runs/` | 41 | evidence artifacts — preserve, not required for the transaction |
| `verifier/verify_sdk.py`, `verify_pkg.py`, `verify_contracts.py`, `v3/`, `v4/` | 5 | useful tooling |
| `evolution/experiments/`, `capsules/`, `run_first_cycle.py` | 6 | **Track B adjacent — do not put on the consequence path** |

**The core mechanisms are not in this list.** Main already has gate, spine, ledger, commit witness, passports. The train's contribution is the *package*, not the *machinery*.

## 7. Contract compatibility

`contracts/outcome.schema.json` was the only contract conflict, and its `required` array is byte-identical on both sides — a textual conflict with no semantic content. See `CONTRACT_COMPATIBILITY_MATRIX.yaml`. **No contract-breaking divergence found**, which is the single most encouraging fact in this document.

## 8. Authority analysis

The prior pass established zero root-authority conflicts in DALEOBANKS by reading the code. This pass adds one structural finding and one open question.

**Finding:** main's `policy/consequence_gate.py` (355 lines) is larger and more developed than the SDK's `gate.py` (254). If the SDK is merged as-is, the institution has **two gate implementations in one repository**. That is the multiple-active-authority condition arriving by merge rather than by drift.

**Therefore the SDK must not ship its own gate.** It must ship a **thin client** that calls the canonical `policy/consequence_gate.py`. This is the single most important design constraint in the recovery, and it is not what merging `phase7` unmodified would produce.

**Open question:** whether `DALEOBANKS/services/capability.py` and the SDK's `capability.py` share grant identifiers or namespaces. If they do, contradictory grants can exist simultaneously. **Not verified this pass** — it is a gate condition.

**Unchanged from the prior pass, and reaffirmed:** `ConstitutionGuard` and the local `KillSwitch` stay local. A kill switch that requires a network call fails open under partition. Local fail-closed veto plus Kernel grant authority is defence in depth, not duplicated authority.

## 9. Counterfactual recovery strategies — simulated, not argued

| | Strategy | Simulated result | Verdict |
|---|---|---|---|
| **A** | Sequential phase merge (11 merges) | Not run individually; all are ancestors of phase7, so the sequence terminates at the same tree | **Reject** — 11× the review burden for an identical result |
| **B** | Merge/rebase `phase7` onto main | **4 conflicts (all non-code), 679 tests pass, SDK imports** | **Viable — selected, with modification** |
| **C** | Selective cherry-pick | Not simulated; unnecessary given B's conflict count | Reject — complexity without benefit |
| **D** | Clean re-cut from main | Would discard 14 SDK test files and 41 verifier run records for no measured gain | **Reject** — I favoured this before simulating; the data does not support it |
| **E** | Adopt PR #31/#32 as base | **Cannot evaluate — PRs not read** | **Unresolved** — blocking |
| **F** | Preserve main, archive branches | Loses the SDK, the only thing that breaks the organ pin | Reject |

**I was wrong before running these.** Reasoning from "127 commits behind" I expected a painful rebase and would have recommended D. The simulation says 4 non-code conflicts and a green suite. **Simulate before selecting.**

## 10. Selected path — **B′ (modified phase7 merge)**

1. Merge `phase7/fast-capability-evolution` into a **new integration branch**, not main.
2. Resolve the 4 conflicts in main's favour (verified safe: identical schema semantics; the other three are docs/criteria).
3. **Replace the SDK's `gate.py` with a thin client** over canonical `policy/consequence_gate.py`. Same for any module duplicating a superior main implementation (`events.py` → `events/spine.py`).
4. Keep SDK modules where the SDK is ahead (`ledger.py`, `commit_witness.py`) — but **as the canonical implementation moved into the root package**, not as a parallel copy.
5. Resolve the 65-test delta before claiming any coverage number.
6. Cut `uniimente-kernel-sdk v0.1.0` from the result.
7. Repoint organ pins from branch tip to version.

**One canonical mechanism per capability. The SDK is a client, never a second engine.**

## 11. Exact sequence with gates

| # | Action | Gate |
|---|---|---|
| 1 | Read PRs #11–#22, #27, #30–#32; complete the inventory | Strategy E resolved or eliminated |
| 2 | `git checkout -b integration/canonical-v1 origin/main` | — |
| 3 | Merge `phase7`, resolve 4 conflicts in main's favour | 679 tests pass |
| 4 | Reconcile the 65-test delta | Every SDK test either collected or documented as duplicate |
| 5 | Diff SDK `gate.py` vs `policy/consequence_gate.py`; convert SDK to thin client | **one gate implementation in the repo** |
| 6 | Same for `events.py` vs `events/spine.py` | one spine |
| 7 | Inspect `build/consequence-gate` (0 conflicts, 30 files) | merge or archive with reason |
| 8 | Compare `phase4/event-spine` against main's spine | merge or archive with reason |
| 9 | Verify grant-namespace collision: SDK vs `DALEOBANKS/services/capability.py` | no contradictory grants possible |
| 10 | Tag `sdk-v0.1.0`, publish artifact + checksum | reproducible from the tagged commit |
| 11 | Repoint DALEOBANKS + WMI pins to `==0.1.0` | branch pins = 0 |
| 12 | Canonical integration proof, sandbox adapter | 14 assertions in §17 |

**Rollback points:** every step is a separate commit on a non-protected branch. Step 3 is revertible by branch deletion. Steps 5–6 are the only semantically risky ones and each is independently revertible.

## 12–13. SDK release and pin migration

See `CANONICAL_SDK_RELEASE_PLAN.md` and `CROSS_REPOSITORY_MIGRATION_PLAN.md`.

## 14. PumpStation and build-your-own-x boundary check

**PumpStation:** no kernel imports, no branch pins, no SDK dependency. Its `governance/admission.js` is JavaScript and shares no contract with the Python SDK. **Unaffected by this recovery.** Its wedge selection is explicitly out of scope for this pass and remains a founder decision.

**build-your-own-x:** 4 files, no code, no dependency, on no runtime path. The selected architecture does not place it on one. Role unchanged: mechanism anatomy atlas.

## 15. Track B isolation

Track B (Minimal Morphogenetic World) is **not** dependency-free, contrary to my prior claim. It shares:

- `evolution/` — `phase7` brings `evolution/experiments/`, `capsules/`, `run_first_cycle.py` into the same tree
- CI, branch space, engineering time
- `developmental/` is untouched by the merge — **verified**: no conflict, no staged change

**Isolation boundary:** Track B keeps `developmental/`. `evolution/` is shared and becomes a conflict surface. Proposal: the merge lands `evolution/experiments/` and `capsules/` as **evidence artifacts only**, with no import from `developmental/` into the consequence path and none the other way. Track B stays credential-free and consequence-inert; that property is unaffected by this merge.

**Do not pause Track B for this work.** Nothing here blocks it.

## 16. Metrics

**Canonical Integration Completion** — capability counts only when merged **and** versioned **and** consumed from a canonical organ branch **and** exercised in the first governed transaction.

Denominator (unique capabilities required for the first governed publication):
identity/principal · evidence envelope · policy decision · approval request · capability grant · commit witness · gate client · event envelope · receipt · reconciliation · local refusal/degraded mode = **11**

**Numerator today: 0 / 11.** Every one exists as code somewhere; **none** satisfies all four conditions. Baseline 0. Target after §11 step 12: 11.

Branch count is explicitly *not* the metric. "0 of 15 branches merged" was branch evidence; the phase branches are cumulative, so the true unique count is far lower.

Hard invariant unchanged: `UNAUTHORIZED_EXTERNAL_EFFECTS = 0`. Institutional outcome metric remains separate: `Clean Verified Outcome Count`, currently **0**.

## 17. Canonical integration proof

Sandbox adapter, deterministic fake platform, **no real public post**. Fourteen assertions: missing approval · forged approval · payload mutation · target mutation · expired grant · revoked grant · replay · exhausted grant · policy-version drift · Kernel unavailable · local KillSwitch active · evidence failure · missing receipt · reconciliation mismatch.

Six of these are covered by existing tests on `DALEOBANKS@phase5` (`tests/test_gate_publishing.py`). The new work is Kernel-unavailability, KillSwitch interaction, missing receipt, and reconciliation mismatch.

## 18. Institutional state of every component

| Component | State |
|---|---|
| Kernel gate, spine, ledger, passports (main) | `MERGED_ACTIVE` |
| `sdk-python/uniimente_kernel` | `IMPLEMENTED_UNMERGED` |
| DALEOBANKS gate adoption (`phase5`) | `IMPLEMENTED_UNMERGED` |
| DALEOBANKS `ConstitutionGuard`, `KillSwitch` | `MERGED_ACTIVE` |
| `evidence_policy.py` anti-cathedral rule | `MERGED_ACTIVE` in DALEOBANKS; **candidate for Kernel promotion** |
| phase2–phase6 branches | `SUPERSEDED` by phase7 |
| `phase4/event-spine`, `build/consequence-gate` | `UNKNOWN` — inspect |
| Credential Broker, Receipt Verifier | `DESCRIBED` |
| Any external outcome | `DESCRIBED` — none exists |

**No component is `EXTERNALLY_VALIDATED`.** Nothing here is an operating institutional capability.

## 19. Adversarial review

**"The phase train is obsolete."** *Partly survives.* Main independently overtook it on gate and spine. But the SDK package and 14 test files have no equivalent on main, and they are exactly what breaks the organ pin. Obsolete in mechanism, load-bearing in packaging.

**"PR #31 already supersedes it."** *Cannot be refuted — PRs unread.* This is the strongest surviving attack and it blocks final selection. Flagged as such rather than dismissed.

**"Main already contains the functionality under different names."** *Survives for gate and spine, fails for the SDK.* This is why the selected path converts SDK modules to thin clients rather than merging them as engines.

**"A clean re-cut repeats old mistakes."** *Neutralised* — the re-cut strategy was rejected on simulation evidence, not preference.

**"Sequential merging preserves hidden incompatibilities."** *Survives as a caution.* The 65-test delta is exactly such a hidden item and is now a gate.

**"The SDK should not be a separate package."** *Strong.* A `sdk-python/` inside the kernel repo that wraps kernel internals is a vendored client of itself. The counter-argument is that organs need a pip-installable artifact without cloning the kernel. **Unresolved — Decision B.**

**"DALEOBANKS' local implementation is safer than Kernel centralization."** *Survives for the KillSwitch,* which is why it stays local. Fails for grant authority, where two issuers can produce contradictory grants.

**"Repository separation causes more harm than benefit."** *Survives.* The mutual pin is a direct cost of separation. But a monorepo trades a merge-train problem for a blast-radius problem, and the fix — versioned releases — is cheaper than consolidation.

**"The publication test is too narrow to prove integration."** *Survives.* One action class on one platform proves that path only. Accepted as a first proof, not a general one.

## 20. What I changed my mind about, this pass

| Before simulation | After |
|---|---|
| Clean re-cut (D) is the right path | **B′** — the merge is nearly clean; re-cut discards tested work for nothing |
| 127 commits behind implies a painful rebase | 4 conflicts, none in source |
| Land the train as-is | **Do not** — merging the SDK's `gate.py` creates a second gate in one repo |
| Track B has no dependencies | It shares `evolution/`, CI, and branch space |
| "0 of 15 branches" is the metric | Branches are cumulative; the metric is unique capabilities, 0 of 11 |
