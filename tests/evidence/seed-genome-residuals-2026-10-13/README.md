# Seed Genome residuals — 2026-10-13

The founder re-issued the Seed Genome build directive on 2026-10-13. Its body is byte-identical to the
preserved text, plus the opening line "Build this prompt meet and exceed all in this prompt:"
([lineage](../../../docs/intent/sources/GREG-SEED-GENOME-DIRECTIVE-REISSUE-2026-10-13-source.md)). The
directive's own requirement map (`docs/cortex/SEED_GENOME_REQUIREMENTS.json`) records a residual for each
section. Each claimed residual was checked against the code on `5c8dd23` plus #161 before anything was
built:

| Section | Recorded residual | Checked against code | Done here |
|---|---|---|---|
| §9 | selective-disclosure evidence package missing | no implementation anywhere | built |
| §5 | characterization harness | a static dictionary of descriptive strings, no measurement | built |
| §12 | decision-specific VOI not wired | `budget.optional_step` exists, but no runtime path calls it; the compile path handed its `latency_budget` to every inner run whole | built in the repeat of 2026-10-14 (below); first deferred, wrongly, because the frozen evaluations pin `cortex.py` |
| §15 | 23 mandatory adversarial cases | covered (17 suite families plus 6 system-level tests), but references were checked only to file level | each reference now resolves to its test node |
| §7, §13 | verifier certificates, legitimacy | fixed in #161 | — |

## §9: Selective-disclosure evidence packages (`greg/cognition/disclosure.py`)

**What it does.** It builds a package an outside actor can check, from GREG's retained receipts:

- **Selective revelation:** every receipt field is committed as an RFC 9901 salted-hash disclosure (128-bit
  salts, decoy digests). The founder chooses which fields to reveal. The default reveals the claim's type,
  status, verdict, dissent and limits, and withholds the problem id, inputs, outputs, proof artifacts and
  evidence pointers.
- **No cherry-picking:** every other retained receipt with the same input is included. Disagreements are
  flagged without revealing their values.
- **Custody:** each item's record hash and sequence number, the ledger head, the chain check (a broken chain
  issues nothing), and the RFC 3161 anchoring state.
- **Actions and remedies:** an authorized-action reference must resolve to a retained record. A remedy is
  labelled as a request, not a finding.
- **Institutional responses** (accepted, partially accepted, disputed, declined, no response) are appended as
  separate journal records, with grounds drawn from data, model, jurisdiction, completeness, relevance and
  other. They grant nothing and never edit the package.

**Interface:**
- `greg cognition package --mission ID --recipient R --purpose P [--remedy T] [--reveal FIELD] --out DIR` is a
  read-only export. It writes `holder.json` (mode 0600, holds the salts, stays with the body) and
  `presentation.json` (the shareable view). Nothing is sent.
- `greg cognition verify-package presentation.json` is the recipient's check. It needs no GREG state, exits 0
  when every revealed value matches its commitment, and exits 1 otherwise.

**What it proves, and what it does not.** It proves that the revealed values match the package's own
commitments. It does not prove:

- **who issued it:** the package is unsigned, because GREG holds no issuer key, so attribution rests on the
  channel it arrived through;
- **ledger inclusion:** GREG's ledger is a linear hash chain whose record hashes cover whole payloads, so showing
  that a record is in it takes the ledger records themselves. A witness bundle only shows that a presented
  ledger was not rewritten after anchoring;
- **factual truth, legitimacy or acceptance.**

The package carries these limits, and the recipient-side check reports its own copy of them, so a package
cannot shorten the list. An earlier draft of this README, and of the package text, said inclusion was checkable
"with the ledger or a witness bundle" and called the package's guarantee "attribution". Both overstated it and
were corrected in a later commit on this PR.

**Evidence:**
- `cli-package.log`: the real CLI on a real body run (an optimization mission). The package verifies, and a
  presentation whose remedy text was edited afterwards exits 1.
- `example-presentation.json`: the shareable output. The holder file is excluded because it holds salts.
- The digest rule reproduces RFC 9901's worked example disclosure (`jsu9yVulwQQlhFlM_3JlzMaSFzglhQG0DpfayQwLUK4`).

## §5: Characterization harness (`greg/cognition/characterize.py`)

Measured through `reason()` on native synthetic workloads whose answers are known by construction
(`characterization.json`; Python 3.11.15, OR-Tools 9.15.6755, Z3 5.1.0.0):

| Family | Available | p50 latency (s) | Lies refuted [Wilson 95%] | Largest correct size (ladder) | Invariant under rename/reorder | Cross-checks |
|---|---|---|---|---|---|---|
| exact | yes | 0.25 | 3/3 [0.44, 1.0] | 16 terms (64 abstains) | 3/3 | — |
| estimation | yes | 0.26 | 4/4 [0.51, 1.0] | 16 factors (whole ladder) | 4/4 | — |
| formal | yes | 0.28 | 4/4 [0.51, 1.0] | 64 variables (whole ladder) | 4/4 | — |
| optimization | yes | 0.68 | 4/4 [0.51, 1.0] | 64 variables (whole ladder) | 4/4 | optimality_cross_engine |
| graph | **no** (not attached on the default registry) | — | — | — | — | — |
| causal | yes | 0.23 | 4/4 [0.51, 1.0] | 256 samples per arm (whole ladder) | 4/4 | — |

**How to read this:**
- **Small samples:** the samples are small, so the intervals are wide. A 100% refutation rate on 4 lies is a
  lower bound of about 0.51, not proof of perfection.
- **Corruption model:** a lie changes the answer's primary field and mirrors the change into the artifact, so
  it is self-consistent. Other lies are possible.
- **Not applicable:** memory depth, persistence, prediction horizon, adaptability, cooperation and
  higher-scale coherence are declared not applicable for single stateless families, each with the place
  where its evidence lives.
- **Sensitivity:** a verifier that accepts everything shows up as 0 refuted. The test suite checks this, and a
  mutant that bypasses the verifier is caught.

## §12: Thinking budget on the compile path (`greg/cognition/budget.py`)

Added when the founder repeated the directive on 2026-10-14
([lineage](../../../docs/intent/sources/GREG-SEED-GENOME-DIRECTIVE-REISSUE-2026-10-13-source.md)). The first round
deferred §12 because the frozen evaluations pin `cortex.py`. That reason was wrong: the #158 lineage's P6 v3 ran
in a clean worktree at its freeze commit `5acda2c`, as its v1 and v2 did, so changing `cortex.py` on a branch alters
no recorded result.

**Defect reproduced first** (`budget-reproduction.log`): on `8ad86ca`, a compile request with a declared 10 s
`latency_budget` handed the full 10 s to each of its four inner runs, the answer and three sensitivity
re-runs. That is 40 s for a 10 s budget, and up to six times the budget when a premises check and a fourth input
also run. No run weighed whether it fitted, no stop reason was kept, and cortex receipts carried a compute
ceiling, not a measurement.

**What runs now:**
- **One budget per decision.** `budget.Controller` holds the declared `latency_budget`, or a labelled 20 s default,
  for the whole compile. Every inner run gets only what remains, capped at 30 s, and keeps its own mandatory
  verification reserve (the cortex gives the solver 45% of a run's limit).
- **Required steps are never priced away.** The answer and the premises check run on whatever remains. Below the
  0.1 s minimum step, a required step is refused with BUDGET_EXHAUSTED and the result narrows: the compile
  abstains, or the claim verdict keeps "premises UNDECIDED (BUDGET_EXHAUSTED)" instead of a proof that may be
  vacuous.
- **Optional steps are priced by their measured tail.** A sensitivity re-run starts only when the slowest step
  measured so far fits in the remaining budget. An input it cannot afford is reported as untested, never as
  robust, and the receipt's dissent says so.
- **Every run and stop is kept** in the compile receipt's `resource_use.budget`: step, required or optional,
  remaining budget, measured cost range, limit, time spent and stop reason.
- **Local compute is measured.** Cortex receipts record `cpu_seconds`: the calling thread plus the solver and
  verifier processes it waited for. Peak memory per run and energy are reported as unmeasured, not as zero.
- **Declared budgets reach the other routes.** A declared budget becomes the ceiling of the cortex-problem route
  (`resources.max_latency_s`) and of the composition route (`max_latency_s`). Those routes are not split into
  steps.

**On the real body path** (`budget-mission.log`): a signed mission's `cognition.solve` request compiles a
financial optimisation with a 1.5 s budget. The answer took 0.60 s and one sensitivity re-run 0.42 s. The other
two stopped, because the slowest measured step (0.60 s) exceeded the 0.46 s left. The compile finished in
1.04 s, the receipt in the journal names both untested inputs, and CPU totalled 1.01 s. With a 30 s budget, all
three re-runs ran. Timings come from this container and vary by machine; the tests use a deterministic clock.

**Still open:**
- `budget.optional_step`, the value-priced variant, has no runtime caller. No optional step yet states its
  decision value in the unit of its cost.
- The 30 s per-run ceiling and the 20 s default are design constants, not measured optima.

## Verification

- 18 new tests: 10 for disclosure (including the CLI), 4 for characterization and 4 for the thinking budget. One coverage test was
  hardened.
- `mutants.log`: 21 mutants, all caught. That is the 7 from #161, 8 for disclosure gates, 5 for the thinking budget and 1 for the
  harness.
- `full-suite.log`: the whole frontier suite at `47bff1d`, the commit that built §9 and §5.
- **Later full runs (same interpreter):**
  - at `ac6952a`, after the first frontier merge: 2821 passed, 5 failed, 16 skipped;
  - at `5362d13`, after the second: 2849 passed, 6 failed, 16 skipped.
  - at `86096ac`, with §12: 2886 passed, 5 failed, 16 skipped.
  - **The failures:** five are the environmental Landlock tests named in `full-suite.log`. The sixth, in `test_greg_competency_compiler.py`, fails identically at the pristine frontier `d5bb5cb` and fails the frontier's own CI there. The frontier fixed it by `5287303`, which is merged here.
- **Cold first solve (2026-10-14, `cold-start.log`):** two thinking-budget tests failed on the first run after a
  container restore and passed on rerun. Each inner run's latency limit is a real solver deadline, while the
  tests' budget clock is fake. With a 5 s or 10 s limit the solver got 2.25 s or 4.5 s, and the first solve
  after the restore did not finish in time; the cortex correctly reported UNKNOWN (TIMEOUT).
  - **Reproduction:** a temporary 2.5 s or 5 s delay on the first worker start reproduces both failure signatures
    on the old tests. The hardened tests give every inner run a real limit of 20 s or more and pass under both.
  - **Not measured:** the restore-time slowness itself; it was gone when looked for.
  - **Possibly related:** the unexplained focused run disclosed on #161 also came right after a merge. Its output
    was not captured, so it stays unexplained.
- **Frozen inputs:** §9 and §5 changed no pinned file. §12 changes `cortex.py` and `compiler.py`, which the P6
  freezes hash as part of the `greg/cognition` closure. No recorded result changes: the #158 lineage's P6 v1 to
  v3 ran at their freeze commits, and its P6 v4 (frozen at `14ec7a6`, held-out arm not yet run at the time of
  writing) is reproduced at its freeze commit too. `verification.py` is unchanged relative to #161.
- **Lineage (founder decision of 2026-10-14, `INTENT-20261014-MIND-LINEAGE-CONVERGENCE`):** this work is built on
  the #158 Mind lineage, and its CI is evidence for that lineage only. Run names such as "P6 v3" are cited here
  with their lineage and freeze commit, because the #155 lineage froze different evaluations under the same names
  and paths. None of this work renames, regenerates or supersedes a frozen artifact of either lineage.

Nothing was sent, attached, activated or merged. Authority delta: none. VEPMC: 0.
