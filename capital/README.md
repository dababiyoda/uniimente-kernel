# capital

The Regenerative Treasury: capital metabolism, executable, over the
declarative policy files in this directory.

## Contents

- `allocation-policy.yaml` — the law: the 11-tier priority waterfall
  (fund in order; never skip upward to fund downward), fund separation,
  conversion chain, portfolio-governor formula.
- `liquidity-policy.yaml`, `concentration-limits.yaml`,
  `acquisition-gates.yaml` — declarative capital rules.
- `treasury.py` — the executor: loads the waterfall FROM the yaml
  (code holds no opinion about the order), flows surplus tier by tier,
  stops at the first underfunded tier and records what went unfunded.
  Double-entry postings with a permanently zero trial balance; sign
  games, zero-amount and self-postings refused. Five regenerative
  accounts (Alfonso sovereignty, institutional resilience, productive
  capital, participant capability, wider system health) as a closed
  set. Regenerative debt — attention drain, relationship damage,
  externalized risk, depleted capacity — blocks autonomy promotion,
  budget expansion, and replication until repaid with evidence of
  repair. The accounts exist to BLOCK things; accounting that never
  blocks anything is decoration.

## Buildability standard (14 conditions)

- **Existing mechanism**: double-entry accounting and priority waterfalls — centuries old; no novel science.
- **Defined interface**: `RegenerativeTreasury.allocate/post/post_regenerative/record_debt/blocks/repay_debt/trial_balance`.
- **Bounded authority**: the treasury allocates and blocks; it moves no external money (that is a gate action); the waterfall order is read-only law from the yaml.
- **Available dependencies**: Python 3 stdlib + pyyaml + the provenance ledger.
- **Security model**: every movement is a balanced posting and a ledger event; the order cannot be redefined at runtime; repayment requires evidence, not intention.
- **Failure modes**: `TreasuryError` (negative surplus, unknown tier, sign games, self-posting, unknown debt kind, evidence-free repayment); all fail closed.
- **Acceptance tests**: `tests/unit/test_treasury.py` (14 tests, adversarial suite included).
- **Recovery path**: balances and debts reconstruct entirely from ledger events; the yaml is version-controlled law.
- **Resource ceiling**: allocation is O(tiers); postings are constant-time; no unbounded state.
- **Operating cost**: constant ledger appends per posting/allocation.
- **Legal operator**: Alfonso (owns the waterfall; amendments follow constitutional process).
- **Handoff state**: the yaml + the ledger's treasury events are the complete handoff.
- **Replaceable**: the executor can be rewritten in any language against the same yaml and event vocabulary without changing the law.

## Orthogonal closures

Verified by `closure/kernel_registry.py` → module `treasury`.
