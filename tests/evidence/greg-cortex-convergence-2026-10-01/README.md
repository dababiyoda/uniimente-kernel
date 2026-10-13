# Cortex convergence onto #140 — preserved as evidence (2026-10-01 → 2026-10-13)

**Status:** `RETAIN_AS_EVIDENCE`. This work is superseded as an active path. It is kept so its mechanisms,
tests and negative results stay recoverable from git rather than from a reclaimed container.

## What it was

On 2026-10-01, before the Claude Mind frontier existed (#143 → #155 → #158), this branch converged the
cortex seed lineage (#141) onto the codex cognition PR #140 (`3ced61d`). It added:

- typed outcomes, a budget, a pipeline and an advantage module;
- evidence-backed legitimacy gates;
- Z3 cross-checks on CP-SAT optimality and infeasibility, and on unsat cores;
- a rehearsal through GREG's real entry points under kills;
- an evaluation harness.

The frontier then implemented most of the same directive independently. Continuing here would
have made a third parallel cortex path, which the build order forbids.

## Disposition of each component

| Component | Disposition | Where the effect lives now |
|---|---|---|
| `greg/cognition/gates.py` (law, consent, rights, authority) | EXTRACT, ported | `greg/cognition/legitimacy.py`, #161 (stacked on #158) |
| Cross-engine checks in `verification.py` | EXTRACT, ported and hardened (deadline, minimality cap, inconclusive reporting) | same PR |
| `settlement.py` logical-key reconcile (uncommitted fix) | RETAIN_AS_EVIDENCE | fixed independently on the Claude frontier (`settlement.py` revision/supersedes keys) |
| `outcomes.py` | SUPERSEDED | `greg/cognition/seed_path.py` outcome taxonomy |
| `budget.py` | SUPERSEDED | `greg/cognition/budget.py` (metered spend, #155) |
| `pipeline.py` | SUPERSEDED | `greg/cognition/composition.py` and `compiler.py` (P6, Layer 5) |
| `advantage.py` (Pareto frontier after gates, ±25% weight perturbation) | SUPERSEDED | `foundry/lawful_leverage.py` (gates not weights, Pareto frontier, adversarial sensitivity) |
| `tests/integration/test_greg_cognition_rehearsal.py` | RETAIN_AS_EVIDENCE | frontier rehearsal evidence `tests/evidence/greg-cortex-rehearsal/` |
| `greg/cognition/evaluation.py` and `examples/cognition/eval-v1/` (dev 22, held-out 120, adversarial 18 items) | RETAIN_AS_EVIDENCE | frozen Seed Genome 120-case comparison on the frontier |

## Negative and incomplete results kept

- **The evaluation was never frozen and the held-out partition was never run.** `dev-results.json` is
  development data: the arms were adjusted after seeing it (the static router was given the scope rule).
  It is **not evidence of routing gain**.
- **Defect found in #140, still present at the codex frontier head (#159, `e125168`); low severity.**
  Reconcile is keyed by `observation_event`. When one logical outcome is observed twice, the result is
  two `cognition.settled` records with no `outcome_id` and no `supersedes` link, so a journal reader
  cannot tell which one is current.
  - **Not double-counted:** competence still counts the outcome once, because it is recomputed from
    observations.
  - **No current consumer:** nothing on #159 reads the settled records except `reconcile` itself.
  - **The Claude frontier differs:** the same input also yields two records, but the second is an
    explicit revision (same `outcome_id`, `supersedes` the first).
  - **Idempotence:** on both frontiers, a third reconcile adds nothing.

  Evidence: `codex-frontier-settlement-repro.log`. This branch's own fix (skip when correctness is
  unchanged) and its test (`test_duplicate_outcome_delivery_settles_once`) are preserved. The
  frontier's revision chain is the stronger design, because it also records re-observations.
- **Rehearsal assumption corrected.** The rehearsal at first assumed an action. A pipeline sensor
  closes the mission without one, so the invariant became one closure, a retained receipt, and a
  truthful WAITING blocker after detach.

## Reproduce

```
python -m pytest -q tests/unit/test_greg_cognition_convergence.py tests/integration/test_greg_cognition_rehearsal.py
python -m greg.cognition.evaluation run --partition dev --out dev-results.json
```

Nothing here is attached, activated, merged or deployed. Authority delta: none. VEPMC: 0.
