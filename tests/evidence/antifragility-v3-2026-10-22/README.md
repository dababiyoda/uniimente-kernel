# Antifragility v3 (§14, condition-specific competence): **NO_GAIN**

- **Pre-registration:** [`PREREGISTRATION.md`](PREREGISTRATION.md), frozen with [`workload.json`](workload.json) in `4229fe1b` (workload `sha256:d7f390e5…`; #189's harness and the mechanism code pinned). The base is the integration owner's final joined head, `9e12b9a6`.
- **Run:** once, from a clean detached worktree at `4229fe1b`, under `taskset -c 1`, 08:28:54 to 08:41:01 UTC. The 1-minute load was 0.66 at the start and 1.08 at the end. Outputs: [`result.json`](result.json) and [`run.log`](run.log).

## Verdict, by the frozen rule

| Arm | Holdout passes, total (of 100) | LOW (of 50) | HIGH (of 50) |
|---|---:|---:|---:|
| PRE | 66 | 45 | 21 |
| LEARN | 66 | 45 | 21 |
| CONTROL | 66 | 45 | 21 |
| A, pooled | 66 | 45 | 21 |
| S, shuffled condition | 66 | 45 | 21 |
| B1, compute-matched | 45 | 45 | **0 (invalid, see below)** |
| B2, best-of-both (2× compute) | 89 | 50 | 39 |

- **Rule 1 (REGRESSION):** does not apply. LEARN loses nothing at LOW against PRE (45 = 45), and is not below CONTROL in total (66 = 66).
- **Rule 2 (NO_GAIN):** applies. **The cell preference never fired in the 36 stress missions.**
- **Outcome:** every arm that reads the evidence routed every holdout instance to the incumbent swarm, which is identical to PRE and CONTROL. The sign test of LEARN against CONTROL has 0 discordant pairs.

## Why it never fired

**The evidence that accumulated.** The stress damaged the body as intended: 16 of 36 missions failed. Shadowing then started after the first failure from another problem. 34 claims were paired, at a cost of 34 shadow trials, 340,000 evaluations and 8.4 s.

- The 20-dimension cell ended with **11 discordant pairs favouring the alternative and 6 favouring the swarm**.
- The one-sided sign test gives p ≈ 0.17. The frozen threshold is p < 0.05, so the preference did not fire. The pre-registered power of about 0.9 assumed the pilot's rates (HIGH 10 → 20 passes of 30); the stress realised a much smaller net effect.

**Each pair attributed to its mission's objective.** Each stress row reads the evidence just after its own mission settles, so the increments attribute exactly:

| Objective (HIGH) | Alternative only | Swarm only | Pairs |
|---|---:|---:|---:|
| Rosenbrock | 6 | 0 | 7 |
| Griewank | 3 | 0 | 7 |
| Sphere | 1 | 0 | 7 |
| Rastrigin | 1 | 2 | 7 |
| Ackley | 0 | 4 | 6 |

**Finding, post hoc and not part of the rule.** Inside the 11–30 d cell, which method is competent depends on the objective, not on the dimension.
- The multistart genome dominates on smooth or valley-shaped objectives: Rosenbrock, Griewank and Sphere.
- It loses on Ackley, as the pilot showed (2 → 0).
- Keyed on dimension alone, the cell mixes both kinds, and the discordant evidence partly cancels.
- B2 bounds the headroom. Choosing the better of the two methods per instance would have passed 89 of 100, against 66, at double the compute. So routing has something to gain, and this key did not capture it.

This finding was not pre-registered. It does not change the verdict. **No redesigned key is re-run here.** A finer key, such as dimension × objective, would need its own pre-registration, fresh seeds and the integration owner's approval. Under the 2026-10-21 directive, a loop that retries until GAIN is not allowed.

## Defects disclosed

**B1 is invalid as a control.**
- At the computed matched budget of 26,800 evaluations per HIGH instance, the swarm **abstained on all 50 HIGH instances** (state ABSTAIN, 0 evaluations). 26,800 is above a budget the swarm's admission path refuses.
- The harness was not tested at budgets above the request's own, so this went unseen before the freeze.
- It does not affect the verdict, because rule 2 decides before rule 3 reads B1. But B1 measured nothing.
- A future run must cap the matched budget at the method's accepted limit, or match compute differently.

**Shadow cost.** The 340,000 shadow evaluations are counted, and they bought no routing change in this run. This is the repair cost section 14 says to count.

## What this does and does not show

- **Shown:** the mechanism works end to end on GREG's canonical path under signed missions and real settlement.
  - Failure-triggered inert shadows ran, were paired under the signed check and accumulated per cell.
  - The preference stayed silent when the evidence did not reach its threshold.
  - No answer changed, nothing self-attached, and no other cell was touched.
- **Not shown:** that GREG learned to route better from stress. **§14's antifragility requirement remains unmet for this mechanism and key.** #189's residual 3 (competence summed across strata) is narrowed: summing across strata was not the only obstacle, because a strata key is also too coarse here. It is not closed.
- **Authority:** none created. Every attach used a per-run test key. VEPMC: 0.

## After the run: the base moved to `78da0332`

The integration owner's hold, which asked for the freeze to use `78da0332`, arrived after this run had finished.

- **What `78da0332` changes:** `constructed_candidates` now rejects a relaxed construction, such as an uncapped `selection.closure` answering a capped portfolio question.
- **What the change cannot touch:** this experiment's request shape. Here the compiler considers only `cognition.swarm` and `cognition.blackbox`, and no construction row exists. No composed construction was attached in any arm.
- **Probe:** compiling pilot-seed requests (seeds 0 and 1, d = 20 and d = 10; not holdout, `execute: False`) on the frozen tree and on that tree merged with `78da0332` gives byte-identical routing (considered, rejected, selected).
- **Owner's decision:** they accepted this accounting. NO_GAIN stands, and there is no rerun.
