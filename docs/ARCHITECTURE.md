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

## Current module map (2026-11-05)

The sections above describe the Kernel pipeline as designed in September. Since
then most code lives in packages they do not name. This map answers "where is
the thing that does X?" for the live integration line. Each directory's
`README.md` has the detail; sizes are from `python scripts/repo_review.py`.

| Package | Owns | Entry point |
|---|---|---|
| `greg/` (~87k lines, the majority of the code) | the product: persistent body, signed founder commands, missions, Capability Genesis, Goal Gravity, organs bridge, Mission Control, morning tribunal | `python -m greg` (`greg/cli.py`); `greg/README.md` |
| `greg/cognition/` | GREG's Mind: Competency Compiler, genome library (`genomes/`), certificates | `greg/cognition/compiler.py` |
| `cortex/` | Polyintelligence Cortex: eligibility-first routing among solvers/verifiers/organs; frozen evaluations | `cortex/routing.py`; `cortex/README.md` |
| `foundry/` | the 55 Foundry systems (`foundry/systems/`), Advantage Foundry, Lawful Leverage Foundry, research line | `foundry/README.md` |
| `egregore/` | ADE-1 standing cognition, Goal Chase, the `main`-line Goal Gravity runtime, morning review | `egregore/runtime.py` |
| `acceptance/` | whole-machine acceptance: Missions A–L, the completion contract, the directive's computed completeness | `python -m acceptance directive` |
| `governance/` | live constitutional-integrity tripwire and the protected-file manifest | `python -m governance.integrity --check` |
| `policy/`, `provenance/`, `events/`, `identity/`, `compiler/` | the consequence path described above (Gate, ledger, spine, passports, UCL) | sections above |
| `capabilities/`, `closure/`, `evolution/`, `loom/`, `twins/`, `memory/`, `autonomy/`, `embassy/`, `capital/`, `business/`, `omnimorph/`, `morphogenesis/`, `linker/`, `adapters/` | the governed-capability layers from the July–September phases | each `README.md` |
| `developmental/` | sealed mechanism-research laboratory | CI `sealed` job |

**Two implementations, one open decision.** Goal Gravity exists as
`egregore/gravity.py` (`main`'s runtime) and `greg/goal_gravity.py` /
`greg/gravity.py` (the GREG line). Which is canonical is a recorded founder
decision (`docs/FOUNDER_INTENT_LEDGER.md`, "the canonical Goal Gravity runtime");
both are kept.

### Dependency rules that are enforced

`tests/unit/test_import_layering.py` (same rules as `scripts/repo_review.py`):

- The published boundary distribution (`adapters/`, `contracts/`, `events/`,
  `provenance/`; `pyproject.toml`) may import only itself. One violation is
  recorded and kept: `provenance/witness.py` lazily imports `capabilities.genome`,
  which a boundary-only install lacks.
- No **new** two-way dependency between top-level packages. Nine exist today
  (for example `greg`↔`cortex`, `greg`↔`foundry`, `closure`↔`foundry`) and are
  listed with reasons; the list can only shrink.

Ordinary one-way imports are not ratcheted: adding them is normal feature work.

### What must not be edited without a founder signature

`governance/integrity/manifest.json` is the authoritative list (Constitution,
authority and identity registries, the Consequence Gate, founder keys). Frozen
evaluation records (`cortex/evaluation/**/freeze*.json`,
`docs/evidence/**/freeze.json`), the sealed `evolution/repair/` and
`evolution/migration/` packages and `evolution/repair/continuity/` are
evidence: new runs get new paths.
