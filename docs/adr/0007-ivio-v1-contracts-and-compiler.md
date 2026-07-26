# ADR-0007: IVIO v1 contracts and deterministic Reality Compiler boundary

Date: 2026-07-22
Status: proposed for founder review

## Context

The kernel already has generic events, evidence, outcomes, capability grants, durable workflows, a Consequence Gate, a Commit Witness, and causal memory. The current blueprints require an executable IVIO proof-to-settlement rail, but the repository has no canonical Case, OutcomeEvent, CompiledInstruction, OutcomeCredential, SettlementIntent, ReconciliationRecord, exception, invalidation, payable-ready, or metrics contract.

Without one shared wire language, CHARIO, TGH-CONTROL-RAIL, WealthMachineIntelligence, and DALEOBANKS will encode similar concepts differently. That creates drift precisely at the identity, proof, and settlement boundary.

## Decision

Create contracts/ivio/v1/schema.json as the only normative IVIO v1 schema source and manifest.json as its object map. Add reality/ivio.py as the deterministic reference compiler and integrity implementation.

The compiler:

- accepts a complete, strict intent;
- refuses to infer absent authority or semantics;
- uses integer minor units and forbids floats;
- produces deterministic timestamps from the request artifact, not wall-clock state;
- binds parameters, policy, Constitution, evidence requirements, approvals, budget, TTL, data rights, expected effect, receipt, reconciliation, reversibility, compensation, settlement path, kill conditions, and reality status;
- emits a content digest under UNIIMENTE-C14N-v1; and
- stops before policy approval, capability issuance, execution, receipt, credential, payable-ready, or settlement.

IVIO v1 uses a W3C VC 2.0-shaped outcome credential, a CloudEvents-compatible outcome event, and JSON Schema Draft 2020-12. These alignments provide portability without delegating truth or authority to a standard.

## Why a single schema file

A single document with named definitions eliminates circular references, gives each consumer one immutable compatibility target, and makes whole-package validation cheap. Language bindings can be generated later from the same source. Splitting definitions into separately edited mirrors is prohibited.

## Why a named canonicalization profile

RFC 8785 establishes the value of invariant JSON for hashing. A complete cross-language JCS implementation would add unnecessary surface to the first milestone. UNIIMENTE-C14N-v1 therefore narrows the domain to printable-ASCII keys, safe integers, no floats, sorted keys, compact UTF-8, and exact Unicode preservation. It is not labeled JCS-compatible. A future replacement requires a contract major version or an explicitly dual-hashed migration.

## Alternatives rejected

- Generic agent platform first: increases surface without moving the external-proof bottleneck.
- Foundry first: packages unproven capabilities before one rail works.
- Blockchain or autonomous wallet: adds cost and governance risk without solving external proof acceptance.
- Mutable database rows as truth: weak replay, diff, and tamper evidence.
- Provider webhook as finality: duplicates, retries, reversals, and forged callbacks require independent reconciliation.
- Duplicated TypeScript and Python hand-written models: guarantees schema drift.
- Direct write to main: removes founder review at the constitutional boundary.

## Consequences

Positive:

- every organ receives one wire contract;
- stale approvals can bind to exact bytes;
- replay and mutation tests become deterministic;
- money never depends on floating-point values;
- exceptions, rejections, and invalidations remain visible;
- the next CHARIO and TGH work can target an explicit contract.

Costs and residual risks:

- UNIIMENTE-C14N-v1 needs parity vectors before non-Python consumers claim compatibility;
- JSON Schema validates shape, not all temporal, authorization, or business invariants;
- VC shape does not prove a ride happened or that a payer accepts it;
- the first live pilot still requires a named verifier, acceptance criteria, legal/privacy review, and a supervised rollback path.

## Rollback

This change has no live side effects. Rollback removes the IVIO v1 package, compiler module, tests, and workflow. No existing generic contract is modified. Once another repository consumes ivio.v1, rollback requires a coordinated versioned migration rather than deletion.
