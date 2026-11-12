# Operational slice: pre-registration of the second case (2026-11-12)

Declared in the first commit of branch `claude/operational-slice-request-case-20261112`, before any case-1 test
passes and before any second case exists. Case 1 and every file named here are synthetic. Case 2 is built by another
worker from withheld fixtures; this branch does not build it.

- **Claim to be tested:** a second, materially different request-led case (a subcontractor's progress-payment draw:
  contract schedule, pay application, inspection sign-off, lien waiver; rules for percent complete, retainage and
  waiver of the prior draw) can be processed by `case.assess` (`greg/cases.py`) and the `request-case` mission
  template (`greg/templates.py`) with a new rulebook and documents only.
- **Measures:** (1) product lines changed between the case-1 commit (the last commit of this branch, whose SHA its
  handoff reports) and case-2 passing, outside fixtures and rulebooks; (2) founder asks raised per adverse case,
  case 2 against case 1; (3) on adverse cases written by someone who has not seen the implementation, the share
  classified as the rulebook requires.
- **Baseline:** a single-purpose script for case 2 alone, written without the mechanism. If it classifies the
  withheld cases as well and costs fewer lines than the changes case 2 needed, the simple script is retained for that
  task and the transfer claim fails.
- **Success:** zero product lines for (1) or a stated small number with each line explained; (3) no worse than the
  baseline; no unknown reported as pass or fail in either.
- **Not claimed:** that the rulebooks describe any real payer; any external validation; any payment.
