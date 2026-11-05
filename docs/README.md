# Documentation index

Every document in `docs/` is listed once below with its role. Nothing has been
moved or deleted; this page only says what each file is and which one wins when
two overlap. Status words follow the Founder Intent Ledger vocabulary
(`docs/FOUNDER_INTENT_LEDGER.md`).

**New here?** Read, in order: `../README.md` → `ARCHITECTURE.md` →
`../CONTRIBUTING.md`. Agents additionally read `../AGENTS.md` and the five
founder documents in the first table.

## 1. Founder doctrine and operating order — binding

When documents conflict, earlier rows in this table govern later ones, and this
table governs every other section.

| Document | Role |
|---|---|
| `FOUNDER_EFFECT_COMPILER.md` | **Controlling interpretation rule** (INTENT-0030): preserve the effect, do not literalize the metaphor |
| `FOUNDER_INTENT_LEDGER.md` | Intent-record format, lifecycle states, traceability rule |
| `RECURSIVE_COLLABORATION_PROTOCOL.md` | Five review roles, mandatory alternatives, two upward passes, merge proof |
| `UNIIMENTE_FINAL_BUILD_ORDER.md` | Preservation and integration order; supersedes destructive simplification |
| `CANONICAL_EXECUTION_ORDER.md` | Dependency order of work; blocker and evidence discipline |
| `intent/` | Individual intent records (`INTENT-*.md`, `INTENT-*.json`) |
| `OPEN_SOURCE_STACK.md` | Open-source-first model and tool selection (INTENT-20260930) |

## 2. Architecture — explanation

| Document | Role |
|---|---|
| `ARCHITECTURE.md` | Pipeline, layer responsibilities, **codemap**, invariants, sealed artifacts |
| `UCL.md` | The constitutional language specification |
| `ADE1_GOVERNED_TRANSLATION.md` | Decision: ADE-1 accepted as a resilience reference, sovereign framing rejected |
| `ADE1_GOVERNED_RUNTIME.md` | How ADE-1 standing cognition is implemented (`egregore/`) |
| `FOUNDRY_OMNIMORPH_V1.md` | Advantage Foundry + OMNIMORPH design (integration candidate) |
| `OPEN_SOURCE_RESEARCH_LINE.md` | The local open-source research assembly (`foundry/research_line.py`) |

## 3. Plans and programs

| Document | Status | Note |
|---|---|---|
| `BUILD_ORDER.md` | historical plan | The original ten-phase, stage-gated plan. Phase exit criteria remain useful; **ordering is governed by §1** (`UNIIMENTE_FINAL_BUILD_ORDER.md`, `CANONICAL_EXECUTION_ORDER.md`) |
| `BACKCAST_GPS.md` | historical analysis (2026-07-19) | Backcast from the target state; source of the phase plan |
| `EGREGORE_V1_INTEGRATION_PROGRAM.md` | active program | Canonical ownership map and integration gates; manifest in `../integration/egregore-v1.yaml` |
| `REPOSITORY_RATIONALIZATION_PLAN.md` | experiment / adoption candidate | Cross-repository rationalization; SR-001 continuation |
| `TARGET_FORM_001.md` | research benchmark | Decisive developmental benchmark (`python -m developmental`) |
| `developmental/TARGET_FORM_002_SPEC.md` | research spec | Successor benchmark specification |
| `founder-loop-entry-gate.json` | gate record | Entry conditions for the persistent founder loop |

## 4. Reports, decisions and release evidence — records (do not edit; append)

| Document | What it records |
|---|---|
| `PHASE_ZERO_REPORT.md` | Phase Zero connection and capability-preservation state (2026-07-20) |
| `SR001_ADOPTION_DECISION.md` | Pre-adoption SR-001 review, retained with its original HOLD recommendation |
| `SR001_MERGE_STATUS.md` | SR-001 authorized adoption status (2026-09-10) |
| `OPEN_SOURCE_RESEARCH_LINE_REVIEW.md` | Founder-effect review of the research line (2026-09-30) |
| `decisions/` | Machine-readable decision records (e.g. `SR001-COMPAT-01.json`) |
| `open-source/` | Dated open-source repository surveys |
| `release/canonical-v1/` | Package 1: canonical core release candidate (start at `00-README.md`) |
| `release/package-3/` | Package 3: governed functional replacement (start at `README.md`) |
| `release/package-4/` | Package 4: stateful canonical replacement (`RESULTS.md`, `EVIDENCE_RECORD.json`) |
| `audits/` | Structural audits, e.g. `STRUCTURAL_AUDIT_2026-11-05.md` |

## 5. Collaboration records

| Document | What it records |
|---|---|
| `collaboration/RECONCILIATION-2026-08-22-KIMI.md` | Cross-model reconciliation record |
| `collaboration/ARCHITECTURE-OWNERSHIP-MAP.yaml` | **One canonical owner per concern** (proposed; founder ratification pending) — check here before adding a module |
| `collaboration/COLLAB-HANDOFF-KIMI-002.yaml` | Handoff record |
| `collaboration/deliberation-kimi-2026-08-22.json`, `intent-records-kimi-0027-0028.json`, `wave0-inventory-kernel-main.json` | Machine-readable deliberation, intent and inventory records |

## Where module documentation lives

Each top-level directory has its own `README.md` (purpose, contents,
consumers, and whether it is sealed). The root `README.md` "Layout" table links
them all; `tests/unit/test_repository_map.py` keeps that table complete.
