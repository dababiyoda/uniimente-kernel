# ADR: Adopt the GREG Polyintelligence Cortex seed as a SANDBOXED, unpromoted experiment

- Decision ID: polyintelligence-cortex-20260930
- Status: proposed
- Date: 2026-10-01
- Decision owner: Alfonso Lopez
- Deliberation level: Constitutional (adds five names to the shared Kernel contract registry; creates no authority)
- Founder intent references: PC-001 to PC-012 in
  [`docs/collaboration/intents-polyintelligence-cortex-20260930.json`](../collaboration/intents-polyintelligence-cortex-20260930.json);
  [`INTENT-20260930-polyintelligence-cortex`](../intent/INTENT-20260930-polyintelligence-cortex.json); INTENT-0030
- Machine-readable deliberation:
  [`deliberation-polyintelligence-cortex-20260930.json`](../collaboration/deliberation-polyintelligence-cortex-20260930.json)
  (passes the protocol's `validate_deliberation.py`)
- Supersedes: none
- Superseded by: none

## Problem

- **Observation:** `main` (19fa33c) has no cognition routing; the Capability Genome, policy engine, causal memory and
  Consequence Gate exist; no capability or model router is implemented (Final Build Order §4.14 lists one as unbuilt).
- **Observation:** the founder's build prompt ordered a seed experiment; it is built on a draft branch as cortex 0.1.5.
- **Inference:** single-model answers on mixed geometries lack jurisdiction, typed proof and gates; whether routing
  beats a strong single model is unknown.
- **Unresolved claim:** routing gain. The declared baselines have not run.
- **Proposed action:** merge as a SANDBOXED, consequence-inert experiment after founder review; promote only on
  `GAIN_VERIFIED`.

## Baseline and evidence

| Claim | Claim class | Evidence tier | Source and location | Finding | Limitation |
| --- | --- | --- | --- | --- | --- |
| Routed seed quality | observation | deterministic fixture | `tests/evidence/cortex-seed-v0.1.4/heldout-results.json` | 0.964 [0.911, 1.000]; 0 critical errors | self-authored, structured items |
| Routing gain | unresolved claim | deterministic fixture | same file, `exit` | `INCONCLUSIVE` | baselines `NOT_RUN` (no reachable model) |
| No authority created | implementation | unit test | `tests/unit/test_cortex_pipeline.py` | schema pins `authority_created: false`; no actuator import | — |
| Safeguards load-bearing | implementation | unit test | `scripts/ci/check_cortex_mutants.py` | 26/26 mutants caught | mutants are hand-chosen |
| Stacks on PR #137 | observation | sandbox execution | report § Stacking on PR #137 | clean merge at the final head; 1556 vs 1201 passed, same 12 skips | isolated venv; PR #137 may move |
| Best Single is hard to beat | external evidence | primary source | LLMRouterBench (arXiv 2601.07206) | several routers fail to beat it | different task mix |

## Alternatives

- **Current baseline:** no cortex on `main`.
- **Do nothing:** branch stays a draft. Zero change to `main`; primitives drift; the directive stays off `main`.
- **Simplest viable alternative:** gate-and-receipt layer around one model, without exact organs. Kept as the fallback.
- **Strongest competing architecture:** a strong single model with tools. It is the declared baseline to beat.
- **Reversible experiment:** merge SANDBOXED and consequence-inert; revert is one merge revert.

Rejected: the full 16-family cortex now (revive on `GAIN_VERIFIED` plus recorded deficits); promotion on the 0.964
result (revive on `GAIN_VERIFIED` on an external suite against strong baselines).

## Five-role review

| Role | Position | Material concerns | Evidence | Recommendation |
| --- | --- | --- | --- | --- |
| Founder-Intent Steward | every prompt line and review section is traced; literal dominance clause preserved and prohibited | 'verbatim' vs the review's own corrections needs a founder ruling | traceability matrix; register | EXPERIMENT |
| Systems Architect | projection of the Capability Genome; one integration edit; stacks on #137 | shared registry names; structural routing only | `capabilities/genome.py`; stack run | EXPERIMENT |
| Adversarial Reviewer | nothing shows the router beats a strong model with tools | self-authored suite; weak local baseline; four post-freeze fixes | dossier; results | EXPERIMENT (dissent recorded) |
| Operator and Maintainer | reproducible; one optional dependency; CI job 6 | documentation volume; stale mutant patterns | CI workflow; mutation script | EXPERIMENT |
| Evidence and Welfare Guardian | protection human-led, identity-free receipts, unknown harm treated as possible harm | no held-out protection item; recipient of handoffs undefined | pipeline tests; protection receipt | EXPERIMENT |

## Pass 1

- **Intended outcome:** a reversible, consequence-inert cognition seed on `main`, promoted only by evidence.
- **Advantages:** exact organs remove error classes models cannot (amplified: certified optimization and witness
  checks become auditable receipts); authority-free receipts with falsifiers narrow disputes (amplified:
  accountability compounds with use); outcome-only settlement fenced from authority (amplified: competence compounds
  without sovereignty).
- **Disadvantages and redesigns:** DIS-1 no comparative evidence → strict per-geometry exit, promotion blocked;
  DIS-2 self-authored suite → external free-text suite before shadow use; DIS-3 shared registry names → schemas kept
  out of the shared-boundary allowlist, founder decision to merge; DIS-4 documentation surface → matrix and register
  are tested.
- **Comparisons:** see Alternatives.

## Pass 2

- **Attack summary:** evaluator capture, bureaucracy, centralization in one router, drift between frozen evidence and
  code.
- **New weaknesses:** NW-1 every fix needs bump/freeze/rerun (kept: that friction exposes post-hoc changes); NW-2 exit
  rule tuned after results (tightened only before any baseline ran, only by adding conditions, all versions kept);
  NW-3 router as de facto authority (schema pin, import test, learning fenced from the registry).
- **Dispositions:** DIS-1 experiment; DIS-2 deferred to Node 2; DIS-3 accepted; DIS-4 resolved.
- **Final design:** cortex 0.1.5 as on the branch; merge only by founder decision; no promotion without
  `GAIN_VERIFIED`.
- **Residual risks:** routing gain never materializes (kill test, gate-and-receipt fallback); protective handoff has
  no named recipient (founder designates).
- **Recommendation:** `NEEDS_FOUNDER_DECISION`.

## Dissent

Adversarial Reviewer: do not treat the seed as evidence of routing value until strong baselines run. Threshold:
`GAIN_VERIFIED` against a strong always-LLM and a committee on the frozen suite, then on an external suite. Owner:
Alfonso. Review trigger: Node 1 verdict.

## Authority impact

- Changes authority: no.
- Authorized-human approval required: yes (constitutional level: shared contract registry).
- Approval state: pending. Chat text does not authenticate the founder (Founder Intent Ledger SR-INTENT-3), so this
  record does not mark approval.
- Approver: none yet.

## Decision

`NEEDS_FOUNDER_DECISION` — the five roles recommend `EXPERIMENT` (merge SANDBOXED, unpromoted); the merge itself is
Alfonso's decision.

## Migration, rollback, and kill criteria

- **Migration:** merge the draft branch; no data migration; earlier freeze manifests and results kept.
- **Rollback:** revert the merge commit (removes the cortex, its five registry names and CI job 6 together).
- **Kill criteria:** `GAIN_ABSENT` against strong baselines on two frozen versions with no critical-error advantage;
  any receipt asserting authority or any actuator import.
- **Material items intentionally unchanged:** the Consequence Gate, policy engine, grants, causal memory, the shared
  contract-validation allowlist, every GREG/VEPMC path on PR #137.
- **Review trigger:** founder review of the draft PR, or a Node 1 verdict.
