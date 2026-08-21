# Fresh held-out draw protocol V2 — fixed strata

Supersedes `FRESH_DRAW_PROTOCOL.md` (V1), which is preserved unchanged. V2
corrects one defect in V1 and changes nothing else.

## 1. The defect in V1

V1 sampled `join_capacity` uniformly from `{2, 3, 4}` and separated restoration
from escalation *after* sampling. That lets the Gate F denominator vary with the
draw: a draw containing several two-producer unsatisfiable joins would leave
fewer than 20 restoration-eligible Gate F episodes while the threshold stayed at
17. A denominator that moves with the sample is not a pre-registered
denominator.

**Stratify before sampling.** Capacity is a stratum, not a sampled parameter.

## 2. Fixed strata

```
Gate F
  exactly 20 restoration-eligible episodes
  threshold 17/20

Gate G
  exactly 20 capacity-sufficient causal-escape episodes
  threshold 15/20

No-valid-replacement
  exactly 8 structurally unsatisfiable episodes
  threshold 8/8 attributable bounded escalations
            0/8 false restorations
```

Gate F and Gate G contain **only** restoration-eligible / capacity-sufficient
episodes. A structurally unsatisfiable episode belongs in the no-replacement
denominator and may never appear inside Gate F or Gate G. Gate F, Gate G and the
no-replacement cohort are scored on their own denominators and are never
combined.

## 3. Generation order

1. Fix the three stratum sizes above: 20, 20, 8. These are constants, not draws.
2. For each stratum, sample structural parameters from the V1 distributions
   (`spine_fanout`, `join_arity`, `chain_depth`, `neighbour_density`,
   `domain_overlap`, `cost_spread`) — **except** `join_capacity`, which is
   determined by the stratum:
   - Gate F and Gate G: `join_capacity >= join_arity + 1`, guaranteeing at least
     one distinct eligible replacement after sibling exclusion;
   - no-replacement: `join_capacity == join_arity`, guaranteeing zero.
3. Compute eligibility structurally for the selected victim and slot. If the
   drawn instance does not match its stratum, reject it and redraw with the next
   derived seed. Record every rejection so the composition is auditable.
4. Only then assign damage classes, round-robin by episode index as before.

This makes the denominators exactly 20 / 20 / 8 by construction, independent of
the instantiating value.

## 4. Unchanged from V1

- structure families are new, never renamed copies of the ten exposed fixtures;
- episode counts per cohort, thresholds, evaluator, sampling method and the 14
  damage classes are fixed in advance;
- per-episode records include `distinct_producers_of_required_type`,
  `eligible_producers_after_sibling_exclusion` and `expected_outcome`, all
  derived before the run and unreachable from the substrate;
- `draw_id = SHA256(instantiating_value || frozen_implementation_sha)[:16]`,
  instantiated only after freeze from a value not disclosed beforehand;
- all eight runner preconditions, including the founder-authorised spend token
  and the retired/spent draw check.

## 5. Still not created

The structures, the seeds and the `draw_id` do not exist and must not exist
until after implementation freeze and founder-authorised instantiation. The
original exposed fixtures and seed ranges remain permanently retired in
`RETIRED_DRAWS.json`.
