# PumpStation Venture Cell Registration Proposal

## Status

**PROPOSED · INACTIVE · ZERO BUDGET · AUTONOMY LEVEL 0**

This document does not register or activate PumpStation. It defines the evidence and approvals required before the UNIIMENTE Kernel may recognize PumpStation as a bounded Venture Cell.

## Proposed identity

`spiffe://uniimente.internal/venture/pumpstation`

The identity is not present in `identity/service-identities.yaml` on this branch. Runtime recognition therefore remains false.

## Proposed role

PumpStation may eventually:

- submit productive-asset opportunities;
- preserve structured deliberation and dissent;
- compile simulation-only decisions;
- compile proposals for Kernel evaluation.

PumpStation may not:

- issue grants;
- select its own legal principal;
- increase its budget;
- alter policy;
- move money or assets;
- hold custody;
- accept outside capital;
- publish asset promotion;
- sign contracts;
- execute an external effect;
- activate itself.

## Legal principal

The registration candidate names `alfonso_lopez` for sandbox proposal authorship only.

`UNIIMENTE` is not and may not become the legal principal.

## Required approvals

Activation requires all of the following as separate evidence-bearing acts:

1. founder approval of the exact PumpStation manifest;
2. service identity registration in the canonical registry;
3. legal-principal confirmation;
4. approval of the exact pinned Kernel contract set;
5. security review;
6. issuance of a narrow, short-lived Kernel capability grant.

A later external consequence would additionally require policy approval, budget, evidence, commit-time revalidation, an injected executor, receipt, postcondition verification, reconciliation, and outcome recording.

## Source binding

The current proposal points to:

- repository: `dababiyoda/PumpStation`;
- branch: `agent/phase3-kernel-contract-adapter`;
- manifest: `kernel/pumpstation-organ-manifest.json`.

Its manifest hash remains `TO_BE_BOUND_AT_APPROVAL`. This prevents a proposal artifact from masquerading as a ratified registration.

## Rollback

Close this draft PR or delete the proposal files. The canonical identity registry and all grants remain unchanged.
