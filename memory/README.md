# memory

Layer 8 — Causal Memory + Functional Affect (issue #7).

## Organs

- `causal.py` — `CausalMemory`: ancestry/descendants over causal-parent
  event links; decision precedent (outcome → receipt → witness joins:
  action class, policy version, result); verification-weighted outcome
  scoring (externally verified > internally observed > self-reported,
  recency-weighted); confidence calibration (predicted vs realized,
  overconfidence named); institutional learning (per-class volume,
  weighted success, trend).
- `affect.py` — `AffectController`: bounded machine control states
  (calm, alert, strained, degraded, recovering). Every state has an
  attributable trigger, an intensity ceiling, a decay rate, and an
  authority ceiling that only descends. Structurally cannot: change
  facts, create evidence, increase authority, override law, resist
  shutdown, or authorize irreversible action. Shutdown works from every
  state; decay always settles to calm.

## Recorded proof

`tests/unit/test_memory.py` (12 tests): ancestry to root, descendant
impact, precedent join with policy version, verification-weighted
scoring, overconfidence detection, declining-trend learning; affect
attribution requirement, ceiling enforcement, decay to calm, descending
authority ceilings, no caution-lowering while active, all six
pathological operations refused, shutdown from every state.

## Buildability standard (14 conditions)

- **Existing mechanism**: causal graphs, calibration curves, circuit-breaker state machines — standard, no novel science.
- **Defined interface**: `CausalMemory.ancestry/descendants/precedents/outcome_weighting/calibrate/institutional_learning`; `AffectController.trigger/decay/may_execute/shutdown`.
- **Bounded authority**: memory reads the ledger, never writes decisions; affect holds no handle on policy, grants, or law — advisory ceilings only.
- **Available dependencies**: Python 3 stdlib + `provenance.ledger`.
- **Security model**: affect's six pathological operations are structurally refused; triggers require attribution; ceilings enforced.
- **Failure modes**: `ValueError` (empty calibration), `AffectViolation` (unknown state, missing trigger, forbidden operation).
- **Acceptance tests**: `tests/unit/test_memory.py` (12 tests).
- **Recovery path**: affect decay converges to calm; shutdown always succeeds; memory is reconstructable from the ledger at any time.
- **Resource ceiling**: ancestry/descendants O(events); precedent joins O(records).
- **Operating cost**: bounded scans over ledger records; no external calls.
- **Legal operator**: Alfonso (memory serves his oversight; affect can only narrow what the institution may do).
- **Handoff state**: the ledger IS the memory — a fresh process rebuilds all causality, precedent, and learning from records.
- **Replaceable**: weights, decay rates, and ceilings are data tables, not code paths.

## Orthogonal closures

Verified by `closure/kernel_registry.py` → module `memory`.
