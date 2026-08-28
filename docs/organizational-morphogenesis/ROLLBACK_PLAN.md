# Rollback Plan

Rollback is fully possible because Phase 1 is inert.

1. Before merge: close the draft PR. No canonical branch changes.
2. After a future merge but before consumers: revert the three contracts,
   their test and linked documentation in one scoped commit.
3. After consumers: first disable consumers and restore the existing static
   DurableWorkflow/organ baseline, then revert schemas only after dependency
   inventory confirms no orphan references.
4. Preserve the intent record, deliberation, negative evidence and reason for
   rollback as historical artifacts.

Rollback triggers include founder rejection, semantic ownership conflict,
parallel runtime/authority creation, inability to fail closed, or any evidence
that the schemas make the canonical static path harder to operate.
