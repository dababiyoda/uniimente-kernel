# Competency characterization, 2026-10-13

Produced by `greg.cognition.benchmark.assess()` on the final tree of this branch (parent commit
`822f37b5363abf49f72820956b4d6db838424e89`, Python 3.11.15). `characterization.json` is the full report.

Summary: {"methods": 18, "measured": 107, "not_applicable": 32, "not_measured_here": 41}.

| method | error correction | detection rate | corruptions | latency p95 (s) |
| --- | --- | --- | --- | --- |
| `cognition.causal` | measured | 1.0 | 3 | 0.10848621439997715 |
| `cognition.collective` | measured | 1.0 | 3 | 0.10000344999997424 |
| `cognition.control` | measured | 1.0 | 3 | 0.09988483500001166 |
| `cognition.estimation` | measured | 1.0 | 3 | 0.11286887399995749 |
| `cognition.exact` | measured | 1.0 | 6 | 0.8062660528000322 |
| `cognition.formal` | measured | 1.0 | 3 | 0.1474554792499589 |
| `cognition.game` | measured | 1.0 | 5 | 0.4875014550000287 |
| `cognition.graph` | measured | 1.0 | 5 | 0.22671755499999335 |
| `cognition.information` | measured | 1.0 | 3 | 0.11921458900002335 |
| `cognition.micro` | measured | 1.0 | 1 | 0.09861506999999392 |
| `cognition.optimization` | measured | 1.0 | 4 | 0.48100241200000937 |
| `cognition.pattern` | measured | 1.0 | 3 | 0.10127363600003036 |
| `cognition.probabilistic` | measured | 1.0 | 4 | 0.13793694100002085 |
| `cognition.search` | measured | 1.0 | 5 | 0.2685655369999722 |
| `cognition.semantic` | not_measured_here |  |  | 0.05709593700004234 |
| `cognition.sequential` | measured | 1.0 | 2 | 0.09914728699999387 |
| `cognition.simulation` | measured | 1.0 | 3 | 0.10837751899998693 |
| `cognition.cortex` | measured |  |  | 0.61096105 |

Before the exact re-checks added the same day, detection was 0.0 for estimation, causal, control,
information, simulation, pattern, micro, sequential and collective, and 0.4 for exact (the `exact`
string and polynomial roots were not re-checked). The cortex row's error correction counts hard
failures in the frozen v0.3 held-out run; its generalization gap per stratum is held-out minus
selection loss on the routed arm (negative means better on fresh samples). Latencies include the
isolated worker's interpreter start and vary with machine load; two cases abstained on a 5 s worker
timeout during one loaded run and passed on the next, which is a latency ceiling, not a verifier
change. The semantic family is not measured here: no founder-selected local model is available.
