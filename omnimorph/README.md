# OMNIMORPH

## Purpose

Compose temporary institutional organs from a passed Advantage Architecture, a dependency-aware Composition Plan, and registered Capability Genomes. OMNIMORPH simulates the proposed organ, records separate human ratification, accepts an exact canonical Gate activation receipt, and supports evidence-backed retirement.

OMNIMORPH does not execute an organ, create a legal entity, mint credentials, move money, grant authority, or activate itself.

## Institutional Morphogenesis compiler — Phase 3

`OrganizationCompiler` extends OMNIMORPH's design role. Given a valid bounded
MissionContract, it deterministically emits materially different
OrchestrationGenome hypotheses and a transparent TopologyDecision. It preserves
the static DurableWorkflow and do-not-instantiate choices, lets static win exact
ties, defers evidence-gated forms and refuses all execution admission.

Each v1.1 genome contains one content-bound, `DESIGN_ONLY` zero-trust profile.
The profile recombines content-addressing, transparency receipts, per-transition
verification, fresh one-task workload capability, independent appraisal,
thresholded improvement proposals and static fallback. It references the
existing Event Spine, identity, authority, provenance and Gate owners. It does
not deploy a blockchain, token, second ledger, second identity system, second
policy engine or second consequence path.

The compiler imports no runtime, model, network, Event Spine, identity issuer,
authority engine, Gate, scheduler or worker executor. Its ranking is a
`HYPOTHESIS_ONLY` experiment input—not organizational knowledge, ratification or
proof that a topology works.

## Buildability contract

- **Existing mechanism:** Advantage Foundry, Spider-Web Tribunal, 55-technology Composition Plan, Capability Genome Registry, Evidence Ledger, human ratification, and canonical Consequence Gate receipts.
- **Defined interface:** `OmnimorphEngine.compose`, `simulate`, `propose_activation`, `record_gate_activation`, and `retire`.
- **Bounded authority:** the engine outputs `PROPOSED_NOT_EXECUTED`; only an external recorded `organ.activate` Gate receipt can change activation state, and no component may ratify itself.
- **Available dependencies:** registered Capability Genomes, passed tribunal report, valid Composition Plan identity, ISO-8601 expiration, legal operator, budget ceilings, kill conditions, and canonical hash references.
- **Security model:** deny by default; exact manifest binding; capability-envelope checks; aggregate budget limit; consequence ceiling; expiration; no system ratifiers; exact action class and principal on Gate receipt; no arbitrary hash substitution; explicit retirement.
- **Failure modes:** unknown or changed architecture, plan, tribunal report, capability, manifest, simulation, ratification, or receipt; partial/target technology; budget escape; expired approval; self-ratification; wrong principal; wrong action class; missing kill conditions; unreconciled retirement.
- **Acceptance tests:** registered capability and budget bounds; passed simulation; no execution authority; self-ratification refusal; approval expiry; exact receipt binding; changed manifest refusal; activation ordering; retirement with human approval and reconciliation.
- **Recovery path:** preserve the manifest and failure telemetry, suspend activation, detach selected technologies in reverse dependency order, restore verified snapshots, reconcile obligations, reconfigure through the Foundry, and issue a new immutable manifest.
- **Resource ceiling:** minimum of OMNIMORPH system ceiling, Composition Plan ceiling, and every bound Capability Genome envelope.
- **Operating cost:** simulation, isolated runtime, storage, observability, verification, rollback, reconciliation, and human review.
- **Legal operator:** a named human or lawful entity; never UNIIMENTE, OMNIMORPH, Foundry, or a child organ.
- **Handoff:** Organ Manifest hash, simulation report, human ratification record, Gate activation receipt, active-state record, retirement record, and reconciliation evidence.
- **Replaceable:** sandbox runtimes, simulation engines, isolation mechanisms, storage, and individual capability implementations may change behind the stable manifest and authority contracts.

## Phase-3 buildability boundary

- **Defined interface:** `OrganizationCompiler.compile` emits a design result;
  it never calls an existing `OmnimorphEngine` activation method.
- **Bounded authority:** every decision says
  `REFUSED_PENDING_SEPARATE_PHASE_DECISION`, `authority_delta=0`, and
  `automatic_instantiation=false`.
- **Integrity:** mission, geometry, policy, zero-trust profile, genomes and
  decision are RFC-8785/SHA-256 content-bound; a digest grants nothing.
- **Zero-trust posture:** design obligations reference canonical identity,
  authority, Event Spine, provenance and Gate owners. Runtime enforcement,
  production key custody, distributed revocation, hardware attestation and an
  external witness remain not implemented.
- **Recovery:** close or revert the stacked Phase-3 draft, preserve its evidence,
  and continue with Phase 2 and the static DurableWorkflow unchanged.
