# Development protocol V2 — restoration-eligible and no-replacement cohorts

Pre-registration. Committed **before** the cohorts are generated and before any
result exists. No runtime change accompanies this document.

## 1. Founder ruling being implemented

The original 48-episode development cohort is structurally confounded for an
all-restoration freeze criterion. It is `_spine × 3 + _tail(2)`: three PX
producers but only **two** AUTH producers, while `reconcile` requires two
*distinct* AUTH inputs. When one AUTH producer is damaged, no independent
replacement exists, and correct behaviour is bounded escalation.

Bounded escalation is **not** retroactively counted as restoration. The bar is
not reinterpreted; the cohort is.

The original cohort is preserved unchanged and reclassified:

```
DIAGNOSTIC
STRUCTURALLY_CONFOUNDED_FOR_RESTORATION_FREEZE
NON_ADMISSIBLE_FOR_THE_41_OF_48_FREEZE_BAR
```

It remains valid evidence about mechanism behaviour and about the fixture
defect itself. Every recorded run (R1, R2, R3, R3b, R4, R5, R5_REPRODUCED) and
both taxonomies stay exactly as they are.

## 2. Cohort A — restoration-eligible development

- **exactly 48 episodes**
- every damaged obligation has **at least one distinct eligible replacement
  after sibling exclusion**
- `expected_outcome = RESTORATION` for all 48
- no formation voids permitted
- every assigned damage class must be observed
- freeze threshold: **≥ 41/48 qualifying**

Eligibility is a structural property, computed before the episode runs:

```
required_type                      = capability.accepts[damaged_slot]
distinct_producers                 = units producing required_type, minus the victim
eligible_producers                 = distinct_producers - suppliers of the
                                     consumer's other slots
RESTORATION-ELIGIBLE  iff  len(eligible_producers) >= 1
```

Construction rule: the fixture generator must supply, for every capability type
consumed by a join of arity *k*, at least *k + 1* distinct producers. For the
claim spine that means `_tail` must provide **three** AUTH producers and three
RECON producers, not two. An episode failing the eligibility check at generation
time is regenerated with the next seed, and the rejection is recorded, so the
cohort's composition is auditable rather than silently filtered.

## 3. Cohort B — structural no-replacement control

- **exactly 8 episodes**
- every damaged obligation has **zero** eligible distinct replacements after
  sibling exclusion
- `expected_outcome = BOUNDED_ESCALATION`
- thresholds: **8/8 attributable bounded escalations**, **0 false restorations**,
  **0 independence violations**

An episode in this cohort passes only if it ends with:

```
BOUNDED_ESCALATION_PROVEN = true
FALSE_RESTORATION         = false
INDEPENDENCE_VIOLATIONS   = 0
```

A restoration here is a **failure**, because it is only reachable by binding one
supplier into both protected slots.

## 4. The denominators are never combined

Cohort A scores restoration. Cohort B scores escalation. No metric mixes them,
and no summary field sums them. This is the same rule that already forbids
combining Gate F with Gate G.

## 5. expected_outcome is not visible to the substrate

`expected_outcome`, `eligible_producers` and `distinct_producers` are derived by
the generator from structure, recorded in the episode plan, and read only by the
evaluator. No unit, need, offer, port or scheduler path can reach them. An
adversarial test asserts the substrate module never references them.

## 6. What this document does not do

- It does not generate either cohort.
- It does not change the 41/48 threshold, which stays exactly 41 of 48.
- It does not change Gate F (17/20) or Gate G (15/20).
- It does not alter, rescore or delete the original 48 episodes.
- It does not license any held-out run.
