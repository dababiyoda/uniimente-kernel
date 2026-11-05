# UNIIMENTE Kernel

A constitutionally governed runtime for AI agents, ventures, media properties, workflows, evidence, and capital.

**Models reason. Agents propose. Humans and policies authorize. The Kernel determines what may become real. Reality determines what was correct.**

## Agent entry — read this before architecture work

All AI/coding/research agents entering this repository must read:

1. `AGENTS.md`
2. `docs/FOUNDER_EFFECT_COMPILER.md`
3. `docs/FOUNDER_INTENT_LEDGER.md`
4. `docs/RECURSIVE_COLLABORATION_PROTOCOL.md`

The controlling founder correction is:

> **Preserve the intended effect. Do not literalize the metaphor. Search reality before inventing architecture.**

Alfonso's terms such as `egregore`, `morphogenesis`, `cells`, `tissues`, `organs`, `immune system`, `healing`, `regeneration`, `embodiment`, `Jarvis`, `omniscience`, and `immortality` are serious capability destinations and mechanism-discovery prompts unless he explicitly specifies a literal implementation. Their surface metaphors are not architectural mandates.

Canonical UNIIMENTE morphogenesis means **functional capability formation/reconfiguration in response to a verified discrepancy or CapabilityDeficit**. Existing biological/developmental and organizational-morphogenesis work remains valuable research and mechanism substrate, but it does not define the required final geometry.

Humans start with `CONTRIBUTING.md` (setup, commands, sealed artifacts) and `docs/README.md` (index of every document and which governs on conflict).

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

The single source of institutional truth for UNIIMENTE, Alfonso Lopez's constitutionally governed, human-sovereign artificial egregore. Every organ (DALEOBANKS, WealthMachineIntelligence, RailScout, future Venture Cells) consumes governance from here. No organ owns governance locally.

This repository contains no production secrets. It contains law, contracts, and registries.

## Layout

Every top-level directory is listed here; `tests/unit/test_repository_map.py`
fails if one is added without a row. Read `docs/ARCHITECTURE.md` for how the
pieces connect and `CONTRIBUTING.md` for how to work in them.

**Law and authority (data, not code).** Several of these files are byte-sealed; see "Sealed artifacts" in `docs/ARCHITECTURE.md`.

| Path | Contents |
|---|---|
| `/constitution` | The Constitution as executable UCL: purpose, rights, prohibitions, sovereignty hierarchy, amendment and shutdown policy |
| `/authority` | Authority matrix, legal principals, reserved matters (permanently non-delegable) |
| `/affect` | Functional affect policy: bounded machine control states, identity coherence, pathological-state tests |
| `/workflows` | Declarative institutional workflows: approval lifecycle, venture validation, incident response, shutdown recovery |
| `/contracts` | Versioned JSON Schemas shared by every organ (events, evidence, decisions, outcomes, grants, packets, charters, wire v1.1) |
| `/organs` | Organ manifests the Linker resolves (`*.manifest.yaml`) |
| `/integration` | Integration program manifests (e.g. Egregore v1 assembly) |

**The consequence path (code).**

| Path | Contents |
|---|---|
| `/compiler` | Layer 1 — UCL compiler: doctrine → deterministic policy decisions, relationship tuples, invariants, grant contract |
| `/identity` | Layer 2 — organ/agent/service registries (YAML) + executable machine passports |
| `/policy` | Layer 3 — policy engine + Consequence Gate: the sole path to external effects |
| `/provenance` | Layers 3+10 — Evidence Ledger, Commit Witness, Merkle proofs |
| `/events` | Layer 4 — event spine and durable workflows: typed events, idempotent inbox, mediated outbox, replay, kill-and-resume |
| `/adapters` | Contract-version adapters between organ wire formats; declare loss, additions and assumptions |
| `/linker` | Resolves typed cross-organ edges from organ manifests; reports unresolved fields instead of inventing them |
| `/common` | Shared mechanics only (canonical JSON, `sha256:` references, UTC clock); no policy, no authority |

**Governed capability, memory and evolution (code).**

| Path | Contents |
|---|---|
| `/capabilities` | Layer 5 — capability genomes with bounded authority envelopes; non-canonical capability router |
| `/embassy` | Layer 7 — foreign agents admitted as minimum-privilege guests; every request routed through the gate |
| `/memory` | Layer 8 — causal memory, outcome weighting, calibration, bounded functional affect |
| `/autonomy` | Layer 13 — evidence-earned A0–A8 autonomy levels; A9 reserved human sovereignty |
| `/closure` | Five orthogonal closures per module + Whole-Body Closure Controller; registries the verifier runs |
| `/evolution` | Strategy trees, spider-web audits, experiments, capsules, ClosureLoop, auto-cycle; frozen repair/migration experiments |
| `/loom` | Automation Loom: machine-authored, human-ratified (hash-bound) workflow patterns |
| `/twins` | Institutional Twins + Counterfactual Tribunal: hermetic forks whose verdicts recommend and never apply |
| `/capital` | Allocation waterfall, liquidity policy, concentration limits, regenerative treasury |
| `/egregore` | ADE-1 standing cognition: scheduled, bounded, evidence-bound deliberation that produces candidates only |

**Ventures, commerce and composition (generic extension candidates).**

| Path | Contents |
|---|---|
| `/business` | Business Genome compiler and the commercial loop (problem → buyer → offer → payment → delivery → outcome) |
| `/foundry` | Advantage Foundry: opportunity intake, tribunal, composition, pipeline, open-source research line |
| `/omnimorph` | Optional temporary-organization/capability-composition mechanism; produces `PROPOSED_NOT_EXECUTED` manifests |
| `/morphogenesis` | Bounded target-state and venture-cell control primitives (one lineage; not the definition of morphogenesis) |

**Research (sealed from consequence).**

| Path | Contents |
|---|---|
| `/developmental` | Biology-inspired mechanism research laboratory; not the canonical definition of morphogenesis |

**Specifications not yet built.**

| Path | Contents |
|---|---|
| `/sandbox` `/observability` | Kernel module specifications (build targets) |
| `/sdk-python` `/sdk-typescript` | Organ integration SDKs (build targets) |

**Verification, tooling and records.**

| Path | Contents |
|---|---|
| `/tests` | Executable suites (`tests/unit`, `tests/integration`), governance test specifications (YAML), preserved evidence (`tests/evidence`) |
| `/verifier` | Institutional verifier (V1–V5) and every recorded run under `verifier/runs/` |
| `/scripts` | CI guard scripts (`scripts/ci/`): schema references, authority singletons, sealed developmental work |
| `/tools` | Standalone operator tools (fail-closed offline test launcher) |
| `/deploy` | Local deployment recipes for the research line (compose, settings) |
| `/examples` | Example inputs and fixtures for runnable entry points |
| `/docs` | Founder doctrine, architecture, build orders, release and evidence records — start at `docs/README.md` |

## Build status

**Phase 1 — Consequence Integrity: executable and verified (2026-07-20).** One bounded action family (`draft.publish`) closes the full loop: Evidence → Policy → Authority → Commit Witness → Execution → Receipt → Reconciliation → Outcome, including 12 adversarial gate cases (revoked/expired/replayed grants, effect mismatch, budget overflow, identity lapse, executor explosion — all fail closed).

**Phase 2 — First Evolution Cycle: executable and verified (2026-07-20).** One complete machine-recorded improvement cycle beat its baseline: the `external_contact` evidence floor rose 0.70 → 0.75, eliminating weak-evidence admissions (2 → 0) with zero new good refusals, verified by formal proof, decision RETAIN, capsule preserved on the ledger with all 10 rejected branches and their revival evidence. Organs: StrategyTree (11 branch kinds, 12 required fields), SpiderWebAudit (8 sides, 4 super-nodes, 11 completeness requirements, decorative removal), ExperimentSpec (irreversible experiments refuse to compile), EvolutionCapsule, 7-level verifier hierarchy (levels 6–7 hypothesis-only, cannot authorize promotion), RetainRegressKill.

**Phase 3 — Fast Capability Evolution + Layers 4/10/13: executable and verified (2026-07-20).** The improvement cycle now runs at machine pace: branch generation across all 11 kinds → isolated testing → failure analysis → baseline comparison → champion proposed to the ClosureLoop. Hard bounds: hypothesis-only verifiers are refused before any test runs (the cycle may not self-authorize); structural doctrinal refusals halt the cycle (it never routes around doctrine); when nothing beats baseline, do_nothing stands. Layer 4 event spine: typed events (identity, legal principal, causal parent, policy version), idempotent inbox, mediated outbox, replay, durable workflows — killed mid-flight, resumed from checkpoint with no manual restatement, retries, approval waits, reverse-order compensation. Layer 13 autonomy ladder A0–A8: weakest-link promotion across 10 criteria, missing outcome records block promotion, severe failure collapses autonomy to A0 immediately (A9 reserved, never granted). Layer 10 Merkle proofs: checkpointed roots anchor the ledger; any record provable in O(log n) without trusting the host.

**Phase 4 — Automation Loom + Phase 5 Institutional Twins + Layers 5/7/8: executable and verified (2026-07-20).** The Loom weaves the institution's own routines: workflow patterns authored as data by the machine, ratified by the human (hash-bound — any edit invalidates ratification), executed on the durable spine; all three canonical workflows (daily reconciliation, evidence-floor review, venture validation gate) run end-to-end, including mid-flight kill → resume. Twins rehearse change in hermetic forks; the Counterfactual Tribunal renders dominance verdicts over frozen, quality-labeled corpora — harm increases can never be named superior, and verdicts recommend but never apply. Layer 5 capability genomes bound every organelle's authority envelope; the Layer 7 Embassy admits foreign agents as zero-budget, TTL-clamped guests whose every request routes through the gate; Layer 8 causal memory reconstructs precedent (outcome→receipt→witness), weights outcomes by verification strength, calibrates confidence against reality, and bounds functional affect (attributable triggers, ceilings, decay, descending authority — structurally unable to change facts, create evidence, raise authority, override law, resist shutdown, or authorize irreversible action).

Current evidence is whatever the commands produce, not a number written here: `make test` (full suite), `make verify` (institutional verifier V1–V5; every run recorded under `verifier/runs/`), `make ci` (every check CI runs). Test counts in the phase notes above are historical at their dates. These are internal evidence for the stated versions, not proof that the full egregore is integrated or operational in the real world.

Next work must follow `docs/CANONICAL_EXECUTION_ORDER.md` and the active repository evidence, not stale phase labels alone.

## The doctrine

Own the control plane. Adopt or rent commodity mechanics.

**Effect compiler:** founder aspiration → observable effect → existing mechanism search → residual CapabilityDeficit → acquire/compose/adapt/build → sandbox/test → verify → attach under authority → resume original goal → measure reality.

Do not build a custom LLM, blockchain, operating system, general database, browser engine, Docker replacement, front-end framework, generic social bot, generic RAG wrapper, digital cell substrate, or organizational hierarchy merely because a source metaphor suggests one. Build or own the layer only when doing so creates a verified control, proof, continuity, composition, security, economic, or strategic advantage.

The metaphor is allowed to be extraordinary. The mechanism must be real.
