# Residual cognition safeguards — 2026-10-13

Four verifier and legitimacy defects were reproduced on the Mind frontier
(`claude/greg-polyintelligence-mind`, reproduced at `d57d47e`; the touched files are
unchanged at `0f4bc52`, the base of this change), then fixed, tested, and attacked with mutants.

## Reproduced before the fix (`reproduction-before-fix.log`, `.json`)

| Lie or assertion | Verdict before | After |
|---|---|---|
| CP-SAT says OPTIMAL for an assignment that is only feasible | STRUCTURALLY_VERIFIED | REFUTED: Z3 finds a strictly better integer assignment |
| CP-SAT says INFEASIBLE for a feasible model | STRUCTURALLY_VERIFIED | REFUTED: Z3 finds a feasible integer assignment |
| Z3 reports an unsat core naming a satisfiable subset | STRUCTURALLY_VERIFIED | REFUTED: a fresh solver finds the subset satisfiable |
| Protection intervention with bare `lawful: true, consent: true` | permitted (not blocked) | blocked: law and consent gates `unresolved` |

Before the fix, the verifier checked only substitution and artifact consistency for these
statuses. Its own dissent said "no independent infeasibility certificate is established".
The protection solver is registered on this frontier but not attached, so the fourth defect
was latent on the live path. The tests call `greg.cognition.protection.assess` directly, and
attaching it remains the founder's decision.

## What changed

- `greg/cognition/verification.py`. A second engine now checks each claim:
  - **OPTIMAL:** Z3 re-checks the integer model and asks for a strictly better assignment.
  - **INFEASIBLE:** Z3 is asked for any feasible assignment.
  - **Unsat cores:** a fresh Z3 solver re-checks the core and tests minimality by deletion.

  Each result is `sat`, `unsat` or `None`. `None` means the engine is missing, has timed out,
  or the model is not integral, and it is listed under `inconclusive` with a dissent line; it
  is never counted as a pass. The verifier also discloses its limits:
  - two engines agreeing is corroboration, not a proof certificate;
  - the core re-check uses the same engine as the solver;
  - a valid but non-minimal core is called out;
  - FEASIBLE is never reported as OPTIMAL.
- `greg/cognition/legitimacy.py` (new): evidence-backed gates for law, consent, rights and
  authority.
  - **States:** `supported`, `prohibited`, `unresolved` and `not_applicable`.
  - **Permission:** each gate accepts only certain origins:
    - law: a `qualified_human` or a `kernel_policy_engine` decision, and always with a named
      reviewer;
    - consent: supported only by `consent_capture` (a policy engine may exempt it or
      prohibit it, never supply it);
    - rights: a qualified human or Kernel policy;
    - authority: founder-signed, Kernel grant or Kernel policy.
  - **Context-only origins** (model interpretation, proof artifact, confidence, benchmark,
    self-assertion) never settle a gate. A prohibition reported by such a source makes the gate `unresolved`.
  - **Expiry:** expired records stop counting.
  - **Missing prohibition:** this is not permission. A consequential action needs every gate
    `supported` or `not_applicable`.
- `greg/cognition/protection.py`: interventions are gated by those records. `lawful: false`
  or `consent: false` is still a hard block. `lawful: true` alone permits nothing.

## Tests and attacks

- `tests/unit/test_cognition_residual_safeguards.py`: 8 tests covering:
  - the three lies;
  - core minimality;
  - shared-engine disclosure;
  - a missing engine reported as inconclusive and never a pass, with no integer truncation;
  - the bare assertion blocked;
  - records that unblock, prohibitions that still block, and expiry;
  - typed records, where context never settles a gate.
- `scripts/ci/check_cognition_residual_mutants.py`: 7 mutants, all caught (`mutants.log`).
  Each one disables a single safeguard in an isolated copy and requires a targeted test to
  fail. The existing `check_greg_cognition_mutants.py` still catches 6 of 6.
- `.github/workflows/canonical-ci.yml`: one step runs both of the above.
- `full-suite.log`: the whole frontier suite on the final tree.
- `frozen-comparison.json`: the Seed Genome 120-case frozen comparison, run with and without
  this change at the same base commit. It compares the timing-independent fields.

## Not claimed

- The checks show that two engines agree. They do not provide a proof certificate (no
  DRAT/LRAT or LP dual certificate is produced).
- A supported legitimacy record is only as good as the decision it points to. This code
  checks origin, reviewer, scope and expiry. It cannot authenticate counsel or a consent
  ledger, and it creates no authority (`authority_created: false`).
- No model or paid route was used. Nothing was attached, activated, merged or deployed.
  VEPMC is unchanged at 0.
