# Developmental Substrate — MICA/CDPE TARGET_FORM_001

## Purpose

Test whether bounded local competencies can recover resource-transport function after structural damage without restoring removed cells or depending on the original route.

The benchmark contains 120 cells and three tissues:

- sensor tissue receives the resource;
- transport tissue routes it through local neighbor interactions;
- actuator tissue consumes it at the target sink.

The experiment removes exactly 20% of cells, blocks every edge in the original route, prohibits exact restoration, and compares:

1. MICA asynchronous local field repair;
2. a brittle static centralized route;
3. a strong adaptive centralized replanner.

A passing verdict is `MECHANICS_VALIDATED_NOT_PRODUCTION_AUTHORIZED`. It does not establish consciousness, biological life, sovereignty, production readiness, or superiority in every environment.

## Frozen contracts

- `CellState v0.1`
- `LocalRuleGenome v0.1`
- `IntelligenceGenome v0.1`
- `TARGET_FORM_001`

The rules and thresholds are immutable during a benchmark run so the system cannot redefine success after seeing the outcome.

## Buildability contract

- **Existing mechanism:** canonical event/evidence doctrine, bounded Capability principles, ternary signals, local von Neumann neighborhoods, deterministic graph perturbation, and Whole-Body Closure verification.
- **Defined interface:** `MICAField`, `DevelopmentalProgramExecutor.run`, `simulate_transport`, and `DevelopmentalBenchmarkReport`.
- **Bounded authority:** every contract fixes `production_authority=false`, `authorization_state=SIMULATED_NOT_AUTHORIZED`, and `external_effects=0`; the benchmark cannot promote itself or call the Consequence Gate.
- **Available dependencies:** Python standard library, immutable v0.1 contracts, deterministic 12x10 lattice, local message queue, and repository test/verifier infrastructure.
- **Security model:** deny exact restoration, removed-cell reactivation, external effects, mutable success criteria, source/sink removal, route cycles, unknown cells, and production authority.
- **Failure modes:** no initial route, no alternate route, incorrect removal fraction, missing tissue, route not blocked, false activation, exact-restoration attempt, recovery timeout, throughput deficit, excessive compute ratio, or invalid centralized counterexample.
- **Acceptance tests:** 120 cells, three tissues, local potential descent, exactly 24 removed cells, original route fully blocked, novel recovered route, static baseline failure, adaptive baseline recovery, >=90% adaptive throughput, <=4x adaptive planning work, zero false activation, zero restoration, deterministic benchmark id, and zero external effects.
- **Recovery path:** preserve the failed report, inspect topology and local-rule assumptions, publish a new immutable Genome version, rerun against the same counterexamples, and retain the simpler centralized architecture when the distributed design fails its promotion threshold.
- **Resource ceiling:** 120 cells, 40 post-damage ticks, one packet injection per tick, one hop per packet per tick, fixed neighborhood, and declared planning-operation ratio.
- **Operating cost:** local field messages, transport operations, centralized path scans, memory for cell state, test execution, and human interpretation of benchmark evidence.
- **Legal operator:** none; this is a sandbox simulation. Any future external experiment requires a named human or lawful entity and a separate Consequence Gate action.
- **Handoff:** frozen contracts, deterministic removal set, blocked-edge set, original and recovered routes, distributed/static/adaptive metrics, benchmark hash, checks, failures, and non-authorizing verdict.
- **Replaceable:** lattice dimensions, transport task, local update algorithm, visualization, and simulator runtime may change only in a new version; the evidence, authority, perturbation, baseline, and no-restoration boundaries must remain explicit.
