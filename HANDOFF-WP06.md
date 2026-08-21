# HANDOFF-WP06 — Fast Capability Evolution

Status: complete in the slice. Branch: `build/fast-evolution` (stacked on
`build/evolution-cycle`). Verifier: v10.

## What shipped

The first AUTOMATED capability-evolution cycle over the UNCHANGED WP-05
ClosureLoop engine (SPEC-WP06; cycle.py is byte-identical to blob
99a3cdcd6744a6f1c871fe797316854bfb4ed66c):

1. BRANCH GENERATION — `kernel/evolution/generate.py`: `MutationSpace` +
   `BranchGenerator` mechanically enumerate the declared space into
   StrategyBranch drafts (control excluded; unscored variants fail closed).
   The `agent_callable` injection point admits a future LLM WITHOUT contract
   changes (agent drafts are validated: StrategyBranch, tree_id="", full
   score rubric). The honest audit declaration rides inside the draft
   hypothesis as a canonical-JSON `variant_config` block — the frozen WP-05
   StrategyBranch shape is never edited.
2. ISOLATED TESTING — `scripts/wp06_bench.py`: ONE pinned matrix harness,
   fresh store per variant, deterministic peak-buffered-rows metric
   (verifier hierarchy level 1; no wall clock anywhere).
3. FAILURE ANALYSIS — sealed `FailureAnalysis` for chunk256
   (threshold_unmet, regression_test_ref pinned at
   `tests/evolution/test_wp06_bench_matrix.py::test_chunk256_peak_rows_below_threshold_regression_pin`)
   and no_commit_stream (audit_killed, killed pre-experiment by
   TransactionSemanticsRule + DeclaredReversibilityRule — a REAL mechanical
   kill of a mechanically generated branch).
4. COMPARISON — `kernel/evolution/compare.py`: pure `build_report` /
   `build_proposal`; sealed `ComparisonReport` ranks stream #1 (peak 1 vs
   baseline 1000, improvement 0.999 >= 0.90), chunk64 beaten (0.936),
   chunk256 below_threshold (0.744), no_commit_stream not_measured.
5. IMPROVEMENT PROPOSAL — sealed PENDING; founder ratification is a gated
   act (`founder_ratify` verifies a founder approval over the proposal
   fingerprint) recorded as a RATIFICATION InstitutionalEvent. The contract
   never self-ratifies.

Ratified adoption (ADR-2 sandbox-first): `PostgresSpine.verify_chain_streaming()`
— ADDITIVE pg.py method, identical Python-side verification logic and
verdicts as `verify_chain` (parity-tested on the honest chain and all four
WP-04 anomaly fixtures), peak buffered rows 1 vs 1000.

## Acceptance evidence

- Full suite: **289 passed** (213 pre-existing + 76 new in
  tests/evolution/test_wp06_*.py), rc=0.
- `python scripts/run_fast_cycle.py` rc=0 TWICE, verdict line byte-identical:
  `... verdict=baseline_beaten ... improvement_ratio=0.999 ...`
- Capsule: `proof/wp06_fast_cycle_capsule.json` (ok=true,
  verdict=baseline_beaten, improvement 0.999), hash-sealed on the spine.
- pg.py / benchmark.py diffs vs the WP-05 blobs: additions only.
- Zero credential hits; no DSN anywhere in the measurement path.

## ADR confirmations (SPEC-WP06 6)

1. NO engine edits — the matrix protocol carries per-variant measurements
   under one gated C2 experiment. cycle.py blob unchanged.
2. Sandbox-first adoption — candidates incubate as harness-local functions;
   only the ratified winner landed in pg.py, additively.
3. One gated experiment for the whole matrix — one bounded action family,
   one witness, one founder approval.
4. Mechanical generation over a declared MutationSpace; agent_callable
   injection point; unscored variants fail closed.
5. Failure produces sealed FailureAnalysis + pinned regression test;
   test-less threshold/regression failures are unconstructable.
6. Ratification is a gated founder act recorded as an event; the proposal
   is sealed pending and never self-ratifies.
7. Deterministic peak-buffered-rows metric; no wall clock.
8. The harness dogfoods WP-05's append_many to build the 1000-record chain
   in ONE batch — the previous cycle's win accelerates this one.

## Deviations / decisions the verifier should know

1. **Matrix protocol 7-key shape** (SPEC-WP06 3.7 RESOLUTION): keys are
   `workload_id, harness_ref, metric, candidate_variant, baseline_value,
   variant_values, variant_traces`. `candidate_variant` names the
   pre-registered selection outcome so the UNCHANGED engine verifier stage
   (which reads `candidate_value` from the receipt facts) works unmodified;
   the full matrix rides in `variant_values` and is cross-checked per variant
   by the WP-06 verifier stage.
2. **benchmark.py extension mechanism**: not a single existing line edited.
   The original `_perform` is preserved as `_WP05_SINGLE_PAIR_PERFORM` and a
   shape dispatcher is installed by same-module rebinding at file end —
   additive at the diff level; WP-05 path delegates byte-for-byte.
3. **`build_report` spec_map**: binds branch_id -> sealed StrategyBranch
   draft; the branch's generator-embedded `variant_config` provides the
   mechanical branch<->variant binding (the frozen ExperimentSpec shape has
   no variant field). `metric_unit` is a required keyword parameter.
4. **`BranchGenerator(scoring, *, declarations=None)`**: the optional second
   parameter carries the honest per-variant audit declarations
   (modifies/touches/new_dependencies/commit_strategy); omitted -> the safe
   sandbox default (all-empty + commit_after). Missing entries fail closed.
5. **Count tests**: both `tests/test_contracts.py` (28 -> 31) and
   `tests/evolution/test_evolution_contracts.py::test_09` (28 -> 31) were
   amended — the latter also pins the exact registry count; leaving it would
   have broken the suite (same forced-amendment pattern as WP-05 A2).
6. **kernel/evolution/__init__.py** gained an import-order guard
   (`from ..gate import pipeline` before `.cycle`) resolving the LATENT WP-05
   circular import (`kernel.evolution` standalone import previously failed);
   additive only, no behavior change.
7. ImprovementProposal is constructable ONLY as pending (model validator);
   the ratified/rejected literals document the event-driven state machine.

## Limitations (honest, SPEC-WP06 7)

- The generator enumerates; it does not invent axes. Genuine novelty needs
  the future agent_callable (LLM) path.
- The audit rules are syntactic, not semantic; human ratification is the
  backstop.
- Peak rows is a memory-complexity proxy, not measured RSS.
- The matrix runs under one approval; per-branch authority is available but
  unused (design choice).
- Ratification here is the founder service in-script; hardware founder-key
  ceremony remains deferred.
