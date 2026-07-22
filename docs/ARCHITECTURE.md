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
Independent proof credential          <- verifier-bound outcome, receipt, evidence, policy and reality status
        |
        v
Principal-authorized settlement       <- exact scope, expiry, idempotency, commit-time revalidation, reconciliation
        |
        v
Scoped reputation + Causal memory     <- context-bound history; never a universal score or spending authority
        |
        v
Portfolio Governor                    <- learning, allocation, replication, termination
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
| Independent Verification | verifier attestations and outcome credentials | deciding whether the underlying physical claim is true by signature alone |
| Settlement Router | principal-signed intent, adapter selection, commit revalidation, receipt reconciliation | AI decisions, legal identity, or unrestricted payment access |
| Scoped Reputation | exact-context evidence history | global scoring, authority, or automatic spending |
| Causal Memory + Portfolio Governor | learning and allocation recommendations | spending authorization (scores never authorize spend) |

## The three histories

Every consequential question must be answerable from three reconstructable histories:

1. **State history**: what was true at time T.
2. **Belief history**: what the institution believed, with what confidence and evidence.
3. **Authority history**: who had permission to do what at time T.

"Why did the system approve this action on September 12?" must reconstruct: evidence available, policy version, responsible actor, capability grant, active affect vector, dissenting analysis, legal principal, and expected outcome.

## Integrity without a blockchain

One governed institution does not need trustless consensus. Use content-addressed objects, cryptographic hashes, signed attestations, append-only logs, independent backups, and optional external timestamping. High-consequence evidence and approvals get independently verifiable signed receipts (evidence escrow). The trust rail can later anchor proofs or settle through a blockchain adapter, but blockchain consensus does not verify an off-chain physical outcome; an independently governed verifier or oracle remains necessary.

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

Black-start recovery core, memory immune system, competence inheritance, controlled self-cannibalization, dependency leverage map. Each enters only through a phase gate in `docs/BUILD_ORDER.md`.
