# Genome admission v9: `convex_qp_dual` 1.0.0 after the transport fix (2026-10-22)

**Verdict: DEFAULT_FOR_GEOMETRY.** The canonical-path smoke passes.

| Step | Commit |
|---|---|
| Pre-registered | `ce760f7a` |
| Frozen | `11a8e318` |
| Run once | from a clean detached worktree on one pinned core, 10:55 to 10:56Z |

**What changed since v8.** v8's rule decision was DEFAULT, demoted to NICHE by the smoke failure. That record stands unchanged. This run is the fresh measurement its README called for.

- **Run:** source commit `11a8e318`, source dirty [], freeze `sha256:6082091af5aac13a…`, finished 2026-10-22T10:56:32.740389+00:00.
- **Host load:** start {'1m': 1.0, '5m': 0.99, '15m': 1.04, 'runnable': 1, 'entities': 110}, end {'1m': 1.0, '5m': 1.0, '15m': 1.04, 'runnable': 1, 'entities': 106} (diagnostic only).

| Family | Layer | Version | Status | Candidate correct/wrong/abstain | vs baseline W-L-T (p better) | vs competitor W-L-T (p better / p worse) | Median s (candidate / baseline / competitor) | Canonical path |
|---|---|---|---|---|---|---|---|---|
| `convex_qp_dual` | 3 | 1.0.0 | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 13-1-16 (0.000916) | 23-0-7 (0.0 / 1.0) | 0.002508 / 0.02307 / 0.193948 | STRUCTURALLY_VERIFIED |

`convex_qp_dual` by subregion: ill_conditioned (n=16): vs baseline 10-1-5, vs competitor 13-0-3; many_constraints (n=3): vs baseline 3-0-0, vs competitor 3-0-0; well_conditioned (n=11): vs baseline 0-0-11, vs competitor 7-0-4.

## Reading

**The defect is closed on the data it was found on.** 14 of the 30 fresh held-out QPs exceed the old 64 KiB limit, and 7 exceed the 128 KiB single-argv cap that was the real constraint. The largest is 381 KB.

- **The smoke instance** is seed 1800 at 92.5 KB, which v8 would have refused. It was solved and verified through `cortex.reason` (STRUCTURALLY_VERIFIED, genome certificate, 0.69 s, no authority created).
- **The rule's own result replicates v8 on fresh seeds:**
  - 30/30 correct;
  - 13-1-16 against the dual projected-gradient baseline (p = 0.0009);
  - 23-0-7 against SciPy `trust-constr`, at about 1/77 of its median latency.

**Where the edge is.** By subregion, the gains come from ill-conditioned and many-constraint QPs. On well-conditioned QPs the genome ties the baseline 0-0-11 and still beats `trust-constr` 7-0-4.

**What this does not establish:**
- **Synthetic instances only.** It says nothing about a natural workload.
- **Routable is not attached.** `convex_qp_dual` is now routable as the default for dense convex QPs at 1.0.0, but attaching it is the founder's decision. Nothing is attached.
- **One ceiling remains.** A signed mission still binds at most 16 KiB of inline data (`greg/missions.py` `DEFAULT_BIND_BYTES`). A founder mission that carries a large QP has to supply it by reference; that path is not part of this run.

**Counts after v9:** 83 executable genomes, all with current-version evidence. 45 DEFAULT_FOR_GEOMETRY, 17 NICHE_CAPABILITY, 12 SUPERSEDED, 3 COMPOSITION_ONLY, 4 EXPERIMENTAL and 2 REJECTED, so 62 are admitted. None is attached.
