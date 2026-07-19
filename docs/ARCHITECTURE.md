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
| IVIO-NEMT | first closed-loop proving ground | full pipeline |
| Personal Command | founder development and capacity | daily brief, decision training |
| Constitutional Control Layer | policy, budgets, kill authority | is the Kernel |
| Adversarial Intelligence | attacks the institution's own reasoning | laboratory tests, dissent records |

## Hidden capabilities (scheduled, not built)

Institutional forks (policy simulation branches), reputation compartments, black-start recovery core, memory immune system, evidence escrow, competence inheritance, controlled self-cannibalization, dependency leverage map. Each enters only through a phase gate in `docs/BUILD_ORDER.md`.
