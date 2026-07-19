# UNIIMENTE Kernel

A constitutionally governed runtime for AI agents, ventures, media properties, workflows, evidence, and capital.

**Models reason. Agents propose. Humans and policies authorize. The Kernel determines what may become real. Reality determines what was correct.**

## The invariant

No consequential external effect occurs without:

1. a recognized identity,
2. a valid legal principal,
3. a current capability grant,
4. sufficient evidence,
5. an applicable policy decision,
6. budget authorization,
7. commit-time revalidation,
8. a provenance record,
9. and an outcome obligation.

Anything that cannot satisfy all nine does not execute. It fails toward silence, containment, preservation, degraded service, or human escalation. It never fails toward uncontrolled external action.

## What this repository is

The single source of institutional truth for UNIIMENTE, Alfonso Lopez's constitutionally governed, human-sovereign artificial egregore. Every organ (DALEOBANKS, WealthMachineIntelligence, RailScout, IVIO-NEMT, future Venture Cells) consumes governance from here. No organ owns governance locally.

This repository contains no production secrets. It contains law, contracts, and registries.

## Layout

| Path | Contents |
|---|---|
| `/constitution` | The Constitution as executable UCL: purpose, rights, prohibitions, sovereignty hierarchy, amendment and shutdown policy |
| `/authority` | Authority matrix, legal principals, reserved matters (permanently non-delegable) |
| `/contracts` | Versioned JSON Schemas shared by every organ: events, evidence, decisions, outcomes, capability grants, packets, charters |
| `/identity` | Organ registry, agent registry, service identities (SPIFFE-style) + executable machine passports (Layer 2) |
| `/affect` | Functional affect policy: bounded machine control states, identity coherence, pathological-state tests |
| `/capital` | Allocation waterfall, liquidity policy, concentration limits, acquisition gates |
| `/workflows` | Approval lifecycle, venture validation gates, incident response, shutdown recovery |
| `/tests` | Governance laboratory: constitutional, authority, capital, security, recovery, provenance test specifications + `/tests/unit` executable suites |
| `/compiler` | UCL compiler (Layer 1): doctrine → deterministic policy decisions, relationship tuples, invariants, grant contract |
| `/policy` | Policy engine + Consequence Gate (Layer 3): the sole path to external effects |
| `/provenance` | Evidence Ledger + Commit Witness (Layers 3+10): hash-chained, HMAC-signed institutional memory |
| `/closure` | Orthogonal loop closure: five closures per module + Whole-Body Closure Controller (13 loops) |
| `/events` `/sandbox` `/observability` | Kernel module specifications (build targets) |
| `/sdk-python` `/sdk-typescript` | Organ integration SDKs (build targets) |
| `/docs` | Architecture, build order, Backcast GPS plan, UCL language specification |

## Build status

**Phase 1 — Consequence Integrity: executable and verified (2026-07-20).** One bounded action family (`draft.publish`) closes the full loop: Evidence → Policy → Authority → Commit Witness → Execution → Receipt → Reconciliation → Outcome. 67 unit tests green including 12 adversarial gate cases (revoked/expired/replayed grants, effect mismatch, budget overflow, identity lapse, executor explosion — all fail closed). Verifier: `python3 verifier/v2/verify.py` (V2–V5 green; run recorded under `verifier/runs/`).

Phase 2 (First Evolution Cycle: StrategyTree, SpiderWebAudit, ExperimentSpec, EvolutionCapsule, VerifierRecord, RetainRegressKillDecision) is next. See `docs/BUILD_ORDER.md` for the ten-phase sequence and `docs/BACKCAST_GPS.md` for the stage-gated plan with kill criteria.

## The doctrine

Own the control plane. Adopt or rent commodity mechanics.

Do not build: a custom LLM, a blockchain, an operating system, a general database, a browser engine, a Docker replacement, a front-end framework, a generic social bot, a generic RAG wrapper. Build the layer that decides what may become real.
