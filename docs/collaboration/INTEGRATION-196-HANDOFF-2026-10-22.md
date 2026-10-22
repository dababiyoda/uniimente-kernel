# Integration candidate 2 (#196): handoff, 2026-10-22

Draft PR #196: `claude/greg-full-machine-completion-whgiee` into #192's branch. Integration owner:
`session_01FBS4KNJR59nSbdGbxo8Mbx` (claim: board #96, comment 6331152598). It merges nothing to `main`. It also
signs, deploys, spends, publishes, contacts and activates nothing.

Completion boundary: BODY + ORGANS + MIND = GREG / UNIIMENTE. This record is an intermediate integration unit and
does not close it.

## Why this was the bottleneck

On 2026-10-22, `main` sat at #170 (`d64a6c93`) with about 100 open draft PRs stacked above it. No single tree held the
verified increments:

- #192 joined #178 and #184.
- Track B (#180–#189), the latest Mind (#179, #158), the portfolio chain (#187/#188/#191/#195) and Cortex 0.2.2 (#194)
  each lived on its own branch.

Neither the 15-step loop nor the founder-device acceptance could therefore run on the machine as built. Single
Bottleneck Metric for this unit: **verified open increments not contained in one CI-checked candidate**. At intake
that was 13 PRs, plus the deltas listed under Pending.

## Intake (pinned heads)

| Source | Head | Disposition | Commit |
|---|---|---|---|
| #192 (base) | `397a38e3` | base | — |
| #173 handoff doc | `4a7343d2` | merged, clean | `4f40ef60` |
| #195, which contains #187/#188/#191 | `0d5e0b12` | merged | `3547c03e` |
| #194 Cortex 0.2.2 | `c0a502f2` | merged | `af50537b` |
| #190 upward-ascent intent | `4ff2f044` | merged | `69692382` |
| #193 team entry | `2ccbbe2b` | merged | `85dd47b6` |
| Track B #189, which contains #180/#181/#183/#185/#186 | `93badaff` | resolving: 21 files, ~58 hunks, by coupled group, adversarial review per group | pending |
| #179 / #158 | `866d4770` / `c04b0f18` | after Track B. Trial: clean except the generated Mind evidence index, which its script regenerates | pending |
| #168 (contains #137's 3 later commits) | `0fd430f3` | after Track B. Trial: 12 conflicts in body, missions, workers, console, tribunal and asks | pending |

## Conflict decisions

| Seam | Decision | Both defenses kept |
|---|---|---|
| `greg/genesis.py` (#192 vs #195) | union of methods; `_attach` takes #192's signature | the goal formation-only rule is checked first (never attached for a goal; awaits the founder's CAPABILITY_ATTACH), then #192's rule that a cognition capability is attached only by the founder's own command |
| `scripts/ci/check_cortex_mutants.py` (#192 vs #194) | union of mutant groups; #194's parallel scratch-copy runner | 15 groups, 192 mutants, none dropped |
| entry files (#190, #193) | union, latest correction first | AGENTS.md no longer tells agents to stack on #137's branch; the board-named candidate replaces it, with #137 lineage kept |

## Defects found by joining (each fixed with a test that fails without the fix)

1. #195's portfolio-question test filtered compilation receipts by the `0.1` schema string. The joined compiler emits
   `0.2`, so the Mind's answer was invisible to the test. The test now filters by `compiler.SCHEMA`: the same
   exact-match assertion, bound to the compiler's own constant.
2. The founder runbook and installer told Alfonso to clone `claude/uniimente-greg-reconciliation-39syff` (#137),
   hundreds of commits behind. A device acceptance would have exercised old code. They now name
   `greg/chromebook/REVIEW_BRANCH`, and a drift guard fails on any other branch. The Mac runbook (`FIRST_MISSION.md`)
   still names `codex/one-greg-vepmc-convergence` (#122). It is held as the real overlapping task for the
   fresh-session coordination test (below).
3. `greg acceptance` did not say which code produced the evidence. It now reports `code` (commit, dirty), and
   `code_identified` passes only for a clean checkout of one named commit.
4. Discussion #89 is unreadable from cloud sessions: github.com returns 403 through the egress proxy, and the GitHub
   connector has no Discussion tool. The public REST API serves the same body without a credential. Verified 2026-10-22;
   the read path is now in AGENTS.md, CLAUDE.md and START_HERE.

## Observations recorded, not yet built

- **Constructed capabilities do not reach competence memory.** On this tree, a signed portfolio mission answered by
  the constructed `selection.budgeted` / `selection.closure` is appraised VERIFIED. The same holds when the Mind routes
  the question to the construction. Yet `settlement.measured_outcomes` credits only builtin cognitive methods and
  installed-package mechanisms, so the outcome settles nothing. Track B's settlement (verified failures, claim
  identity by signed params) auto-merges and does not change this. Value is limited while a construction is the only
  fit for its function. It matters as soon as two fits compete (e.g. MILP vs closure). Recorded as a seam for the
  15-step map (step 13).
- **Local-model baselines stay NOT_RUN.** This environment's network policy denies `huggingface.co`, `ollama.com` and
  GitHub release downloads.

## Validation bound to exact heads

| Head | Check | Result |
|---|---|---|
| `3547c03e` | portfolio chain, Genesis, cognition-Genesis and Mind-constructs-capability tests (py3.11, local) | 175 passed, 0 failed |
| `af50537b` | CI job 6 test set plus cognition missions (local) | 821 passed, 0 failed |
| `af50537b` | Canonical CI | jobs 2, 3, 4, 5, 7, 8 success (job 8: both whole-machine proofs against pinned organs); 1, 6 and 9 were still running when this was written |
| `ae29d16f` | acceptance, installer and doctor tests; supervised Chromebook rehearsal and VEPMC path, with supervisord on PATH (local) | 4 + 16 + 4 passed (15 passed + 4 skipped before supervisord was on PATH) |
| `85dd47b6` | collaboration receipt and developmental inheritance tests (local) | 72 passed |

Organs: DALEOBANKS `667439f`, WealthMachine `ec82b80` (CI pins, unchanged; neither organ moved its pinned code).

## Dispatched

- **§14 antifragility v3 (condition-specific competence):** assigned to `session_01GRT2jX7cQXwvMkn64ZgvLk`, the Track B
  owner, on board #96. Not yet acknowledged.

## Self-review

This is one agent working through five lenses. It is not independent review.

- **Builder:** every merge keeps both lineages' code paths. The only test edits bind an assertion to a constant or add
  coverage.
- **Adversary:**
  - The residual risk is Track B's 21-file resolution in core runtime. An independent reviewer per group checks it
    against both parents.
  - A second risk is #168's later commits touching the same files. That intake is serialized after Track B, not
    parallel.
- **Operator:**
  - Adopting #193's receipt workflow means every push to this PR needs a fresh receipt with the new head SHA. That
    cost is part of the pilot measurement.
  - Python 3.11 matches CI. Locally the cert-bundle variables are unset (as recorded in #192).
- **Beneficiary:** the founder now installs the candidate actually under review, and the acceptance names its commit.
- **Constitutional:** no authority path was added. #182, the integrity pins and the protected hashes are untouched.

**Pass 1:**
- The intake is serialized by conflict surface (small lineages first, then Track B, then #179/#158/#168).
- Every intake records its source head, so moving producer heads become pending deltas, not chased targets.

**Pass 2:**
- Attack 1: this is a second integration line beside #192. Answer: it is stacked on #192 as a child PR, not
  parallel. Closing #196 leaves #192 intact.
- Attack 2: Alfonso cannot review a 1000-commit stack. Answer: the review unit is this record's decision table, plus
  CI and acceptance on one head. Merge stays his decision.

## Pending

- Track B join and its review.
- #179/#158 (index regenerated by `scripts/build_mind_evidence_index.py`).
- #168.
- A full local suite on the joined head.
- CI on the joined head.
- The 15-step map on the joined head.
- The fresh-session coordination test.
- Device acceptance (founder).
- #182 (founder signature).

## Rollback

Close #196. #192 and every source branch are unchanged. Each merge commit reverts independently.
