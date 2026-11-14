# Review cadence: keeping the repository understandable

Status: **active procedure, draft until adopted** (`INTENT-20261105-REGULAR-REVIEW`).
It creates no authority. Every step reads, measures or proposes. Changes still
go through a claim on board #96, a draft PR and the usual review.

The founder asked for "a regular review process to maintain the project's
integrity and adapt to evolving standards" (2026-11-05). This file builds that
process out of mechanisms the repository already has, and adds only what was
missing:

- SOP-06 (`docs/collaboration/START_HERE.md`) defined the right metrics but
  recorded "Baseline is NOT_MEASURED" and "No recurring job is enabled".
- `RECURSIVE_COLLABORATION_PROTOCOL.md` §6 asks for a periodic self-audit but
  gives it no trigger.

## The five rhythms

| Rhythm | What runs | Who acts on it | Output |
|---|---|---|---|
| **Every change** | Canonical CI; the receipt check; `tests/unit/test_repository_map.py` and `tests/unit/test_import_layering.py`, which are part of the normal suite | the PR author | a green PR, or a fix |
| **Weekly (automatic)** | `.github/workflows/repository-review.yml`, Mondays 06:17 UTC: `scripts/repo_review.py` plus PR-flow proxies | the integration owner, at the next intake batch | job summary and a 90-day artifact. **Nothing is posted and nothing fails a PR.** |
| **Every five completed coordinated PRs** (SOP-06's existing trigger) | SOP-06's five measures, using the weekly report's proxies as the starting point | the maintaining reviewer | one line in `docs/collaboration/VALIDATION.md`, plus a keep/simplify decision |
| **Monthly** | contributor friction review: new `contributor-friction` issues, replies on board #96 and the open rows of the newest `docs/collaboration/CONTRIBUTOR-PAIN-POINTS-*.md` | any session that claims it on #96 | a new dated register that keeps the old one; the top unowned item gets a claim or a founder ask |
| **Quarterly** | standards refresh: re-check the practices table below against their current sources and against what contributors report | a claiming session; Alfonso decides any change to obligations | a dated note: adopt, defer or reject each practice, with two passes when material |

The weekly workflow runs only from the default branch, as GitHub requires for
scheduled workflows. It therefore starts once the integration line reaches
`main`, a founder merge. Until then, run `python scripts/repo_review.py
--github dababiyoda/uniimente-kernel` at intake.

## What the weekly report contains

`python scripts/repo_review.py` (add `--json` for machine use, `--check` to exit
non-zero):

1. **Map integrity:**
   - every top-level directory has a README and a README layout row;
   - `docs/README.md` lists every top-level doc;
   - every entry file defers to the canonical reading order in `AGENTS.md`;
   - the PR template pair is marked.
2. **Layering ratchets:**
   - no new two-way package dependency;
   - no new import out of the published boundary distribution.

   The tables are shrink-only.
3. **Mutation-gate liveness.** Every literal anchor in `scripts/ci/check_*mutant*.py`
   must still occur in its target file. A stale anchor is a hard finding. An anchor
   at several sites is advisory. A gate whose anchors are not written as literals is
   not read: its own run in CI is what reports `STALE`. Every gate must be named in
   some workflow, except the gates on `KEPT_UNWIRED_GATES`; that list is compared with
   the tree, not with a base, so `tests/unit/test_repo_health_gates.py` pins its contents.
   On the tree before commit `5ad39868`, this check names the anchor that CI job 6
   reported STALE, in about 3 s instead of after a CI run.
4. **Lint trend (`--lint`):** a ruff F/E9 finding count by rule. A trend, never a gate.
5. **Catalogs:** `scripts/branch_catalog.py` classifies every branch (finished on
   the line, open PR, merged elsewhere, closed, or commits no PR carries) as a
   weekly artifact, with an **intake queue** of unfinished branches that merge into
   the line cleanly today (`git merge-tree`, in memory; nothing is merged); `scripts/docs_catalog.py --check` reports whether
   `docs/CATALOG.md` is stale. Neither gates a PR: a generated file that every PR
   must regenerate conflicts between parallel PRs (pain points P-1, P-3). The
   integrator regenerates `docs/CATALOG.md` at intake, and the monthly review
   commits a dated branch snapshot and asks the owners of `NO_PR` branches to
   claim, fold in or park them.
6. **Duplicate function bodies:** function bodies of 10+ lines repeated across files,
   counting renamed copies as one shape. A trend, never a gate: some copies are
   deliberate (frozen scripts, organs that must not import each other).
7. **Size profile:** the largest files and how many exceed 1,500 lines. This is
   a trend, not a rule.
8. **PR-flow proxies (SOP-06), when given `--github`:**
   - open PRs and drafts, and their base branches;
   - receipt coverage of recently closed PRs;
   - how many recently closed PRs mention rework words (stale, superseded,
     duplicate, conflict, re-record).

   These are **proxies**. A receipt block is a declaration, not a verified
   handoff, and a word count is not a measure of rework.

The structural rules in items 1–3 are the same functions the unit tests call,
so the weekly report and a PR cannot disagree about a rule.

## Practices adopted and their sources

| Practice | Source project | Where it lives here |
|---|---|---|
| A short architecture codemap: "where is the thing that does X?" | rust-analyzer; matklad, *ARCHITECTURE.md* (2021) | `docs/ARCHITECTURE.md` § Current module map |
| Docs separated by purpose, with one index | Diátaxis (adopted by Canonical/Ubuntu, Django) | `docs/README.md`, `docs/collaboration/INDEX.md` |
| One agent entry contract that other files defer to | the AGENTS.md convention | `AGENTS.md` § Canonical reading order |
| Import-boundary rules enforced by tests | import-linter (Python), Kubernetes `import-boss` | `tests/unit/test_import_layering.py` |
| Shrink-only ratchets with a stated reason per exception | this repository: #246, #254 | `KEPT_*` tables in `scripts/repo_review.py` |
| Scheduled, read-only repository health report | OpenSSF Scorecard's scheduled action | `.github/workflows/repository-review.yml` |
| Structured friction intake | GitHub issue forms | `.github/ISSUE_TEMPLATE/contributor-friction.yml` |

Each quarter, re-check each row against its source. A practice that stops
helping is regressed in the same table, with its reason.

## Recursive application and kill criteria

This cadence applies `RECURSIVE_COLLABORATION_PROTOCOL.md` §6 to itself.

- **Keep it** while it catches drift or reduces stale-context rework.
- **Simplify it** if two consecutive monthly reviews find nothing actionable
  and no friction is reported: drop to the weekly report plus a quarterly
  review.
- **Kill a rhythm** whose output nobody acted on for a quarter, and record that
  here.
- A larger document count is not progress (SOP-06).
