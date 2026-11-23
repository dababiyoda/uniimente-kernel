# F7 with flow_expansion_mcf: attempt 1 (no result)

- **Freeze:** `cortex/evaluation/composition_lift/freeze-v6.json`, committed at `4430138` and kept unchanged.
- **Run:** 2026-10-16 from 06:27 UTC, in a fresh detached worktree at `4430138`, using
  `python -I cortex/evaluation/composition_lift/run_v6.py --workers 2 --cores 0,1 --out ...`.
- **What happened:**
  - The gate passed (130 frozen files).
  - The warm-up item ran in the parent and printed. It is a development item, not a held-out item; its line is
    the only line in `run.log`.
  - No held-out item then finished in either worker, and nothing more was printed.
  - The process was killed at the 40-minute background limit, and no results file was written.
- **No held-out outcome was observed.**
- **Cause, reproduced on development items only:** the warm-up started the solver libraries' native threads (8
  after one item), and the pinned worker pool was forked after them, so the forked workers deadlocked. The
  development runs had used one worker, or forked before doing any work, so they never met this.
- **Fix:** `run_v6.worker_pool` forks the pool before the warm-up. The regression test is
  `test_the_heldout_pool_is_forked_before_the_warmup_starts_any_solver_thread`. Nothing else changed: the rule, the
  arms, the thresholds, the items and the secondary decision are the same.
- **Attempt 2:** a new freeze, `freeze-v6-attempt2.json`, then one run at its commit.
