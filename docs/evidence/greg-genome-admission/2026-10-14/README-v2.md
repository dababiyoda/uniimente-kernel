# IntelligenceGenome admission v2: Layer 1/2/4 repertoire on native geometries, 2026-10-14

Runner `cortex/evaluation/genome_admission/run_v2.py`; freeze `freeze-v2.json` committed before the run
(`b99daba`); results `results-v2.json` (every per-seed metric retained). Seeds 2001-2040; v1's frozen status
rule. Code: `greg/cognition/repertoire.py`, reachable as `cognition.robust_pattern`, `cognition.crowd`,
`cognition.swarm`, `cognition.blackbox` (built and VERIFIED; not attached until the founder attaches them).

| Family (layer) | Candidate | vs baseline W/L (p) | vs competitor W/L (p) | Status (frozen rule) |
|---|---|---|---|---|
| robust_pattern (1) | median/MAD modified z 3.5 | Tukey IQR 10/5 (0.15) | generalized ESD 4/3 (0.50) | EXPERIMENTAL |
| crowd (2) | Dawid-Skene EM | majority vote 29/9 (0.0008) | one-step agreement-weighted vote 15/18 | **DEFAULT_FOR_GEOMETRY** |
| swarm (2) | particle swarm (constriction) | random search 39/1 | differential evolution 18/21 | **DEFAULT_FOR_GEOMETRY** |
| blackbox (4) | differential evolution | random search 39/1 | multistart L-BFGS-B 8/26 (worse, p = 0.0015) | **SUPERSEDED** |

Mean metric (lower is better): robust_pattern 1-F1 0.113 / IQR 0.137 / ESD 0.129; crowd error 0.178 /
majority 0.213 / one-step 0.166 / oracle 0.133; swarm best fitness 14.97 / random 140.45 / DE 2.72;
blackbox 2.72 / random 140.45 / L-BFGS-B 1.99.

References outside the rule: MAD beats the v1 population z-score (REJECTED in v1) 25/5; the oracle vote
that knows every observer's true accuracy beats Dawid-Skene 27/7 (no deployable method can know them).

## What this changes

- **Layer 2 has its first admitted collective mechanism:** Dawid-Skene learns observer reliability from
  agreement alone and beats majority vote at p < 0.001 on crowds with experts, average observers and
  spammers. Caveat: the simpler one-step agreement-weighted vote is statistically tied with it (and has a
  slightly lower mean error), so Dawid-Skene's extra machinery is not yet shown to beat the simplest
  competent method; the next admission should test sparse, multi-class crowds where EM's advantage is
  expected, or prefer the one-step vote.
- **Layer 1:** MAD replaces the rejected z-score in effect (25/5) but is not admitted over IQR fences on
  this mixed Gaussian/heavy-tailed geometry. EXPERIMENTAL; IQR remains the simple baseline to beat.
- **Black-box optimisation:** DE on its native geometry beats random search but loses to multistart
  L-BFGS-B. **Post hoc (not pre-registered; per-seed values in results-v2.json): multistart L-BFGS-B also
  beats PSO 32/7 (p = 3.5e-5).** PSO's DEFAULT status is relative to what GREG had; the strongest mechanism
  measured on this geometry is commodity SciPy multistart L-BFGS-B. Acquisition target for Capability
  Genesis; the next pre-registered admission must use it as the competitor for swarm and blackbox.
- The objective menu is smooth or mildly multimodal (sphere, rastrigin, ackley, rosenbrock, griewank) at
  2-8 dimensions; gradient-free methods may regain ground on noisy or discontinuous objectives. Not run.
