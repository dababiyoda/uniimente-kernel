# Zero-Trust Developmental Substrate

## Decision boundary

The substrate is a set of design constraints compiled into every candidate
organization. It is not a blockchain deployment, cryptocurrency, DAO,
consensus authority, separate policy engine, new event ledger, new identity
issuer, or promise that an agent cannot misbehave.

The security objective is narrower and testable: reduce implicit trust and
blast radius; make organizational content, identity, authority, freshness,
resource use, evidence, dissent, improvement, and consequence boundaries
inspectable; refuse closed when a required verifier is unavailable.

## Recombined security cell

| Imported primitive | Material mutation | Existing owner | Compiled obligation |
|---|---|---|---|
| Block/content hash | Bind mission, geometry, policy, genome and decision; no chain consensus | `provenance/`, contracts | RFC-8785 SHA-256 digest, independently recomputable |
| Append-only transparency log | Use the existing Event Spine; register claims/receipts, not truth | `events/`, `provenance/` | no second ledger; checkpoint/inclusion proof where implemented |
| Zero-trust policy enforcement | Verify every organizational transition, not only a network session | `identity/`, `authority/`, policy | default deny; identity + attenuated grant + freshness + policy version |
| Short-lived workload identity | Bind identity to one task lease and re-derive replacement eligibility | `identity/`, Phase-2 contracts | identity is never authority; expiry/revocation required |
| Remote attestation roles | Worker produces evidence, evaluator appraises, acceptance authority relies | assessment/governance seams | producer cannot self-verify; attestation cannot authorize |
| Multisig/threshold layout | Distinct evidence roles admit only a versioned experiment proposal | collaboration/governance | no token voting or automatic protocol upgrade |
| Finality/settlement | Verified closure only after reconciliation and receipt | `closure/`, Gate | uncertain effects block retry and closure |

## Five-power security geometry

1. Mission authority supplies a bounded immutable contract and existing grants.
2. Organization design emits content-bound hypotheses only.
3. Organization execution, when later admitted, uses the one canonical durable
   substrate and one-task leases.
4. Independent evaluation appraises evidence and preserves dissent; it neither
   executes nor grants consequence authority.
5. Consequence authority remains the accountable legal principal plus the
   existing Gate.

No component owns all five. Identity, content integrity, score, quorum,
attestation, or topology rank can never substitute for authority.

## Recursive improvement without self-expansion

An improvement is a new content-bound proposal, never a live mutation. It must
name the current and proposed genomes, deficit, evidence, affected state,
resource impact, authority invariants, rollback and kill conditions. During the
developmental stage it moves only through simulation, sandbox, shadow and a
separately authorized canary. Correlated models do not form an independent
quorum. A verifier's absence produces UNKNOWN/refusal, not PASS.

The compounding asset is verified history: enough real episodes may improve
topology selection, pool sizing, routing, provider assignment, retry versus
replacement, evaluator placement, resource allocation and reconfiguration
timing. No loop expands authority automatically.

## Security reality ledger

| Claim | Current evidence |
|---|---|
| Deterministic content binding | Phase-3 unit target; not yet CI-tested |
| Append-only internal transition truth | Existing Event Spine tests |
| Merkle inclusion/checkpoint mechanism | Existing provenance unit tests |
| Workload PKI and in-process mutual TLS | Existing stacked-line unit tests |
| Production key custody | UNAVAILABLE |
| Distributed revocation propagation | UNAVAILABLE |
| Hardware workload attestation | NOT IMPLEMENTED |
| Independent external anti-equivocation witness | NOT IMPLEMENTED |
| Runtime enforcement of the compiled profile | NOT IMPLEMENTED |
| Prevention of all rogue/harmful behavior | IMPOSSIBLE CLAIM; PROHIBITED |

## Fail-closed degradation

- Invalid mission/schema/digest: refuse compilation.
- Missing static or do-not-instantiate option: refuse compilation.
- Unknown identity, stale freshness, revoked credential, excessive grant,
  unavailable policy or missing proof: refuse execution admission.
- Missing independent evaluator: do not verify or close.
- Uncertain external effect: reconcile before retry or closure.
- Critical risk while controls remain design-only: recommend
  do-not-instantiate.
- Tie or marginal dynamic benefit: static DurableWorkflow wins.

This document defines an experimental design substrate. It does not establish
LIVE, PROVEN, HARDENED, autonomous-regeneration, external-security, or
morphogenetic-superiority status.
