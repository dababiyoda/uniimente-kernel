<!-- GENERATED FILE — DO NOT EDIT BY HAND -->
<!-- source: planning/graph/nodes/ via planning/compiler/render.py -->
<!-- graph-digest: c65a4d773a988a1c54da122175adc896c5bb2033a49f3813f0c4da5aadc3a36d -->
<!-- projection: PR66_DISPOSITION_DOSSIER -->


# PR #66 — Immutable Research Specimen, Shadow State and Disposition

**PR #66 received zero writes during this round.** Its state is reconstructed
here from commits, source, tests, CI and evidence artifacts, so that the pull
request description stops being the place where the truth about PR #66 has to
live. The description becomes a projection that can be regenerated from this
capsule, exactly as evidence-first architecture requires everywhere else.

Every claim in the existing body is classified `SUPPORTED`, `STALE`,
`SUPERSEDED_BY_OWN_TIP`, `FALSIFIED` or `UNRESOLVED`.

The proposed replacement body and disposition comment are stored **inert**.
Applying either is a later, explicit founder action.

**3 nodes** projected from graph digest `c65a4d773a988a1c`. Regenerate with `python planning/compiler/render.py`.

## pr capsule (1)

### `pr66.state_capsule` — PR #66 state capsule — SHA-bound reconstruction

**Evidence:** `verified_by_execution`
- `dababiyoda/uniimente-kernel` @ `a6f14d344f2c` · via `pull_request_read(get|get_check_runs); git log main..origin/claude/uniimente-repo-audit-jpytcy`

- **subject_head**: a6f14d344f2ca073fd334a885e5c2bdb921d082e
- **subject_base**: 8cb3074a4a837c89aada9bdb5351d7d9b3e4a9c1
- **branch**: claude/uniimente-repo-audit-jpytcy
- **captured_at**: 2026-08-08
- **state**:
  - **open**: yes
  - **draft**: yes
  - **merged**: no
  - **mergeable_state**: clean
- **scale**:
  - **commits**: 133
  - **changed_files**: 240
  - **additions**: 145317
  - **deletions**: 2
  - **comments**: 9
- **ci**:
  - **checks**: 5
  - **conclusion**: all success
  - **run**: 31244720948
- **suite_local**: 924 passed · 1 skipped · 24 xfailed · 0 failed
- **suite_ci_merge_ref**: 922 passed · 3 skipped · 24 xfailed · 0 failed
- **gates**:
  - **F**: UNMEASURED
  - **G**: UNMEASURED
  - **R8**: NOT_RUN
  - **r8_eligibility**: NOT_ELIGIBLE
- **body_claims_classified**:
  - - **claim**: Head 15623a9
    - **status**: STALE
    - **actual**: a6f14d3 — one commit further (RA-2)
  - - **claim**: next active bottleneck is truthful and exclusive authority over root-generation retirement
    - **status**: SUPERSEDED_BY_OWN_TIP
    - **actual**: RA-2 corrected the framing: the coupling is broader than retirement authority. Canonical and legacy repair share load-bearing state.
  - - **claim**: 924 passed · 1 skipped · 24 xfailed
    - **status**: SUPPORTED
  - - **claim**: CI merge-ref 922 passed · 3 skipped · 24 xfailed
    - **status**: SUPPORTED
  - - **claim**: Gate F/G UNMEASURED, R8 NOT ELIGIBLE
    - **status**: SUPPORTED
  - - **claim**: the conventional durable workflow engine still wins on the evidence available
    - **status**: SUPPORTED_AND_LOAD_BEARING
  - - **claim**: Design A removes the legacy authority cleanly
    - **status**: FALSIFIED
    - **actual**: 21 regressions, 0 strict XPASS; A, E and H all eliminated
  - - **claim**: DUAL_REPAIR_SEARCHES detector ordering is correct
    - **status**: UNRESOLVED
    - **actual**: correct but uncommitted; arrived inside a falsified candidate and still needs its own negative control
- **mechanisms_validated**:
  - 2D sender-owned ingress (ENFORCED)
  - pre-arrival control (IMPLEMENTED AND ADVERSARIALLY VERIFIED, PA-1..PA-5)
  - causal need closure (NC-3, the only runtime change in the series)
  - author-direction classification (probe-bound, fails closed, no kind fallback)
  - one source of truth (0 runtime reads; hostile-projection twin identical)
- **mechanisms_falsified**:
  - Design A — remove the legacy ledger (21 regressions, 0 XPASS)
  - Design E — remove the legacy repair path entirely (strictly larger than A)
  - Design H — supervisor ownership (rejected on authority grounds)
  - LC-2b — recommended design was wrong; implementing it proved it
  - LC-2b' — second design falsified, actual mechanism located
- **mechanisms_surviving_unadopted**:
  - B
  - C
  - D
  - F
- **leading_hypothesis**: B + D — separate the ledger's bookkeeping from its authority; centralise retirement. NOT ADOPTED.
- **self_reported_defects**: The branch documents its own errors at unusual length: edge-id collision between roots, settlement driven from the wrong place, eight vacuous specs across four commits, two audits withdrawn in full, a stale integrity manifest, a hostile-projection instrument that could not fail, a PA-0 artifact that did not reproduce its own experiment, reading $? after a pipe (which hid a failing verifier three times), and a wrong overwrite attribution later withdrawn. One mechanism runs through most of them: an instrument without execution proof silently converts UNKNOWN into PASS.
- **write_policy**: ZERO_WRITES

_Relates to: `pr.kernel.66`, `pr.kernel.66.latest_finding`, `pr.kernel.66.dissent`, `discrepancy.pr66_body_stale`_

## pr disposition (1)

### `pr66.disposition_dossier` — PR #66 disposition — FREEZE AS TRACK B RESEARCH

**Evidence:** `derived`
- _no evidence reference — this node is explicitly unresolved_

- **disposition**: FREEZE_AS_TRACK_B_RESEARCH
- **what_it_proves**: That pre-arrival control, sender-owned ingress, causal need closure and author-direction classification can be built and adversarially verified; and — more valuable — that five plausible designs for decoupling canonical from legacy repair are wrong, each falsified by measurement rather than by argument.
- **what_it_does_not_prove**: Anything about the comparison it exists to settle. Its own body says so: the work establishes correctness prerequisites and measurement integrity, not evidence that the morphogenetic substrate beats a conventional durable workflow engine. Only R8 decides that, and R8 is prohibited until a freeze that has receded repeatedly.
- **mechanisms_to_promote_to_capability_candidates**:
  - pre-arrival control (bounded pending-control mechanism with fail-closed authentication)
  - causal need closure (NC-3 obligation-generation predicate)
  - the instrument-liveness discipline itself — arguably the most transferable output
- **tests_to_promote_to_protected_evaluators**:
  - the 24 strict xfail specifications as a regression corpus
  - adopted_edge_return_negative_control.py
  - prearrival_adversarial_twin.py
- **artifacts_historical_only**:
  - the five falsified design comparisons (retain as counterfactual evidence)
  - two withdrawn audits (retain — a withdrawn audit is evidence about auditing)
- **needs_bounded_completion_milestone**: no
- **milestone_rationale**: A bounded milestone was considered and rejected. The natural candidate is "land the DUAL_REPAIR_SEARCHES detector reordering with its negative control", which is small and correct. But it does not change the branch's standing, does not move Gate F or G, and reopens a runtime workstream this round has just decided to freeze. Record it as the first task if the branch is ever resumed, not as a reason to keep it warm.
- **evidence_that_would_justify_resuming**: A measured result showing the morphogenetic substrate beating the conventional baseline on an equivalent task, or a decision to run R8.
- **evidence_that_would_kill_the_mechanism_as_default**: A sixth falsified design in the B/C/D/F family, which would make it likely that the underlying lifecycle model — not the individual designs — is wrong.
- **preservation**: Nothing deleted. Branch retained, PR left open and draft, all 133 commits and 240 files preserved with lineage. Freezing is a routing decision, not a removal.

_Relates to: `pr66.state_capsule`, `pr.kernel.66.dissent`, `route.01_pr66_first`, `decision.final`_

## pr proposed sync (1)

### `pr66.proposed_sync` — PR #66 proposed body refresh and disposition comment — INERT, NOT POSTED

**Evidence:** `derived`
- _no evidence reference — this node is explicitly unresolved_

- **status**: NOT_APPLIED
- **application_requires**: explicit founder action
- **historical_body_preserved**: the existing PR #66 body is preserved verbatim in GitHub history; this proposes an addition, not a replacement of the record
- **proposed_body_delta**: Update the head reference from 15623a9 to a6f14d3. Add an RA-2 section recording that Design A was implemented, measured (904 passed / 21 failed, 0 strict XPASS) and reverted, that A/E/H are eliminated and B/C/D/F survive, and that the corrected finding is that canonical and legacy repair share load-bearing state rather than that a disabled subsystem retains authority. Replace the "next active bottleneck" section, which its own tip supersedes.
- **proposed_comment**: A whole-system planning round (issue #69, draft PR #68) has classified this branch as FREEZE_AS_TRACK_B_RESEARCH. Nothing here is merged, deleted or modified. The reasoning: this branch's own recorded dissent — that the conventional durable workflow engine still wins on available evidence — is the reason it must not gate Track A, and its five falsified designs are preserved as institutional evidence rather than treated as failure. Its pre-arrival control, causal need closure and instrument-liveness discipline are promoted to capability candidates. Resume conditions and kill conditions are recorded in the disposition dossier.
- **head_change_detection**: If origin/claude/uniimente-repo-audit-jpytcy moves beyond a6f14d3, this capsule and disposition are marked STALE and only the conclusions the new evidence invalidates are recomputed. The round must not finish an analysis of a6f14d3 after another writer has moved the branch.

_Relates to: `pr66.state_capsule`, `pr66.disposition_dossier`, `round.pr66_zero_writes`_
