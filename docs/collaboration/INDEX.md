# docs/collaboration — how to read this folder

This folder holds about 170 collaboration records from many sessions. Most are
**dated records of a moment**, not current truth. This index sorts them by kind
so a newcomer can tell live procedure from history. It lists patterns, not every
file, so it does not need regenerating after each merge. The per-file listing is
[`../CATALOG.md`](../CATALOG.md); the state of every branch is the newest
`BRANCH-CATALOG-*.md`.

**Current coordination truth is not in this folder.** Read the live work board
(issue #96, newest comments first), the integration PR it names (today #196), and
`python -m greg path` for the acceptance node and `python -m greg path --build`
for the separate engineering frontier. The founder-device acceptance does not block
independent developmental engineering (the October 30 correction). Read the
[current full-machine route](../BACKCAST_GPS.md#current-full-machine-route) for
N0–N10, the Mind path, Foundry obligations and exact founder-source pointers.
A dated file here is evidence of what was true on that date.

## Live procedure (read when you contribute)

| File | What it is |
|---|---|
| `START_HERE.md` | Team entry, claims, the six SOPs. Note: its line pinning the SOP to commit `eb795c7d` "while those files are absent from main" is provenance; both files are present in this tree at `docs/PROJECT_COGNITION_SOP.md` and `docs/PROJECT_COGNITION_CONTINUITY.md`. |
| `RECEIPT.md` | The version-2 PR receipt (checked by `.github/workflows/collaboration-receipt.yml`) |
| `ROLLOUT.md`, `VALIDATION.md` | Repository routing/adoption, and the measured results of the collaboration process |
| `TEAM-ENTRY-DECISION-2026-10-21.md` | Why the team-entry process exists, with its two-pass decision |
| `CONTEXT-ROUTE-2026-11-12.md` | Dated inspection, source access, overlap and propagation receipt for the complete context route; adoption remains separately verified |

## Live registries (machine-read; edit only through their owning process)

| File | Read by |
|---|---|
| `RELEASE-EXCLUSIONS.json` | `scripts/check_release_exclusions.py` |
| `DEVELOPMENTAL-INHERITANCE-2026-09-30.json` | `tests/unit/test_developmental_inheritance.py`; the ten placement classes for `greg/path.json` |
| `ARCHITECTURE-OWNERSHIP-MAP.yaml` | humans; **PROPOSED** 2026-08-22, never ratified, and it predates `greg/`, `cortex/`, `governance/` and `acceptance/`. Use `docs/ARCHITECTURE.md` § Current module map until it is updated |

## Dated records, by kind (history: append, never rewrite)

| Pattern | Kind | Current when |
|---|---|---|
| `deliberation-*-YYYYMMDD.json`, `DELIBERATION-*` | two-pass decision records (34) | for the decision named, until a linked newer deliberation |
| `*-HANDOFF-*`, `HANDOFF-*`, `REHEARSAL-HANDOFF.md` | session handoffs | until the next handoff on the same task (check #96) |
| `*-RECONCILIATION-*`, `*-CONVERGENCE-*`, `*-SUPERSESSION.md`, `PR1*-*` | branch and lineage reconciliations | as lineage only |
| `FOUNDER-DECISIONS-*`, `FOUNDER-ACTIONS-*` | founder-pending decisions and actions as of a date | until the founder answers (check the ledger) |
| `MIND-*`, `GREG-*`, `GOAL-CHASE-*`, `WHOLE-MACHINE-*`, `ONE-*` | product-line state reports | as of their date |
| `*-AUDIT-*`, `*-COVERAGE-*`, `LINEAGE-*`, `SOURCE-COVERAGE-*`, `REPOSITORY-*`, `wave0-*` | inventories and audits | as of their date |
| `DIGEST-RULE-CONSOLIDATION-*`, `LEDGER-DEDUP-*`, `FINDING-*` | duplication and defect findings | until their follow-up PRs land |
| `BRANCH-CATALOG-*` | every remote branch: finished (on the line), open PR, parked or unclaimed (`scripts/branch_catalog.py`) | the newest one; regenerated weekly |
| `COMPOSE-REHEARSAL-*` | what merging a set of heads breaks in behaviour, and what causes it (`scripts/compose_rehearsal.py`) | as of its date and the line head it names |
| `CONTRIBUTOR-PAIN-POINTS-*` | contributor friction register | the newest one; re-measured by the monthly review (`docs/REVIEW_CADENCE.md`) |

Sub-folders: `reviews/` (independent review reports), `lineage-archive/`
(preserved superseded sources), `goal-chase-*-evidence/` (evidence bundles).

Undated files (`GOAL-CHASE-V0.md`, `OPUS-RECONCILIATION.md`, `RECEIPT.md`, …)
take the date of their last commit: `git log -1 --format=%cs -- <file>`.

To list the most recently changed records: `git log --since=14.days --name-only --format= -- docs/collaboration | sort -u`.
