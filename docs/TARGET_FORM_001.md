# TARGET_FORM_001 — Decisive Developmental Benchmark

## Question

Can bounded local competencies recover a required institutional function after structural damage without restoring removed components, using only local signals, while remaining competitive with a strong adaptive centralized planner?

## Target form

A 12 × 10 lattice containing 120 cells and three tissues:

- 20 sensor cells;
- 80 transport cells;
- 20 actuator cells.

The required function is resource transport from one protected sensor source to one protected actuator sink.

## Local rules

Each active cell:

1. reads only immediate von Neumann neighbors;
2. receives a ternary signal: inhibit, neutral, or activate;
3. updates its target potential from local neighbor messages;
4. moves a packet at most one hop per tick;
5. moves only to a strictly lower local potential;
6. carries no external authority.

No cell receives a global route.

## Perturbation

The benchmark applies the same deterministic damage to all three policies:

- remove exactly 24 of 120 cells;
- protect source, sink, and one alternate corridor to keep the experiment falsifiable rather than impossible;
- block every edge in the original source-to-sink route;
- prohibit exact restoration;
- leave removed cells inhibited and unable to reactivate.

## Counterfactual policies

### MICA local field

The sink emits potential zero. Cells update through asynchronous local message propagation. The source follows the resulting local gradient.

### Static centralized route

The original master route is retained after damage and is not recomputed. This represents brittle top-down orchestration.

### Adaptive centralized replanner

A global breadth-first planner observes the damaged topology and recomputes the shortest available route. This is the strongest comparison and prevents the benchmark from defeating only a strawman.

## Promotion thresholds

The distributed mechanics pass only when:

- all 120 cells and three tissues are present before damage;
- exactly 20% of cells are removed;
- every original-route edge is blocked;
- removed cells remain removed;
- the recovered route is nonempty and differs from the original;
- distributed transport delivers resources after damage;
- static central transport fails;
- adaptive central transport succeeds;
- distributed post-damage throughput is at least 90% of adaptive central throughput;
- distributed planning operations are no more than 4× adaptive central planning operations;
- first delivery occurs within 40 ticks;
- false activations equal zero;
- exact-restoration attempts equal zero;
- external effects equal zero;
- production authority remains false.

## Verdict semantics

### `MECHANICS_VALIDATED_NOT_PRODUCTION_AUTHORIZED`

The local substrate demonstrated bounded functional recovery under the declared topology and perturbation. It may continue as research and simulation evidence.

### `NO_MATERIAL_ADVANTAGE`

The distributed substrate failed one or more declared comparisons. The simpler centralized architecture remains preferred until a new immutable developmental program passes the same or stronger counterexamples.

### `INVALID_EXPERIMENT`

The starting target form or comparison was not valid enough to support a conclusion.

## What this benchmark does not prove

It does not prove:

- consciousness;
- subjective experience;
- biological life;
- sovereign intent;
- general intelligence;
- market value;
- lawful operating authority;
- safety in physical systems;
- superiority outside this benchmark;
- a real customer outcome.

## Evidence packet

Each run emits:

- benchmark hash;
- frozen contract versions;
- cell and tissue counts;
- deterministic removal set;
- blocked-edge count;
- original and recovered routes;
- distributed, static, and adaptive metrics;
- throughput and compute ratios;
- false-activation and restoration counters;
- checks and failures;
- non-authorizing verdict.

The first real institutional birth threshold remains one paid, accepted, externally verified, economically reconciled IVIO/OBVIO outcome.