# Fresh held-out draw protocol (pre-registration)

Pre-registers **how** a replacement held-out draw will be generated. It does
**not** create the draw. The draw cannot exist yet: it must be instantiated from
a value that is unpredictable at the time the implementation is frozen, and the
implementation is not frozen.

The original draw is retired in `RETIRED_DRAWS.json` — `CONTAMINATED`,
`NON_ADMISSIBLE`, never reusable for a gate claim.

## 1. Structure families

New families, **not renamed copies of the ten exposed fixtures**. A renamed copy
of an exposed structure is still exposed.

Each family is a generator over a fixed distribution, so the draw selects
*instances*, not hand-authored graphs:

| family | parameter | fixed distribution |
|---|---|---|
| `spine_fanout` | independent spines feeding the tail | uniform {2, 3, 4, 5} |
| `join_capacity` | distinct producers per join input type | uniform {2, 3, 4} |
| `join_arity` | inputs per join | uniform {2, 3} |
| `chain_depth` | capability layers ENV→SINK | uniform {5, 6, 7, 8} |
| `neighbour_density` | connection probability | uniform {0.6, 0.7, 0.8, 0.9} |
| `domain_overlap` | share of producers in one resource domain | uniform {0.0, 0.5, 1.0} |
| `cost_spread` | ratio of dearest to cheapest producer | uniform {1.0, 1.5, 2.5} |

**`join_capacity` is recorded per episode and is a mandatory stratifier.** The
Phase 3G development fixture had three PX producers but only two AUTH producers
feeding a two-input reconcile, which makes that layer unsatisfiable by
construction. An evaluation that does not record join capacity cannot tell
"repair failed" from "no distinct replacement existed", and would score correct
bounded escalation as failure. Every episode records, for the damaged slot:

```
distinct_producers_of_required_type
eligible_producers_after_sibling_exclusion
expected_outcome: RESTORATION | BOUNDED_ESCALATION
```

`expected_outcome` is derived from structure before the episode runs and is
never read by the substrate.

## 2. Fixed counts, thresholds, evaluator, sampling

Unchanged in kind from the retired manifest, so the standard is not lowered
after seeing results:

- episode counts per cohort: identical to the retired manifest;
- Gate F and Gate G thresholds: identical, and scored on their own denominators;
- Gate F and Gate G are never combined;
- evaluator: `evaluator.py` at the frozen hash;
- sampling: for each cohort, draw parameters i.i.d. from the tables above using
  the instantiating seed, then derive per-episode seeds by
  `SHA256(draw_id || cohort || index)`;
- damage classes: the same 14, assigned round-robin by episode index;
- victim selection: the existing pre-registered interior-carrier rule.

Episodes whose `expected_outcome` is `BOUNDED_ESCALATION` are scored on
attributable bounded escalation, **not** on restoration, and are reported on a
separate denominator. Restoration on such an episode is a **failure**, because
it can only be reached by violating independence.

## 3. Instantiation, after freeze

The draw is instantiated from a 256-bit value not disclosed before the freeze
commit — supplied by the founder, or another post-freeze unpredictable value.
`draw_id = SHA256(instantiating_value || frozen_implementation_sha)[:16]`.

## 4. Held-out runner preconditions

The environment variable alone is not protection. Every one of these must hold,
and the runner must abort naming the first that fails:

1. `git rev-parse HEAD` equals the recorded frozen implementation SHA;
2. working tree clean, tracked and untracked;
3. `draw_id` appears in neither `retired_draws` nor `spent_draws`;
4. manifest hash matches the freeze record;
5. `evaluator.py` hash matches the freeze record;
6. `fixtures.py` hash matches the freeze record;
7. a founder-authorised spend token for this exact `draw_id` is present;
8. `PHASE3G_SPEND_HELDOUT=1`.

On completion the runner appends `draw_id` to `spent_draws` in the same commit
as the results, so a second run against the same draw is refused by rule 3.

## 5. What this protocol does not do

- It does not create the replacement draw.
- It does not change any Gate F or Gate G threshold.
- It does not alter the development cohort, whose seeds were never held out.
- It does not license using the contaminated outcomes to tune the mechanism.
