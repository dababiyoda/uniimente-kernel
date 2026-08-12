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
| `/provenance` | Evidence Ledger + Commit Witness + Merkle proofs (Layers 3+10): hash-chained, HMAC-signed, checkpoint-anchored institutional memory |
| `/closure` | Orthogonal loop closure: five closures per module + Whole-Body Closure Controller (13 loops) |
| `/evolution` | Recursive self-improvement: strategy trees, spider-web audits, experiments, capsules, the ClosureLoop, and the Phase 3 machine-paced auto-cycle |
| `/events` | Event spine + durable workflows (Layer 4): typed events, idempotent inbox, mediated outbox, replay, kill-and-resume workflows |
| `/autonomy` | Autonomy licensing (Layer 13): evidence-earned A0–A8 levels on exact 9-dimension tuples; A9 reserved human sovereignty |
| `/loom` | Automation Loom (Phase 4): machine-authored, human-ratified workflow patterns woven onto the durable spine |
| `/twins` | Institutional Twins + Counterfactual Tribunal (Phase 5): hermetic counterfactual forks; dominance-verdict hearings that recommend and never apply |
| `/capabilities` | Capability genomes (Layer 5): portable organelles with bounded authority envelopes |
| `/embassy` | Agent Embassy (Layer 7): foreign agents admitted as minimum-privilege guests; every request routed through the gate |
| `/memory` | Causal memory + functional affect (Layer 8): precedent, outcome weighting, calibration, bounded control states |
| `/blueprint` | Opus Maximus hardening ladder over the 55-technology arsenal: six rungs, a separate reality axis, an evidence binder that resolves every claim against the real tree, and a critical-path compiler (`python -m blueprint`) |
| `/discovery` | Capability Discovery Service (§4.10): read-only directory over organ manifests. Discovery does not grant access |
| `/knowledge` | Institutional Knowledge Graph (§4.15): provenance-aware projection; a node with no provenance is refused |
| `/routing` | Decision Router (§4.14): ranks competing implementations, records every decision, invokes nothing |
| `/handoff` | Frozen Claude/ChatGPT handoff bundle: contract, schemas, acceptance vectors, bundle manifest and two-commit seal (`python -m handoff.conform`) |
| `/organs` | Organ manifests. Five published; `identity/organ-registry.yaml` separately registers eight identities — a manifest is discovery, never identity |
| `/sandbox` `/observability` | Kernel module specifications (build targets) |
| `/sdk-python` `/sdk-typescript` | Organ integration SDKs (build targets) |
| `/docs` | Architecture, build order, Backcast GPS plan, UCL language specification |

## Build status

**Phase 1 — Consequence Integrity: executable and verified (2026-07-20).** One bounded action family (`draft.publish`) closes the full loop: Evidence → Policy → Authority → Commit Witness → Execution → Receipt → Reconciliation → Outcome, including 12 adversarial gate cases (revoked/expired/replayed grants, effect mismatch, budget overflow, identity lapse, executor explosion — all fail closed).

**Phase 2 — First Evolution Cycle: executable and verified (2026-07-20).** One complete machine-recorded improvement cycle beat its baseline: the `external_contact` evidence floor rose 0.70 → 0.75, eliminating weak-evidence admissions (2 → 0) with zero new good refusals, verified by formal proof, decision RETAIN, capsule preserved on the ledger with all 10 rejected branches and their revival evidence. Organs: StrategyTree (11 branch kinds, 12 required fields), SpiderWebAudit (8 sides, 4 super-nodes, 11 completeness requirements, decorative removal), ExperimentSpec (irreversible experiments refuse to compile), EvolutionCapsule, 7-level verifier hierarchy (levels 6–7 hypothesis-only, cannot authorize promotion), RetainRegressKill.

**Phase 3 — Fast Capability Evolution + Layers 4/10/13: executable and verified (2026-07-20).** The improvement cycle now runs at machine pace: branch generation across all 11 kinds → isolated testing → failure analysis → baseline comparison → champion proposed to the ClosureLoop. Hard bounds: hypothesis-only verifiers are refused before any test runs (the cycle may not self-authorize); structural doctrinal refusals halt the cycle (it never routes around doctrine); when nothing beats baseline, do_nothing stands. Layer 4 event spine: typed events (identity, legal principal, causal parent, policy version), idempotent inbox, mediated outbox, replay, durable workflows — killed mid-flight, resumed from checkpoint with no manual restatement, retries, approval waits, reverse-order compensation. Layer 13 autonomy ladder A0–A8: weakest-link promotion across 10 criteria, missing outcome records block promotion, severe failure collapses autonomy to A0 immediately (A9 reserved, never granted). Layer 10 Merkle proofs: checkpointed roots anchor the ledger; any record provable in O(log n) without trusting the host.

**Phase 4 — Automation Loom + Phase 5 Institutional Twins + Layers 5/7/8: executable and verified (2026-07-20).** The Loom weaves the institution's own routines: workflow patterns authored as data by the machine, ratified by the human (hash-bound — any edit invalidates ratification), executed on the durable spine; all three canonical workflows (daily reconciliation, evidence-floor review, venture validation gate) run end-to-end, including mid-flight kill → resume. Twins rehearse change in hermetic forks; the Counterfactual Tribunal renders dominance verdicts over frozen, quality-labeled corpora — harm increases can never be named superior, and verdicts recommend but never apply. Layer 5 capability genomes bound every organelle's authority envelope; the Layer 7 Embassy admits foreign agents as zero-budget, TTL-clamped guests whose every request routes through the gate; Layer 8 causal memory reconstructs precedent (outcome→receipt→witness), weights outcomes by verification strength, calibrates confidence against reality, and bounds functional affect (attributable triggers, ceilings, decay, descending authority — structurally unable to change facts, create evidence, raise authority, override law, resist shutdown, or authorize irreversible action).

172 unit tests green. 13 modules × 5 orthogonal closures green. Verifier: `python3 verifier/v2/verify.py` (V2–V5 green; every run recorded under `verifier/runs/`).

Next: Phase 6 (first AI influencer company + Rabbit Hole Engine, WealthMachineIntelligence) and organ contract consumption (issue #5; DALEOBANKS #57). See `docs/BUILD_ORDER.md` and `docs/BACKCAST_GPS.md` for the stage-gated plan with kill criteria.

**Opus Maximus blueprint — executable, evidence-bound (2026-08-12).** The
55-technology Foundry arsenal stopped being a description and became an instrument.
Every technology now carries a rung the evidence actually supports
(`BLUEPRINT → SKETCHED → BUILT → EXERCISED → PROVEN → HARDENED`) and, separately, a
reality (`BLUEPRINT_ONLY | SIMULATED | IMPLEMENTED`). A rung claim whose evidence does
not resolve against the real tree is refused, not warned about. `python -m blueprint`
prints the ladder, the unblocked build frontier ranked by leverage, and, for everything
blocked, the exact dependency holding it down. **Nothing stands at HARDENED**: that rung
requires a reconciled external outcome and the institution has zero. Three frontier
components landed with it — Capability Discovery (#27), the Institutional Knowledge
Graph (#18) and the Decision Router (#25) — each authority-free by AST assertion, each
registered for five-closure verification. Technology #25 is **not closed**: a second
router exists in draft PR #70 whose `resolve()` invokes a provider, and naming the
canonical selector is a founder decision.

## The doctrine

Own the control plane. Adopt or rent commodity mechanics.

Do not build: a custom LLM, a blockchain, an operating system, a general database, a browser engine, a Docker replacement, a front-end framework, a generic social bot, a generic RAG wrapper. Build the layer that decides what may become real.
