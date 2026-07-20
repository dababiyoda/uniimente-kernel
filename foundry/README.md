# foundry

Phase 6 — AI Influencer Company Foundry + Rabbit Hole Engine: synthetic
media companies as complete, chartered, gate-governed organs.

## Organs

- `territory.py` — Territory Graphs: a knowledge domain as a DAG of
  questions rooted at one entry node. Explicit doors (interlinks in the
  content, not hoped for in the algorithm), exactly one owned exit onto
  owned ground, Reality Gradient evidence levels, expiry dates, and a
  PUBLIC correction layer (corrections and retirements are ledger
  events). Nodes below the evidence floor, stale, or retired refuse to
  publish. Draft floor 3 nodes; production territories are 50–300.
- `company.py` — MediaCompanyCharter: identity, visual canon, editorial
  constitution (8 required rules including no outrage optimization, no
  exploitation of vulnerable attention, no fear-based retention hooks,
  standing correction obligation), narrative world, owned hub,
  subscriber list, products, community. Synthetic disclosure is
  mandatory: agents identify as machines everywhere, always. Charters
  are hash-bound to human ratification — an edited charter is an
  unratified charter. Every publish routes through the Consequence Gate
  as `external_contact`.
- `distribution.py` — the Distribution Loop measured: narrative →
  qualified attention → owned relationship → useful action → measured
  value. Ranking metric is informed return (useful actions per returning
  visitor), never watch time. Impressions-without-relationships is the
  canonical FALSELY_CLOSED verdict; impression growth with zero behavior
  change trips the organ's kill condition.

## Buildability standard (14 conditions)

- **Existing mechanism**: directed graphs, content hashing, ledger events — no novel science.
- **Defined interface**: `CompanyFoundry.submit_charter/publish`, `TerritoryGraph.add/validate/publishable`, `DistributionLoop.open_window/evaluate`.
- **Bounded authority**: the foundry can refuse but never execute; external effects exist only through the Consequence Gate; charters activate only by human ratification.
- **Available dependencies**: Python 3 stdlib + kernel modules (loom ratifier, policy gate, provenance ledger).
- **Security model**: hash-bound ratification (any edit invalidates), synthetic disclosure enforced structurally, publishes carry evidence refs and pass full gate revalidation.
- **Failure modes**: `TerritoryError`, `FoundryError` (unratified/edited charter, stale/weak/retired node, invalid graph); all fail closed.
- **Acceptance tests**: `tests/unit/test_foundry.py` (23 tests, adversarial suite included).
- **Recovery path**: corrections revise publicly; retirements preserve negative evidence; the territory rebuilds from ledger events.
- **Resource ceiling**: production territories capped at 300 nodes; distribution windows are bounded counters.
- **Operating cost**: constant ledger appends per publish/correction; one gate run per publish.
- **Legal operator**: Alfonso (never UNIIMENTE — refused at validation).
- **Handoff state**: charter hash + territory graph + ledger events reconstruct the company without hidden context.
- **Replaceable**: platforms, executors, and personas are parameters; the charter and territory survive any platform loss (owned exit is the asset).

## Orthogonal closures

Verified by `closure/kernel_registry.py` → module `foundry`.
