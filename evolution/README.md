# evolution

Phase 2 — First Evolution Cycle: the recursive self-improvement machinery.

## Organs

- `strategy_tree.py` — Strategic Tree Search: 11 mandated branch kinds
  (fastest path → do-nothing), 12 required fields per branch, rejected
  branches preserved with rejection reason and revival evidence.
- `spider_web.py` — Spider-Web Integrity Engine: 8 sides, 4 governing
  super-nodes (eligibility, default routing, proof & truth, cashflow &
  settlement), 11 completeness requirements, decorative mechanisms removed.
- `experiment.py` — Experiment Compiler: decisive unknown → smallest
  reversible experiment. Irreversible, unfalsifiable, or unbudgeted
  experiments refuse to compile.
- `capsule.py` — EvolutionCapsule, VerifierRecord (7-level verifier
  hierarchy; levels 6–7 are hypothesis-only and cannot authorize
  promotion), RetainRegressKillDecision.
- `loop.py` — ClosureLoop: bottleneck → branches → audit → decisive
  unknown → experiment → measurement → verification → comparison vs
  baseline → retain/regress/kill → capsule on the ledger → whole-body
  evaluation of the change itself.

## Recorded proof

`tests/unit/test_evolution.py::test_complete_machine_recorded_improvement_cycle`
runs one complete manual machine-recorded cycle against the real
Consequence Gate: raising the `external_contact` evidence floor from
0.70 → 0.75 eliminates weak-evidence admissions (2 → 0) with zero new
good refusals, verified by formal proof (deterministic replay invariant),
decision RETAIN, capsule preserved on the ledger with all 10 rejected
branches and their revival evidence.

## Buildability standard (14 conditions)

- **Existing mechanism**: search trees, audit checklists, experiment runners — all standard, no novel science.
- **Defined interface**: `ClosureLoop.run_cycle(...) -> EvolutionCapsule`; typed dataclasses throughout.
- **Bounded authority**: proposes and judges; applies nothing to production (experiments carry `authority_requirements`; retain decisions go to Alfonso).
- **Available dependencies**: Python 3 stdlib + kernel modules.
- **Security model**: hypothesis-only verifiers cannot authorize retain; incomplete audits refuse; irreversible experiments refuse to compile.
- **Failure modes**: `CycleRefused` (audit incomplete, experiment invalid, verifier invalid); all refusals ledgered.
- **Acceptance tests**: `tests/unit/test_evolution.py` (10 tests incl. the full recorded cycle).
- **Recovery path**: regress decisions name the experiment's rollback path; capsules preserve the whole trail.
- **Resource ceiling**: branches bounded by tree, cycles bounded by one executor call per cycle.
- **Operating cost**: one executor invocation + constant ledger appends per cycle.
- **Legal operator**: Alfonso (ratifies retains; owns the improvement doctrine).
- **Handoff state**: the capsule IS the handoff — bottleneck, tree, audit, experiment, measurement, verifier, decision.
- **Replaceable**: executors and verifiers are injected; the loop survives any component swap.

## Orthogonal closures

Verified by `closure/kernel_registry.py` → module `evolution`.
