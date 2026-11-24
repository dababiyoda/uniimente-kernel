# Provider change review — 2026-11-17

Window: 2026-11-10 17:41 UTC through 2026-11-17 17:41 UTC. Only material changes are recorded. Provider documentation establishes provider claims, not verified UNIIMENTE behavior.

## Decision

**NEEDS_FOUNDER_DECISION.** Add this evidence packet and its machine-readable deliberation to draft PR #105; leave `docs/RECURSIVE_COLLABORATION_PROTOCOL.md` unchanged. Existing section 7 already requires exact provider contracts, leased provider state, canonical receipts and idempotency, receipt-gated recovery, independent evaluation, bounded credentials/data scope, complete cost accounting, and one canonical runtime. No provider feature, account setting, credential, route, or authority is adopted.

## Default-branch exposure

| Repository | Inspected default head | Direct exposure |
|---|---:|---|
| `dababiyoda/uniimente-kernel` | `d64a6c931bb05aba4e3454847b665e73384bbdfa` | Local/loopback model route; no Anthropic linked-billing policy, self-hosted Managed Agents service, OpenAI Workspace Agent, provider Costs API, or Kimi runtime found. |
| `dababiyoda/DALEOBANKS` | `667439f49442bd898d3655666a389f53114f1412` | Local by default; optional OpenAI `gpt-4o-mini` Chat Completions and `text-embedding-3-small`. No reviewed incident directly named these routes this week. |
| `dababiyoda/WealthMachineIntelligence` | `ec82b8027d987c865dc123215afb53d20916908f` | No direct OpenAI, Anthropic, or Kimi runtime route found. |
| `dababiyoda/PumpStation` | `db6758dfa8621a4f6fb0504c20343e60db5336c1` | No direct OpenAI, Anthropic, or Kimi runtime route found. |

Exact default-branch searches returned no `billing_policy`, `user-profiles-billing-2026-10-01`, Anthropic self-hosted Managed Agents service, Claude Managed Agents database or worker, OpenAI Costs API consumer, Moonshot endpoint, or Kimi model. References to managed agents in prose and Claude collaboration provenance do not constitute provider runtime adapters. Repository inspection cannot establish non-repository account use.

## Material changes and bounded response

### Anthropic linked billing beta — released 2026-11-17

Anthropic introduced linked billing for apps. A customer can link its direct-billed Claude organization to an application, set an app spend cap, and later unlink it. Once linked, the application selects the payer on every `/v1/messages` or `/v1/chat/completions` request through `billing_policy` under beta header `user-profiles-billing-2026-10-01`. The feature applies only to organizations that pay Anthropic directly. Official sources: https://platform.claude.com/docs/en/release-notes/overview and https://platform.claude.com/docs/en/manage-claude/oauth-apps/organization-billing-connections

- **Canonical authority / one source of truth:** a provider billing connection, payer selection, spend cap, or organization identity is subordinate contract evidence. It cannot redefine the canonical task, actor, grant, budget owner, customer consent, legal responsibility, or cost ledger.
- **Provider contract:** bind every attempt to the exact beta/API version, application identity, opaque billing-connection identity and version, payer policy, customer organization, effective cap, model, region, and canonical task/attempt. Do not infer contract terms from public documentation for a particular customer.
- **Replay / retry / idempotency:** retry under the original canonical idempotency identity and the same authorized payer. An unlink, cap change, authorization change, or missing `billing_policy` is a contract transition—not permission to silently charge the app, switch organizations, or replay under another payer. Reconcile provider receipts before retrying an ambiguous request.
- **Evaluator independence:** the provider's link status, cap display, usage response, or invoice cannot solely certify correct payer allocation. Reconcile request receipts, canonical budget events, customer records, and independent billing evidence.
- **Credentials / data residency:** linking requires separate customer consent and least-privilege OAuth/administrative scope. Separate app credentials from customer billing authorization; record revocation and unlink postconditions. Billing linkage does not prove model-processing region, retention, or ZDR eligibility.
- **Cost:** attribute tokens, tools, retries, credits, taxes, and corrections to both the canonical work item and authorized payer without double booking. A provider cap is a guardrail, not the canonical budget or complete cost ceiling.
- **No duplicate runtime:** payer selection and spend enforcement remain adapter functions. Provider billing state may not become a second identity, authorization, scheduling, retry, or cost-control runtime.
- **Next step:** no account or code action. Any proposal must start with a founder-approved, read-only contract and consent design; explicit no-fallback payer semantics; disconnect/cap/error/idempotency fixtures; independent invoice reconciliation; residency/retention review; and rollback to application-paid billing without orphaning canonical receipts.

### Anthropic self-hosted Managed Agents — released 2026-11-12

Anthropic made the Managed Agents service available for self-hosting. Operators run the service/API, agent loop, session history, database, workers, and sandboxes on their infrastructure while model inference can remain at Anthropic or another chosen provider. PostgreSQL 16+ provides persistence; without it, state is in memory and restart erases it. Workers poll the service and run shell/file tools, and Anthropic states that the worker itself does not provide isolation. Deployments use separate server API, inference, and environment credentials. Model calls transmit conversation content, tool inputs/results, and session, agent, and environment identifiers to the inference provider. Official sources: https://platform.claude.com/docs/en/release-notes/overview and https://platform.claude.com/docs/en/managed-agents/self-hosted

- **Canonical authority / one source of truth:** self-hosting changes custody, not authority. Managed-agent sessions, histories, database rows, environment IDs, queues, and worker state remain leased execution artifacts subordinate to UNIIMENTE canonical tasks, events, grants, evidence, and receipts.
- **Provider contract:** pin the service version and license, API behavior, inference provider/model, database schema, queue/worker topology, sandbox image, tool manifest, network policy, and persistence mode. A compatible API does not establish equivalent security, durability, replay, or semantics across hosted and self-hosted modes.
- **Replay / retry / idempotency:** in-memory loss, worker polling, restart, partial tool execution, and database/queue races can make completion ambiguous. Every session, phase, worker, model call, and tool effect needs a canonical attempt identity and receipt; reconcile effects before rescheduling. Never reconstruct canonical history solely from the Managed Agents database.
- **Evaluator independence:** the acting agent service, its inference model, and its database cannot solely certify completion or safety. Use deterministic postconditions and an evaluator outside the candidate execution route.
- **Credentials / data residency:** separate server, inference, environment, database, and worker credentials; isolate shell workers in containers or VMs; restrict network and filesystem access. Self-hosted session storage does not imply local inference, ZDR, or single-region processing because model traffic and identifiers can leave the deployment.
- **Cost:** account for servers, PostgreSQL, backups, workers, sandbox compute, egress, inference, tools, observability, security operations, incident recovery, and duplicate/abandoned work. Compare total cost and operator burden against the existing local-first runtime.
- **No duplicate runtime:** the service's agent loop, database, session history, queue, and workers must not become a parallel scheduler or source of truth. Adoption is prohibited unless it replaces or is strictly leased beneath the canonical runtime with one consequence, receipt, and retry plane.
- **Next step:** no adoption. A future proposal needs founder-approved architectural necessity and license review; an explicit replace-versus-adapter decision; isolated offline fixtures for restart, duplicate delivery, partial tool effects, database loss, queue races, and credential revocation; residency/retention proof; complete cost baseline; independent evaluation; migration/rollback; and kill criteria that stop any second scheduler.

### Material provider incidents — 2026-11-11 through 2026-11-17

Official status communications reported: OpenAI Workspace Agents unable to start new runs on November 12 and delayed Costs data in the Compliance API on November 16; Anthropic elevated errors for Sonnet 5.5 and Fable 5.2 on November 16 and a Claude Meetings joining incident still under monitoring at the review snapshot; Kimi TTFT delays for K2.8 Preview, K2.7 Code Highspeed, K3, and K2.8 Preview on November 11, 14, and 17. Official sources: https://status.openai.com/history, https://status.claude.com/, and https://status.moonshot.cn/

- **Direct exposure:** no affected Workspace Agent, Compliance Costs, Anthropic, Meetings, or Kimi runtime was found on the four default branches. DALEOBANKS' optional OpenAI Chat Completions and embeddings routes were not named in these incidents.
- **Authority / one source of truth:** a provider failure, recovery notice, cost dashboard, meeting transcript, or status page is evidence—not proof that an individual run, tool effect, charge, or record exists or is absent.
- **Provider contract / replay / idempotency:** start failures and high TTFT can leave dispatch ambiguous. Retain the original canonical idempotency identity, reconcile receipts and effects before retry/failover, and record each subordinate attempt, partial result, and cost separately.
- **Evaluator / credentials / residency:** use an independent health check and only pre-approved routes. An incident does not authorize new regions, providers, credentials, or data scopes.
- **Cost / no duplicate runtime:** delayed cost data must not close canonical budgets; append later corrections with lineage. No provider-side recovery poller, auto-retry service, or failover scheduler may become a second runtime.
- **Next step:** existing section 7 incident rules are sufficient. Carry agent-start, missing-cost, elevated-error, meeting-ingestion, and TTFT fixtures into any future adapter; make no runtime change now.

### No other material platform change in the window

OpenAI's API changelog added a specialized CSAM-moderation model on November 16, but no relevant moderation or media-safety route exists in the inspected repositories and the release does not alter current collaboration or agent contracts. Kimi's platform changelog still lists October as its latest release group; no new Kimi release, pricing, policy, or deprecation crossed the materiality threshold. Official sources: https://developers.openai.com/api/docs/changelog and https://platform.kimi.ai/docs/platform-changelog

## Alternatives, dissent, and exactly two strengthening passes

Baseline: local-first default routes; one optional legacy OpenAI surface; no Anthropic/Kimi runtime; and provider-neutral controls in draft section 7.

Alternatives considered: (1) brief only and no repository change; (2) add two dated evidence files; (3) add vendor-specific protocol clauses; (4) adopt linked billing or self-hosted Managed Agents; (5) let provider billing/session/queue state own identity, authority, scheduling, retry, or cost. The strongest competing architecture centralizes orchestration and payer enforcement in the provider service; it is rejected because it duplicates canonical authority and obscures consent, idempotency, evaluator independence, and total cost.

**Pass 1:** evidence-only recording preserves the new request-level payer contract and self-hosted runtime/security boundary without adopting either. Disadvantages: recurring review debt; no direct feature exposure; no live provider or billing verification; mutable documentation; unknown non-repository use. Response: add two unique files only, label exposure and evidence tier, pin dates/URLs/SHAs, and require separate authorized inventory before any implementation.

**Pass 2:** attack the design for bureaucracy, one-model self-review, self-hosting exceptionalism, silent payer fallback, misleading local-residency assumptions, queue-driven duplicate work, and incomplete cost evidence. Strengthening: keep draft status; make no protocol or runtime change; prohibit account linking and service deployment; require exact payer and service-topology binding, no-fallback semantics, receipt-gated retry, separate credentials, sandbox isolation, independent reconciliation/evaluation, and kill adoption on a second scheduler or missing residency/total-cost proof.

**Dissent:** the Adversarial Reviewer prefers brief-only reporting because neither feature is present on the default branches and existing section 7 already governs the invariants. That dissent controls scope. Request-level payer selection and a self-hosted provider agent loop/database/worker stack cross the materiality gate, so only dated evidence is added—no protocol amendment, adapter, deployment, provider call, account inspection, billing link, or migration.

## Verification, migration, rollback, and kill criteria

- **Verification:** official provider sources; exact searches on the four listed default heads; inspected open `main`-target pull requests for path overlap; schema validation of the deliberation; Canonical CI on the resulting draft head. No provider account, credential, invoice, or live API was accessed.
- **Migration:** none. Any future linked-billing proposal must pin the payer contract and prove consent, no-fallback replay, reconciliation, residency, and rollback. Any Managed Agents proposal must first prove architectural necessity and choose replacement or strict adapter mode; then pass isolated failure fixtures, independent evaluation, license/security review, residency/retention proof, total-cost comparison, and founder approval.
- **Rollback:** leave PR #105 unmerged or revert only the 2026-11-17 evidence commits while preserving historical evidence and dissent.
- **Kill:** any default-branch write or merge; account linking, credential, production, routing, spending, or authority change; silent payer fallback or double charging; a provider billing link treated as canonical consent/identity; self-hosted session/database/queue state treated as canonical; a second agent loop, scheduler, retry, evaluator, cost, or consequence plane; shell workers without isolation; retry after ambiguous completion without receipt/effect reconciliation; local-storage claims used as residency proof; missing total cost; or an immaterial recurring repository update.

