# Phase-3 Organization Compiler ADR

Status: **EXPERIMENT / PROPOSAL ONLY**  
Decision: `DECISION-OM-ZERO-TRUST-COMPILER-2026-09-04`  
Stack base: draft PR #90  
Runtime/external effects: **NONE**

## Decision

Add one pure deterministic compiler under OMNIMORPH. It validates an existing
`MissionContract`, content-binds the mission and its `ProblemGeometry`, emits
materially different candidate `OrchestrationGenome` documents, and records one
transparent `TopologyDecision`. It does not instantiate its recommendation.

The compiler produces only these Phase-3 candidates when the mission permits
them:

1. static durable workflow;
2. centralized bounded coordination;
3. hierarchical bounded coordination;
4. hybrid coordination/execution/evaluation;
5. do not instantiate.

Decentralized and developmental/local forms remain named but evidence-gated.
The current WMI fixed roster remains a protected external competitor for the
later experiment rather than being rewritten as a synthetic genome here.

## Narrow canonical seam

| Power or semantic | Owner | Compiler relationship |
|---|---|---|
| Mission authority | Existing legal-principal/governance mechanisms | Reads immutable existing refs; cannot issue or change them |
| Organization design | `omnimorph/organization_compiler.py` | Owns only deterministic hypotheses and score traces |
| Organization execution | Existing Event Spine plus unresolved runtime owner | No import, call, event, worker or activation |
| Independent evaluation | Existing assessment/governance seams | Requires a distinct evaluator; does not impersonate it |
| Consequence authority | Existing Consequence Gate/legal principal | No import or effect path |
| Shared design semantics | `contracts/` | Compatible genome v1.1 profile plus fail-closed decision schema |
| Identity and authorization | Existing `identity/` and `authority/` | Emits obligations/policy refs; never credentials or grants |
| Evidence and integrity | Existing `provenance/` and Event Spine | Uses content digests; creates no second ledger |

No component in this slice owns all five powers.

## Deterministic policy

Inputs are schema-validated and copied before use. Policy, mission, geometry,
profile, genomes and decision are identified by SHA-256 over RFC 8785 canonical
JSON. Only a self-referential top-level `digest` field may be excluded. A digest
is content identity—not correctness, truth, authorization, execution proof, or
outcome evidence.

Scores use integer basis points. Each candidate exposes its signals, weights,
contributions, complexity penalty, coordination penalty, design-security-gap
penalty and final score. The weights are a preregistered hypothesis for
`OM-EXP-001`; they are not learned knowledge. Static wins exact ties.

Critical risk, any non-`none` external-effect policy, or an external-contact,
financial or irreversible consequence ceiling forces a design recommendation
of `do_not_instantiate` while enforcement remains design-only.

Every recommendation has:

- `automatic_instantiation=false`;
- `execution_admission=REFUSED_PENDING_SEPARATE_PHASE_DECISION`;
- `authority_delta=0`;
- `external_effects=0`;
- no executed episode references;
- an explicit `HYPOTHESIS_ONLY` status.

## Recombined zero-trust substrate

The profile applies the frozen M11–M17 mechanisms without importing a chain or
new control plane:

- canonical content binding instead of blocks;
- append-only receipts and existing Merkle checkpoints instead of a token or
  public consensus network;
- identity + attenuated capability + freshness + policy at each protected
  transition instead of implicit trust;
- one-task workload identity and replacement re-verification;
- producer / independent verifier / relying-authority separation;
- thresholded, versioned improvement proposals instead of live self-rewrite;
- static workflow or refusal when verification/security state is uncertain.

The genome marks the profile `DESIGN_ONLY`. Production key custody, distributed
revocation, actual network enforcement, hardware attestation and an independent
external anti-equivocation witness are not implemented.

## Strongest counterexample

The static `DurableWorkflow` remains the strongest supported architecture: it
has explicit state, targeted retries, low message amplification and simpler
supervision. It is mandatory, the default fallback and the exact-tie winner.
Phase 3 does not assert that any dynamic form beats it.

## Dependencies and supply-chain boundary

`rfc8785==0.1.4` is pinned for exact JSON Canonicalization Scheme behavior. It
is a small, dependency-free implementation, but its beta classification and
maintainer concentration are retained as risk. Loss, advisory, incompatible
test vector or ownership change triggers review. Canonicalization failure is a
refusal; the package is never an authorization dependency.

Primary references:

- [NIST SP 800-207](https://csrc.nist.gov/pubs/sp/800/207/final)
- [RFC 8785 JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785)
- [RFC 9334 RATS Architecture](https://www.rfc-editor.org/rfc/rfc9334)
- [RFC 9943 SCITT Architecture](https://www.rfc-editor.org/rfc/rfc9943.html)
- [SPIFFE specifications](https://spiffe.io/docs/latest/spiffe-specs/)
- [in-toto specification](https://in-toto.io/docs/)

## Entry, exit, rollback and kill gates

Entry was a frozen Phase-3 inspection ledger, ownership record, founder intent,
five-role review and exactly two strengthening passes. Exit is schema-valid,
deterministic candidate generation with negative controls and canonical CI.

Rollback is to close or revert the stacked Phase-3 draft while retaining its
inspection, deliberation, dissent and failed evidence. PR #90 and the static
workflow remain unchanged.

Kill Phase 3 if it emits an event, calls a runtime/model/network/Gate, creates a
second authority/identity/ledger system, changes mission authority/resources,
omits static or do-not-instantiate, treats a digest/identity/score as authority,
admits an evidence-gated form, or claims LIVE, PROVEN, HARDENED, rogue-proof,
autonomous regeneration or morphogenetic superiority.

## Next gate

Phase 4 is not authorized by this ADR. It requires a separately linked decision,
resolved canonical runtime ownership, sealed development/held-out/negative
corpora, an independent reviewer, identical competitor envelopes and preserved
failure/loser episodes.
