# Founder Decision Record — Canonical Integration

**Seven decisions. None executed.** No branch merged, no credential moved, no production authority changed.

**One is blocking:** Decision F. PRs #11–#22 and #27, #30–#32 were **not read** this pass — the GitHub tools were intermittently unavailable. If PR #31 already supersedes the phase train, Decisions A and B change. Everything below is provisional on that.

---

## Decision A — Sequential merge vs. clean re-cut

```yaml
founder_decision:
  decision: How to canonicalize the phase train
  verified_facts:
    - Phase train is cumulative; phase7 contains phase2-phase6 (ahead-counts 3->49, monotonic)
    - phase4/event-spine and build/consequence-gate are SIBLINGS, not ancestors
    - All phase branches are 127 commits behind main
    - phase7 -> main: 4 conflicts, ZERO in source code
    - Conflicts: policy/README.md, verifier/README.md, verifier/v2/criteria.json,
      contracts/outcome.schema.json (whose `required` arrays are IDENTICAL)
    - Merged tree: 679 tests pass; `import uniimente_kernel` succeeds
  assumptions:
    - PR #31 does not already supersede this (UNVERIFIED - Decision F)
  recommendation: >-
    Strategy B-prime. Merge phase7 into a new integration branch, resolve the four
    conflicts in main's favour, THEN convert SDK modules that duplicate a superior
    main implementation into thin clients. Not a clean re-cut.
  strongest_objection: >-
    A merge inherits 127 commits of divergence whose semantic drift no test covers.
    Green tests prove the tests pass, not that the mechanisms agree.
  alternatives:
    - Sequential merge of 11 branches - rejected, terminates at the same tree
    - Clean re-cut - rejected on evidence; discards 14 tested SDK files for no measured gain
    - Cherry-pick - rejected, complexity without benefit at 4 conflicts
    - Preserve main, archive - rejected, loses the SDK that breaks the pin
  reversible: true
  affected_repositories: [uniimente-kernel]
  migration_cost: one integration branch, four trivial resolutions, two thin-client rewrites
  rollback: delete the integration branch
  evidence_required: the 65-test delta reconciled before any tag
  smallest_authorized_next_action: >-
    git checkout -b integration/canonical-v1 origin/main  (no merge yet)
```

**I changed my mind here.** Before simulating I expected a painful rebase and would have recommended a clean re-cut. Four non-code conflicts and a green suite says otherwise. Simulate before selecting.

---

## Decision B — SDK release contents and packaging

```yaml
founder_decision:
  decision: What ships in uniimente-kernel-sdk v0.1.0, and where it lives
  verified_facts:
    - main policy/consequence_gate.py = 355 lines; SDK gate.py = 254
    - main events/spine.py = 320; SDK events.py = 259
    - SDK ledger.py = 272 vs main provenance/ledger.py = 120
    - SDK commit_witness.py = 245 vs main provenance/commit_witness.py = 122
    - phase7 SDK has 16 modules; only 8 are required for the first transaction
  assumptions:
    - Organs need a pip-installable artifact without cloning the kernel
  recommendation: >-
    Ship 8 modules. gate.py and events.py become THIN CLIENTS over the canonical
    root packages - never second engines. Where the SDK is ahead (ledger,
    commit_witness), move the implementation into the root package rather than
    keeping two copies. Exclude evolution, prompt_firewall, raw_vault, heartbeat,
    context_packet, constitution_check from v0.1.0.
  strongest_objection: >-
    An sdk-python/ subdirectory inside the kernel repository is a vendored client of
    the repository it lives in. That smell is real and I have not resolved it.
  alternatives:
    - Separate SDK repository - violates the five-repository constraint without an approved exception
    - No SDK; organs import the kernel directly - reintroduces the branch-pin problem
    - Ship all 16 modules - rejected; shipping a module because it exists is how surface grows
  reversible: true  (packaging location is harder to reverse than contents)
  affected_repositories: [uniimente-kernel, DALEOBANKS, WealthMachineIntelligence]
  migration_cost: two thin-client rewrites; two module relocations
  rollback: organs revert the pin; note there is no earlier version to revert TO
  evidence_required: exactly one gate engine and one event spine in the tree
  smallest_authorized_next_action: >-
    diff SDK gate.py against policy/consequence_gate.py and report the delta
```

---

## Decision C — DALEOBANKS local capability migration

```yaml
founder_decision:
  decision: Which DALEOBANKS mechanisms move to the Kernel and which stay local
  verified_facts:
    - constitution.py (83) is a ConstitutionGuard - hashes the constitution, re-verifies
      at runtime, DISARMS live posting on mismatch. Not a rival source of law.
    - capability.py (286) docstring - "This module authorizes nothing by itself - it
      verifies that a human did." Effect-bound, expiring, revocable, replay-protected.
    - ledger.py (289) is a hash-chained journal PLUS KillSwitch PLUS RateGovernor
    - evidence_policy.py (213) is the anti-cathedral rule; the Kernel has no equivalent
    - ZERO root-authority conflicts found
  assumptions:
    - Grant namespaces do not currently collide (UNVERIFIED - gate condition)
  recommendation: >-
    Kernel becomes canonical for grant issuance. DALEOBANKS capability.py is retained
    as a VERIFIER of Kernel grants. ConstitutionGuard and KillSwitch stay local,
    unchanged. ledger.py becomes an explicitly non-canonical local journal.
    PROMOTE evidence_policy.py into the Kernel.
  strongest_objection: >-
    Two grant implementations will drift. The counter is that one issues and one
    verifies, which is separation of powers rather than duplication - but only if the
    namespace check passes.
  reversible: true
  affected_repositories: [uniimente-kernel, DALEOBANKS]
  migration_cost: one adapter; one promotion; no deletions
  rollback: DALEOBANKS retains its local path throughout the compatibility period
  evidence_required: >-
    Proof that SDK grants and DALEOBANKS grants cannot both validate the same action
    with contradictory scope
  smallest_authorized_next_action: trace grant identifier namespaces in both implementations
```

**The KillSwitch argument, stated once more because it is easy to get backwards:** a kill switch that requires a network call to the Kernel **fails open under partition** — precisely when it is needed. Local fail-closed veto plus Kernel grant authority is defence in depth. Do not centralize it for conceptual tidiness.

---

## Decision D — Promote `evidence_policy.py` into the Kernel

```yaml
founder_decision:
  decision: Whether the anti-cathedral rule becomes constitutional
  verified_facts:
    - "When the external-evidence window is empty, internal expansion is denied -
      except security repair, compliance repair, critical reliability, and work that
      directly produces or unblocks external evidence."
    - Lexicographic metric hierarchy; a constitutional breach HARD-ZEROS the period
    - No Kernel equivalent exists
  recommendation: >-
    Promote. This is the executable form of the founder's own anti-simulation doctrine
    and it is the strongest single mechanism found in any organ. It would apply to
    every organ, not only DALEOBANKS.
  strongest_objection: >-
    A rule that blocks internal work when external evidence is absent could block the
    very integration work that produces the first external evidence. The existing
    carve-out for "work that unblocks external evidence" may not be precise enough to
    prevent deadlock.
  reversible: true
  affected_repositories: [uniimente-kernel, DALEOBANKS, WealthMachineIntelligence, PumpStation]
  migration_cost: one module move; carve-out needs tightening
  rollback: revert; DALEOBANKS keeps its copy throughout
  evidence_required: the carve-out cannot deadlock the first governed transaction
  smallest_authorized_next_action: >-
    test the rule against this session's own work - would it have blocked the merge audit?
```

---

## Decision E — Contract versioning policy

```yaml
founder_decision:
  decision: How contracts version across five repositories
  verified_facts:
    - 15 contracts on main; exactly 1 conflicted on merge; 0 semantically incompatible
    - The single conflict had IDENTICAL required arrays
  recommendation: >-
    0.x - interface may change on minor; organs pin exactly. 1.0 after the first
    governed transaction - additive bumps minor; field removal or enum narrowing bumps
    major and requires an adapter declaring information lost. This extends the existing
    adapter doctrine from 2 wire contracts to all 15.
  strongest_objection: >-
    Contract stability was measured against one branch. phase4/event-spine and
    build/consequence-gate were merge-tested but their contract diffs were not read.
  reversible: true
  affected_repositories: all five
  evidence_required: contract diff for the two sibling branches
  smallest_authorized_next_action: diff contracts/ across both sibling branches
```

---

## Decision F — PRs #31 and #32 — **BLOCKING**

```yaml
founder_decision:
  decision: Whether a later PR already supersedes the phase train
  verified_facts:
    - NONE. No PR was read this pass.
  assumptions:
    - The phase branches represent the most advanced integration work (UNVERIFIED)
  recommendation: >-
    Read PRs #11-#22, #27, #30, #31, #32 before executing Decision A. If #31
    supersedes the train, Strategy E replaces Strategy B-prime and this document's
    selection is void.
  strongest_objection: >-
    This is the strongest surviving attack on the entire analysis, and I cannot refute
    it. Recommending a merge strategy without reading the PR graph is exactly the
    error - inferring from partial evidence - that this pass exists to correct.
  reversible: true (nothing executed)
  affected_repositories: [uniimente-kernel]
  evidence_required: PR state, base, head, merge status, and file overlap for each
  smallest_authorized_next_action: read PR #31 and #32
```

---

## Decision G — Authorize the first canonical integration proof

```yaml
founder_decision:
  decision: Whether the sandboxed publication proof may proceed after A-F resolve
  verified_facts:
    - DALEOBANKS@phase5 tests/test_gate_publishing.py already asserts "the publishing
      family is 100% mediated" and covers 6 of the 14 required assertions
    - The remaining 4 are Kernel-unavailability, KillSwitch interaction, missing
      receipt, and reconciliation mismatch
  recommendation: >-
    Authorize AFTER Decisions A-C. Deterministic fake platform adapter. NO REAL PUBLIC
    POST. Real publication is a separate, separately authorized experiment.
  strongest_objection: >-
    One action class on one platform proves that path only. It does not prove the
    architecture generalizes to payments, wallet signing, or contract deployment.
  reversible: true - sandbox only, zero external effect
  affected_repositories: [uniimente-kernel, DALEOBANKS]
  evidence_required: all 14 assertions pass against the versioned SDK
  smallest_authorized_next_action: >-
    write the deterministic fake platform adapter - it has no dependency on A-F
```

---

## Metric

**Canonical Integration Completion: 0 / 11.**

All eleven capabilities exist as code. None satisfies all four conditions (merged **and** versioned **and** consumed from a canonical organ branch **and** exercised in the first governed transaction). Denominator and per-capability evidence in `UNIQUE_CAPABILITY_MATRIX.yaml`.

Unchanged and separate: `UNAUTHORIZED_EXTERNAL_EFFECTS = 0` (hard invariant) · `Clean Verified Outcome Count = 0` (institutional reality).

Branch count is **not** the metric. "0 of 15 merged" was branch evidence; the phase branches are cumulative, which collapses 15 branches to 11 unique capabilities and one merge candidate.
