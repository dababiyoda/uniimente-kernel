# Foundry

The Asymmetric Advantage Foundry converts a fully specified market failure into a bounded advantage architecture, preserves rejected strategic branches, coordinates paid validation, and seals reusable competence only after verified external economic consequence.

## Existing mechanism

The implementation uses standard typed records, deterministic scoring, state machines, HMAC-authenticated wire messages, append-only event reconstruction, WSGI, and immutable version identifiers. It claims no novel science.

## Defined interface

Primary interfaces are:

- `AdvantageFoundry.intake()`
- `AdvantageFoundry.complete_route_tournament()`
- `AdvantageFoundry.compile_architecture()`
- `AdvantageFoundry.seal_advantage_genome()`
- `CommercialClosureCompiler.open_case()/advance()/decide()`
- `FoundryPipeline.design()/propose_activation()/record_gate_activation()/open_commercial_validation()/finalize_retained_genome()`
- `opportunity_from_underwriting_wire()`
- `FoundryWSGIApp`

## Bounded authority

The Foundry creates data, recommendations, architectures, and non-executing pipeline state. It cannot issue capability grants, ratify itself, contact a buyer, move money, activate an organ, or call an external adapter. Human approval and the canonical Consequence Gate remain separate requirements.

## Available dependencies

Runtime modules use the Python standard library and existing Kernel modules. Verification additionally uses `pytest`, `PyYAML`, and `jsonschema`, installed by CI.

## Security model

Inbound underwriting is treated as untrusted. The boundary enforces service identity, HMAC body signatures, timestamp freshness, nonce replay protection, changed-content idempotency protection, schema floors, body limits, provenance hashes, human approval provenance, zero execution authority, and an accountable legal operator.

## Failure modes

The module fails closed on incomplete opportunities, missing evidence, duplicate routes, changed-content replay, widened authority, malformed provenance, unresolved blockers, skipped commercial stages, unverified outcomes, negative-margin closure, missing Gate receipts, and changed architecture content.

## Acceptance tests

Unit coverage includes strategy completeness, replay refusal, false-closure rejection, signed transport, WSGI intake, full restart recovery, paid-validation transitions, pipeline reconstruction, self-ratification refusal, and immutable Genome sealing. The complete registry executes five closure checks for this module.

## Recovery path

Accepted opportunities, compiled architectures, commercial cases, pipeline snapshots, rejected branches, closure evaluations, and sealed Genomes are recorded on the Evidence Ledger. Restart reconstructs resumable state. Invalid mutations are rejected rather than patched in place.

## Resource ceiling

Every opportunity declares trapped value and constraints. Capability needs declare budgets. Commercial progression is stage-gated. Transport bodies are capped at 1 MB. No operation receives implicit or unlimited budget.

## Operating cost

Core validation and lookup are linear in the number of branches, capabilities, or ledger records being replayed. External model, network, and commercial costs are outside this module and require explicit authorization.

## Legal operator

Every accepted opportunity and Genome names an accountable legal operator. `UNIIMENTE` is categorically refused as the legal operator.

## Handoff

The handoff state is the content-addressed opportunity, architecture, pipeline run, commercial case, evidence references, and immutable Advantage Genome. Downstream organs consume these records without inheriting authority.

## Replaceable

Scoring policies, transport hosts, capability implementations, and commercial adapters are replaceable behind typed contracts. The Evidence Ledger, authority boundaries, and historical records survive replacement.
