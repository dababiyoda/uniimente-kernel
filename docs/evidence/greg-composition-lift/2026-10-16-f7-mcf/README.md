# F7 with flow_expansion_mcf on v4's held-out items: MATCH (2026-10-16)

- **What this is:** a declared re-use of P6 v4's 200 held-out F7 items: real SNDlib backbones, surge capacity leasing under a budget. These items had already been looked at twice, by v4 (`14ec7a6`) and by the Track B audit (`49b2d58`/`8bbd3b8`). This run cannot change v4's verdict and adds nothing to VPL.
- **Question:** on real items, does the admitted single genome `flow_expansion_mcf` 1.0.0, served through `cortex.reason`, match the routed composition `graph_then_allocate`?
- **Pre-registration:** `cortex/evaluation/composition_lift/prereg-v6.json`, committed at `311dfa0`. The rule, arms, thresholds and secondary decision are unchanged since then; only an `attempts` disclosure was added.
- **Runner:** `cortex/evaluation/composition_lift/run_v6.py`.
- **Freeze:** `freeze-v6-attempt2.json`, committed at `91b826c` and covering 130 code files.
- **Run:** once, in a fresh detached worktree at `91b826c`, under `python -I`, with 2 workers pinned to cores 0 and 1. Load average was 0.8 at the start and 2.0 at the end, with no other Python processes. The run finished with exit 0 and `integrity: []`.
- **Attempt 1** hung before any held-out item finished, and no outcome was observed. See `attempt-1/README.md`.

## Result (copied from `results-v6.json`)

| Arm | Optimal | Median s |
|---|---:|---:|
| `flow_expansion_mcf` (cortex.reason, isolated worker, independent verifier) | 200/200 | 0.7529 |
| routed composition `graph_then_allocate` | 200/200 | 2.8663 |
| Competency Compiler | 200/200 | 0.7624 |
| parametric min-cost flow (in process, truth algorithm) | 200/200 | 0.0042 |

- **Rule: MATCH.**
  - No wrong answer, and a decision on every item.
  - Wins and losses 0-0, so p_worse = 1.0.
  - Latency ratio 0.2627, against the 1.25 limit.
  - The comparator replicated v4.
  - The result is uninformative beyond replication. It is the expected tie, and it replicates admission v3's DEFAULT verdict on real items.
- **Independent rescoring:** SciPy max flow plus a HiGHS MILP truth, sharing no code with `flow.py`. The truth agrees on 200/200, all four arms agree on 200/200, and there are 0 disagreements.
- **Compiler:** it selected `cognition.flow_expansion_mcf` on 200/200 items, with outcome, throughput and increments identical to the genome's.
- **Secondary, F7_LIFT_WITH_GENOME: NO_LIFT.** The best constituent is the genome, so routed is no more optimal and the sign test cannot pass. With the exact single method in the repertoire, F7's composition lift does not survive. v4's frozen verdict, which was over a repertoire that lacked it, is unchanged.

## Reading

- On F7's real geometry, the single exact genome is canonical. It matches the composition's quality on all 200 real items at about a quarter of the latency, through the same governed path.
- The Competency Compiler already routes there; attaching the genome remains the founder's decision.
- Natural-family VPL stays as recorded. F7 is now a family where the lift was over GREG's earlier repertoire, not over its current admitted one.
- **Data terms:** SNDlib's are unresolved. This is a release blocker and a founder decision.
