# UNIIMENTE Kernel: Architecture

## Pipeline

```
Signals and requests
        |
        v
Evidence intake and quarantine        <- Evidence Browser: raw vault, hashes, source authority, instruction-shaped content quarantined
        |
        v
Institutional Event Spine             <- typed CloudEvents envelopes, causal parents, policy versions
        |
        v
Identity + authority resolution       <- SPIFFE-style identities, legal principal resolution, grant lookup
        |
        v
Constitutional policy compiler        <- UCL compiles to policy decisions
        |
        v
Durable Plan Executor                 <- workflows survive crashes, approvals, timers, compensation
        |
        v
Sandboxed agent or tool execution     <- typed interfaces, least capability, quotas, isolation
        |
        v
Commit-time authorization             <- revalidate grant freshness, effect binding, budget, legal principal
        |
        v
External action gateway               <- the only path to real-world effects
        |
        v
Outcome + provenance ledger           <- append-only, hash-chained, signed receipts
        |
        v
Causal memory + Portfolio Governor    <- learning, allocation, replication, termination
```

## Layer responsibilities

| Layer | Owns | Explicitly does not own |
|---|---|---|
| Alfonso Sovereign Interface | decisions, shutdown, amendments, capital authority | execution |
| Constitution (UCL) | purpose, rights, prohibitions, authority hierarchy | application code |
| Identity + Authority Fabric | who/what every actor is, grants, legal principals | authentication of humans (delegated to IdP later) |
| Event Spine | typed institutional events | direct organ-to-organ calls |
| Plan Executor | durable workflow state | business logic |
| Agent Cell Sandbox | isolation, typed tools, quotas | model weights |
| Commit-Time Gateway | final revalidation before any real effect | policy authorship |
| Outcome + Provenance | append-only consequence record | observability signals (kept separate per OpenTelemetry split) |
| Causal Memory + Portfolio Governor | learning and allocation recommendations | spending authorization (scores never authorize spend) |

## The three histories

Every consequential question must be answerable from three reconstructable histories:

1. **State history**: what was true at time T.
2. **Belief history**: what the institution believed, with what confidence and evidence.
3. **Authority history**: who had permission to do what at time T.

"Why did the system approve this action on September 12?" must reconstruct: evidence available, policy version, responsible actor, capability grant, active affect vector, dissenting analysis, legal principal, and expected outcome.

## Integrity without a blockchain

One governed institution does not need trustless consensus. Use content-addressed objects, cryptographic hashes, signed attestations, append-only logs, independent backups, and optional external timestamping. High-consequence evidence and approvals get independently verifiable signed receipts (evidence escrow).

## Organs

| Organ | Role | Consumes from Kernel |
|---|---|---|
| RailScout | perception and evidence refinery | event spine, evidence contracts |
| DALEOBANKS | public voice and distribution | shared governance services, action gateway |
| WealthMachine | venture evaluation and Venture Cell management | opportunity/assessment contracts, charters, autonomy levels |
| Personal Command | founder development and capacity | daily brief, decision training |
| Constitutional Control Layer | policy, budgets, kill authority | is the Kernel |
| Adversarial Intelligence | attacks the institution's own reasoning | laboratory tests, dissent records |

## Hidden capabilities (scheduled, not built)

Institutional forks (policy simulation branches), reputation compartments, black-start recovery core, memory immune system, evidence escrow, competence inheritance, controlled self-cannibalization, dependency leverage map. Each enters only through a phase gate in `docs/BUILD_ORDER.md`.

## Codemap

Where is the thing that does X? This is a map, not an atlas: it names
directories and the few files that anchor them. Each directory's `README.md`
has the detail. (Format after matklad's ARCHITECTURE.md convention.)

**Law (data).** `constitution/*.ucl` → compiled by `compiler/ucl_compiler.py`
(`compile_constitution`) into the `CompiledConstitution` that `policy/engine.py`
evaluates. `authority/`, `identity/*.yaml`, `affect/`, `workflows/` are the
other declarative sources.

**The consequence path.** A `policy.engine.Proposal` enters
`policy/consequence_gate.py` (`ConsequenceGate.run`). The gate checks identity
(`identity/machine_passport.py`), grants, evidence floors, budget and
commit-time revalidation, signs a `provenance/commit_witness.py` witness,
calls the executor, and appends witness, receipt and outcome to
`provenance/ledger.py` (`EvidenceLedger`, hash-chained; `provenance/proof.py`
gives Merkle proofs). Nothing else in the repository may cause an external
effect.

**Coordination.** `events/spine.py` (typed events, inbox/outbox,
`DurableWorkflow` kill-and-resume) is the nervous system; `loom/` weaves
human-ratified workflow patterns onto it. Cross-organ shapes are
`contracts/*.schema.json`; `adapters/` translate between versions;
`linker/` resolves organ-to-organ edges from `organs/*.manifest.yaml`.

**Governed capability.** `capabilities/` (genomes, authority envelopes),
`embassy/` (foreign agents as guests), `autonomy/` (A0–A8 ladder), `memory/`
(causal memory, calibration, affect), `capital/` (treasury waterfall),
`twins/` (counterfactual tribunal). All of them *recommend*; the gate decides.

**Improvement.** `evolution/` runs strategy trees → spider-web audits →
experiments → capsules → retain/regress/kill (`evolution/loop.py`,
`evolution/auto_cycle.py`). `evolution/repair/` and `evolution/migration/` are
frozen Package 3/4 experiments.

**Closure and verification.** `closure/` declares five orthogonal closures per
module (`kernel_registry.py`, `integration_registry.py`) and the Whole-Body
Closure Controller (`whole_body.py`). `verifier/v2/verify.py` runs them (V1–V5)
and records each run under `verifier/runs/`.

**Extensions.** `egregore/` (ADE-1 standing cognition, `runtime.tick`),
`foundry/` (Advantage Foundry and the open-source research line),
`omnimorph/`, `business/`, `morphogenesis/`. Each produces proposals; any
effect must be submitted as a `Proposal` to `ConsequenceGate.run`
(`egregore/gate_adapter.py` is the reference adapter).

**Research.** `developmental/` is sealed from consequence; CI job 4 proves it.

**Shared mechanics.** `common/` (canonical JSON, `sha256:` refs, UTC clock).

## Dependency direction

- Law and identity data depend on nothing.
- `compiler/` → law; `policy/` → `compiler/`, `identity/`, `provenance/`.
- Everything that can propose depends on `policy/` for effects; `policy/`
  depends on none of them.
- The published boundary distribution (`adapters/`, `contracts/`, `events/`,
  `provenance/`; see `pyproject.toml`) imports only itself and the standard
  library plus `jsonschema`. WealthMachineIntelligence and DALEOBANKS pin it.
- Core packages never import from venture code (`tests/unit/test_core_venture_boundary.py`).

## Invariants (each enforced by a named check)

| Invariant | Enforced by |
|---|---|
| Exactly one Constitution, Gate, authority matrix, legal-principal and identity registry | `scripts/ci/check_authority_singleton.py` (CI job 3) |
| Every contract `$ref` resolves | `scripts/ci/check_schema_refs.py` (CI job 2) |
| Developmental research has zero external effects and no self-granted authority | `scripts/ci/check_sealed_developmental.py` (CI job 4) |
| Every core module closes all five closures | verifier V3 |
| False closure is detected | verifier V4 |
| Core never depends on ventures | `tests/unit/test_core_venture_boundary.py` |
| Frozen experiments still describe the real artifacts | `tests/unit/test_repair_spec_frozen.py`, `test_migration_spec_frozen.py` |
| Every top-level directory is documented | `tests/unit/test_repository_map.py` |

## Sealed artifacts

These bytes are pinned by preserved experiment records
(`evolution/repair/subjects.py`, `evolution/repair/spec.py`,
`evolution/migration/spec.py`). Editing them is not a refactor: it changes
constitutional identity and fails the continuity tests until a new reviewed
binding is recorded.

- `constitution/*.ucl` (all five)
- `authority/authority-matrix.yaml`, `legal-principals.yaml`, `reserved-matters.yaml`
- `identity/organ-registry.yaml`, `agent-registry.yaml`, `service-identities.yaml`
- `policy/consequence_gate.py`
- source of `events.spine.DurableWorkflow` and `events.spine.WorkflowStep`
  (hashed with `inspect.getsource`)
- everything under `evolution/repair/` and `evolution/migration/` (frozen
  experiment implementations; changes there would rewrite evidence)

## Cross-cutting conventions

- **Canonical hashing.** `common.sha256_ref` for non-boundary code;
  `provenance.commit_witness.sha256_obj` inside the boundary package;
  `egregore.contracts.digest` for ADE-1 records (stricter form, different
  bytes for non-ASCII). Do not switch an existing caller between them.
- **Time.** UTC everywhere; `common.utc_now()` / `utc_now_iso()` (`Z` suffix).
- **Failure.** Validation errors subclass `ValueError` per module
  (`AdvantageRefused`, `RouterError`, `CompilationError`, …) and fail closed.
- **Lifecycle words.** `canonical`, `active_experimental`, `fallback`,
  `superseded`, `historical`, `quarantined` (integration program §3); intent
  states per `FOUNDER_INTENT_LEDGER.md`.
