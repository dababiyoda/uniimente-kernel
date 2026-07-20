# business

Phase 7 — Digital Business Foundry: business creation as an
evidence-gated manufacturing process, not improvisation.

## Organs

- `genome.py` — BusinessGenome + BusinessGenomeCompiler: problem, buyer,
  offer, price, distribution, conversion, fulfillment, retention,
  economics, demand evidence, required capabilities (checked against the
  Capability Genome Registry), required workflows (must be ratified Loom
  patterns), legal restrictions, regenerative effect, kill condition,
  and the 90-day falsification test. Incomplete genomes, negative
  margins, missing demand evidence, absent capabilities, and unratified
  workflows refuse to compile; refusals are preserved as negative
  evidence on the ledger.
- `commercial_loop.py` — the Commercial Loop (loop 7), closed in order
  or not at all: problem → buyer → offer → payment → delivery →
  customer outcome → retention or termination. Payment (`financial`)
  and delivery (`external_contact`) each run through the Consequence
  Gate with exact-effect-bound single-use grants, their own Commit
  Witnesses and receipts. Customer outcomes are accepted only from the
  strong half of the verifier hierarchy (self-report and model
  confidence cannot verify customer value). Launch without revenue
  evaluates FALSELY_CLOSED. The precommitted kill condition terminates
  the business and blocks all further steps.

## Buildability standard (14 conditions)

- **Existing mechanism**: typed contracts, state machines, gate-mediated transactions — no novel science.
- **Defined interface**: `BusinessGenomeCompiler.compile(genome) -> CompiledBusiness`; `CommercialLoop.open_case/present_offer/take_payment/deliver/verify_outcome/resolve/evaluate/trigger_kill`.
- **Bounded authority**: the loop cannot move money or contact buyers itself; every payment and delivery is a gate run with its own witness, receipt, and commit-time revalidation.
- **Available dependencies**: Python 3 stdlib + kernel modules (capability registry, loom ratifier, policy gate, provenance ledger).
- **Security model**: exact-effect-bound single-use grants per charge/delivery; stage order enforced; accepted-verifier whitelist for outcomes.
- **Failure modes**: `GenomeCompileError`, `CommercialLoopError` (out-of-order advance, unrecorded payment/delivery, weak verification, dead business); all fail closed.
- **Acceptance tests**: `tests/unit/test_business.py` (17 tests, adversarial suite included).
- **Recovery path**: case history and gate receipts reconstruct every stage; a terminated business preserves its full trail as learning.
- **Resource ceiling**: spending bounded per-case by the genome's price and marginal cost via grant spending limits.
- **Operating cost**: two gate runs + constant ledger appends per customer case.
- **Legal operator**: Alfonso (never UNIIMENTE — refused at compile).
- **Handoff state**: genome hash + compiled record + case histories + ledger receipts are the complete handoff.
- **Replaceable**: executors (payment/delivery rails) are injected; genomes are data; the loop survives swapping any provider.

## Orthogonal closures

Verified by `closure/kernel_registry.py` → module `business`.
