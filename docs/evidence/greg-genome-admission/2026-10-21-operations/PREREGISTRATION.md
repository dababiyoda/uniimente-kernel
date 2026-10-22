# Operation re-admission: pre-registration (2026-10-21)

**Status:** pre-registered. Both files in this directory were committed before any held-out instance was generated. `freeze.json` is the machine-checked half; `--run` refuses to report if any frozen input differs.

## What is fixed before the run

| Item | Value |
|---|---|
| Run id | `2026-10-21-operations` |
| Families | `control`, `game`, `information`, `probabilistic`: the four #155 operation verdicts (2026-10-14, seeds 1001-1040) that the PR #184 merge left UNEVALUATED because their solver closures changed (#159's native-qualified `solvers.py`) |
| Held-out seeds | 2600-2629 (n = 30), never generated before this run. Refused at freeze: development seeds 0-9; P8's reserved 7000-8059; every genome-admission freeze (v1 1000-1029, v2 1100-1129, v3 1200-1229); #155's runs (1001-1040, 2001-2040, 3001-3040). A scan of every tracked file at the pre-registration commit (every integer under a JSON key containing "seed", every [a, b] seed pair, every Python range literal, and a text search near seed/held/split/range words) found no use of 2600-2629. The first window chosen, 1300-1329, was abandoned before any instance was drawn because seed 1311 is used by a frozen cross-geometry held-out item (HEL-CAU-C184, a confounded causal generator); no seed was drawn there. Seeds 900000-900999, 960000-960029 and 961000-961029 were drawn in scratch while planning and reviewing this runner and are never used as held-out seeds. |
| Rule (routes) | the canonical genome-admission `RULE`, verbatim in `freeze.json` (`inputs.rule`), unchanged since v2 |
| #155 rule (does not route) | #155's `status()` on the same rows, recorded per family as `rule_155_status`; its text is `inputs.rule_155` |
| Generators and arms | #155's, verbatim (`cortex/evaluation/genome_admission/run.py`), split into an instance and three timed arms; exact parity with #155's `BENCHMARKS` on development seeds 0-9 is a unit test |
| One declared change | `GEOMETRY` compute_limit 100000 (latency_limit 10.0 as #155). #155's 200000 exceeds the merged native ceiling, so every merged solver raises CognitionError |
| Verification | every solver answer behind a candidate output passes `greg.cognition.verification.verify` (120 per control episode); a refuted output is scored wrong, below abstaining |
| Statistics | paired one-sided exact sign tests, alpha 0.05, ties within 1e-9; median wall-clock latency in this container |
| Canonical path | one held-out instance per family through `greg.cognition.cortex.reason` with `cognition.<family>` attached in an evaluation-only registry view; a smoke that is not STRUCTURALLY_VERIFIED demotes DEFAULT to NICHE. Nothing is attached on any body |
| Code | the import closure of the runner, the genome harness and the isolated worker, all of `greg/cognition`, the requirement files and the dependency versions, each hashed in `freeze.json` |
| Run | once, in a clean worktree at the commit that adds this file, pinned to one CPU core (`taskset -c 1`). A crash is recorded, never retried; any repair needs a new run id and new seeds |

## What this measures, and what it does not

- The arms are #155's: P-only kp=2, pure maximin, always acquire, Jeffreys posterior mean. They are weaker than the genome library's strongest competitors for these geometries (`pid_simopt`, `game_lp_dual`, `bayes_interval`). A verdict here answers #155's question on the merged code. It is **not** a strongest-competitor admission.
- Expected outcomes, from scratch resampling on seeds 900000-900999 outside every used range (plan, and an independent review's bootstrap of `decide()` at n = 30 with the runner's own adapter, 4000 resamples; not evidence):
  - control, game and information are significantly better than both arms with probability about 1.0 (information DEFAULT 0.999, game 1.0);
  - probabilistic, under the canonical rule: DEFAULT_FOR_GEOMETRY about 0.35, NICHE_CAPABILITY about 0.45, EXPERIMENTAL about 0.20. The Jeffreys arm is inline arithmetic, so the 1.25x latency clause cannot rescue a non-significant result. Under #155's rule: DEFAULT about 0.81, EXPERIMENTAL about 0.19; that column is reported, never routed;
  - **NICHE_CAPABILITY and EXPERIMENTAL are both acceptable recorded outcomes for probabilistic.** EXPERIMENTAL removes it from routing; the review's single simulated run on scratch seeds 960000-960029 came out EXPERIMENTAL (17-9 against the baseline, p = 0.084).
- The run is refused unless `freeze.json` is committed at HEAD unchanged and the tree is clean outside this directory (`NOT_PRE_REGISTERED`), and a frozen seed that is negative, development, P8-reserved, #155's or spent by another freeze is refused at freeze and again at run. The results record `pre_registered`, `freeze_commit` and `source_commit`; the evidence index routes a run that is not pre-registered as UNEVALUATED.

## What the outcome changes, and what it cannot

- DEFAULT_FOR_GEOMETRY or NICHE_CAPABILITY routes the family again at the measured solver closure (the index binds it). It does not attach anything: attaching is the founder's decision.
- SUPERSEDED, EXPERIMENTAL or REJECTED excludes the family from routing until a later re-admission.
- No result is re-run, re-scored or re-labelled. The README is generated from `results.json` by script; negative verdicts are reported with the same prominence as positive ones.
- A later change to any measured closure member (solvers `control`, `game`, `information`, `bayesian`, `_request`, `_work`, `_native_source`, `result`; contracts `canonical`, `digest`, `integer`, `number`, `CognitionError`) makes the verdict stale again.
