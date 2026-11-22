# Cortex 0.2.3: optimality proofs are bound, and only a conclusive engine confirms

Source: findings 4 and 5 of the independent convergence review on #196 (comment 6934260821, 2026-11-17). Findings 1,
2, 3 and 6 were claimed by `session_0174qtqgRsbJVdBkBitTyxkf` on its own lineage branches (#96 comment 6934306349)
and are not part of this change.

## What changed

**Finding 4.** The adversarial verifier accepted a solver's native `OPTIMAL` status as sufficient proof of an
optimum, and the Z3 optimality certificate carried nothing tying it to the answer it vouched for.

- `cortex/organs/cpsat.py`: `z3_optimality_certificate` now records a `binding` on every outcome (CERTIFIED,
  REFUTED, UNKNOWN, NOT_RUN): the model's digest, the objective value and the sense.
- `cortex/organs/adversarial.py`: the optimality obligation is "no feasible assignment is strictly better". It is
  independently discharged only by the formal engine's own UNSAT proof, or by a CERTIFIED certificate bound to this
  model, this objective value and this sense.
  - A certificate that binds a different claim, or none, is a critical finding (`certificate_does_not_bind_answer`).
  - A native `OPTIMAL` alone stays acceptable but is reported as a major, non-blocking finding
    (`optimality_not_independently_certified`).

**Finding 5.** A second engine's matching answer was recorded as confirmation whatever its state, and an engine that
returned nothing was labelled a disagreement.

- `cortex/routing.py`: only a conclusive second answer (state `OK` or `WORLD_UNVERIFIED`) confirms or contests.
- Anything else is recorded as `confirmation_inconclusive`; the attempt is labelled `inconclusive`, and the lead
  verdict stays unconfirmed.
- One exception keeps the safer direction: an inconclusive engine's feasibility witness that the solver-independent
  evaluator accepts still refutes an impossibility verdict (`engine_disagreement.witness_checked`).

## Evidence

- `tests/unit/test_cortex_proof_acceptance.py`: 16 tests. Copied unchanged onto `12119590`, 13 fail and 3 pass. The
  3 that pass guard behaviour the old code already had: conclusive confirmation, conclusive disagreement, and a
  CERTIFIED certificate accepted as proof (the old code accepted any certificate; the new code accepts only a bound
  one).
- `cortex/evaluation/freeze-v0.2.3.json`: a new manifest for the new version. `freeze-v0.2.2.json` and its results
  are kept unchanged. The 0.2.3 manifest was regenerated once before publication, because a later edit to
  `adversarial.py` (keeping 0.2.2's critical rule for a claimant with no basis of its own) changed a frozen file; the
  first manifest (`sha256:7978525e...`) was never committed.
- `cortex/evaluation/seed_genome/freeze-v13.json`: the Seed Genome re-sealed; its only changed input is
  `cortex/contracts.py` (the version). v12 is kept.
- The existing rule is unchanged: a route that claims an optimum with neither its own UNSAT proof nor a native
  `OPTIMAL` status is critical (`optimality_claim_without_proof`), even if another engine later certifies the value.
- `scripts/ci/check_cortex_mutants.py`, group "proof acceptance": seven mutants, one per new safeguard.
- `heldout-results.json`: the held-out partition `heldout-v0.1` (42 items) was **already observed** under 0.2.1 and
  0.2.2. This run is a regression check, not a fresh claim. Every item's disposition, state, outcome and score
  equals the 0.2.2 record; routed mean quality 0.964, 0 critical errors. The model baselines were not run (no local
  model), as before.

## Not claimed

No new capability, admission or attachment. No authority, spend, contact or merge. VEPMC 0.

## Rollback

Revert the commit. `freeze-v0.2.2.json` and the 0.2.2 evidence remain valid for the 0.2.2 code.
