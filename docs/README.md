# Documentation index

Every top-level file in `docs/` is listed once below with its role. Nothing has
been moved or renamed: this page says what each file is and where to go next.
`tests/unit/test_repository_map.py` fails if a new top-level doc is added without
a row here.

**Reading order is not defined here.** It is defined once, in
[AGENTS.md § Canonical reading order](../AGENTS.md#canonical-reading-order); every
other entry file defers to it. This index is for finding a document, not for
deciding what to read first.

**To find any document or record**, use [`CATALOG.md`](CATALOG.md): every file under
`docs/` once, by area, kind and date, without moving anything. **To find any branch**
and whether its work is finished, use the newest
`collaboration/BRANCH-CATALOG-*.md`.

## 1. Founder intent and doctrine (binding)

| Document | Role |
|---|---|
| `FOUNDER_EFFECT_COMPILER.md` | Controlling interpretation rule (INTENT-0030): preserve the effect, do not literalize the metaphor |
| `FOUNDER_INTENT_LEDGER.md` | Every founder intent, newest first, with lifecycle state |
| `intent/` | Individual intent records (`INTENT-*.json`/`.md`) and verbatim sources (`intent/sources/`) |
| `RECURSIVE_COLLABORATION_PROTOCOL.md` | Five review roles, alternatives, exactly two strengthening passes |
| `UNIIMENTE_FINAL_BUILD_ORDER.md` | Preservation and integration order (with its 2026-09-11 and 2026-09-30 corrections at the top) |
| `CANONICAL_EXECUTION_ORDER.md` | Dependency order of work; blocker and evidence discipline; Spider-Web compounding rule |
| `OPEN_SOURCE_STACK.md` | Open-source-first model and tool selection |

## 2. How contributors work (procedure)

| Document | Role |
|---|---|
| `PROJECT_COGNITION_SOP.md` | Mandatory agent procedure: context reconstruction, product delta, handoff |
| `PROJECT_COGNITION_CONTINUITY.md` | Source ingestion, context checksum, anti-context-loss test |
| `PROJECT_SOURCE_CENSUS_2026-09-26.md` | Inventory of founder Project sources (dated) |
| `PROJECT_COGNITION_PROPAGATION_RECEIPT_2026-09-26.md` | Record of where the SOP was propagated (dated) |
| `CATALOG.md` | Generated catalog of every document and record, by area, kind and date (`scripts/docs_catalog.py`) |
| `REVIEW_CADENCE.md` | The recurring review: what runs per PR, weekly, per five PRs, monthly, quarterly |
| `DISCUSSIONS_SEED.md` | Seed text for the pinned founder Discussion #89 |
| `collaboration/` | Claims, handoffs, deliberations, reconciliations; **start at `collaboration/INDEX.md`** (team entry: `collaboration/START_HERE.md`) |

## 3. Architecture (explanation)

| Document | Role |
|---|---|
| `ARCHITECTURE.md` | Kernel pipeline, layer responsibilities and the **current module map** (GREG, cortex, governance, acceptance, foundry, egregore) |
| `UCL.md` | The constitutional language |
| `GOAL_GRAVITY.md` | Goal Gravity: authorized goals as attractors for perception and preparation |
| `ADE1_GOVERNED_TRANSLATION.md`, `ADE1_GOVERNED_RUNTIME.md` | ADE-1 standing cognition: the decision and its implementation (`egregore/`) |
| `FOUNDRY_OMNIMORPH_V1.md` | Advantage Foundry + OMNIMORPH design (integration candidate) |
| `OPEN_SOURCE_RESEARCH_LINE.md`, `OPEN_SOURCE_RESEARCH_LINE_REVIEW.md` | The local open-source research assembly and its founder-effect review |
| `cortex/`, `mechanisms/`, `developmental/` | Cortex design records, Mechanism Cards, developmental research specs |

## 4. Plans and programs

| Document | Status | Note |
|---|---|---|
| `EGREGORE_V1_INTEGRATION_PROGRAM.md` | active program | Canonical ownership map and gates |
| `BACKCAST_GPS.md` | historical analysis (2026-07-19) | Origin of the phase plan; current path is `greg/path.json` (`greg path`) |
| `BUILD_ORDER.md` | historical plan | Original ten phases; ordering is governed by §1's build orders |
| `REPOSITORY_RATIONALIZATION_PLAN.md` | experiment / adoption record | SR-001 continuation |
| `TARGET_FORM_001.md` | research benchmark | `python -m developmental` |
| `opus-maximus/` | active deliverables | OPUS MAXIMUS directive deliverables and next-wave horizons |
| `founder-loop-entry-gate.json` | gate record | Founder-loop entry conditions |

## 5. Records (append, do not edit)

| Document | What it records |
|---|---|
| `PHASE_ZERO_REPORT.md` | Phase Zero state, 2026-07-20 |
| `SR001_ADOPTION_DECISION.md`, `SR001_MERGE_STATUS.md` | SR-001 review (with its original HOLD) and authorized adoption |
| `GREG_LOCAL_START.md` | **Archived** synthetic-authority console runbook (directive §76); kept as lineage |
| `decisions/`, `deliberations/` | ADRs and founder rulings |
| `evidence/` | Frozen and dated evidence bundles (`docs/evidence/<topic>/<date>/README.md`) |
| `open-source/`, `release/` | Dated open-source surveys; release packages |
