# Business Foundry

## Purpose

Compile a complete Business Genome and operate its commercial loop from recurring problem through buyer, offer, payment, delivery, verified customer outcome, and retention or termination.

## Buildability contract

- **Existing mechanism:** Capability Genome Registry, Loom Ratifier, Consequence Gate, Evidence Ledger, and Whole-Body Closure Controller.
- **Defined interface:** `BusinessGenomeCompiler.compile()` and `CommercialLoop` stage methods.
- **Bounded authority:** compilation grants no execution authority; payment and delivery require exact Gate-bound proposals.
- **Available dependencies:** Python, canonical Kernel modules, registered capabilities, ratified workflows, and evidence references.
- **Security model:** deny by default; UNIIMENTE cannot be legal operator; no out-of-order stages; no weak-evidence payment.
- **Failure modes:** missing demand, absent capability, unratified workflow, negative margin, weak evidence, failed external execution, unverifiable outcome, or triggered kill condition.
- **Acceptance tests:** invalid genomes fail closed; full ordered loop reaches `CLOSED`; self-reported outcomes do not count.
- **Recovery path:** preserve refusal/termination evidence, correct the Genome, recompile as a new version, and resume only from reconciled state.
- **Resource ceiling:** Genome budget, Capability authority envelopes, Gate budget reservations, and marginal-cost constraints.
- **Operating cost:** explicitly modeled as marginal cost, Gate reservations, and fully loaded fulfillment cost.
- **Legal operator:** a named human or lawful entity, never UNIIMENTE.
- **Handoff:** accepted deliverables, receipts, outcome verification, reconciliation record, and sealed Capability Genome.
- **Replaceable:** pricing, distribution, fulfillment, and capability implementations may change behind stable contracts.
