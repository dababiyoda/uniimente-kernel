# OMNIMORPH

OMNIMORPH is UNIIMENTE's bounded institutional morphogenesis layer. It resolves registered Capability Genomes and composes them into temporary Organ Manifests without granting itself authority or executing external effects.

## Existing mechanism

The implementation uses standard dependency resolution, typed manifests, content hashing, capability-envelope checks, append-only event reconstruction, deterministic simulation reports, and explicit human ratification records. It claims no novel science.

## Defined interface

Primary interfaces are:

- `OmnimorphEngine.compose()`
- `OmnimorphEngine.simulate()`
- `OmnimorphEngine.propose_activation()`
- `OmnimorphEngine.record_gate_activation()`
- `OmnimorphEngine.get_manifest()`
- `OmnimorphEngine.get_simulation()`
- `OmnimorphEngine.validate_paid_outcome()`

## Bounded authority

OMNIMORPH may compose, simulate, and propose. It cannot create a Capability Genome, expand an authority envelope, ratify itself, mint a Gate receipt, execute an adapter, move money, or redefine institutional ends. An activation remains `PROPOSED_NOT_EXECUTED` until a canonical Consequence Gate receipt is supplied.

## Available dependencies

Runtime code uses the Python standard library plus the existing Capability Genome, Foundry contract, and Evidence Ledger modules. It does not require a framework or model provider.

## Security model

Each capability must already exist in the canonical `GenomeRegistry`. Requested consequence class and budget must fit inside the registered envelope. Aggregate organ budget is capped. Manifests are content-addressed, state namespaces are isolated, self-ratification is refused, and Gate activation must bind to the exact registered manifest.

## Failure modes

The module fails closed on missing capabilities, unknown versions, incompatible consequence classes, excessive capability or aggregate budgets, changed manifests, absent simulations, failed simulations, mismatched ratification, system self-ratification, missing signatures, and malformed Gate receipt hashes.

## Acceptance tests

Unit coverage includes composition, simulation, capability-envelope refusal, aggregate-budget refusal, self-ratification refusal, changed-manifest refusal, Gate receipt requirements, full manifest and simulation reconstruction, and reuse of one capability substrate across distinct isolated organs. The complete registry executes five closure checks for this module.

## Recovery path

Organ Manifests, simulation reports, activation proposals, ratification metadata, and Gate activation receipts are recorded on the Evidence Ledger. Restart reconstructs the complete body plan and activation state without human restatement.

## Resource ceiling

Every bound capability has a budget ceiling and consequence class. OMNIMORPH separately enforces an aggregate organ budget. An organ has an explicit expiration, kill conditions, and isolated state namespace.

## Operating cost

Composition is linear in the number of capability needs. Registry lookup is constant-time per capability. Ledger recovery is linear in the relevant institutional event history.

## Legal operator

The Organ Manifest inherits an accountable legal operator from the Advantage Architecture. `UNIIMENTE` cannot be the legal operator and OMNIMORPH cannot ratify its own output.

## Handoff

The handoff state is the content-addressed Organ Manifest, exact capability versions, simulation report, ratification record, and Gate receipt reference. Operational execution remains outside OMNIMORPH.

## Replaceable

Capability implementations, model providers, adapters, storage, and runtime hosts are replaceable behind the manifest and Genome interfaces. The manifest hash, evidence history, authority envelope, and rollback boundary survive replacement.
