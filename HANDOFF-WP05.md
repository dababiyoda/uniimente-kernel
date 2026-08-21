# HANDOFF-WP05: First Evolution Cycle — Contracts, Engine, and One Sealed Cycle Beating Baseline

Status: COMPLETE. Branch: `build/evolution-cycle` (stacked on `build/pg-spine`).
Spec: `SPEC-WP05.md` v1.0 — implemented faithfully; two builder deviations
ratified as spec amendments (section 8 of the spec, A1/A2/A3).

## What was built

- `kernel/contracts/evolution.py` — the eight Phase 2 contracts plus the
  `AuditFinding` sub-record: `StrategyBranch`, `StrategyTree`,
  `SpiderWebAudit` (overall/findings consistency validator, both directions),
  `ExperimentSpec` (`threshold_improvement` in (0,1); `pre_registered`
  Literal[True] — a False value is unconstructable), `VerifierRecord`,
  `RetainRegressKillDecision`, `ClosureLoop`, `EvolutionCapsule` (sha256-hex
  validators on hash fields). All frozen, extra-forbid, tz-aware via
  `KernelModel`.
- `kernel/contracts/__init__.py` — registry extended 20 -> 28 (+1 finding
  type). Additive only.
- `kernel/evolution/cycle.py` — `EvolutionCycle`, the ClosureLoop engine:
  propose_tree (drafts sealed with tree_id via model_copy; drafts never
  mutated), audit (AUDIT_KILLED/AUDIT_PASSED as InstitutionalEvents), select
  (killed branches never eligible; missing audit fails closed; rule = max
  expected_value with risk <= 0.3 and reversibility >= 0.8, ties to lower
  cost then lower id), register_experiment (sealed before execution; order
  enforced via spine seq), run_experiment (the ONLY gated side effect: C2
  `evolution_experiment`, REQUIRE_HUMAN via the gate), verify (independent
  harness re-run cross-checked against the signed receipt facts and the
  pre-registered baseline; any contradiction -> CycleError), decide (retain
  REQUIRES threshold_met; kill decisions are first-class sealed records),
  seal_capsule (ADR-8 dual-reference order; loop record hash predicted with
  the frozen WP-01 formula and asserted against the actual append),
  seal_aborted (status="aborted", capsule_id="", never an EvolutionCapsule).
  Every refusal raises `CycleError` and appends nothing — fail closed.
- `kernel/adapters/benchmark.py` — `BenchmarkAdapter`: witness-only (Hard
  Rule 1 inherited from BoundedAdapter), pinned protocol parsed from
  `witness.expected_outcome` (exact 7-key set), harness allowlist enforced
  before any code loads, executed op trace verified against the pinned
  protocol (counts AND order), ADR-6 attestation hash, measured values in the
  signed receipt facts (external_id canonical JSON).
- `kernel/spine/pg.py` — ADDITIVE ONLY: `append_many` (one advisory lock, one
  head read, N inserts, one commit; all-or-nothing rollback; frozen per-record
  formula byte-identical to sequential append; per-element spine_seq; empty
  batch is a no-op). Diff vs the WP-04-pushed blob dd072388: 0 lines removed,
  54 lines added (verified by the orchestrator against the byte-exact WP-04
  reference, not by the builder's claim).
- `scripts/wp05_bench.py` — pinned hermetic harness: `CountingConnection`
  (op counter + op trace + honest rollback emulation; DDL never counted),
  10 fully pinned events, `measure_baseline()` = exactly 40 ops,
  `measure_candidate()` = exactly 13 ops, traces pinned.
- `scripts/run_evolution_cycle.py` — the complete cycle on a file spine in a
  temp dir (ADR-7 hermetic): tree B1/B2/B3, audits kill B2 (violates WP-04
  ADR-1) and B3 (writer multiplication risk), B1 selected, ExperimentSpec
  sealed pre-execution, gated experiment under founder approval, honest
  pytest re-run inside the cycle, decisions retain/kill/kill, capsule sealed.
  One-line verdict; exit 0 only if everything holds.
- `tests/evolution/` — 36 tests (spec section 4 categories 1-6, with
  parametrization): contract validation, append_many correctness incl. THE
  hash-parity test, bench determinism pins (40/13), engine rules, hostile
  adapter/verifier/capsule paths, end-to-end cycle.
- `proof/wp05_evolution_capsule.json` — the verifier's own cycle run.

## Verification evidence (independently re-run by the orchestrator)

- Full suite: **213 passed, rc=0** (177 pre-existing + 36 new).
- Cycle script, twice: rc=0 both times, verdict lines byte-identical:
  `ok=True verdict=baseline_beaten cycle_index=1 baseline_value=40.0
  measured_value=13.0 improvement_ratio=0.675 threshold_improvement=0.5
  threshold_met=True tests_green=True decisions=retain:'Batch append API
  (append_many)',kill:'Server-side hash chaining in SQL',kill:'Connection
  pooling for parallel appends' records=28 chain_verified=True
  capsule_hash_ok=True`
- Improvement 0.675 >= 0.5 pre-registered threshold (SPEC-WP05 3.4).
- Capsule receipt facts re-verified against current file bytes:
  baseline_source_sha256(pg.py) = 5fd979d1acee84c983f68ebfd73424e8c54ab53d80dc1ed8083216a3827809f4,
  harness_sha256(wp05_bench.py) = 19623c96b93f7f0703ac56b22794b6d07c8e395b8985afa1b7292714bf90a43d.
- Credential audit: zero `npg_`/`neon.tech`/`postgresql://` hits on every new
  artifact. WP-05 needs no DSN anywhere (hermetic by design).
- WP-04 surface: all 19 WP-04 tests unchanged and green; the live Neon drill
  was NOT re-run (append_many is additive; no existing method changed).
- Git blob SHA parity: see verifier v9 (13 files).

## Deviations ratified as spec amendments (SPEC-WP05 section 8)

- A1: `EvolutionCapsule.sealed_head_hash` = head after the ClosureLoop seal
  append = the capsule record's `prev_hash` on-chain. The spec's original
  "head after both appends" is a sha256 self-reference fixpoint, impossible.
  The capsule file documents the note; `test_32` asserts the binding.
- A2: slice-local `tests/test_contracts.py` registry-count invariant updated
  20 -> 28 (that file is not pushed upstream; the exact-count invariant is
  preserved, not weakened).
- A3: 36 tests delivered vs ~24 estimated; all six mandated categories covered.

## ADRs (confirmed, per SPEC-WP05 section 6)

1. Frozen discipline: transitions are InstitutionalEvents, never mutations.
2. The experiment is a gated C2 side effect with founder approval — the
   manual cycle honors the gate, never bypasses it.
3. ADR-6 attestation-hash contract shape reused; receipt metadata field still
   deferred to the contract-shape WP.
4. Deterministic op-count metric over wall-clock — hermetic, reproducible,
   attackable proofs.
5. First cycle additive only: zero edits to any previously verified method.
6. Kill decisions are first-class sealed records; B2/B3 are permanent
   negative knowledge, not deleted drafts.
7. File spine for this cycle's capsule; Postgres-resident cycles are a later
   WP (the substrate is WP-04 + append_many).
8. Dual-reference ClosureLoop/EvolutionCapsule seal via in-memory
   pre-construction; aborted cycles seal no capsule contract.

## Limitations (honest, per SPEC-WP05 section 7)

- Manual cycle: branches and audit content are operator-authored, not
  agent-generated (that is Phase 3 fast capability evolution).
- The metric is connection op-count on a fake DBAPI, not wall-clock latency
  on real Neon; the real-world win is presumed proportional, not proven.
- Single-horizon tree; no cross-cycle learning or branch genealogy yet.
- The verifier re-run re-executes the same harness code; independent
  execution, not independent implementation.
- The selection rule exists in prose (`selection_rule`) and in engine code;
  a UCL-compiled selection policy is future work.

## Resume steps for the next agent

1. Read `SPEC-WP05.md` (incl. section 8 amendments), this file, and
   `kernel/evolution/cycle.py`.
2. Re-run: `python -m pytest` (expect 213 passed) and
   `python scripts/run_evolution_cycle.py` (expect rc=0, verdict
   baseline_beaten; a fresh `proof/wp05_evolution_capsule.json` — record ids
   differ per run by design, uuid4; the verdict and metrics are stable).
3. Next work package per the locked build order: Phase 3 — fast capability
   evolution (agent-authored branches; the manual cycle of WP-05 becomes the
   governed substrate). Then Phase 4 Automation Loom.
