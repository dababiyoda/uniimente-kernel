# ADR: Linker-proven generic contract delivery on the existing EventSpine

- Decision ID: TRACK-A-P3-ROUTE-B-2026-08-08
- Status: accepted as a draft-branch experiment
- Date: 2026-08-08
- Decision owner: alfonso_lopez
- Deliberation level: Constitutional
- Founder intent references: FI-TRACK-A-001, FI-TRACK-A-002, FI-TRACK-A-003
- Supersedes: none
- Superseded by: none

## Problem

Observation: the kernel linker proves typed producer-contract-consumer edges, while the EventSpine routes event-type prefixes. On the inspected baseline, no production subscriber or canonical mapping connected those namespaces.

Observation: the legitimate consumer for `wire-opportunity-packet` lives in WealthMachineIntelligence, not in the kernel. DALEOBANKS also contains a credential-free local mock that can return a valid-looking assessment without calling WealthMachineIntelligence.

Inference: a P3 counterfactual is valid only if the linker edge controls delivery to the real pinned consumer and the local mock is explicitly rejected.

Unresolved claim: the in-process seam has not proven service deployment, trusted production artifact identity, external verifier acceptance, settlement, or a developmental closure.

Proposed action: run a reversible, consequence-inert draft-branch experiment using one generic typed delivery event on the existing EventSpine.

## Baseline and evidence

| Claim | Claim class | Evidence tier | Source and location | Finding | Limitation |
| --- | --- | --- | --- | --- | --- |
| No contract-to-event binding existed | observed | primary source | `runtime/P3_INSPECTION.md` at the pre-P3 branch head | Linker topology had no runtime subscriber | Repository inspection only |
| Real producer and consumer execute at manifest pins | observed | sandbox execution | Route B probe using DALEOBANKS `829c5f2` and WMI `6549984` | Packet becomes a human-gated assessment | One process, network denied |
| Missing edge removes the function | causal counterfactual | sandbox execution | Probe state B | Binding is refused and no assessment exists | Internal computation only |
| DALEOBANKS mock is a bypass threat | adversarial counterfactual | sandbox execution | Probe state C | Lookalike exists, but handler provenance rejects it | Handler reference is not production artifact attestation |
| Reality Compiler is a useful direction | design synthesis | model output | Supplied PDFs 02 and 03 | External verifier is the decisive bottleneck | Not independent outcome evidence |

## Alternatives

- Current baseline: retain a graph that no real runtime function consumes.
- Do nothing: keep P3 partial and preserve zero new runtime surface.
- Simplest viable alternative: directly call the WMI method, which is smaller but bypasses topology and canonical event evidence.
- Strongest competing architecture: define a separate event type for every contract, which is readable but currently lacks an authorized mapping.
- Reversible experiment: add one generic router, one four-state probe, one integration wrapper, and one post-suite exact-pin CI step.

Rejected alternatives and revival evidence are preserved in `runtime/P3_ROUTE_B_DELIBERATION.json`. A per-contract event can revive only when a canonical schema declares its event identifier. A direct call can revive only for organ-local behavior. A fixture consumer remains ineligible for closure evidence.

## Five-role review

| Role | Position | Material concerns | Evidence | Recommendation |
| --- | --- | --- | --- | --- |
| Founder-Intent Steward | Preserve human sovereignty and the real proof-to-settlement direction | No closure inflation | Doctrine and intent ledger | EXPERIMENT |
| Systems Architect | Reuse the linker and EventSpine | No second bus or naming convention | Linker, spine, inspection | EXPERIMENT |
| Adversarial Reviewer | Attack mock substitution and revision spoofing | Valid-looking bypass | State C and git HEAD checks | EXPERIMENT |
| Operator and Maintainer | Isolate sibling checkouts after ordinary tests | CI pollution and drift | Canonical CI design | EXPERIMENT |
| Evidence and Welfare Guardian | Restrict the claim to sandbox routing geometry | No external verifier or welfare result | Frozen runtime contract | EXPERIMENT |

## Pass 1

- Intended outcome: make one real internal function depend on the exact edge already proven by the kernel.
- Advantages and amplified value: topology becomes behaviorally decisive; existing canonical primitives remain canonical; request and result become causally traceable.
- Disadvantages, IDs, and redesigns: D1 cross-repository dependency stays probe-local and pinned; D2 mock substitution is rejected by stable handler reference; D3 machine-specific schema paths become a relative locator plus digest; D4 closure inflation is prohibited by explicit zero-effect and zero-delta assertions.
- Baseline comparison: the baseline proves structure but controls no real function.
- Do-nothing comparison: simpler, but leaves the selected deficit unresolved.
- Simplest alternative comparison: a direct call does not prove institutional routing.
- Strongest architecture comparison: contract-specific events require semantics not present in the contracts.
- Reversible experiment: draft PR only, no merge, deploy, publication, money, credential, or external effect.
- Rejected alternatives and revival evidence: recorded in the machine-readable deliberation.

## Pass 2

- Attack summary: source-label spoofing, mock substitution, absolute-path receipts, sibling test collection, sensitive payload retention, and claim inflation were attacked.
- New weaknesses created by Pass 1: the binder still accepts a revision string rather than a trusted runtime artifact; full wire bodies may require future field-level retention controls.
- Disposition of every Pass-1 disadvantage ID: D1 experiment, D2 resolved, D3 resolved, D4 prohibited.
- Final strengthened design: `ContractEventRouter` accepts only an `INERT` consequence classification, one exact `LinkReport` edge, a stable real handler reference, both source revisions, and the linked schema digest; the probe verifies both checkout HEADs and executes four counterfactual states with network denied.
- Residual risks: no production artifact attestation, no transport proof, no external verifier acceptance, and no remote full-suite result until Canonical CI completes.
- Recommendation: EXPERIMENT.

## Dissent

The Evidence and Welfare Guardian dissents from any description of P3 as a developmental closure, deployment, commercial result, or proof-to-settlement outcome. The dissent remains binding until an independently verified episode satisfies all twelve frozen closure conditions. Owner: alfonso_lopez. Review trigger: any attempt to increment `VERIFIED_DEVELOPMENTAL_CLOSURES` or widen the P3 claim.

## Authority impact

- Changes authority: no
- Authorized-human approval required: yes, because this is cross-repository architecture
- Approval state: approved for this consequence-inert draft-branch experiment
- Approver: alfonso_lopez
- Consequence-gate compatibility: the router grants no capability, stages no outbox item, and cannot flush an external effect

## Canonical ownership

| Concern | Canonical owner | P3 effect |
| --- | --- | --- |
| Contract topology | Kernel `InstitutionalLinker` | Consumed, not reimplemented |
| Event evidence | Kernel `EventSpine` | Reused, not replaced |
| Route materialization | Kernel `ContractEventRouter` | New narrow seam |
| Opportunity production | DALEOBANKS | Real pinned producer |
| Opportunity evaluation | WealthMachineIntelligence | Real pinned consumer |
| Human authority | Kernel constitution and consequence gate | Unchanged |
| Closure judgment | Frozen Track-A evaluator contract | Unchanged at 0 |

## Decision

`EXPERIMENT`

## Migration, rollback, and kill criteria

- Migration: land only on draft PR #70, run exact-pin local evidence, require the single Canonical CI workflow, and enter P4 only after green evidence.
- Rollback: revert the bounded P3 commit and restore the work packet to P3 partial.
- Kill criteria: missing edge still yields an attributed assessment; mock binds as WMI; pins mismatch; any network or external effect occurs; human approval becomes false; schema provenance loses digest or portability; closure count changes; or CI requires widening P3 scope.
- Material items intentionally unchanged: `runtime/contract.py`, main, PR #66, authority, identity, money, outbox, settlement, and deployment.
- Review trigger: CI result, manifest pin or decisive symbol change, or any promotion beyond the consequence-inert experiment.
