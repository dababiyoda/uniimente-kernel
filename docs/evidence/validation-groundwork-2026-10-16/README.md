# Foundry #9/#10 validation groundwork: preserved, inactive, unvalidated

Status: **preserved, inactive, not validated.** Nothing here is applied, imported or run.

- Source: stash `greg-validation-grant-wip-2026-10-16` (commit `2785f0ee`), made on
  `claude/greg-whole-machine-convergence` at `46719e4`, exported as `tracked.patch` and `untracked.patch`.
  Both apply cleanly to `46719e4` (`git apply --check`) and are not applied.
- Review outcome: the proposed `VALIDATION_GRANT` command kind is **not restored**. It would duplicate the canonical
  authority path (founder-signed MISSION light cone, exact-scope DECISION, single-action Kernel grant, Consequence
  Gate), it lacked revocation and an enforced run count, it widened device delegation, and it has no consumer.
- Further work on #9/#10 validation is stopped by a safety restriction reported in this session. It is recorded as
  blocked; no alternative route is proposed here.
