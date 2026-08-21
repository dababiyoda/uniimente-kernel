# Canonical Authority Decision

**Gate A is satisfiable, and the answer is not the implementation that was easiest to merge.**

Executable evidence: [`DIFFERENTIAL_AUTHORITY_CONFORMANCE.json`](DIFFERENTIAL_AUTHORITY_CONFORMANCE.json) ·
[`AUTHORITY_SEMANTICS_MATRIX.yaml`](AUTHORITY_SEMANTICS_MATRIX.yaml) ·
[`TEST_COUNT_EXPLANATION.md`](TEST_COUNT_EXPLANATION.md)

| | refusals earned | doctrinally wrong | cannot express |
|---|---:|---:|---:|
| `main` root engine | 10 | 6 | 12 |
| **PR #21** `build/consequence-gate` | **24** | 3 | **2** |
| phase7 SDK | 10 | 1 | 18 |

One shared 30-case corpus, three git worktrees, drift injected at the same pipeline position in each engine. A case an engine cannot structurally pose is recorded `ABSENT`, never given a fabricated verdict.

---

## The decision

**Strategy C — a composed canonical engine, with PR #21's 15-stage pipeline as the spine.**

Not strategy A (PR #21 wholesale) and not B (main remains canonical). Three of the four rows where main is stronger are real and must survive; the SDK owns the only control that closes two shared gaps.

| Component | Owner | Why |
|---|---|---|
| Pipeline, stages, refusal taxonomy | **PR #21** | 24/30 refusals; 11 revalidation conditions vs main's 6 |
| Intent fingerprint | **PR #21** | 11 bound fields vs main's 3 — directly fixes defects 27 and 28 |
| Signed approval artifact | **PR #21** | main and SDK have no approval object at all |
| Ed25519 signing / receipt verification | **PR #21** | main's HMAC cannot support independent verification |
| Constitutional policy evaluation | **main** | PR #21's evaluator reads only `consequence_class` |
| Identity / PassportRegistry | **main** | PR #21 checks only that `legal_principal` is non-empty |
| Budget reserve→commit→release unwind | **main** | only engine that unwinds on every failure path |
| `named_targets` + `permitted_actions` grant scoping | **phase7 SDK** | only engine that refuses cases 25 and 26 |
| KillSwitch (fail-closed veto) | **DALEOBANKS, local** | stays local — see below |

### Why not simply take main

Three verified authority defects, each confirmed by direct execution outside the harness ([`verify_main_holes.py`](DIFFERENTIAL_AUTHORITY_CONFORMANCE.json) — see `verified_defects`):

- **Case 26 — undeclared capability.** An actor whose passport declares only `['draft.publish']` executed `requested_capability='funds.transfer'` and reached `state='recorded'`. Nothing binds the requested capability to the passport.
- **Case 27 — authority escalation.** `consequence_class` raised from `external_contact` to `irreversible` inside the commit window still reached `state='recorded'`. `_reauthorize_at_commit` refuses only on `Verdict.DENY`, so a commit-time `REQUIRE_HUMAN` is silently discarded — escalating *into* a class that mandates a human is how you bypass the human.
- **Case 28 — cross-actor redemption.** A grant issued to actor A was redeemed by actor B. `bound_effect_hash = sha256({payload, target, action_class})` omits the grantee.

All three share one root cause: **the effect hash is too narrow.** PR #21's 11-field fingerprint refuses all three.

And the decisive architectural row: **main signs witnesses with symmetric HMAC-SHA256**, dev-key literal `b"uniimente-dev-witness-key"`. Whoever can verify can forge. An institution whose thesis is *attributable autonomy* cannot rest attribution on a shared secret.

### Why not simply take PR #21

- Its policy evaluator inspects `consequence_class` and nothing else — no constitution, no evidence content, no target, no capability.
- It has no identity registry.
- **It does not run from a clean clone.** It imports `pydantic`, `cryptography` and `cffi`; its `requirements-dev.txt` is byte-identical to main's and declares none of them. A hostile suite that cannot be executed is not protecting anything. Cheap to fix, disqualifying until fixed.
- Cases 25 and 26 pass through it too.

---

## Adversarial pass — which attacks survive

I tried to break my own conclusion on all ten fronts. Four survive.

**SURVIVES — 3. "Phase7 SDK contains the strongest actual engine."** Partly true and I was wrong to expect otherwise. The SDK is the *only* engine that refuses cases 25 and 26, because it is the only one that scopes grants by `named_targets` and `permitted_actions`. Mutation-detection is not an allowlist. This attack is why the decision is Strategy C rather than "PR #21 wins".

**SURVIVES — 5. "Centralizing grant semantics creates an availability hazard."** Correct and unrebutted. A veto requiring a network call to the Kernel fails **open** under partition — precisely when needed. This is why DALEOBANKS keeps its local KillSwitch. It is also why the SDK finding matters: the SDK's KillSwitch **does not gate execution** (verified — `commit_witness.py` only ever *sets* it, on postcondition failure, and never reads `.armed`). Anyone who assumed the SDK carried a working local veto was wrong, including me before I tested it.

**SURVIVES — 6. "Differential equivalence hides different trust roots."** The strongest attack of the ten. The engines are not merely differently-featured; main's trust root is a symmetric secret and PR #21's is an Ed25519 keypair. These are not reconcilable by composition — one must be chosen, and choosing PR #21's means every existing main-signed witness is unverifiable under the new root. **Migration of historical witnesses is unsolved and is called out as a founder decision below.**

**SURVIVES — 7. "The 679 green tests are misleading because imports select the wrong implementation."** Not refuted. Gate B proved the test *inventory* is additive (495 + 184, byte-for-byte, zero collisions) and that the merged tree is green. It did **not** prove that the 495 main tests exercise the same mechanisms after the merge, and 127 commits of divergence sit under it. Inventory closure is not semantic closure.

**Falls — 1. "PR #21 is obsolete."** It earns 24 of 30 refusals against a corpus written after it. Not obsolete.

**Falls — 2. "Current main is incomplete despite being larger."** Sustained, not refuted: main is 355 lines against PR #21's 571+122+33 and expresses 12 fewer cases. Size was never the metric.

**Falls — 4. "The SDK should remain an independent local enforcement library."** This is precisely the second-authority hazard. The SDK embeds its own in-process authority objects while being named `uniimente_kernel` — case 22 is `ABSENT` for it because *there is no remote kernel to be unavailable*. It must become a client.

**Falls — 9. "A clean re-cut is safer than composition."** Would discard 24 earned refusals and the only working Ed25519 trust root.

**Falls — 10. "The discrepancy reveals unexecuted code."** Refuted outright — the 65 were my own measurement error (see Gate B).

**Undetermined — 8. "PR #31's merged linker is incompatible with the selected contracts."** I did not test the linker against PR #21's contracts. Recorded as unverified, not as safe.

---

## Gate status

```
ACTIVE_CANONICAL_CONSEQUENCE_ENGINES = 3     ← Gate A NOT YET SATISFIED
UNEXPLAINED_TEST_COLLECTION_DELTA    = 0     ← Gate B SATISFIED
Gate C (sandbox transaction)                 ← NOT ATTEMPTED
```

**Gate A is analysed, not closed.** Three engines capable of independently authorizing an effect exist in the tree today. The decision above says which one wins and what is promoted into it, but **no code has been written to collapse them**, and I am not reporting otherwise.

Per the standing instruction — *open a draft PR only after local evidence shows `ACTIVE_CANONICAL_CONSEQUENCE_ENGINES = 1`* — the branch `agent/canonical-authority-rc1` was **not** created and no code PR was opened. Gate A is not met, so the precondition is not met.

---

## Founder decisions

### Decision 1 — Canonical authority implementation

```yaml
founder_decision:
  decision: Which implementation owns the active consequence semantics
  verified_facts:
    - PR21 earns 24/30 refusals; main 10; sdk 10
    - PR21 cannot express 2 cases; main 12; sdk 18
    - main has 3 verified authority defects (cases 26, 27, 28), each confirmed
      by direct execution outside the harness
    - main's effect hash binds 3 fields; PR21's binds 11
    - main signs witnesses with symmetric HMAC; PR21 with Ed25519
    - PR21's policy evaluator reads consequence_class only
    - the sdk is the only engine refusing cases 25 and 26
  recommendation: >-
    Strategy C. PR21's pipeline becomes the canonical spine. Promote main's
    constitutional evaluator, PassportRegistry and budget unwind into it.
    Promote the sdk's named_targets and permitted_actions grant scoping.
    Retain main's engine as a registered SUPERSEDED implementation and as a
    regression oracle - it is not deleted.
  strongest_opposition: >-
    Attack 6 survives. Composing two engines with different trust roots does not
    merge the trust roots. Choosing Ed25519 renders every existing HMAC-signed
    witness unverifiable under the new root, and I have not solved that migration.
  alternatives:
    - PR21 wholesale - rejected; loses constitutional evaluation and identity
    - main remains canonical - rejected on three verified defects
    - clean re-cut - rejected; discards 24 earned refusals
    - keep all three behind a router - rejected; that IS multiple active authorities
  reversible: true (nothing executed)
  authority_implications: changes which code may authorize an external effect
  repositories_affected: [uniimente-kernel, DALEOBANKS, WealthMachineIntelligence, PumpStation]
  migration: >-
    Unsolved for historical witnesses. Every witness signed under the HMAC root
    needs either re-signing under the Ed25519 root or an explicit
    "verifiable-under-legacy-root-only" marker. This is the real cost.
  rollback: revert the branch; main's engine is untouched throughout
  evidence_required: >-
    a composed engine passing all 30 cases, with cases 25 and 26 refused
  smallest_authorized_next_action: >-
    declare pydantic, cryptography and cffi in PR21's requirements-dev.txt and
    confirm its 36 tests pass from a clean clone
```

### Decision 2 — PR #21 disposition

**Recommendation: extract the mechanisms, do not merge the PR whole.** Its pipeline, fingerprint, signed approvals and Ed25519 root are the canonical spine. Its policy evaluator and identity handling are weaker than main's and must not land. Merging it whole would create the second engine this pass exists to prevent. Its hostile suite becomes the conformance suite regardless of the engine outcome. **Blocking sub-issue:** the three undeclared dependencies.

### Decision 3 — SDK boundary

**Recommendation: the SDK becomes a client and stops being an authority.** `gate.py` and `capability.py` become thin clients over the canonical root. `named_targets`/`permitted_actions` move *into* the root as grant-scoping. `commit_witness.py` and `ledger.py` are ahead of main's and their implementations move into the root rather than being kept twice. Contracts and verification helpers stay in the SDK. **The KillSwitch does not move — it is verified non-functional as a veto and must not be presented as one.**

### Decision 4 — DALEOBANKS local capability

**Recommendation: unchanged from the prior pass, and now better supported.** Kernel becomes canonical for grant issuance; DALEOBANKS `capability.py` is retained as a *verifier*; `ConstitutionGuard` and `KillSwitch` stay local and unchanged. The availability argument (attack 5) survived adversarial review. **Caveat:** the DALEOBANKS column of the matrix is source-read from a prior pass and was **not** re-executed this session; it is not evidence of equal weight to the three executed columns.

### Decision 5 — PR #32 recovery

**Not attempted this pass.** `PR32_RECOVERY_CLASSIFICATION.yaml` is not written. Recorded as outstanding rather than quietly dropped.

---

## What was not done

Stated plainly, because a gap named is worth more than a gap implied:

- `COMMIT_DAG_RECONSTRUCTION.json` — not produced. The DAG facts established in the prior pass stand, but the full per-tip `commit_lineage` record across all branches and both organ repositories was not built.
- `SDK_MODULE_DISPOSITION.yaml` — the four load-bearing modules are dispositioned in Decision 3; the full 14-module YAML is not written.
- `PR21_DISPOSITION.md`, `PR32_RECOVERY_CLASSIFICATION.yaml`, `RC1_IMPLEMENTATION_PLAN.md`, `FOUNDER_DECISION_RECORD_V2.md` — not written as separate artifacts. Decisions 1–5 above carry their content.
- **Gate C — neither sandbox proof was attempted.** No authority-path proof, no cross-organ proof.
- `agent/canonical-authority-rc1` — not created, because Gate A is not met.
- Track B (morphogenetic) — untouched, as required. No digital cell was granted authority, nothing was moved onto the consequence path, and no production dependency on morphogenesis was created.

Nothing was merged to `main`. No credential was moved. No external effect was produced.
