# Recursive Collaboration Protocol

This protocol turns collaboration, dissent, and founder-intent preservation into an auditable institutional process.

## 1. Required review roles

Every material architectural change must receive explicit analysis from five roles. One person may perform multiple roles, but each perspective must be recorded separately.

1. **Builder** - strongest implementation case.
2. **Adversary** - strongest failure, abuse, drift, and counterexample case.
3. **Operator** - deployment, maintenance, observability, recovery, and cost.
4. **Beneficiary Representative** - participant welfare, accessibility, dignity, and externalities.
5. **Constitutional Reviewer** - authority, evidence, legality, reversibility, and shutdown integrity.

Disagreement is preserved. Consensus is not manufactured.

## 2. Mandatory alternatives

Every proposal must compare at least:

- proposed design;
- simplest viable design;
- strongest competing design;
- do-nothing / preserve-current-state option;
- staged or reversible experiment.

Each alternative records benefits, liabilities, evidence, dependencies, migration cost, rollback path, and kill criteria.

## 3. Two upward passes

A proposal cannot be marked ready until it completes exactly two strengthening passes.

### Pass 1 - structural inversion

For every advantage:

- identify how it can become a moat, default pathway, interoperability advantage, proof advantage, cost advantage, or participant-welfare flywheel;
- identify the condition under which the advantage reverses into a liability.

For every disadvantage:

- remove it;
- bound it;
- make it observable;
- make it reversible;
- or convert it into a useful constraint, test, modular boundary, market signal, or governance advantage.

### Pass 2 - adversarial compounding

Re-attack the strengthened design as though Pass 1 were already deployed.

- Find new concentration, complexity, incentive, authority, security, maintenance, adoption, and evidence risks.
- Strengthen the design again.
- A Pass-1 downside may not disappear from the record. It must be resolved, accepted with a named owner and threshold, or converted into a kill condition.

## 4. Merge proof

A material change is mergeable only when the record contains:

- founder-intent references;
- system boundary affected;
- all alternatives;
- five-role debate;
- Pass 1 and Pass 2 maps;
- explicit unresolved dissent;
- evidence and counterevidence;
- tests and verifier strength;
- migration and rollback plan;
- operational owner;
- kill criteria;
- decision: `retain`, `regress`, `kill`, `defer`, or `experiment`.

No document, model output, majority vote, reputation score, or reviewer enthusiasm authorizes production effects. The Consequence Gate and human constitutional authority remain final.

## 5. Collaboration norms

- Critique claims and mechanisms, not people.
- Steelman before rejecting.
- Preserve contributor lineage and rejected branches.
- Prefer narrow contracts over duplicated implementations.
- Prefer reversible experiments over argument when the decisive uncertainty is testable.
- Escalate irreducible value conflicts to the founder.
- Record negative and zero results.
- Never hide scope, assumptions, unresolved risk, or contradictory evidence.
- Optimize for shared capability and market health, not collaborator dependence.

## 6. Recursive application

This protocol applies to itself. At each major release, audit whether it improves decision quality, contributor comprehension, cycle time, defect escape rate, duplicated work, and founder-intent fidelity. Retain, revise, or regress it based on measured outcomes.

## 7. Provider-change intake and execution

Provider release notes, status notices, prices, and policies are evidence inputs, not authority grants. A provider change cannot by itself alter founder intent, the Consequence Gate, canonical ownership, or production configuration. Wire-format compatibility with an OpenAI, Anthropic, or other provider protocol does not prove semantic parity and must not create a second runtime.

### 7.1 Weekly official-source review

At least weekly, review official release notes, technical documentation, deprecation notices, pricing, policy, and status communications for every active or approved model provider. Report a finding only when it can materially affect one or more of:

- model, endpoint, SDK, tool, file, or feature availability;
- request, response, streaming, usage, finish-state, reasoning, or tool-call semantics;
- authentication, workload identity, permissions, retention, processing geography, or data residency;
- price, quota, rate limit, cache behavior, or session-runtime cost;
- policy or terms governing an existing or proposed UNIIMENTE use;
- outage behavior that can make task completion ambiguous or cause unsafe retry or failover;
- prompt, tokenizer, context-window, or model behavior relied on by a contract, evaluator, or cross-model handoff.

A no-material-change run produces a short no-change brief and no repository change.

### 7.2 Required change packet

Every material finding must record:

- provider, official source URL, observation time, publication date, effective date, and last-known-good baseline;
- exact affected model, endpoint, SDK, beta header, tool, file shape, status component, price, or policy clause;
- direct exposure in each canonical UNIIMENTE repository, cited by path and commit, or an explicit `prospective_only` finding;
- a compatibility diff covering request and response shapes, tool and file semantics, streaming and usage accounting, error and retry behavior, and model or prompt behavior;
- impact on one-source-of-truth, authority, replay, retry and idempotency, evaluator independence, and no-duplicate-runtime constraints;
- owner, deadline, tests, staged migration, rollback, and kill criteria.

Provider documentation establishes what the provider claims. It is not evidence that UNIIMENTE's integration works. Contract fixtures, deterministic replay, sandbox execution, and independent evaluation establish integration behavior.

### 7.3 Execution rules

1. Change the narrow provider adapter, fixture, or compatibility contract. Do not fork the canonical workflow, task fabric, authority path, event spine, or evidence ledger.
2. Reuse canonical workflow and task identities, leases, idempotency keys, and receipts. A provider-native agent, session, thread, queue, or memory store is never a second source of truth or an independent scheduler.
3. Treat mutable model aliases and unversioned protocol behavior as unpinned dependencies. Promote a change only through a reversible experiment with captured fixtures and declared behavioral baselines.
4. Protocol compatibility is transport compatibility only. Each provider still requires capability, tool-semantics, error-semantics, and output-contract tests.
5. A timeout, disconnect, or provider error after dispatch is an ambiguous completion. Do not retry or fail over an effectful task until the canonical receipt and idempotency record prove that the prior attempt is absent or safely resumable.
6. Preserve the raw provider response and the mapped canonical event. No adapter may silently fabricate, discard, or reinterpret authority-bearing fields.
7. The provider or model under test cannot authorize its own promotion and cannot be the sole evaluator of the change. Use deterministic checks or an independent evaluator with recorded identity and evidence.
8. A scheduled reviewer may read official sources and repositories, and may prepare documentation, fixtures, tests, or adapter changes on a dedicated branch and draft pull request when current human authorization permits. It may not write to a default branch, merge, change production routing or credentials, expand authority, or create a parallel runtime.
9. Use the protocol's existing decision states: `retain`, `regress`, `kill`, `defer`, or `experiment`. Vendor urgency is evidence for the decision; it is not a new authority state.

### 7.4 Incident and recovery discipline

When an official status communication reports degradation:

- circuit-break only the affected adapter or capability;
- distinguish failure before dispatch, ambiguous completion, and completion with a valid receipt;
- keep canonical work replayable without issuing a second external effect;
- degrade only to a pre-approved provider or deterministic fallback, preserving provider and evaluator lineage;
- treat provider recovery as permission for a canary, not automatic promotion; and
- record negative and zero results, including disconnected sessions and failed retries.

If an emergency response would alter authority, production routing, external-effect policy, or the protected runtime, stop at `NEEDS_FOUNDER_DECISION`.
