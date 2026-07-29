# Taxonomy V2 — complete cohort matrix and the isolated causal break

Evaluator-only. No runtime behaviour changed. V1 (`classify_failures.py`) is
preserved byte-for-byte as the record of what was measured wrongly.

Implementation: development cohort, 48 episodes, seeds 4000–4047.

## 1. Complete cohort matrix (all 48 episodes, mutually exclusive)

| group | episodes |
|---|---|
| formation_failed | 7 |
| damage_not_observed_but_reported_success | 3 |
| damage_not_observed_and_failed | 5 |
| damage_observed_and_restored | 15 |
| damage_observed_and_not_restored | 18 |
| **total** | **48** |

The audit's cohort-wide figure is confirmed and decomposed: **15 of 48 episodes
never observed their assigned damage** = 7 formation failures (damage never
injected) + 8 injections that did not take effect.

Diagnostic denominators (these do **not** replace or alter the preregistered
Gate F denominator):

```
VALID_FORMATION_AND_OBSERVED_DAMAGE_EPISODES = 33
VALID_OBSERVED_DAMAGE_RESTORATIONS           = 15
VALID_OBSERVED_DAMAGE_QUALIFYING             = 14
```

**`17/48` was not a clean restoration score.** Reconciled against the harness:
18 episodes restored, 17 of those qualified (episode 16 restored but no
pre-repair semantic loss was proven, so it fails the qualifying predicate), and
**3 of the 18 restorations are episodes where the assigned damage never
occurred.** The honest observed-damage restoration rate is **15/33**; the honest
observed-damage qualifying rate is **14/33**.

V2 was verified faithful to the scored harness at the same implementation:
**0 mismatches across all 48 episodes** on healthy formation, damage
observation and semantic restoration.

## 2. Edge identity, with generation

Edges are keyed by `consumer | slot | supplier | need generation | work-item
generation`, using two new provenance fields on `Bond` (`settled_by`,
`settled_item`) that nothing in the runtime branches on.

`duplicate_instrumentation_candidates = 0`. The episode-27 case where V1 showed
`reconcile.10` twice was **two legitimate distinct edges** — different
consumer/slot pairs bonded to the same supplier — not duplicate counting.
`(consumer, slot)` is unique per snapshot because bonds are a dict keyed by slot.

Cone-scoped edge classification, split by outcome — a class occurring at a
similar rate in restored and unrestored episodes is background, not cause:

| classification | unrestored (23) | restored (18) |
|---|---|---|
| replacement_settled_supplier_not_produced | 0 episodes | 0 episodes |
| preexisting_active_supplier_not_produced | 22 episodes / 41 occurrences | **0** |
| off_path_idle_bonded_supplier | 2 episodes / 2 occurrences | 0 |

V1's `39` was edge occurrences. The cone-scoped, generation-keyed count is **41
occurrences across 22 episodes**, and **not one of them is a newly settled
replacement.** Every flagged edge is a pre-existing bond unchanged from the
healthy run.

## 3. The settlement-activation hypothesis is dead

| | episodes |
|---|---|
| replacement settled during the repair work item, among **restored** | **17 of 18** |
| replacement settled during the repair work item, among **unrestored** | **3 of 23** |

Repair that settles a replacement restores 17/20 of the time. Repair that
settles nothing restores 1/21 of the time. The break is **before settlement**,
not in activation after it.

## 4. The first scheduler lifecycle break

Scoped to the obligation the damage actually created — the `(consumer, slot)`
pairs bonded to the victim in the healthy run. An earlier unscoped version of
this measurement reported `offer_received_never_settled` for 20/23 unrestored
*and* 16/18 restored episodes, which is V1's scoping error in a new place; the
scoped version discriminates:

| first break | unrestored (23) | restored (18) |
|---|---|---|
| offer_received_never_settled | **19** | **0** |
| need_sent_no_offer_received | 2 | 2 |
| no_reopen_detected | 1 | 1 |
| consumer_resumed_sink_not_reached | 1 | 0 |
| no_break_restored | 0 | 15 |

## 5. Why the offer is never settled

Every refusal path in `_settle` now records a reason. Previously only `nonfirm`,
`stale` and `cooldown` did, so these 19 episodes read `offers=1, rejected={}` —
an offer counted as received and then silently dropped, with four candidate
paths and no way to distinguish them.

With the gap closed, at the isolated break:

```
duplicate_supplier : 18
stale              :  1
```

The controlling rule is in `Unit._settle`:

```python
if any(b.supplier == offer.supplier for b in self.bonds.values()):
    return False
```

An offer is refused when the offering supplier already fills **another slot on
the same consumer**. The units that fail are the join capabilities —
`authorise(PX, PX)` and `reconcile(AUTH, AUTH)`, two slots of the same type. When
one slot's supplier is damaged and reopened, the offers that arrive come from the
supplier already bonded to the sibling slot, the distinctness rule refuses them,
and search credits remain unspent (7–12 of the budget) because no other producer
of that type is reachable on the frontier.

This is not an accident of instrumentation. It is the supplier-distinctness
guard added in Phase 3E to stop one supplier filling both join slots. That guard
enforces path independence, which Gate G's semantics depend on. It also makes
repair structurally impossible on a two-slot join whose only remaining
same-type producer is the sibling's supplier.

Recorded as an isolated causal break, not yet as a mechanism decision: the fix
trades path independence against repairability on joins, and that trade is an
architectural choice, not a defect repair.
