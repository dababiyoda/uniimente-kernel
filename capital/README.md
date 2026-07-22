# Regenerative Treasury

## Purpose

Route legally deployable surplus through the declared allocation waterfall while preserving obligations, reserves, balanced books, and regenerative repair.

## Buildability contract

- **Existing mechanism:** `allocation-policy.yaml`, Evidence Ledger, double-entry postings, and regenerative-debt controls.
- **Defined interface:** `allocate`, `post`, `post_regenerative`, `record_debt`, `blocks`, and `repay_debt`.
- **Bounded authority:** accounting and recommendations do not authorize movement of funds; human and Gate approval remain required.
- **Available dependencies:** PyYAML, canonical allocation policy, and an append-only ledger.
- **Security model:** restricted funds remain separate; unknown tiers, negative amounts, self-postings, and waterfall skipping fail closed.
- **Failure modes:** insufficient surplus, underfunded higher tiers, invalid postings, policy mismatch, missing repair evidence, or unresolved debt.
- **Acceptance tests:** waterfall ordering, zero trial balance, blocked lower tiers, debt-gated expansion, and evidence-based repayment.
- **Recovery path:** stop allocation, preserve the shortfall event, reconcile balances, repair debt, and rerun from a known policy version.
- **Resource ceiling:** available unrestricted surplus and the requirements declared for each ordered tier.
- **Operating cost:** accounting, compliance, reserve, reconciliation, and transaction costs are explicit obligations.
- **Legal operator:** a named authorized human or lawful treasury entity, never UNIIMENTE.
- **Handoff:** signed allocation decision, balanced postings, evidence receipts, and unresolved obligations.
- **Replaceable:** custody, banking, payment, and ledger implementations may change behind the stable policy contract.
