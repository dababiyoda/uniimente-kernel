# cortex

Polyintelligence Cortex seed (0.1.6): the Competency Compiler seed. A deterministic router classifies a
problem's geometry, checks which cognitive organs are eligible, runs them under a budget, attacks the output with
an independent verifier, and returns `recommend` / `abstain` / `bounded_test` / `handoff` with a content-addressed
receipt that creates no authority. Full documentation: `docs/cortex/README.md`,
`docs/cortex/SEED_EXPERIMENT_REPORT.md`, `docs/cortex/CONVERGENCE_2026-10-13.md`.

## Organs

- `routing.py` — `Cortex.run(problem, records=...)`: geometry → eligibility → budget → route or bounded
  composition → typed artifact → adversarial verification → disposition → receipt.
- `organs/` — Formal (Z3, certified optimization), Estimation (Fermi), Evidence/Causal, Semantic (local model),
  Deterrence (lawful, Becker condition), Adversarial verifier.
- `gates.py` — hard gates before any ranking; `memory.py` — `CompetenceLedger` settling only on verified
  outcomes; `genome.py` — `IntelligenceGenome` projection of `capabilities.genome.CapabilityGenome`;
  `evaluation/` — frozen harness, scorer, exit rule, `replay.py` for transcript-served baseline arms.

## Recorded proof

`tests/unit/test_cortex_*.py` (routes, pipeline, gates/genome, traceability, register, replay, proposer,
defect fixes); `scripts/ci/check_cortex_mutants.py` (43 safeguard-removing mutants, all caught by behavioural tests with the freeze-hash checks deselected);
`tests/evidence/cortex-seed-v*/` frozen held-out runs.

## Buildability standard (14 conditions)

- **Existing mechanism**: per-instance algorithm portfolios, SMT solving, Monte Carlo estimation, adjustment estimators, exact-quote grounding — standard, no novel science.
- **Defined interface**: `Cortex.run`, `IntelligenceRegistry.eligibility`, `CompetenceLedger.settle/estimate/reorder`, `egregore.cortex_proposer.CortexProposer`; receipts, geometries, genomes, proofs and routing memory are JSON Schema contracts under `contracts/cortex-*.schema.json`.
- **Bounded authority**: every receipt carries `authority_created: false` and `execution_authority: "none"`; the package imports no Gate, adapter or actuator; financial/irreversible, legal, normative and institutional questions are handed off.
- **Available dependencies**: Python 3 stdlib, `jsonschema`, optional `z3-solver` (`requirements-cortex.txt`); the semantic organ uses the existing loopback `egregore.local_model` client.
- **Security model**: hard gates before ranking; permission-bearing records only from provenance-checked origins; declared harm may raise the consequence class, never lower it; the verifier only lowers a disposition; the proposer refuses receipts that fail their contract, content address or spend ceiling.
- **Failure modes**: explicit states (`FORMALIZATION_INCOMPLETE`, `WORLD_UNVERIFIED`, `DEPENDENCY_UNAVAILABLE`, `TIMEOUT`, `BUDGET_EXHAUSTED`, `NOT_IDENTIFIED`, `INSUFFICIENT_EVIDENCE`, `CONTESTED`, `MALFORMED_INPUT`, …) map to abstain/bounded_test/handoff; never a guess.
- **Acceptance tests**: the test modules named above; `closure/cortex_registry.py` five closures (verifier V3).
- **Recovery path**: receipts are pure data; the competence ledger rolls back to any head; a bad organ is detached by registry status, never patched in place.
- **Resource ceiling**: `ResourceLimits` (cost, latency, model and solver calls) refused before spending; the composition cap is two routes and is disclosed on the receipt.
- **Operating cost**: solver and arithmetic in-process; one loopback model call per sourced item at most.
- **Legal operator**: Alfonso Lopez (named on every seed genome; UNIIMENTE is never an operator).
- **Handoff state**: the receipt plus the ledgered `cortex.receipt` record; a fresh process re-derives eligibility and routing from the registry and the frozen policy table.
- **Replaceable**: organs are registry entries behind one interface; the route policy is a readable table; reserved families register disabled and must beat a simpler baseline before any executor exists.

## Orthogonal closures

Verified by `closure/cortex_registry.py` → module `cortex` (through `closure/integration_registry.py`).
